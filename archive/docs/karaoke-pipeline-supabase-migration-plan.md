# Karaoke Pipeline - Supabase Migration Plan

---

# ⚠️ DEBUGGING CHRONICLE (2026-01-02)

**Session Summary**: Debugging worker-claim-api bug reported by Claude Linux. Multiple issues discovered and partially fixed. Handoff notes for session resumption.

---

## Issues Encountered

### Issue 1: n8n Workflow Execution Crash - Type Mismatch
**Error**: `Wrong type: '401' is a number but was expecting a boolean [condition 0, item 0]`

**Root Cause**: The "IF Auth Valid" node used:
```json
{
  "operator": { "type": "boolean", "operation": "notExists" },
  "leftValue": "={{ $json.statusCode }}",
  "typeValidation": "strict"
}
```
When `statusCode` was 401 (a number), strict boolean validation crashed.

**Fix Applied**: Changed to check `$json.authenticated === true` with loose validation:
```json
{
  "operator": { "type": "boolean", "operation": "true" },
  "leftValue": "={{ $json.authenticated }}",
  "typeValidation": "loose"
}
```

**Status**: ✅ FIXED - committed `d76b8a2`, deployed to VPS

---

### Issue 2: Regex Double-Escaping in Bearer Token Matcher
**Error**: "Invalid Authorization format" for valid `Bearer <token>` headers

**Root Cause**: JSON contained `\\\\s` which became `\\s` in JavaScript (should be `\s`).

**Original (broken)**:
```javascript
authHeader.match(/^Bearer\\\\s+(.+)$/i)
```

**Fixed**:
```javascript
authHeader.match(/^Bearer\\s+(.+)$/i)
```

**Status**: ✅ FIXED - committed `d76b8a2`, deployed to VPS

---

### Issue 3: Missing WORKER_TOKEN Environment Variable
**Error**: Token validation always failed because `$env.WORKER_TOKEN` was undefined.

**Fix Applied**:
1. Generated token: `87d27295284d6a7e3c3ce7f3d4382b75`
2. Added to VPS `/root/.env`: `WORKER_TOKEN=87d27295284d6a7e3c3ce7f3d4382b75`
3. Added to VPS `docker-compose.yml` under n8n environment: `- WORKER_TOKEN=${WORKER_TOKEN:-}`
4. Restarted n8n container

**Status**: ✅ FIXED - VPS configured

---

### Issue 4: HTTP 200 Empty Body Instead of HTTP 204
**Symptom**: When no jobs are available, API returns HTTP 200 with empty body instead of HTTP 204 No Content.

**Investigation**:
- Workflow has correct structure: `IF Job Available` → false branch → `No Jobs 204` node
- `No Jobs 204` node configured correctly: `responseCode: 204`, `respondWith: "noData"`
- Auth flow works correctly (401 for invalid token, proceeds for valid)
- Airtable query succeeds (can see it executing)

**Current Theory**: Data flow not reaching the 204 node, OR response is being overridden somewhere.

**Status**: ❌ NOT FIXED - needs investigation

---

### Issue 5: n8n-MCP Tools Not Loading
**Symptom**: `/mcp` shows n8n-mcp as "Connected" but `mcp__n8n-mcp__*` tools return "No such tool available"

**Impact**: Forces manual SSH+curl debugging instead of using proper MCP tools.

**Status**: ❌ NOT FIXED - User will address before next session

---

## What Was Tried

| Action | Result | Commit/Location |
|--------|--------|-----------------|
| Fixed IF Auth Valid condition | Auth crash fixed | `d76b8a2` |
| Fixed regex escaping | Bearer parsing works | `d76b8a2` |
| Added WORKER_TOKEN to VPS | Token validation works | VPS `/root/.env` |
| Tested with curl | Auth works, but 200 empty instead of 204 | - |
| Checked execution logs | No errors visible after fixes | - |
| Verified 204 node exists | Node configuration looks correct | - |

---

## Current State

**Workflow ID on VPS**: `VlShzGUGSwbHkWcj`

**Working**:
- ✅ Webhook receives requests
- ✅ Bearer token extraction works
- ✅ Token validation works (401 for invalid, passes for valid)
- ✅ IF Auth Valid node doesn't crash

**Not Working**:
- ❌ 204 response for empty queue (getting 200 empty)
- ❌ Haven't tested with actual jobs in queue

**VPS Test Command**:
```bash
curl -v -X POST https://n8n.1215group.com/webhook/worker/claim \
  -H "Authorization: Bearer 87d27295284d6a7e3c3ce7f3d4382b75" \
  -H "Content-Type: application/json" \
  -d '{"workerId": "test-worker-123"}'
```

---

## Files Modified

| File | Changes |
|------|---------|
| `n8n-workflows/worker-claim-api.json` | IF condition fix, regex fix |
| VPS `/root/.env` | Added WORKER_TOKEN |
| VPS `docker-compose.yml` | Added WORKER_TOKEN to n8n env |

---

## Next Steps (for resumption)

1. **User sets up**:
   - n8n workflow skills/plugins
   - Supabase MCP server

2. **Then investigate 204 issue**:
   - Check if Airtable query returns empty array vs null
   - Check IF Job Available condition with empty array
   - May need to trace data flow step by step
   - Consider rebuilding workflow in n8n UI for cleaner debugging

3. **Alternative path**: Migrate to Supabase first (cleaner than debugging Airtable+n8n quirks)

---

## Archon Task Reference

**Bug Task ID**: `c29b34a5-dbbd-4ba4-b81d-5458b597e621`
**Status**: `review` (partially fixed, needs follow-up)

---

## Recommendation

**Migrate to Supabase** instead of continuing to debug Airtable workflow quirks. The 204 issue is likely a data shape problem (Airtable empty array vs null) that Supabase would handle more predictably with proper SQL.

---

# END DEBUGGING CHRONICLE

---

## Overview
Migrate the Karaoke Pipeline from Airtable to Supabase for improved reliability, SQL power, and cost efficiency. This replaces Phase 1 (Airtable schema) with a Supabase-native implementation.

---

## Why Supabase Over Airtable

| Factor | Airtable | Supabase |
|--------|----------|----------|
| **Reliability** | Rate limits, occasional API issues | PostgreSQL-backed, stable |
| **Query Power** | Formula-based filtering | Full SQL, indexes, views |
| **Real-time** | Polling only | WebSocket subscriptions |
| **Cost** | Per-seat pricing | Usage-based, generous free tier |
| **n8n Integration** | Native node | HTTP Request or Supabase node |
| **Archon Already Uses** | ❌ | ✅ (task management) |

---

## Current Airtable Dependencies

### 6 n8n Workflows to Migrate

| Workflow | Airtable Nodes | Operations |
|----------|----------------|------------|
| `worker-claim-api.json` | 2 | search (lease available), update (claim) |
| `worker-update-api.json` | 3 | search (get job), update (status), update (runpod status) |
| `karaoke-submit-api.json` | 1 | append (create job) |
| `karaoke-library-api.json` | 1 | search (published tracks) |
| `job-status-api.json` | 1 | search (job by ID) |
| `karaoke-publish.json` | 4 | search (get job), update (published), search (failed), update (failed) |

### Current Airtable Schema (KaraokeLibrary table)

```sql
-- Reconstructed from workflow analysis
JobID          TEXT PRIMARY KEY
Title          TEXT
Artist         TEXT
Slug           TEXT UNIQUE
SourceURL      TEXT
VideoID        TEXT
SourceType     TEXT  -- 'youtube' | 'upload'
ProcessingStatus TEXT  -- 'queued' | 'leased' | 'downloading' | 'uploaded_source' | 'runpod_processing' | 'published' | 'failed'
LeaseOwner     TEXT
LeaseUntil     TIMESTAMP
Attempts       INTEGER DEFAULT 0
LastError      TEXT
WorkerHeartbeatAt TIMESTAMP
Duration       INTEGER  -- seconds
PublicURL      TEXT
Created        TIMESTAMP DEFAULT NOW()
UpdatedAt      TIMESTAMP
```

---

## Supabase Migration Plan

### Phase M1: Supabase Setup (Priority: 100)
**Replaces Phase 1 (Airtable Schema)**

#### Tasks

| Task | Description | Assignee |
|------|-------------|----------|
| M1.1 | Create Supabase project (or use existing) | User |
| M1.2 | Create `karaoke_jobs` table with SQL migration | Windows |
| M1.3 | Create `karaoke_library` view (published only) | Windows |
| M1.4 | Add n8n credentials (Supabase API key + URL) | User |
| M1.5 | Add `SUPABASE_URL` and `SUPABASE_ANON_KEY` to n8n environment | User |

#### SQL Migration

```sql
-- Create karaoke_jobs table
CREATE TABLE public.karaoke_jobs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  job_id TEXT UNIQUE NOT NULL,
  title TEXT,
  artist TEXT,
  slug TEXT UNIQUE,
  source_url TEXT NOT NULL,
  video_id TEXT,
  source_type TEXT CHECK (source_type IN ('youtube', 'upload')) DEFAULT 'youtube',
  processing_status TEXT CHECK (processing_status IN (
    'queued', 'leased', 'downloading', 'uploaded_source',
    'runpod_processing', 'published', 'failed'
  )) DEFAULT 'queued',
  lease_owner TEXT,
  lease_until TIMESTAMPTZ,
  attempts INTEGER DEFAULT 0,
  last_error TEXT,
  worker_heartbeat_at TIMESTAMPTZ,
  duration INTEGER,
  public_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for worker claim queries
CREATE INDEX idx_karaoke_jobs_claim ON public.karaoke_jobs (processing_status, lease_until)
  WHERE processing_status = 'queued' OR lease_until < NOW();

-- Index for library queries
CREATE INDEX idx_karaoke_jobs_published ON public.karaoke_jobs (processing_status)
  WHERE processing_status = 'published';

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER karaoke_jobs_updated_at
  BEFORE UPDATE ON public.karaoke_jobs
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- View for published library
CREATE VIEW public.karaoke_library AS
SELECT
  id, job_id, title, artist, slug,
  duration, public_url, created_at
FROM public.karaoke_jobs
WHERE processing_status = 'published'
ORDER BY created_at DESC;

-- Enable Row Level Security (optional, for direct client access later)
ALTER TABLE public.karaoke_jobs ENABLE ROW LEVEL SECURITY;

-- Allow n8n service role full access
CREATE POLICY "Service role full access" ON public.karaoke_jobs
  FOR ALL USING (true) WITH CHECK (true);
```

### Phase M2: n8n Workflow Conversion (Priority: 90)

#### Conversion Pattern: Airtable → Supabase HTTP Request

**Before (Airtable node):**
```json
{
  "type": "n8n-nodes-base.airtable",
  "parameters": {
    "operation": "search",
    "base": { "value": "appxpg9NIjFsplDAH" },
    "table": { "value": "tbl938vOmNXD5iDx3" },
    "filterByFormula": "AND({ProcessingStatus} = 'queued', ...)"
  }
}
```

**After (HTTP Request to Supabase REST API):**
```json
{
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "GET",
    "url": "={{ $env.SUPABASE_URL }}/rest/v1/karaoke_jobs",
    "authentication": "genericCredentialType",
    "genericAuthType": "httpHeaderAuth",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "apikey", "value": "={{ $env.SUPABASE_ANON_KEY }}" },
        { "name": "Authorization", "value": "Bearer {{ $env.SUPABASE_ANON_KEY }}" },
        { "name": "Prefer", "value": "return=representation" }
      ]
    },
    "sendQuery": true,
    "queryParameters": {
      "parameters": [
        { "name": "processing_status", "value": "eq.queued" },
        { "name": "or", "value": "(lease_until.is.null,lease_until.lt.now())" },
        { "name": "order", "value": "created_at.asc" },
        { "name": "limit", "value": "1" }
      ]
    }
  }
}
```

#### Workflow Conversion Tasks

| Task | Workflow | Changes |
|------|----------|---------|
| M2.1 | `worker-claim-api.json` | Replace 2 Airtable nodes with Supabase HTTP |
| M2.2 | `worker-update-api.json` | Replace 3 Airtable nodes with Supabase HTTP |
| M2.3 | `karaoke-submit-api.json` | Replace 1 Airtable node with Supabase POST |
| M2.4 | `karaoke-library-api.json` | Replace 1 Airtable node with Supabase view query |
| M2.5 | `job-status-api.json` | Replace 1 Airtable node with Supabase GET |
| M2.6 | `karaoke-publish.json` | Replace 4 Airtable nodes with Supabase HTTP |

### Phase M3: Home Agent Update (Priority: 70)

Update `home-agent/karaoke-agent.py` - no changes needed if using n8n API endpoints. The agent talks to n8n webhooks, not Airtable directly.

### Phase M4: Testing & Cutover (Priority: 60)

| Task | Description |
|------|-------------|
| M4.1 | Deploy updated workflows to n8n (inactive) |
| M4.2 | Create test job via new submit endpoint |
| M4.3 | Verify home-agent claims job |
| M4.4 | Verify Runpod callback updates status |
| M4.5 | Verify publish workflow completes |
| M4.6 | Verify UI library shows published track |
| M4.7 | Cutover: Activate new workflows, deactivate old |

---

## Supabase Query Reference (PostgREST)

### Insert (POST)
```bash
POST /rest/v1/karaoke_jobs
Content-Type: application/json
Prefer: return=representation

{"job_id": "abc123", "source_url": "https://youtube.com/...", "title": "Song"}
```

### Select with filter (GET)
```bash
GET /rest/v1/karaoke_jobs?processing_status=eq.queued&limit=1&order=created_at.asc
```

### Update (PATCH)
```bash
PATCH /rest/v1/karaoke_jobs?job_id=eq.abc123
Content-Type: application/json
Prefer: return=representation

{"processing_status": "leased", "lease_owner": "worker-1"}
```

### Complex filter (lease expired OR queued)
```bash
GET /rest/v1/karaoke_jobs?or=(processing_status.eq.queued,lease_until.lt.now())
```

---

## n8n Environment Variables (Add to VPS)

```bash
# Supabase credentials (add to n8n container environment)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...your-anon-key
```

---

## Benefits of This Migration

1. **No more Airtable rate limits** - PostgreSQL handles concurrent claims
2. **Proper indexes** - Worker claim query is O(log n) not table scan
3. **Real-time option** - Could add Supabase Realtime for status updates
4. **Unified backend** - Archon already uses Supabase for task management
5. **SQL power** - Complex queries, views, functions available
6. **Cost savings** - No per-seat Airtable charges

---

## Rollback Plan

If issues arise:
1. Keep Airtable workflows as backup (rename with `-backup` suffix)
2. Airtable data remains untouched during migration
3. Can switch back by reactivating old workflows

---

## Migration Checklist

- [ ] Supabase project created/selected
- [ ] SQL migration applied
- [ ] n8n environment variables added
- [ ] `worker-claim-api.json` converted
- [ ] `worker-update-api.json` converted
- [ ] `karaoke-submit-api.json` converted
- [ ] `karaoke-library-api.json` converted
- [ ] `job-status-api.json` converted
- [ ] `karaoke-publish.json` converted
- [ ] End-to-end test passed
- [ ] Old Airtable workflows archived

---

# ORIGINAL PLAN BELOW (for reference)
# =====================================

---

## Multi-Machine Archon Workflow (NEW)

**Both machines share the same Archon project via Supabase sync.**

### Machine Roles

| Machine | Primary Focus | Archon Use |
|---------|--------------|------------|
| **Windows PC** | n8n workflows, VPS management, Runpod config | Assign tasks, track VPS-side work |
| **Linux PC** | home-agent dev, yt-dlp testing, local debugging | Claim tasks, report progress |

### Parallel Workflow

```
Windows Claude                    Archon (Supabase)                 Linux Claude
     │                                   │                               │
     │ manage_task(status="todo")        │                               │
     │──────────────────────────────────►│                               │
     │                                   │◄──────────────────────────────│
     │                                   │  find_tasks(status="todo")    │
     │                                   │                               │
     │                                   │  manage_task(status="doing")  │
     │                                   │◄──────────────────────────────│
     │                                   │                               │
     │  find_tasks() - sees "doing"      │                               │
     │◄──────────────────────────────────│                               │
     │                                   │                               │
     │                                   │  manage_task(status="done")   │
     │                                   │◄──────────────────────────────│
```

### Task Assignment Strategy

| Task Type | Assign To | Rationale |
|-----------|-----------|-----------|
| n8n workflow creation | Windows | Has n8n-mcp via SSH to VPS |
| Airtable schema | Windows | Has Airtable MCP |
| home-agent code | Linux | Native Python dev environment |
| yt-dlp testing | Linux | Residential IP for YouTube |
| Runpod deployment | Windows | API access, monitoring |
| End-to-end testing | Both | Coordinate via Archon |

### Handoff Pattern

1. **Windows**: Creates task, assigns to Linux (`assignee: "Linux"`)
2. **Linux**: `find_tasks(filter_by="assignee", filter_value="Linux")`
3. **Linux**: Works on task, updates status
4. **Windows**: Monitors progress, creates follow-up tasks

### Shared Knowledge Base

Both machines access the same RAG:
- `rag_search_knowledge_base()` - Same docs
- `rag_search_code_examples()` - Same examples
- Research done on one machine benefits both

---

## Pre-Implementation Setup

### Step 0.1: Create Archon Project
```bash
manage_project("create",
  title="Karaoke Pipeline - Distributed Processing MVP",
  description="Distributed karaoke processing: Home Agent (YouTube download) → Runpod GPU (Demucs) → VPS (publish). Lease-based job claiming, S3 handoff bus, multi-audio MP4 canonical artifact.",
  github_repo="https://github.com/mdc159/Hostinger"
)
```

### Step 0.2: Add Runpod Documentation to Archon RAG
Research and add Runpod API docs to knowledge base for future reference.

### Step 0.3: Update CLAUDE.md
Append Archon integration section (see detailed spec below).

---

## Phase 1: Airtable Schema Enhancement
**⚠️ DEPRECATED**: This phase is superseded by the Supabase migration. Airtable MCP has been removed from the project. See Phase 0 (Supabase Migration) for the current implementation approach.

**Feature**: `airtable-schema` | **Priority**: 100 (blocking all others) | **Status**: Deprecated

### Tasks
| Task | Description | Assignee |
|------|-------------|----------|
| 1.1 | Update ProcessingStatus choices: queued, leased, downloading, uploaded_source, runpod_processing, published, failed | User |
| 1.2 | Add SourceType field (Single Select: youtube, upload) | User |
| 1.3 | Add LeaseOwner (text), LeaseUntil (date), Attempts (number), WorkerHeartbeatAt (date) | User |
| 1.4 | Add LastError (long text), UpdatedAt (date) | User |
| 1.5 | Add VideoID (text) for YouTube video ID storage | User |

### Critical Files
- PRD Section 9: `Features/01-Karaoke/karaoke-pipeline-prd.md:321-353`

### Validation
- ~~Use `mcp__airtable__list_tables` to verify fields exist~~ (Airtable MCP removed)
- Create test record with all new fields

---

## Phase 2: n8n Worker API Endpoints
**Feature**: `n8n-worker-api` | **Priority**: 90

### Tasks
| Task | Description | Agent |
|------|-------------|-------|
| 2.1 | Design worker/claim endpoint architecture | User / codebase-analyst |
| 2.2 | Implement POST /api/worker/claim workflow | User |
| 2.3 | Design worker/update endpoint architecture | User / codebase-analyst |
| 2.4 | Implement POST /api/worker/update workflow | User |
| 2.5 | Test worker API | User |

### New Files to Create
- `n8n-workflows/worker-claim-api.json`
- `n8n-workflows/worker-update-api.json`

### Critical Files
- PRD Section 8.4-8.5: `Features/01-Karaoke/karaoke-pipeline-prd.md:293-305`
- Implementation plan: `Features/01-Karaoke/karaoke-pipeline-implementation-plan.md:52-82`

---

## Phase 3: Enhanced Submit & Library Endpoints
**Feature**: `n8n-submit-enhance` | **Priority**: 85

### Tasks
| Task | Description | Agent |
|------|-------------|-------|
| 3.1 | Refactor karaoke-submit: remove VPS download, create Supabase record only | User |
| 3.2 | Fix karaoke-library-api: add ProcessingStatus='published' filter | User |
| 3.3 | Fix job-status-api: add updatedAt field, correct status mapping | User |

### Files to Modify
- `n8n-workflows/karaoke-pipeline.json` (major refactor)
- `n8n-workflows/karaoke-library-api.json`
- `n8n-workflows/job-status-api.json`

---

## Phase 4: Runpod Worker Enhancement
**Feature**: `runpod-worker` | **Priority**: 80

### Tasks
| Task | Description | Agent/Assignee |
|------|-------------|----------------|
| 4.1 | Research Runpod S3 API patterns | User / codebase-analyst |
| 4.2 | Research FFmpeg multi-audio MP4 remux commands | library-researcher |
| 4.3 | Design handler.py rewrite spec | codebase-analyst |
| 4.4 | Implement handler.py with new processing flow | User |
| 4.5 | Update Dockerfile and requirements.txt | User |
| 4.6 | Test worker locally with sample MP4 | User |

### Files to Modify
- `runpod-demucs-worker/handler.py` (complete rewrite)
- `runpod-demucs-worker/Dockerfile`
- `runpod-demucs-worker/requirements.txt`

### Critical Files
- PRD Section 11: `Features/01-Karaoke/karaoke-pipeline-prd.md:411-430`
- Implementation plan: `Features/01-Karaoke/karaoke-pipeline-implementation-plan.md:108-200`

---

## Phase 5: Home Linux Agent
**Feature**: `home-agent` | **Priority**: 70

### Tasks
| Task | Description | Agent/Assignee |
|------|-------------|----------------|
| 5.1 | Research yt-dlp and boto3 patterns | library-researcher |
| 5.2 | Design home agent architecture | codebase-analyst |
| 5.3 | Create karaoke-agent.py (main worker loop) | User |
| 5.4 | Create karaoke-agent.service (systemd) | User |
| 5.5 | Create install.sh (setup script) | User |
| 5.6 | Create env.example | User |
| 5.7 | Write README.md (setup docs) | User |

### New Directory Structure
```
home-agent/
├── karaoke-agent.py
├── karaoke-agent.service
├── install.sh
├── env.example
└── README.md
```

### Home PC Dependencies (needs setup)
- Python 3.10+
- yt-dlp
- ffmpeg
- boto3
- requests

---

## Phase 6: VPS Publishing Workflow
**Feature**: `vps-publish` | **Priority**: 60

### Tasks
| Task | Description | Agent |
|------|-------------|-------|
| 6.1 | Design publish workflow architecture | User / codebase-analyst |
| 6.2 | Implement karaoke-publish workflow | User |
| 6.3 | End-to-end pipeline test | User |

### New Files
- `n8n-workflows/karaoke-publish.json`

---

## Context Window Optimization Strategy

### MCP Server Management by Phase

| Phase | Keep Enabled | Can Disable | Rationale |
|-------|--------------|-------------|-----------|
| 0 (Setup) | archon | n8n-mcp, airtable | Project/task creation only |
| 1 (Airtable) | airtable, archon | n8n-mcp | Schema changes only |
| 2-3 (n8n) | n8n-mcp, airtable, archon | - | Full workflow building |
| 4-5 (Python) | archon | n8n-mcp, airtable | Pure Python coding |
| 6 (Integration) | ALL | - | End-to-end testing |

### Disable Greptile MCP
The `greptile` MCP server is not needed for this implementation - it focuses on PR/code review which isn't our primary workflow. Can be disabled to save context.

### Skill Loading Strategy
Only load n8n skills when working on Phases 2-3 and 6:
- `n8n-code-javascript`
- `n8n-expression-syntax`
- `n8n-validation-expert`
- `n8n-workflow-patterns`
- `n8n-node-configuration`

---

## CLAUDE.md Integration (Append This Section)

```markdown
## Archon Project Management

**CRITICAL: Use Archon MCP for task management. This overrides TodoWrite.**

### Karaoke Pipeline Project
- **Find project**: `find_projects(query="karaoke")`
- **Get tasks**: `find_tasks(project_id="<PROJECT_ID>")`

### Task Workflow (MANDATORY)
1. **Get next task**: `find_tasks(filter_by="status", filter_value="todo")`
2. **Start work**: `manage_task("update", task_id="...", status="doing")`
3. **Research first**: `rag_search_knowledge_base(query="...", match_count=5)`
4. **Complete work**: `manage_task("update", task_id="...", status="done")`

### Feature Groups (by priority)
| Feature | Priority | Description |
|---------|----------|-------------|
| airtable-schema | 100 | Airtable field setup |
| n8n-worker-api | 90 | Worker claim/update endpoints |
| n8n-submit-enhance | 85 | Submit workflow refactor |
| runpod-worker | 80 | GPU processing handler |
| home-agent | 70 | YouTube download agent |
| vps-publish | 60 | Publishing workflow |

### RAG Before Implementation
Always search knowledge base before coding:
```bash
rag_search_knowledge_base(query="runpod s3", source_id="...")
rag_search_code_examples(query="n8n webhook", match_count=3)
```
```

---

## Agent Orchestration Summary

### By Phase
| Phase | Primary Agents | Purpose |
|-------|---------------|---------|
| 2-3 | codebase-analyst → User | Design, build, test n8n workflows |
| 4 | codebase-analyst → User | Research APIs and patterns for Runpod worker |
| 5 | codebase-analyst → User | Research patterns for home agent |
| 6 | codebase-analyst → User | Build and test publish workflow |

### Agent Usage Pattern
```
1. ARCHITECT designs blueprint (read-only, produces spec)
2. BUILDER implements from blueprint (creates/modifies workflows)
3. TESTER validates endpoints (webhook testing)
4. DEBUGGER diagnoses failures (if issues arise)
```

---

## Validation Gates

### Phase 1: Airtable
- [ ] All 5 new fields exist in KaraokeLibrary table
- [ ] ProcessingStatus has all 7 choices
- [ ] Test record creates successfully

### Phase 2: Worker API
- [ ] POST /api/worker/claim returns job with token
- [ ] POST /api/worker/claim returns 204 when empty
- [ ] POST /api/worker/update transitions status correctly
- [ ] Status=uploaded_source triggers Runpod

### Phase 4: Runpod Worker
- [ ] Handler accepts MP4 input
- [ ] Produces karaoke_six_stem.mp4 with 6 audio tracks
- [ ] Produces stems.json matching UI contract
- [ ] All artifacts upload to S3

### Phase 5: Home Agent
- [ ] Agent claims jobs from VPS API
- [ ] yt-dlp downloads succeed
- [ ] S3 upload succeeds
- [ ] Status updates work

### Phase 6: End-to-End
- [ ] Submit YouTube URL
- [ ] Home agent downloads
- [ ] Runpod processes
- [ ] VPS publishes
- [ ] UI plays with all stems

---

## Execution Order

1. **Step 0**: Setup (Archon project, Runpod docs, CLAUDE.md update)
2. **Phase 1**: Airtable schema (blocking - must complete first)
3. **Phase 2-3**: n8n endpoints (can partially parallel with Phase 4)
4. **Phase 4-5**: Runpod worker and Home agent (can parallel)
5. **Phase 6**: Publishing and integration testing

---

## Quick Reference: Archon Task Commands

```bash
# List all karaoke tasks
find_tasks(project_id="<PROJECT_ID>", filter_by="status", filter_value="todo")

# Start a task
manage_task("update", task_id="<TASK_ID>", status="doing")

# Complete a task
manage_task("update", task_id="<TASK_ID>", status="done")

# Create new task
manage_task("create",
  project_id="<PROJECT_ID>",
  feature="airtable-schema",
  title="Add ProcessingStatus choices",
  description="Update field with: queued, leased, downloading, uploaded_source, runpod_processing, published, failed",
  task_order=100
)
```

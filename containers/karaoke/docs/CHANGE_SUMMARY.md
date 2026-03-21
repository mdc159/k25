2# Karaoke Containerization - Change Summary

**Date**: 2026-01-06
**Archon Project**: `2d3bd6e1-4831-4edc-839e-a8c5a2fa6025`

---

## What Was Changed

### 1. Docker Container Infrastructure

Created containerized deployment for the karaoke pipeline:

| File | Purpose |
|------|---------|
| `containers/karaoke/docker-compose.yml` | Orchestrates home-agent and karaoke-ui containers |
| `containers/karaoke/home-agent/Dockerfile` | Python 3.11 + yt-dlp + ffmpeg for YouTube downloads |
| `containers/karaoke/home-agent/requirements.txt` | Python dependencies (boto3, requests, pydantic) |
| `containers/karaoke/karaoke-ui/Dockerfile` | Multi-stage build: Node 22 builder + nginx alpine |
| `containers/karaoke/karaoke-ui/nginx.conf` | SPA routing with gzip and cache headers |
| `containers/karaoke/.env.example` | Environment template (deprecated - use root .env) |

### 2. Home-Agent Code Updates (`home-agent/karaoke-agent.py`)

**Environment Variable Compatibility**:
```python
# Now supports both AWS_* (preferred) and RUNPOD_* (legacy) naming
self.s3_endpoint = get_env("AWS_S3_ENDPOINT", os.getenv("RUNPOD_S3_ENDPOINT"))
self.s3_bucket = get_env("AWS_S3_BUCKET", os.getenv("RUNPOD_BUCKET"))
self.supabase_key = get_env("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_SERVICE_KEY"))
```

**Heartbeat Table Change**:
- Changed from `worker_health` to `worker_heartbeats` table
- Added `on_conflict=worker_id` for proper upsert
- Added circuit breaker state reporting (`s3_circuit_breaker`, `api_circuit_breaker`)
- Added `capabilities` field for feature flags

**Capabilities Support**:
```python
self.capabilities = {"stem_splitting": self.stem_splitting_enabled}
```

### 3. Dashboard UI Updates (`apps/karaoke-ui/`)

- Added `'dashboard'` to drawer type in `useStore.ts`
- Added capabilities toggle to `WorkerStatusCard.tsx`
- Fixed TypeScript build errors (unused imports)

### 4. n8n Workflow Updates

- Created `worker-capabilities-api.json` for PATCH `/webhook/worker/capabilities`
- Updated `worker-update-api.json` with `skipRunpod` flag support

### 5. Database Migration

Added `capabilities` column to `worker_heartbeats` table:
```sql
ALTER TABLE worker_heartbeats
ADD COLUMN capabilities jsonb DEFAULT '{"stem_splitting": true}'::jsonb;
```

---

## Why These Changes Were Made

### Single Environment File
- **Problem**: Multiple `.env` files across containers caused sync issues and credential duplication
- **Solution**: All containers use root `../../.env` via `env_file` directive
- **Benefit**: One source of truth, easy VPS sync via git

### Environment Variable Naming
- **Problem**: Agent used `RUNPOD_*` names but root `.env` uses `AWS_*` convention
- **Solution**: Agent now accepts both, preferring `AWS_*`
- **Benefit**: Backward compatibility + cleaner naming

### Heartbeat Table
- **Problem**: Dashboard expected `worker_heartbeats` schema, agent wrote to `worker_health`
- **Solution**: Updated agent to use `worker_heartbeats` with correct column names
- **Benefit**: Dashboard displays worker status correctly

### Capabilities Field
- **Problem**: No way to enable/disable features per worker
- **Solution**: Added `capabilities` jsonb field with `stem_splitting` toggle
- **Benefit**: Download-only nodes can skip Runpod GPU processing

---

## Assumptions Made

### 1. Root `.env` Is Authoritative
All credentials and configuration come from `/mnt/x/GitHub/Hostinger/.env`. This file is assumed to:
- Exist on all deployment nodes
- Be synced via git or other mechanism
- Contain valid Supabase and AWS credentials

### 2. Port 8082 Is Available
Karaoke UI runs on port 8082, assuming:
- Port 8080 is used by open-webui
- Port 8081 is used by searxng
- No other service conflicts

### 3. Worker ID Uniqueness
Each node must set a unique `WORKER_ID` in environment. Default is `home-agent-docker` which should be overridden per node.

### 4. Supabase Schema Is Current
The `worker_heartbeats` table must have:
- `capabilities` column (jsonb)
- `s3_circuit_breaker` column
- `api_circuit_breaker` column
- Unique constraint on `worker_id`

### 5. n8n Workflows Are Deployed
The following workflows must be active:
- `worker-claim-api` - Job claiming
- `worker-update-api` - Status updates (with skipRunpod support)
- `worker-capabilities-api` - Capability updates

---

## What Remains TODO

### High Priority

- [ ] **Test YouTube download end-to-end**: Submit a job and verify full pipeline
- [ ] **Test S3 upload**: Verify credentials work for `karaoke-pimpshizzle` bucket
- [ ] **Test multi-node**: Deploy on second machine with different WORKER_ID
- [ ] **Dashboard integration test**: Verify workers show in UI with capabilities toggle

### Medium Priority

- [ ] **Add STEM_SPLITTING_ENABLED to root .env**: Currently defaults to `true`
- [ ] **Clean up deprecated .env files**: Remove `containers/karaoke/.env.example` references
- [ ] **Add Prometheus metrics endpoint**: For Grafana monitoring
- [ ] **Add container logging to file**: Currently stdout only

### Low Priority

- [ ] **Health check improvements**: Add actual job processing health, not just HTTP
- [ ] **Auto-scaling documentation**: How to add/remove nodes dynamically
- [ ] **CI/CD pipeline**: Automate container builds on push
- [ ] **Remove deprecated `worker_health` table**: Migrate any remaining references

### Known Issues

1. **First heartbeat may fail**: If `worker_heartbeats` row doesn't exist, first POST creates it. Subsequent upserts work fine.

2. **Dashboard polling**: UI polls every 3 seconds which may be aggressive for production.

3. **No graceful shutdown propagation**: Container stop doesn't notify Supabase the worker is offline.

---

## Deployment Checklist

```bash
# On any node:
cd /path/to/Hostinger/containers/karaoke

# 1. Ensure root .env exists with credentials
cat ../../.env | grep -E "^(AWS_|SUPABASE_|VPS_|WORKER_)" | wc -l
# Should show ~10+ variables

# 2. Set unique WORKER_ID (edit root .env or export)
export WORKER_ID=home-agent-$(hostname)

# 3. Build and start
docker compose up -d --build

# 4. Verify
docker ps --filter "name=karaoke"
# Both should show "healthy"

# 5. Check logs
docker logs karaoke-home-agent | tail -20
# Should show "Karaoke Agent initialized" with no errors

# 6. Access UI
curl -s http://localhost:8082/ | head -5
# Should return HTML
```

---

## File Reference

```
Hostinger/
├── .env                          # Single source of truth for all credentials
├── containers/karaoke/
│   ├── docker-compose.yml        # Main orchestration
│   ├── docs/
│   │   └── CHANGE_SUMMARY.md     # This file
│   ├── home-agent/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── karaoke-ui/
│       ├── Dockerfile
│       └── nginx.conf
├── home-agent/
│   └── karaoke-agent.py          # Updated with AWS_* support
├── apps/karaoke-ui/              # React dashboard
└── n8n-workflows/karaoke-pipeline/
    ├── worker-capabilities-api.json
    └── worker-update-api.json
```

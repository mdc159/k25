# Karaoke Pipeline Implementation Plan

## Overview

Implement the distributed karaoke pipeline per PRD at `Features/01-Karaoke/karaoke-pipeline-prd.md`:
- **Home Linux Agent** downloads from YouTube (bypasses VPS IP blocking)
- **Runpod Serverless GPU** processes with Demucs and produces canonical multi-audio MP4
- **VPS** publishes outputs and maintains Airtable library

## Scope: MVP (Phases 1-4)

**In Scope:**
- Phase 1: Airtable schema + core n8n endpoints
- Phase 2: Runpod worker enhancement (multi-audio MP4)
- Phase 3: Home Linux agent
- Phase 4: VPS publishing workflow

**Deferred (Post-MVP):**
- Phase 5: Manual upload path (presigned URLs)
- Phase 6: Ops hardening (lease expiration cron, heartbeat monitor)

**Assumptions:**
- Runpod credentials ready (S3 endpoint, keys, serverless endpoint)
- Home Linux PC available for agent deployment
- Generate new worker auth token

---

## Phase 1: Airtable Schema & Core n8n Endpoints (CRITICAL)

**Goal**: Establish foundation for distributed worker system

### 1.1 Airtable Schema Enhancement

Add missing fields to `KaraokeLibrary` table (Base: `appxpg9NIjFsplDAH`, Table: `tbl938vOmNXD5iDx3`):

| Field | Type | Purpose |
|-------|------|---------|
| `SourceType` | Single Select (youtube, upload) | Track source origin |
| `LastError` | Long Text | Error message storage |
| `UpdatedAt` | Date | Last modification timestamp |
| `LeaseOwner` | Text | Worker ID holding lease |
| `LeaseUntil` | Date | Lease expiration time |
| `Attempts` | Number | Retry counter |
| `WorkerHeartbeatAt` | Date | Last heartbeat from worker |

Update `ProcessingStatus` choices to match PRD state machine:
- `queued` → `leased` → `downloading` → `uploaded_source` → `runpod_processing` → `published` → `failed`

### 1.2 Worker Claim Endpoint

**New file**: `n8n-workflows/worker-claim-api.json`

```
POST /api/worker/claim
Auth: Bearer WORKER_TOKEN
Response: 204 (no job) OR 200 {jobId, url, runpodBucket, runpodInputKey, outputPrefix, slugHint, leaseUntil}
```

Logic:
1. Validate bearer token
2. Query Airtable: `ProcessingStatus=queued AND (LeaseUntil < NOW() OR LeaseUntil IS EMPTY)`
3. If no job: return 204
4. Update job: `ProcessingStatus=leased`, `LeaseOwner=workerId`, `LeaseUntil=NOW()+5min`, `Attempts+=1`
5. Return job details

### 1.3 Worker Update Endpoint

**New file**: `n8n-workflows/worker-update-api.json`

```
POST /api/worker/update
Auth: Bearer WORKER_TOKEN
Body: {jobId, status, message?, inputKey?, heartbeat?}
```

Logic:
1. Validate bearer token
2. Update Airtable record by JobID
3. If `status=uploaded_source`: Trigger Runpod serverless job
4. If `heartbeat=true`: Update `WorkerHeartbeatAt=NOW()`

### 1.4 Enhanced Submit Endpoint

**Modify**: `n8n-workflows/karaoke-pipeline.json`

Current flow processes locally. New flow:
```
Webhook → Generate JobID → Airtable Create (status=queued, sourceType=youtube) → Respond 202
```

Remove VPS download/processing nodes (handled by home agent + Runpod).

### 1.5 Fix Library Endpoint

**Modify**: `n8n-workflows/karaoke-library-api.json`

Add filter: `{ProcessingStatus} = 'published'` to only return ready tracks.

### 1.6 Fix Job Status Endpoint

**Modify**: `n8n-workflows/job-status-api.json`

Add `updatedAt` field to response. Map status values correctly.

---

## Phase 2: Runpod Worker Enhancement (CRITICAL)

**Goal**: Produce canonical multi-audio MP4 + derived web assets

**Modify**: `runpod-demucs-worker/handler.py`

### Current State (Gaps)
- Expects WAV input (line 67: `input_path = in_dir / "input.wav"`)
- Only produces stems + basic `stems.json` with `{job_id, format, stems: [{id, file}]}`
- Missing: video extraction, video.mp4, karaoke_six_stem.mp4, correct manifest schema

### New Processing Flow

```python
def handler(job):
    # Input: source.mp4 (video with audio)

    # 1. Download source.mp4 from S3

    # 2. Extract audio to WAV for Demucs
    # ffmpeg -i source.mp4 -vn -acodec pcm_s16le -ar 44100 audio.wav

    # 3. Extract video-only track (for web UI)
    # ffmpeg -i source.mp4 -an -c:v copy video.mp4

    # 4. Get metadata (duration, title if embedded)
    # ffprobe -v quiet -print_format json -show_format source.mp4

    # 5. Run Demucs separation (produces 6 WAV stems)
    # python -m demucs -n htdemucs_6s --out stems/ audio.wav

    # 6. Encode stems to AAC m4a (for web UI)
    # ffmpeg -i stem.wav -c:a aac -b:a 192k stem.m4a

    # 7. Create canonical multi-audio MP4 (PRD Section 7.1)
    # ffmpeg -hide_banner -y \
    #   -i video.mp4 \
    #   -i vocals.wav -i drums.wav -i bass.wav -i guitar.wav -i piano.wav -i other.wav \
    #   -map 0:v \
    #   -map 1:a -metadata:s:a:0 handler_name="Vocals" \
    #   -map 2:a -metadata:s:a:1 handler_name="Drums" \
    #   -map 3:a -metadata:s:a:2 handler_name="Bass" \
    #   -map 4:a -metadata:s:a:3 handler_name="Guitar" \
    #   -map 5:a -metadata:s:a:4 handler_name="Piano" \
    #   -map 6:a -metadata:s:a:5 handler_name="Ambience" \
    #   -c:v copy -c:a aac -b:a 256k -movflags +faststart \
    #   -disposition:a:0 none \
    #   karaoke_six_stem.mp4

    # 8. Generate stems.json matching UI contract (apps/karaoke-ui/src/types/karaoke.ts)
    manifest = {
        "title": metadata.get("title", "Unknown"),
        "artist": metadata.get("artist", "Unknown"),
        "duration": probe_duration,
        "video": "video.mp4",
        "sourceUrl": job_metadata.get("sourceUrl"),
        "videoId": job_metadata.get("videoId"),
        "stems": [
            {"id": "vocals", "name": "vocals", "file": "vocals.m4a", "default_gain": 1.0},
            {"id": "drums", "name": "drums", "file": "drums.m4a", "default_gain": 1.0},
            {"id": "bass", "name": "bass", "file": "bass.m4a", "default_gain": 1.0},
            {"id": "guitar", "name": "guitar", "file": "guitar.m4a", "default_gain": 1.0},
            {"id": "piano", "name": "piano", "file": "piano.m4a", "default_gain": 1.0},
            {"id": "other", "name": "other", "file": "other.m4a", "default_gain": 1.0}
        ]
    }

    # 9. Upload all outputs to S3:
    #    - karaoke_six_stem.mp4 (canonical)
    #    - video.mp4 (video-only)
    #    - 6x stem.m4a files
    #    - stems.json
```

### New Input Schema

```json
{
  "input": {
    "job_id": "recXXXX",
    "bucket": "n6tzw6zfhk",
    "input_key": "karaoke/in/recXXXX/source.mp4",
    "output_prefix": "karaoke/out/recXXXX/",
    "model": "htdemucs_6s",
    "metadata": {
      "title": "Song Title",
      "artist": "Artist Name",
      "sourceUrl": "https://youtube.com/...",
      "videoId": "dQw4w9WgXcQ"
    }
  }
}
```

---

## Phase 3: Home Linux Agent (CRITICAL)

**Goal**: Download YouTube videos from residential IP

**New directory**: `home-agent/`

### Files to Create

| File | Purpose |
|------|---------|
| `home-agent/karaoke-agent.py` | Main worker loop |
| `home-agent/karaoke-agent.service` | systemd unit file |
| `home-agent/env.example` | Environment template |
| `home-agent/install.sh` | Installation script |
| `home-agent/README.md` | Setup documentation |

### Worker Loop Logic (karaoke-agent.py)

```python
while True:
    # 1. POST /api/worker/claim → get job or 204
    # 2. If job:
    #    a. Update status: downloading
    #    b. yt-dlp download to local spool
    #    c. Upload to Runpod S3: karaoke/in/{jobId}/source.mp4
    #    d. Update status: uploaded_source (triggers Runpod)
    #    e. Cleanup local file
    # 3. Sleep POLL_INTERVAL seconds
```

### systemd Service

```ini
[Unit]
Description=Karaoke Home Agent
After=network.target

[Service]
Type=simple
EnvironmentFile=/etc/karaoke-agent/env
ExecStart=/usr/bin/python3 /opt/karaoke-agent/karaoke-agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Environment Variables

```bash
VPS_API_BASE=https://karaoke.1215group.com/api
WORKER_TOKEN=<secret>
RUNPOD_S3_ENDPOINT=https://s3api-us-ca-2.runpod.io
RUNPOD_BUCKET=n6tzw6zfhk
RUNPOD_S3_KEY=<key>
RUNPOD_S3_SECRET=<secret>
POLL_INTERVAL_SECONDS=30
DOWNLOAD_DIR=/var/lib/karaoke-agent/spool
```

---

## Phase 4: VPS Publishing Workflow

**Goal**: Pull processed outputs from S3 and publish to web server

**New file**: `n8n-workflows/karaoke-publish.json`

### Trigger Options
1. Runpod completion webhook callback
2. n8n schedule polling S3 for completed jobs

### Flow
```
Trigger → Download from S3 (all outputs)
       → Write to /var/www/karaoke/videos/{slug}/
       → Update Airtable (status=published, PublicURL=...)
       → Optional: Cleanup S3 outputs
```

### Output Directory Structure
```
/var/www/karaoke/videos/{slug}/
├── karaoke_six_stem.mp4   (canonical portable artifact)
├── video.mp4              (video-only for web mixer)
├── vocals.m4a
├── drums.m4a
├── bass.m4a
├── guitar.m4a
├── piano.m4a
├── other.m4a
└── stems.json
```

---

## Deferred: Phase 5 & 6 (Post-MVP)

These phases are documented for future reference but not in MVP scope:

- **Phase 5**: Manual upload path (presigned S3 URLs for direct browser upload)
- **Phase 6**: Ops hardening (lease expiration cron, heartbeat monitoring, alerting)

---

## File Inventory (MVP Scope)

### New Files
| Path | Description |
|------|-------------|
| `home-agent/karaoke-agent.py` | Home agent main script |
| `home-agent/karaoke-agent.service` | systemd unit |
| `home-agent/env.example` | Environment template |
| `home-agent/install.sh` | Installation script |
| `home-agent/README.md` | Setup documentation |
| `n8n-workflows/worker-claim-api.json` | Claim endpoint |
| `n8n-workflows/worker-update-api.json` | Update endpoint |
| `n8n-workflows/karaoke-publish.json` | VPS publish workflow |

### Files to Modify
| Path | Changes |
|------|---------|
| `runpod-demucs-worker/handler.py` | Full rewrite: MP4 input, video extraction, multi-audio remux, correct stems.json |
| `n8n-workflows/karaoke-pipeline.json` | Remove VPS processing, add Airtable-only creation |
| `n8n-workflows/karaoke-library-api.json` | Add status=published filter |
| `n8n-workflows/job-status-api.json` | Add updatedAt, fix status mapping |
| `DEVELOPMENT.md` | Mark Bright Data plan as deprecated |

---

## Validation Criteria (MVP)

### Phase 1
- [ ] All new Airtable fields exist
- [ ] POST /api/worker/claim returns job or 204
- [ ] POST /api/worker/update transitions states correctly
- [ ] POST /api/karaoke-submit creates queued job in Airtable

### Phase 2
- [ ] Runpod worker accepts MP4 input
- [ ] video.mp4 (video-only) produced
- [ ] karaoke_six_stem.mp4 has 1 video + 6 audio tracks with metadata
- [ ] stems.json matches `StemsManifest` interface exactly

### Phase 3
- [ ] Home agent claims jobs
- [ ] yt-dlp downloads succeed
- [ ] Upload to S3 succeeds
- [ ] Status transitions work: queued → leased → downloading → uploaded_source

### Phase 4
- [ ] VPS pulls outputs from S3
- [ ] Files written to /var/www/karaoke/videos/{slug}/
- [ ] Airtable updated to status=published
- [ ] React UI can load and play track

### End-to-End Test
- [ ] Submit YouTube URL via UI
- [ ] Home agent picks up job and downloads
- [ ] Runpod processes and produces all artifacts
- [ ] VPS publishes to web server
- [ ] UI can play track with all 6 stems + video

---

## Implementation Order

1. **Phase 1** (Foundation) - Must complete first
2. **Phase 2** (Runpod Worker) - Can start in parallel with Phase 3
3. **Phase 3** (Home Agent) - Can start in parallel with Phase 2
4. **Phase 4** (Publishing) - Requires Phase 2 complete

**Recommended approach**: Complete Phase 1, then work on Phase 2 and 3 in parallel, then Phase 4.

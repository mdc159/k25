# Karaoke Pipeline PRD — Canonical (CloudFront + Private S3 + Lean Home Node)

**Version:** 3.0  
**Last Updated:** 2026-01-11  
**Status:** Active Implementation  
**Canon:** This document supersedes prior PRD phrasing that implied publishing primarily to VPS filesystem.

## Executive Summary

A distributed karaoke processing pipeline that:

- Accepts a YouTube URL (or upload) via the VPS Karaoke UI.
- Uses n8n on the VPS as the control plane to create and manage jobs in Supabase.
- Uses a lean Home Node worker (residential IP) to download YouTube and either:
  - split stems locally (free path), or
  - upload source to S3 for RunPod serverless GPU processing (paid path).
- Writes all intermediate artifacts to AWS S3 staging prefixes.
- Promotes artifacts from S3 staging → S3 public in a deterministic publish step.
- Serves published assets via CloudFront (private S3 via OAC) to the Karaoke player UI.
- Provides operator visibility via a Pipeline Dashboard endpoint and delivers alerts via Slack.

**Key principle:** Control plane lives on VPS. Data plane work happens on the Home Node and/or RunPod. S3 is the shared artifact bus.

## Non-Negotiables

### Security posture

- S3 bucket is private and served via CloudFront OAC.
- Do not propose making the bucket public.
- Do not require presigned URLs for public playback.

### Separation of concerns

- **VPS:** orchestration, DB, publish, monitoring, dashboards.
- **Home Node:** yt-dlp, ffmpeg, optional demucs, S3 upload, webhook updates.
- **RunPod:** optional compute fallback only (demucs + ffmpeg + callback).

### Determinism and idempotency

- S3 key conventions are fixed and must be followed exactly.
- Publish step is idempotent (safe to re-run; overwrites the same public keys).

System Roles
1) VPS (Control Plane)

Runs:

n8n workflows (submit / claim / update / dashboard / monitors / publish)

Supabase job queue and library

Publish script (staging → public)

Slack notifications (pipeline monitors)

Karaoke UI frontend (served at https://karaoke.1215group.com) 

README

Does not:

download from YouTube (datacenter IP blocks)

run GPU demucs workloads

2) Home Node (Lean Worker)

Runs:

yt-dlp download (residential IP)

ffmpeg

demucs (optional; only for local split path)

optional lightweight local dashboard for worker status/toggles

Does not:

run n8n

run OpenWebUI / Ollama / “full VPS stack”

talk directly to Supabase (no DB credentials on home node)

Home node talks to VPS only via n8n webhook endpoints + S3 API.

3) RunPod Serverless GPU (Optional)

Runs:

demucs htdemucs_6s (6 stems)

ffmpeg packaging tasks

uploads staging outputs to S3

calls back to VPS webhook when outputs are ready

### 4) AWS S3 + CloudFront

- **Bucket:** `karaoke-pimpshizzle`
- CloudFront distribution serves `karaoke/pub/{slug}/...` paths securely (private bucket via OAC).

## Canonical S3 Layout (Authoritative)

All components must use this layout exactly.

### A) Staging Inputs (job-scoped)

```
karaoke/in/{job_id}/source.mp4
karaoke/in/{job_id}/metadata.json (yt-dlp JSON; recommended)
```

### B) Staging Outputs (job-scoped)

```
karaoke/out/{job_id}/video.mp4
karaoke/out/{job_id}/manifest.json
karaoke/out/{job_id}/stems/vocals.wav
karaoke/out/{job_id}/stems/drums.wav
karaoke/out/{job_id}/stems/bass.wav
karaoke/out/{job_id}/stems/guitar.wav
karaoke/out/{job_id}/stems/piano.wav
karaoke/out/{job_id}/stems/other.wav
karaoke/out/{job_id}/karaoke_six_stem.mp4 (optional; if produced)
```

### C) Public Library Outputs (slug-scoped)

Promoted by the publish step:

```
karaoke/pub/{slug}/video.mp4
karaoke/pub/{slug}/stems/vocals.m4a
karaoke/pub/{slug}/stems/drums.m4a
karaoke/pub/{slug}/stems/bass.m4a
karaoke/pub/{slug}/stems/guitar.m4a
karaoke/pub/{slug}/stems/piano.m4a
karaoke/pub/{slug}/stems/shizzle.m4a (renamed from other)
karaoke/pub/{slug}/stems.json
```

## Supabase Ownership and Worker Isolation

- Supabase is authoritative for jobs and library.
- Only the VPS control plane writes to Supabase directly.
- Home Node never needs Supabase keys.
- Home Node communicates job progress through VPS webhooks (claim/update/capabilities/heartbeat style).

## API Contracts (n8n Webhooks)

### Submit (UI → VPS)

- `POST /webhook/karaoke-submit` creates a job in Supabase and returns `job_id`.
- UI opens a progress stepper modal and polls job status.

### Worker Claim (Home Node → VPS)

- `POST /webhook/worker/claim`
- returns either `204` (no jobs) or job payload including `job_id`, `source_url`, and S3 key prefixes.

### Worker Update (Home Node → VPS)

- `POST /webhook/worker/update`
- used for status transitions and reporting "facts" (download complete, uploaded_source, uploaded_outputs, errors, etc.)

### Dashboard (Operator UI → VPS)

- `GET /webhook/dashboard`
- read-only aggregation for pipeline monitoring UI.

## UX Requirements

### 1) Main Karaoke UI: Add Source Progress Modal

When a user drops a URL, show a lightweight stepper:

```
Queued → Downloading → Extracting Audio → Separating Stems → Encoding → Complete
```

- Must support "Run in Background"
- Driven by polling a VPS job-status API (or equivalent) rather than reading S3 directly.
- (Implementation detail: the backend may map richer job statuses to these UX stages.)

### 2) Home Node: Lightweight Worker Dashboard (Optional)

Allowed and desired if it stays lean:

- local-only (localhost)
- shows worker state + last job + toggle like "local split ON/OFF"
- does not require n8n or Supabase locally
- does not become a full karaoke UI

## Processing Flow (Canonical)

### Phase 0 — Submit (VPS)

1. UI submits URL.
2. VPS creates job record in Supabase: `queued`.
3. UI receives `job_id` and begins progress modal.

### Phase 1 — Lease (Home Node via VPS)

1. Home Node polls `worker/claim`.
2. VPS leases job to worker: `leased`, sets lease owner/expiry.

### Phase 2 — Download (Home Node)

1. Home Node updates: `downloading`.
2. Downloads source via yt-dlp (residential IP).
3. Captures metadata JSON (recommended).

### Phase 3 — Decide split path (Home Node)

**Decision inputs:**

- job preference (e.g., prefer local split)
- worker capability (has GPU? demucs available? local toggle?)

#### A) Local Split Path (Free)

1. Update: `processing_local`.
2. Run demucs locally.
3. Upload staging outputs directly to: `karaoke/out/{job_id}/...`
4. Update: `uploaded_outputs`.

#### B) RunPod Path (Paid)

1. Upload staging input to:
   - `karaoke/in/{job_id}/source.mp4`
   - optionally `metadata.json`
2. Update: `uploaded_source`.
3. VPS triggers RunPod job, sets status: `runpod_processing`.
4. RunPod writes staging outputs to `karaoke/out/{job_id}/...`
5. RunPod calls back to VPS → status: `outputs_ready`.

### Phase 4 — Publish (VPS)

1. VPS sets status: `publishing`.
2. Publish step:
   - downloads staging outputs from `karaoke/out/{job_id}/`
   - converts WAV → m4a
   - uploads public outputs to `karaoke/pub/{slug}/`
   - writes `stems.json`
3. VPS updates Supabase:
   - `processing_status = published`
   - `public_url = https://karaoke.1215group.com/karaoke/pub/{slug}`

## Monitoring and Slack Alerts (Must Keep)

### VPS Monitoring (n8n scheduled workflows)

- stuck jobs detection
- lease cleanup
- queue depth monitoring
- worker heartbeat monitoring
- Slack alerts (incoming webhook)

### Home Node Reliability Alerts

- systemd OnFailure Slack notification for the home agent service (immediate operator visibility).

_(These cover different failure modes and are not redundant.)_

## Retention / Cleanup (Recommended)

Configure lifecycle rules:

- `karaoke/out/` delete after ~3 days
- `karaoke/in/` delete after ~14 days
- `karaoke/pub/` retain indefinitely

## Acceptance Criteria (E2E)

A job is successful when:

- `karaoke/pub/{slug}/stems.json` exists
- `karaoke/pub/{slug}/video.mp4` exists
- `karaoke/pub/{slug}/stems/*.m4a` exist
- CloudFront can serve `stems.json` and stem audio
- Karaoke UI can load the track via `public_url`
- progress modal reaches Complete
- Slack alerts function for both pipeline monitors and home-agent failures

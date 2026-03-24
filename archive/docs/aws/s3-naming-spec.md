```md
# Karaoke Pipeline S3 Naming Specification

**Status:** IMPLEMENTED (v3.0)
**Last Updated:** 2026-01-06
**Bucket:** `karaoke-pimpshizzle` (AWS S3, us-east-1)
**CDN:** CloudFront Distribution E1TTUZICNONOHR → `https://karaoke.1215group.com/`

---

## Implementation References

- **Runpod Worker:** `runpod-demucs-worker/handler.py` (Docker: `mdc159/karaoke-demucs-worker-aws:v3`)
- **Publish Script:** `Scripts/karaoke_publish.py`
- **n8n Workflow:** `n8n-workflows/karaoke-pipeline/karaoke-publish.json`
- **Frontend:** `apps/karaoke-ui/` (uses `track.publicUrl` from library API)

---

# SPECIFICATION (Original Prompt)

You are an engineering agent responsible for implementing a deterministic karaoke processing pipeline. **Assume the S3 bucket has been completely nuked**: all prior folder structures, objects, and "LLM-created" naming conventions are **deleted**. There is nothing in the bucket now. We are starting fresh.

Your job is to:
1) Define the **canonical S3 key/folder conventions** (staging vs public),
2) Explain **why** this structure is correct (determinism, idempotency, cleanup),
3) Update/author code + workflows so every component writes to the new structure only,
4) Ensure the system remains **secure** (private S3 + CloudFront OAC), and
5) Produce implementation artifacts (code + docs + diagrams) that can be executed.

## Non-Negotiables (Hard Requirements)
- The pipeline must be **deterministic** and **idempotent**. Re-running steps must not corrupt state.
- **Do not invent alternate folder hierarchies.** Use the spec below.
- S3 is **private**. CloudFront reads using **OAC**. Bucket is NOT public.
- Large uploads (MP4 can be big) must use a **multipart uploader** with retries (reference: our proven large-file uploader pattern).
- LLMs may be used for **metadata normalization** (artist/title/slug) and **alert enrichment**, but must not be required for runtime correctness.

## Architecture (Roles)
- **Old Linux PC worker (always-on, no NVIDIA GPU):** downloads YouTube MP4 (yt-dlp) + uploads to S3 + updates DB.
- **Runpod GPU worker:** downloads MP4 from S3, runs Demucs, uploads stems to S3, calls back to VPS.
- **VPS (n8n + DB + dashboard + alerts):** job creation, state machine, slugging, publishing, monitoring, Slack alerts, optional cleanup.

## Canonical S3 Layout (START HERE)
We strictly separate **staging** (job-scoped, ephemeral) from **public** (slug-scoped, user-facing).

### A) STAGING / EPHEMERAL (Job-scoped; safe to delete later)
All staging keys MUST be under job_id to avoid collisions and enable prefix deletion.

**Inputs**
- `karaoke/in/{job_id}/source.mp4`
- `karaoke/in/{job_id}/metadata.json`  (yt-dlp -J output)

**Outputs (Demucs)**
- `karaoke/out/{job_id}/stems/vocals.wav`
- `karaoke/out/{job_id}/stems/drums.wav`
- `karaoke/out/{job_id}/stems/bass.wav`
- `karaoke/out/{job_id}/stems/guitar.wav`
- `karaoke/out/{job_id}/stems/piano.wav`
- `karaoke/out/{job_id}/stems/other.wav`
- `karaoke/out/{job_id}/manifest.json` (what was produced, durations, hashes if available)

### B) PUBLIC / LIBRARY (Slug-scoped; stable URLs)
Public keys are what the player/dashboard should use.

- `karaoke/pub/{slug}/video.mp4` (video-only MP4 if you publish that way)
- `karaoke/pub/{slug}/stems/vocals.m4a`  (or .wav if you insist; prefer .m4a for bandwidth)
- `karaoke/pub/{slug}/stems/drums.m4a`
- `karaoke/pub/{slug}/stems/bass.m4a`
- `karaoke/pub/{slug}/stems/guitar.m4a`
- `karaoke/pub/{slug}/stems/piano.m4a`
- `karaoke/pub/{slug}/stems/shizzle.m4a`  (renamed from "other" during publish)
- `karaoke/pub/{slug}/stems.json` (public manifest for player)

### Why this layout?
- **Job-scoped staging** prevents naming collisions and supports retries.
- **Slug-scoped public** creates human-friendly stable URLs.
- Cleanup is deterministic: delete `karaoke/in/{job_id}/` and `karaoke/out/{job_id}/` by prefix without risk.
- Publishing is explicit: copy/move from staging → public, then mark DB published.

## Slug Specification (Deterministic, Collision-Resistant)
Slug format MUST be:

`{artist}--{title}--{source}--{shortid}`

Example:
`queen--bohemian-rhapsody--yt--dQw4w`

Rules:
- Normalize to lowercase, ascii-safe where possible.
- Replace spaces with hyphens, collapse repeats.
- Remove “junk tokens” like: official video, lyrics, HD, 4K, remastered, live, visualizer.
- `{source}` is typically `yt`.
- `{shortid}` is first 5–6 characters of the YouTube video_id (preferred) OR a stable hash of (artist|title|video_id).

**Important:** Store raw metadata and cleaned values in DB. Slug generation is deterministic from stored fields.

## Database / State Machine (Conceptual)
Define job states (minimum):
- queued
- leased
- downloading
- uploaded_source
- runpod_processing
- published
- failed (retryable)
- permanently_failed

Key invariants:
- Only control-plane code changes state.
- Every failure sets `last_error` and increments `retry_count` deterministically.
- Leases expire and can be reclaimed safely.

## CloudFront / Security
- S3 bucket is private.
- CloudFront distribution uses **OAC** to read S3.
- Bucket policy only allows `s3:GetObject` from CloudFront distribution ARN.
- Keep “Block Public Access” enabled.
- Configure S3 CORS for GET/HEAD to support browser playback.

## Publishing Policy
Publishing MUST create a stable public artifact set under `karaoke/pub/{slug}/` and write `stems.json`.
If you choose to publish to VPS filesystem instead, keep the same slug-based directory structure:
`/var/www/karaoke/videos/{slug}/...`
but still keep S3 staging (`in/` and `out/`) as specified.

## Optional Cleanup / Retention
Implement cleanup in either:
- S3 Lifecycle Rules (preferred), OR
- n8n scheduled workflow (safe, with dry-run first)

Recommended retention:
- `karaoke/out/` delete after 3 days
- `karaoke/in/` delete after 14 days
- `karaoke/pub/` retain indefinitely

## Implementation Deliverables (What you must produce)
1) **Spec doc**: `ARCHITECTURE.md` with the above conventions and rationale.
2) Mermaid diagrams:
   - Data flow diagram
   - State machine diagram
3) Worker implementation (Linux PC):
   - yt-dlp download + metadata capture
   - multipart upload to S3 using robust retry logic
   - status updates + heartbeat
4) Runpod worker:
   - download input from S3
   - demucs split to 6 stems
   - upload to `karaoke/out/{job_id}/stems/`
   - upload `manifest.json`
   - callback to VPS webhook with uploaded keys
5) VPS/n8n control plane:
   - submit job
   - claim/lease
   - publish callback handler
   - slugging: rules-first + LLM fallback
   - alerts + dashboard feed
   - optional cleanup workflow

## DO THIS FIRST (Sequence)
1) Write the spec + Mermaid diagrams.
2) Implement S3 key utilities (single source of truth) so every component uses identical key generation.
3) Implement worker upload using multipart uploader.
4) Implement Runpod output + manifest + callback.
5) Implement publish + slugging + monitoring.

## Success Criteria
- A job flows end-to-end and results exist at:
  - `karaoke/pub/{slug}/stems.json`
  - `karaoke/pub/{slug}/stems/*`
- CloudFront can serve public objects via `https://<your-domain>/karaoke/pub/{slug}/...`
- Staging prefixes can be deleted safely by job_id.
- Renaming a slug is handled by DB override + alias strategy (optional), without breaking the pipeline.

Proceed now. Produce the spec, then the code/workflows following it exactly.
```

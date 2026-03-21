CloudFront is already configured.

- Distribution ID: E1TTUZICNONOHR
- Public domain: https://karaoke.1215group.com/
- S3 bucket is private and served via CloudFront OAC (do NOT propose making the bucket public or using presigned URLs).
- CORS enabled for GET/HEAD.

## Implementation Status

All required changes have been implemented. See below for details.

---

## COMPLETED CHANGES

### 1) Fix Runpod output key layout (staging) - DONE

**File:** `runpod-demucs-worker/handler.py`
**Docker Image:** `mdc159/karaoke-demucs-worker-aws:v3`

Runpod now writes to:
- `karaoke/out/{job_id}/stems/vocals.wav`
- `karaoke/out/{job_id}/stems/drums.wav`
- `karaoke/out/{job_id}/stems/bass.wav`
- `karaoke/out/{job_id}/stems/guitar.wav`
- `karaoke/out/{job_id}/stems/piano.wav`
- `karaoke/out/{job_id}/stems/other.wav`
- `karaoke/out/{job_id}/manifest.json`
- `karaoke/out/{job_id}/video.mp4`
- `karaoke/out/{job_id}/karaoke_six_stem.mp4`

### 2) Implement "Publish: staging → public" - DONE

**File:** `Scripts/karaoke_publish.py`
**n8n Workflow:** `n8n-workflows/karaoke-pipeline/karaoke-publish.json`

The publish script:
1. Downloads from `karaoke/out/{job_id}/`
2. Converts WAV → m4a using ffmpeg
3. Uploads to `karaoke/pub/{slug}/`
4. Creates public `stems.json` manifest
5. Updates DB: `processing_status='published'`, `public_url=https://karaoke.1215group.com/karaoke/pub/{slug}`

Public artifacts:
- `karaoke/pub/{slug}/stems.json`
- `karaoke/pub/{slug}/stems/*.m4a`
- `karaoke/pub/{slug}/video.mp4`

Publishing is idempotent - re-running overwrites safely.

### 3) Slugging + overrides - DONE

Slug is generated deterministically from `artist/title/source/shortid` and stored in DB.
Manual override supported via DB update.

### 4) Update URLs used by frontend/dashboard - DONE

**Files:**
- `apps/karaoke-ui/src/lib/api.ts` - `loadManifest()` accepts CloudFront base URL
- `apps/karaoke-ui/src/hooks/useAudioSync.ts` - Uses `track.publicUrl` for stems
- `apps/karaoke-ui/src/components/player/PlayerShell.tsx` - Uses `track.publicUrl` for video
- `n8n-workflows/karaoke-pipeline/karaoke-library-api.json` - Returns `publicUrl` field

Frontend uses:
- `https://karaoke.1215group.com/karaoke/pub/{slug}/stems.json`
- Assets referenced in manifest under same base path

### 5) Add optional retention - PENDING

Recommended S3 Lifecycle Rules (to be configured in AWS Console):
- `karaoke/out/` - delete after 3 days
- `karaoke/in/` - delete after 14 days
- `karaoke/pub/` - retain indefinitely

---

## Deliverables

1. **Code diffs/patches:** See commits in `runpod-demucs-worker/handler.py`, `Scripts/karaoke_publish.py`
2. **Manifest formats:** See `docs/karaoke-publish-flow.md`
3. **Mermaid diagram:** See `docs/karaoke-publish-flow.md`
4. **Test plan:** See `docs/karaoke-publish-flow.md`

---

## Test Plan

1. Deploy Runpod worker v3: `mdc159/karaoke-demucs-worker-aws:v3`
2. Submit test job via n8n webhook
3. Verify staging outputs:
   ```bash
   aws s3 ls s3://karaoke-pimpshizzle/karaoke/out/{job_id}/
   aws s3 ls s3://karaoke-pimpshizzle/karaoke/out/{job_id}/stems/
   ```
4. Verify publish completes and public outputs exist:
   ```bash
   aws s3 ls s3://karaoke-pimpshizzle/karaoke/pub/{slug}/
   ```
5. Test CloudFront delivery:
   ```bash
   curl -I https://karaoke.1215group.com/karaoke/pub/{slug}/stems.json
   ```
6. Test frontend playback at `https://karaoke.1215group.com/`

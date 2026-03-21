# Runpod Demucs Worker

Serverless GPU worker for 6-stem audio separation using Demucs. Processes karaoke jobs from AWS S3.

**Docker Image:** `mdc159/karaoke-demucs-worker-aws:v3`
**Model:** `htdemucs_6s` (6-stem separation)

## Overview

This worker:
1. Downloads source video from AWS S3 (`karaoke/in/{job_id}/source.mp4`)
2. Extracts audio and runs Demucs 6-stem separation
3. Uploads WAV stems to S3 (`karaoke/out/{job_id}/stems/*.wav`)
4. Sends callback to VPS for publishing

## Output Structure

Per the s3-naming-spec, staging output uses WAV files in a `stems/` subfolder:

```
karaoke/out/{job_id}/
├── video.mp4              # Video-only track (no audio)
├── manifest.json          # Staging manifest
├── karaoke_six_stem.mp4   # Optional canonical multi-audio file
└── stems/
    ├── vocals.wav
    ├── drums.wav
    ├── bass.wav
    ├── guitar.wav
    ├── piano.wav
    └── other.wav
```

## Input Payload

```json
{
  "input": {
    "job_id": "uuid-here",
    "bucket": "karaoke-pimpshizzle",
    "input_key": "karaoke/in/{job_id}/source.mp4",
    "output_prefix": "karaoke/out/{job_id}/",
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

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_ACCESS_KEY_ID` | Yes | AWS IAM access key |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS IAM secret key |
| `AWS_REGION` | No | AWS region (default: `us-east-1`) |
| `AWS_S3_BUCKET` | No | Default bucket (default: `karaoke-pimpshizzle`) |
| `CALLBACK_URL` | No | VPS webhook for publish callback |

## Callback Response

On success, sends POST to `CALLBACK_URL`:

```json
{
  "status": "ok",
  "job_id": "uuid-here",
  "bucket": "karaoke-pimpshizzle",
  "output_prefix": "karaoke/out/{job_id}/",
  "duration": 240.5,
  "uploads": [
    {"file": "karaoke_six_stem.mp4", "key": "karaoke/out/{job_id}/karaoke_six_stem.mp4"},
    {"file": "video.mp4", "key": "karaoke/out/{job_id}/video.mp4"},
    {"file": "stems/vocals.wav", "key": "karaoke/out/{job_id}/stems/vocals.wav"},
    {"file": "stems/drums.wav", "key": "karaoke/out/{job_id}/stems/drums.wav"},
    {"file": "stems/bass.wav", "key": "karaoke/out/{job_id}/stems/bass.wav"},
    {"file": "stems/guitar.wav", "key": "karaoke/out/{job_id}/stems/guitar.wav"},
    {"file": "stems/piano.wav", "key": "karaoke/out/{job_id}/stems/piano.wav"},
    {"file": "stems/other.wav", "key": "karaoke/out/{job_id}/stems/other.wav"},
    {"file": "manifest.json", "key": "karaoke/out/{job_id}/manifest.json"}
  ],
  "uploaded_count": 9
}
```

On error:

```json
{
  "status": "error",
  "job_id": "uuid-here",
  "error": "Error message"
}
```

## Building & Deploying

### Build Docker Image

```bash
cd runpod-demucs-worker
docker build -t mdc159/karaoke-demucs-worker-aws:v3 .
```

### Push to Docker Hub

```bash
docker push mdc159/karaoke-demucs-worker-aws:v3
```

### Deploy to Runpod

1. Go to Runpod Console → Serverless → Templates
2. Click "New Release" on existing template
3. Enter new image: `mdc159/karaoke-demucs-worker-aws:v3`
4. Deploy

### Environment Setup in Runpod

Add these environment variables to the Runpod endpoint:

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
AWS_S3_BUCKET=karaoke-pimpshizzle
CALLBACK_URL=https://n8n.1215group.com/webhook/karaoke-publish
```

## Demucs Parameters

The worker uses optimized parameters for the htdemucs_6s model:

| Parameter | Value | Notes |
|-----------|-------|-------|
| `--segment` | 7 | Max is 7.8 for htdemucs_6s |
| `--overlap` | 0.25 | 25% overlap between segments |
| `--shifts` | 0 | No random shifts for consistency |
| `--clip-mode` | rescale | Prevents clipping |
| `--int24` | enabled | 24-bit WAV output |

## Stems Produced

| Stem | Description |
|------|-------------|
| `vocals.wav` | Lead vocals |
| `drums.wav` | Drums and percussion |
| `bass.wav` | Bass instruments |
| `guitar.wav` | Guitar tracks |
| `piano.wav` | Piano and keyboards |
| `other.wav` | Ambience and other sounds |

## Typical Performance

| Video Duration | Processing Time | Notes |
|----------------|-----------------|-------|
| 3-4 minutes | 5-10 minutes | Typical song |
| 5-7 minutes | 10-20 minutes | Longer tracks |
| 10+ minutes | 20-30 minutes | Extended mixes |

Processing time depends on GPU availability and serverless cold start time.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v3 | 2026-01-06 | AWS S3, stems/ subfolder, WAV output |
| v2 | 2026-01-05 | Fixed python → python3 |
| v1 | 2026-01-04 | Initial AWS migration |

## Related Documentation

- [S3 Naming Spec](/s3-naming-spec.md)
- [CloudFront Config](/cloudfront.md)
- [Karaoke Pipeline README](/n8n-workflows/karaoke-pipeline/README.md)
- [Publish Flow Diagram](/docs/karaoke-publish-flow.md)

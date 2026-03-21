# K25 - Karaoke Pipeline

Self-hosted karaoke system: YouTube download, 6-stem audio separation (Demucs), S3 publishing, and a React web player with real-time stem mixing.

## Components

| Directory | What | Stack |
|-----------|------|-------|
| `agent/` | Home node worker (download + split + upload) | Python 3.11, UV, yt-dlp, Demucs, boto3 |
| `ui/` | Web player with 6-stem mixer | React 19, TypeScript, Vite, Tailwind, Web Audio API |
| `containers/` | Docker images for VPS pipeline steps | demucs, yt-dlp, karaoke-publish, home-agent |
| `runpod/` | Serverless GPU fallback for stem separation | RunPod worker, Demucs, FFmpeg |
| `docs/` | Pipeline PRD, S3 layout spec, CloudFront config | Markdown |
| `stack/` | Deployment config and env templates | Docker Compose, .env |

## Architecture

```
User submits URL
  -> n8n webhook (VPS)
  -> Job queued in Supabase
  -> Home agent leases job
  -> yt-dlp downloads (residential IP)
  -> Demucs splits 6 stems (local GPU or RunPod fallback)
  -> Stems uploaded to S3 (multipart)
  -> Published to CloudFront CDN
  -> UI plays with real-time stem mixing
```

## Quick Start

See `docs/KARAOKE_PIPELINE_PRD-3.0.md` for the canonical pipeline specification.

## Extracted From

Previously embedded in `~/projects/agent-os/stack/`. Extracted 2026-02-17 to standalone repo.

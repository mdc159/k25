# CLAUDE.md - K25 Karaoke Pipeline

## What This Repository Is

Standalone karaoke pipeline: YouTube download, Demucs 6-stem separation, S3/CloudFront publishing, and a React web player with real-time audio mixing.

## Component Map

| Component | Path | Entry Point |
|-----------|------|-------------|
| Home agent (worker) | `agent/` | `src/karaoke_agent/cli.py` |
| Web player UI | `ui/` | `src/main.tsx` |
| VPS containers | `containers/` | Individual Dockerfiles |
| RunPod GPU worker | `runpod/` | Worker entry |
| Pipeline docs | `docs/` | `KARAOKE_PIPELINE_PRD-3.0.md` |
| Deploy config | `stack/` | `.env.karaoke.example` |

## Key References

- Pipeline PRD: `docs/KARAOKE_PIPELINE_PRD-3.0.md`
- S3 layout: `docs/aws/s3-naming-spec.md`
- CloudFront: `docs/aws/cloudfront.md`
- Agent README: `agent/README.md`

## Environment

- Python: UV preferred
- Node: npm (ui uses Vite)
- AWS S3 bucket: `karaoke-pimpshizzle`
- Supabase: job queue backend
- n8n: webhook orchestration on VPS

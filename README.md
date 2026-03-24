# K25 - Local Karaoke Stem Splitter

Local karaoke tool: upload a video file, separate audio into 6 stems with Demucs on your GPU, and mix them in real time through a browser-based player.

This README describes the **active local workflow** in this repo (`local-server/` + `ui/`). The cloud pipeline in `archive/` is legacy reference only.

## Important Note: YouTube Input Wording Removed

A previous UI version included wording such as "Add a YouTube URL."

That wording was intentionally removed in the current local app because the active backend path is local file upload (`POST /api/upload`) and does not currently process YouTube URLs directly.

This is a scope-alignment change only. The intent is to add URL-based ingest back in a future cloud-based workflow version.

## How It Works

```
Upload video file via browser (video/*)
  -> FastAPI backend (Docker, NVIDIA GPU)
  -> FFmpeg extracts audio (WAV 16-bit 44.1kHz) + video (codec copy)
  -> Demucs htdemucs_6s splits into 6 stems (24-bit WAV)
       vocals | drums | bass | guitar | piano | other
  -> FFmpeg muxes video + 6 AAC tracks into multi-track.mp4
  -> Browser loads 6 individual stem files as <audio> elements
  -> Web Audio API: per-stem gain control (-12 to +6 dB)
  -> Video plays muted; all audio comes from stems
```

## Components

| Component | Path | Port |
|-----------|------|------|
| FastAPI backend | `local-server/` | 8001 |
| React player UI | `ui/` | 5173 (Vite dev) |
| Docker GPU config | `docker-compose.yml` | - |
| Launch script | `launch-local.ps1` | - |

## Quick Start

**Requirements**: Docker with NVIDIA GPU support, Node.js, npm

```powershell
# Start everything (Docker backend + Vite frontend + opens browser)
.\launch-local.ps1
```

If this is your first run:

```powershell
cd ui
npm install
```

Or manually:

```bash
# Backend (GPU container)
docker compose up --build -d

# Frontend
cd ui && npm install && npm run dev
```

Open `http://localhost:5173`. Press `/` to upload a video file.

## Processing Pipeline

Each uploaded file gets a 12-character job ID and its own directory under `data/`.

### Step 1: Extract Audio

```bash
ffmpeg -y -i source.mp4 -vn -acodec pcm_s16le -ar 44100 -ac 2 audio.wav
```

PCM 16-bit, 44.1kHz, stereo.

### Step 2: Extract Video

```bash
ffmpeg -y -i source.mp4 -an -c:v copy video.mp4
```

Video track only, no re-encoding.

### Step 3: Demucs 6-Stem Separation

```bash
python3 -m demucs -n htdemucs_6s \
  --segment 7 --overlap 0.25 --shifts 0 \
  --clip-mode rescale --int24 \
  --out demucs_out audio.wav
```

| Parameter | Value | Why |
|-----------|-------|-----|
| Model | `htdemucs_6s` | 6-stem: vocals, drums, bass, guitar, piano, other |
| Segment | 7 seconds | GPU memory efficient |
| Overlap | 25% | Smooth segment transitions |
| Shifts | 0 | No augmentation (faster) |
| Clip mode | rescale | Prevents clipping artifacts |
| Output | 24-bit integer WAV | Higher precision than 16-bit |

### Step 4: Multi-Track MP4

```bash
ffmpeg -y -i video.mp4 \
  -i vocals.wav -i drums.wav -i bass.wav \
  -i guitar.wav -i piano.wav -i other.wav \
  -map 0:v \
  -map 1:a -metadata:s:a:0 handler_name=Vocals \
  -map 2:a -metadata:s:a:1 handler_name=Drums \
  -map 3:a -metadata:s:a:2 handler_name=Bass \
  -map 4:a -metadata:s:a:3 handler_name=Guitar \
  -map 5:a -metadata:s:a:4 handler_name=Piano \
  -map 6:a -metadata:s:a:5 handler_name=Shizzle \
  -c:v copy -c:a aac -b:a 256k \
  -movflags +faststart \
  multi-track.mp4
```

Video copied as-is. Each stem encoded to AAC at 256kbps. The `multi-track.mp4` is available for download from the UI.

## Data Layout

```
data/
└── {job_id}/              # 12-char hex ID
    ├── source.mp4         # Original upload
    ├── video.mp4          # Video only (no audio)
    ├── stems/
    │   ├── vocals.wav     # 24-bit WAV from Demucs
    │   ├── drums.wav
    │   ├── bass.wav
    │   ├── guitar.wav
    │   ├── piano.wav
    │   └── other.wav
    ├── stems.json         # Manifest (metadata + stem file list)
    └── multi-track.mp4    # Video + 6 AAC audio tracks
```

Temporary artifacts created during processing and removed on success:

- `audio.wav`
- `demucs_out/`

### stems.json

```json
{
  "title": "Song Title",
  "artist": "",
  "duration": 199.67,
  "video": "video.mp4",
  "stems": [
    { "id": "vocals", "name": "Vocals", "file": "stems/vocals.wav", "default_gain": 0 },
    { "id": "drums",  "name": "Drums",  "file": "stems/drums.wav",  "default_gain": 0 },
    { "id": "bass",   "name": "Bass",   "file": "stems/bass.wav",   "default_gain": 0 },
    { "id": "guitar", "name": "Guitar", "file": "stems/guitar.wav", "default_gain": 0 },
    { "id": "piano",  "name": "Piano",  "file": "stems/piano.wav",  "default_gain": 0 },
    { "id": "shizzle","name": "Shizzle","file": "stems/other.wav",  "default_gain": 0 }
  ]
}
```

The presence of `stems.json` in a job directory marks it as complete and makes it appear in the library.

## Current Scope Notes

- Current ingest path is **local file upload only** via `POST /api/upload`.
- The app does **not** currently process YouTube URLs directly in active local mode.
- UI text that references YouTube in some places is legacy wording and not the active behavior.

## Frontend Player

The UI is a single-page React app (no routing). Everything overlays a full-viewport video player.

### Audio Playback

The video element plays **muted**. Audio comes entirely from 6 separate `<audio>` elements managed through the Web Audio API:

```
<audio> (stem) -> MediaElementSource -> GainNode -> AudioContext.destination
                                         ↑
                              dB slider (-12 to +6)
```

All 6 stems load in parallel (full file download, not streaming). Playback starts when all stems report `canplaythrough`. A drift-correction check runs every 5 seconds - if any stem is >100ms out of sync with the video, it resyncs.

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space | Play / Pause |
| `/` | Open upload dialog |
| `L` | Toggle library drawer |
| `M` | Toggle mixer drawer |
| Esc | Close drawers |

### Mixer

6 sliders control individual stem volume in real time. Range is -12 dB to +6 dB in 0.5 dB steps. Gain changes use `setTargetAtTime` with a 50ms time constant for smooth transitions. Volume and gain settings persist in localStorage.

## API

All endpoints are prefixed with `/api`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload video file, returns `{ jobId }` |
| `GET` | `/api/jobs/{id}` | Poll job status |
| `GET` | `/api/library` | List all completed tracks |
| `GET` | `/api/tracks/{id}/download` | Download multi-track MP4 |
| `GET` | `/api/tracks/{id}/{path}` | Serve any file from job directory |

### Job Status Flow

```
pending -> extracting -> splitting -> encoding -> ready
                                               -> failed
```

Jobs are processed one at a time (async lock prevents GPU contention). Status is tracked in memory and resets on server restart.

## Docker

The backend runs in an NVIDIA CUDA 12.1 container with PyTorch, Demucs, and FFmpeg pre-installed.

```yaml
# docker-compose.yml
services:
  local-server:
    build: local-server/
    ports: ["8001:8001"]
    volumes: ["./data:/app/data"]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

## Archive

The `archive/` directory contains a previous distributed cloud pipeline (agent workers, RunPod serverless GPU, S3/CloudFront publishing, Supabase job queue, n8n webhooks). It's kept for reference but is not part of the current local workflow. It can be deleted without affecting anything.

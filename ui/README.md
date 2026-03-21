# Karaoke UI

A React-based stem-mixing karaoke player with real-time audio control. Built with React 19, TypeScript, Vite, and Web Audio API.

**Version:** 3.0 (CloudFront CDN)
**Last Updated:** 2026-01-06

## Features

- **6-Stem Audio Mixing**: Independent volume control for vocals, drums, bass, guitar, piano, and other
- **Real-Time Control**: Adjust stem volumes during playback with zero latency
- **Video Sync**: Synchronized video playback with muted audio (audio comes from stems)
- **CloudFront CDN Delivery**: All assets served via AWS CloudFront for global performance
- **Library Management**: Browse and select processed karaoke tracks
- **Dual Source Input**: Submit YouTube URLs or local file paths (VPS-side)
- **Job Processing**: Real-time progress tracking with step-by-step status updates
- **Responsive UI**: Mobile-friendly dark theme interface

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Karaoke UI                                      │
│                                                                              │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│   │   PlayerShell   │    │   MixerDrawer   │    │  LibraryDrawer  │        │
│   │   (Video +      │    │   (6 Faders)    │    │   (Track List)  │        │
│   │   Transport)    │    │                 │    │                 │        │
│   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘        │
│            │                      │                      │                  │
│   ┌─────────────────┐             │                      │                  │
│   │ AddSourceModal  │─────────────┼──────────────────────┘                  │
│   │ (URL or Path)   │             │                                          │
│   └────────┬────────┘             │                                          │
│            └──────────────────────┼──────────────────────────────────────────│
│                                   │                                          │
│                         ┌─────────┴─────────┐                                │
│                         │   Zustand Store   │◄──── Persisted gains/volume   │
│                         └─────────┬─────────┘                                │
│                                   │                                          │
│            ┌──────────────────────┼──────────────────────┐                  │
│            │                      │                      │                  │
│   ┌────────┴────────┐   ┌────────┴────────┐   ┌────────┴────────┐         │
│   │  useAudioSync   │   │  audioManager   │   │    API Layer    │         │
│   │  (Sync Hook)    │   │  (Web Audio)    │   │  (n8n Webhooks) │         │
│   └─────────────────┘   └─────────────────┘   └─────────────────┘         │
│            │                      │                      │                  │
│            ▼                      ▼                      ▼                  │
│   Video ←→ Audio Sync     6 GainNodes        /api/karaoke-library          │
│   (Drift correction)      (dB → Linear)      /api/karaoke-submit           │
│                                              /api/jobs?jobId=xxx           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              VPS Backend                                     │
│                                                                              │
│   Input Detection (n8n Source Router):                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  User Input ──► Source Router ──┬──► YouTube URL ──► yt-dlp         │   │
│   │    (URL or     (IF node)        │                    (download)     │   │
│   │     Path)                       │                                    │   │
│   │                                 └──► Local Path ──► ffprobe         │   │
│   │                                                     (metadata)      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │   Unified Pipeline: Demucs (6-stem) → FFmpeg (encode) → Publish     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   /videos/{slug}/              /api/                     Processing          │
│   ├── video.mp4                ├── karaoke-library       ┌───────────┐      │
│   ├── vocals.m4a               ├── karaoke-submit        │  Demucs   │      │
│   ├── drums.m4a                └── jobs?jobId=xxx        │  FFmpeg   │      │
│   ├── bass.m4a                      │                    │  yt-dlp   │      │
│   ├── guitar.m4a                    ▼                    └───────────┘      │
│   ├── piano.m4a               ┌───────────┐                                 │
│   ├── other.m4a               │ Supabase  │                                 │
│   └── stems.json              │  Library  │                                 │
│                               └───────────┘                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | React 19 |
| Build | Vite 7 |
| Language | TypeScript 5.9 |
| State | Zustand 5 (with persistence) |
| Audio | Web Audio API (AudioContext, GainNode) |
| UI Components | Radix UI + shadcn/ui |
| Styling | Tailwind CSS 4 |
| Icons | Lucide React |
| Notifications | Sonner |

## Project Structure

```
src/
├── components/
│   ├── library/
│   │   └── LibraryDrawer.tsx     # Track browsing & selection with search
│   ├── mixer/
│   │   └── MixerDrawer.tsx       # 6-channel stem mixer with dB sliders
│   ├── player/
│   │   ├── PlayerShell.tsx       # Main player with video + audio sync
│   │   └── TransportControls.tsx # Play/pause/seek/volume controls
│   ├── source/
│   │   └── AddSourceModal.tsx    # URL/Path input + job progress stepper
│   └── ui/                       # shadcn/ui components
│       ├── button.tsx
│       ├── dialog.tsx
│       ├── input.tsx
│       ├── sheet.tsx
│       └── slider.tsx
│
├── hooks/
│   └── useAudioSync.ts           # Video-audio synchronization hook
│
├── lib/
│   ├── api.ts                    # n8n webhook API client (library, submit, jobs)
│   ├── audio.ts                  # StemAudioManager class (Web Audio API)
│   └── utils.ts                  # Utility functions (cn, etc.)
│
├── stores/
│   └── useStore.ts               # Zustand store (persisted gains, session state)
│
├── types/
│   └── karaoke.ts                # TypeScript interfaces (Track, JobStatus, etc.)
│
├── App.tsx                       # Root component with drawer layout
├── main.tsx                      # Entry point with Toaster
└── index.css                     # Tailwind CSS imports
```

## Data Flow

### Audio Playback

```
1. User selects track from LibraryDrawer
2. loadTrack() updates currentTrack in store
3. PlayerShell loads manifest via loadManifest(slug)
4. useAudioSync hook:
   - Creates 6 GainNodes (one per stem)
   - Loads stem audio files as AudioBufferSourceNode
   - Connects: Source → GainNode → AudioContext.destination
5. Video plays muted, stems play through Web Audio
6. Periodic drift correction syncs audio to video time
```

### Stem Mixing

```
1. User adjusts slider in MixerDrawer
2. handleGainChange(stem, dbValue):
   - Updates store: setStemGain(stem, dbValue)
   - Updates audio: audioManager.setGain(stem, linear)
3. dB to linear conversion: linear = 10^(dB/20)
4. GainNode.gain.value updated instantly
```

### Job Processing

```
1. User enters YouTube URL or local file path in AddSourceModal
   - YouTube: https://youtube.com/watch?v=xxx
   - Local: /root/videos/song.mp4 (VPS path)
2. submitSource(source) → POST /api/karaoke-submit { "source": "..." }
3. n8n Source Router detects input type:
   - YouTube URL (contains 'youtube.com' or 'youtu.be') → yt-dlp download path
   - Local path (starts with '/') → ffprobe metadata extraction path
4. Both paths merge into unified pipeline:
   - Demucs 6-stem separation
   - FFmpeg encoding (WAV → AAC)
   - Publish to /var/www/karaoke/videos/{slug}/
5. Polling every 3s: getJobStatus(jobId)
6. Progress display: pending → downloading → extracting → splitting → encoding → ready
7. On ready: close modal, refresh library
```

### Source Detection Flow

```
                    ┌─────────────────────┐
                    │  AddSourceModal     │
                    │  (URL or Path)      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  POST /api/submit   │
                    │  { source: "..." }  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Source Router     │
                    │   (n8n IF node)     │
                    └──────────┬──────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   │                   ▼
  ┌─────────────────┐          │        ┌─────────────────┐
  │  YouTube URL    │          │        │  Local Path     │
  │  → yt-dlp       │          │        │  → ffprobe      │
  │  (download)     │          │        │  → copy file    │
  └────────┬────────┘          │        └────────┬────────┘
           │                   │                 │
           └───────────────────┼─────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Unified Metadata   │
                    │  → Demucs → FFmpeg  │
                    │  → Publish          │
                    └─────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/karaoke-library` | GET | List all ready tracks (Supabase query) |
| `/api/karaoke-submit` | POST | Submit source for processing (JSON: `{ "source": "..." }`) |
| `/api/jobs?jobId=xxx` | GET | Get job processing status |

### CloudFront CDN Assets

All media assets are served via CloudFront from AWS S3:

| Asset | URL Pattern |
|-------|-------------|
| Manifest | `https://karaoke.1215group.com/karaoke/pub/{slug}/stems.json` |
| Video | `https://karaoke.1215group.com/karaoke/pub/{slug}/video.mp4` |
| Stems | `https://karaoke.1215group.com/karaoke/pub/{slug}/stems/{stem}.m4a` |

The `publicUrl` field from the library API provides the base URL for each track.

### Source Input Formats

| Format | Example | Detection |
|--------|---------|-----------|
| YouTube URL | `https://youtube.com/watch?v=dQw4w9WgXcQ` | Contains `youtube.com` or `youtu.be` |
| Local VPS Path | `/root/videos/song.mp4` | Starts with `/` |

## State Management

### Persisted State (localStorage)

| Key | Type | Description |
|-----|------|-------------|
| `volume` | number | Master volume (0-1) |
| `stemGains` | Record<StemId, number> | Per-stem dB values (-12 to +6) |

### Session State

| Key | Type | Description |
|-----|------|-------------|
| `currentTrack` | Track \| null | Currently loaded track |
| `manifest` | StemsManifest \| null | Loaded stems manifest |
| `playing` | boolean | Playback state |
| `currentTime` | number | Current playback time (seconds) |
| `duration` | number | Track duration (seconds) |
| `activeDrawer` | string | Which drawer is open |
| `activeJob` | JobStatus \| null | Currently processing job |

## Development

### Prerequisites

- Node.js 20+
- npm 10+

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Development Server

The dev server runs at `http://localhost:5173` by default.

API calls are proxied:
- `/api/*` → n8n webhooks
- `/videos/*` → Static assets

### Vite Configuration

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'https://n8n.1215group.com/webhook',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/videos': {
        target: 'https://karaoke.1215group.com',
        changeOrigin: true,
      },
    },
  },
});
```

## Deployment

### Build

```bash
npm run build
```

Outputs to `dist/` directory.

### Deploy to VPS

```bash
rsync -avz --delete dist/ root@VPS_IP:/var/www/karaoke/
```

### NGINX Configuration

```nginx
server {
    server_name karaoke.1215group.com;
    root /var/www/karaoke;
    index index.html;

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Video/stem assets
    location /videos/ {
        alias /var/www/karaoke/videos/;
        add_header Accept-Ranges bytes;
        add_header Cache-Control "public, max-age=604800";
    }

    # API proxy to n8n
    location /api/ {
        proxy_pass http://127.0.0.1:5678/webhook/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SSL managed by certbot
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/karaoke.1215group.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/karaoke.1215group.com/privkey.pem;
}
```

## Stem Manifest Format (stems.json)

The public manifest served via CloudFront:

```json
{
  "title": "Song Title",
  "artist": "Artist Name",
  "duration": 240.5,
  "video": "video.mp4",
  "sourceUrl": "https://youtube.com/watch?v=...",
  "videoId": "dQw4w9WgXcQ",
  "stems": [
    { "id": "vocals", "name": "vocals", "file": "stems/vocals.m4a", "default_gain": 1.0 },
    { "id": "drums", "name": "drums", "file": "stems/drums.m4a", "default_gain": 1.0 },
    { "id": "bass", "name": "bass", "file": "stems/bass.m4a", "default_gain": 1.0 },
    { "id": "guitar", "name": "guitar", "file": "stems/guitar.m4a", "default_gain": 1.0 },
    { "id": "piano", "name": "piano", "file": "stems/piano.m4a", "default_gain": 1.0 },
    { "id": "other", "name": "other", "file": "stems/other.m4a", "default_gain": 1.0 }
  ]
}
```

**Note:** Stem file paths are relative to the manifest URL base path.

## Audio Engine Details

### StemAudioManager

The `StemAudioManager` class in `src/lib/audio.ts` manages Web Audio API:

```typescript
class StemAudioManager {
  private context: AudioContext;
  private gains: Map<StemId, GainNode>;
  private sources: Map<StemId, AudioBufferSourceNode>;

  // Load all stems from manifest
  async loadStems(baseUrl: string, stems: StemsManifest['stems']): Promise<void>

  // Play all stems synchronized
  play(startTime?: number): void

  // Pause all stems
  pause(): void

  // Seek to time (reloads buffers)
  seek(time: number): void

  // Set gain for a stem (0-2 linear scale)
  setGain(stem: StemId, value: number): void

  // Convert dB to linear
  static dbToLinear(db: number): number

  // Convert linear to dB
  static linearToDb(linear: number): number
}
```

### Gain Range

| Scale | Min | Default | Max |
|-------|-----|---------|-----|
| dB | -12 | 0 | +6 |
| Linear | 0.25 | 1.0 | 2.0 |

Conversion: `linear = Math.pow(10, dB / 20)`

## Browser Compatibility

- Chrome 66+ (Web Audio, AudioWorklet)
- Firefox 76+ (Web Audio, AudioWorklet)
- Safari 14.1+ (Web Audio, AudioWorklet)
- Edge 79+ (Chromium-based)

**Note**: Web Audio API requires user interaction before AudioContext can start (browser autoplay policy).

## Related Documentation

- [Karaoke Pipeline Implementation](../../02-Feature-Stage-Split/IMPLEMENTATION.md)
- [n8n Workflow: karaoke-pipeline.json](../../n8n-workflows/karaoke-pipeline.json)
- [Main DEVELOPMENT.md](../../DEVELOPMENT.md)

## License

Private - Internal use only.

# Karaoke Mixer Frontend - Implementation Status

**Date:** December 31, 2025
**Status:** Alpha / Foundation Complete

## 1. What Has Been Built

We have successfully established the foundational frontend for the "Video-First" Karaoke Mixer. The application is running as a static Single Page Application (SPA).

### A. Core Architecture
- **Framework**: React 19 + Vite (Builds successfully).
- **Styling**: Tailwind CSS v4 using the `@tailwindcss/vite` plugin.
- **Theme**: "Neutral Dark" (Zinc/Slate palette) with no lavender gradients, strictly adhering to the "immersive" design goal.
- **State Management**: `Zustand` store handling:
  - Player state (play/pause, time, volume).
  - UI state (active drawers, auto-hiding controls).
  - Mixer state (stem gain levels).

### B. Components Implemented
1.  **PlayerShell (`src/components/player/PlayerShell.tsx`)**
    - Handles the fullscreen video element.
    - Implements the "auto-hide" logic: controls disappear after 2.5s of inactivity.
    - specialized "Video First" layout that prevents scrolling.

2.  **TransportControls (`src/components/player/TransportControls.tsx`)**
    - Floating bottom bar with Play, Pause, Seek, and Volume.
    - Accessible only when mouse moves or interaction occurs.

3.  **Drawers & Modals (Overlays)**
    - **Library (`src/components/library/LibraryDrawer.tsx`)**: Left-side sheet for browsing tracks. Currently fetches mock data.
    - **Mixer (`src/components/mixer/MixerDrawer.tsx`)**: Right-side sheet with real-time sliders for 6-stem control.
    - **Add Source (`src/components/source/AddSourceModal.tsx`)**: Dialog for importing YouTube URLs.

4.  **UI Primitives (Shadcn/UI)**
    - Re-implemented core primitives: `Button`, `Slider`, `Sheet`, `Dialog` manually to ensure compatibility and lack of bloat.

### C. key Fixes Applied during Build
- **Tailwind v4 Integration**: Fixed initial "raw text" styling issue by installing `@tailwindcss/vite` and `tailwindcss-animate`.
- **Legacy Cleanup**: Removed conflicting legacy `TopBar` and `hooks` that were causing build errors.
- **Type Safety**: Resolved all TypeScript errors in the build pipeline.

---

## 2. What Still Needs Completing

The frontend is visually complete and interactive, but functionally relies on mocks for the heavy lifting.

### A. API Integration (Critical)
- [ ] **Replace Mocks**: Update `src/lib/api.ts` to fetch from the real n8n/Backend.
  - `GET /api/library`: Connect to real video index.
  - `POST /api/load`: trigger real download jobs.
- [ ] **Job Status**: creating a polling mechanism to check status of "Add Source" jobs.

### B. Audio Engine (Complex)
- [ ] **Web Audio API**: The `MixerDrawer` currently updates a number in the store. This needs to be wired to a real `GainNode` graph in the browser to actually change the volume of individual stems (Vocals, Drums, etc.) in real-time.
- [ ] **Stem Synchronization**: ensuring all 6 audio stems play in perfect sync with the video.

### C. Infrastructure
- [ ] **Deployment**: Setup `rsync` or CI/CD to deploy the `dist/` folder to `/var/www/karaoke/`.
- [ ] **Assets**: Ensure the VPS NGINX is correctly serving the video files from `/var/www/karaoke/videos/` with CORS enabled so the frontend can play them.

## 3. How to Run Locally

```bash
cd apps/karaoke-ui
npm install
npm run dev
```

## 4. How to Build for Production

```bash
cd apps/karaoke-ui
npm run build
# Output will be in dist/
```

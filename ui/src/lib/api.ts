/**
 * API Client for Karaoke Pipeline
 *
 * Communicates with n8n webhooks for:
 * - Library browsing (tracks with status=ready)
 * - YouTube URL submission
 * - Job status polling
 * - Stem manifest loading
 */

import type { Track, StemsManifest, JobStatus, LibraryResponse } from '@/types/karaoke';

// API base URL:
// - Development: empty (uses Vite proxy to n8n webhooks)
// - Production: set VITE_API_BASE to 'https://n8n.1215group.com/webhook'
const API_BASE = import.meta.env.VITE_API_BASE || '';

// Videos base URL:
// - Development: empty (uses Vite proxy to karaoke.1215group.com)
// - Production: set VITE_VIDEOS_BASE to 'https://karaoke.1215group.com/videos'
const VIDEOS_BASE = import.meta.env.VITE_VIDEOS_BASE || '/videos';

// Helper to build API URLs
const apiUrl = (path: string) => API_BASE ? `${API_BASE}${path}` : `/api${path}`;

/**
 * Fetch library of ready tracks from n8n webhook
 */
export async function getLibrary(query?: string): Promise<Track[]> {
  const params = new URLSearchParams();
  if (query) params.set('query', query);

  const baseUrl = apiUrl('/karaoke-library');
  const url = params.toString() ? `${baseUrl}?${params}` : baseUrl;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch library: ${response.statusText}`);
  }

  const data: LibraryResponse = await response.json();
  return data.tracks;
}

/**
 * Submit a source for processing (YouTube URL or local file path)
 * Returns immediately with a jobId for polling
 */
export async function submitSource(source: string): Promise<{ jobId: string; status: string }> {
  const response = await fetch(apiUrl('/karaoke-submit'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source }),
  });

  if (!response.ok) {
    throw new Error(`Failed to submit URL: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Poll job status during processing
 */
export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${apiUrl('/jobs')}?jobId=${encodeURIComponent(jobId)}`);

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Job not found');
    }
    throw new Error(`Failed to get job status: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Load stems manifest for a track
 * The manifest contains video path and stem file references
 * @param slug - Track slug for fallback path
 * @param baseUrl - Optional S3 base URL (e.g., https://bucket.s3.region.amazonaws.com/path)
 */
export async function loadManifest(slug: string, baseUrl?: string): Promise<StemsManifest> {
  const manifestUrl = baseUrl
    ? `${baseUrl}/stems.json`
    : `${VIDEOS_BASE}/${slug}/stems.json`;
  const response = await fetch(manifestUrl);

  if (!response.ok) {
    throw new Error(`Failed to load manifest: ${response.statusText}`);
  }

  return response.json();
}


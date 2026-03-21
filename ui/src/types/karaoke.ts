// Stem definitions
export type StemId = 'vocals' | 'drums' | 'bass' | 'guitar' | 'piano' | 'shizzle';

export interface Stem {
  id: StemId;
  name: string;
  file: string;
  default_gain: number;
}

export interface StemsManifest {
  title: string;
  artist: string;
  duration: number;
  video: string;
  sourceUrl?: string;
  videoId?: string;
  stems: Stem[];
}

export interface Track {
  id: string;
  title: string;
  artist: string;
  slug: string;
  duration: number;
  videoId?: string;
  thumbnailUrl?: string;
  publicUrl: string;
  status?: 'ready' | 'processing' | 'failed';
}

export interface LibraryResponse {
  tracks: Track[];
  total: number;
}

export interface JobStatus {
  jobId: string;
  status: 'pending' | 'downloading' | 'extracting' | 'splitting' | 'encoding' | 'ready' | 'failed';
  progress?: number;
  message?: string;
  error?: string;
}


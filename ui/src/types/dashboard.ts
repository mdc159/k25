// Dashboard Types for Karaoke Pipeline Monitoring

// Worker capabilities for stem splitting control
export interface WorkerCapabilities {
  stem_splitting?: boolean;
}

// Worker status from heartbeat table
export interface WorkerStatus {
  workerId: string;
  status: 'online' | 'offline' | 'error';
  lastHeartbeat: string;
  jobsProcessed: number;
  jobsToday: number;
  currentJobId: string | null;
  circuitBreakers: {
    s3: CircuitBreakerState;
    api: CircuitBreakerState;
  };
  capabilities?: WorkerCapabilities;
}

export type CircuitBreakerState = 'closed' | 'open' | 'half-open';

// Aggregated statistics for dashboard header
export interface DashboardStats {
  workers: {
    online: number;
    total: number;
  };
  queued: number;
  processing: number;
  completed: number;
  failed: number;
}

// Job status values matching Supabase karaoke_jobs.processing_status
export type JobStatus =
  | 'queued'
  | 'leased'
  | 'downloading'
  | 'uploaded_source'
  | 'runpod_processing'
  | 'published'
  | 'failed'
  | 'permanently_failed';

// Processing stage for runpod_processing status
export type ProcessingStage = 'extracting' | 'splitting' | 'encoding' | 'complete';

// Job data for dashboard display
export interface DashboardJob {
  jobId: string;
  title: string;
  artist: string;
  status: JobStatus;
  stage?: ProcessingStage;
  progress: number;
  createdAt: string;
  updatedAt: string;
  retryCount: number;
  lastError?: string;
  workerId?: string;
  // Enhanced tracking fields
  leaseUntil?: string;      // When current lease expires
  stateEnteredAt?: string;  // When job entered current state
  attempts?: number;        // Total processing attempts
}

// Complete dashboard response from API
export interface DashboardData {
  stats: DashboardStats;
  workers: WorkerStatus[];
  activeJobs: DashboardJob[];
  recentJobs: DashboardJob[];
}

export type PipelineHealthStatus = 'healthy' | 'degraded' | 'critical';

export interface PipelineWorkerHealth {
  status: 'online' | 'offline' | 'error';
  lastSeen: string;
  jobsToday: number;
  errorsToday: number;
}

export interface PipelineHealth {
  status: PipelineHealthStatus;
  timestamp: string;
  workers: Record<string, PipelineWorkerHealth>;
  queue: {
    queued: number;
    processing: number;
    completed24h: number;
    failed24h: number;
  };
  lastCompleted?: string | null;
  successRate24h: string;
}

export const PIPELINE_STATUS_COLORS: Record<PipelineHealthStatus, { bg: string; border: string; text: string; dot: string }> = {
  healthy: {
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/40',
    text: 'text-emerald-300',
    dot: 'bg-emerald-400',
  },
  degraded: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/40',
    text: 'text-amber-300',
    dot: 'bg-amber-400',
  },
  critical: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/40',
    text: 'text-red-300',
    dot: 'bg-red-400',
  },
};

// Status color configuration for Archon-style UI
export const STATUS_COLORS = {

  queued: {
    bg: 'bg-pink-500/10',
    border: 'border-pink-500/50',
    glow: 'shadow-pink-500/30',
    text: 'text-pink-400',
  },
  leased: {
    bg: 'bg-pink-500/10',
    border: 'border-pink-500/50',
    glow: 'shadow-pink-500/30',
    text: 'text-pink-400',
  },
  downloading: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/50',
    glow: 'shadow-blue-500/30',
    text: 'text-blue-400',
  },
  uploaded_source: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/50',
    glow: 'shadow-blue-500/30',
    text: 'text-blue-400',
  },
  runpod_processing: {
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/50',
    glow: 'shadow-cyan-500/30',
    text: 'text-cyan-400',
  },
  published: {
    bg: 'bg-green-500/10',
    border: 'border-green-500/50',
    glow: 'shadow-green-500/30',
    text: 'text-green-400',
  },
  failed: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/50',
    glow: 'shadow-red-500/30',
    text: 'text-red-400',
  },
  permanently_failed: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/50',
    glow: 'shadow-red-500/30',
    text: 'text-red-400',
  },
} as const;

// Human-readable status labels
export const STATUS_LABELS: Record<JobStatus, string> = {
  queued: 'Queued',
  leased: 'Claimed',
  downloading: 'Downloading',
  uploaded_source: 'Uploaded',
  runpod_processing: 'Processing',
  published: 'Published',
  failed: 'Failed',
  permanently_failed: 'Failed',
};

// Stage labels for processing display
export const STAGE_LABELS: Record<ProcessingStage, string> = {
  extracting: 'Extracting Audio',
  splitting: 'Separating Stems',
  encoding: 'Encoding',
  complete: 'Finalizing',
};

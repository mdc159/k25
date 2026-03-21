/**
 * Dashboard API Client for Karaoke Pipeline Monitoring
 *
 * Communicates with n8n webhook for real-time dashboard data:
 * - Pipeline statistics (queued, processing, completed, failed)
 * - Worker status and health
 * - Active and recent jobs
 */

import type { DashboardData, DashboardStats, WorkerStatus, DashboardJob, PipelineHealth } from '@/types/dashboard';

// API base URL (same as main api.ts)
const API_BASE = import.meta.env.VITE_API_BASE || '';

// Helper to build API URLs
const apiUrl = (path: string) => API_BASE ? `${API_BASE}${path}` : `/api${path}`;

/**
 * API response wrapper
 */
interface DashboardApiResponse {
  success: boolean;
  error?: string;
  stats: DashboardStats;
  workers: WorkerStatus[];
  activeJobs: DashboardJob[];
  recentJobs: DashboardJob[];
  timestamp: string;
}

// ============================================================================
// Error Types
// ============================================================================

/**
 * Thrown when the network request fails (e.g., no internet, DNS failure)
 */
export class DashboardNetworkError extends Error {
  constructor(message: string = 'Network request failed') {
    super(message);
    this.name = 'DashboardNetworkError';
  }
}

/**
 * Thrown when the dashboard backend returns an error status
 */
export class DashboardApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'DashboardApiError';
    this.status = status;
  }

  get isServerError(): boolean {
    return this.status >= 500;
  }

  get isClientError(): boolean {
    return this.status >= 400 && this.status < 500;
  }
}

/**
 * Thrown when the dashboard backend endpoint is not available (404)
 */
export class DashboardUnavailableError extends Error {
  constructor() {
    super('Dashboard backend is unavailable');
    this.name = 'DashboardUnavailableError';
  }
}

// ============================================================================
// Fallback Data
// ============================================================================

/**
 * Returns empty dashboard data for graceful degradation
 */
export function getEmptyDashboardData(): DashboardData {
  return {
    stats: {
      workers: { online: 0, total: 0 },
      queued: 0,
      processing: 0,
      completed: 0,
      failed: 0,
    },
    workers: [],
    activeJobs: [],
    recentJobs: [],
  };
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch complete dashboard data from n8n webhook
 * Returns stats, workers, active jobs, and recent completions
 *
 * @throws {DashboardNetworkError} When network request fails
 * @throws {DashboardUnavailableError} When backend returns 404
 * @throws {DashboardApiError} When backend returns other error status
 */
export async function getDashboardData(): Promise<DashboardData> {
  let response: Response;

  try {
    response = await fetch(apiUrl('/dashboard'));
  } catch (e) {
    // Network errors (no internet, DNS failure, CORS, etc.)
    if (e instanceof TypeError) {
      throw new DashboardNetworkError('Failed to connect to dashboard API');
    }
    throw new DashboardNetworkError(e instanceof Error ? e.message : 'Unknown network error');
  }

  // Handle specific HTTP status codes
  if (response.status === 404) {
    throw new DashboardUnavailableError();
  }

  if (response.status >= 500) {
    throw new DashboardApiError(
      response.status,
      `Server error: ${response.status} ${response.statusText}`
    );
  }

  if (!response.ok) {
    throw new DashboardApiError(
      response.status,
      `API error: ${response.status} ${response.statusText}`
    );
  }

  let data: DashboardApiResponse;
  try {
    data = await response.json();
  } catch {
    throw new DashboardApiError(response.status, 'Invalid JSON response from dashboard API');
  }

  if (!data.success) {
    throw new DashboardApiError(
      response.status,
      data.error || 'Unknown dashboard error'
    );
  }

  return {
    stats: data.stats,
    workers: data.workers,
    activeJobs: data.activeJobs,
    recentJobs: data.recentJobs,
  };
}

/**
 * Fetch complete dashboard data with fallback on error
 * Returns empty data instead of throwing for graceful degradation
 *
 * @param onError Optional callback to handle errors (for logging/monitoring)
 */
export async function getDashboardDataSafe(
  onError?: (error: Error) => void
): Promise<DashboardData> {
  try {
    return await getDashboardData();
  } catch (e) {
    if (onError && e instanceof Error) {
      onError(e);
    }
    return getEmptyDashboardData();
  }
}

/**
 * Fetch only dashboard stats (lightweight polling option)
 *
 * @throws {DashboardNetworkError} When network request fails
 * @throws {DashboardUnavailableError} When backend returns 404
 * @throws {DashboardApiError} When backend returns other error status
 */
export async function getDashboardStats(): Promise<DashboardStats> {
  const data = await getDashboardData();
  return data.stats;
}

/**
 * Fetch only active jobs (for focused updates)
 *
 * @throws {DashboardNetworkError} When network request fails
 * @throws {DashboardUnavailableError} When backend returns 404
 * @throws {DashboardApiError} When backend returns other error status
 */
export async function getActiveJobs(): Promise<DashboardJob[]> {
  const data = await getDashboardData();
  return data.activeJobs;
}

export async function getPipelineHealth(): Promise<PipelineHealth> {
  let response: Response;

  try {
    response = await fetch(apiUrl('/pipeline-health'));
  } catch (e) {
    if (e instanceof TypeError) {
      throw new DashboardNetworkError('Failed to connect to pipeline health API');
    }
    throw new DashboardNetworkError(e instanceof Error ? e.message : 'Unknown network error');
  }

  if (!response.ok) {
    throw new DashboardApiError(
      response.status,
      `Pipeline health API error: ${response.status} ${response.statusText}`
    );
  }

  const raw = await response.json();
  const workers: PipelineHealth['workers'] = {};
  const workerEntries = raw.workers ? Object.entries(raw.workers as Record<string, any>) : [];

  for (const [workerId, worker] of workerEntries) {
    workers[workerId] = {
      status: worker.status ?? 'offline',
      lastSeen: worker.last_seen ?? worker.lastSeen ?? '',
      jobsToday: worker.jobs_today ?? worker.jobsToday ?? 0,
      errorsToday: worker.errors_today ?? worker.errorsToday ?? 0,
    };
  }

  return {
    status: raw.status ?? 'healthy',
    timestamp: raw.timestamp ?? new Date().toISOString(),
    workers,
    queue: {
      queued: raw.queue?.queued ?? 0,
      processing: raw.queue?.processing ?? 0,
      completed24h: raw.queue?.completed_24h ?? raw.queue?.completed24h ?? 0,
      failed24h: raw.queue?.failed_24h ?? raw.queue?.failed24h ?? 0,
    },
    lastCompleted: raw.last_completed ?? raw.lastCompleted ?? null,
    successRate24h: raw.success_rate_24h ?? raw.successRate24h ?? '100%'
  };
}

/**
 * Update worker capabilities (e.g., stem splitting toggle)
 *
 * @param workerId - The worker ID to update
 * @param capabilities - The capabilities to set
 *
 * @throws {DashboardNetworkError} When network request fails
 * @throws {DashboardApiError} When backend returns error status
 */
export async function updateWorkerCapabilities(
  workerId: string,
  capabilities: { stem_splitting?: boolean }
): Promise<{ success: boolean; workerId: string }> {
  let response: Response;

  try {
    response = await fetch(apiUrl('/worker/capabilities'), {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ workerId, capabilities }),
    });
  } catch (e) {
    if (e instanceof TypeError) {
      throw new DashboardNetworkError('Failed to connect to worker capabilities API');
    }
    throw new DashboardNetworkError(e instanceof Error ? e.message : 'Unknown network error');
  }

  if (!response.ok) {
    throw new DashboardApiError(
      response.status,
      `Worker capabilities API error: ${response.status} ${response.statusText}`
    );
  }

  return response.json();
}

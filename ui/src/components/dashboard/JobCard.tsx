/**
 * JobCard Component
 *
 * Displays individual job progress with:
 * - Title and artist
 * - Progress bar with percentage
 * - Status badge with processing stage
 * - Time since creation
 * - Retry count (if > 0)
 * - Error message (if failed)
 *
 * Uses Archon-style glassmorphism with status-colored edge glow.
 */

import { RefreshCw, AlertCircle, User, Timer, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DashboardJob, JobStatus } from '@/types/dashboard';
import { STATUS_COLORS, STATUS_LABELS, STAGE_LABELS } from '@/types/dashboard';

interface JobCardProps {
  job: DashboardJob;
  className?: string;
}

// Get display status (combines status and stage for processing jobs)
function getDisplayStatus(job: DashboardJob): string {
  if (job.status === 'runpod_processing' && job.stage) {
    return STAGE_LABELS[job.stage] || STATUS_LABELS[job.status];
  }
  return STATUS_LABELS[job.status];
}

// Get progress value (estimated if not provided)
function getProgress(job: DashboardJob): number {
  if (job.progress > 0) return job.progress;

  // Estimate progress based on status/stage
  switch (job.status) {
    case 'queued':
    case 'leased':
      return 0;
    case 'downloading':
      return 5;
    case 'uploaded_source':
      return 10;
    case 'runpod_processing':
      switch (job.stage) {
        case 'extracting':
          return 15;
        case 'splitting':
          return 40;
        case 'encoding':
          return 85;
        case 'complete':
          return 95;
        default:
          return 50;
      }
    case 'published':
      return 100;
    default:
      return 0;
  }
}

// Check if job is in an active processing state
function isProcessing(status: JobStatus): boolean {
  return ['downloading', 'uploaded_source', 'runpod_processing'].includes(status);
}

// Format duration in state
function formatDuration(dateString: string | undefined): string | null {
  if (!dateString) return null;
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);

  if (diffSecs < 60) return `${diffSecs}s`;
  if (diffSecs < 3600) return `${Math.floor(diffSecs / 60)}m ${diffSecs % 60}s`;
  if (diffSecs < 86400) return `${Math.floor(diffSecs / 3600)}h ${Math.floor((diffSecs % 3600) / 60)}m`;
  return `${Math.floor(diffSecs / 86400)}d`;
}

// Check if lease is expired
function isLeaseExpired(leaseUntil: string | undefined): boolean {
  if (!leaseUntil) return false;
  return new Date(leaseUntil) < new Date();
}

// Format lease countdown
function formatLeaseCountdown(leaseUntil: string | undefined): string | null {
  if (!leaseUntil) return null;
  const lease = new Date(leaseUntil);
  const now = new Date();
  const diffMs = lease.getTime() - now.getTime();
  const diffSecs = Math.floor(diffMs / 1000);

  if (diffSecs < 0) {
    const expiredSecs = Math.abs(diffSecs);
    if (expiredSecs < 60) return `expired ${expiredSecs}s ago`;
    if (expiredSecs < 3600) return `expired ${Math.floor(expiredSecs / 60)}m ago`;
    return `expired ${Math.floor(expiredSecs / 3600)}h ago`;
  }

  if (diffSecs < 60) return `${diffSecs}s left`;
  if (diffSecs < 3600) return `${Math.floor(diffSecs / 60)}m left`;
  return `${Math.floor(diffSecs / 3600)}h left`;
}

export function JobCard({ job, className }: JobCardProps) {
  const colors = STATUS_COLORS[job.status];
  const progress = getProgress(job);
  const isFailed = job.status === 'failed' || job.status === 'permanently_failed';
  const isActive = isProcessing(job.status);

  return (
    <div
      className={cn(
        // Glassmorphism base
        'rounded-lg border backdrop-blur-md',
        'bg-white/5 border-white/10',
        'shadow-lg shadow-black/20',
        // Status-colored border and glow
        colors.border,
        `shadow-[0_0_15px_3px] ${colors.glow}`,
        // Layout
        'p-4 space-y-3',
        // Hover effect
        'transition-all duration-200 hover:bg-white/[0.07]',
        className
      )}
    >
      {/* Header: Title and Status Badge */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-medium text-zinc-200 truncate">
            {job.title || 'Untitled'}
          </h4>
          <p className="text-xs text-zinc-500 truncate">
            {job.artist || 'Unknown Artist'}
          </p>
        </div>

        {/* Status badge */}
        <span
          className={cn(
            'text-[10px] px-2 py-1 rounded font-medium whitespace-nowrap',
            colors.bg,
            colors.text
          )}
        >
          {getDisplayStatus(job)}
        </span>
      </div>

      {/* Progress bar */}
      <div className="space-y-1">
        <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all duration-500',
              isFailed
                ? 'bg-gradient-to-r from-red-600 to-red-400'
                : 'bg-gradient-to-r from-cyan-600 to-blue-400',
              isActive && 'animate-pulse'
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-zinc-600">
          <span>Progress</span>
          <span>{progress}%</span>
        </div>
      </div>

      {/* Error message */}
      {isFailed && job.lastError && (
        <div className="flex items-start gap-2 px-2 py-1.5 rounded bg-red-500/10 border border-red-500/20">
          <AlertCircle className="h-3.5 w-3.5 text-red-400 flex-shrink-0 mt-0.5" />
          <span className="text-xs text-red-300 line-clamp-2">{job.lastError}</span>
        </div>
      )}

      {/* Footer: Metadata */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-zinc-500 pt-1 border-t border-white/5">
        {/* Job ID (truncated) */}
        <span className="font-mono truncate max-w-[80px]" title={job.jobId}>
          {job.jobId.slice(0, 12)}...
        </span>

        {/* Time in current state */}
        {job.stateEnteredAt && (
          <div className="flex items-center gap-1">
            <Timer className="h-3 w-3" />
            <span>{formatDuration(job.stateEnteredAt)}</span>
          </div>
        )}

        {/* Lease status (for leased jobs) */}
        {job.leaseUntil && job.status === 'leased' && (
          <div className={cn(
            "flex items-center gap-1",
            isLeaseExpired(job.leaseUntil) ? "text-red-400" : "text-zinc-500"
          )}>
            {isLeaseExpired(job.leaseUntil) && <AlertTriangle className="h-3 w-3" />}
            <span>{formatLeaseCountdown(job.leaseUntil)}</span>
          </div>
        )}

        {/* Worker (if assigned) */}
        {job.workerId && (
          <div className="flex items-center gap-1">
            <User className="h-3 w-3" />
            <span className="truncate max-w-[60px]">{job.workerId.split('-').pop()}</span>
          </div>
        )}

        {/* Attempts count (if > 1) */}
        {(job.attempts ?? 0) > 1 && (
          <div className={cn(
            "flex items-center gap-1",
            (job.attempts ?? 0) >= 3 ? "text-red-400" : "text-yellow-500"
          )}>
            <RefreshCw className="h-3 w-3" />
            <span>×{job.attempts}</span>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * RecentJobsList Component
 *
 * Compact list of recently completed/failed jobs.
 * Shows: Job ID, title, final status, completion time.
 */

import { CheckCircle, XCircle, History, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DashboardJob } from '@/types/dashboard';

interface RecentJobsListProps {
  jobs: DashboardJob[];
  className?: string;
  maxItems?: number;
}

// Format relative time
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);

  if (diffSecs < 60) return 'just now';
  if (diffSecs < 3600) return `${Math.floor(diffSecs / 60)}m ago`;
  if (diffSecs < 86400) return `${Math.floor(diffSecs / 3600)}h ago`;
  return `${Math.floor(diffSecs / 86400)}d ago`;
}

interface RecentJobRowProps {
  job: DashboardJob;
}

function RecentJobRow({ job }: RecentJobRowProps) {
  const isPublished = job.status === 'published';
  const isFailed = job.status === 'failed' || job.status === 'permanently_failed';

  return (
    <div
      className={cn(
        'flex items-center gap-3 py-2 px-3 rounded-md',
        'transition-colors hover:bg-white/5',
        'border-l-2',
        isPublished && 'border-l-green-500/50',
        isFailed && 'border-l-red-500/50'
      )}
    >
      {/* Status icon */}
      {isPublished ? (
        <CheckCircle className="h-4 w-4 text-green-400 flex-shrink-0" />
      ) : (
        <XCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
      )}

      {/* Job info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm text-zinc-300 truncate">
            {job.title || 'Untitled'}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
          <span className="font-mono">{job.jobId.slice(0, 10)}...</span>
          {job.artist && (
            <>
              <span>•</span>
              <span className="truncate">{job.artist}</span>
            </>
          )}
        </div>
      </div>

      {/* Time and status */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <span
          className={cn(
            'text-[10px] px-1.5 py-0.5 rounded',
            isPublished && 'bg-green-500/20 text-green-400',
            isFailed && 'bg-red-500/20 text-red-400'
          )}
        >
          {isPublished ? 'published' : 'failed'}
        </span>

        <span className="text-xs text-zinc-600 w-16 text-right">
          {formatRelativeTime(job.updatedAt)}
        </span>

        {/* View in library link (for published) */}
        {isPublished && (
          <button
            className="p-1 hover:bg-white/10 rounded transition-colors"
            title="View in library"
            onClick={() => {
              // This would navigate to the track in library
              // For now just log it
              console.log('View track:', job.jobId);
            }}
          >
            <ExternalLink className="h-3.5 w-3.5 text-zinc-500 hover:text-zinc-300" />
          </button>
        )}
      </div>
    </div>
  );
}

export function RecentJobsList({ jobs, className, maxItems = 10 }: RecentJobsListProps) {
  // Filter to only completed/failed and limit
  const recentJobs = jobs
    .filter((j) => ['published', 'failed', 'permanently_failed'].includes(j.status))
    .slice(0, maxItems);

  return (
    <div className={cn('space-y-2', className)}>
      {/* Header */}
      <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
        <History className="h-4 w-4 text-zinc-400" />
        Recent Completions
        <span className="text-xs text-zinc-500">({recentJobs.length})</span>
      </h3>

      {/* List */}
      {recentJobs.length === 0 ? (
        <div className="text-center py-6 text-zinc-500 text-sm">
          No completed jobs yet
        </div>
      ) : (
        <div
          className={cn(
            'rounded-lg border backdrop-blur-md',
            'bg-white/[0.02] border-white/10',
            'divide-y divide-white/5'
          )}
        >
          {recentJobs.map((job) => (
            <RecentJobRow key={job.jobId} job={job} />
          ))}
        </div>
      )}
    </div>
  );
}

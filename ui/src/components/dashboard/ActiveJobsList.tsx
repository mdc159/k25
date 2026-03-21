/**
 * ActiveJobsList Component
 *
 * Displays list of active/processing jobs with filtering options.
 * Shows queued, downloading, and processing jobs with progress.
 */

import { useState } from 'react';
import { Filter, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { JobCard } from './JobCard';
import type { DashboardJob } from '@/types/dashboard';

interface ActiveJobsListProps {
  jobs: DashboardJob[];
  className?: string;
}

type FilterType = 'all' | 'queued' | 'downloading' | 'processing';

const FILTER_OPTIONS: { value: FilterType; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'queued', label: 'Queued' },
  { value: 'downloading', label: 'Downloading' },
  { value: 'processing', label: 'Processing' },
];

function matchesFilter(job: DashboardJob, filter: FilterType): boolean {
  if (filter === 'all') return true;
  if (filter === 'queued') return ['queued', 'leased'].includes(job.status);
  if (filter === 'downloading') return ['downloading', 'uploaded_source'].includes(job.status);
  if (filter === 'processing') return job.status === 'runpod_processing';
  return true;
}

export function ActiveJobsList({ jobs, className }: ActiveJobsListProps) {
  const [filter, setFilter] = useState<FilterType>('all');

  const filteredJobs = jobs.filter((job) => matchesFilter(job, filter));

  return (
    <div className={cn('space-y-3', className)}>
      {/* Header with filter */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
          <RefreshCw className="h-4 w-4 text-cyan-400" />
          Active Jobs
          <span className="text-xs text-zinc-500">({filteredJobs.length})</span>
        </h3>

        {/* Filter dropdown */}
        <div className="flex items-center gap-2">
          <Filter className="h-3.5 w-3.5 text-zinc-500" />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as FilterType)}
            className={cn(
              'text-xs bg-zinc-800/50 border border-zinc-700/50 rounded px-2 py-1',
              'text-zinc-300 focus:outline-none focus:ring-1 focus:ring-cyan-500/50'
            )}
          >
            {FILTER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Jobs list */}
      {filteredJobs.length === 0 ? (
        <div className="text-center py-8 text-zinc-500 text-sm">
          <p>No active jobs</p>
          <p className="text-xs mt-1">
            {filter === 'all' ? 'Submit a URL to start processing' : 'No jobs match this filter'}
          </p>
        </div>
      ) : (
        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
          {filteredJobs.map((job) => (
            <JobCard key={job.jobId} job={job} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * WorkerStatusCard Component
 *
 * Displays worker health and status:
 * - Worker ID with online/offline indicator
 * - Last heartbeat (relative time)
 * - Current job being processed
 * - Circuit breaker status (S3, API)
 * - Jobs processed today
 */

import { Server, Heart, Briefcase, Shield, AlertTriangle, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { WorkerStatus, CircuitBreakerState } from '@/types/dashboard';

interface WorkerStatusCardProps {
  worker: WorkerStatus;
  className?: string;
  onCapabilityChange?: (workerId: string, capability: string, enabled: boolean) => void;
}

// Simple relative time formatter
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);

  if (diffSecs < 5) return 'just now';
  if (diffSecs < 60) return `${diffSecs}s ago`;
  if (diffSecs < 3600) return `${Math.floor(diffSecs / 60)}m ago`;
  if (diffSecs < 86400) return `${Math.floor(diffSecs / 3600)}h ago`;
  return `${Math.floor(diffSecs / 86400)}d ago`;
}

// Circuit breaker status indicator
function CircuitBreakerBadge({
  name,
  state,
}: {
  name: string;
  state: CircuitBreakerState;
}) {
  const colors = {
    closed: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'OK' },
    open: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'OPEN' },
    'half-open': { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'HALF' },
  };
  const color = colors[state];

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-zinc-500">{name}</span>
      <span
        className={cn(
          'text-[10px] px-1.5 py-0.5 rounded font-medium',
          color.bg,
          color.text
        )}
      >
        {color.label}
      </span>
    </div>
  );
}

export function WorkerStatusCard({ worker, className, onCapabilityChange }: WorkerStatusCardProps) {
  const isOnline = worker.status === 'online';
  const hasError = worker.status === 'error';
  const stemSplitting = worker.capabilities?.stem_splitting ?? true;

  return (
    <div
      className={cn(
        // Glassmorphism base
        'rounded-lg border backdrop-blur-md',
        'bg-white/5 border-white/10',
        'shadow-lg shadow-black/20',
        // Conditional border glow
        isOnline && 'border-green-500/30 shadow-[0_0_20px_5px_rgba(34,197,94,0.1)]',
        hasError && 'border-red-500/30 shadow-[0_0_20px_5px_rgba(239,68,68,0.1)]',
        !isOnline && !hasError && 'border-zinc-500/30',
        // Layout
        'p-4 space-y-3',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-zinc-400" />
          <span className="text-sm font-medium text-zinc-200 truncate max-w-[200px]">
            {worker.workerId}
          </span>
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-2">
          <div
            className={cn(
              'h-2.5 w-2.5 rounded-full',
              isOnline && 'bg-green-500 shadow-[0_0_8px_2px_rgba(34,197,94,0.6)]',
              hasError && 'bg-red-500 shadow-[0_0_8px_2px_rgba(239,68,68,0.6)] animate-pulse',
              !isOnline && !hasError && 'bg-zinc-500'
            )}
          />
          <span
            className={cn(
              'text-xs font-medium',
              isOnline && 'text-green-400',
              hasError && 'text-red-400',
              !isOnline && !hasError && 'text-zinc-500'
            )}
          >
            {worker.status.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-4 text-xs">
        {/* Last heartbeat */}
        <div className="flex items-center gap-1.5 text-zinc-400">
          <Heart className="h-3.5 w-3.5" />
          <span>{formatRelativeTime(worker.lastHeartbeat)}</span>
        </div>

        {/* Jobs today */}
        <div className="flex items-center gap-1.5 text-zinc-400">
          <Briefcase className="h-3.5 w-3.5" />
          <span>{worker.jobsToday} today</span>
        </div>
      </div>

      {/* Current job */}
      {worker.currentJobId && (
        <div className="flex items-center gap-2 px-2 py-1.5 rounded bg-cyan-500/10 border border-cyan-500/20">
          <div className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-xs text-cyan-300 truncate">
            Processing: {worker.currentJobId}
          </span>
        </div>
      )}

      {/* Circuit breakers */}
      <div className="flex items-center gap-3 pt-1 border-t border-white/5">
        <Shield className="h-3.5 w-3.5 text-zinc-500" />
        <CircuitBreakerBadge name="S3" state={worker.circuitBreakers.s3} />
        <CircuitBreakerBadge name="API" state={worker.circuitBreakers.api} />

        {/* Show warning if any circuit breaker is not closed */}
        {(worker.circuitBreakers.s3 !== 'closed' || worker.circuitBreakers.api !== 'closed') && (
          <AlertTriangle className="h-3.5 w-3.5 text-yellow-400 ml-auto" />
        )}
      </div>

      {/* Capabilities toggle */}
      <div className="flex items-center justify-between pt-2 border-t border-white/5">
        <div className="flex items-center gap-2">
          <Settings className="h-3.5 w-3.5 text-zinc-500" />
          <span className="text-xs text-zinc-400">Stem Splitting</span>
        </div>
        <button
          onClick={() => onCapabilityChange?.(worker.workerId, 'stem_splitting', !stemSplitting)}
          className={cn(
            'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
            stemSplitting ? 'bg-cyan-500' : 'bg-zinc-600'
          )}
          aria-label={`Stem splitting ${stemSplitting ? 'enabled' : 'disabled'}`}
        >
          <span
            className={cn(
              'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform',
              stemSplitting ? 'translate-x-5' : 'translate-x-1'
            )}
          />
        </button>
      </div>
    </div>
  );
}

// List of workers component
interface WorkerStatusListProps {
  workers: WorkerStatus[];
  className?: string;
  onCapabilityChange?: (workerId: string, capability: string, enabled: boolean) => void;
}

export function WorkerStatusList({ workers, className, onCapabilityChange }: WorkerStatusListProps) {
  if (workers.length === 0) {
    return (
      <div className={cn('text-center py-6 text-zinc-500 text-sm', className)}>
        No workers registered
      </div>
    );
  }

  return (
    <div className={cn('space-y-3', className)}>
      {workers.map((worker) => (
        <WorkerStatusCard
          key={worker.workerId}
          worker={worker}
          onCapabilityChange={onCapabilityChange}
        />
      ))}
    </div>
  );
}

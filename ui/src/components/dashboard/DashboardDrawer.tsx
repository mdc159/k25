/**
 * DashboardDrawer Component
 *
 * Full-page overlay dashboard for pipeline monitoring.
 * Composed from: StatsGrid, WorkerStatusCard, ActiveJobsList, RecentJobsList
 *
 * Features:
 * - Real-time data polling via useDashboard hook
 * - Manual refresh button
 * - Last update timestamp
 * - Error/loading states
 */

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { RefreshCw, X, Activity, Wifi, WifiOff, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useDashboard } from '@/hooks/useDashboard';
import { useStore } from '@/stores/useStore';
import { StatsGrid } from './StatsGrid';
import { WorkerStatusList } from './WorkerStatusCard';
import { ActiveJobsList } from './ActiveJobsList';
import { RecentJobsList } from './RecentJobsList';

// Loading skeleton for stats
function StatsSkeleton() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {[...Array(4)].map((_, i) => (
        <div
          key={i}
          className="h-24 rounded-lg bg-zinc-800/50 animate-pulse"
        />
      ))}
    </div>
  );
}

// Loading skeleton for cards
function CardSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {[...Array(rows)].map((_, i) => (
        <div
          key={i}
          className="h-24 rounded-lg bg-zinc-800/50 animate-pulse"
        />
      ))}
    </div>
  );
}

// Format time for last update display
function formatUpdateTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function DashboardDrawer() {
  const { activeDrawer, setActiveDrawer } = useStore();
  const isOpen = activeDrawer === 'dashboard';

  const {
    data,
    loading,
    error,
    lastUpdated,
    isPolling,
    refresh,
  } = useDashboard({ pollingInterval: 3000 });

  const handleClose = () => setActiveDrawer('none');

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent
        className={cn(
          // Full-page overlay styling
          'fixed inset-4 max-w-none translate-x-0 translate-y-0 left-0 top-0',
          'sm:rounded-xl overflow-hidden',
          // Glassmorphism
          'bg-zinc-950/95 backdrop-blur-xl border-zinc-800',
          // Custom dimensions
          'w-[calc(100%-2rem)] h-[calc(100%-2rem)]',
          'flex flex-col'
        )}
      >
        {/* Header */}
        <DialogHeader className="flex-shrink-0 border-b border-zinc-800 pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-cyan-500/10">
                <Activity className="h-5 w-5 text-cyan-400" />
              </div>
              <div>
                <DialogTitle className="text-xl text-zinc-100">
                  Pipeline Dashboard
                </DialogTitle>
                <DialogDescription className="text-zinc-500">
                  Real-time karaoke processing status
                </DialogDescription>
              </div>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-3">
              {/* Polling status */}
              <div className="flex items-center gap-2 text-xs text-zinc-500">
                {isPolling ? (
                  <Wifi className="h-3.5 w-3.5 text-green-400" />
                ) : (
                  <WifiOff className="h-3.5 w-3.5 text-zinc-600" />
                )}
                {lastUpdated && (
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatUpdateTime(lastUpdated)}
                  </span>
                )}
              </div>

              {/* Refresh button */}
              <Button
                variant="outline"
                size="sm"
                onClick={refresh}
                disabled={loading}
                className="border-zinc-700 hover:bg-zinc-800"
              >
                <RefreshCw className={cn('h-4 w-4 mr-2', loading && 'animate-spin')} />
                Refresh
              </Button>

              {/* Close button */}
              <Button
                variant="ghost"
                size="icon"
                onClick={handleClose}
                className="hover:bg-zinc-800"
              >
                <X className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </DialogHeader>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Error state */}
          {error && (
            <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400">
              <p className="font-medium">Failed to load dashboard</p>
              <p className="text-sm mt-1 opacity-80">{error}</p>
            </div>
          )}

          {/* Stats Grid */}
          <section>
            {loading && !data ? (
              <StatsSkeleton />
            ) : data ? (
              <StatsGrid stats={data.stats} />
            ) : null}
          </section>

          {/* Main content grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left column: Workers + Active Jobs */}
            <div className="lg:col-span-2 space-y-6">
              {/* Workers */}
              <section>
                <h3 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                  Workers
                </h3>
                {loading && !data ? (
                  <CardSkeleton rows={1} />
                ) : data ? (
                  <WorkerStatusList workers={data.workers} />
                ) : null}
              </section>

              {/* Active Jobs */}
              <section>
                {loading && !data ? (
                  <CardSkeleton rows={3} />
                ) : data ? (
                  <ActiveJobsList jobs={data.activeJobs} />
                ) : null}
              </section>
            </div>

            {/* Right column: Recent Jobs */}
            <div className="lg:col-span-1">
              {loading && !data ? (
                <CardSkeleton rows={5} />
              ) : data ? (
                <RecentJobsList jobs={data.recentJobs} />
              ) : null}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

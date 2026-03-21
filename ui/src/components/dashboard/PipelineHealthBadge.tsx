import { useMemo } from 'react';
import { AlertTriangle, Activity, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useStore } from '@/stores/useStore';
import { usePipelineHealth } from '@/hooks/usePipelineHealth';
import { PIPELINE_STATUS_COLORS } from '@/types/dashboard';
import type { PipelineHealthStatus } from '@/types/dashboard';

const STATUS_LABELS: Record<PipelineHealthStatus, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  critical: 'Critical',
};

export function PipelineHealthBadge() {
  const { setActiveDrawer } = useStore();
  const { data, loading, error, refresh } = usePipelineHealth({ interval: 20000 });

  const status = data?.status ?? 'healthy';
  const colors = PIPELINE_STATUS_COLORS[status];
  const timestamp = useMemo(() => {
    if (!data?.timestamp) return null;
    const date = new Date(data.timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }, [data?.timestamp]);

  if (error) {
    return (
      <div className="flex items-center gap-3 rounded-full border border-red-500/40 bg-red-500/10 px-4 py-2 text-xs text-red-300 shadow-lg shadow-red-900/20">
        <AlertTriangle className="h-4 w-4" />
        <span className="font-medium">Health check failed</span>
        <Button size="sm" variant="ghost" className="h-7 px-2 text-red-200 hover:bg-red-500/20" onClick={refresh}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-zinc-800/60 bg-black/60 px-4 py-3 text-xs text-zinc-300 shadow-lg shadow-black/40 backdrop-blur">
      <div className="flex items-center justify-between gap-4">
        <div className={cn('flex items-center gap-2 rounded-full border px-3 py-1 text-emerald-200 text-xs font-semibold', colors.bg, colors.border, colors.text)}>
          <span className={cn('h-2.5 w-2.5 rounded-full', colors.dot)} />
          {loading && !data ? 'Checking…' : `${STATUS_LABELS[status]} Pipeline`}
        </div>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-zinc-300 hover:bg-zinc-800"
          onClick={() => setActiveDrawer('dashboard')}
        >
          <Activity className="mr-1 h-3.5 w-3.5" />
          Dashboard
        </Button>
      </div>

      <div className="flex items-center justify-between text-[11px] text-zinc-400">
        <div className="flex items-center gap-3">
          <div>
            <span className="text-zinc-200 font-semibold mr-1">{data?.queue.queued ?? '—'}</span>
            queued
          </div>
          <div>
            <span className="text-zinc-200 font-semibold mr-1">{data?.queue.processing ?? '—'}</span>
            processing
          </div>
          <div>
            <span className="text-zinc-200 font-semibold mr-1">{data?.successRate24h ?? '—'}</span>
            success
          </div>
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-1 text-zinc-500 hover:text-zinc-200"
          onClick={refresh}
          title="Refresh pipeline health"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
          {timestamp ? `Updated ${timestamp}` : 'Refresh'}
        </button>
      </div>
    </div>
  );
}

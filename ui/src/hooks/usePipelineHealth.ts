import { useCallback, useEffect, useRef, useState } from 'react';
import { getPipelineHealth } from '@/lib/dashboard-api';
import type { PipelineHealth } from '@/types/dashboard';

interface UsePipelineHealthOptions {
    interval?: number;
  immediate?: boolean;
}

interface UsePipelineHealthReturn {
  data: PipelineHealth | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function usePipelineHealth(options: UsePipelineHealthOptions = {}): UsePipelineHealthReturn {
  const { interval = 15000, immediate = true } = options;

  const [data, setData] = useState<PipelineHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  const fetchSnapshot = useCallback(async () => {
    try {
      const snapshot = await getPipelineHealth();
      setData(snapshot);
      setError(null);
      setLoading(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch pipeline health';
      setError(message);
      setLoading(false);
      console.error('Pipeline health fetch failed:', err);
    }
  }, []);

  const scheduleNext = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = window.setTimeout(() => {
      fetchSnapshot().finally(() => {
        scheduleNext();
      });
    }, interval);
  }, [fetchSnapshot, interval]);

  useEffect(() => {
    if (immediate) {
      fetchSnapshot().then(() => {
        scheduleNext();
      });
    } else {
      scheduleNext();
    }

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [fetchSnapshot, scheduleNext, immediate]);

  const refresh = useCallback(async () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    await fetchSnapshot();
    scheduleNext();
  }, [fetchSnapshot, scheduleNext]);

  return { data, loading, error, refresh };
}

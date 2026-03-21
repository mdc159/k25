/**
 * useDashboard Hook
 *
 * Provides real-time dashboard data with smart polling:
 * - Pauses when tab is not visible (saves bandwidth)
 * - Exponential backoff on errors
 * - Manual refresh capability
 * - Automatic cleanup on unmount
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { getDashboardData } from '@/lib/dashboard-api';
import type { DashboardData } from '@/types/dashboard';

interface UseDashboardOptions {
  /** Polling interval in milliseconds (default: 3000) */
  pollingInterval?: number;
  /** Maximum backoff interval on errors (default: 30000) */
  maxBackoff?: number;
  /** Whether to start polling immediately (default: true) */
  autoStart?: boolean;
}

interface UseDashboardReturn {
  /** Dashboard data (null while loading or on error) */
  data: DashboardData | null;
  /** Whether initial load is in progress */
  loading: boolean;
  /** Error message (null if no error) */
  error: string | null;
  /** Timestamp of last successful update */
  lastUpdated: Date | null;
  /** Whether polling is currently active */
  isPolling: boolean;
  /** Manually trigger a refresh */
  refresh: () => Promise<void>;
  /** Start polling (if stopped) */
  startPolling: () => void;
  /** Stop polling */
  stopPolling: () => void;
}

const BASE_BACKOFF = 1000; // 1 second

export function useDashboard(options: UseDashboardOptions = {}): UseDashboardReturn {
  const {
    pollingInterval = 3000,
    maxBackoff = 30000,
    autoStart = true,
  } = options;

  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isPolling, setIsPolling] = useState(autoStart);

  // Refs for managing polling state
  const timeoutRef = useRef<number | null>(null);
  const consecutiveErrorsRef = useRef(0);
  const currentIntervalRef = useRef(pollingInterval);
  const isVisibleRef = useRef(true);
  const isMountedRef = useRef(true);

  // Fetch dashboard data
  const fetchData = useCallback(async () => {
    if (!isMountedRef.current) return;

    try {
      const result = await getDashboardData();

      if (!isMountedRef.current) return;

      setData(result);
      setError(null);
      setLastUpdated(new Date());
      setLoading(false);

      // Reset backoff on success
      consecutiveErrorsRef.current = 0;
      currentIntervalRef.current = pollingInterval;
    } catch (err) {
      if (!isMountedRef.current) return;

      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch dashboard';
      setError(errorMessage);
      setLoading(false);

      // Exponential backoff on errors
      consecutiveErrorsRef.current++;
      currentIntervalRef.current = Math.min(
        BASE_BACKOFF * Math.pow(2, consecutiveErrorsRef.current),
        maxBackoff
      );

      console.error(
        `Dashboard fetch error (attempt ${consecutiveErrorsRef.current}, next in ${currentIntervalRef.current}ms):`,
        err
      );
    }
  }, [pollingInterval, maxBackoff]);

  // Schedule next poll
  const schedulePoll = useCallback(() => {
    if (!isMountedRef.current || !isPolling) return;

    // Don't poll if tab is not visible
    if (!isVisibleRef.current) return;

    timeoutRef.current = window.setTimeout(async () => {
      await fetchData();
      schedulePoll();
    }, currentIntervalRef.current);
  }, [fetchData, isPolling]);

  // Clear any pending timeout
  const clearPoll = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  // Manual refresh
  const refresh = useCallback(async () => {
    clearPoll();
    setLoading(true);
    await fetchData();
    if (isPolling && isVisibleRef.current) {
      schedulePoll();
    }
  }, [clearPoll, fetchData, schedulePoll, isPolling]);

  // Start polling
  const startPolling = useCallback(() => {
    setIsPolling(true);
    consecutiveErrorsRef.current = 0;
    currentIntervalRef.current = pollingInterval;
  }, [pollingInterval]);

  // Stop polling
  const stopPolling = useCallback(() => {
    setIsPolling(false);
    clearPoll();
  }, [clearPoll]);

  // Handle visibility changes
  useEffect(() => {
    const handleVisibilityChange = () => {
      const isVisible = document.visibilityState === 'visible';
      isVisibleRef.current = isVisible;

      if (isVisible && isPolling) {
        // Tab became visible - fetch immediately and resume polling
        fetchData().then(() => {
          schedulePoll();
        });
      } else {
        // Tab hidden - stop polling
        clearPoll();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchData, schedulePoll, clearPoll, isPolling]);

  // Initial fetch and polling setup
  useEffect(() => {
    isMountedRef.current = true;

    // Initial fetch
    fetchData().then(() => {
      if (isPolling) {
        schedulePoll();
      }
    });

    return () => {
      isMountedRef.current = false;
      clearPoll();
    };
  }, [fetchData, schedulePoll, clearPoll, isPolling]);

  // Restart polling when isPolling changes to true
  useEffect(() => {
    if (isPolling && !timeoutRef.current && isVisibleRef.current) {
      schedulePoll();
    }
  }, [isPolling, schedulePoll]);

  return {
    data,
    loading,
    error,
    lastUpdated,
    isPolling,
    refresh,
    startPolling,
    stopPolling,
  };
}

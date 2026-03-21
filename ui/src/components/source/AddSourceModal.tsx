import React, { useState, useEffect, useRef } from 'react';
import { useStore } from '@/stores/useStore';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Loader2, Plus, Check, X, AlertCircle } from 'lucide-react';
import { submitSource, getJobStatus } from '@/lib/api';
import { toast } from 'sonner';
import type { JobStatus } from '@/types/karaoke';
import { cn } from '@/lib/utils';

// Processing steps for progress display
const STEPS = [
  { status: 'pending', label: 'Queued' },
  { status: 'downloading', label: 'Downloading' },
  { status: 'extracting', label: 'Extracting Audio' },
  { status: 'splitting', label: 'Separating Stems' },
  { status: 'encoding', label: 'Encoding' },
  { status: 'ready', label: 'Complete' },
] as const;

// Polling configuration
const BASE_POLL_INTERVAL = 3000;  // 3 seconds
const MAX_POLL_INTERVAL = 30000;  // 30 seconds max backoff
const MAX_POLL_DURATION = 30 * 60 * 1000;  // 30 minutes timeout

export const AddSourceModal: React.FC = () => {
  const { activeDrawer, setActiveDrawer, setActiveJob } = useStore();
  const isOpen = activeDrawer === 'source';

  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);

  const pollIntervalRef = useRef<number | null>(null);
  const pollStartTimeRef = useRef<number>(0);
  const consecutiveErrorsRef = useRef<number>(0);
  const currentPollIntervalRef = useRef<number>(BASE_POLL_INTERVAL);

  // Cleanup polling on unmount or close
  useEffect(() => {
    return () => stopPolling();
  }, []);

  // Stop polling when modal closes
  useEffect(() => {
    if (!isOpen) {
      stopPolling();
    }
  }, [isOpen]);

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearTimeout(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    consecutiveErrorsRef.current = 0;
    currentPollIntervalRef.current = BASE_POLL_INTERVAL;
  };

  const schedulePoll = (id: string) => {
    pollIntervalRef.current = window.setTimeout(async () => {
      // Check for timeout
      const elapsed = Date.now() - pollStartTimeRef.current;
      if (elapsed > MAX_POLL_DURATION) {
        stopPolling();
        setError('Processing timeout - job may be stuck. Check the dashboard or try again.');
        setLoading(false);
        toast.error('Processing timeout');
        return;
      }

      try {
        const status = await getJobStatus(id);
        setJobStatus(status);
        setActiveJob(status);

        // Reset backoff on success
        consecutiveErrorsRef.current = 0;
        currentPollIntervalRef.current = BASE_POLL_INTERVAL;

        if (status.status === 'ready') {
          stopPolling();
          toast.success('Track ready! Refresh library to see it.');
          setTimeout(() => {
            handleClose();
          }, 2000);
        } else if (status.status === 'failed') {
          stopPolling();
          setError(status.error || 'Processing failed');
          setLoading(false);
          toast.error('Processing failed');
        } else {
          // Continue polling
          schedulePoll(id);
        }
      } catch (err) {
        // Exponential backoff on errors
        consecutiveErrorsRef.current++;
        currentPollIntervalRef.current = Math.min(
          BASE_POLL_INTERVAL * Math.pow(2, consecutiveErrorsRef.current),
          MAX_POLL_INTERVAL
        );
        console.error(`Poll error (attempt ${consecutiveErrorsRef.current}, next in ${currentPollIntervalRef.current}ms):`, err);

        // Continue polling with backoff
        schedulePoll(id);
      }
    }, currentPollIntervalRef.current);
  };

  const startPolling = (id: string) => {
    stopPolling();
    pollStartTimeRef.current = Date.now();
    schedulePoll(id);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setJobStatus(null);

    try {
      const result = await submitSource(url);
      setJobId(result.jobId);
      setJobStatus({ jobId: result.jobId, status: 'pending' });
      toast.success('Processing started');
      startPolling(result.jobId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit');
      setLoading(false);
      toast.error('Failed to submit URL');
    }
  };

  const handleClose = () => {
    stopPolling();
    setUrl('');
    setLoading(false);
    setError(null);
    setJobId(null);
    setJobStatus(null);
    setActiveJob(null);
    setActiveDrawer('none');
  };

  const handleRetry = () => {
    setError(null);
    setJobStatus(null);
    setJobId(null);
    setLoading(false);
  };

  // Get current step index for progress display
  const getCurrentStepIndex = () => {
    if (!jobStatus) return -1;
    return STEPS.findIndex(s => s.status === jobStatus.status);
  };

  const currentStepIndex = getCurrentStepIndex();

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-[425px] bg-zinc-950 border-zinc-800 text-zinc-100">
        <DialogHeader>
          <DialogTitle>Add Source</DialogTitle>
          <DialogDescription className="text-zinc-500">
            {jobStatus ? 'Processing your track...' : 'Enter a YouTube URL or local file path.'}
          </DialogDescription>
        </DialogHeader>

        {!jobStatus ? (
          // URL Input Form
          <form onSubmit={handleSubmit} className="space-y-4 py-4">
            <div className="space-y-2">
              <input
                required
                type="text"
                placeholder="YouTube URL or /path/to/video.mp4"
                className="w-full bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-600"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={loading}
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 text-red-400 text-sm">
                <AlertCircle className="h-4 w-4" />
                {error}
              </div>
            )}

            <DialogFooter>
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                {loading ? "Submitting..." : "Import Track"}
              </Button>
            </DialogFooter>
          </form>
        ) : (
          // Progress Display
          <div className="py-6 space-y-6">
            {/* Progress Steps */}
            <div className="space-y-3">
              {STEPS.map((step, idx) => {
                const isComplete = idx < currentStepIndex;
                const isCurrent = idx === currentStepIndex;
                const isPending = idx > currentStepIndex;
                const isFailed = jobStatus.status === 'failed' && isCurrent;

                return (
                  <div
                    key={step.status}
                    className={cn(
                      "flex items-center gap-3 text-sm transition-colors",
                      isComplete && "text-green-400",
                      isCurrent && !isFailed && "text-white font-medium",
                      isFailed && "text-red-400",
                      isPending && "text-zinc-600"
                    )}
                  >
                    {/* Status Icon */}
                    <div className={cn(
                      "h-6 w-6 rounded-full flex items-center justify-center border",
                      isComplete && "bg-green-500/20 border-green-500",
                      isCurrent && !isFailed && "bg-white/10 border-white animate-pulse",
                      isFailed && "bg-red-500/20 border-red-500",
                      isPending && "bg-zinc-800 border-zinc-700"
                    )}>
                      {isComplete && <Check className="h-3 w-3" />}
                      {isCurrent && !isFailed && <Loader2 className="h-3 w-3 animate-spin" />}
                      {isFailed && <X className="h-3 w-3" />}
                    </div>

                    <span>{step.label}</span>
                  </div>
                );
              })}
            </div>

            {/* Error State */}
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
                <p className="font-medium">Processing Failed</p>
                <p className="text-red-400/80 mt-1">{error}</p>
              </div>
            )}

            {/* Job ID for reference */}
            {jobId && (
              <div className="text-xs text-zinc-600 font-mono">
                Job ID: {jobId}
              </div>
            )}

            {/* Actions */}
            <DialogFooter>
              {error ? (
                <Button onClick={handleRetry} variant="outline" className="w-full">
                  Try Again
                </Button>
              ) : jobStatus.status === 'ready' ? (
                <Button onClick={handleClose} className="w-full">
                  <Check className="mr-2 h-4 w-4" />
                  Done
                </Button>
              ) : (
                <Button onClick={handleClose} variant="ghost" className="w-full">
                  Run in Background
                </Button>
              )}
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

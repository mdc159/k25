/**
 * useAudioSync Hook
 *
 * Manages synchronization between video playback and audio stems.
 * - Loads stems when manifest changes
 * - Syncs play/pause between video and audioManager
 * - Applies stem gains from store to audioManager
 * - Handles periodic drift correction
 */

import { useEffect, useRef, useCallback } from 'react';
import { useStore } from '@/stores/useStore';
import { audioManager, StemAudioManager } from '@/lib/audio';
import type { StemId } from '@/types/karaoke';

interface UseAudioSyncOptions {
  videoRef: React.RefObject<HTMLVideoElement | null>;
}

interface UseAudioSyncReturn {
  isReady: boolean;
  handleSeek: (time: number) => void;
  handlePlay: () => Promise<void>;
  handlePause: () => void;
}

export function useAudioSync({ videoRef }: UseAudioSyncOptions): UseAudioSyncReturn {
  const {
    manifest,
    currentTrack,
    playing,
    stemGains,
    setPlaying,
  } = useStore();

  const isReadyRef = useRef(false);
  const syncIntervalRef = useRef<number | null>(null);

  // Load stems when manifest changes
  useEffect(() => {
    if (!manifest || !currentTrack) {
      isReadyRef.current = false;
      return;
    }

    const loadStems = async () => {
      try {
        // Build base path from track's public URL (S3) or fallback to VPS path
        const basePath = currentTrack.publicUrl || `/videos/${currentTrack.slug}`;

        await audioManager.loadStems(basePath, manifest.stems);
        isReadyRef.current = true;

        // Apply current gain settings from store
        Object.entries(stemGains).forEach(([stem, dbValue]) => {
          const linearGain = StemAudioManager.dbToLinear(dbValue);
          audioManager.setGain(stem as StemId, linearGain);
        });

        // Start playing if requested
        if (playing) {
          await audioManager.play();
        }
      } catch (err) {
        console.error('Failed to load stems:', err);
        isReadyRef.current = false;
      }
    };

    loadStems();

    return () => {
      audioManager.cleanup();
      isReadyRef.current = false;
    };
  }, [manifest, currentTrack?.slug]);

  // Sync play/pause state
  useEffect(() => {
    if (!isReadyRef.current) return;

    if (playing) {
      // CRITICAL: Sync audio to video time BEFORE playing to prevent drift
      if (videoRef.current) {
        audioManager.syncToVideoTime(videoRef.current.currentTime);
      }
      audioManager.play().catch(console.error);
      startSyncInterval();
    } else {
      audioManager.pause();
      stopSyncInterval();
    }
  }, [playing, videoRef]);

  // Apply gain changes from store to audio engine
  useEffect(() => {
    if (!isReadyRef.current) return;

    Object.entries(stemGains).forEach(([stem, dbValue]) => {
      const linearGain = StemAudioManager.dbToLinear(dbValue);
      audioManager.setGain(stem as StemId, linearGain);
    });
  }, [stemGains]);

  // Periodic sync to handle drift
  const startSyncInterval = useCallback(() => {
    stopSyncInterval();
    syncIntervalRef.current = window.setInterval(() => {
      if (videoRef.current && isReadyRef.current) {
        audioManager.syncToVideoTime(videoRef.current.currentTime);
      }
    }, 5000);
  }, [videoRef]);

  const stopSyncInterval = useCallback(() => {
    if (syncIntervalRef.current) {
      clearInterval(syncIntervalRef.current);
      syncIntervalRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopSyncInterval();
      audioManager.cleanup();
    };
  }, [stopSyncInterval]);

  // Seek handler - syncs both video and audio
  const handleSeek = useCallback((time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
    }
    if (isReadyRef.current) {
      audioManager.seek(time);
    }
  }, [videoRef]);

  // Play handler - starts both video and audio
  const handlePlay = useCallback(async () => {
    if (videoRef.current && isReadyRef.current) {
      try {
        await Promise.all([
          videoRef.current.play(),
          audioManager.play(),
        ]);
        setPlaying(true);
      } catch (err) {
        console.error('Failed to start playback:', err);
      }
    }
  }, [videoRef, setPlaying]);

  // Pause handler - pauses both video and audio
  const handlePause = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.pause();
    }
    if (isReadyRef.current) {
      audioManager.pause();
    }
    setPlaying(false);
  }, [videoRef, setPlaying]);

  return {
    isReady: isReadyRef.current,
    handleSeek,
    handlePlay,
    handlePause,
  };
}

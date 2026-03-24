"""
Karaoke Agent - Main worker implementation.

Orchestrates the karaoke processing pipeline:
1. Claims jobs from VPS API via n8n webhooks
2. Downloads YouTube videos using yt-dlp (residential IP)
3. Uploads source.mp4 + metadata.json to S3
4. Reports health via heartbeats to Supabase

Uses modular components:
- config: Pydantic-based configuration
- supabase_client: Backend API operations
- s3_multipart: Robust multipart uploads
- yt_dlp_wrapper: YouTube downloads
- utils.circuit_breaker: Failure protection
"""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from karaoke_agent.config import Settings, load_settings
from karaoke_agent import demucs
from karaoke_agent.s3_multipart import S3MultipartUploader, S3UploadConfig
from karaoke_agent.supabase_client import BackendClient, JobClaim
from karaoke_agent.utils import CircuitBreaker
from karaoke_agent.yt_dlp_wrapper import YtDlpConfig, YtDlpWrapper

if TYPE_CHECKING:
    from types import FrameType

logger = logging.getLogger(__name__)


@dataclass
class JobResult:
    """Result of processing a single job."""

    job_id: str
    success: bool
    s3_key: str | None = None
    error: str | None = None
    download_mb: float = 0.0
    upload_seconds: float = 0.0


class KaraokeAgent:
    """
    Worker agent for karaoke video processing.

    Coordinates:
    - Job claiming and status updates
    - YouTube video downloads
    - S3 multipart uploads
    - Health heartbeats
    - Lease renewal for long-running jobs
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """
        Initialize the karaoke agent.

        Args:
            settings: Optional settings (loads from env if not provided)
        """
        self.settings = settings or load_settings()

        # Initialize circuit breakers
        self._s3_circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.worker.circuit_breaker_threshold,
            timeout_seconds=self.settings.worker.circuit_breaker_timeout,
            name="s3",
        )
        self._api_circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.worker.circuit_breaker_threshold,
            timeout_seconds=self.settings.worker.circuit_breaker_timeout,
            name="api",
        )

        # Initialize backend client
        self._backend = BackendClient(
            supabase_config=self.settings.supabase,
            api_config=self.settings.api,
            worker_config=self.settings.worker,
            circuit_breaker=self._api_circuit_breaker,
        )

        # Initialize S3 uploader
        self._s3_config = S3UploadConfig(
            endpoint=self.settings.s3.endpoint,
            bucket=self.settings.s3.bucket,
            access_key=self.settings.s3.access_key,
            secret_key=self.settings.s3.secret_key,
            region=self.settings.s3.region,
            part_size_mb=self.settings.s3.part_size_mb,
            max_retries=self.settings.s3.max_retries,
            max_concurrency=self.settings.s3.max_concurrency,
        )
        self._s3_uploader = S3MultipartUploader(self._s3_config)

        # Initialize yt-dlp wrapper
        self._yt_dlp = YtDlpWrapper(
            YtDlpConfig(
                retries=self.settings.worker.max_retries,
                fragment_retries=self.settings.worker.max_retries,
            )
        )

        # Worker state
        self._shutdown_requested = False
        self._current_job_id: str | None = None

        # Shutdown event for efficient waiting (replaces busy-wait loops)
        self._shutdown_event = threading.Event()

        # Background threads
        self._heartbeat_thread: threading.Thread | None = None
        self._lease_thread: threading.Thread | None = None
        self._lease_job_id: str | None = None
        self._lease_stop_event: threading.Event | None = None

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        # Detect GPU capability at startup
        self._gpu_available = self._detect_gpu()

        # Log initialization
        logger.info(f"Karaoke Agent initialized: worker_id={self.settings.worker.worker_id}")
        logger.info(f"API Base: {self.settings.api.base_url}")
        logger.info(f"S3 Bucket: {self.settings.s3.bucket}")
        logger.info(f"GPU available: {self._gpu_available}")
        logger.info(
            f"Stem splitting enabled: {self.settings.worker.stem_splitting_enabled}"
        )

        # Log capability decision
        if self.settings.worker.stem_splitting_enabled and self._gpu_available:
            logger.info("STEM SPLITTING: Enabled (local GPU processing)")
        else:
            logger.info("STEM SPLITTING: Disabled (RunPod fallback)")

    def _detect_gpu(self) -> bool:
        """
        Detect if NVIDIA GPU is available.

        In containerized deployment (DEMUCS_DIRECT_MODE=true):
            Uses PyTorch's torch.cuda.is_available() for GPU detection.

        In host deployment (DEMUCS_DIRECT_MODE=false):
            Tests GPU via Docker with nvidia-smi.

        Returns:
            True if GPU is available and working, False otherwise
        """
        # Check if we're in containerized mode (Demucs installed directly)
        if os.environ.get("DEMUCS_DIRECT_MODE", "true").lower() == "true":
            return self._detect_gpu_pytorch()
        else:
            return self._detect_gpu_docker()

    def _detect_gpu_pytorch(self) -> bool:
        """Detect GPU via PyTorch (for containerized deployment)."""
        try:
            import torch

            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                logger.info(f"GPU detection: PyTorch found CUDA device: {device_name}")
                return True
            logger.warning("GPU detection: PyTorch reports no CUDA available")
            return False
        except ImportError:
            logger.warning("GPU detection: PyTorch not installed")
            return False
        except Exception as e:
            logger.warning(f"GPU detection (PyTorch) failed: {e}")
            return False

    def _detect_gpu_docker(self) -> bool:
        """Detect GPU via Docker nvidia-smi (for host deployment)."""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--gpus",
                    "all",
                    "nvidia/cuda:11.8.0-base-ubuntu22.04",
                    "nvidia-smi",
                ],
                capture_output=True,
                timeout=10,
                text=True,
            )
            if result.returncode == 0:
                logger.info("GPU detection: nvidia-smi succeeded via Docker")
                return True
            logger.warning(
                f"GPU detection: nvidia-smi failed (exit {result.returncode})"
            )
            return False
        except subprocess.TimeoutExpired:
            logger.warning("GPU detection: nvidia-smi timed out after 10s")
            return False
        except FileNotFoundError:
            logger.warning("GPU detection: Docker command not found")
            return False
        except Exception as e:
            logger.warning(f"GPU detection (Docker) failed: {e}")
            return False

    def _should_process_locally(self) -> bool:
        """
        Determine if job should be processed locally.

        CRITICAL - Per INVARIANT: If stem_splitting_enabled=true AND GPU available,
        local processing MUST be used and RunPod MUST NOT be invoked.

        This is WORKER-level control, not per-job.

        Returns:
            True if local processing should be used, False for RunPod fallback
        """
        if not self.settings.worker.stem_splitting_enabled:
            logger.info("Stem splitting disabled by worker config → RunPod path")
            return False

        if not self._gpu_available:
            logger.warning(
                "Stem splitting enabled but GPU not available → RunPod fallback"
            )
            return False

        logger.info("Stem splitting enabled + GPU available → LOCAL PATH (free)")
        return True

    def _handle_shutdown(self, signum: int, _frame: FrameType | None) -> None:
        """Handle shutdown signals for graceful termination."""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown")
        self._shutdown_requested = True
        self._shutdown_event.set()  # Wake all waiting threads immediately

    # -------------------------------------------------------------------------
    # Heartbeat Management
    # -------------------------------------------------------------------------
    def _heartbeat_loop(self) -> None:
        """Background thread for periodic heartbeats."""
        logger.info("Heartbeat thread started")
        while not self._shutdown_requested:
            self._backend.send_heartbeat()
            # Wait efficiently with instant shutdown response
            self._shutdown_event.wait(timeout=self.settings.worker.heartbeat_interval)
        logger.info("Heartbeat thread stopped")

    def start_heartbeat(self) -> None:
        """Start background heartbeat thread."""
        if self._heartbeat_thread is None or not self._heartbeat_thread.is_alive():
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                daemon=True,
                name="heartbeat",
            )
            self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        """Stop background heartbeat thread."""
        self._shutdown_requested = True
        self._shutdown_event.set()  # Wake the heartbeat thread immediately
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=5)

    # -------------------------------------------------------------------------
    # Lease Renewal Management
    # -------------------------------------------------------------------------
    def _lease_renewal_loop(self) -> None:
        """Background thread for job lease renewal."""
        job_id = self._lease_job_id
        stop_event = self._lease_stop_event
        logger.info(f"Lease renewal started for job {job_id}")

        while self._lease_job_id == job_id and not self._shutdown_requested:
            # Wait efficiently with instant response to stop or shutdown
            if stop_event:
                stop_event.wait(timeout=self.settings.worker.lease_renewal_interval)

            if self._lease_job_id != job_id or self._shutdown_requested:
                break

            # Renew lease
            if job_id:
                self._backend.renew_lease(job_id)

        logger.info(f"Lease renewal stopped for job {job_id}")

    def start_lease_renewal(self, job_id: str) -> None:
        """Start background lease renewal for a job."""
        self.stop_lease_renewal()
        self._lease_job_id = job_id
        self._lease_stop_event = threading.Event()
        self._lease_thread = threading.Thread(
            target=self._lease_renewal_loop,
            daemon=True,
            name=f"lease-{job_id[:8]}",
        )
        self._lease_thread.start()

    def stop_lease_renewal(self) -> None:
        """Stop background lease renewal."""
        if self._lease_thread and self._lease_thread.is_alive():
            self._lease_job_id = None
            if self._lease_stop_event:
                self._lease_stop_event.set()  # Wake the lease thread immediately
            self._lease_thread.join(timeout=5)
        self._lease_stop_event = None

    # -------------------------------------------------------------------------
    # Disk Space Check
    # -------------------------------------------------------------------------
    def check_disk_space(self) -> bool:
        """Check if sufficient disk space is available."""
        try:
            stat = os.statvfs(self.settings.worker.download_dir)
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            required = self.settings.worker.required_disk_space_gb

            if free_gb < required:
                logger.warning(f"Insufficient disk space: {free_gb:.2f} GB (need {required} GB)")
                return False

            logger.debug(f"Disk space OK: {free_gb:.2f} GB available")
            return True
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            return False

    # -------------------------------------------------------------------------
    # Job Processing
    # -------------------------------------------------------------------------
    def process_job(self, job: JobClaim, dry_run: bool = False) -> JobResult:
        """
        Process a single job: download -> DECISION -> local processing or RunPod.

        CRITICAL DECISION POINT: After download, check if local processing enabled.
        - If stem_splitting_enabled + GPU available -> process_job_local() (FREE)
        - Otherwise -> upload to S3 and trigger RunPod (PAID)

        Args:
            job: Job to process
            dry_run: If True, skip actual download/upload

        Returns:
            JobResult with success status and metadata
        """
        job_id = job.job_id
        self._current_job_id = job_id
        self._backend.update_health(status="active", current_job_id=job_id)

        logger.info(f"Processing job {job_id}: {job.source_url}")

        # Create job-specific directory
        job_dir = self.settings.worker.download_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        video_path = job_dir / "source.mp4"
        metadata_path = job_dir / "metadata.json"

        try:
            # Step 1: Update status to downloading
            self._backend.update_job(job_id, "downloading")

            if dry_run:
                logger.info(f"[DRY RUN] Would download: {job.source_url}")
                return JobResult(job_id=job_id, success=True)

            # Step 2: Download YouTube video with metadata
            download_result = self._yt_dlp.download(
                url=job.source_url,
                output_path=video_path,
                extract_metadata=True,
            )

            if not download_result.success:
                error = download_result.error or "YouTube download failed"
                self._backend.update_job(job_id, "failed", error=error)
                return JobResult(job_id=job_id, success=False, error=error)

            # Step 3: Save metadata.json
            if download_result.metadata:
                metadata_path.write_text(download_result.metadata.to_json())
                logger.info(f"Saved metadata: {metadata_path}")

            # DECISION: Local vs RunPod path (CRITICAL INVARIANT enforcement)
            if self._should_process_locally():
                # HOME GPU PATH (FREE) - default when GPU available
                logger.info(
                    f"Processing job {job_id} locally (free) - INVARIANT enforced"
                )
                return self.process_job_local(job, video_path, job_dir)

            # RUNPOD PATH (PAID) - fallback when GPU not available or disabled
            logger.info(f"Processing job {job_id} via RunPod (paid)")

            # Step 4: Upload video to S3
            s3_video_key = f"karaoke/in/{job_id}/source.mp4"

            if self._s3_circuit_breaker.is_open():
                error = f"S3 circuit breaker open: {self._s3_circuit_breaker.get_status()}"
                self._backend.update_job(job_id, "failed", error=error)
                return JobResult(job_id=job_id, success=False, error=error)

            def upload_video() -> bool:
                result = self._s3_uploader.upload(video_path, s3_video_key, "video/mp4")
                return result.success

            try:
                video_uploaded = self._s3_circuit_breaker.call(upload_video)
            except Exception as e:
                error = f"S3 video upload failed: {e}"
                self._backend.update_job(job_id, "failed", error=error)
                return JobResult(job_id=job_id, success=False, error=error)

            if not video_uploaded:
                error = "S3 video upload failed"
                self._backend.update_job(job_id, "failed", error=error)
                return JobResult(job_id=job_id, success=False, error=error)

            # Step 5: Upload metadata.json to S3
            if metadata_path.exists():
                s3_metadata_key = f"karaoke/in/{job_id}/metadata.json"
                try:
                    metadata_result = self._s3_uploader.upload(
                        metadata_path, s3_metadata_key, "application/json"
                    )
                    if metadata_result.success:
                        logger.info(f"Uploaded metadata: {s3_metadata_key}")
                    else:
                        logger.warning(f"Metadata upload failed: {metadata_result.error}")
                except Exception as e:
                    logger.warning(f"Metadata upload error: {e}")

            # Step 6: Update status to uploaded_source (triggers Runpod)
            if not self._backend.update_job(job_id, "uploaded_source", s3_key=s3_video_key):
                logger.error("Failed to update job status to uploaded_source")
                return JobResult(
                    job_id=job_id,
                    success=False,
                    error="Failed to update job status",
                )

            logger.info(f"Job {job_id} completed successfully")
            self._backend.update_health(increment_jobs=True)

            return JobResult(
                job_id=job_id,
                success=True,
                s3_key=s3_video_key,
                download_mb=download_result.file_size_mb,
            )

        except Exception as e:
            logger.exception(f"Error processing job {job_id}")
            self._backend.update_job(job_id, "failed", error=str(e))
            self._backend.update_health(increment_errors=True)
            return JobResult(job_id=job_id, success=False, error=str(e))

        finally:
            # Reset health status
            self._current_job_id = None
            self._backend.update_health(status="idle", current_job_id=None)

            # Cleanup local files
            self._cleanup_job_dir(job_dir)

    def _cleanup_job_dir(self, job_dir: Path) -> None:
        """Clean up local job directory."""
        try:
            if job_dir.exists():
                shutil.rmtree(job_dir)
                logger.info(f"Cleaned up: {job_dir}")
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")

    def process_job_local(
        self, job: JobClaim, source_mp4: Path, job_dir: Path
    ) -> JobResult:
        """
        Process stems locally using Docker + Demucs + GPU (FREE).

        Steps:
        1. Update status to processing_local
        2. Extract audio.wav from source.mp4
        3. Extract video-only track
        4. Run Demucs via Docker (6-stem separation)
        5. Upload WAV stems + video to AWS S3 staging (karaoke/out/{job_id}/)
        6. Update status to uploaded_outputs (triggers publish workflow)

        On failure: Fallback to RunPod path by setting status to uploaded_source.

        Args:
            job: Job claim with metadata
            source_mp4: Path to downloaded source video
            job_dir: Working directory for job

        Returns:
            JobResult with success status
        """
        job_id = job.job_id

        try:
            # Step 1: Update status to processing_local
            logger.info(f"Processing job {job_id} locally with Demucs")
            self._backend.update_job(job_id, "processing_local")

            # Step 2: Extract audio + video
            audio_wav = job_dir / "audio.wav"
            video_only = job_dir / "video.mp4"
            demucs_out = job_dir / "demucs_output"

            logger.info("Extracting audio from video")
            if not demucs.extract_audio(source_mp4, audio_wav):
                raise RuntimeError("Audio extraction failed")

            logger.info("Extracting video-only track")
            if not demucs.extract_video_only(source_mp4, video_only):
                raise RuntimeError("Video-only extraction failed")

            # Get duration for manifest
            duration = demucs.get_video_duration(source_mp4)
            logger.info(f"Video duration: {duration:.2f} seconds")

            # Step 3: Run Demucs stem separation
            logger.info("Running Demucs stem separation (this may take 10-30 minutes)")
            stem_wavs = demucs.run_demucs_docker(
                audio_wav,
                demucs_out,
                model=self.settings.worker.demucs_model,
                docker_image=self.settings.worker.demucs_docker_image,
            )

            # Step 4: Upload outputs to S3
            logger.info(f"Uploading {len(stem_wavs)} stems + video to S3")
            output_prefix = f"karaoke/out/{job_id}"

            # Upload video-only
            video_key = f"{output_prefix}/video.mp4"
            video_result = self._s3_uploader.upload(
                video_only, video_key, "video/mp4"
            )
            if not video_result.success:
                raise RuntimeError(f"Failed to upload video: {video_result.error}")

            # Upload stem WAV files
            for stem_name, stem_path in stem_wavs.items():
                stem_key = f"{output_prefix}/stems/{stem_name}.wav"
                stem_result = self._s3_uploader.upload(
                    stem_path, stem_key, "audio/wav"
                )
                if not stem_result.success:
                    raise RuntimeError(
                        f"Failed to upload {stem_name}: {stem_result.error}"
                    )
                logger.info(f"Uploaded stem: {stem_name}.wav")

            # Step 5: Create and upload manifest
            manifest = {
                "job_id": job_id,
                "source_url": job.source_url,
                "title": job.title or "Unknown",
                "artist": job.raw_data.get("artist", "Unknown"),
                "duration_seconds": duration,
                "model": self.settings.worker.demucs_model,
                "worker_id": self.settings.worker.worker_id,
                "stem_count": len(stem_wavs),
                "stems": {
                    stem: {"filename": f"stems/{stem}.wav"}
                    for stem in stem_wavs.keys()
                },
            }

            import json

            manifest_path = job_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))

            manifest_key = f"{output_prefix}/manifest.json"
            manifest_result = self._s3_uploader.upload(
                manifest_path, manifest_key, "application/json"
            )
            if not manifest_result.success:
                logger.warning(f"Manifest upload failed: {manifest_result.error}")

            # Step 6: Update status to uploaded_outputs (triggers publish workflow)
            self._backend.update_job(job_id, "uploaded_outputs")

            logger.info(
                f"Local processing complete: {len(stem_wavs)} stems uploaded"
            )
            self._backend.update_health(increment_jobs=True)

            return JobResult(job_id=job_id, success=True, s3_key=video_key)

        except Exception as e:
            # Fallback to RunPod on any local processing failure
            logger.warning(
                f"Local processing failed for {job_id}: {e} - falling back to RunPod"
            )
            logger.exception("Local processing exception details:")

            # Upload source video to S3 for RunPod to process
            try:
                s3_video_key = f"karaoke/in/{job_id}/source.mp4"
                upload_result = self._s3_uploader.upload(
                    source_mp4, s3_video_key, "video/mp4"
                )
                if upload_result.success:
                    self._backend.update_job(job_id, "uploaded_source", s3_key=s3_video_key)
                    logger.info(f"Fallback: uploaded to {s3_video_key}, RunPod will process")
                    return JobResult(
                        job_id=job_id,
                        success=True,
                        s3_key=s3_video_key,
                    )
                else:
                    raise RuntimeError(f"Fallback upload failed: {upload_result.error}")
            except Exception as fallback_error:
                # Complete failure - mark job as failed
                error_msg = f"Local processing failed AND fallback to RunPod failed: {fallback_error}"
                logger.error(error_msg)
                self._backend.update_job(job_id, "failed", error=error_msg)
                return JobResult(job_id=job_id, success=False, error=error_msg)

    def process_job_with_retry(self, job: JobClaim, dry_run: bool = False) -> JobResult:
        """
        Process job with exponential backoff retry logic.

        Args:
            job: Job to process
            dry_run: If True, skip actual operations

        Returns:
            JobResult from final attempt
        """
        job_id = job.job_id

        try:
            # Start lease renewal
            self.start_lease_renewal(job_id)

            for attempt in range(1, self.settings.worker.max_job_retries + 1):
                # Check disk space
                if not self.check_disk_space():
                    error = "Insufficient disk space"
                    self._backend.update_job(job_id, "failed", error=error)
                    return JobResult(job_id=job_id, success=False, error=error)

                # Process job
                result = self.process_job(job, dry_run)

                if result.success:
                    logger.info(f"Job {job_id} succeeded on attempt {attempt}")
                    return result

                # Don't retry on shutdown
                if self._shutdown_requested:
                    logger.info(f"Shutdown requested, not retrying job {job_id}")
                    return result

                # Calculate backoff
                if attempt < self.settings.worker.max_job_retries:
                    backoff = self.settings.worker.retry_backoff_base * (2 ** (attempt - 1))
                    logger.warning(
                        f"Job {job_id} failed attempt {attempt}, retrying in {backoff}s"
                    )

                    # Wait with instant shutdown response
                    if self._shutdown_event.wait(timeout=backoff):
                        # Event was set (shutdown requested)
                        return result

            # All retries exhausted
            error = f"Failed after {self.settings.worker.max_job_retries} attempts"
            self._backend.update_job(job_id, "failed", error=error)
            return JobResult(job_id=job_id, success=False, error=error)

        finally:
            self.stop_lease_renewal()

    # -------------------------------------------------------------------------
    # Main Run Methods
    # -------------------------------------------------------------------------
    def run_once(self, dry_run: bool = False) -> JobResult | None:
        """
        Claim and process a single job.

        Args:
            dry_run: If True, skip actual operations

        Returns:
            JobResult if a job was processed, None if no jobs available
        """
        job = self._backend.claim_job()
        if not job:
            logger.info("No jobs available")
            return None

        return self.process_job_with_retry(job, dry_run)

    def run_loop(self, dry_run: bool = False) -> None:
        """
        Main worker loop - continuously claim and process jobs.

        Args:
            dry_run: If True, skip actual operations
        """
        logger.info("Starting Karaoke Agent worker loop")
        logger.info(f"Poll interval: {self.settings.worker.poll_interval}s")

        # Start heartbeat
        self.start_heartbeat()
        self._backend.send_heartbeat()

        consecutive_errors = 0
        max_consecutive_errors = 50

        try:
            while not self._shutdown_requested:
                try:
                    # Claim job
                    job = self._backend.claim_job()

                    if job:
                        result = self.process_job_with_retry(job, dry_run)
                        if result.success:
                            consecutive_errors = 0
                        else:
                            consecutive_errors += 1
                    else:
                        consecutive_errors = 0
                        logger.debug("No jobs available, waiting...")

                    # Check for too many errors
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Too many consecutive errors ({consecutive_errors})")
                        self._backend.update_health(status="error")
                        self._backend.send_heartbeat()
                        sys.exit(1)

                except KeyboardInterrupt:
                    logger.info("Keyboard interrupt, shutting down")
                    break
                except Exception as e:
                    consecutive_errors += 1
                    logger.exception(f"Unexpected error in worker loop: {e}")

                # Wait before next poll (with instant shutdown response)
                self._shutdown_event.wait(timeout=self.settings.worker.poll_interval)

        finally:
            # Cleanup
            self._backend.update_health(status="offline")
            self._backend.send_heartbeat()
            self.stop_heartbeat()
            self._backend.close()

    def shutdown(self) -> None:
        """Initiate graceful shutdown."""
        logger.info("Shutdown requested")
        self._shutdown_requested = True
        self._shutdown_event.set()  # Wake all waiting threads immediately

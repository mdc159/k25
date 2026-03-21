"""
Demucs stem separation module for local GPU processing.

Provides audio/video extraction and Demucs-based stem separation.
Supports two modes:
- Direct: Run Demucs directly (when agent runs inside container with Demucs installed)
- Docker: Run Demucs via Docker container (legacy mode for host-based deployment)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Demucs htdemucs_6s model produces 6 stems
STEM_ORDER = ["vocals", "drums", "bass", "guitar", "piano", "other"]

# Check if we're running inside a container (Demucs available directly)
DEMUCS_DIRECT_MODE = os.environ.get("DEMUCS_DIRECT_MODE", "true").lower() == "true"


def extract_audio(video_path: Path, audio_path: Path) -> bool:
    """
    Extract audio from video to WAV format for Demucs.

    Args:
        video_path: Path to source video file
        audio_path: Path to output WAV file

    Returns:
        True if extraction succeeded, False otherwise
    """
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",  # No video
            "-acodec",
            "pcm_s16le",  # PCM 16-bit LE
            "-ar",
            "44100",  # 44.1kHz sample rate
            "-ac",
            "2",  # Stereo
            str(audio_path),
        ]
        logger.info(f"Extracting audio: {video_path.name} -> {audio_path.name}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            logger.error(f"FFmpeg audio extraction failed: {result.stderr}")
            return False
        return audio_path.exists()
    except subprocess.TimeoutExpired:
        logger.error("Audio extraction timed out after 5 minutes")
        return False
    except Exception as e:
        logger.error(f"Audio extraction error: {e}")
        return False


def extract_video_only(source_path: Path, output_path: Path) -> bool:
    """
    Extract video track without audio (for web mixer).

    Args:
        source_path: Path to source video file
        output_path: Path to output video-only file

    Returns:
        True if extraction succeeded, False otherwise
    """
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-an",  # No audio
            "-c:v",
            "copy",  # Copy video codec (no re-encoding)
            str(output_path),
        ]
        logger.info(f"Extracting video-only: {source_path.name} -> {output_path.name}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            logger.error(f"FFmpeg video extraction failed: {result.stderr}")
            return False
        return output_path.exists()
    except subprocess.TimeoutExpired:
        logger.error("Video extraction timed out after 5 minutes")
        return False
    except Exception as e:
        logger.error(f"Video extraction error: {e}")
        return False


def get_video_duration(video_path: Path) -> float:
    """
    Get video duration in seconds using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Duration in seconds, or 0.0 if unable to determine
    """
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0))
    except Exception as e:
        logger.warning(f"Could not get video duration: {e}")
    return 0.0


def run_demucs(
    audio_path: Path,
    output_dir: Path,
    model: str = "htdemucs_6s",
    docker_image: str = "mdc159/karaoke-demucs-worker-aws:latest",
) -> dict[str, Path]:
    """
    Run Demucs stem separation.

    Automatically selects mode based on DEMUCS_DIRECT_MODE environment variable:
    - Direct mode (default): Runs Demucs directly (for containerized deployment)
    - Docker mode: Runs Demucs via Docker container (for host-based deployment)

    Args:
        audio_path: Path to input audio WAV file
        output_dir: Directory for Demucs output
        model: Demucs model name (default: htdemucs_6s)
        docker_image: Docker image containing Demucs (only used in Docker mode)

    Returns:
        Dict mapping stem name to WAV path

    Raises:
        RuntimeError: If Demucs fails or stems not found
    """
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    if DEMUCS_DIRECT_MODE:
        # Direct mode: Run Demucs directly (containerized deployment)
        cmd = [
            "python3",
            "-m",
            "demucs",
            "-n",
            model,
            "--segment",
            "7",
            "--overlap",
            "0.25",
            "--shifts",
            "0",
            "--clip-mode",
            "rescale",
            "--int24",
            "--out",
            str(output_dir),
            str(audio_path),
        ]
        logger.info(f"Running Demucs (direct): model={model}, audio={audio_path.name}")
    else:
        # Docker mode: Run Demucs via Docker container
        cmd = [
            "docker",
            "run",
            "--rm",
            "--gpus",
            "all",
            "-v",
            f"{audio_path.parent}:/input:ro",
            "-v",
            f"{output_dir}:/output",
            docker_image,
            "python3",
            "-m",
            "demucs",
            "-n",
            model,
            "--segment",
            "7",
            "--overlap",
            "0.25",
            "--shifts",
            "0",
            "--clip-mode",
            "rescale",
            "--int24",
            "--out",
            "/output",
            f"/input/{audio_path.name}",
        ]
        logger.info(f"Running Demucs (docker): model={model}, image={docker_image}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout for long songs
        )

        if result.returncode != 0:
            logger.error(f"Demucs failed: {result.stderr}")
            raise RuntimeError(f"Demucs processing failed: {result.stderr[:500]}")

    except subprocess.TimeoutExpired:
        raise RuntimeError("Demucs processing timed out after 1 hour")

    # Locate demucs output folder (demucs creates nested directories)
    # Pattern: output_dir/model_name/track_name/*.wav
    track_dir = None
    for p in output_dir.rglob("audio"):
        if p.is_dir() and list(p.glob("*.wav")):
            track_dir = p
            break

    if not track_dir:
        # Try alternate pattern (model/trackname/)
        for p in output_dir.rglob("*.wav"):
            track_dir = p.parent
            break

    if not track_dir:
        raise RuntimeError(
            "Could not find Demucs output folder containing stem WAV files"
        )

    # Verify all stems exist
    stem_wavs = {}
    for stem in STEM_ORDER:
        wav_path = track_dir / f"{stem}.wav"
        if not wav_path.exists():
            raise RuntimeError(f"Missing stem: {stem}.wav in {track_dir}")
        file_size_mb = wav_path.stat().st_size / (1024 * 1024)
        logger.info(f"Found stem: {stem}.wav ({file_size_mb:.1f} MB)")
        stem_wavs[stem] = wav_path

    return stem_wavs


# Backwards compatibility alias
run_demucs_docker = run_demucs

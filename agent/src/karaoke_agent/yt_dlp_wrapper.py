"""
yt-dlp wrapper module for Karaoke Agent.

Provides typed interface for YouTube video downloads with:
- Video download in best quality MP4
- Metadata extraction using yt-dlp -J
- Progress reporting
- Cookie support for authenticated downloads
- Configurable yt-dlp binary path
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from karaoke_agent.config import WorkerConfig

logger = logging.getLogger(__name__)


# Type alias for progress callback
# Called with (status: str, progress_pct: float, speed: str, eta: str)
ProgressCallback = Callable[[str, float, str, str], None]


@dataclass
class VideoMetadata:
    """Extracted video metadata from yt-dlp."""

    video_id: str
    title: str
    description: str | None
    duration: int | None  # Duration in seconds
    uploader: str | None
    uploader_id: str | None
    channel: str | None
    channel_id: str | None
    upload_date: str | None  # YYYYMMDD format
    view_count: int | None
    like_count: int | None
    thumbnail: str | None
    webpage_url: str
    extractor: str
    raw_info: dict[str, Any] = field(repr=False)

    @classmethod
    def from_yt_dlp_info(cls, info: dict[str, Any]) -> VideoMetadata:
        """Create VideoMetadata from yt-dlp JSON output."""
        return cls(
            video_id=info.get("id", "unknown"),
            title=info.get("title", "Unknown Title"),
            description=info.get("description"),
            duration=info.get("duration"),
            uploader=info.get("uploader"),
            uploader_id=info.get("uploader_id"),
            channel=info.get("channel"),
            channel_id=info.get("channel_id"),
            upload_date=info.get("upload_date"),
            view_count=info.get("view_count"),
            like_count=info.get("like_count"),
            thumbnail=info.get("thumbnail"),
            webpage_url=info.get("webpage_url", ""),
            extractor=info.get("extractor", "unknown"),
            raw_info=info,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "description": self.description,
            "duration": self.duration,
            "uploader": self.uploader,
            "uploader_id": self.uploader_id,
            "channel": self.channel,
            "channel_id": self.channel_id,
            "upload_date": self.upload_date,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "thumbnail": self.thumbnail,
            "webpage_url": self.webpage_url,
            "extractor": self.extractor,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class DownloadResult:
    """Result of a video download operation."""

    success: bool
    video_path: Path | None = None
    metadata: VideoMetadata | None = None
    file_size_mb: float = 0.0
    error: str | None = None

    @property
    def metadata_json(self) -> str | None:
        """Return metadata as JSON string."""
        if self.metadata:
            return self.metadata.to_json()
        return None


@dataclass
class YtDlpConfig:
    """Configuration for yt-dlp wrapper."""

    # yt-dlp binary path
    binary_path: str = "yt-dlp"

    # Download settings
    format_spec: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    merge_format: str = "mp4"
    retries: int = 3
    fragment_retries: int = 3
    timeout_seconds: int = 1800  # 30 minutes

    # Cookie file for authenticated downloads
    cookie_file: Path | None = None

    # User agent (helps avoid rate limiting)
    user_agent: str | None = None

    # Network settings
    socket_timeout: int = 30

    # Output settings
    no_mtime: bool = True  # Don't set file modification time
    no_playlist: bool = True  # Only download single video


class YtDlpWrapper:
    """
    Wrapper for yt-dlp command-line tool.

    Provides typed interface for:
    - Video downloads
    - Metadata extraction
    - Progress reporting
    """

    def __init__(self, config: YtDlpConfig | None = None) -> None:
        """
        Initialize yt-dlp wrapper.

        Args:
            config: Optional configuration (uses defaults if not provided)
        """
        self.config = config or YtDlpConfig()
        self._validate_binary()

    def _validate_binary(self) -> None:
        """Verify yt-dlp binary exists and is executable."""
        try:
            result = subprocess.run(
                [self.config.binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.debug(f"yt-dlp version: {version}")
            else:
                logger.warning(f"yt-dlp version check failed: {result.stderr}")
        except FileNotFoundError:
            logger.warning(f"yt-dlp binary not found at: {self.config.binary_path}")
        except subprocess.TimeoutExpired:
            logger.warning("yt-dlp version check timed out")

    def _build_base_args(self) -> list[str]:
        """Build base command-line arguments."""
        args = [self.config.binary_path]

        if self.config.no_playlist:
            args.append("--no-playlist")

        if self.config.cookie_file and self.config.cookie_file.exists():
            args.extend(["--cookies", str(self.config.cookie_file)])

        if self.config.user_agent:
            args.extend(["--user-agent", self.config.user_agent])

        args.extend(["--socket-timeout", str(self.config.socket_timeout)])

        return args

    def _build_download_args(self, output_path: Path) -> list[str]:
        """Build download-specific command-line arguments."""
        args = self._build_base_args()

        args.extend(["-f", self.config.format_spec])
        args.extend(["--merge-output-format", self.config.merge_format])
        args.extend(["-o", str(output_path)])

        if self.config.no_mtime:
            args.append("--no-mtime")

        args.extend(["--retries", str(self.config.retries)])
        args.extend(["--fragment-retries", str(self.config.fragment_retries)])

        return args

    def get_metadata(self, url: str) -> VideoMetadata | None:
        """
        Extract video metadata without downloading.

        Args:
            url: YouTube video URL

        Returns:
            VideoMetadata if successful, None otherwise
        """
        args = self._build_base_args()
        args.extend(["-J", "--no-download", url])

        logger.info(f"Extracting metadata for: {url}")

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=60,  # Metadata extraction should be quick
            )

            if result.returncode != 0:
                logger.error(f"yt-dlp metadata extraction failed: {result.stderr}")
                return None

            info = json.loads(result.stdout)
            metadata = VideoMetadata.from_yt_dlp_info(info)
            logger.info(f"Extracted metadata: {metadata.title} ({metadata.video_id})")
            return metadata

        except subprocess.TimeoutExpired:
            logger.error("Metadata extraction timed out")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse yt-dlp JSON output: {e}")
            return None
        except Exception as e:
            logger.error(f"Metadata extraction error: {e}")
            return None

    def download(
        self,
        url: str,
        output_path: Path,
        extract_metadata: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """
        Download video from YouTube.

        Args:
            url: YouTube video URL
            output_path: Path for downloaded video file
            extract_metadata: Whether to extract metadata before download
            progress_callback: Optional callback for progress updates

        Returns:
            DownloadResult with success status, path, and metadata
        """
        metadata: VideoMetadata | None = None

        # Extract metadata first if requested
        if extract_metadata:
            metadata = self.get_metadata(url)
            if metadata:
                logger.info(f"Video: {metadata.title} (duration: {metadata.duration}s)")

        # Build download command
        args = self._build_download_args(output_path)

        # Add progress output for callback support
        if progress_callback:
            args.extend(["--newline", "--progress"])

        args.append(url)

        logger.info(f"Downloading: {url}")
        logger.debug(f"Command: {' '.join(args)}")

        try:
            if progress_callback:
                # Run with progress parsing
                return self._download_with_progress(
                    args, output_path, metadata, progress_callback
                )

            # Simple blocking download
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )

            if result.returncode != 0:
                logger.error(f"yt-dlp download failed: {result.stderr}")
                return DownloadResult(
                    success=False,
                    metadata=metadata,
                    error=f"yt-dlp failed: {result.stderr[:500]}",
                )

            if not output_path.exists():
                logger.error(f"Download completed but file not found: {output_path}")
                return DownloadResult(
                    success=False,
                    metadata=metadata,
                    error="Download completed but file not found",
                )

            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Downloaded: {output_path.name} ({file_size_mb:.1f} MB)")

            return DownloadResult(
                success=True,
                video_path=output_path,
                metadata=metadata,
                file_size_mb=file_size_mb,
            )

        except subprocess.TimeoutExpired:
            logger.error(f"Download timed out after {self.config.timeout_seconds} seconds")
            return DownloadResult(
                success=False,
                metadata=metadata,
                error=f"Download timed out after {self.config.timeout_seconds}s",
            )
        except Exception as e:
            logger.error(f"Download error: {e}")
            return DownloadResult(
                success=False,
                metadata=metadata,
                error=str(e),
            )

    def _download_with_progress(
        self,
        args: list[str],
        output_path: Path,
        metadata: VideoMetadata | None,
        progress_callback: ProgressCallback,
    ) -> DownloadResult:
        """
        Download with real-time progress parsing.

        Args:
            args: yt-dlp command arguments
            output_path: Output file path
            metadata: Pre-extracted metadata
            progress_callback: Progress callback function

        Returns:
            DownloadResult
        """
        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Parse progress output
            for line in iter(process.stdout.readline, ""):  # type: ignore[union-attr]
                line = line.strip()
                if not line:
                    continue

                # Parse yt-dlp progress line
                # Format: [download]  XX.X% of ~XXX.XXMIB at XXX.XXKIB/s ETA XX:XX
                if "[download]" in line and "%" in line:
                    try:
                        parts = line.split()
                        for _idx, part in enumerate(parts):
                            if "%" in part:
                                progress_pct = float(part.rstrip("%"))
                                speed = ""
                                eta = ""

                                # Find speed (contains "/s")
                                for p in parts:
                                    if "/s" in p.lower():
                                        speed = p
                                        break

                                # Find ETA (after "ETA")
                                if "ETA" in parts:
                                    eta_idx = parts.index("ETA")
                                    if eta_idx + 1 < len(parts):
                                        eta = parts[eta_idx + 1]

                                progress_callback("downloading", progress_pct, speed, eta)
                                break
                    except (ValueError, IndexError):
                        pass  # Skip unparseable lines

                elif "[Merger]" in line:
                    progress_callback("merging", 100.0, "", "")

            process.wait(timeout=self.config.timeout_seconds)

            if process.returncode != 0:
                return DownloadResult(
                    success=False,
                    metadata=metadata,
                    error="yt-dlp download failed",
                )

            if not output_path.exists():
                return DownloadResult(
                    success=False,
                    metadata=metadata,
                    error="Download completed but file not found",
                )

            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Downloaded: {output_path.name} ({file_size_mb:.1f} MB)")

            return DownloadResult(
                success=True,
                video_path=output_path,
                metadata=metadata,
                file_size_mb=file_size_mb,
            )

        except subprocess.TimeoutExpired:
            process.kill()  # type: ignore[union-attr]
            logger.error(f"Download timed out after {self.config.timeout_seconds}s")
            return DownloadResult(
                success=False,
                metadata=metadata,
                error=f"Download timed out after {self.config.timeout_seconds}s",
            )


def create_wrapper_from_config(worker_config: WorkerConfig) -> YtDlpWrapper:
    """
    Create YtDlpWrapper from karaoke-agent WorkerConfig.

    Args:
        worker_config: WorkerConfig from karaoke_agent.config

    Returns:
        Configured YtDlpWrapper instance
    """
    # Find yt-dlp binary dynamically via PATH
    import shutil
    binary_path = shutil.which("yt-dlp") or "yt-dlp"

    config = YtDlpConfig(
        binary_path=binary_path,
        retries=worker_config.max_retries,
        fragment_retries=worker_config.max_retries,
    )

    return YtDlpWrapper(config)

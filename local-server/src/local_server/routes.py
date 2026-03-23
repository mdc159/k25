"""API routes for local karaoke server."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .models import JobStatus, JobStatusEnum, LibraryResponse, TrackInfo
from .processing import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# In-memory job tracking
jobs: dict[str, JobStatus] = {}

# Simple lock: one pipeline at a time
_pipeline_lock = asyncio.Lock()

# Track background tasks for graceful shutdown
_tasks: set[asyncio.Task] = set()

# Data directory (set by main.py on startup)
DATA_DIR: Path = Path()


def set_data_dir(path: Path) -> None:
    global DATA_DIR
    DATA_DIR = path


def scan_library() -> list[TrackInfo]:
    """Scan data/ for completed tracks (those with stems.json)."""
    tracks = []
    if not DATA_DIR.exists():
        return tracks

    for job_dir in sorted(DATA_DIR.iterdir()):
        if not job_dir.is_dir():
            continue
        manifest = job_dir / "stems.json"
        if not manifest.exists():
            continue

        try:
            data = json.loads(manifest.read_text())
        except Exception:
            continue

        tracks.append(TrackInfo(
            id=job_dir.name,
            title=data.get("title", job_dir.name),
            artist=data.get("artist", ""),
            slug=job_dir.name,
            duration=data.get("duration", 0),
            publicUrl=f"/api/tracks/{job_dir.name}",
        ))

    return tracks


@router.post("/upload")
async def upload_file(file: UploadFile) -> dict:
    """Accept an MP4 upload and start the processing pipeline."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    if file.content_type and not file.content_type.startswith("video/"):
        raise HTTPException(400, "Only video files are accepted")

    job_id = uuid.uuid4().hex[:12]
    job_dir = DATA_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file — stream to disk to avoid buffering large files in RAM
    source_path = job_dir / "source.mp4"

    def _save_upload(src, dst: Path) -> None:
        with open(dst, "wb") as f:
            shutil.copyfileobj(src, f)

    await asyncio.to_thread(_save_upload, file.file, source_path)

    # Derive title from original filename
    original_title = Path(file.filename).stem

    # Initialize job status
    jobs[job_id] = JobStatus(jobId=job_id, status=JobStatusEnum.pending)

    # Start pipeline in background
    task = asyncio.create_task(_run_pipeline(job_id, job_dir, source_path, original_title))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

    return {"jobId": job_id}


async def _run_pipeline(job_id: str, job_dir: Path, source_path: Path, title: str | None = None) -> None:
    """Run the pipeline in background, updating job status."""
    async with _pipeline_lock:
        def on_status(status: str, message: str) -> None:
            jobs[job_id] = JobStatus(
                jobId=job_id,
                status=JobStatusEnum(status),
                message=message,
            )

        try:
            await asyncio.to_thread(run_pipeline, job_dir, source_path, on_status, title)
            jobs[job_id] = JobStatus(jobId=job_id, status=JobStatusEnum.ready)
        except Exception as e:
            logger.exception("Pipeline failed for job %s", job_id)
            jobs[job_id] = JobStatus(
                jobId=job_id,
                status=JobStatusEnum.failed,
                error=str(e),
            )


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> JobStatus:
    """Get processing status for a job."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@router.get("/library")
async def get_library() -> LibraryResponse:
    """List all completed tracks."""
    tracks = scan_library()
    return LibraryResponse(tracks=tracks, total=len(tracks))


@router.get("/tracks/{job_id}/download")
async def download_track(job_id: str) -> FileResponse:
    """Download the multi-track MP4."""
    mp4 = DATA_DIR / job_id / "multi-track.mp4"
    if not mp4.exists():
        raise HTTPException(404, "Multi-track file not found")
    return FileResponse(
        mp4,
        media_type="video/mp4",
        filename=f"{job_id}-multi-track.mp4",
    )


@router.get("/tracks/{job_id}/{path:path}")
async def serve_track_file(job_id: str, path: str) -> FileResponse:
    """Serve video, stems, or manifest files for a track."""
    file_path = (DATA_DIR / job_id / path).resolve()

    # Security: ensure path stays within job directory
    job_dir = (DATA_DIR / job_id).resolve()
    if not file_path.is_relative_to(job_dir):
        raise HTTPException(403, "Access denied")

    if not file_path.exists():
        raise HTTPException(404, f"File not found: {path}")

    # Determine media type
    suffix = file_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".wav": "audio/wav",
        ".json": "application/json",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(file_path, media_type=media_type)

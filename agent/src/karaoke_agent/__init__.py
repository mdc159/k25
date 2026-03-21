"""
Karaoke Agent - Home Linux Worker for YouTube Downloads

A production-grade worker that:
- Claims jobs from Supabase via n8n webhooks
- Downloads YouTube videos using yt-dlp (residential IP)
- Uploads to S3 using robust multipart upload with resumability
- Reports health via heartbeats to Supabase

This is a refactored, modular version of the original home-agent.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("karaoke-agent")
except PackageNotFoundError:
    __version__ = "2.0.0.dev0"

__all__ = ["__version__"]

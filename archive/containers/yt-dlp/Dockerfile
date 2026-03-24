# yt-dlp - YouTube Video Downloader Container
# Used for downloading videos and extracting metadata

FROM python:3.11-slim

# Install system dependencies:
# - ffmpeg: for merging video+audio streams
# - curl, unzip: for installing deno
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Deno - required JavaScript runtime for yt-dlp YouTube extraction
# See: https://github.com/yt-dlp/yt-dlp/wiki/EJS
ENV DENO_INSTALL=/usr/local
RUN curl -fsSL https://deno.land/install.sh | sh -s -- --no-modify-path \
    && ln -sf /usr/local/bin/deno /usr/bin/deno

# Install latest yt-dlp (unpinned to get YouTube extractor fixes)
RUN pip install --no-cache-dir yt-dlp

WORKDIR /data

# Usage:
#   Metadata: docker exec yt-dlp yt-dlp -J --no-playlist "URL"
#   Download: docker exec yt-dlp yt-dlp -f "bestvideo+bestaudio/best" -o "/data/output.mp4" "URL"

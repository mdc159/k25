# Karaoke Agent Container
# Bundles: Python 3.11, yt-dlp, ffmpeg, PyTorch+CUDA, Demucs
#
# Build: docker build -t karaoke-agent .
# Run:   docker run --gpus all --env-file .env karaoke-agent

# CUDA 12.1 runtime with cuDNN (matches RunPod worker)
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

LABEL maintainer="Hostinger Team"
LABEL description="Karaoke Agent - YouTube download + Demucs stem separation"
LABEL version="2.0.0"

# Environment configuration
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    # Enable direct Demucs mode (not Docker-in-Docker)
    DEMUCS_DIRECT_MODE=true \
    # Default stem splitting enabled
    STEM_SPLITTING_ENABLED=true

# System dependencies: Python 3.11, ffmpeg, yt-dlp prerequisites
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    ffmpeg \
    git \
    ca-certificates \
    curl \
    # yt-dlp may need these for some extractors
    atomicparsley \
    && rm -rf /var/lib/apt/lists/* \
    # Make python3.11 the default
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /app

# Install PyTorch with CUDA 12.1 support
# This is large (~2GB) so we do it early for better layer caching
RUN pip3 install --upgrade pip \
    && pip3 install --index-url https://download.pytorch.org/whl/cu121 \
    torch torchaudio

# Install yt-dlp (latest version)
RUN pip3 install yt-dlp

# Install Demucs and audio dependencies
RUN pip3 install \
    demucs \
    soundfile \
    numpy'<2'

# Copy and install karaoke-agent package
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip3 install -e .

# Create spool directory for downloads
RUN mkdir -p /var/lib/karaoke-agent/spool \
    && chmod 755 /var/lib/karaoke-agent

# Non-root user for security (optional, commented out for GPU access)
# RUN useradd -m -s /bin/bash agent \
#     && chown -R agent:agent /app /var/lib/karaoke-agent
# USER agent

# Health check - verify GPU and dependencies
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import torch; assert torch.cuda.is_available(), 'No GPU'; import demucs; print('OK')"

# Default command: run agent in loop mode
ENTRYPOINT ["karaoke-agent"]
CMD ["--loop"]

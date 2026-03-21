# Demucs - Audio Source Separation Container
# CPU-only build for VPS without GPU
# Model: htdemucs_6s (6-stem separation)

FROM python:3.11-slim

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install demucs with pinned versions for reproducibility
# Using CPU-only torch to reduce image size
# Pin numpy<2 to avoid compatibility issues with demucs
RUN pip install --no-cache-dir \
    "numpy<2" \
    torch==2.1.2+cpu \
    torchaudio==2.1.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir demucs==4.0.1 soundfile

# Pre-download the htdemucs_6s model during build
# This makes container startup faster
RUN python -c "import demucs.pretrained; demucs.pretrained.get_model('htdemucs_6s')"

WORKDIR /data

# Usage: docker exec demucs python -m demucs -n htdemucs_6s --out /data/output /data/input.mp4

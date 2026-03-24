FROM python:3.11-slim

# Install system dependencies including Docker CLI for invoking GPU containers
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install yt-dlp
RUN uv tool install yt-dlp

# Create directories
RUN mkdir -p /app /data/spool/input /data/spool/output

# Copy application
WORKDIR /app
COPY home-agent/karaoke-agent.py .
COPY containers/karaoke/home-agent/requirements.txt .

# Install Python dependencies
RUN uv pip install --system -r requirements.txt

# Health check (heartbeat to Supabase)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)" || exit 1

# Run agent
CMD ["python", "karaoke-agent.py", "--loop"]

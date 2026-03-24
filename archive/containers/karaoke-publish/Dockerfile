# Karaoke publish utility - runs on demand
FROM python:3.12-slim

RUN pip install --no-cache-dir boto3 supabase httpx

WORKDIR /app
ENTRYPOINT ["tail", "-f", "/dev/null"]

"""
Configuration module for Karaoke Agent.

Uses Pydantic BaseSettings for type-safe configuration with:
- Environment variable support
- .env file loading
- Validation with clear error messages
- Sensible defaults for optional settings
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class S3Config(BaseSettings):
    """AWS S3 storage configuration."""

    model_config = SettingsConfigDict(
        env_prefix="AWS_",
        extra="ignore",
    )

    endpoint: str = Field(
        alias="AWS_S3_ENDPOINT",
        description="S3 endpoint URL",
    )
    bucket: str = Field(
        alias="AWS_S3_BUCKET",
        description="S3 bucket name",
    )
    access_key: str = Field(
        alias="AWS_ACCESS_KEY_ID",
        description="AWS access key ID",
    )
    secret_key: str = Field(
        alias="AWS_SECRET_ACCESS_KEY",
        description="AWS secret access key",
    )
    region: str = Field(
        default="us-east-1",
        alias="AWS_REGION",
        description="AWS region",
    )

    # Multipart upload settings
    part_size_mb: int = Field(
        default=50,
        ge=5,
        le=500,
        description="Multipart upload chunk size in MB (min 5MB for S3)",
    )
    max_concurrency: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Number of concurrent upload threads",
    )
    max_retries: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum retries per upload operation",
    )

    @property
    def part_size_bytes(self) -> int:
        """Return part size in bytes."""
        return self.part_size_mb * 1024 * 1024


class SupabaseConfig(BaseSettings):
    """Supabase database configuration."""

    model_config = SettingsConfigDict(
        env_prefix="SUPABASE_",
        extra="ignore",
    )

    url: str = Field(
        alias="SUPABASE_URL",
        description="Supabase project URL",
    )
    service_key: str = Field(
        alias="SUPABASE_SERVICE_ROLE_KEY",
        description="Supabase service role key for server-side operations",
    )


class APIConfig(BaseSettings):
    """VPS/n8n API configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    base_url: str = Field(
        alias="VPS_API_BASE",
        description="Base URL for n8n webhook endpoints (e.g., https://n8n.example.com/webhook)",
    )
    worker_token: str = Field(
        alias="WORKER_TOKEN",
        description="Authentication token for worker API calls",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base URL doesn't have trailing slash."""
        return v.rstrip("/")


class WorkerConfig(BaseSettings):
    """Worker behavior configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    worker_id: str = Field(
        default_factory=lambda: f"home-agent-{os.getpid()}",
        alias="WORKER_ID",
        description="Unique worker identifier",
    )
    poll_interval: int = Field(
        default=30,
        ge=5,
        le=300,
        alias="POLL_INTERVAL_SECONDS",
        description="Seconds between job claim attempts",
    )
    heartbeat_interval: int = Field(
        default=60,
        ge=10,
        le=300,
        alias="HEARTBEAT_INTERVAL_SECONDS",
        description="Seconds between health heartbeats",
    )
    lease_renewal_interval: int = Field(
        default=300,
        ge=60,
        le=600,
        alias="LEASE_RENEWAL_INTERVAL_SECONDS",
        description="Seconds between lease renewals during job processing",
    )
    download_dir: Path = Field(
        default=Path("/var/lib/karaoke-agent/spool"),
        alias="DOWNLOAD_DIR",
        description="Directory for temporary downloads",
    )
    log_file: Path | None = Field(
        default=Path("/var/lib/karaoke-agent/karaoke-agent.log"),
        alias="LOG_FILE",
        description="Log file path (None for stdout only)",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        alias="MAX_RETRIES",
        description="Max retries for individual operations",
    )
    max_job_retries: int = Field(
        default=3,
        ge=1,
        le=5,
        alias="MAX_JOB_RETRIES",
        description="Max retries for entire job processing",
    )
    retry_backoff_base: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Base seconds for exponential backoff (60s, 120s, 240s)",
    )
    required_disk_space_gb: float = Field(
        default=5.0,
        ge=1.0,
        le=50.0,
        description="Minimum free disk space in GB before processing",
    )

    # Circuit breaker settings
    circuit_breaker_threshold: int = Field(
        default=5,
        ge=2,
        le=20,
        description="Number of failures before circuit breaker opens",
    )
    circuit_breaker_timeout: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Seconds before circuit breaker attempts recovery",
    )

    # Local stem splitting configuration (worker-level control)
    stem_splitting_enabled: bool = Field(
        default=True,
        alias="STEM_SPLITTING_ENABLED",
        description="Enable local GPU stem splitting (default: TRUE per requirements)",
    )
    demucs_model: str = Field(
        default="htdemucs_6s",
        alias="DEMUCS_MODEL",
        description="Demucs model for stem separation",
    )
    demucs_docker_image: str = Field(
        default="mdc159/karaoke-demucs-worker-aws:latest",
        alias="DEMUCS_IMAGE",
        description="Docker image for Demucs processing",
    )

    @field_validator("download_dir", mode="before")
    @classmethod
    def parse_path(cls, v: str | Path) -> Path:
        """Convert string to Path."""
        return Path(v) if isinstance(v, str) else v


class Settings(BaseSettings):
    """
    Main configuration class combining all sub-configurations.

    Load order (later overrides earlier):
    1. Default values
    2. .env file (if exists)
    3. Environment variables

    Usage:
        settings = Settings()
        # or with explicit env file
        settings = Settings(_env_file=".env")
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Sub-configurations
    s3: S3Config = Field(default_factory=S3Config)
    supabase: SupabaseConfig = Field(default_factory=SupabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)

    @model_validator(mode="after")
    def ensure_download_dir_exists(self) -> Settings:
        """Create download directory if it doesn't exist."""
        with contextlib.suppress(PermissionError):
            self.worker.download_dir.mkdir(parents=True, exist_ok=True)
        return self


def load_settings(env_file: str | Path | None = None) -> Settings:
    """
    Load and validate settings from environment.

    Args:
        env_file: Optional path to .env file

    Returns:
        Validated Settings instance

    Raises:
        ValidationError: If required settings are missing or invalid
    """
    if env_file:
        return Settings(_env_file=env_file)
    return Settings()


# Convenience function for quick access
def get_settings() -> Settings:
    """Get settings singleton (loads on first call)."""
    if not hasattr(get_settings, "_settings"):
        get_settings._settings = load_settings()
    return get_settings._settings

"""Tests for configuration module."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from karaoke_agent.config import (
    S3Config,
    WorkerConfig,
    load_settings,
)


class TestS3Config:
    """Test S3 configuration validation.

    Note: Pydantic BaseSettings uses aliases for env var mapping.
    These tests verify behavior via environment variables set by clean_env fixture.
    """

    def test_valid_config_from_env(self) -> None:
        """Valid S3 config loads from environment."""
        # Uses clean_env fixture's env vars
        config = S3Config()
        assert config.endpoint == "https://s3.test.com"
        assert config.bucket == "test-bucket"
        assert config.region == "us-east-1"  # Default

    def test_part_size_bytes_calculation(self) -> None:
        """Part size correctly calculates bytes."""
        config = S3Config()
        assert config.part_size_bytes == config.part_size_mb * 1024 * 1024

    def test_concurrency_bounds(self) -> None:
        """Max concurrency is within valid range."""
        config = S3Config()
        assert config.max_concurrency >= 1
        assert config.max_concurrency <= 16

    def test_max_retries_bounds(self) -> None:
        """Max retries is within valid range."""
        config = S3Config()
        assert config.max_retries >= 1
        assert config.max_retries <= 10


class TestWorkerConfig:
    """Test worker configuration validation."""

    def test_default_worker_id_includes_pid(self) -> None:
        """Default worker ID includes process ID."""
        config = WorkerConfig()
        assert "home-agent-" in config.worker_id
        assert str(os.getpid()) in config.worker_id

    def test_poll_interval_default(self) -> None:
        """Poll interval has valid default."""
        config = WorkerConfig()
        assert config.poll_interval >= 5
        assert config.poll_interval <= 300

    def test_download_dir_is_path(self) -> None:
        """Download dir is a Path object."""
        config = WorkerConfig()
        assert isinstance(config.download_dir, Path)

    def test_retry_bounds(self) -> None:
        """Retry settings are within bounds."""
        config = WorkerConfig()
        assert config.max_retries >= 1
        assert config.max_retries <= 10
        assert config.max_job_retries >= 1
        assert config.max_job_retries <= 5

    def test_heartbeat_interval_bounds(self) -> None:
        """Heartbeat interval is within bounds."""
        config = WorkerConfig()
        assert config.heartbeat_interval >= 10
        assert config.heartbeat_interval <= 300

    def test_circuit_breaker_settings(self) -> None:
        """Circuit breaker settings are valid."""
        config = WorkerConfig()
        assert config.circuit_breaker_threshold >= 2
        assert config.circuit_breaker_timeout >= 10


class TestSettingsFromEnv:
    """Test loading settings from environment variables."""

    def test_load_settings_from_env(self) -> None:
        """Settings loads from environment variables."""
        # clean_env fixture sets up test env vars
        settings = load_settings()

        assert settings.api.base_url == "https://test-api.example.com/webhook"
        assert settings.supabase.url == "https://test.supabase.co"
        assert settings.s3.bucket == "test-bucket"

    def test_missing_required_env_raises_error(self) -> None:
        """Missing required environment variables raise ValidationError."""
        # Remove all required env vars
        with patch.dict(os.environ, {}, clear=True), pytest.raises(ValidationError):
            load_settings()


class TestSettingsValidation:
    """Test settings validation behavior."""

    def test_settings_creates_download_dir(self, tmp_path: Path) -> None:
        """Settings creates download directory if it doesn't exist."""
        download_dir = tmp_path / "new_spool"
        assert not download_dir.exists()

        with patch.dict(os.environ, {"DOWNLOAD_DIR": str(download_dir)}):
            settings = load_settings()

        # Directory should be created by the model validator
        assert settings.worker.download_dir.exists()

    def test_base_url_strips_trailing_slash(self) -> None:
        """API base URL has trailing slash stripped."""
        with patch.dict(os.environ, {"VPS_API_BASE": "https://test.com/webhook/"}):
            settings = load_settings()
            assert settings.api.base_url == "https://test.com/webhook"


class TestConfigDefaults:
    """Test configuration defaults."""

    def test_s3_defaults(self) -> None:
        """S3 config has sensible defaults."""
        config = S3Config()
        assert config.part_size_mb == 50
        assert config.max_concurrency == 4
        assert config.max_retries == 5

    def test_worker_defaults(self) -> None:
        """Worker config has sensible defaults."""
        config = WorkerConfig()
        assert config.poll_interval == 30
        assert config.heartbeat_interval == 60
        assert config.max_retries == 3
        assert config.required_disk_space_gb == 5.0

    def test_circuit_breaker_defaults(self) -> None:
        """Circuit breaker settings have sensible defaults."""
        config = WorkerConfig()
        assert config.circuit_breaker_threshold == 5
        assert config.circuit_breaker_timeout == 60


class TestConfigIntegration:
    """Test complete settings integration."""

    def test_full_settings_loads(self) -> None:
        """Complete settings object loads successfully."""
        settings = load_settings()

        # Check all sub-configs exist
        assert settings.s3 is not None
        assert settings.supabase is not None
        assert settings.api is not None
        assert settings.worker is not None

        # Check some values
        assert settings.s3.endpoint
        assert settings.supabase.url
        assert settings.api.base_url
        assert settings.worker.worker_id

    def test_s3_config_part_size_property(self) -> None:
        """S3 config part_size_bytes property works."""
        settings = load_settings()
        assert settings.s3.part_size_bytes == settings.s3.part_size_mb * 1024 * 1024

"""
Pytest fixtures for karaoke-agent tests.

Provides:
- Mock S3 service using moto
- Test configuration
- Mock backend client
- Temporary directories
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from karaoke_agent.config import (
    APIConfig,
    S3Config,
    Settings,
    SupabaseConfig,
    WorkerConfig,
)
from karaoke_agent.s3_multipart import S3UploadConfig
from karaoke_agent.supabase_client import BackendClient, JobClaim

# =============================================================================
# Environment Setup
# =============================================================================


@pytest.fixture(autouse=True)
def clean_env() -> Generator[None, None, None]:
    """Clean environment variables before each test."""
    # Store original env
    original_env = os.environ.copy()

    # Set minimal test env vars
    test_env = {
        "VPS_API_BASE": "https://test-api.example.com/webhook",
        "WORKER_TOKEN": "test-token",
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
        "AWS_S3_ENDPOINT": "https://s3.test.com",
        "AWS_S3_BUCKET": "test-bucket",
        "AWS_ACCESS_KEY_ID": "test-access-key",
        "AWS_SECRET_ACCESS_KEY": "test-secret-key",
        "AWS_REGION": "us-east-1",
    }

    for key, value in test_env.items():
        os.environ[key] = value

    yield

    # Restore original env
    os.environ.clear()
    os.environ.update(original_env)


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def s3_config() -> S3Config:
    """Create test S3 configuration."""
    return S3Config(
        endpoint="https://s3.test.com",
        bucket="test-bucket",
        access_key="test-access-key",
        secret_key="test-secret-key",
        region="us-east-1",
        part_size_mb=5,  # Minimum for S3
        max_concurrency=2,
        max_retries=3,
    )


@pytest.fixture
def supabase_config() -> SupabaseConfig:
    """Create test Supabase configuration."""
    return SupabaseConfig(
        url="https://test.supabase.co",
        service_key="test-service-key",
    )


@pytest.fixture
def api_config() -> APIConfig:
    """Create test API configuration."""
    return APIConfig(
        base_url="https://test-api.example.com/webhook",
        worker_token="test-token",
    )


@pytest.fixture
def worker_config(tmp_path: Path) -> WorkerConfig:
    """Create test worker configuration."""
    return WorkerConfig(
        worker_id="test-worker",
        poll_interval=5,
        heartbeat_interval=10,
        lease_renewal_interval=30,
        download_dir=tmp_path / "spool",
        log_file=None,
        max_retries=2,
        max_job_retries=2,
        retry_backoff_base=1,  # Fast retries for tests
        required_disk_space_gb=0.1,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout=5,
    )


@pytest.fixture
def settings(
    s3_config: S3Config,
    supabase_config: SupabaseConfig,
    api_config: APIConfig,
    worker_config: WorkerConfig,
) -> Settings:
    """Create complete test settings."""
    # Create download dir
    worker_config.download_dir.mkdir(parents=True, exist_ok=True)

    settings = MagicMock(spec=Settings)
    settings.s3 = s3_config
    settings.supabase = supabase_config
    settings.api = api_config
    settings.worker = worker_config
    return settings


# =============================================================================
# S3 Fixtures (using moto)
# =============================================================================


@pytest.fixture
def mock_s3() -> Generator[None, None, None]:
    """Start mock S3 service."""
    with mock_aws():
        yield


@pytest.fixture
def s3_client(_mock_s3: None = None, s3_config: S3Config = None):  # noqa: ARG001
    """Create mock S3 client with test bucket."""
    # Note: moto doesn't work with custom endpoints, so use AWS defaults
    if s3_config is None:
        s3_config = S3Config(
            endpoint="https://s3.test.com",
            bucket="test-bucket",
            access_key="test-access-key",
            secret_key="test-secret-key",
        )
    client = boto3.client(
        "s3",
        region_name=s3_config.region,
        aws_access_key_id=s3_config.access_key,
        aws_secret_access_key=s3_config.secret_key,
    )

    # Create test bucket
    client.create_bucket(Bucket=s3_config.bucket)

    return client


@pytest.fixture
def s3_upload_config() -> S3UploadConfig:
    """Create S3 upload configuration for tests."""
    return S3UploadConfig(
        endpoint="http://localhost:5000",  # Will be mocked
        bucket="test-bucket",
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
        part_size_mb=5,
        max_retries=2,
        max_concurrency=2,
    )


# =============================================================================
# Backend Client Fixtures
# =============================================================================


@pytest.fixture
def mock_backend_client() -> MagicMock:
    """Create mock backend client."""
    client = MagicMock(spec=BackendClient)
    client.worker_id = "test-worker"

    # Default mock responses
    client.send_heartbeat.return_value = True
    client.update_job.return_value = True
    client.renew_lease.return_value = True
    client.claim_job.return_value = None

    return client


@pytest.fixture
def sample_job_claim() -> JobClaim:
    """Create sample job claim for testing."""
    return JobClaim(
        job_id="test-job-123",
        source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        video_id="dQw4w9WgXcQ",
        title="Test Video",
        raw_data={
            "jobId": "test-job-123",
            "sourceUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "videoId": "dQw4w9WgXcQ",
            "title": "Test Video",
        },
    )


# =============================================================================
# File Fixtures
# =============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_video_file(temp_dir: Path) -> Path:
    """Create sample video file for upload tests."""
    video_path = temp_dir / "test_video.mp4"
    # Create 6MB file (larger than minimum part size)
    with open(video_path, "wb") as f:
        f.write(b"0" * (6 * 1024 * 1024))
    return video_path


@pytest.fixture
def small_file(temp_dir: Path) -> Path:
    """Create small file for simple upload tests."""
    file_path = temp_dir / "small_file.txt"
    file_path.write_text("Hello, World!")
    return file_path


# =============================================================================
# Circuit Breaker Fixtures
# =============================================================================


@pytest.fixture
def circuit_breaker():
    """Create circuit breaker for testing."""
    from karaoke_agent.utils import CircuitBreaker

    return CircuitBreaker(
        failure_threshold=3,
        timeout_seconds=1,  # Fast timeout for tests
        name="test",
    )


# =============================================================================
# Markers
# =============================================================================


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (may require external services)",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (longer running)",
    )

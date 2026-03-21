"""
Supabase and VPS API client module for Karaoke Agent.

Handles all backend communication:
- Direct Supabase REST API calls (heartbeat to worker_health table)
- VPS/n8n webhook API calls (job claim, update, lease renewal)

Both are encapsulated here as they form the "backend" for the karaoke pipeline.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import requests
from requests.exceptions import RequestException, Timeout

if TYPE_CHECKING:
    from karaoke_agent.config import APIConfig, SupabaseConfig, WorkerConfig
    from karaoke_agent.utils import CircuitBreaker

logger = logging.getLogger(__name__)


@dataclass
class WorkerHealth:
    """Health metrics for worker heartbeat."""

    worker_id: str
    worker_type: str = "home-agent"
    status: str = "idle"
    jobs_processed_today: int = 0
    errors_today: int = 0
    current_job_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """Convert to Supabase REST API payload."""
        return {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type,
            "last_seen": datetime.now(UTC).isoformat(),
            "status": self.status,
            "jobs_processed_today": self.jobs_processed_today,
            "errors_today": self.errors_today,
            "current_job_id": self.current_job_id,
            "metadata": self.metadata,
        }


@dataclass
class JobClaim:
    """Represents a claimed job from the API."""

    job_id: str
    source_url: str
    video_id: str
    title: str
    raw_data: dict[str, Any]

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> JobClaim:
        """Create JobClaim from API response."""
        return cls(
            job_id=data["jobId"],
            source_url=data["sourceUrl"],
            video_id=data.get("videoId", "unknown"),
            title=data.get("title", "Unknown"),
            raw_data=data,
        )


class SupabaseClient:
    """Client for direct Supabase REST API operations."""

    def __init__(self, config: SupabaseConfig) -> None:
        """
        Initialize Supabase client.

        Args:
            config: Supabase configuration with URL and service key
        """
        self.url = config.url.rstrip("/")
        self.service_key = config.service_key
        self._session = requests.Session()
        self._session.headers.update(
            {
                "apikey": self.service_key,
                "Authorization": f"Bearer {self.service_key}",
                "Content-Type": "application/json",
            }
        )

    def send_heartbeat(self, health: WorkerHealth) -> bool:
        """
        Send health heartbeat to Supabase worker_health table.

        Uses upsert (merge-duplicates) to insert or update the worker record.

        Args:
            health: Worker health metrics

        Returns:
            True if heartbeat was sent successfully
        """
        try:
            response = self._session.post(
                f"{self.url}/rest/v1/worker_health",
                headers={"Prefer": "resolution=merge-duplicates"},
                json=health.to_payload(),
                timeout=10,
            )

            if response.status_code in (200, 201):
                logger.debug(f"Heartbeat sent: status={health.status}")
                return True

            logger.warning(f"Heartbeat failed: {response.status_code} - {response.text}")
            return False

        except Timeout:
            logger.error("Heartbeat timed out")
            return False
        except RequestException as e:
            logger.error(f"Heartbeat error: {e}")
            return False

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()


class VPSApiClient:
    """Client for VPS/n8n webhook API operations."""

    def __init__(
        self,
        api_config: APIConfig,
        worker_config: WorkerConfig,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        """
        Initialize VPS API client.

        Args:
            api_config: API configuration with base URL and worker token
            worker_config: Worker configuration with worker ID
            circuit_breaker: Optional circuit breaker for API calls
        """
        self.base_url = api_config.base_url.rstrip("/")
        self.worker_token = api_config.worker_token
        self.worker_id = worker_config.worker_id
        self.circuit_breaker = circuit_breaker
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.worker_token}",
                "Content-Type": "application/json",
                "X-Worker-ID": self.worker_id,
            }
        )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> requests.Response | None:
        """
        Make an API request with optional circuit breaker protection.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/worker/claim")
            payload: Optional JSON payload
            timeout: Request timeout in seconds

        Returns:
            Response object or None if circuit breaker is open
        """
        if self.circuit_breaker and self.circuit_breaker.is_open():
            logger.warning(f"API circuit breaker open: {self.circuit_breaker.get_status()}")
            return None

        def _request() -> requests.Response:
            return self._session.request(
                method,
                f"{self.base_url}{endpoint}",
                json=payload,
                timeout=timeout,
            )

        if self.circuit_breaker:
            return self.circuit_breaker.call(_request)
        return _request()

    def claim_job(self) -> JobClaim | None:
        """
        Claim a job from the VPS API.

        Returns:
            JobClaim if a job was claimed, None if no jobs available or error
        """
        try:
            response = self._make_request(
                "POST",
                "/worker/claim",
                payload={"worker_id": self.worker_id},
            )

            if response is None:
                return None

            if response.status_code == 204:
                # No jobs available
                return None

            if response.status_code == 200:
                data = response.json()
                job = JobClaim.from_api_response(data)
                logger.info(f"Claimed job: {job.job_id} - {job.title}")
                return job

            logger.warning(f"Claim failed: {response.status_code} - {response.text}")
            return None

        except RequestException as e:
            logger.error(f"API error claiming job: {e}")
            return None

    def update_job(
        self,
        job_id: str,
        status: str,
        error: str | None = None,
        s3_key: str | None = None,
    ) -> bool:
        """
        Update job status on VPS.

        Args:
            job_id: Job identifier
            status: New job status
            error: Optional error message
            s3_key: Optional S3 key for uploaded file

        Returns:
            True if update was successful
        """
        try:
            payload: dict[str, Any] = {
                "jobId": job_id,
                "status": status,
                "workerId": self.worker_id,
            }

            if error:
                payload["error"] = error
            if s3_key:
                payload["s3Key"] = s3_key

            response = self._make_request("POST", "/worker/update", payload=payload)

            if response is None:
                return False

            if response.status_code == 200:
                logger.info(f"Updated job {job_id} -> {status}")
                return True

            logger.warning(f"Update failed: {response.status_code} - {response.text}")
            return False

        except RequestException as e:
            logger.error(f"API error updating job: {e}")
            return False

    def renew_lease(self, job_id: str) -> bool:
        """
        Renew lease for a job being processed.

        This should be called periodically during long-running job processing
        to prevent the job from being reclaimed by another worker.

        Args:
            job_id: Job identifier

        Returns:
            True if lease renewal was successful
        """
        try:
            response = self._make_request(
                "POST",
                "/worker/renew-lease",
                payload={"jobId": job_id},
                timeout=10,
            )

            if response is None:
                return False

            if response.status_code == 200:
                logger.debug(f"Lease renewed for job {job_id}")
                return True

            logger.warning(f"Lease renewal failed for {job_id}: {response.status_code}")
            return False

        except RequestException as e:
            logger.warning(f"Lease renewal error for {job_id}: {e}")
            return False

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()


class BackendClient:
    """
    Combined client for all backend operations.

    Provides a single interface for:
    - Supabase operations (heartbeat)
    - VPS API operations (job management)
    """

    def __init__(
        self,
        supabase_config: SupabaseConfig,
        api_config: APIConfig,
        worker_config: WorkerConfig,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        """
        Initialize combined backend client.

        Args:
            supabase_config: Supabase configuration
            api_config: VPS API configuration
            worker_config: Worker configuration
            circuit_breaker: Optional circuit breaker for API calls
        """
        self.supabase = SupabaseClient(supabase_config)
        self.vps_api = VPSApiClient(api_config, worker_config, circuit_breaker)
        self.worker_id = worker_config.worker_id

        # Health metrics
        self._health = WorkerHealth(
            worker_id=self.worker_id,
            metadata={
                "hostname": os.uname().nodename,
            },
        )
        self._last_heartbeat_date = datetime.now(UTC).date()

    def _reset_daily_counters(self) -> None:
        """Reset daily counters at midnight UTC."""
        today = datetime.now(UTC).date()
        if today != self._last_heartbeat_date:
            logger.info("New day - resetting daily counters")
            self._health.jobs_processed_today = 0
            self._health.errors_today = 0
            self._last_heartbeat_date = today

    def update_health(
        self,
        status: str | None = None,
        current_job_id: str | None = None,
        increment_jobs: bool = False,
        increment_errors: bool = False,
    ) -> None:
        """
        Update health metrics.

        Args:
            status: New worker status
            current_job_id: Currently processing job ID
            increment_jobs: Increment jobs_processed_today counter
            increment_errors: Increment errors_today counter
        """
        if status is not None:
            self._health.status = status
        if current_job_id is not None:
            self._health.current_job_id = current_job_id
        if increment_jobs:
            self._health.jobs_processed_today += 1
        if increment_errors:
            self._health.errors_today += 1

    def send_heartbeat(self) -> bool:
        """Send health heartbeat to Supabase."""
        self._reset_daily_counters()
        return self.supabase.send_heartbeat(self._health)

    def claim_job(self) -> JobClaim | None:
        """Claim a job from the VPS API."""
        return self.vps_api.claim_job()

    def update_job(
        self,
        job_id: str,
        status: str,
        error: str | None = None,
        s3_key: str | None = None,
    ) -> bool:
        """Update job status on VPS."""
        return self.vps_api.update_job(job_id, status, error, s3_key)

    def renew_lease(self, job_id: str) -> bool:
        """Renew lease for a job."""
        return self.vps_api.renew_lease(job_id)

    def close(self) -> None:
        """Close all HTTP sessions."""
        self.supabase.close()
        self.vps_api.close()

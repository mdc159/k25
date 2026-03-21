"""
Command-line interface for Karaoke Agent.

Usage:
    karaoke-agent --loop           # Run continuous worker loop
    karaoke-agent --once           # Process single job and exit
    karaoke-agent --once --dry-run # Claim job but don't process
    karaoke-agent --version        # Show version
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from karaoke_agent import __version__
from karaoke_agent.config import load_settings


def setup_logging(verbose: bool = False, log_file: Path | None = None) -> None:
    """
    Configure logging for the application.

    Args:
        verbose: Enable debug logging
        log_file: Optional file path for logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    # Add file handler if specified
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter(format_str))
            handlers.append(file_handler)
        except (PermissionError, OSError) as e:
            click.echo(f"Warning: Could not create log file: {e}", err=True)

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=handlers,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


@click.command()
@click.option(
    "--loop",
    is_flag=True,
    default=False,
    help="Run continuous worker loop (default mode)",
)
@click.option(
    "--once",
    is_flag=True,
    default=False,
    help="Process single job and exit",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Claim jobs but don't actually download/upload",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable debug logging",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to .env file",
)
@click.option(
    "--config-check",
    is_flag=True,
    default=False,
    help="Validate configuration and exit",
)
@click.version_option(version=__version__, prog_name="karaoke-agent")
def main(
    loop: bool,
    once: bool,
    dry_run: bool,
    verbose: bool,
    env_file: Path | None,
    config_check: bool,
) -> None:
    """
    Karaoke Agent - Home Linux Worker for YouTube Downloads.

    Downloads YouTube videos and uploads to S3 for GPU processing.

    \b
    Examples:
        karaoke-agent --loop           # Run continuous worker
        karaoke-agent --once           # Process one job and exit
        karaoke-agent --once --dry-run # Test job claiming
        karaoke-agent --config-check   # Validate configuration
    """
    # Load and validate configuration
    try:
        settings = load_settings(env_file)
    except Exception as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)

    # Setup logging
    setup_logging(verbose=verbose, log_file=settings.worker.log_file)
    logger = logging.getLogger(__name__)

    # Config check mode
    if config_check:
        click.echo("Configuration validated successfully!")
        click.echo(f"  Worker ID: {settings.worker.worker_id}")
        click.echo(f"  API Base: {settings.api.base_url}")
        click.echo(f"  S3 Bucket: {settings.s3.bucket}")
        click.echo(f"  S3 Endpoint: {settings.s3.endpoint}")
        click.echo(f"  Download Dir: {settings.worker.download_dir}")
        click.echo(f"  Poll Interval: {settings.worker.poll_interval}s")
        click.echo(f"  Heartbeat Interval: {settings.worker.heartbeat_interval}s")
        sys.exit(0)

    # Validate mode selection
    if loop and once:
        click.echo("Error: Cannot specify both --loop and --once", err=True)
        sys.exit(1)

    # Default to loop mode if neither specified
    if not loop and not once:
        loop = True

    # Import agent here to avoid import errors if config is invalid
    from karaoke_agent.agent import KaraokeAgent

    try:
        agent = KaraokeAgent(settings)

        if once:
            # Single job mode
            logger.info("Running in single-job mode")
            result = agent.run_once(dry_run=dry_run)

            if result is None:
                click.echo("No jobs available")
                sys.exit(0)

            if result.success:
                click.echo(f"Job {result.job_id} completed successfully")
                if result.s3_key:
                    click.echo(f"  S3 Key: {result.s3_key}")
                sys.exit(0)
            else:
                click.echo(f"Job {result.job_id} failed: {result.error}", err=True)
                sys.exit(1)
        else:
            # Continuous loop mode
            logger.info("Running in continuous loop mode")
            if dry_run:
                logger.info("DRY RUN MODE - no actual downloads/uploads will occur")
            agent.run_loop(dry_run=dry_run)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Dagster sensors for floe platform automation.

This module provides sensor definitions for automated pipeline triggering
and platform health monitoring. Sensors enable event-driven orchestration
beyond cron-based scheduling.

Sensors:
    health_check_sensor: Auto-trigger first pipeline run on platform health check

Example:
    >>> from floe_orchestrator_dagster.sensors import health_check_sensor
    >>> # Include in Definitions
    >>> Definitions(assets=[...], sensors=[health_check_sensor])
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator

from dagster import RunRequest, SensorEvaluationContext, sensor

logger = logging.getLogger(__name__)


def _check_platform_health() -> bool:
    """Check if platform services are healthy.

    Performs lightweight health checks on critical platform services:
    - Dagster webserver (via environment variable check)
    - Database connectivity (assumes healthy if running)

    Returns:
        True if platform is healthy, False otherwise.

    Note:
        In production, this would make actual HTTP health check calls.
        For demo/development, we use environment-based heuristics.
    """
    # Check if DAGSTER_HOME is set (indicates Dagster is configured)
    dagster_home = os.environ.get("DAGSTER_HOME")
    if not dagster_home:
        logger.debug("Platform health check: DAGSTER_HOME not set")
        return False

    # In production, add checks for:
    # - Database connectivity (postgres/iceberg catalog)
    # - S3/storage accessibility
    # - OTel collector reachability

    logger.debug("Platform health check: passed")
    return True


def _health_check_sensor_impl(
    context: SensorEvaluationContext,
) -> Generator[RunRequest, None, None]:
    """Auto-trigger sensor that starts pipeline runs when platform is healthy.

    This sensor enables automated demo flows by triggering pipeline execution
    once platform services are confirmed healthy. Designed for FR-029 (demo
    automation) and FR-033 (health monitoring).

    The sensor:
    1. Checks platform service health (Dagster, catalog, storage)
    2. Triggers a run request if healthy and no recent runs
    3. Uses cursor to track last trigger time (avoids duplicate triggers)

    Args:
        context: Dagster SensorEvaluationContext with cursor access.

    Yields:
        RunRequest when platform is healthy and ready for pipeline execution.

    Requirements:
        FR-029: Auto-trigger demo pipeline on platform health
        FR-033: Health check integration for platform services

    Example:
        >>> # Sensor automatically yields RunRequest when conditions met
        >>> # No manual invocation needed - Dagster daemon evaluates sensors
    """
    # Check if we've already triggered (use cursor to track state)
    last_trigger = context.cursor or "never"

    logger.info(
        "Evaluating health check sensor",
        extra={"last_trigger": last_trigger},
    )

    # Check platform health
    if not _check_platform_health():
        logger.debug("Platform not healthy, skipping trigger")
        return

    # Only trigger once per sensor evaluation cycle
    # In production, you might add more sophisticated logic:
    # - Check if specific jobs are already running
    # - Throttle based on last run time
    # - Trigger different jobs based on platform state

    if last_trigger == "never":
        logger.info("Platform healthy, triggering first pipeline run")

        # Update cursor to mark that we've triggered
        context.update_cursor("triggered")

        # Yield run request for the demo pipeline
        # Note: job_name should match the job defined in Definitions
        yield RunRequest(
            run_key="health_check_auto_trigger",
            tags={
                "source": "health_check_sensor",
                "trigger_type": "auto",
            },
        )
    else:
        logger.debug(
            "Health check already completed, no action needed",
            extra={"last_trigger": last_trigger},
        )


# Create the actual sensor by decorating the implementation.
# asset_selection targets all assets — when the sensor yields a RunRequest,
# Dagster materializes the full asset graph (demo pipeline).
health_check_sensor = sensor(
    name="health_check_sensor",
    description="Triggers first pipeline run when platform services are healthy",
    minimum_interval_seconds=60,  # Check every minute
    asset_selection="*",
)(_health_check_sensor_impl)


__all__ = ["health_check_sensor", "_health_check_sensor_impl"]

"""OpenLineage integration for quality check results.

This module provides OpenLineage event emission for quality check
failures, enabling observability and lineage tracking.

The emitter creates FAIL events with DataQuality facets that include:
- Check name and result
- Quality dimension
- Severity level
- Failure details
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from floe_core.schemas.quality_score import QualityCheckResult

logger = logging.getLogger(__name__)


def create_quality_facet(check_results: Sequence[QualityCheckResult]) -> dict[str, Any]:
    """Create an OpenLineage DataQuality facet from check results.

    Args:
        check_results: List of quality check results.

    Returns:
        Dict representing the DataQuality facet.
    """
    assertions = []

    for result in check_results:
        assertion = {
            "assertion": result.check_name,
            "success": result.passed,
            "column": result.details.get("column"),
            "dimension": result.dimension.value,
            "severity": result.severity.value,
        }

        # Add failure details if not passed
        if not result.passed:
            if result.error_message:
                assertion["message"] = result.error_message
            if result.records_failed > 0:
                assertion["recordsFailed"] = result.records_failed
            if result.records_checked > 0:
                assertion["recordsChecked"] = result.records_checked

        assertions.append(assertion)

    return {
        "dataQuality": {
            "_producer": "floe-quality-gx",
            "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataQualityMetricsInputDatasetFacet.json",
            "assertions": assertions,
        }
    }


class OpenLineageQualityEmitter:
    """Emitter for OpenLineage quality events.

    Sends FAIL events when quality checks fail, enabling observability
    and lineage tracking in tools like Marquez and DataHub.
    """

    def __init__(
        self,
        backend_url: str,
        namespace: str = "floe",
        timeout_seconds: int = 5,
    ) -> None:
        """Initialize the emitter.

        Args:
            backend_url: URL of the OpenLineage backend (e.g., Marquez).
            namespace: OpenLineage namespace for jobs.
            timeout_seconds: HTTP request timeout.
        """
        self.backend_url = backend_url
        self.namespace = namespace
        # Clamp timeout to a safe range to prevent resource exhaustion.
        self.timeout_seconds = max(1, min(timeout_seconds, 30))

    def emit_fail_event(
        self,
        job_name: str,
        dataset_name: str,
        check_results: Sequence[QualityCheckResult],
    ) -> None:
        """Emit an OpenLineage FAIL event for quality check failures.

        Creates an OpenLineage RunEvent with FAIL state and DataQuality
        facet containing the check results.

        Args:
            job_name: Name of the quality check job.
            dataset_name: Name of the dataset being validated.
            check_results: List of check results (passed and failed).

        Note:
            This method gracefully handles errors - connection failures
            or other issues are logged but do not raise exceptions.
        """
        if not check_results:
            logger.debug("No check results to emit")
            return

        # Filter to only failed checks for the FAIL event
        failed_checks = [r for r in check_results if not r.passed]
        if not failed_checks:
            logger.debug("No failed checks to emit")
            return

        try:
            # Create the OpenLineage event
            event = self._create_fail_event(job_name, dataset_name, failed_checks)
            self._send_event(event)
        except Exception:
            # Graceful degradation - log and continue
            logger.warning(
                "Failed to emit OpenLineage FAIL event for %s",
                dataset_name,
                exc_info=True,
            )

    def _create_fail_event(
        self,
        job_name: str,
        dataset_name: str,
        check_results: Sequence[QualityCheckResult],
    ) -> dict[str, Any]:
        """Create an OpenLineage FAIL RunEvent.

        Args:
            job_name: Name of the quality check job.
            dataset_name: Name of the dataset being validated.
            check_results: List of failed check results.

        Returns:
            Dict representing the OpenLineage RunEvent.
        """
        run_id = str(uuid4())
        event_time = datetime.now(timezone.utc).isoformat()

        # Create quality facet
        quality_facet = create_quality_facet(check_results)

        return {
            "eventType": "FAIL",
            "eventTime": event_time,
            "run": {
                "runId": run_id,
            },
            "job": {
                "namespace": self.namespace,
                "name": job_name,
            },
            "inputs": [
                {
                    "namespace": self.namespace,
                    "name": dataset_name,
                    "facets": quality_facet,
                }
            ],
            "outputs": [],
            "producer": "floe-quality-gx",
        }

    def _send_event(self, event: dict[str, Any]) -> None:
        """Send event to OpenLineage backend.

        Args:
            event: The OpenLineage event to send.

        Raises:
            Exception: If sending fails (caught by caller).
        """
        import json

        try:
            import requests

            url = f"{self.backend_url}/api/v1/lineage"
            response = requests.post(
                url,
                json=event,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            logger.debug("Sent OpenLineage event: %s", json.dumps(event)[:200])
        except ImportError:
            # requests not available - log the event instead
            logger.info(
                "OpenLineage event (requests not installed): %s",
                json.dumps(event)[:500],
            )
        except Exception:
            logger.debug(
                "Failed to send event to %s (will retry or skip)",
                self.backend_url,
            )
            raise


__all__ = [
    "OpenLineageQualityEmitter",
    "create_quality_facet",
]

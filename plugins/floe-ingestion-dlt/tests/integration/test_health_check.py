"""Integration tests for DltIngestionPlugin health check.

These tests validate that the DltIngestionPlugin health_check() method
correctly reports plugin health and meets all health check requirements.

Requirements Covered:
- 4F-FR-007: Plugin health_check() method
- CR-002: Plugin health_check contract
- SC-007: Health checks respond within 1 second

NOTE: The current DltIngestionPlugin.health_check() implementation does NOT
yet support the timeout parameter, response_time_ms, or checked_at fields.
These will be implemented in T017 (Phase 4).

The following tests from BaseHealthCheckTests are expected to FAIL:
- test_health_check_includes_response_time
- test_health_check_includes_checked_at_timestamp
- test_health_check_accepts_timeout_parameter
- test_health_check_rejects_invalid_timeout_low
- test_health_check_rejects_invalid_timeout_high
- test_health_check_accepts_boundary_timeout_min
- test_health_check_accepts_boundary_timeout_max

The following tests SHOULD PASS with current implementation:
- test_health_check_exists
- test_health_check_returns_health_status
- test_health_check_reports_healthy_when_connected
- test_health_check_reports_unhealthy_when_not_connected
- test_health_check_does_not_raise_when_unhealthy
- test_health_check_includes_message
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from testing.base_classes.base_health_check_tests import BaseHealthCheckTests

from floe_ingestion_dlt import DltIngestionPlugin

if TYPE_CHECKING:
    pass


@pytest.mark.requirement("4F-FR-007")
class TestDltIngestionHealthCheck(BaseHealthCheckTests):
    """Integration tests for DltIngestionPlugin health check.

    Inherits standard health check tests from BaseHealthCheckTests.
    These tests validate:
    - HealthStatus return type
    - Healthy/unhealthy state reporting
    - Response time capture (T017)
    - Timeout handling (T017)
    - Timestamp inclusion (T017)
    - Unconnected state handling
    """

    @pytest.fixture
    def unconnected_plugin(self) -> DltIngestionPlugin:
        """Return plugin that hasn't been started.

        Returns:
            Unconnected DltIngestionPlugin instance.
        """
        return DltIngestionPlugin()

    @pytest.fixture
    def connected_plugin(self) -> Generator[DltIngestionPlugin, None, None]:
        """Return plugin that has been started.

        Yields:
            Connected DltIngestionPlugin instance.
        """
        plugin = DltIngestionPlugin()
        plugin.startup()
        yield plugin
        plugin.shutdown()

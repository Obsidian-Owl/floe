"""Integration tests for DltIngestionPlugin health check.

These tests validate that the DltIngestionPlugin health_check() method
correctly reports import-only runtime health without probing catalog or
object-storage services.

Requirements Covered:
- 4F-FR-007: Plugin health_check() method
- CR-002: Plugin health_check contract
- SC-007: Health checks respond within 1 second

The plugin-level health check intentionally avoids network reachability probes;
configured service checks are covered by targeted helpers and tests.
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
    - Response time capture
    - Timeout handling
    - Timestamp inclusion
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

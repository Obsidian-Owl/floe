"""Integration tests for DuckDB plugin discovery via entry points.

Tests for:
- FR-006: Plugin is discoverable via floe.computes entry point
- FR-004: Plugin correctly implements PluginMetadata
- FR-024: Plugin entry point discovery

These tests verify that the DuckDB plugin is correctly registered
via entry points and can be discovered at runtime.

This module uses BasePluginDiscoveryTests to provide standard discovery
test cases, reducing test duplication across plugins.

Task ID: T048
Phase: 7 - US7 (Reduce Test Duplication)
User Story: US7 - Reduce Test Duplication
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

from floe_core import ComputePlugin
from testing.base_classes import BasePluginDiscoveryTests

if TYPE_CHECKING:
    from typing import Any


@pytest.mark.integration
class TestDuckDBPluginDiscovery(BasePluginDiscoveryTests):
    """Integration tests for DuckDB plugin discovery.

    Inherits standard discovery tests from BasePluginDiscoveryTests:
    - Entry point registration tests
    - Plugin loading tests
    - Metadata presence tests
    - ABC compliance tests
    - Lifecycle method presence tests

    DuckDB-specific tests are added below.
    """

    # Required class variables for BasePluginDiscoveryTests
    entry_point_group: ClassVar[str] = "floe.computes"
    expected_name: ClassVar[str] = "duckdb"
    expected_module_prefix: ClassVar[str] = "floe_compute_duckdb"
    expected_class_name: ClassVar[str] = "DuckDBComputePlugin"
    expected_plugin_abc: ClassVar[type[Any]] = ComputePlugin

    # =========================================================================
    # DuckDB-Specific Tests
    # =========================================================================

    @pytest.mark.requirement("001-FR-001")
    def test_duckdb_plugin_is_self_hosted(self) -> None:
        """Test DuckDBComputePlugin is marked as self-hosted.

        DuckDB runs within the platform K8s cluster (self-hosted),
        unlike cloud services like Snowflake or BigQuery.
        """
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin = matching[0].load()()

        assert plugin.is_self_hosted is True

    @pytest.mark.requirement("001-FR-001")
    def test_duckdb_plugin_description_mentions_duckdb(self) -> None:
        """Test DuckDB plugin description mentions DuckDB."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin = matching[0].load()()

        assert "DuckDB" in plugin.description

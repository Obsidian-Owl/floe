"""Unit tests for Dagster orchestrator plugin discovery via entry points.

Tests for:
- FR-006: Plugin is discoverable via floe.orchestrators entry point
- FR-004: Plugin correctly implements PluginMetadata
- FR-024: Plugin entry point discovery

These tests verify that the Dagster orchestrator plugin is correctly registered
via entry points and can be discovered at runtime. They do NOT require external
services (K8s, Dagster).

This module uses BasePluginDiscoveryTests to provide standard discovery
test cases, reducing test duplication across plugins.

Task ID: T050
Phase: 7 - US7 (Reduce Test Duplication)
User Story: US7 - Reduce Test Duplication
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest
from floe_core.plugins.orchestrator import OrchestratorPlugin
from testing.base_classes import BasePluginDiscoveryTests

if TYPE_CHECKING:
    from typing import Any


class TestDagsterOrchestratorPluginDiscovery(BasePluginDiscoveryTests):
    """Unit tests for Dagster orchestrator plugin discovery.

    Inherits standard discovery tests from BasePluginDiscoveryTests:
    - Entry point registration tests
    - Plugin loading tests
    - Metadata presence tests
    - ABC compliance tests
    - Lifecycle method presence tests

    Dagster-specific tests are added below.
    """

    # Required class variables for BasePluginDiscoveryTests
    entry_point_group: ClassVar[str] = "floe.orchestrators"
    expected_name: ClassVar[str] = "dagster"
    expected_module_prefix: ClassVar[str] = "floe_orchestrator_dagster"
    expected_class_name: ClassVar[str] = "DagsterOrchestratorPlugin"
    expected_plugin_abc: ClassVar[type[Any]] = OrchestratorPlugin

    # =========================================================================
    # Dagster-Specific Tests
    # =========================================================================

    @pytest.mark.requirement("004-FR-003")
    def test_dagster_plugin_description_mentions_dagster(self) -> None:
        """Test Dagster plugin description mentions Dagster."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin = self.create_plugin_instance(matching[0].load())

        assert "dagster" in plugin.description.lower()

    @pytest.mark.requirement("004-FR-002")
    def test_dagster_plugin_instantiation_without_dependencies(self) -> None:
        """Test plugin can be instantiated without external services.

        Verifies that the plugin can be created without needing
        a running Dagster service or other external dependencies.
        """
        from importlib.metadata import entry_points

        # Load and instantiate plugin
        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin = self.create_plugin_instance(matching[0].load())

        # Basic properties should be accessible without external deps
        assert plugin.name == "dagster"
        assert isinstance(plugin.version, str) and len(plugin.version) > 0
        assert plugin.floe_api_version == "1.0"
        assert isinstance(plugin.description, str) and len(plugin.description) > 0

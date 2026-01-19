"""Unit tests for Dagster orchestrator plugin discovery via entry points.

Tests for:
- FR-002: Plugin is discoverable via floe.orchestrators entry point
- FR-003: Plugin has complete metadata
- FR-004: Plugin correctly implements OrchestratorPlugin ABC

These tests verify that the Dagster orchestrator plugin is correctly registered
via entry points and can be discovered at runtime. They do NOT require external
services (K8s, Dagster).
"""

from __future__ import annotations

import pytest


class TestDagsterOrchestratorPluginDiscovery:
    """Unit tests for Dagster orchestrator plugin discovery.

    These tests use importlib.metadata entry_points which is pure Python
    and does not require any external services.
    """

    @pytest.mark.requirement("004-FR-002")
    def test_dagster_plugin_discovered_via_entry_points(self) -> None:
        """Test DagsterOrchestratorPlugin is discoverable via entry points.

        Verifies that the plugin can be discovered using Python's
        importlib.metadata entry_points mechanism.
        """
        from importlib.metadata import entry_points

        # Get all floe.orchestrators entry points
        eps = entry_points(group="floe.orchestrators")

        # Find dagster entry point
        dagster_eps = [ep for ep in eps if ep.name == "dagster"]

        assert len(dagster_eps) == 1, "Expected exactly one 'dagster' entry point"

        # Load the plugin class
        ep = dagster_eps[0]
        plugin_class = ep.load()

        # Verify it's the correct class
        assert plugin_class.__name__ == "DagsterOrchestratorPlugin"

        # Verify it can be instantiated
        plugin = plugin_class()
        assert plugin.name == "dagster"

    @pytest.mark.requirement("004-FR-004")
    def test_dagster_plugin_is_orchestrator_plugin(self) -> None:
        """Test DagsterOrchestratorPlugin implements OrchestratorPlugin ABC.

        Verifies that the plugin loaded via entry points is a valid
        OrchestratorPlugin implementation with all required properties.
        """
        from importlib.metadata import entry_points

        from floe_core.plugins.orchestrator import OrchestratorPlugin

        # Load plugin class via entry point
        eps = entry_points(group="floe.orchestrators")
        dagster_ep = next(ep for ep in eps if ep.name == "dagster")
        plugin_class = dagster_ep.load()

        # Instantiate and verify ABC compliance
        plugin = plugin_class()

        assert isinstance(plugin, OrchestratorPlugin)
        assert plugin.name == "dagster"

    @pytest.mark.requirement("004-FR-003")
    def test_dagster_plugin_metadata_complete(self) -> None:
        """Test Dagster plugin has complete metadata.

        Verifies that all required PluginMetadata fields are properly
        populated with valid values.
        """
        from importlib.metadata import entry_points

        # Load plugin via entry point
        eps = entry_points(group="floe.orchestrators")
        dagster_ep = next(ep for ep in eps if ep.name == "dagster")
        plugin = dagster_ep.load()()

        # Verify all metadata properties
        assert plugin.name == "dagster"
        assert len(plugin.version.split(".")) == 3  # Semver format
        assert plugin.floe_api_version == "1.0"
        assert "dagster" in plugin.description.lower()

    @pytest.mark.requirement("004-FR-002")
    def test_entry_point_module_path(self) -> None:
        """Test entry point correctly references plugin module.

        Verifies that the entry point value correctly references
        the DagsterOrchestratorPlugin class in the expected module.
        """
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.orchestrators")
        dagster_ep = next(ep for ep in eps if ep.name == "dagster")

        # Verify entry point references correct module and class
        assert "floe_orchestrator_dagster" in dagster_ep.value
        assert "DagsterOrchestratorPlugin" in dagster_ep.value

    @pytest.mark.requirement("004-FR-002")
    def test_plugin_instantiation_without_dependencies(self) -> None:
        """Test plugin can be instantiated without external services.

        Verifies that the plugin can be created without needing
        a running Dagster service or other external dependencies.
        """
        from importlib.metadata import entry_points

        # Load and instantiate plugin
        eps = entry_points(group="floe.orchestrators")
        dagster_ep = next(ep for ep in eps if ep.name == "dagster")
        plugin_class = dagster_ep.load()

        # Should not raise any exceptions
        plugin = plugin_class()

        # Basic properties should be accessible
        assert plugin.name is not None
        assert plugin.version is not None
        assert plugin.floe_api_version is not None
        assert plugin.description is not None

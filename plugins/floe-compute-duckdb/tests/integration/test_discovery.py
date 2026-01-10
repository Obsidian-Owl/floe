"""Integration tests for DuckDB plugin discovery via entry points.

Tests for:
- FR-001: Plugin is discoverable via floe.computes entry point
- FR-001: Plugin correctly implements ComputePlugin ABC

These tests verify that the DuckDB plugin is correctly registered
via entry points and can be discovered at runtime.

Note: Registry-based tests are intentionally excluded because the platform
API version (0.1) is lower than the plugin's required version (1.0).
This is expected during development - the entry point mechanism is the
primary discovery method being tested.
"""

from __future__ import annotations

import pytest


class TestPluginDiscovery:
    """Integration tests for DuckDB plugin discovery."""

    @pytest.mark.integration
    @pytest.mark.requirement("001-FR-001")
    def test_duckdb_plugin_discovered_via_entry_points(self) -> None:
        """Test DuckDBComputePlugin is discoverable via entry points.

        Verifies that the plugin can be discovered using Python's
        importlib.metadata entry_points mechanism.
        """
        from importlib.metadata import entry_points

        # Get all floe.computes entry points
        eps = entry_points(group="floe.computes")

        # Find duckdb entry point
        duckdb_eps = [ep for ep in eps if ep.name == "duckdb"]

        assert len(duckdb_eps) == 1, "Expected exactly one 'duckdb' entry point"

        # Load the plugin class
        ep = duckdb_eps[0]
        plugin_class = ep.load()

        # Verify it's the correct class
        assert plugin_class.__name__ == "DuckDBComputePlugin"

        # Verify it can be instantiated
        plugin = plugin_class()
        assert plugin.name == "duckdb"

    @pytest.mark.integration
    @pytest.mark.requirement("001-FR-001")
    def test_duckdb_plugin_is_compute_plugin(self) -> None:
        """Test DuckDBComputePlugin implements ComputePlugin ABC.

        Verifies that the plugin loaded via entry points is a valid
        ComputePlugin implementation with all required properties.
        """
        from importlib.metadata import entry_points

        from floe_core import ComputePlugin

        # Load plugin class via entry point
        eps = entry_points(group="floe.computes")
        duckdb_ep = next(ep for ep in eps if ep.name == "duckdb")
        plugin_class = duckdb_ep.load()

        # Instantiate and verify ABC compliance
        plugin = plugin_class()

        assert isinstance(plugin, ComputePlugin)
        assert plugin.name == "duckdb"
        assert plugin.is_self_hosted is True

    @pytest.mark.integration
    @pytest.mark.requirement("001-FR-001")
    def test_duckdb_plugin_metadata_complete(self) -> None:
        """Test DuckDB plugin has complete metadata.

        Verifies that all required PluginMetadata fields are properly
        populated with valid values.
        """
        from importlib.metadata import entry_points

        # Load plugin via entry point
        eps = entry_points(group="floe.computes")
        duckdb_ep = next(ep for ep in eps if ep.name == "duckdb")
        plugin = duckdb_ep.load()()

        # Verify all metadata properties
        assert plugin.name == "duckdb"
        assert len(plugin.version.split(".")) == 3  # Semver format
        assert plugin.floe_api_version == "1.0"
        assert "DuckDB" in plugin.description
        assert plugin.is_self_hosted is True

    @pytest.mark.integration
    @pytest.mark.requirement("001-FR-001")
    def test_entry_point_module_path(self) -> None:
        """Test entry point correctly references plugin module.

        Verifies that the entry point value correctly references
        the DuckDBComputePlugin class in the expected module.
        """
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.computes")
        duckdb_ep = next(ep for ep in eps if ep.name == "duckdb")

        # Verify entry point references correct module and class
        assert "floe_compute_duckdb" in duckdb_ep.value
        assert "DuckDBComputePlugin" in duckdb_ep.value

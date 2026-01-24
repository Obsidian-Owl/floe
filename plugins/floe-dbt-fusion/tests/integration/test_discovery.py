"""Integration tests for DBTFusionPlugin entry point discovery.

These tests verify that DBTFusionPlugin is correctly registered and discoverable
via the floe.dbt entry point group.

Requirements:
    FR-001: DBTPlugin ABC defines dbt execution interface
    FR-017: DBTFusionPlugin registered via entry point
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase


class TestDBTFusionPluginDiscovery(IntegrationTestBase):
    """Integration tests for DBTFusionPlugin entry point discovery."""

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.mark.integration
    @pytest.mark.requirement("FR-017")
    def test_fusion_plugin_discovered_via_entry_points(self) -> None:
        """DBTFusionPlugin MUST be discoverable via floe.dbt entry point."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.dbt")
        names = [ep.name for ep in eps]

        assert "fusion" in names, (
            f"'fusion' entry point not found in floe.dbt group. "
            f"Available: {names}"
        )

    @pytest.mark.integration
    @pytest.mark.requirement("FR-017")
    def test_fusion_plugin_loads_from_entry_point(self) -> None:
        """DBTFusionPlugin MUST be loadable from entry point."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.dbt")
        ep = next((ep for ep in eps if ep.name == "fusion"), None)

        assert ep is not None, "'fusion' entry point not found"

        plugin_class = ep.load()

        assert plugin_class.__name__ == "DBTFusionPlugin"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-017")
    def test_fusion_plugin_instantiable_from_entry_point(self) -> None:
        """DBTFusionPlugin loaded from entry point MUST be instantiable.

        Note: Uses mock for Fusion binary detection since the actual
        Fusion CLI may not be installed in test environment.
        """
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.dbt")
        ep = next((ep for ep in eps if ep.name == "fusion"), None)

        assert ep is not None

        plugin_class = ep.load()

        # Mock binary detection for instantiation
        mock_info = MagicMock()
        mock_info.available = True
        mock_info.version = "0.1.0-mock"
        mock_info.binary_path = Path("/usr/local/bin/dbt-sa-cli")
        mock_info.adapters_available = ["duckdb", "snowflake"]

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ), patch(
            "floe_dbt_fusion.plugin.detect_fusion",
            return_value=mock_info,
        ):
            plugin = plugin_class()
            assert plugin.name == "fusion"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-017")
    def test_fusion_plugin_implements_dbt_plugin_abc(self) -> None:
        """DBTFusionPlugin from entry point MUST implement DBTPlugin ABC."""
        from importlib.metadata import entry_points

        from floe_core.plugins.dbt import DBTPlugin

        eps = entry_points(group="floe.dbt")
        ep = next((ep for ep in eps if ep.name == "fusion"), None)

        assert ep is not None

        plugin_class = ep.load()

        assert issubclass(plugin_class, DBTPlugin)

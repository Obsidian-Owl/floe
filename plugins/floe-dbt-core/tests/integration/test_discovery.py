"""Integration tests for DBTCorePlugin entry point discovery.

These tests verify that DBTCorePlugin is correctly registered and discoverable
via the floe.dbt entry point group.

Requirements:
    FR-001: DBTPlugin ABC defines dbt execution interface
    FR-002: DBTCorePlugin registered via entry point
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase


class TestDBTCorePluginDiscovery(IntegrationTestBase):
    """Integration tests for DBTCorePlugin entry point discovery."""

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.mark.integration
    @pytest.mark.requirement("FR-001")
    def test_core_plugin_discovered_via_entry_points(self) -> None:
        """DBTCorePlugin MUST be discoverable via floe.dbt entry point."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.dbt")
        names = [ep.name for ep in eps]

        assert "core" in names, (
            f"'core' entry point not found in floe.dbt group. "
            f"Available: {names}"
        )

    @pytest.mark.integration
    @pytest.mark.requirement("FR-001")
    def test_core_plugin_loads_from_entry_point(self) -> None:
        """DBTCorePlugin MUST be loadable from entry point."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.dbt")
        ep = next((ep for ep in eps if ep.name == "core"), None)

        assert ep is not None, "'core' entry point not found"

        plugin_class = ep.load()

        assert plugin_class.__name__ == "DBTCorePlugin"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-001")
    def test_core_plugin_instantiable_from_entry_point(self) -> None:
        """DBTCorePlugin loaded from entry point MUST be instantiable."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.dbt")
        ep = next((ep for ep in eps if ep.name == "core"), None)

        assert ep is not None

        plugin_class = ep.load()
        plugin = plugin_class()

        assert plugin.name == "core"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-001")
    def test_core_plugin_implements_dbt_plugin_abc(self) -> None:
        """DBTCorePlugin from entry point MUST implement DBTPlugin ABC."""
        from importlib.metadata import entry_points

        from floe_core.plugins.dbt import DBTPlugin

        eps = entry_points(group="floe.dbt")
        ep = next((ep for ep in eps if ep.name == "core"), None)

        assert ep is not None

        plugin_class = ep.load()

        assert issubclass(plugin_class, DBTPlugin)

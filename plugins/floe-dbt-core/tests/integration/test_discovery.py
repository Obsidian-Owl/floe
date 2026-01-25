"""Integration tests for DBTCorePlugin entry point discovery.

These tests verify that DBTCorePlugin is correctly registered and discoverable
via the floe.dbt entry point group.

Requirements:
    FR-001: DBTPlugin ABC defines dbt execution interface
    FR-002: DBTCorePlugin registered via entry point
    FR-004: All plugins MUST inherit from PluginMetadata
    FR-006: Plugin is discoverable via entry points
    FR-024: Entry point discovery mechanism
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.base_classes.plugin_discovery_tests import BasePluginDiscoveryTests

from floe_core.plugins.dbt import DBTPlugin


class TestDBTCorePluginDiscovery(BasePluginDiscoveryTests, IntegrationTestBase):
    """Integration tests for DBTCorePlugin entry point discovery.

    Uses BasePluginDiscoveryTests to provide standardized discovery tests:
    - Entry point registration (3 tests)
    - Plugin loading (3 tests)
    - Metadata validation (2 tests)
    - ABC compliance (2 tests)
    - Lifecycle methods (1 test)
    """

    # BasePluginDiscoveryTests configuration
    entry_point_group: ClassVar[str] = "floe.dbt"
    expected_name: ClassVar[str] = "core"
    expected_module_prefix: ClassVar[str] = "floe_dbt_core"
    expected_class_name: ClassVar[str] = "DBTCorePlugin"
    expected_plugin_abc: ClassVar[type[Any]] = DBTPlugin

    # IntegrationTestBase configuration
    required_services: ClassVar[list[tuple[str, int]]] = []

    def create_plugin_instance(self, plugin_class: type[Any]) -> Any:
        """Create DBTCorePlugin instance.

        DBTCorePlugin can be instantiated without configuration.
        """
        return plugin_class()

    # =========================================================================
    # Additional DBT-Specific Tests
    # =========================================================================

    @pytest.mark.integration
    @pytest.mark.requirement("FR-001")
    def test_core_plugin_has_dbt_methods(self) -> None:
        """DBTCorePlugin MUST implement all DBTPlugin abstract methods."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.dbt")
        ep = next((ep for ep in eps if ep.name == "core"), None)
        assert ep is not None

        plugin_class = ep.load()
        plugin = plugin_class()

        # Required DBTPlugin methods
        assert hasattr(plugin, "compile_project")
        assert hasattr(plugin, "run_models")
        assert hasattr(plugin, "test_models")
        assert hasattr(plugin, "lint_project")
        assert hasattr(plugin, "get_manifest")
        assert hasattr(plugin, "get_run_results")
        assert hasattr(plugin, "supports_parallel_execution")
        assert hasattr(plugin, "supports_sql_linting")
        assert hasattr(plugin, "get_runtime_metadata")

        assert callable(plugin.compile_project)
        assert callable(plugin.run_models)
        assert callable(plugin.test_models)
        assert callable(plugin.lint_project)
        assert callable(plugin.get_manifest)
        assert callable(plugin.get_run_results)
        assert callable(plugin.supports_parallel_execution)
        assert callable(plugin.supports_sql_linting)
        assert callable(plugin.get_runtime_metadata)

    @pytest.mark.integration
    @pytest.mark.requirement("FR-001")
    def test_core_plugin_reports_thread_safety(self) -> None:
        """DBTCorePlugin MUST report NOT thread-safe (dbtRunner limitation)."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.dbt")
        ep = next((ep for ep in eps if ep.name == "core"), None)
        assert ep is not None

        plugin_class = ep.load()
        plugin = plugin_class()

        # dbtRunner is NOT thread-safe per dbt documentation
        assert plugin.supports_parallel_execution() is False

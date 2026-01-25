"""Integration tests for DBTFusionPlugin entry point discovery.

These tests verify that DBTFusionPlugin is correctly registered and discoverable
via the floe.dbt entry point group.

Requirements:
    FR-001: DBTPlugin ABC defines dbt execution interface
    FR-004: All plugins MUST inherit from PluginMetadata
    FR-006: Plugin is discoverable via entry points
    FR-017: DBTFusionPlugin registered via entry point
    FR-024: Entry point discovery mechanism

Note: dbt-fusion is EXPERIMENTAL (no stable releases). Tests use mocking
for binary detection since Fusion CLI may not be installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.base_classes.plugin_discovery_tests import BasePluginDiscoveryTests

from floe_core.plugins.dbt import DBTPlugin


class TestDBTFusionPluginDiscovery(BasePluginDiscoveryTests, IntegrationTestBase):
    """Integration tests for DBTFusionPlugin entry point discovery.

    Uses BasePluginDiscoveryTests to provide standardized discovery tests:
    - Entry point registration (3 tests)
    - Plugin loading (3 tests)
    - Metadata validation (2 tests)
    - ABC compliance (2 tests)
    - Lifecycle methods (1 test)

    Note: Uses mocking for Fusion binary detection since the actual
    Fusion CLI may not be installed in test environment.
    """

    # BasePluginDiscoveryTests configuration
    entry_point_group: ClassVar[str] = "floe.dbt"
    expected_name: ClassVar[str] = "fusion"
    expected_module_prefix: ClassVar[str] = "floe_dbt_fusion"
    expected_class_name: ClassVar[str] = "DBTFusionPlugin"
    expected_plugin_abc: ClassVar[type[Any]] = DBTPlugin

    # IntegrationTestBase configuration
    required_services: ClassVar[list[tuple[str, int]]] = []

    def create_plugin_instance(self, plugin_class: type[Any]) -> Any:
        """Create DBTFusionPlugin instance with mocked binary detection.

        DBTFusionPlugin requires Fusion CLI to be available. We mock
        the binary detection to allow instantiation in test environment.
        """
        mock_info = MagicMock()
        mock_info.available = True
        mock_info.version = "0.1.0-mock"
        mock_info.binary_path = Path("/usr/local/bin/dbt-sa-cli")
        mock_info.adapters_available = ["duckdb", "snowflake"]

        with (
            patch(
                "floe_dbt_fusion.plugin.detect_fusion_binary",
                return_value=Path("/usr/local/bin/dbt-sa-cli"),
            ),
            patch(
                "floe_dbt_fusion.plugin.detect_fusion",
                return_value=mock_info,
            ),
        ):
            return plugin_class()

    # =========================================================================
    # Additional DBT-Fusion-Specific Tests
    # =========================================================================

    @pytest.mark.integration
    @pytest.mark.requirement("FR-017")
    def test_fusion_plugin_has_dbt_methods(self) -> None:
        """DBTFusionPlugin MUST implement all DBTPlugin abstract methods."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.dbt")
        ep = next((ep for ep in eps if ep.name == "fusion"), None)
        assert ep is not None

        plugin_class = ep.load()
        plugin = self.create_plugin_instance(plugin_class)

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
    @pytest.mark.requirement("FR-017")
    def test_fusion_plugin_reports_thread_safety(self) -> None:
        """DBTFusionPlugin SHOULD report thread-safe (Fusion is stateless)."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.dbt")
        ep = next((ep for ep in eps if ep.name == "fusion"), None)
        assert ep is not None

        plugin_class = ep.load()
        plugin = self.create_plugin_instance(plugin_class)

        # Fusion is stateless and thread-safe (unlike dbtRunner)
        assert plugin.supports_parallel_execution() is True

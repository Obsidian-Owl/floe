"""Integration tests for DBTFusionPlugin with real Fusion CLI.

These tests require the dbt Fusion CLI (dbt-sa-cli) to be installed.
Tests are skipped if the binary is not available.

Run these tests in the Kind cluster where Fusion is installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase

from .conftest import require_fusion

# ---------------------------------------------------------------------------
# Fusion CLI Integration Tests
# ---------------------------------------------------------------------------


class TestFusionCLIIntegration(IntegrationTestBase):
    """Integration tests for DBTFusionPlugin with real Fusion CLI."""

    # No external services required - just the Fusion CLI
    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.mark.integration
    @pytest.mark.requirement("FR-017")
    def test_fusion_plugin_compile_project(
        self,
        temp_dbt_project_for_fusion: Path,
    ) -> None:
        """DBTFusionPlugin compiles project using real Fusion CLI."""
        require_fusion()

        from floe_dbt_fusion import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        manifest_path = plugin.compile_project(
            project_dir=temp_dbt_project_for_fusion,
            profiles_dir=temp_dbt_project_for_fusion,
            target="dev",
        )

        assert manifest_path.exists()
        assert manifest_path.name == "manifest.json"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-017")
    def test_fusion_plugin_run_models(
        self,
        temp_dbt_project_for_fusion: Path,
    ) -> None:
        """DBTFusionPlugin runs models using real Fusion CLI."""
        require_fusion()

        from floe_dbt_fusion import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        result = plugin.run_models(
            project_dir=temp_dbt_project_for_fusion,
            profiles_dir=temp_dbt_project_for_fusion,
            target="dev",
        )

        assert result.success is True
        assert result.models_run > 0
        assert result.failures == 0

    @pytest.mark.integration
    @pytest.mark.requirement("FR-017")
    def test_fusion_plugin_run_models_with_select(
        self,
        temp_dbt_project_for_fusion: Path,
    ) -> None:
        """DBTFusionPlugin runs selected models using Fusion CLI."""
        require_fusion()

        from floe_dbt_fusion import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        result = plugin.run_models(
            project_dir=temp_dbt_project_for_fusion,
            profiles_dir=temp_dbt_project_for_fusion,
            target="dev",
            select="example_model",
        )

        assert result.success is True
        assert result.models_run == 1

    @pytest.mark.integration
    @pytest.mark.requirement("FR-017")
    def test_fusion_plugin_test_models(
        self,
        temp_dbt_project_with_tests: Path,
    ) -> None:
        """DBTFusionPlugin runs tests using real Fusion CLI."""
        require_fusion()

        from floe_dbt_fusion import DBTFusionPlugin

        plugin = DBTFusionPlugin()

        # First run models to populate data
        plugin.run_models(
            project_dir=temp_dbt_project_with_tests,
            profiles_dir=temp_dbt_project_with_tests,
            target="dev",
        )

        # Then run tests
        result = plugin.test_models(
            project_dir=temp_dbt_project_with_tests,
            profiles_dir=temp_dbt_project_with_tests,
            target="dev",
        )

        assert result.success is True
        assert result.tests_run > 0

    @pytest.mark.integration
    @pytest.mark.requirement("FR-018")
    def test_fusion_plugin_supports_parallel_execution(self) -> None:
        """DBTFusionPlugin correctly reports parallel execution support."""
        require_fusion()

        from floe_dbt_fusion import DBTFusionPlugin

        plugin = DBTFusionPlugin()

        # Fusion is Rust-based and thread-safe
        assert plugin.supports_parallel_execution() is True

    @pytest.mark.integration
    @pytest.mark.requirement("FR-019")
    def test_fusion_plugin_lint_project(
        self,
        temp_dbt_project_with_lint_issues: Path,
    ) -> None:
        """DBTFusionPlugin lints project using Fusion static analysis."""
        require_fusion()

        from floe_dbt_fusion import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        result = plugin.lint_project(
            project_dir=temp_dbt_project_with_lint_issues,
            profiles_dir=temp_dbt_project_with_lint_issues,
            target="dev",
            fix=False,
        )

        # Should detect lint issues
        assert result.files_checked > 0
        # May or may not have issues depending on Fusion's rules

    @pytest.mark.integration
    @pytest.mark.requirement("FR-020")
    def test_fusion_plugin_get_manifest(
        self,
        temp_dbt_project_for_fusion: Path,
    ) -> None:
        """DBTFusionPlugin retrieves manifest after compilation."""
        require_fusion()

        from floe_dbt_fusion import DBTFusionPlugin

        plugin = DBTFusionPlugin()

        # Compile first
        plugin.compile_project(
            project_dir=temp_dbt_project_for_fusion,
            profiles_dir=temp_dbt_project_for_fusion,
            target="dev",
        )

        # Get manifest
        manifest = plugin.get_manifest(temp_dbt_project_for_fusion)

        assert isinstance(manifest, dict)
        assert "metadata" in manifest
        assert "nodes" in manifest

    @pytest.mark.integration
    @pytest.mark.requirement("FR-020")
    def test_fusion_plugin_get_run_results(
        self,
        temp_dbt_project_for_fusion: Path,
    ) -> None:
        """DBTFusionPlugin retrieves run_results after execution."""
        require_fusion()

        from floe_dbt_fusion import DBTFusionPlugin

        plugin = DBTFusionPlugin()

        # Run first
        plugin.run_models(
            project_dir=temp_dbt_project_for_fusion,
            profiles_dir=temp_dbt_project_for_fusion,
            target="dev",
        )

        # Get run results
        run_results = plugin.get_run_results(temp_dbt_project_for_fusion)

        assert isinstance(run_results, dict)
        assert "metadata" in run_results
        assert "results" in run_results

    @pytest.mark.integration
    @pytest.mark.requirement("FR-020")
    def test_fusion_plugin_get_runtime_metadata(self) -> None:
        """DBTFusionPlugin returns runtime metadata."""
        require_fusion()

        from floe_dbt_fusion import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        metadata = plugin.get_runtime_metadata()

        assert metadata["runtime"] == "fusion"
        assert metadata["thread_safe"] is True
        assert "fusion_version" in metadata
        assert "adapters_available" in metadata


# ---------------------------------------------------------------------------
# Fusion Detection Integration Tests
# ---------------------------------------------------------------------------


class TestFusionDetectionIntegration(IntegrationTestBase):
    """Integration tests for Fusion binary detection."""

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.mark.integration
    @pytest.mark.requirement("FR-020")
    def test_detect_fusion_binary(self) -> None:
        """detect_fusion_binary() finds real Fusion CLI."""
        require_fusion()

        from floe_dbt_fusion import detect_fusion_binary

        binary_path = detect_fusion_binary()

        assert binary_path is not None
        assert binary_path.exists()
        assert binary_path.name == "dbt-sa-cli"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-020")
    def test_get_fusion_version(self) -> None:
        """get_fusion_version() parses real Fusion CLI version."""
        require_fusion()

        from floe_dbt_fusion import detect_fusion_binary, get_fusion_version

        binary_path = detect_fusion_binary()
        assert binary_path is not None

        version = get_fusion_version(binary_path)

        assert version is not None
        # Version should be semver format
        assert "." in version

    @pytest.mark.integration
    @pytest.mark.requirement("FR-020")
    @pytest.mark.requirement("FR-021")
    def test_detect_fusion(self) -> None:
        """detect_fusion() returns complete detection info."""
        require_fusion()

        from floe_dbt_fusion import detect_fusion

        info = detect_fusion()

        assert info.available is True
        assert info.binary_path is not None
        assert info.version is not None
        assert "duckdb" in info.adapters_available
        assert "snowflake" in info.adapters_available


# ---------------------------------------------------------------------------
# Fallback Integration Tests
# ---------------------------------------------------------------------------


class TestFallbackIntegration(IntegrationTestBase):
    """Integration tests for automatic fallback mechanism."""

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.mark.integration
    @pytest.mark.requirement("FR-021")
    def test_get_best_plugin_returns_fusion_for_duckdb(self) -> None:
        """get_best_plugin() returns Fusion for supported adapter."""
        require_fusion()

        from floe_dbt_fusion import get_best_plugin

        plugin = get_best_plugin(adapter="duckdb")

        assert plugin.name == "fusion"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-021")
    def test_check_adapter_available_for_duckdb(self) -> None:
        """check_adapter_available() returns True for DuckDB."""
        from floe_dbt_fusion import check_adapter_available

        assert check_adapter_available("duckdb") is True

    @pytest.mark.integration
    @pytest.mark.requirement("FR-021")
    def test_check_adapter_available_for_bigquery(self) -> None:
        """check_adapter_available() returns False for BigQuery."""
        from floe_dbt_fusion import check_adapter_available

        assert check_adapter_available("bigquery") is False

    @pytest.mark.integration
    @pytest.mark.requirement("FR-021")
    def test_get_available_adapters(self) -> None:
        """get_available_adapters() returns supported Rust adapters."""
        from floe_dbt_fusion import get_available_adapters

        adapters = get_available_adapters()

        assert isinstance(adapters, list)
        assert "duckdb" in adapters
        assert "snowflake" in adapters
        assert "bigquery" not in adapters

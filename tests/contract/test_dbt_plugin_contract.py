"""Contract tests for DBTPlugin ABC.

These tests validate that the DBTPlugin ABC contract remains stable for
dbt plugin implementations (floe-dbt-core, floe-dbt-fusion).

Contract tests ensure:
- All abstract methods are present and required
- Method signatures match the documented contract
- Return types are enforced
- Both plugin implementations comply with the contract

Requirements Covered:
- SC-003: Plugin contract test coverage
- FR-001: DBTPlugin ABC defines dbt execution interface
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# DBTPlugin ABC Contract Tests (T061)
# ---------------------------------------------------------------------------


class TestDBTPluginABCContract:
    """Contract tests for DBTPlugin ABC stability.

    These tests ensure that the DBTPlugin ABC maintains backward
    compatibility for existing plugin implementations.
    """

    @pytest.mark.requirement("SC-003")
    def test_dbt_plugin_is_abstract(self) -> None:
        """Verify DBTPlugin cannot be instantiated directly.

        Plugin implementations must subclass and implement all abstract methods.
        """
        from floe_core.plugins.dbt import DBTPlugin

        with pytest.raises(TypeError, match="abstract"):
            DBTPlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("SC-003")
    def test_dbt_plugin_has_required_abstract_methods(self) -> None:
        """Verify DBTPlugin declares all required abstract methods.

        The following methods MUST be abstract (part of the contract):
        - compile_project
        - run_models
        - test_models
        - lint_project
        - get_manifest
        - get_run_results
        - supports_parallel_execution
        - supports_sql_linting
        - get_runtime_metadata
        - name (from PluginMetadata)
        - version (from PluginMetadata)
        - floe_api_version (from PluginMetadata)
        """
        from floe_core.plugins.dbt import DBTPlugin

        # Get abstract methods
        abstract_methods = set()
        for name, method in inspect.getmembers(DBTPlugin):
            if getattr(method, "__isabstractmethod__", False):
                abstract_methods.add(name)

        expected_abstract = {
            # DBTPlugin-specific methods
            "compile_project",
            "run_models",
            "test_models",
            "lint_project",
            "get_manifest",
            "get_run_results",
            "supports_parallel_execution",
            "supports_sql_linting",
            "get_runtime_metadata",
            # From PluginMetadata base class
            "name",
            "version",
            "floe_api_version",
        }

        # All expected abstract methods must be present
        for method in expected_abstract:
            assert method in abstract_methods, (
                f"Missing abstract method: {method}. "
                "Removing abstract methods is a breaking change."
            )

    @pytest.mark.requirement("SC-003")
    def test_compile_project_signature(self) -> None:
        """Verify compile_project has correct signature.

        Contract:
            def compile_project(
                self,
                project_dir: Path,
                profiles_dir: Path,
                target: str,
            ) -> Path
        """
        from floe_core.plugins.dbt import DBTPlugin

        method = DBTPlugin.compile_project
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Check parameter names (excluding 'self')
        assert "project_dir" in params, "Missing project_dir parameter"
        assert "profiles_dir" in params, "Missing profiles_dir parameter"
        assert "target" in params, "Missing target parameter"

    @pytest.mark.requirement("SC-003")
    def test_run_models_signature(self) -> None:
        """Verify run_models has correct signature.

        Contract:
            def run_models(
                self,
                project_dir: Path,
                profiles_dir: Path,
                target: str,
                select: str | None = None,
                exclude: str | None = None,
                full_refresh: bool = False,
            ) -> DBTRunResult
        """
        from floe_core.plugins.dbt import DBTPlugin

        method = DBTPlugin.run_models
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Check required parameters
        assert "project_dir" in params
        assert "profiles_dir" in params
        assert "target" in params

        # Check optional parameters exist with defaults
        assert "select" in params
        assert "exclude" in params
        assert "full_refresh" in params

    @pytest.mark.requirement("SC-003")
    def test_test_models_signature(self) -> None:
        """Verify test_models has correct signature.

        Contract:
            def test_models(
                self,
                project_dir: Path,
                profiles_dir: Path,
                target: str,
                select: str | None = None,
            ) -> DBTRunResult
        """
        from floe_core.plugins.dbt import DBTPlugin

        method = DBTPlugin.test_models
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        assert "project_dir" in params
        assert "profiles_dir" in params
        assert "target" in params
        assert "select" in params

    @pytest.mark.requirement("SC-003")
    def test_lint_project_signature(self) -> None:
        """Verify lint_project has correct signature.

        Contract:
            def lint_project(
                self,
                project_dir: Path,
                profiles_dir: Path,
                target: str,
                fix: bool = False,
            ) -> LintResult
        """
        from floe_core.plugins.dbt import DBTPlugin

        method = DBTPlugin.lint_project
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        assert "project_dir" in params
        assert "profiles_dir" in params
        assert "target" in params
        assert "fix" in params

    @pytest.mark.requirement("SC-003")
    def test_get_manifest_signature(self) -> None:
        """Verify get_manifest has correct signature.

        Contract:
            def get_manifest(self, project_dir: Path) -> dict[str, Any]
        """
        from floe_core.plugins.dbt import DBTPlugin

        method = DBTPlugin.get_manifest
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        assert "project_dir" in params

    @pytest.mark.requirement("SC-003")
    def test_get_run_results_signature(self) -> None:
        """Verify get_run_results has correct signature.

        Contract:
            def get_run_results(self, project_dir: Path) -> dict[str, Any]
        """
        from floe_core.plugins.dbt import DBTPlugin

        method = DBTPlugin.get_run_results
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        assert "project_dir" in params

    @pytest.mark.requirement("SC-003")
    def test_supports_parallel_execution_signature(self) -> None:
        """Verify supports_parallel_execution has correct signature.

        Contract:
            def supports_parallel_execution(self) -> bool
        """
        from floe_core.plugins.dbt import DBTPlugin

        method = DBTPlugin.supports_parallel_execution
        sig = inspect.signature(method)

        # Should only have 'self' parameter
        assert len(sig.parameters) == 1
        assert "self" in sig.parameters

    @pytest.mark.requirement("SC-003")
    def test_supports_sql_linting_signature(self) -> None:
        """Verify supports_sql_linting has correct signature.

        Contract:
            def supports_sql_linting(self) -> bool
        """
        from floe_core.plugins.dbt import DBTPlugin

        method = DBTPlugin.supports_sql_linting
        sig = inspect.signature(method)

        # Should only have 'self' parameter
        assert len(sig.parameters) == 1
        assert "self" in sig.parameters

    @pytest.mark.requirement("SC-003")
    def test_get_runtime_metadata_signature(self) -> None:
        """Verify get_runtime_metadata has correct signature.

        Contract:
            def get_runtime_metadata(self) -> dict[str, Any]
        """
        from floe_core.plugins.dbt import DBTPlugin

        method = DBTPlugin.get_runtime_metadata
        sig = inspect.signature(method)

        # Should only have 'self' parameter
        assert len(sig.parameters) == 1
        assert "self" in sig.parameters


# ---------------------------------------------------------------------------
# Parametrized Plugin Loading Fixture (T062)
# ---------------------------------------------------------------------------


@pytest.fixture(params=["core", "fusion"])
def dbt_plugin(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    """Load DBTPlugin implementation by name.

    Parametrized fixture that loads both 'core' and 'fusion' plugins.
    Tests using this fixture run twice - once per plugin.

    Uses generator (yield) pattern to keep patches active during test execution.

    Args:
        request: Pytest fixture request with 'core' or 'fusion' param.
        tmp_path: Temporary directory for test files.

    Yields:
        Instantiated DBTPlugin (DBTCorePlugin or DBTFusionPlugin).
    """
    plugin_name = request.param

    if plugin_name == "core":
        from floe_dbt_core import DBTCorePlugin

        yield DBTCorePlugin()

    elif plugin_name == "fusion":
        # Mock Fusion binary detection and detection info for testing
        # Using yield keeps the patch active during test execution
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
            from floe_dbt_fusion import DBTFusionPlugin

            yield DBTFusionPlugin()

    else:
        raise ValueError(f"Unknown plugin: {plugin_name}")


@pytest.fixture
def temp_dbt_project(tmp_path: Path) -> Path:
    """Create minimal dbt project for contract testing."""
    project_dir = tmp_path / "dbt_project"
    project_dir.mkdir()

    # dbt_project.yml
    (project_dir / "dbt_project.yml").write_text(
        """
name: contract_test
version: '1.0.0'
profile: contract_test
model-paths: ['models']
"""
    )

    # models directory
    (project_dir / "models").mkdir()
    (project_dir / "models" / "test_model.sql").write_text(
        "SELECT 1 AS id"
    )

    # target directory for artifacts
    (project_dir / "target").mkdir()

    return project_dir


# ---------------------------------------------------------------------------
# Contract Compliance Tests for Both Plugins (T063)
# ---------------------------------------------------------------------------


class TestDBTPluginCompliance:
    """Contract compliance tests for DBTPlugin implementations.

    These tests verify that both DBTCorePlugin and DBTFusionPlugin
    comply with the DBTPlugin contract.
    """

    @pytest.mark.requirement("SC-003")
    def test_plugin_has_name_property(self, dbt_plugin: Any) -> None:
        """Both plugins must implement name property."""
        assert hasattr(dbt_plugin, "name")
        assert isinstance(dbt_plugin.name, str)
        assert len(dbt_plugin.name) > 0

    @pytest.mark.requirement("SC-003")
    def test_plugin_has_version_property(self, dbt_plugin: Any) -> None:
        """Both plugins must implement version property."""
        assert hasattr(dbt_plugin, "version")
        assert isinstance(dbt_plugin.version, str)
        # Verify semver-like format
        parts = dbt_plugin.version.split(".")
        assert len(parts) >= 2, "Version should be semver format (X.Y.Z)"

    @pytest.mark.requirement("SC-003")
    def test_plugin_has_floe_api_version_property(self, dbt_plugin: Any) -> None:
        """Both plugins must implement floe_api_version property."""
        assert hasattr(dbt_plugin, "floe_api_version")
        assert isinstance(dbt_plugin.floe_api_version, str)

    @pytest.mark.requirement("SC-003")
    def test_compile_project_is_callable(self, dbt_plugin: Any) -> None:
        """Both plugins must implement compile_project method."""
        assert hasattr(dbt_plugin, "compile_project")
        assert callable(dbt_plugin.compile_project)

    @pytest.mark.requirement("SC-003")
    def test_run_models_is_callable(self, dbt_plugin: Any) -> None:
        """Both plugins must implement run_models method."""
        assert hasattr(dbt_plugin, "run_models")
        assert callable(dbt_plugin.run_models)

    @pytest.mark.requirement("SC-003")
    def test_test_models_is_callable(self, dbt_plugin: Any) -> None:
        """Both plugins must implement test_models method."""
        assert hasattr(dbt_plugin, "test_models")
        assert callable(dbt_plugin.test_models)

    @pytest.mark.requirement("SC-003")
    def test_lint_project_is_callable(self, dbt_plugin: Any) -> None:
        """Both plugins must implement lint_project method."""
        assert hasattr(dbt_plugin, "lint_project")
        assert callable(dbt_plugin.lint_project)

    @pytest.mark.requirement("SC-003")
    def test_get_manifest_is_callable(self, dbt_plugin: Any) -> None:
        """Both plugins must implement get_manifest method."""
        assert hasattr(dbt_plugin, "get_manifest")
        assert callable(dbt_plugin.get_manifest)

    @pytest.mark.requirement("SC-003")
    def test_get_run_results_is_callable(self, dbt_plugin: Any) -> None:
        """Both plugins must implement get_run_results method."""
        assert hasattr(dbt_plugin, "get_run_results")
        assert callable(dbt_plugin.get_run_results)

    @pytest.mark.requirement("SC-003")
    def test_supports_parallel_execution_returns_bool(
        self, dbt_plugin: Any
    ) -> None:
        """Both plugins must return bool from supports_parallel_execution."""
        result = dbt_plugin.supports_parallel_execution()
        assert isinstance(result, bool)

    @pytest.mark.requirement("SC-003")
    def test_supports_sql_linting_returns_bool(self, dbt_plugin: Any) -> None:
        """Both plugins must return bool from supports_sql_linting."""
        result = dbt_plugin.supports_sql_linting()
        assert isinstance(result, bool)

    @pytest.mark.requirement("SC-003")
    def test_get_runtime_metadata_returns_dict(self, dbt_plugin: Any) -> None:
        """Both plugins must return dict from get_runtime_metadata."""
        metadata = dbt_plugin.get_runtime_metadata()
        assert isinstance(metadata, dict)
        # Should have at least 'runtime' key
        assert "runtime" in metadata


# ---------------------------------------------------------------------------
# Plugin Differentiation Tests
# ---------------------------------------------------------------------------


class TestDBTPluginDifferentiation:
    """Tests validating the differences between Core and Fusion plugins."""

    @pytest.mark.requirement("FR-018")
    def test_core_plugin_not_thread_safe(self) -> None:
        """DBTCorePlugin should return False for parallel execution."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        assert plugin.supports_parallel_execution() is False

    @pytest.mark.requirement("FR-018")
    def test_fusion_plugin_is_thread_safe(self) -> None:
        """DBTFusionPlugin should return True for parallel execution."""
        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            from floe_dbt_fusion import DBTFusionPlugin

            plugin = DBTFusionPlugin()
            assert plugin.supports_parallel_execution() is True

    @pytest.mark.requirement("FR-013")
    def test_core_plugin_supports_sql_linting(self) -> None:
        """DBTCorePlugin should support SQL linting via SQLFluff."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        assert plugin.supports_sql_linting() is True

    @pytest.mark.requirement("FR-019")
    def test_fusion_plugin_supports_sql_linting(self) -> None:
        """DBTFusionPlugin should support SQL linting via built-in analysis."""
        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            from floe_dbt_fusion import DBTFusionPlugin

            plugin = DBTFusionPlugin()
            assert plugin.supports_sql_linting() is True

    @pytest.mark.requirement("FR-001")
    def test_core_plugin_runtime_is_core(self) -> None:
        """DBTCorePlugin should identify as 'core' runtime."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        metadata = plugin.get_runtime_metadata()
        assert metadata.get("runtime") == "core"

    @pytest.mark.requirement("FR-017")
    def test_fusion_plugin_runtime_is_fusion(self) -> None:
        """DBTFusionPlugin should identify as 'fusion' runtime."""
        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            from floe_dbt_fusion import DBTFusionPlugin

            plugin = DBTFusionPlugin()
            metadata = plugin.get_runtime_metadata()
            assert metadata.get("runtime") == "fusion"

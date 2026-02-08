"""Unit tests for DBTResource ConfigurableResource.

Tests the DBTResource Dagster ConfigurableResource that provides
DBTPlugin integration for asset materialization.

Requirements:
    - FR-037: DBTResource MUST be a Dagster ConfigurableResource
    - FR-030: DBTResource MUST load DBTPlugin from registry
    - FR-031: DBTResource MUST delegate to plugin methods
    - FR-032: DBTResource MUST pass select/exclude patterns

Note: These tests are written TDD-style. They will FAIL until
DBTResource is implemented in T030-T032.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# DBTResource Configuration Tests
# ---------------------------------------------------------------------------


class TestDBTResourceConfiguration:
    """Test DBTResource Dagster ConfigurableResource configuration."""

    @pytest.mark.requirement("FR-037")
    def test_dbt_resource_is_configurable_resource(self) -> None:
        """DBTResource MUST inherit from ConfigurableResource."""
        from dagster import ConfigurableResource

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        assert issubclass(DBTResource, ConfigurableResource)

    @pytest.mark.requirement("FR-037")
    def test_dbt_resource_has_plugin_name_field(self) -> None:
        """DBTResource MUST have plugin_name configuration field."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(plugin_name="core")
        assert resource.plugin_name == "core"

    @pytest.mark.requirement("FR-037")
    def test_dbt_resource_plugin_name_defaults_to_core(self) -> None:
        """DBTResource plugin_name SHOULD default to 'core'."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource()
        assert resource.plugin_name == "core"

    @pytest.mark.requirement("FR-037")
    def test_dbt_resource_accepts_fusion_plugin_name(self) -> None:
        """DBTResource MUST accept 'fusion' as plugin_name."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(plugin_name="fusion")
        assert resource.plugin_name == "fusion"

    @pytest.mark.requirement("FR-037")
    def test_dbt_resource_has_project_dir_field(self) -> None:
        """DBTResource MUST have project_dir configuration field."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(project_dir="/path/to/project")
        assert resource.project_dir == "/path/to/project"

    @pytest.mark.requirement("FR-037")
    def test_dbt_resource_has_profiles_dir_field(self) -> None:
        """DBTResource MUST have profiles_dir configuration field."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(profiles_dir="/path/to/profiles")
        assert resource.profiles_dir == "/path/to/profiles"

    @pytest.mark.requirement("FR-037")
    def test_dbt_resource_has_target_field(self) -> None:
        """DBTResource MUST have target configuration field."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(target="dev")
        assert resource.target == "dev"

    @pytest.mark.requirement("FR-037")
    def test_dbt_resource_target_defaults_to_dev(self) -> None:
        """DBTResource target SHOULD default to 'dev'."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource()
        assert resource.target == "dev"


# ---------------------------------------------------------------------------
# DBTResource Plugin Loading Tests
# ---------------------------------------------------------------------------


class TestDBTResourcePluginLoading:
    """Test DBTResource plugin loading from registry."""

    @pytest.mark.requirement("FR-030")
    def test_get_plugin_returns_dbt_plugin(self, mock_dbt_plugin: MagicMock) -> None:
        """get_plugin() MUST return a DBTPlugin instance."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(plugin_name="core")
            plugin = resource.get_plugin()

            assert plugin is mock_dbt_plugin

    @pytest.mark.requirement("FR-030")
    def test_get_plugin_loads_from_registry_by_name(
        self, mock_dbt_plugin: MagicMock
    ) -> None:
        """get_plugin() MUST load plugin by name from registry."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ) as mock_load:
            resource = DBTResource(plugin_name="fusion")
            resource.get_plugin()

            mock_load.assert_called_once_with("fusion")

    @pytest.mark.requirement("FR-030")
    def test_get_plugin_caches_plugin_instance(
        self, mock_dbt_plugin: MagicMock
    ) -> None:
        """get_plugin() SHOULD cache the plugin instance."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ) as mock_load:
            resource = DBTResource(plugin_name="core")

            # Call get_plugin twice
            plugin1 = resource.get_plugin()
            plugin2 = resource.get_plugin()

            # Should only load once (cached)
            mock_load.assert_called_once()
            assert plugin1 is plugin2

    @pytest.mark.requirement("FR-030")
    def test_get_plugin_raises_on_invalid_plugin_name(self) -> None:
        """get_plugin() MUST raise error for unknown plugin name."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            side_effect=ValueError("Unknown plugin: nonexistent"),
        ):
            resource = DBTResource(plugin_name="nonexistent")

            with pytest.raises(ValueError, match="Unknown plugin"):
                resource.get_plugin()


# ---------------------------------------------------------------------------
# DBTResource Method Delegation Tests
# ---------------------------------------------------------------------------


class TestDBTResourceCompile:
    """Test DBTResource compile method."""

    @pytest.mark.requirement("FR-031")
    def test_compile_delegates_to_plugin(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """compile() MUST delegate to plugin.compile_project()."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            resource.compile()

            mock_dbt_plugin.compile_project.assert_called_once()

    @pytest.mark.requirement("FR-031")
    def test_compile_passes_configured_paths(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """compile() MUST pass project_dir, profiles_dir, target to plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        project_dir = tmp_path / "project"
        profiles_dir = tmp_path / "profiles"
        project_dir.mkdir()
        profiles_dir.mkdir()

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(project_dir),
                profiles_dir=str(profiles_dir),
                target="prod",
            )

            resource.compile()

            mock_dbt_plugin.compile_project.assert_called_once_with(
                project_dir=project_dir,
                profiles_dir=profiles_dir,
                target="prod",
            )

    @pytest.mark.requirement("FR-031")
    def test_compile_returns_manifest_path(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """compile() MUST return path to manifest.json."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        expected_path = tmp_path / "target" / "manifest.json"
        mock_dbt_plugin.compile_project.return_value = expected_path

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            result = resource.compile()

            assert result == expected_path


class TestDBTResourceRunModels:
    """Test DBTResource run_models method."""

    @pytest.mark.requirement("FR-031")
    def test_run_models_delegates_to_plugin(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """run_models() MUST delegate to plugin.run_models()."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            resource.run_models()

            mock_dbt_plugin.run_models.assert_called_once()

    @pytest.mark.requirement("FR-032")
    def test_run_models_passes_select_pattern(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """run_models() MUST pass select pattern to plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            resource.run_models(select="tag:daily")

            call_kwargs = mock_dbt_plugin.run_models.call_args.kwargs
            assert call_kwargs.get("select") == "tag:daily"

    @pytest.mark.requirement("FR-032")
    def test_run_models_passes_exclude_pattern(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """run_models() MUST pass exclude pattern to plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            resource.run_models(exclude="tag:skip")

            call_kwargs = mock_dbt_plugin.run_models.call_args.kwargs
            assert call_kwargs.get("exclude") == "tag:skip"

    @pytest.mark.requirement("FR-032")
    def test_run_models_passes_full_refresh(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """run_models() MUST pass full_refresh to plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            resource.run_models(full_refresh=True)

            call_kwargs = mock_dbt_plugin.run_models.call_args.kwargs
            assert call_kwargs.get("full_refresh") is True

    @pytest.mark.requirement("FR-031")
    def test_run_models_returns_dbt_run_result(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """run_models() MUST return DBTRunResult from plugin."""
        from floe_core.plugins.dbt import DBTRunResult

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        expected_result = DBTRunResult(
            success=True,
            manifest_path=tmp_path / "target" / "manifest.json",
            run_results_path=tmp_path / "target" / "run_results.json",
            models_run=5,
            failures=0,
        )
        mock_dbt_plugin.run_models.return_value = expected_result

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            result = resource.run_models()

            assert result is expected_result
            assert result.success is True
            assert result.models_run == 5


class TestDBTResourceTestModels:
    """Test DBTResource test_models method."""

    @pytest.mark.requirement("FR-031")
    def test_test_models_delegates_to_plugin(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """test_models() MUST delegate to plugin.test_models()."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            resource.test_models()

            mock_dbt_plugin.test_models.assert_called_once()

    @pytest.mark.requirement("FR-032")
    def test_test_models_passes_select_pattern(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """test_models() MUST pass select pattern to plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            resource.test_models(select="test_type:data")

            call_kwargs = mock_dbt_plugin.test_models.call_args.kwargs
            assert call_kwargs.get("select") == "test_type:data"

    @pytest.mark.requirement("FR-031")
    def test_test_models_returns_dbt_run_result(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """test_models() MUST return DBTRunResult from plugin."""
        from floe_core.plugins.dbt import DBTRunResult

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        expected_result = DBTRunResult(
            success=True,
            manifest_path=tmp_path / "target" / "manifest.json",
            run_results_path=tmp_path / "target" / "run_results.json",
            tests_run=10,
            failures=0,
        )
        mock_dbt_plugin.test_models.return_value = expected_result

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            result = resource.test_models()

            assert result is expected_result
            assert result.tests_run == 10


class TestDBTResourceLintProject:
    """Test DBTResource lint_project method."""

    @pytest.mark.requirement("FR-031")
    def test_lint_project_delegates_to_plugin(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """lint_project() MUST delegate to plugin.lint_project()."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            resource.lint_project()

            mock_dbt_plugin.lint_project.assert_called_once()

    @pytest.mark.requirement("FR-031")
    def test_lint_project_passes_fix_parameter(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """lint_project() MUST pass fix parameter to plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            resource.lint_project(fix=True)

            call_kwargs = mock_dbt_plugin.lint_project.call_args.kwargs
            assert call_kwargs.get("fix") is True


# ---------------------------------------------------------------------------
# DBTResource Capability Query Tests
# ---------------------------------------------------------------------------


class TestDBTResourceCapabilities:
    """Test DBTResource capability query methods."""

    @pytest.mark.requirement("FR-031")
    def test_supports_parallel_execution_delegates_to_plugin(
        self, mock_dbt_plugin: MagicMock
    ) -> None:
        """supports_parallel_execution() MUST delegate to plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        mock_dbt_plugin.supports_parallel_execution.return_value = False

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(plugin_name="core")

            result = resource.supports_parallel_execution()

            assert result is False
            # Called during __init__ (for logging) and again when method invoked
            assert mock_dbt_plugin.supports_parallel_execution.call_count >= 1

    @pytest.mark.requirement("FR-031")
    def test_supports_parallel_execution_returns_true_for_fusion(
        self, mock_dbt_plugin: MagicMock
    ) -> None:
        """supports_parallel_execution() MUST return True for fusion plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        mock_dbt_plugin.supports_parallel_execution.return_value = True

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(plugin_name="fusion")

            result = resource.supports_parallel_execution()

            assert result is True

    @pytest.mark.requirement("FR-031")
    def test_supports_sql_linting_delegates_to_plugin(
        self, mock_dbt_plugin: MagicMock
    ) -> None:
        """supports_sql_linting() MUST delegate to plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        mock_dbt_plugin.supports_sql_linting.return_value = True

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(plugin_name="core")

            result = resource.supports_sql_linting()

            assert result is True
            mock_dbt_plugin.supports_sql_linting.assert_called_once()


# ---------------------------------------------------------------------------
# DBTResource Metadata Tests
# ---------------------------------------------------------------------------


class TestDBTResourceMetadata:
    """Test DBTResource metadata retrieval methods."""

    @pytest.mark.requirement("FR-031")
    def test_get_manifest_delegates_to_plugin(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """get_manifest() MUST delegate to plugin.get_manifest()."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        expected_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.7.0"},
            "nodes": {},
        }
        mock_dbt_plugin.get_manifest.return_value = expected_manifest

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
            )

            result = resource.get_manifest()

            assert result == expected_manifest

    @pytest.mark.requirement("FR-031")
    def test_get_run_results_delegates_to_plugin(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """get_run_results() MUST delegate to plugin.get_run_results()."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        expected_results: dict[str, Any] = {
            "results": [],
            "elapsed_time": 1.5,
        }
        mock_dbt_plugin.get_run_results.return_value = expected_results

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
            )

            result = resource.get_run_results()

            assert result == expected_results

    @pytest.mark.requirement("FR-031")
    def test_get_runtime_metadata_delegates_to_plugin(
        self, mock_dbt_plugin: MagicMock
    ) -> None:
        """get_runtime_metadata() MUST delegate to plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        expected_metadata: dict[str, Any] = {
            "runtime": "core",
            "dbt_version": "1.7.0",
        }
        mock_dbt_plugin.get_runtime_metadata.return_value = expected_metadata

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(plugin_name="core")

            result = resource.get_runtime_metadata()

            assert result == expected_metadata


# ---------------------------------------------------------------------------
# DBTResource Error Handling Tests
# ---------------------------------------------------------------------------


class TestDBTResourceErrorHandling:
    """Test DBTResource error handling."""

    @pytest.mark.requirement("FR-031")
    def test_compile_propagates_plugin_errors(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """compile() MUST propagate errors from plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        mock_dbt_plugin.compile_project.side_effect = Exception("Compilation failed")

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            with pytest.raises(Exception, match="Compilation failed"):
                resource.compile()

    @pytest.mark.requirement("FR-031")
    def test_run_models_propagates_plugin_errors(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """run_models() MUST propagate errors from plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        mock_dbt_plugin.run_models.side_effect = Exception("Execution failed")

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            with pytest.raises(Exception, match="Execution failed"):
                resource.run_models()

    @pytest.mark.requirement("FR-031")
    def test_test_models_propagates_plugin_errors(
        self, mock_dbt_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """test_models() MUST propagate errors from plugin."""
        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        mock_dbt_plugin.test_models.side_effect = Exception("Tests failed")

        with patch(
            "floe_orchestrator_dagster.resources.dbt_resource.load_dbt_plugin",
            return_value=mock_dbt_plugin,
        ):
            resource = DBTResource(
                plugin_name="core",
                project_dir=str(tmp_path),
                profiles_dir=str(tmp_path),
                target="dev",
            )

            with pytest.raises(Exception, match="Tests failed"):
                resource.test_models()


# ---------------------------------------------------------------------------
# Fixture for mock DBT plugin (shared with dbt_fixtures.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_dbt_plugin() -> MagicMock:
    """Create a mock DBTPlugin for testing DBTResource.

    Returns:
        MagicMock: Configured mock of DBTPlugin.
    """
    from unittest.mock import PropertyMock

    from floe_core.plugins.dbt import DBTRunResult, LintResult

    mock_plugin = MagicMock()

    # Metadata
    type(mock_plugin).name = PropertyMock(return_value="mock-dbt")
    type(mock_plugin).version = PropertyMock(return_value="1.0.0")
    type(mock_plugin).floe_api_version = PropertyMock(return_value="1.0")

    # Default successful method returns
    mock_plugin.compile_project.return_value = Path("target/manifest.json")
    mock_plugin.run_models.return_value = DBTRunResult(
        success=True,
        manifest_path=Path("target/manifest.json"),
        run_results_path=Path("target/run_results.json"),
        models_run=5,
        failures=0,
    )
    mock_plugin.test_models.return_value = DBTRunResult(
        success=True,
        manifest_path=Path("target/manifest.json"),
        run_results_path=Path("target/run_results.json"),
        tests_run=10,
        failures=0,
    )
    mock_plugin.lint_project.return_value = LintResult(
        success=True,
        violations=[],
        files_checked=5,
    )
    mock_plugin.get_manifest.return_value = {
        "metadata": {"dbt_version": "1.7.0"},
        "nodes": {},
    }
    mock_plugin.get_run_results.return_value = {
        "results": [],
        "elapsed_time": 1.0,
    }
    mock_plugin.supports_parallel_execution.return_value = False
    mock_plugin.supports_sql_linting.return_value = True
    mock_plugin.get_runtime_metadata.return_value = {
        "runtime": "core",
        "dbt_version": "1.7.0",
    }

    return mock_plugin


# ---------------------------------------------------------------------------
# Tests for load_dbt_plugin function (error path coverage)
# ---------------------------------------------------------------------------


class TestLoadDbtPlugin:
    """Unit tests for load_dbt_plugin function error handling."""

    @pytest.mark.requirement("FR-030")
    def test_load_dbt_plugin_raises_value_error_for_unknown_plugin(self) -> None:
        """Test load_dbt_plugin raises ValueError for unknown plugin name.

        This tests the error path in load_dbt_plugin lines 76-79 where
        PluginNotFoundError is caught and re-raised as ValueError with
        available plugins listed.
        """
        from unittest.mock import PropertyMock

        from floe_core.plugin_errors import PluginNotFoundError
        from floe_core.plugin_types import PluginType

        from floe_orchestrator_dagster.resources.dbt_resource import load_dbt_plugin

        # Create mock registry that raises PluginNotFoundError
        mock_registry = MagicMock()
        mock_registry.get.side_effect = PluginNotFoundError(
            PluginType.DBT,  # positional: plugin_type
            "nonexistent",  # positional: name
        )

        # Create mock plugin info for available plugins list
        mock_core_plugin = MagicMock()
        type(mock_core_plugin).name = PropertyMock(return_value="core")
        mock_fusion_plugin = MagicMock()
        type(mock_fusion_plugin).name = PropertyMock(return_value="fusion")
        mock_registry.list.return_value = [mock_core_plugin, mock_fusion_plugin]

        with patch(
            "floe_core.plugin_registry.PluginRegistry",
            return_value=mock_registry,
        ):
            with pytest.raises(ValueError, match="Unknown plugin: nonexistent"):
                load_dbt_plugin("nonexistent")

    @pytest.mark.requirement("FR-030")
    def test_load_dbt_plugin_includes_available_plugins_in_error(self) -> None:
        """Test load_dbt_plugin error message includes list of available plugins."""
        from unittest.mock import PropertyMock

        from floe_core.plugin_errors import PluginNotFoundError
        from floe_core.plugin_types import PluginType

        from floe_orchestrator_dagster.resources.dbt_resource import load_dbt_plugin

        mock_registry = MagicMock()
        mock_registry.get.side_effect = PluginNotFoundError(
            PluginType.DBT,  # positional: plugin_type
            "unknown",  # positional: name
        )

        # Mock available plugins
        mock_plugin = MagicMock()
        type(mock_plugin).name = PropertyMock(return_value="available-plugin")
        mock_registry.list.return_value = [mock_plugin]

        with patch(
            "floe_core.plugin_registry.PluginRegistry",
            return_value=mock_registry,
        ):
            with pytest.raises(ValueError) as exc_info:
                load_dbt_plugin("unknown")

            error_message = str(exc_info.value)
            assert "Available:" in error_message
            assert "available-plugin" in error_message

    @pytest.mark.requirement("FR-030")
    def test_load_dbt_plugin_success(self) -> None:
        """Test load_dbt_plugin returns plugin on success."""
        from floe_orchestrator_dagster.resources.dbt_resource import load_dbt_plugin

        mock_plugin = MagicMock()
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_plugin

        with patch(
            "floe_core.plugin_registry.PluginRegistry",
            return_value=mock_registry,
        ):
            result = load_dbt_plugin("core")

            assert result is mock_plugin
            mock_registry.discover_all.assert_called_once()
            mock_registry.get.assert_called_once()

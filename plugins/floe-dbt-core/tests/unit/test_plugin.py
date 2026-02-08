"""Unit tests for DBTCorePlugin core methods.

Tests compile_project, run_models, and test_models using mocked dbtRunner.
These tests verify plugin behavior without actual dbt execution.

Requirements:
    - FR-002: compile_project invokes dbt compile
    - FR-003: run_models invokes dbt run with select/exclude/full_refresh
    - FR-004: test_models invokes dbt test
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# Import will fail until implementation exists - this is TDD
# The test should fail with ImportError initially


class TestDBTCorePluginMetadata:
    """Test plugin metadata properties."""

    @pytest.mark.requirement("FR-001")
    def test_plugin_name_is_core(self) -> None:
        """Plugin name should be 'core'."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        assert plugin.name == "core"

    @pytest.mark.requirement("FR-001")
    def test_plugin_version_is_semver(self) -> None:
        """Plugin version should follow semantic versioning."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        # Should match X.Y.Z pattern
        parts = plugin.version.split(".")
        assert len(parts) >= 2, "Version should have at least major.minor"
        assert all(p.isdigit() for p in parts[:2]), "Version parts should be numeric"

    @pytest.mark.requirement("FR-001")
    def test_plugin_floe_api_version(self) -> None:
        """Plugin should declare compatible floe API version."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        assert plugin.floe_api_version is not None
        assert len(plugin.floe_api_version) > 0


class TestDBTCorePluginCompile:
    """Test compile_project method."""

    @pytest.fixture
    def mock_dbt_runner(self) -> Generator[MagicMock, None, None]:
        """Mock dbtRunner for unit tests."""
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.exception = None
        mock_runner.invoke.return_value = mock_result

        with patch("floe_dbt_core.plugin.dbtRunner", return_value=mock_runner):
            yield mock_runner

    @pytest.mark.requirement("FR-002")
    def test_compile_project_invokes_dbt_compile(
        self, mock_dbt_runner: MagicMock, tmp_path: Path
    ) -> None:
        """compile_project should invoke dbt compile command."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test")

        # Create target directory for manifest
        (project_dir / "target").mkdir()
        (project_dir / "target" / "manifest.json").write_text("{}")

        plugin.compile_project(
            project_dir=project_dir,
            profiles_dir=tmp_path,
            target="dev",
        )

        # Verify dbt compile was invoked
        mock_dbt_runner.invoke.assert_called_once()
        call_args = mock_dbt_runner.invoke.call_args[0][0]
        assert "compile" in call_args

    @pytest.mark.requirement("FR-002")
    def test_compile_project_returns_manifest_path(
        self, mock_dbt_runner: MagicMock, tmp_path: Path
    ) -> None:
        """compile_project should return path to manifest.json."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test")

        # Create target directory for manifest
        target_dir = project_dir / "target"
        target_dir.mkdir()
        manifest_path = target_dir / "manifest.json"
        manifest_path.write_text("{}")

        result = plugin.compile_project(
            project_dir=project_dir,
            profiles_dir=tmp_path,
            target="dev",
        )

        assert result == manifest_path
        assert result.exists()

    @pytest.mark.requirement("FR-002")
    def test_compile_project_passes_target(
        self, mock_dbt_runner: MagicMock, tmp_path: Path
    ) -> None:
        """compile_project should pass target to dbt command."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test")
        (project_dir / "target").mkdir()
        (project_dir / "target" / "manifest.json").write_text("{}")

        plugin.compile_project(
            project_dir=project_dir,
            profiles_dir=tmp_path,
            target="production",
        )

        call_args = mock_dbt_runner.invoke.call_args[0][0]
        assert "--target" in call_args
        target_idx = call_args.index("--target")
        assert call_args[target_idx + 1] == "production"

    @pytest.mark.requirement("FR-033")
    def test_compile_project_raises_on_failure(self, tmp_path: Path) -> None:
        """compile_project should raise DBTCompilationError on failure."""
        from floe_dbt_core import DBTCorePlugin
        from floe_dbt_core.errors import DBTCompilationError

        # Mock failed compilation
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.exception = Exception("Undefined variable 'foo'")
        mock_runner.invoke.return_value = mock_result

        with patch("floe_dbt_core.plugin.dbtRunner", return_value=mock_runner):
            plugin = DBTCorePlugin()
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            (project_dir / "dbt_project.yml").write_text("name: test")

            with pytest.raises(DBTCompilationError) as exc_info:
                plugin.compile_project(
                    project_dir=project_dir,
                    profiles_dir=tmp_path,
                    target="dev",
                )

            assert "Undefined variable" in str(exc_info.value)


class TestDBTCorePluginRun:
    """Test run_models method."""

    @pytest.fixture
    def mock_dbt_runner(self) -> Generator[MagicMock, None, None]:
        """Mock dbtRunner for unit tests."""
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.exception = None
        mock_result.result = []
        mock_runner.invoke.return_value = mock_result

        with patch("floe_dbt_core.plugin.dbtRunner", return_value=mock_runner):
            yield mock_runner

    @pytest.mark.requirement("FR-003")
    def test_run_models_invokes_dbt_run(
        self, mock_dbt_runner: MagicMock, tmp_path: Path
    ) -> None:
        """run_models should invoke dbt run command."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test")
        (project_dir / "target").mkdir()
        (project_dir / "target" / "run_results.json").write_text("{}")

        plugin.run_models(
            project_dir=project_dir,
            profiles_dir=tmp_path,
            target="dev",
        )

        mock_dbt_runner.invoke.assert_called_once()
        call_args = mock_dbt_runner.invoke.call_args[0][0]
        assert "run" in call_args

    @pytest.mark.requirement("FR-003")
    def test_run_models_with_select(
        self, mock_dbt_runner: MagicMock, tmp_path: Path
    ) -> None:
        """run_models should pass select pattern to dbt."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test")
        (project_dir / "target").mkdir()
        (project_dir / "target" / "run_results.json").write_text("{}")

        plugin.run_models(
            project_dir=project_dir,
            profiles_dir=tmp_path,
            target="dev",
            select="tag:daily",
        )

        call_args = mock_dbt_runner.invoke.call_args[0][0]
        assert "--select" in call_args
        select_idx = call_args.index("--select")
        assert call_args[select_idx + 1] == "tag:daily"

    @pytest.mark.requirement("FR-003")
    def test_run_models_with_exclude(
        self, mock_dbt_runner: MagicMock, tmp_path: Path
    ) -> None:
        """run_models should pass exclude pattern to dbt."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test")
        (project_dir / "target").mkdir()
        (project_dir / "target" / "run_results.json").write_text("{}")

        plugin.run_models(
            project_dir=project_dir,
            profiles_dir=tmp_path,
            target="dev",
            exclude="tag:deprecated",
        )

        call_args = mock_dbt_runner.invoke.call_args[0][0]
        assert "--exclude" in call_args
        exclude_idx = call_args.index("--exclude")
        assert call_args[exclude_idx + 1] == "tag:deprecated"

    @pytest.mark.requirement("FR-003")
    def test_run_models_with_full_refresh(
        self, mock_dbt_runner: MagicMock, tmp_path: Path
    ) -> None:
        """run_models should pass --full-refresh flag when requested."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test")
        (project_dir / "target").mkdir()
        (project_dir / "target" / "run_results.json").write_text("{}")

        plugin.run_models(
            project_dir=project_dir,
            profiles_dir=tmp_path,
            target="dev",
            full_refresh=True,
        )

        call_args = mock_dbt_runner.invoke.call_args[0][0]
        assert "--full-refresh" in call_args

    @pytest.mark.requirement("FR-003")
    def test_run_models_returns_dbt_run_result(
        self, mock_dbt_runner: MagicMock, tmp_path: Path
    ) -> None:
        """run_models should return DBTRunResult."""
        from floe_core.plugins.dbt import DBTRunResult

        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test")
        target_dir = project_dir / "target"
        target_dir.mkdir()
        (target_dir / "run_results.json").write_text("{}")
        (target_dir / "manifest.json").write_text("{}")

        result = plugin.run_models(
            project_dir=project_dir,
            profiles_dir=tmp_path,
            target="dev",
        )

        assert isinstance(result, DBTRunResult)
        assert result.success is True

    @pytest.mark.requirement("FR-034")
    def test_run_models_raises_on_failure(self, tmp_path: Path) -> None:
        """run_models should raise DBTExecutionError on failure."""
        from floe_dbt_core import DBTCorePlugin
        from floe_dbt_core.errors import DBTExecutionError

        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.exception = Exception("Column 'foo' not found")
        mock_runner.invoke.return_value = mock_result

        with patch("floe_dbt_core.plugin.dbtRunner", return_value=mock_runner):
            plugin = DBTCorePlugin()
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            (project_dir / "dbt_project.yml").write_text("name: test")

            with pytest.raises(DBTExecutionError) as exc_info:
                plugin.run_models(
                    project_dir=project_dir,
                    profiles_dir=tmp_path,
                    target="dev",
                )

            assert "Column 'foo' not found" in str(exc_info.value)


class TestDBTCorePluginTest:
    """Test test_models method."""

    @pytest.fixture
    def mock_dbt_runner(self) -> Generator[MagicMock, None, None]:
        """Mock dbtRunner for unit tests."""
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.exception = None
        mock_result.result = []
        mock_runner.invoke.return_value = mock_result

        with patch("floe_dbt_core.plugin.dbtRunner", return_value=mock_runner):
            yield mock_runner

    @pytest.mark.requirement("FR-004")
    def test_test_models_invokes_dbt_test(
        self, mock_dbt_runner: MagicMock, tmp_path: Path
    ) -> None:
        """test_models should invoke dbt test command."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test")
        (project_dir / "target").mkdir()
        (project_dir / "target" / "run_results.json").write_text("{}")

        plugin.test_models(
            project_dir=project_dir,
            profiles_dir=tmp_path,
            target="dev",
        )

        mock_dbt_runner.invoke.assert_called_once()
        call_args = mock_dbt_runner.invoke.call_args[0][0]
        assert "test" in call_args

    @pytest.mark.requirement("FR-004")
    def test_test_models_with_select(
        self, mock_dbt_runner: MagicMock, tmp_path: Path
    ) -> None:
        """test_models should pass select pattern to dbt."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test")
        (project_dir / "target").mkdir()
        (project_dir / "target" / "run_results.json").write_text("{}")

        plugin.test_models(
            project_dir=project_dir,
            profiles_dir=tmp_path,
            target="dev",
            select="test_type:generic",
        )

        call_args = mock_dbt_runner.invoke.call_args[0][0]
        assert "--select" in call_args
        select_idx = call_args.index("--select")
        assert call_args[select_idx + 1] == "test_type:generic"

    @pytest.mark.requirement("FR-004")
    def test_test_models_returns_dbt_run_result(
        self, mock_dbt_runner: MagicMock, tmp_path: Path
    ) -> None:
        """test_models should return DBTRunResult with test counts."""
        from floe_core.plugins.dbt import DBTRunResult

        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test")
        target_dir = project_dir / "target"
        target_dir.mkdir()
        (target_dir / "run_results.json").write_text("{}")
        (target_dir / "manifest.json").write_text("{}")

        result = plugin.test_models(
            project_dir=project_dir,
            profiles_dir=tmp_path,
            target="dev",
        )

        assert isinstance(result, DBTRunResult)
        assert result.success is True


class TestDBTCorePluginCapabilities:
    """Test plugin capability methods."""

    @pytest.mark.requirement("FR-012")
    def test_supports_parallel_execution_returns_false(self) -> None:
        """DBTCorePlugin should NOT support parallel execution.

        dbt-core's dbtRunner is NOT thread-safe. This plugin must
        return False to prevent concurrent execution issues.
        """
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        assert plugin.supports_parallel_execution() is False

    @pytest.mark.requirement("FR-009")
    def test_supports_sql_linting_returns_true(self) -> None:
        """DBTCorePlugin should support SQL linting via SQLFluff."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        assert plugin.supports_sql_linting() is True

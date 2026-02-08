"""Unit tests for DBTFusionPlugin methods.

Tests for the DBTFusionPlugin implementation using mocked subprocess calls.
All tests mock the subprocess execution to avoid requiring actual Fusion CLI.

Requirements:
    FR-017: compile_project() using subprocess
    FR-018: supports_parallel_execution() returning True
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Plugin Metadata Tests
# ---------------------------------------------------------------------------


class TestDBTFusionPluginMetadata:
    """Tests for DBTFusionPlugin metadata properties."""

    @pytest.mark.requirement("FR-017")
    def test_plugin_name_is_fusion(self) -> None:
        """DBTFusionPlugin.name MUST be 'fusion'."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        assert plugin.name == "fusion"

    @pytest.mark.requirement("FR-017")
    def test_plugin_version_exists(self) -> None:
        """DBTFusionPlugin MUST have a version."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        assert plugin.version is not None
        assert isinstance(plugin.version, str)
        # Version should follow semver-like pattern
        assert "." in plugin.version

    @pytest.mark.requirement("FR-017")
    def test_plugin_floe_api_version_exists(self) -> None:
        """DBTFusionPlugin MUST declare floe_api_version."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        assert plugin.floe_api_version is not None
        assert isinstance(plugin.floe_api_version, str)


# ---------------------------------------------------------------------------
# compile_project Tests
# ---------------------------------------------------------------------------


class TestDBTFusionPluginCompileProject:
    """Tests for DBTFusionPlugin.compile_project() method."""

    @pytest.mark.requirement("FR-017")
    def test_compile_project_calls_subprocess(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """compile_project() MUST call subprocess with dbt-sa-cli compile."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            plugin.compile_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
            )

            mock_fusion_cli.assert_called_once()
            call_args = mock_fusion_cli.call_args
            cmd = call_args[0][0]
            assert "dbt-sa-cli" in cmd[0] or "compile" in cmd

    @pytest.mark.requirement("FR-017")
    def test_compile_project_passes_project_dir(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """compile_project() MUST pass --project-dir argument."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            plugin.compile_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
            )

            call_args = mock_fusion_cli.call_args
            cmd = call_args[0][0]
            assert "--project-dir" in cmd
            assert str(temp_dbt_project) in cmd

    @pytest.mark.requirement("FR-017")
    def test_compile_project_passes_profiles_dir(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """compile_project() MUST pass --profiles-dir argument."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        profiles_dir = temp_dbt_project / "profiles"
        profiles_dir.mkdir(exist_ok=True)

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            plugin.compile_project(
                project_dir=temp_dbt_project,
                profiles_dir=profiles_dir,
                target="dev",
            )

            call_args = mock_fusion_cli.call_args
            cmd = call_args[0][0]
            assert "--profiles-dir" in cmd
            assert str(profiles_dir) in cmd

    @pytest.mark.requirement("FR-017")
    def test_compile_project_passes_target(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """compile_project() MUST pass --target argument."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            plugin.compile_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="prod",
            )

            call_args = mock_fusion_cli.call_args
            cmd = call_args[0][0]
            assert "--target" in cmd
            assert "prod" in cmd

    @pytest.mark.requirement("FR-017")
    def test_compile_project_returns_manifest_path(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """compile_project() MUST return path to manifest.json."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        # Create fake manifest
        target_dir = temp_dbt_project / "target"
        target_dir.mkdir(exist_ok=True)
        manifest_path = target_dir / "manifest.json"
        manifest_path.write_text('{"metadata": {}}')

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            result = plugin.compile_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
            )

            assert result == manifest_path
            assert result.name == "manifest.json"

    @pytest.mark.requirement("FR-017")
    def test_compile_project_raises_on_failure(
        self,
        mock_fusion_cli_failure: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """compile_project() MUST raise DBTCompilationError on CLI failure."""
        from floe_dbt_core.errors import DBTCompilationError

        from floe_dbt_fusion.plugin import DBTFusionPlugin

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()

            with pytest.raises(DBTCompilationError):
                plugin.compile_project(
                    project_dir=temp_dbt_project,
                    profiles_dir=temp_dbt_project,
                    target="dev",
                )

    @pytest.mark.requirement("FR-020")
    def test_compile_project_raises_when_fusion_not_found(
        self,
        temp_dbt_project: Path,
    ) -> None:
        """compile_project() MUST raise DBTFusionNotFoundError when CLI missing."""
        from floe_dbt_fusion.errors import DBTFusionNotFoundError
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=None,
        ):
            plugin = DBTFusionPlugin()

            with pytest.raises(DBTFusionNotFoundError):
                plugin.compile_project(
                    project_dir=temp_dbt_project,
                    profiles_dir=temp_dbt_project,
                    target="dev",
                )


# ---------------------------------------------------------------------------
# run_models Tests
# ---------------------------------------------------------------------------


class TestDBTFusionPluginRunModels:
    """Tests for DBTFusionPlugin.run_models() method."""

    @pytest.mark.requirement("FR-017")
    def test_run_models_calls_subprocess(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """run_models() MUST call subprocess with dbt-sa-cli run."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        # Create fake manifest and run_results
        target_dir = temp_dbt_project / "target"
        target_dir.mkdir(exist_ok=True)
        (target_dir / "manifest.json").write_text('{"metadata": {}}')
        (target_dir / "run_results.json").write_text(
            '{"results": [], "elapsed_time": 1.0}'
        )

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            plugin.run_models(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
            )

            mock_fusion_cli.assert_called_once()
            call_args = mock_fusion_cli.call_args
            cmd = call_args[0][0]
            assert "run" in cmd

    @pytest.mark.requirement("FR-017")
    def test_run_models_passes_select(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """run_models() MUST pass --select argument when provided."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        target_dir = temp_dbt_project / "target"
        target_dir.mkdir(exist_ok=True)
        (target_dir / "manifest.json").write_text('{"metadata": {}}')
        (target_dir / "run_results.json").write_text(
            '{"results": [], "elapsed_time": 1.0}'
        )

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            plugin.run_models(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                select="tag:daily",
            )

            call_args = mock_fusion_cli.call_args
            cmd = call_args[0][0]
            assert "--select" in cmd
            assert "tag:daily" in cmd

    @pytest.mark.requirement("FR-017")
    def test_run_models_passes_exclude(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """run_models() MUST pass --exclude argument when provided."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        target_dir = temp_dbt_project / "target"
        target_dir.mkdir(exist_ok=True)
        (target_dir / "manifest.json").write_text('{"metadata": {}}')
        (target_dir / "run_results.json").write_text(
            '{"results": [], "elapsed_time": 1.0}'
        )

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            plugin.run_models(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                exclude="tag:skip",
            )

            call_args = mock_fusion_cli.call_args
            cmd = call_args[0][0]
            assert "--exclude" in cmd
            assert "tag:skip" in cmd

    @pytest.mark.requirement("FR-017")
    def test_run_models_passes_full_refresh(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """run_models() MUST pass --full-refresh when True."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        target_dir = temp_dbt_project / "target"
        target_dir.mkdir(exist_ok=True)
        (target_dir / "manifest.json").write_text('{"metadata": {}}')
        (target_dir / "run_results.json").write_text(
            '{"results": [], "elapsed_time": 1.0}'
        )

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            plugin.run_models(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                full_refresh=True,
            )

            call_args = mock_fusion_cli.call_args
            cmd = call_args[0][0]
            assert "--full-refresh" in cmd

    @pytest.mark.requirement("FR-017")
    def test_run_models_returns_dbt_run_result(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """run_models() MUST return DBTRunResult."""
        from floe_core.plugins.dbt import DBTRunResult

        from floe_dbt_fusion.plugin import DBTFusionPlugin

        target_dir = temp_dbt_project / "target"
        target_dir.mkdir(exist_ok=True)
        (target_dir / "manifest.json").write_text('{"metadata": {}}')
        (target_dir / "run_results.json").write_text(
            '{"results": [{"status": "success"}], "elapsed_time": 1.5}'
        )

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            result = plugin.run_models(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
            )

            assert isinstance(result, DBTRunResult)
            assert result.success is True


# ---------------------------------------------------------------------------
# test_models Tests
# ---------------------------------------------------------------------------


class TestDBTFusionPluginTestModels:
    """Tests for DBTFusionPlugin.test_models() method."""

    @pytest.mark.requirement("FR-017")
    def test_test_models_calls_subprocess(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """test_models() MUST call subprocess with dbt-sa-cli test."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        target_dir = temp_dbt_project / "target"
        target_dir.mkdir(exist_ok=True)
        (target_dir / "manifest.json").write_text('{"metadata": {}}')
        (target_dir / "run_results.json").write_text(
            '{"results": [], "elapsed_time": 1.0}'
        )

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            plugin.test_models(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
            )

            mock_fusion_cli.assert_called_once()
            call_args = mock_fusion_cli.call_args
            cmd = call_args[0][0]
            assert "test" in cmd

    @pytest.mark.requirement("FR-017")
    def test_test_models_passes_select(
        self,
        mock_fusion_cli: MagicMock,
        temp_dbt_project: Path,
    ) -> None:
        """test_models() MUST pass --select when provided."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        target_dir = temp_dbt_project / "target"
        target_dir.mkdir(exist_ok=True)
        (target_dir / "manifest.json").write_text('{"metadata": {}}')
        (target_dir / "run_results.json").write_text(
            '{"results": [], "elapsed_time": 1.0}'
        )

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            plugin.test_models(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                select="test_type:data",
            )

            call_args = mock_fusion_cli.call_args
            cmd = call_args[0][0]
            assert "--select" in cmd
            assert "test_type:data" in cmd


# ---------------------------------------------------------------------------
# Capability Query Tests
# ---------------------------------------------------------------------------


class TestDBTFusionPluginCapabilities:
    """Tests for DBTFusionPlugin capability query methods."""

    @pytest.mark.requirement("FR-018")
    def test_supports_parallel_execution_returns_true(self) -> None:
        """supports_parallel_execution() MUST return True for Fusion."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        result = plugin.supports_parallel_execution()

        # Fusion is Rust-based and thread-safe
        assert result is True

    @pytest.mark.requirement("FR-019")
    def test_supports_sql_linting_returns_true(self) -> None:
        """supports_sql_linting() MUST return True (Fusion has static analysis)."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        result = plugin.supports_sql_linting()

        # Fusion has built-in static analysis
        assert result is True


# ---------------------------------------------------------------------------
# Metadata Tests
# ---------------------------------------------------------------------------


class TestDBTFusionPluginMetadataMethods:
    """Tests for DBTFusionPlugin metadata methods."""

    @pytest.mark.requirement("FR-017")
    def test_get_runtime_metadata_returns_dict(self) -> None:
        """get_runtime_metadata() MUST return dictionary with runtime info."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion",
        ) as mock_detect:
            mock_detect.return_value = MagicMock(
                available=True,
                version="0.1.0",
                adapters_available=["duckdb", "snowflake"],
            )

            plugin = DBTFusionPlugin()
            metadata = plugin.get_runtime_metadata()

            assert isinstance(metadata, dict)
            assert metadata["runtime"] == "fusion"
            assert metadata["thread_safe"] is True

    @pytest.mark.requirement("FR-017")
    def test_get_runtime_metadata_includes_fusion_version(self) -> None:
        """get_runtime_metadata() SHOULD include Fusion version."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion",
        ) as mock_detect:
            mock_detect.return_value = MagicMock(
                available=True,
                version="0.1.0",
                adapters_available=["duckdb", "snowflake"],
            )

            plugin = DBTFusionPlugin()
            metadata = plugin.get_runtime_metadata()

            assert "fusion_version" in metadata
            assert metadata["fusion_version"] == "0.1.0"

    @pytest.mark.requirement("FR-017")
    def test_get_manifest_returns_dict(
        self,
        temp_dbt_project_with_artifacts: Path,
    ) -> None:
        """get_manifest() MUST return parsed manifest.json."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        manifest = plugin.get_manifest(temp_dbt_project_with_artifacts)

        assert isinstance(manifest, dict)
        assert "metadata" in manifest

    @pytest.mark.requirement("FR-017")
    def test_get_manifest_raises_file_not_found(
        self,
        temp_dbt_project: Path,
    ) -> None:
        """get_manifest() MUST raise FileNotFoundError if manifest missing."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        plugin = DBTFusionPlugin()

        with pytest.raises(FileNotFoundError):
            plugin.get_manifest(temp_dbt_project)

    @pytest.mark.requirement("FR-017")
    def test_get_run_results_returns_dict(
        self,
        temp_dbt_project_with_artifacts: Path,
    ) -> None:
        """get_run_results() MUST return parsed run_results.json."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        plugin = DBTFusionPlugin()
        run_results = plugin.get_run_results(temp_dbt_project_with_artifacts)

        assert isinstance(run_results, dict)
        assert "results" in run_results

    @pytest.mark.requirement("FR-017")
    def test_get_run_results_raises_file_not_found(
        self,
        temp_dbt_project: Path,
    ) -> None:
        """get_run_results() MUST raise FileNotFoundError if results missing."""
        from floe_dbt_fusion.plugin import DBTFusionPlugin

        plugin = DBTFusionPlugin()

        with pytest.raises(FileNotFoundError):
            plugin.get_run_results(temp_dbt_project)

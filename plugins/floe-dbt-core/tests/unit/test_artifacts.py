"""Unit tests for DBTCorePlugin artifact methods.

Tests get_manifest and get_run_results methods.

Requirements:
    - FR-006: get_manifest reads target/manifest.json
    - FR-007: get_run_results reads target/run_results.json
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestGetManifest:
    """Test get_manifest method."""

    @pytest.mark.requirement("FR-006")
    def test_get_manifest_returns_dict(self, tmp_path: Path) -> None:
        """get_manifest should return parsed manifest dictionary."""
        from floe_dbt_core import DBTCorePlugin

        # Create project with manifest
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        target_dir = project_dir / "target"
        target_dir.mkdir()

        manifest_data = {
            "metadata": {"dbt_version": "1.7.0"},
            "nodes": {"model.test.example": {"name": "example"}},
        }
        (target_dir / "manifest.json").write_text(json.dumps(manifest_data))

        plugin = DBTCorePlugin()
        result = plugin.get_manifest(project_dir)

        assert isinstance(result, dict)
        assert result["metadata"]["dbt_version"] == "1.7.0"
        assert "model.test.example" in result["nodes"]

    @pytest.mark.requirement("FR-006")
    def test_get_manifest_raises_when_not_found(self, tmp_path: Path) -> None:
        """get_manifest should raise FileNotFoundError when manifest missing."""
        from floe_dbt_core import DBTCorePlugin

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        # No target directory created

        plugin = DBTCorePlugin()

        with pytest.raises(FileNotFoundError):
            plugin.get_manifest(project_dir)

    @pytest.mark.requirement("FR-006")
    def test_get_manifest_from_custom_target_path(self, tmp_path: Path) -> None:
        """get_manifest should read from project_dir/target/manifest.json."""
        from floe_dbt_core import DBTCorePlugin

        # Create nested project structure
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        target_dir = project_dir / "target"
        target_dir.mkdir()

        manifest_data = {"nodes": {}, "metadata": {}}
        (target_dir / "manifest.json").write_text(json.dumps(manifest_data))

        plugin = DBTCorePlugin()
        result = plugin.get_manifest(project_dir)

        assert isinstance(result, dict)
        assert "nodes" in result


class TestGetRunResults:
    """Test get_run_results method."""

    @pytest.mark.requirement("FR-007")
    def test_get_run_results_returns_dict(self, tmp_path: Path) -> None:
        """get_run_results should return parsed run_results dictionary."""
        from floe_dbt_core import DBTCorePlugin

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        target_dir = project_dir / "target"
        target_dir.mkdir()

        run_results_data = {
            "metadata": {"dbt_version": "1.7.0"},
            "results": [
                {"unique_id": "model.test.example", "status": "success"},
            ],
            "elapsed_time": 5.2,
        }
        (target_dir / "run_results.json").write_text(json.dumps(run_results_data))

        plugin = DBTCorePlugin()
        result = plugin.get_run_results(project_dir)

        assert isinstance(result, dict)
        assert result["elapsed_time"] == pytest.approx(5.2)
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "success"

    @pytest.mark.requirement("FR-007")
    def test_get_run_results_raises_when_not_found(self, tmp_path: Path) -> None:
        """get_run_results should raise FileNotFoundError when missing."""
        from floe_dbt_core import DBTCorePlugin

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        # No target directory created

        plugin = DBTCorePlugin()

        with pytest.raises(FileNotFoundError):
            plugin.get_run_results(project_dir)

    @pytest.mark.requirement("FR-007")
    def test_get_run_results_from_correct_path(self, tmp_path: Path) -> None:
        """get_run_results should read from project_dir/target/run_results.json."""
        from floe_dbt_core import DBTCorePlugin

        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        target_dir = project_dir / "target"
        target_dir.mkdir()

        run_results_data = {"results": [], "elapsed_time": 1.0}
        (target_dir / "run_results.json").write_text(json.dumps(run_results_data))

        plugin = DBTCorePlugin()
        result = plugin.get_run_results(project_dir)

        assert isinstance(result, dict)
        assert "results" in result


class TestGetRuntimeMetadata:
    """Test get_runtime_metadata method."""

    @pytest.mark.requirement("FR-010")
    def test_get_runtime_metadata_returns_dict(self) -> None:
        """get_runtime_metadata should return metadata dictionary."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        metadata = plugin.get_runtime_metadata()

        assert isinstance(metadata, dict)

    @pytest.mark.requirement("FR-010")
    def test_get_runtime_metadata_includes_runtime_name(self) -> None:
        """get_runtime_metadata should include runtime identifier."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        metadata = plugin.get_runtime_metadata()

        assert "runtime" in metadata
        assert metadata["runtime"] == "core"

    @pytest.mark.requirement("FR-010")
    def test_get_runtime_metadata_includes_dbt_version(self) -> None:
        """get_runtime_metadata should include dbt version."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()
        metadata = plugin.get_runtime_metadata()

        # Should have dbt_version key
        assert "dbt_version" in metadata
        # Version should be a string like "1.7.0"
        assert isinstance(metadata["dbt_version"], str)

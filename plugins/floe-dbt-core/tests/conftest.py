"""Shared pytest fixtures for floe-dbt-core tests.

This module provides fixtures for testing DBTCorePlugin:
- Mock dbtRunner for unit tests
- Temporary dbt project fixtures
- Common test utilities

Usage:
    def test_compile_project(mock_dbt_runner, temp_dbt_project):
        plugin = DBTCorePlugin()
        plugin.compile_project(temp_dbt_project)
        mock_dbt_runner.invoke.assert_called_once()
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass  # Reserved for future type-only imports


# ---------------------------------------------------------------------------
# dbtRunner Mock Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_dbt_runner() -> Generator[MagicMock, None, None]:
    """Create a mock dbtRunner for unit tests.

    The mock simulates dbt-core's dbtRunner.invoke() behavior.
    Default behavior is a successful run with empty results.

    Yields:
        MagicMock: Configured mock of dbtRunner.

    Example:
        def test_compile(mock_dbt_runner):
            mock_dbt_runner.invoke.return_value.success = True
            plugin = DBTCorePlugin()
            result = plugin.compile_project(Path("project"))
            assert mock_dbt_runner.invoke.called
    """
    mock_runner = MagicMock()

    # Default successful result
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.exception = None
    mock_result.result = []
    mock_runner.invoke.return_value = mock_result

    with patch("dbt.cli.main.dbtRunner", return_value=mock_runner):
        yield mock_runner


@pytest.fixture
def mock_dbt_runner_failure() -> Generator[MagicMock, None, None]:
    """Create a mock dbtRunner that simulates a failure.

    Useful for testing error handling paths.

    Yields:
        MagicMock: Configured mock of dbtRunner that returns failure.

    Example:
        def test_compile_failure(mock_dbt_runner_failure):
            with pytest.raises(DBTCompilationError):
                plugin.compile_project(Path("project"))
    """
    mock_runner = MagicMock()

    # Failed result
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.exception = Exception("Compilation failed: undefined variable 'foo'")
    mock_result.result = []
    mock_runner.invoke.return_value = mock_result

    with patch("dbt.cli.main.dbtRunner", return_value=mock_runner):
        yield mock_runner


# ---------------------------------------------------------------------------
# Temporary dbt Project Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dbt_project(tmp_path: Path) -> Path:
    """Create a minimal temporary dbt project for testing.

    Creates a valid dbt project structure with:
    - dbt_project.yml (project configuration)
    - profiles.yml (DuckDB target)
    - models/example.sql (simple model)

    Args:
        tmp_path: pytest's temporary directory fixture.

    Returns:
        Path to the temporary dbt project directory.

    Example:
        def test_compile(temp_dbt_project):
            plugin = DBTCorePlugin()
            result = plugin.compile_project(temp_dbt_project)
            assert (temp_dbt_project / "target" / "manifest.json").exists()
    """
    project_dir = tmp_path / "test_dbt_project"
    project_dir.mkdir(parents=True)

    # Create dbt_project.yml
    dbt_project = {
        "name": "test_project",
        "version": "1.0.0",
        "config-version": 2,
        "profile": "test_profile",
        "model-paths": ["models"],
        "analysis-paths": ["analyses"],
        "test-paths": ["tests"],
        "seed-paths": ["seeds"],
        "macro-paths": ["macros"],
        "snapshot-paths": ["snapshots"],
        "clean-targets": ["target", "dbt_packages"],
    }
    (project_dir / "dbt_project.yml").write_text(
        "# Test dbt project\n" + _dict_to_yaml(dbt_project)
    )

    # Create profiles.yml with DuckDB target
    profiles = {
        "test_profile": {
            "target": "dev",
            "outputs": {
                "dev": {
                    "type": "duckdb",
                    "path": str(project_dir / "dev.duckdb"),
                    "threads": 1,
                }
            },
        }
    }
    (project_dir / "profiles.yml").write_text(_dict_to_yaml(profiles))

    # Create models directory with example model
    models_dir = project_dir / "models"
    models_dir.mkdir()
    (models_dir / "example.sql").write_text(
        "-- Example model for testing\nSELECT 1 AS id, 'test' AS name\n"
    )

    # Create empty directories
    (project_dir / "tests").mkdir()
    (project_dir / "macros").mkdir()
    (project_dir / "seeds").mkdir()
    (project_dir / "snapshots").mkdir()
    (project_dir / "analyses").mkdir()

    return project_dir


@pytest.fixture
def temp_dbt_project_with_packages(temp_dbt_project: Path) -> Path:
    """Create a dbt project with packages.yml for dependency testing.

    Extends temp_dbt_project with a packages.yml file that declares
    external package dependencies.

    Args:
        temp_dbt_project: Base temporary project fixture.

    Returns:
        Path to the project with packages.yml.
    """
    packages = {
        "packages": [
            {"package": "dbt-labs/dbt_utils", "version": "1.1.1"},
        ]
    }
    (temp_dbt_project / "packages.yml").write_text(_dict_to_yaml(packages))
    return temp_dbt_project


# ---------------------------------------------------------------------------
# Manifest and Artifact Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_manifest() -> dict[str, Any]:
    """Create a sample dbt manifest.json structure.

    Returns:
        Dictionary representing a minimal dbt manifest.

    Example:
        def test_get_manifest(sample_manifest, tmp_path):
            (tmp_path / "target" / "manifest.json").write_text(
                json.dumps(sample_manifest)
            )
            result = plugin.get_manifest(tmp_path)
            assert result["metadata"]["dbt_version"]
    """
    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v10.json",
            "dbt_version": "1.7.0",
            "generated_at": "2026-01-24T00:00:00.000000Z",
            "invocation_id": "test-invocation-id",
            "project_name": "test_project",
            "adapter_type": "duckdb",
        },
        "nodes": {
            "model.test_project.example": {
                "unique_id": "model.test_project.example",
                "resource_type": "model",
                "name": "example",
                "database": "dev",
                "schema": "main",
                "alias": "example",
                "fqn": ["test_project", "example"],
                "path": "example.sql",
                "original_file_path": "models/example.sql",
                "package_name": "test_project",
                "config": {"materialized": "view"},
                "depends_on": {"nodes": [], "macros": []},
            }
        },
        "sources": {},
        "macros": {},
        "docs": {},
        "exposures": {},
        "metrics": {},
        "selectors": {},
        "disabled": {},
    }


@pytest.fixture
def sample_run_results() -> dict[str, Any]:
    """Create a sample dbt run_results.json structure.

    Returns:
        Dictionary representing a minimal dbt run_results.

    Example:
        def test_get_run_results(sample_run_results, tmp_path):
            (tmp_path / "target" / "run_results.json").write_text(
                json.dumps(sample_run_results)
            )
            result = plugin.get_run_results(tmp_path)
            assert result["results"][0]["status"] == "success"
    """
    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/run-results/v5.json",
            "dbt_version": "1.7.0",
            "generated_at": "2026-01-24T00:00:00.000000Z",
            "invocation_id": "test-invocation-id",
        },
        "results": [
            {
                "unique_id": "model.test_project.example",
                "status": "success",
                "timing": [
                    {
                        "name": "compile",
                        "started_at": "2026-01-24T00:00:00Z",
                        "completed_at": "2026-01-24T00:00:01Z",
                    },
                    {
                        "name": "execute",
                        "started_at": "2026-01-24T00:00:01Z",
                        "completed_at": "2026-01-24T00:00:02Z",
                    },
                ],
                "thread_id": "Thread-1",
                "execution_time": 2.0,
                "adapter_response": {"_message": "CREATE VIEW"},
                "message": "CREATE VIEW",
                "failures": None,
            }
        ],
        "elapsed_time": 2.5,
        "args": {},
    }


@pytest.fixture
def temp_dbt_project_with_artifacts(
    temp_dbt_project: Path,
    sample_manifest: dict[str, Any],
    sample_run_results: dict[str, Any],
) -> Path:
    """Create a dbt project with pre-populated target artifacts.

    Useful for testing get_manifest() and get_run_results() methods.

    Args:
        temp_dbt_project: Base temporary project fixture.
        sample_manifest: Sample manifest data.
        sample_run_results: Sample run results data.

    Returns:
        Path to project with target/ directory populated.
    """
    target_dir = temp_dbt_project / "target"
    target_dir.mkdir()

    (target_dir / "manifest.json").write_text(json.dumps(sample_manifest, indent=2))
    (target_dir / "run_results.json").write_text(json.dumps(sample_run_results, indent=2))

    return temp_dbt_project


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------


def _dict_to_yaml(data: dict[str, Any], indent: int = 0) -> str:
    """Convert a dictionary to YAML-like string.

    Simple YAML serializer that doesn't require PyYAML dependency.
    Handles nested dicts and lists for dbt config files.

    Args:
        data: Dictionary to convert.
        indent: Current indentation level.

    Returns:
        YAML-formatted string.
    """
    lines: list[str] = []
    prefix = "  " * indent

    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_dict_to_yaml(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    item_dict: dict[str, Any] = item
                    # First key on same line as -
                    first_key: str = next(iter(item_dict))
                    first_val: Any = item_dict[first_key]
                    lines.append(f"{prefix}  - {first_key}: {_yaml_value(first_val)}")
                    # Rest of keys indented
                    for k, v in list(item_dict.items())[1:]:
                        lines.append(f"{prefix}    {k}: {_yaml_value(v)}")
                else:
                    lines.append(f"{prefix}  - {_yaml_value(item)}")
        else:
            lines.append(f"{prefix}{key}: {_yaml_value(value)}")

    return "\n".join(lines)


def _yaml_value(value: Any) -> str:
    """Format a value for YAML output."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        # Quote strings with special characters
        if any(c in value for c in ":#{}[]&*!|>'\""):
            return f'"{value}"'
        return value
    if value is None:
        return "null"
    return str(value)

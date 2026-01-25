"""Shared pytest fixtures for floe-dbt-fusion tests.

This module provides fixtures for testing DBTFusionPlugin:
- Mock subprocess for CLI invocation tests
- Mock Fusion binary detection
- Temporary dbt project fixtures

Usage:
    def test_compile_project(mock_fusion_cli, temp_dbt_project):
        plugin = DBTFusionPlugin()
        plugin.compile_project(temp_dbt_project)
        mock_fusion_cli.assert_called_once()
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass  # Reserved for future type-only imports


def _generate_unique_project_name(prefix: str = "test_project") -> str:
    """Generate unique project name to prevent test pollution.

    Uses UUID suffix to ensure isolation between parallel test runs.
    """
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Fusion CLI Mock Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_fusion_cli() -> Generator[MagicMock, None, None]:
    """Create a mock subprocess.run for Fusion CLI tests.

    The mock simulates dbt Fusion CLI (dbt-sa-cli) execution.
    Default behavior is a successful run with zero exit code.

    Yields:
        MagicMock: Configured mock of subprocess.run.

    Example:
        def test_compile(mock_fusion_cli):
            plugin = DBTFusionPlugin()
            result = plugin.compile_project(Path("project"))
            assert mock_fusion_cli.called
    """
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"status": "success"}'
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        yield mock_run


@pytest.fixture
def mock_fusion_cli_failure() -> Generator[MagicMock, None, None]:
    """Create a mock subprocess.run that simulates Fusion CLI failure.

    Useful for testing error handling paths.

    Yields:
        MagicMock: Configured mock that returns non-zero exit code.

    Example:
        def test_compile_failure(mock_fusion_cli_failure):
            with pytest.raises(DBTExecutionError):
                plugin.compile_project(Path("project"))
    """
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "Error: Compilation failed at models/dim_customers.sql:15"

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        yield mock_run


@pytest.fixture
def mock_fusion_cli_not_found() -> Generator[MagicMock, None, None]:
    """Create a mock that simulates Fusion CLI binary not found.

    Yields:
        MagicMock: Mock that raises FileNotFoundError.

    Example:
        def test_fusion_not_found(mock_fusion_cli_not_found):
            with pytest.raises(DBTFusionNotFoundError):
                plugin.compile_project(Path("project"))
    """
    with patch(
        "subprocess.run",
        side_effect=FileNotFoundError("dbt-sa-cli not found"),
    ) as mock_run:
        yield mock_run


# ---------------------------------------------------------------------------
# Fusion Binary Detection Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_fusion_binary_exists() -> Generator[MagicMock, None, None]:
    """Mock shutil.which to simulate Fusion binary found in PATH.

    Yields:
        MagicMock: Mock returning path to Fusion binary.
    """
    with patch("shutil.which", return_value="/usr/local/bin/dbt-sa-cli") as mock_which:
        yield mock_which


@pytest.fixture
def mock_fusion_binary_not_found() -> Generator[MagicMock, None, None]:
    """Mock shutil.which to simulate Fusion binary not in PATH.

    Yields:
        MagicMock: Mock returning None (binary not found).
    """
    with patch("shutil.which", return_value=None) as mock_which:
        yield mock_which


@pytest.fixture
def mock_fusion_version() -> Generator[MagicMock, None, None]:
    """Mock Fusion version detection.

    Simulates running `dbt-sa-cli --version` and parsing output.

    Yields:
        MagicMock: Mock returning version string.
    """
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "dbt-sa-cli 0.1.0"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        yield mock_run


# ---------------------------------------------------------------------------
# Adapter Availability Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_adapter_available() -> Generator[MagicMock, None, None]:
    """Mock adapter availability check returning available.

    Simulates checking if a Rust adapter is available for the target.

    Yields:
        MagicMock: Mock for adapter check returning True.
    """
    with patch(
        "floe_dbt_fusion.detection.check_adapter_available",
        return_value=True,
    ) as mock_check:
        yield mock_check


@pytest.fixture
def mock_adapter_unavailable() -> Generator[MagicMock, None, None]:
    """Mock adapter availability check returning unavailable.

    Simulates checking if a Rust adapter is NOT available (e.g., BigQuery).

    Yields:
        MagicMock: Mock for adapter check returning False.
    """
    with patch(
        "floe_dbt_fusion.detection.check_adapter_available",
        return_value=False,
    ) as mock_check:
        yield mock_check


# ---------------------------------------------------------------------------
# Fallback Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_fallback_available() -> Generator[MagicMock, None, None]:
    """Mock floe-dbt-core being available for fallback.

    Yields:
        MagicMock: Mock for importlib.util.find_spec returning a spec.
    """
    mock_spec = MagicMock()
    with patch("importlib.util.find_spec", return_value=mock_spec) as mock_find:
        yield mock_find


@pytest.fixture
def mock_fallback_not_available() -> Generator[MagicMock, None, None]:
    """Mock floe-dbt-core NOT being available for fallback.

    Yields:
        MagicMock: Mock for importlib.util.find_spec returning None.
    """
    with patch("importlib.util.find_spec", return_value=None) as mock_find:
        yield mock_find


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

    Uses unique project name to prevent test pollution.

    Args:
        tmp_path: pytest's temporary directory fixture.

    Returns:
        Path to the temporary dbt project directory.
    """
    project_name = _generate_unique_project_name()
    project_dir = tmp_path / project_name
    project_dir.mkdir(parents=True)

    # Create dbt_project.yml
    dbt_project_content = f"""# Test dbt project
name: {project_name}
version: 1.0.0
config-version: 2
profile: test_profile
model-paths:
  - models
"""
    (project_dir / "dbt_project.yml").write_text(dbt_project_content)

    # Create profiles.yml with DuckDB target
    profiles_content = f"""test_profile:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: {project_dir / "dev.duckdb"}
      threads: 1
"""
    (project_dir / "profiles.yml").write_text(profiles_content)

    # Create models directory with example model
    models_dir = project_dir / "models"
    models_dir.mkdir()
    (models_dir / "example.sql").write_text(
        "-- Example model for testing\nSELECT 1 AS id, 'test' AS name\n"
    )

    # Create target directory (where artifacts go)
    (project_dir / "target").mkdir()

    return project_dir


@pytest.fixture
def temp_dbt_project_with_artifacts(temp_dbt_project: Path) -> Path:
    """Create a dbt project with pre-populated target artifacts.

    Useful for testing get_manifest() and get_run_results() methods.

    Args:
        temp_dbt_project: Base temporary project fixture.

    Returns:
        Path to project with target/ directory populated.
    """
    target_dir = temp_dbt_project / "target"

    manifest = {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v10.json",
            "dbt_version": "1.7.0",
            "project_name": "test_project",
            "adapter_type": "duckdb",
        },
        "nodes": {},
    }

    run_results = {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/run-results/v5.json",
            "dbt_version": "1.7.0",
        },
        "results": [],
        "elapsed_time": 1.0,
    }

    (target_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (target_dir / "run_results.json").write_text(json.dumps(run_results, indent=2))

    return temp_dbt_project


# ---------------------------------------------------------------------------
# CLI Output Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_fusion_compile_output() -> dict[str, Any]:
    """Sample JSON output from Fusion compile command.

    Returns:
        Dictionary representing Fusion CLI compile output.
    """
    return {
        "status": "success",
        "compiled_models": 5,
        "elapsed_time_ms": 150,
        "manifest_path": "target/manifest.json",
    }


@pytest.fixture
def sample_fusion_run_output() -> dict[str, Any]:
    """Sample JSON output from Fusion run command.

    Returns:
        Dictionary representing Fusion CLI run output.
    """
    return {
        "status": "success",
        "models_run": 5,
        "models_success": 5,
        "models_error": 0,
        "elapsed_time_ms": 2500,
    }


@pytest.fixture
def sample_fusion_lint_output() -> dict[str, Any]:
    """Sample JSON output from Fusion static analysis.

    Returns:
        Dictionary representing Fusion CLI lint output.
    """
    return {
        "status": "success",
        "files_analyzed": 10,
        "violations": [
            {
                "file": "models/staging/stg_orders.sql",
                "line": 15,
                "column": 1,
                "rule": "L001",
                "message": "Trailing whitespace",
                "severity": "warning",
            },
            {
                "file": "models/marts/dim_customers.sql",
                "line": 42,
                "column": 5,
                "rule": "L003",
                "message": "Inconsistent indentation",
                "severity": "warning",
            },
        ],
    }

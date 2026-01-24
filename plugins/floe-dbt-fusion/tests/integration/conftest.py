"""Integration test fixtures for floe-dbt-fusion.

This module provides fixtures for integration tests that require
real Fusion CLI execution.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


def skip_if_no_fusion() -> None:
    """Skip test if Fusion CLI not available."""
    if shutil.which("dbt-sa-cli") is None:
        pytest.skip("dbt-sa-cli (Fusion CLI) not found in PATH")


@pytest.fixture
def fusion_available() -> bool:
    """Check if Fusion CLI is available.

    Returns:
        True if dbt-sa-cli is in PATH, False otherwise.
    """
    return shutil.which("dbt-sa-cli") is not None


@pytest.fixture
def temp_dbt_project_for_fusion(tmp_path: Path) -> Path:
    """Create a minimal dbt project for Fusion testing.

    Creates a valid dbt project with DuckDB target (supported by Fusion).

    Args:
        tmp_path: pytest's temporary directory fixture.

    Returns:
        Path to the temporary dbt project directory.
    """
    project_dir = tmp_path / "fusion_test_project"
    project_dir.mkdir(parents=True)

    # Create dbt_project.yml
    dbt_project_content = """# Test dbt project for Fusion
name: fusion_test_project
version: 1.0.0
config-version: 2
profile: fusion_test_profile
model-paths:
  - models
"""
    (project_dir / "dbt_project.yml").write_text(dbt_project_content)

    # Create profiles.yml with DuckDB target (supported by Fusion)
    profiles_content = f"""fusion_test_profile:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: {project_dir / 'dev.duckdb'}
      threads: 1
"""
    (project_dir / "profiles.yml").write_text(profiles_content)

    # Create models directory with example models
    models_dir = project_dir / "models"
    models_dir.mkdir()

    # Simple model
    (models_dir / "example_model.sql").write_text(
        "-- Example model for Fusion testing\n"
        "SELECT 1 AS id, 'test' AS name\n"
    )

    # Another model referencing the first
    (models_dir / "downstream_model.sql").write_text(
        "-- Downstream model\n"
        "SELECT id, name, 'processed' AS status\n"
        "FROM {{ ref('example_model') }}\n"
    )

    # Create target directory (where artifacts go)
    (project_dir / "target").mkdir()

    return project_dir


@pytest.fixture
def temp_dbt_project_with_tests(temp_dbt_project_for_fusion: Path) -> Path:
    """Create a dbt project with test definitions.

    Args:
        temp_dbt_project_for_fusion: Base project fixture.

    Returns:
        Path to project with tests configured.
    """
    models_dir = temp_dbt_project_for_fusion / "models"

    # Create schema.yml with tests
    schema_content = """version: 2

models:
  - name: example_model
    columns:
      - name: id
        tests:
          - not_null
          - unique
      - name: name
        tests:
          - not_null
"""
    (models_dir / "schema.yml").write_text(schema_content)

    return temp_dbt_project_for_fusion


@pytest.fixture
def temp_dbt_project_with_lint_issues(temp_dbt_project_for_fusion: Path) -> Path:
    """Create a dbt project with linting issues.

    Args:
        temp_dbt_project_for_fusion: Base project fixture.

    Returns:
        Path to project with lint issues.
    """
    models_dir = temp_dbt_project_for_fusion / "models"

    # Create model with trailing whitespace and inconsistent indentation
    (models_dir / "lint_issues.sql").write_text(
        "-- Model with lint issues\n"
        "SELECT   \n"  # Trailing whitespace
        "    1 AS id,  \n"  # Trailing whitespace
        "  'test' AS name\n"  # Inconsistent indentation
    )

    return temp_dbt_project_for_fusion

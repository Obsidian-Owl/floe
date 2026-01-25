"""Integration test fixtures for floe-dbt-fusion.

This module provides fixtures for integration tests that require
real Fusion CLI execution.

Note: dbt-fusion is EXPERIMENTAL (no stable releases). Tests may fail
if upstream changes break the build.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest


def _generate_unique_project_name(prefix: str = "fusion_test_project") -> str:
    """Generate unique project name to prevent test pollution.

    Uses UUID suffix to ensure isolation between parallel test runs.
    """
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def pytest_configure(config: pytest.Config) -> None:
    """Register markers for dbt-fusion tests."""
    config.addinivalue_line(
        "markers",
        "experimental: marks tests as experimental (may fail due to upstream changes)",
    )


def require_fusion() -> None:
    """Fail test if Fusion CLI not available.

    Tests FAIL (not skip) when infrastructure missing per testing standards.
    Checks for official Fusion CLI (dbt/dbtf) or legacy dbt-sa-cli.
    """
    from floe_dbt_fusion.detection import detect_fusion_binary

    binary_path = detect_fusion_binary()
    if binary_path is None:
        pytest.fail(
            "dbt Fusion CLI not found in PATH.\n"
            "Install from: https://docs.getdbt.com/docs/fusion/install-fusion-cli\n"
            "Or run: curl -fsSL https://public.cdn.getdbt.com/fs/install/install.sh | sh"
        )


@pytest.fixture
def fusion_available() -> bool:
    """Check if Fusion CLI is available.

    Returns:
        True if dbt Fusion CLI is available, False otherwise.
    """
    from floe_dbt_fusion.detection import detect_fusion_binary

    return detect_fusion_binary() is not None


@pytest.fixture
def temp_dbt_project_for_fusion(tmp_path: Path) -> Path:
    """Create a minimal dbt project for Fusion testing.

    Creates a valid dbt project with DuckDB target (supported by Fusion).
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
    dbt_project_content = f"""# Test dbt project for Fusion
name: {project_name}
version: 1.0.0
config-version: 2
profile: fusion_test_profile
model-paths:
  - models
"""
    (project_dir / "dbt_project.yml").write_text(dbt_project_content)

    # Create profiles.yml with Snowflake target (supported by official Fusion CLI)
    # Uses mock credentials - Fusion can parse but won't connect
    # Note: DuckDB is NOT supported in official Fusion, only in dbt-sa-cli standalone
    profiles_content = """fusion_test_profile:
  target: dev
  outputs:
    dev:
      type: snowflake
      account: test_account_12345
      user: test_user
      password: test_password_placeholder
      role: TEST_ROLE
      warehouse: TEST_WH
      database: TEST_DB
      schema: TEST_SCHEMA
      threads: 1
"""
    (project_dir / "profiles.yml").write_text(profiles_content)

    # Create models directory with example models
    models_dir = project_dir / "models"
    models_dir.mkdir()

    # Simple model
    (models_dir / "example_model.sql").write_text(
        "-- Example model for Fusion testing\nSELECT 1 AS id, 'test' AS name\n"
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

"""DBT-related test fixtures for Dagster integration tests.

This module provides fixtures for testing DBTResource integration:
- Mock DBTPlugin for unit tests
- Mock DBT execution results
- Sample manifest and run_results data

Usage:
    from tests.fixtures.dbt_fixtures import mock_dbt_plugin, sample_manifest

    def test_dbt_resource(mock_dbt_plugin):
        resource = DBTResource(plugin=mock_dbt_plugin)
        result = resource.compile()
        assert result is not None
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Mock DBTPlugin Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_dbt_plugin() -> MagicMock:
    """Create a mock DBTPlugin for unit testing DBTResource.

    Returns a MagicMock that simulates DBTPlugin behavior with default
    successful responses for all methods.

    Returns:
        MagicMock: Configured mock of DBTPlugin.

    Example:
        def test_dbt_resource_compile(mock_dbt_plugin):
            resource = DBTResource(plugin_name="core")
            # Inject mock
            resource._plugin = mock_dbt_plugin
            result = resource.compile(Path("project"))
            mock_dbt_plugin.compile_project.assert_called_once()
    """
    mock_plugin = MagicMock()

    # Metadata
    type(mock_plugin).name = PropertyMock(return_value="mock-dbt")
    type(mock_plugin).version = PropertyMock(return_value="1.0")
    type(mock_plugin).floe_api_version = PropertyMock(return_value="1.0")

    # Default successful method returns
    mock_plugin.compile_project.return_value = Path("target/manifest.json")
    mock_plugin.run_models.return_value = {
        "success": True,
        "models_run": 5,
        "models_success": 5,
        "models_error": 0,
    }
    mock_plugin.test_models.return_value = {
        "success": True,
        "tests_run": 10,
        "tests_passed": 10,
        "tests_failed": 0,
    }
    mock_plugin.lint_project.return_value = {
        "success": True,
        "violations": [],
    }
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
        "dbt_version": "1.7.0",
        "adapter": "duckdb",
    }

    return mock_plugin


@pytest.fixture
def mock_dbt_plugin_failure() -> MagicMock:
    """Create a mock DBTPlugin that simulates failures.

    Returns:
        MagicMock: Mock configured to raise errors on method calls.
    """
    mock_plugin = MagicMock()

    # Metadata
    type(mock_plugin).name = PropertyMock(return_value="mock-dbt")
    type(mock_plugin).version = PropertyMock(return_value="1.0")
    type(mock_plugin).floe_api_version = PropertyMock(return_value="1.0")

    # Configure to raise exceptions
    mock_plugin.compile_project.side_effect = Exception("Compilation failed")
    mock_plugin.run_models.side_effect = Exception("Execution failed")
    mock_plugin.test_models.side_effect = Exception("Tests failed")

    return mock_plugin


@pytest.fixture
def mock_dbt_plugin_parallel() -> MagicMock:
    """Create a mock DBTPlugin that supports parallel execution.

    Simulates DBTFusionPlugin behavior where parallel execution is safe.

    Returns:
        MagicMock: Mock with supports_parallel_execution returning True.
    """
    mock_plugin = MagicMock()

    type(mock_plugin).name = PropertyMock(return_value="mock-fusion")
    type(mock_plugin).version = PropertyMock(return_value="0.1.0")
    type(mock_plugin).floe_api_version = PropertyMock(return_value="1.0")

    mock_plugin.supports_parallel_execution.return_value = True
    mock_plugin.compile_project.return_value = Path("target/manifest.json")
    mock_plugin.run_models.return_value = {"success": True}

    return mock_plugin


# ---------------------------------------------------------------------------
# Sample Data Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_dbt_manifest() -> dict[str, Any]:
    """Sample dbt manifest.json for testing asset creation.

    Returns:
        Dictionary representing a dbt manifest with nodes.
    """
    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v10.json",
            "dbt_version": "1.7.0",
            "generated_at": "2026-01-24T00:00:00.000000Z",
            "project_name": "test_project",
            "adapter_type": "duckdb",
        },
        "nodes": {
            "model.test_project.stg_customers": {
                "unique_id": "model.test_project.stg_customers",
                "resource_type": "model",
                "name": "stg_customers",
                "schema": "staging",
                "fqn": ["test_project", "staging", "stg_customers"],
                "path": "staging/stg_customers.sql",
                "config": {"materialized": "view"},
                "depends_on": {"nodes": [], "macros": []},
            },
            "model.test_project.stg_orders": {
                "unique_id": "model.test_project.stg_orders",
                "resource_type": "model",
                "name": "stg_orders",
                "schema": "staging",
                "fqn": ["test_project", "staging", "stg_orders"],
                "path": "staging/stg_orders.sql",
                "config": {"materialized": "view"},
                "depends_on": {"nodes": [], "macros": []},
            },
            "model.test_project.dim_customers": {
                "unique_id": "model.test_project.dim_customers",
                "resource_type": "model",
                "name": "dim_customers",
                "schema": "marts",
                "fqn": ["test_project", "marts", "dim_customers"],
                "path": "marts/dim_customers.sql",
                "config": {"materialized": "table"},
                "depends_on": {
                    "nodes": ["model.test_project.stg_customers"],
                    "macros": [],
                },
            },
            "model.test_project.fct_orders": {
                "unique_id": "model.test_project.fct_orders",
                "resource_type": "model",
                "name": "fct_orders",
                "schema": "marts",
                "fqn": ["test_project", "marts", "fct_orders"],
                "path": "marts/fct_orders.sql",
                "config": {"materialized": "table"},
                "depends_on": {
                    "nodes": [
                        "model.test_project.stg_orders",
                        "model.test_project.dim_customers",
                    ],
                    "macros": [],
                },
            },
        },
        "sources": {},
        "metrics": {},
        "exposures": {},
    }


@pytest.fixture
def sample_dbt_run_results() -> dict[str, Any]:
    """Sample dbt run_results.json for testing execution results.

    Returns:
        Dictionary representing dbt run results.
    """
    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/run-results/v5.json",
            "dbt_version": "1.7.0",
            "generated_at": "2026-01-24T00:00:00.000000Z",
        },
        "results": [
            {
                "unique_id": "model.test_project.stg_customers",
                "status": "success",
                "execution_time": 0.5,
                "adapter_response": {"_message": "CREATE VIEW"},
            },
            {
                "unique_id": "model.test_project.stg_orders",
                "status": "success",
                "execution_time": 0.6,
                "adapter_response": {"_message": "CREATE VIEW"},
            },
            {
                "unique_id": "model.test_project.dim_customers",
                "status": "success",
                "execution_time": 1.2,
                "adapter_response": {"_message": "CREATE TABLE"},
            },
            {
                "unique_id": "model.test_project.fct_orders",
                "status": "success",
                "execution_time": 1.5,
                "adapter_response": {"_message": "CREATE TABLE"},
            },
        ],
        "elapsed_time": 4.5,
        "args": {"select": [], "exclude": []},
    }


@pytest.fixture
def sample_lint_violations() -> list[dict[str, Any]]:
    """Sample SQLFluff lint violations for testing lint results.

    Returns:
        List of lint violation dictionaries.
    """
    return [
        {
            "file_path": "models/staging/stg_orders.sql",
            "line_number": 15,
            "column_number": 1,
            "code": "L001",
            "description": "Trailing whitespace",
            "severity": "warning",
        },
        {
            "file_path": "models/marts/dim_customers.sql",
            "line_number": 42,
            "column_number": 5,
            "code": "L003",
            "description": "Inconsistent indentation",
            "severity": "warning",
        },
        {
            "file_path": "models/marts/fct_orders.sql",
            "line_number": 100,
            "column_number": 10,
            "code": "L044",
            "description": "Query produces columns not in SELECT",
            "severity": "error",
        },
    ]


# ---------------------------------------------------------------------------
# Temporary Project Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dagster_dbt_project(tmp_path: Path) -> Path:
    """Create a temporary dbt project for Dagster integration testing.

    Creates a valid dbt project structure that can be used with
    Dagster's dbt integration.

    Args:
        tmp_path: pytest's temporary directory fixture.

    Returns:
        Path to the temporary project directory.
    """
    project_dir = tmp_path / "dagster_dbt_project"
    project_dir.mkdir(parents=True)

    # Create dbt_project.yml
    dbt_project = {
        "name": "dagster_test_project",
        "version": "1.0.0",
        "config-version": 2,
        "profile": "dagster_profile",
        "model-paths": ["models"],
    }
    (project_dir / "dbt_project.yml").write_text(_simple_yaml(dbt_project))

    # Create profiles.yml
    profiles = {
        "dagster_profile": {
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
    (project_dir / "profiles.yml").write_text(_simple_yaml(profiles))

    # Create models directory
    models_dir = project_dir / "models"
    models_dir.mkdir()

    # Create staging models
    staging_dir = models_dir / "staging"
    staging_dir.mkdir()
    (staging_dir / "stg_customers.sql").write_text(
        "SELECT 1 AS customer_id, 'Test Customer' AS name"
    )
    (staging_dir / "stg_orders.sql").write_text(
        "SELECT 1 AS order_id, 1 AS customer_id, 100.00 AS amount"
    )

    # Create marts models
    marts_dir = models_dir / "marts"
    marts_dir.mkdir()
    (marts_dir / "dim_customers.sql").write_text(
        "SELECT * FROM {{ ref('stg_customers') }}"
    )
    (marts_dir / "fct_orders.sql").write_text(
        "SELECT o.*, c.name AS customer_name\n"
        "FROM {{ ref('stg_orders') }} o\n"
        "JOIN {{ ref('dim_customers') }} c ON o.customer_id = c.customer_id"
    )

    # Create target directory
    (project_dir / "target").mkdir()

    return project_dir


def _simple_yaml(data: dict[str, Any]) -> str:
    """Convert dictionary to simple YAML string.

    Only handles the basic structures needed for dbt config files.
    """
    lines: list[str] = []

    def _render(obj: Any, indent: int = 0) -> None:
        prefix = "  " * indent
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, dict | list):
                    lines.append(f"{prefix}{key}:")
                    _render(value, indent + 1)
                else:
                    lines.append(f"{prefix}{key}: {_format_value(value)}")
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    lines.append(f"{prefix}-")
                    _render(item, indent + 1)
                else:
                    lines.append(f"{prefix}- {_format_value(item)}")

    def _format_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return value
        if value is None:
            return "null"
        return str(value)

    _render(data)
    return "\n".join(lines)

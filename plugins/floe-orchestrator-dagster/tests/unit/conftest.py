"""Unit test fixtures for floe-orchestrator-dagster.

Unit tests use mocks and don't require external services.

Fixtures:
    dagster_plugin: Fresh DagsterOrchestratorPlugin instance
    valid_compiled_artifacts: Minimal valid CompiledArtifacts dict
    valid_compiled_artifacts_with_models: CompiledArtifacts with dependency graph
    invalid_compiled_artifacts_missing_metadata: Invalid artifacts for error testing
    invalid_compiled_artifacts_missing_identity: Invalid artifacts for error testing
    sample_transform_config: Single TransformConfig instance
    sample_transform_configs: List of TransformConfigs with dependencies
    sample_dataset: Dataset for lineage testing
    mock_httpx_success_response: Mock successful HTTP response
    mock_httpx_error_response: Mock HTTP error response

Requirements:
    NFR-003: Unit test coverage and mock fixtures
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


@pytest.fixture
def dagster_plugin() -> DagsterOrchestratorPlugin:
    """Create a DagsterOrchestratorPlugin instance for testing."""
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    return DagsterOrchestratorPlugin()


@pytest.fixture
def valid_compiled_artifacts() -> dict[str, Any]:
    """Create a valid CompiledArtifacts dict for testing.

    This fixture provides a minimal valid CompiledArtifacts dictionary
    that passes Pydantic validation.
    """
    return {
        "version": "0.3.0",
        "metadata": {
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "floe_version": "0.3.0",
            "source_hash": "sha256:abc123def456",
            "product_name": "test-pipeline",
            "product_version": "1.0.0",
        },
        "identity": {
            "product_id": "default.test_pipeline",
            "domain": "default",
            "repository": "github.com/test/test-pipeline",
        },
        "mode": "simple",
        "observability": {
            "telemetry": {
                "enabled": True,
                "resource_attributes": {
                    "service_name": "test-pipeline",
                    "service_version": "1.0.0",
                    "deployment_environment": "dev",
                    "floe_namespace": "default",
                    "floe_product_name": "test-pipeline",
                    "floe_product_version": "1.0.0",
                    "floe_mode": "dev",
                },
            },
            "lineage": True,
            "lineage_namespace": "test-pipeline",
        },
        "plugins": {
            "compute": {"type": "duckdb", "version": "0.9.0"},
            "orchestrator": {"type": "dagster", "version": "1.5.0"},
        },
        "transforms": {
            "models": [
                {"name": "stg_customers", "compute": "duckdb"},
            ],
            "default_compute": "duckdb",
        },
    }


@pytest.fixture
def valid_compiled_artifacts_with_models() -> dict[str, Any]:
    """Create a valid CompiledArtifacts dict with multiple models.

    This fixture provides a CompiledArtifacts dictionary with multiple
    models that have dependencies between them.
    """
    return {
        "version": "0.3.0",
        "metadata": {
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "floe_version": "0.3.0",
            "source_hash": "sha256:abc123def456",
            "product_name": "test-pipeline",
            "product_version": "1.0.0",
        },
        "identity": {
            "product_id": "default.test_pipeline",
            "domain": "default",
            "repository": "github.com/test/test-pipeline",
        },
        "mode": "simple",
        "observability": {
            "telemetry": {
                "enabled": True,
                "resource_attributes": {
                    "service_name": "test-pipeline",
                    "service_version": "1.0.0",
                    "deployment_environment": "dev",
                    "floe_namespace": "default",
                    "floe_product_name": "test-pipeline",
                    "floe_product_version": "1.0.0",
                    "floe_mode": "dev",
                },
            },
            "lineage": True,
            "lineage_namespace": "test-pipeline",
        },
        "plugins": {
            "compute": {"type": "duckdb", "version": "0.9.0"},
            "orchestrator": {"type": "dagster", "version": "1.5.0"},
        },
        "transforms": {
            "models": [
                {"name": "raw_customers", "compute": "duckdb"},
                {
                    "name": "stg_customers",
                    "compute": "duckdb",
                    "depends_on": ["raw_customers"],
                },
                {
                    "name": "dim_customers",
                    "compute": "duckdb",
                    "tags": ["core"],
                    "depends_on": ["stg_customers"],
                },
            ],
            "default_compute": "duckdb",
        },
    }


@pytest.fixture
def sample_transform_config() -> Any:
    """Create a sample TransformConfig for testing."""
    from floe_core.plugins.orchestrator import TransformConfig

    return TransformConfig(
        name="stg_customers",
        path="models/staging/stg_customers.sql",
        schema_name="staging",
        materialization="view",
        tags=["daily", "core"],
        depends_on=["raw_customers"],
        compute="duckdb",
    )


@pytest.fixture
def sample_transform_configs() -> list[Any]:
    """Create a list of sample TransformConfigs with dependencies."""
    from floe_core.plugins.orchestrator import TransformConfig

    return [
        TransformConfig(
            name="raw_customers",
            path="models/raw/raw_customers.sql",
            schema_name="raw",
            materialization="table",
        ),
        TransformConfig(
            name="stg_customers",
            path="models/staging/stg_customers.sql",
            schema_name="staging",
            materialization="view",
            depends_on=["raw_customers"],
        ),
        TransformConfig(
            name="dim_customers",
            path="models/marts/dim_customers.sql",
            schema_name="marts",
            materialization="table",
            depends_on=["stg_customers"],
            tags=["core"],
        ),
    ]


@pytest.fixture
def sample_dataset() -> Any:
    """Create a sample Dataset for lineage testing."""
    from floe_core.plugins.orchestrator import Dataset

    return Dataset(
        namespace="floe-test",
        name="staging.stg_customers",
        facets={"schema": {"fields": [{"name": "id", "type": "INTEGER"}]}},
    )


@pytest.fixture
def invalid_compiled_artifacts_missing_metadata() -> dict[str, Any]:
    """Create invalid CompiledArtifacts missing metadata field.

    Use this fixture to test validation error handling.
    """
    return {
        "version": "0.3.0",
        # metadata is missing - should trigger validation error
        "identity": {
            "product_id": "default.test_pipeline",
            "domain": "default",
            "repository": "github.com/test/test-pipeline",
        },
        "mode": "simple",
        "observability": {
            "telemetry": {"enabled": False},
            "lineage": False,
        },
        "plugins": {
            "compute": {"type": "duckdb", "version": "0.9.0"},
            "orchestrator": {"type": "dagster", "version": "1.5.0"},
        },
        "transforms": {"models": [], "default_compute": "duckdb"},
    }


@pytest.fixture
def invalid_compiled_artifacts_missing_identity() -> dict[str, Any]:
    """Create invalid CompiledArtifacts missing identity field.

    Use this fixture to test validation error handling.
    """
    return {
        "version": "0.3.0",
        "metadata": {
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "floe_version": "0.3.0",
            "source_hash": "sha256:abc123def456",
            "product_name": "test-pipeline",
            "product_version": "1.0.0",
        },
        # identity is missing - should trigger validation error
        "mode": "simple",
        "observability": {
            "telemetry": {"enabled": False},
            "lineage": False,
        },
        "plugins": {
            "compute": {"type": "duckdb", "version": "0.9.0"},
            "orchestrator": {"type": "dagster", "version": "1.5.0"},
        },
        "transforms": {"models": [], "default_compute": "duckdb"},
    }


@pytest.fixture
def mock_httpx_success_response() -> MagicMock:
    """Create a mock successful HTTP response for validate_connection tests.

    Returns a mock response with status_code 200.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"__typename": "Query"}}
    return mock_response


@pytest.fixture
def mock_httpx_error_response() -> MagicMock:
    """Create a mock HTTP error response for validate_connection tests.

    Returns a mock response with status_code 500.
    """
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    return mock_response


@pytest.fixture
def mock_httpx_client(mock_httpx_success_response: MagicMock) -> MagicMock:
    """Create a mock httpx.Client for validate_connection tests.

    The mock client is configured as a context manager that returns
    the success response by default.

    Args:
        mock_httpx_success_response: The mock response to return.

    Returns:
        MagicMock configured as httpx.Client context manager.
    """
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_httpx_success_response
    return mock_client

"""Unit test fixtures for floe-orchestrator-dagster.

Unit tests use mocks and don't require external services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


@pytest.fixture
def dagster_plugin() -> DagsterOrchestratorPlugin:
    """Create a DagsterOrchestratorPlugin instance for testing."""
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    return DagsterOrchestratorPlugin()


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

"""Semantic layer pytest fixtures for unit and integration tests.

Provides fixtures for CubeSemanticPlugin testing including configuration,
plugin instances, sample dbt manifests, and temporary output directories.

Example:
    from testing.fixtures.semantic import cube_config, cube_plugin

    def test_with_cube(cube_plugin):
        assert cube_plugin.name == "cube"

Requirements Covered:
    - FR-051: Test fixtures for semantic layer
    - FR-052: Sample dbt manifest fixture
    - FR-053: Temporary output directory fixture
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from floe_semantic_cube.config import CubeSemanticConfig
from floe_semantic_cube.plugin import CubeSemanticPlugin
from pydantic import SecretStr


def _semantic_meta(**semantic: Any) -> dict[str, Any]:
    """Wrap semantic publication metadata in the dbt meta namespace."""
    return {"floe": {"semantic": semantic}}


def _manifest_column(
    name: str,
    data_type: str,
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a dbt manifest column entry."""
    return {"name": name, "data_type": data_type, "meta": meta or {}}


def customer_360_semantic_manifest() -> dict[str, Any]:
    """Build a Customer 360 dbt manifest with explicit semantic publication.

    The fixture intentionally includes sensitive and unannotated columns to
    prove Cube schema generation is deny-by-default.
    """
    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12/manifest.json",
            "dbt_version": "1.9.0",
            "generated_at": "2026-01-01T00:00:00Z",
        },
        "nodes": {
            "model.analytics.mart_customer_360": {
                "unique_id": "model.analytics.mart_customer_360",
                "resource_type": "model",
                "name": "mart_customer_360",
                "schema": "gold",
                "database": "analytics",
                "depends_on": {"nodes": []},
                "columns": {
                    "customer_id": _manifest_column("customer_id", "integer"),
                    "lifetime_value": _manifest_column("lifetime_value", "decimal"),
                    "is_active": _manifest_column("is_active", "boolean"),
                    "segment": _manifest_column("segment", "varchar"),
                    "signup_date": _manifest_column("signup_date", "date"),
                    "email": _manifest_column(
                        "email",
                        "varchar",
                        meta={"sensitive": True},
                    ),
                    "phone": _manifest_column(
                        "phone",
                        "varchar",
                        meta={"sensitive": True},
                    ),
                    "address": _manifest_column(
                        "address",
                        "varchar",
                        meta={"masking_policy": "mask_address"},
                    ),
                    "ssn_hash": _manifest_column(
                        "ssn_hash",
                        "varchar",
                        meta={"sensitive": True},
                    ),
                    "internal_risk_score": _manifest_column(
                        "internal_risk_score",
                        "decimal",
                    ),
                },
                "meta": _semantic_meta(
                    publish=True,
                    measures={
                        "total_lifetime_value": {
                            "source": "lifetime_value",
                            "type": "sum",
                        },
                        "active_customer_count": {
                            "source": "customer_id",
                            "type": "count_distinct",
                            "filters": [{"sql": "{CUBE}.is_active = true"}],
                        },
                    },
                    dimensions={
                        "customer_segment": {
                            "source": "segment",
                            "type": "string",
                        }
                    },
                    time_dimensions={
                        "signup_date": {
                            "source": "signup_date",
                            "granularities": ["day", "month"],
                        }
                    },
                    validation_metrics=["total_lifetime_value", "active_customer_count"],
                ),
                "tags": ["analytics", "semantic"],
                "config": {"materialized": "table"},
            },
        },
    }


@pytest.fixture(scope="session")
def cube_config() -> CubeSemanticConfig:
    """Session-scoped CubeSemanticConfig for testing.

    Returns:
        CubeSemanticConfig with test defaults.
    """
    return CubeSemanticConfig(
        server_url="http://localhost:4000",
        api_secret=SecretStr("test-secret"),
        database_name="test_analytics",
    )


@pytest.fixture
def cube_plugin(
    cube_config: CubeSemanticConfig,
) -> Generator[CubeSemanticPlugin, None, None]:
    """Function-scoped CubeSemanticPlugin instance.

    Creates a plugin, runs startup, yields it, then runs shutdown.

    Args:
        cube_config: Session-scoped configuration.

    Yields:
        Started CubeSemanticPlugin instance.
    """
    plugin = CubeSemanticPlugin(config=cube_config)
    plugin.startup()
    yield plugin
    plugin.shutdown()


@pytest.fixture
def sample_dbt_manifest(tmp_path: Path) -> Path:
    """Create a sample dbt manifest.json with 3 models.

    The manifest follows the dbt manifest v12 schema with three models:
    - customers: Basic customer dimension table
    - orders: Published order fact table with explicit semantic metadata
    - order_items: Detail table with foreign key relationships

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Path to the generated manifest.json file.
    """
    manifest: dict[str, Any] = {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12/manifest.json",
            "dbt_version": "1.9.0",
            "generated_at": "2026-01-01T00:00:00Z",
        },
        "nodes": {
            "model.analytics.customers": {
                "unique_id": "model.analytics.customers",
                "resource_type": "model",
                "name": "customers",
                "schema": "gold",
                "database": "analytics",
                "depends_on": {"nodes": []},
                "columns": {
                    "customer_id": {
                        "name": "customer_id",
                        "data_type": "integer",
                        "meta": {},
                    },
                    "customer_name": {
                        "name": "customer_name",
                        "data_type": "varchar",
                        "meta": {},
                    },
                    "email": {
                        "name": "email",
                        "data_type": "varchar",
                        "meta": {},
                    },
                    "created_at": {
                        "name": "created_at",
                        "data_type": "timestamp",
                        "meta": {},
                    },
                },
                "meta": {},
                "tags": ["analytics"],
                "config": {"materialized": "table"},
            },
            "model.analytics.orders": {
                "unique_id": "model.analytics.orders",
                "resource_type": "model",
                "name": "orders",
                "schema": "gold",
                "database": "analytics",
                "depends_on": {
                    "nodes": ["model.analytics.customers"],
                },
                "columns": {
                    "order_id": {
                        "name": "order_id",
                        "data_type": "integer",
                        "meta": {},
                    },
                    "customer_id": {
                        "name": "customer_id",
                        "data_type": "integer",
                        "meta": {},
                    },
                    "order_total": {
                        "name": "order_total",
                        "data_type": "decimal",
                        "meta": {},
                    },
                    "order_date": {
                        "name": "order_date",
                        "data_type": "date",
                        "meta": {},
                    },
                    "status": {
                        "name": "status",
                        "data_type": "varchar",
                        "meta": {},
                    },
                },
                "meta": _semantic_meta(
                    publish=True,
                    measures={
                        "total_order_amount": {
                            "source": "order_total",
                            "type": "sum",
                        }
                    },
                    dimensions={
                        "order_status": {
                            "source": "status",
                            "type": "string",
                        }
                    },
                    time_dimensions={
                        "order_date": {
                            "source": "order_date",
                            "granularities": ["day", "month"],
                        }
                    },
                    validation_metrics=["total_order_amount"],
                ),
                "tags": ["analytics", "cube"],
                "config": {"materialized": "table"},
            },
            "model.analytics.order_items": {
                "unique_id": "model.analytics.order_items",
                "resource_type": "model",
                "name": "order_items",
                "schema": "gold",
                "database": "analytics",
                "depends_on": {
                    "nodes": [
                        "model.analytics.orders",
                        "model.analytics.customers",
                    ],
                },
                "columns": {
                    "item_id": {
                        "name": "item_id",
                        "data_type": "integer",
                        "meta": {},
                    },
                    "order_id": {
                        "name": "order_id",
                        "data_type": "integer",
                        "meta": {},
                    },
                    "quantity": {
                        "name": "quantity",
                        "data_type": "integer",
                        "meta": {},
                    },
                    "unit_price": {
                        "name": "unit_price",
                        "data_type": "decimal",
                        "meta": {},
                    },
                },
                "meta": {},
                "tags": ["analytics"],
                "config": {"materialized": "table"},
            },
        },
    }

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest_path


@pytest.fixture
def cube_output_dir(tmp_path: Path) -> Path:
    """Temporary directory for Cube schema YAML output.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Path to a clean output directory for generated schemas.
    """
    output_dir = tmp_path / "cube_schemas"
    output_dir.mkdir()
    return output_dir

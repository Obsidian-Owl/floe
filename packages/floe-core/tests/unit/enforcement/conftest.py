"""Unit test fixtures for the policy enforcement module.

This module provides fixtures specific to enforcement unit tests, which:
- Run without external services (no K8s, no databases)
- Use mocks/fakes for all plugin dependencies
- Execute quickly (< 1s per test)

Task: T004
Requirements: FR-001 (PolicyEnforcer), US1-US7 (All user stories)

For shared fixtures across all test tiers, see ../conftest.py.

Fixtures provided:
- sample_dbt_manifest: Minimal valid dbt manifest.json structure
- sample_governance_config: Default GovernanceConfig for testing
- sample_naming_config: Default NamingConfig for testing
- sample_quality_gates_config: Default QualityGatesConfig for testing
- medallion_compliant_models: List of model names following medallion convention
- medallion_violating_models: List of model names violating medallion convention
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from floe_core.schemas.manifest import GovernanceConfig


@pytest.fixture
def sample_dbt_manifest() -> dict[str, Any]:
    """Provide a minimal valid dbt manifest.json structure for testing.

    This fixture provides a simplified dbt manifest with the essential
    structure needed for policy enforcement validation.

    Returns:
        Dict containing minimal dbt manifest structure with nodes.
    """
    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json",
            "dbt_version": "1.8.0",
            "project_name": "test_project",
            "project_id": "test-project-id",
            "send_anonymous_usage_stats": False,
        },
        "nodes": {
            "model.test_project.bronze_customers": {
                "name": "bronze_customers",
                "resource_type": "model",
                "package_name": "test_project",
                "path": "bronze/bronze_customers.sql",
                "original_file_path": "models/bronze/bronze_customers.sql",
                "unique_id": "model.test_project.bronze_customers",
                "fqn": ["test_project", "bronze", "bronze_customers"],
                "alias": "bronze_customers",
                "description": "Raw customer data from source system",
                "columns": {
                    "id": {
                        "name": "id",
                        "description": "Primary key",
                        "data_type": "integer",
                    },
                    "email": {
                        "name": "email",
                        "description": "Customer email address",
                        "data_type": "varchar",
                    },
                    "created_at": {
                        "name": "created_at",
                        "description": "Record creation timestamp",
                        "data_type": "timestamp",
                    },
                },
                "meta": {},
                "config": {"materialized": "view"},
            },
            "model.test_project.silver_customers": {
                "name": "silver_customers",
                "resource_type": "model",
                "package_name": "test_project",
                "path": "silver/silver_customers.sql",
                "original_file_path": "models/silver/silver_customers.sql",
                "unique_id": "model.test_project.silver_customers",
                "fqn": ["test_project", "silver", "silver_customers"],
                "alias": "silver_customers",
                "description": "Cleaned customer data",
                "columns": {
                    "customer_id": {
                        "name": "customer_id",
                        "description": "Customer unique identifier",
                        "data_type": "integer",
                    },
                    "email": {
                        "name": "email",
                        "description": "Validated email address",
                        "data_type": "varchar",
                    },
                },
                "meta": {},
                "config": {"materialized": "table"},
            },
        },
        "sources": {},
        "macros": {},
        "docs": {},
        "exposures": {},
        "metrics": {},
        "groups": {},
        "selectors": {},
        "disabled": {},
        "parent_map": {
            "model.test_project.silver_customers": ["model.test_project.bronze_customers"],
        },
        "child_map": {
            "model.test_project.bronze_customers": ["model.test_project.silver_customers"],
        },
    }


@pytest.fixture
def sample_dbt_manifest_with_tests(
    sample_dbt_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Provide a dbt manifest with test nodes for coverage validation.

    This extends the base manifest with test nodes that reference columns,
    enabling test coverage calculation.

    Args:
        sample_dbt_manifest: Base manifest fixture.

    Returns:
        Dict containing dbt manifest with test nodes.
    """
    manifest = sample_dbt_manifest.copy()
    manifest["nodes"] = manifest["nodes"].copy()

    # Add test nodes
    manifest["nodes"]["test.test_project.not_null_bronze_customers_id"] = {
        "name": "not_null_bronze_customers_id",
        "resource_type": "test",
        "package_name": "test_project",
        "unique_id": "test.test_project.not_null_bronze_customers_id",
        "test_metadata": {
            "name": "not_null",
            "kwargs": {"column_name": "id"},
        },
        "attached_node": "model.test_project.bronze_customers",
        "column_name": "id",
    }
    manifest["nodes"]["test.test_project.unique_bronze_customers_id"] = {
        "name": "unique_bronze_customers_id",
        "resource_type": "test",
        "package_name": "test_project",
        "unique_id": "test.test_project.unique_bronze_customers_id",
        "test_metadata": {
            "name": "unique",
            "kwargs": {"column_name": "id"},
        },
        "attached_node": "model.test_project.bronze_customers",
        "column_name": "id",
    }

    # Update child_map to include tests
    manifest["child_map"]["model.test_project.bronze_customers"] = [
        "model.test_project.silver_customers",
        "test.test_project.not_null_bronze_customers_id",
        "test.test_project.unique_bronze_customers_id",
    ]

    return manifest


@pytest.fixture
def medallion_compliant_models() -> list[str]:
    """Provide model names that comply with medallion naming convention.

    Returns:
        List of valid medallion-compliant model names.
    """
    return [
        "bronze_customers",
        "bronze_orders",
        "bronze_products",
        "silver_customers",
        "silver_orders",
        "silver_products",
        "gold_revenue",
        "gold_customer_ltv",
        "gold_daily_metrics",
    ]


@pytest.fixture
def medallion_violating_models() -> list[str]:
    """Provide model names that violate medallion naming convention.

    Returns:
        List of model names that fail medallion pattern validation.
    """
    return [
        "stg_customers",  # staging prefix
        "dim_customer",  # kimball prefix
        "fact_orders",  # kimball prefix
        "customers",  # no prefix
        "raw_orders",  # raw prefix (not medallion)
        "int_orders",  # intermediate prefix
        "Bronze_Customers",  # wrong case
        "bronze-customers",  # wrong separator
    ]


@pytest.fixture
def kimball_compliant_models() -> list[str]:
    """Provide model names that comply with kimball naming convention.

    Returns:
        List of valid kimball-compliant model names.
    """
    return [
        "dim_customer",
        "dim_product",
        "dim_date",
        "fact_orders",
        "fact_sales",
        "fact_inventory",
        "bridge_order_product",
        "bridge_customer_account",
    ]


@pytest.fixture
def model_without_description() -> dict[str, Any]:
    """Provide a model node missing its description.

    Returns:
        Dict containing a model node with empty description.
    """
    return {
        "name": "bronze_missing_desc",
        "resource_type": "model",
        "package_name": "test_project",
        "unique_id": "model.test_project.bronze_missing_desc",
        "description": "",  # Empty description
        "columns": {
            "id": {
                "name": "id",
                "description": "Primary key",
                "data_type": "integer",
            },
        },
        "meta": {},
    }


@pytest.fixture
def model_with_placeholder_description() -> dict[str, Any]:
    """Provide a model node with placeholder description.

    Returns:
        Dict containing a model node with TBD/TODO description.
    """
    return {
        "name": "bronze_placeholder_desc",
        "resource_type": "model",
        "package_name": "test_project",
        "unique_id": "model.test_project.bronze_placeholder_desc",
        "description": "TBD - needs description",  # Placeholder
        "columns": {
            "id": {
                "name": "id",
                "description": "TODO",  # Placeholder column description
                "data_type": "integer",
            },
        },
        "meta": {},
    }


# =========================================================================
# Dry-Run Test Fixtures (T080 - Test Duplication Reduction)
# =========================================================================


@pytest.fixture
def strict_naming_governance_config() -> GovernanceConfig:
    """Provide strict governance config with medallion naming enforcement.

    Returns:
        GovernanceConfig with strict naming policy.
    """
    from floe_core.schemas.governance import NamingConfig
    from floe_core.schemas.manifest import GovernanceConfig

    return GovernanceConfig(
        policy_enforcement_level="strict",
        naming=NamingConfig(
            pattern="medallion",
            enforcement="strict",
        ),
    )


@pytest.fixture
def strict_multi_policy_governance_config() -> GovernanceConfig:
    """Provide strict governance config with multiple policy types.

    Returns:
        GovernanceConfig with naming and quality gates enforcement.
    """
    from floe_core.schemas.governance import NamingConfig, QualityGatesConfig
    from floe_core.schemas.manifest import GovernanceConfig

    return GovernanceConfig(
        policy_enforcement_level="strict",
        naming=NamingConfig(
            pattern="medallion",
            enforcement="strict",
        ),
        quality_gates=QualityGatesConfig(
            require_descriptions=True,
        ),
    )


@pytest.fixture
def dbt_manifest_with_naming_violation() -> dict[str, Any]:
    """Provide dbt manifest with a medallion naming violation.

    Returns:
        Dict containing dbt manifest with invalid model name.
    """
    return {
        "metadata": {"dbt_version": "1.8.0"},
        "nodes": {
            "model.my_project.bad_model_name": {
                "name": "bad_model_name",
                "resource_type": "model",
                "columns": {},
            },
        },
    }


@pytest.fixture
def dbt_manifest_with_multi_violations() -> dict[str, Any]:
    """Provide dbt manifest with naming and documentation violations.

    Returns:
        Dict containing dbt manifest with multiple violation types.
    """
    return {
        "metadata": {"dbt_version": "1.8.0"},
        "nodes": {
            "model.my_project.bad_model_name": {
                "name": "bad_model_name",
                "resource_type": "model",
                "description": "",  # Documentation violation
                "columns": {},
            },
        },
    }


@pytest.fixture
def dbt_manifest_compliant() -> dict[str, Any]:
    """Provide dbt manifest that is fully compliant with medallion naming.

    Returns:
        Dict containing dbt manifest with valid model names.
    """
    return {
        "metadata": {"dbt_version": "1.8.0"},
        "nodes": {
            "model.my_project.bronze_orders": {
                "name": "bronze_orders",
                "resource_type": "model",
                "description": "Raw order data from source system",
                "columns": {},
            },
        },
    }

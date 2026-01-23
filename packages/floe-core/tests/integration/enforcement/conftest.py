"""Integration test fixtures for the policy enforcement module.

This module provides fixtures specific to enforcement integration tests, which:
- Run in K8s (Kind cluster) for production parity
- Test real compilation pipeline integration
- Validate end-to-end enforcement behavior

Task: T004 (part of test directory structure), T080 (Test Duplication Reduction)
Requirements: FR-002 (Pipeline integration), US1 (Compile-time enforcement)

For shared fixtures across all test tiers, see ../conftest.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from floe_core.schemas.manifest import GovernanceConfig


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


@pytest.fixture
def dbt_manifest_with_multiple_models() -> dict[str, Any]:
    """Provide dbt manifest with multiple models having violations.

    Returns:
        Dict containing dbt manifest with multiple models.
    """
    return {
        "metadata": {"dbt_version": "1.8.0"},
        "nodes": {
            "model.my_project.bad_name": {
                "name": "bad_name",
                "resource_type": "model",
                "description": "",  # Documentation violation
                "columns": {},
            },
            "model.my_project.another_bad": {
                "name": "another_bad",
                "resource_type": "model",
                "description": "",
                "columns": {},
            },
        },
    }

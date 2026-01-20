"""Pytest fixtures for exporter tests.

This module provides shared fixtures for testing the enforcement exporters:
- JSON exporter
- SARIF exporter
- HTML exporter

Task: T003 (Epic 3B - Policy Validation Enhancement)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.fixture
def sample_violation() -> dict[str, object]:
    """Create a sample violation dict for testing.

    Returns:
        Dictionary with violation data matching the Violation model schema.
    """
    return {
        "error_code": "FLOE-E201",
        "policy_type": "naming",
        "model_name": "stg_customers",
        "message": "Model 'stg_customers' violates medallion naming convention",
        "suggestion": "Rename model to follow the pattern: stg_<source>_<entity>",
        "severity": "error",
        "column_name": None,
        "file_path": "models/staging/stg_customers.sql",
        "downstream_impact": ["dim_customers", "fct_orders"],
        "first_detected": None,
        "occurrences": None,
        "override_applied": None,
    }


@pytest.fixture
def sample_enforcement_result(sample_violation: dict[str, object]) -> dict[str, object]:
    """Create a sample enforcement result dict for testing.

    Args:
        sample_violation: A sample violation to include in the result.

    Returns:
        Dictionary with enforcement result data matching the EnforcementResult model schema.
    """
    return {
        "passed": False,
        "violations": [sample_violation],
        "summary": {
            "total_models": 10,
            "models_validated": 10,
            "naming_violations": 1,
            "coverage_violations": 0,
            "documentation_violations": 0,
            "semantic_violations": 0,
            "custom_rule_violations": 0,
            "duration_ms": 150.5,
            "overrides_applied": 0,
        },
        "enforcement_level": "strict",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "manifest_version": "1.7.0",
    }


@pytest.fixture
def empty_enforcement_result() -> dict[str, object]:
    """Create an empty (passing) enforcement result for testing.

    Returns:
        Dictionary with a passing enforcement result (no violations).
    """
    return {
        "passed": True,
        "violations": [],
        "summary": {
            "total_models": 10,
            "models_validated": 10,
            "naming_violations": 0,
            "coverage_violations": 0,
            "documentation_violations": 0,
            "semantic_violations": 0,
            "custom_rule_violations": 0,
            "duration_ms": 50.0,
            "overrides_applied": 0,
        },
        "enforcement_level": "strict",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "manifest_version": "1.7.0",
    }

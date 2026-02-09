"""Unit test fixtures for the governance module.

This module provides fixtures specific to governance unit tests, which:
- Run without external services (no K8s, no databases)
- Use mocks/fakes for all plugin dependencies
- Execute quickly (< 1s per test)

Task: T003
Requirements: FR-001 through FR-012 (All governance functional requirements)

For shared fixtures across all test tiers, see ../conftest.py.

Fixtures provided:
- sample_secret_finding: Sample SecretFinding for testing
- sample_governance_check_result: Sample GovernanceCheckResult for testing
"""

from __future__ import annotations

import pytest

from floe_core.enforcement.result import Violation
from floe_core.governance.types import GovernanceCheckResult, SecretFinding


@pytest.fixture
def sample_secret_finding() -> SecretFinding:
    """Provide a sample SecretFinding instance for testing.

    Returns:
        SecretFinding with typical detection values.
    """
    return SecretFinding(
        file_path="src/config/database.py",
        line_number=42,
        pattern_name="aws_access_key_id",
        severity="error",
        match_context="AWS_ACCESS_KEY_ID = 'AKIA***************'",
        confidence="high",
    )


@pytest.fixture
def sample_governance_check_result() -> GovernanceCheckResult:
    """Provide a sample GovernanceCheckResult instance for testing.

    Returns:
        GovernanceCheckResult with a sample rbac violation.
    """
    return GovernanceCheckResult(
        check_type="rbac",
        violations=[
            Violation(
                error_code="FLOE-E401",
                severity="error",
                policy_type="custom",
                model_name="bronze_sensitive_data",
                message="Model requires RBAC annotations",
                expected="rbac_role annotation in meta",
                actual="No rbac_role annotation found",
                suggestion="Add 'meta: {rbac_role: analyst}' to model",
                documentation_url="https://floe.dev/docs/governance/rbac",
            )
        ],
        duration_ms=125.5,
        metadata={"roles_checked": ["analyst", "admin"], "models_scanned": 1},
    )

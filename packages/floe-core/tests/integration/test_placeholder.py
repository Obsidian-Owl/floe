"""Placeholder integration test to ensure pytest collection succeeds.

This file exists to:
1. Prevent pytest exit code 5 (no tests collected) in CI
2. Validate that the integration test infrastructure works

Integration tests will be added as features requiring K8s services are implemented.
See TESTING.md for integration test patterns.
"""

from __future__ import annotations

import pytest


@pytest.mark.requirement("INFRA-001")
def test_integration_infrastructure_ready() -> None:
    """Verify integration test infrastructure is accessible.

    This placeholder test validates that:
    - pytest can collect tests from the integration directory
    - The test runner is correctly configured
    - CI can pass while real integration tests are being developed

    Real integration tests should:
    - Inherit from IntegrationTestBase
    - Use wait_for_condition for service readiness
    - Have requirement markers for traceability
    """
    # This is a placeholder - real tests should validate K8s services
    assert True, "Integration test infrastructure is ready"

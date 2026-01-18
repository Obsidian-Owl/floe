"""Policy enforcement module for compile-time governance validation.

This module provides the PolicyEnforcer engine that validates dbt manifests against
platform-defined policies including naming conventions, test coverage thresholds,
and documentation requirements.

Task: T002
Requirements: FR-001 (PolicyEnforcer core module), FR-002 (Pipeline integration)

Example:
    >>> from floe_core.enforcement import PolicyEnforcer, EnforcementResult
    >>> from floe_core.schemas.governance import GovernanceConfig
    >>>
    >>> enforcer = PolicyEnforcer()
    >>> result = enforcer.enforce(dbt_manifest, governance_config)
    >>> if not result.passed:
    ...     for violation in result.violations:
    ...         print(f"{violation.error_code}: {violation.message}")
"""

from __future__ import annotations

# Imports will be added as modules are implemented:
# - T025-T027: EnforcementResult, Violation, EnforcementSummary from result.py
# - T028: PolicyEnforcementError from errors.py
# - T029-T030: PolicyEnforcer from policy_enforcer.py

__all__: list[str] = [
    # Result models (T025-T027)
    # "EnforcementResult",
    # "EnforcementSummary",
    # "Violation",
    # Error types (T028)
    # "PolicyEnforcementError",
    # Core enforcer (T029-T030)
    # "PolicyEnforcer",
]

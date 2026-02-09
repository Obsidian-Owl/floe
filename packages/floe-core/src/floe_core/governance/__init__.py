"""Governance integration module for floe.

This module provides governance capabilities including:
- RBAC (Role-Based Access Control) validation
- Secret scanning for sensitive data
- Integration with the floe compilation pipeline

The governance module is pluggable and extensible, allowing custom
governance policies to be implemented via the plugin system.

Architecture:
    - GovernanceIntegrator: Orchestrates governance checks during compilation
    - RBACChecker: Validates identity/role configurations against catalog
    - BuiltinSecretScanner: Detects hardcoded secrets in configuration
    - Types: Common data structures for governance results

Usage:
    from floe_core.governance import GovernanceIntegrator

    integrator = GovernanceIntegrator()
    result = integrator.run_checks(spec)
    if not result.passed:
        raise GovernanceError(result.errors)
"""

from __future__ import annotations

from floe_core.governance.integrator import GovernanceIntegrator
from floe_core.governance.policy_evaluator import PolicyDefinition, PolicyEvaluator
from floe_core.governance.rbac_checker import RBACChecker
from floe_core.governance.secrets import BuiltinSecretScanner
from floe_core.governance.types import GovernanceCheckResult, SecretFinding, SecretPattern

__all__: list[str] = [
    "BuiltinSecretScanner",
    "GovernanceCheckResult",
    "GovernanceIntegrator",
    "PolicyDefinition",
    "PolicyEvaluator",
    "RBACChecker",
    "SecretFinding",
    "SecretPattern",
]

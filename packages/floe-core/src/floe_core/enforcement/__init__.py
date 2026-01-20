"""Policy enforcement module for compile-time governance validation.

This module provides the PolicyEnforcer engine that validates dbt manifests against
platform-defined policies including naming conventions, test coverage thresholds,
and documentation requirements.

Task: T002, T088
Requirements: FR-001 (PolicyEnforcer core module), FR-002 (Pipeline integration)

Example:
    >>> from floe_core.enforcement import PolicyEnforcer, EnforcementResult
    >>> from floe_core.schemas.manifest import GovernanceConfig
    >>> from floe_core.schemas.governance import NamingConfig
    >>>
    >>> config = GovernanceConfig(
    ...     policy_enforcement_level="strict",
    ...     naming=NamingConfig(pattern="medallion", enforcement="strict"),
    ... )
    >>> enforcer = PolicyEnforcer(governance_config=config)
    >>> result = enforcer.enforce(dbt_manifest)
    >>> if not result.passed:
    ...     for violation in result.violations:
    ...         print(f"{violation.error_code}: {violation.message}")
"""

from __future__ import annotations

# Error types (T028)
from floe_core.enforcement.errors import PolicyEnforcementError

# Patterns module (T040-T042)
from floe_core.enforcement.patterns import (
    DOCUMENTATION_URLS,
    KIMBALL_PATTERN,
    MEDALLION_PATTERN,
    InvalidPatternError,
    get_documentation_url,
    get_pattern_for_type,
    matches_custom_patterns,
    validate_custom_patterns,
)

# Core enforcer (T029-T030)
from floe_core.enforcement.policy_enforcer import PolicyEnforcer

# Result models (T025-T027)
from floe_core.enforcement.result import (
    EnforcementResult,
    EnforcementSummary,
    Violation,
)

# Validators (T043-T045, T053-T059, T065-T069, T017-T020, T027-T033)
from floe_core.enforcement.validators import (
    CoverageValidator,
    CustomRuleValidator,
    DocumentationValidator,
    NamingValidator,
    SemanticValidator,
)

__all__: list[str] = [
    # Result models (T025-T027)
    "EnforcementResult",
    "EnforcementSummary",
    "Violation",
    # Error types (T028)
    "PolicyEnforcementError",
    # Core enforcer (T029-T030)
    "PolicyEnforcer",
    # Patterns (T040-T042)
    "MEDALLION_PATTERN",
    "KIMBALL_PATTERN",
    "DOCUMENTATION_URLS",
    "InvalidPatternError",
    "validate_custom_patterns",
    "matches_custom_patterns",
    "get_pattern_for_type",
    "get_documentation_url",
    # Validators (T043-T045, T053-T059, T065-T069, T017-T020, T027-T033)
    "NamingValidator",
    "CoverageValidator",
    "DocumentationValidator",
    "SemanticValidator",
    "CustomRuleValidator",
]

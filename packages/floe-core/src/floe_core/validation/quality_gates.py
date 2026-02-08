"""Quality gate validation functions.

This module provides validation functions for quality gates including:
- Coverage validation (FLOE-DQ103)
- Required tests validation (FLOE-DQ104)
- Override validation (FLOE-DQ107)

These functions are used during compilation to enforce quality requirements
at the bronze/silver/gold tier levels.
"""

from __future__ import annotations

from typing import Any

from floe_core.quality_errors import (
    QualityCoverageError,
    QualityMissingTestsError,
    QualityOverrideError,
)
from floe_core.schemas.quality_config import QualityGates

TIER_HIERARCHY = ["enterprise", "domain", "product"]


def validate_coverage(
    model_name: str,
    tier: str,
    actual_coverage: float,
    gates: QualityGates,
) -> None:
    """Validate test coverage meets tier requirements.

    Args:
        model_name: Name of the model being validated.
        tier: Quality tier (bronze, silver, gold).
        actual_coverage: Actual coverage percentage (0-100).
        gates: Quality gates configuration.

    Raises:
        QualityCoverageError: If coverage is below tier minimum (FLOE-DQ103).
    """
    gate_tier = getattr(gates, tier, None)
    if gate_tier is None:
        return

    required_coverage = gate_tier.min_test_coverage
    if actual_coverage < required_coverage:
        raise QualityCoverageError(
            model_name=model_name,
            tier=tier,
            actual_coverage=actual_coverage,
            required_coverage=required_coverage,
        )


def validate_required_tests(
    model_name: str,
    tier: str,
    actual_tests: set[str],
    gates: QualityGates,
) -> None:
    """Validate required test types are present.

    Args:
        model_name: Name of the model being validated.
        tier: Quality tier (bronze, silver, gold).
        actual_tests: Set of test types present on the model.
        gates: Quality gates configuration.

    Raises:
        QualityMissingTestsError: If required tests are missing (FLOE-DQ104).
    """
    gate_tier = getattr(gates, tier, None)
    if gate_tier is None:
        return

    required_tests = set(gate_tier.required_tests)
    missing_tests = required_tests - actual_tests

    if missing_tests:
        raise QualityMissingTestsError(
            model_name=model_name,
            tier=tier,
            missing_tests=sorted(missing_tests),
        )


def validate_override(
    setting_name: str,
    value: Any,
    overridable: bool,
    locked_by: str | None,
    attempted_by: str,
) -> None:
    """Validate that a setting override is allowed.

    Args:
        setting_name: Name of the setting being overridden.
        value: The value being set (for context, not used in validation).
        overridable: Whether the setting is overridable.
        locked_by: Level that locked the setting (enterprise, domain, None).
        attempted_by: Level attempting the override (domain, product).

    Raises:
        QualityOverrideError: If override is not allowed (FLOE-DQ107).
    """
    del value

    if locked_by is None:
        return

    if locked_by == attempted_by:
        return

    if overridable:
        return

    locked_idx = TIER_HIERARCHY.index(locked_by) if locked_by in TIER_HIERARCHY else -1
    attempted_idx = TIER_HIERARCHY.index(attempted_by) if attempted_by in TIER_HIERARCHY else -1

    if attempted_idx > locked_idx:
        raise QualityOverrideError(
            setting_name=setting_name,
            locked_by=locked_by,
            attempted_by=attempted_by,
        )


__all__ = [
    "validate_coverage",
    "validate_override",
    "validate_required_tests",
]

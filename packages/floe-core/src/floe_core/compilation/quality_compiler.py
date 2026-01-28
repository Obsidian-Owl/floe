"""Quality gate validation integration for the compilation pipeline.

This module wires quality gate validation into the compilation process,
emitting FLOE-DQ103 and FLOE-DQ104 errors when quality requirements are not met.

T076: Wire quality gate validation into compiler
"""

from __future__ import annotations

from typing import Any

from floe_core.compilation.errors import CompilationError, CompilationException
from floe_core.compilation.stages import CompilationStage
from floe_core.quality_errors import QualityCoverageError, QualityMissingTestsError
from floe_core.schemas.quality_config import QualityConfig, QualityGates
from floe_core.validation import calculate_coverage, validate_coverage, validate_required_tests


def validate_quality_gates_for_models(
    models: list[dict[str, Any]],
    quality_config: QualityConfig | None,
) -> list[CompilationError]:
    """Validate quality gates for all models during compilation.

    This function is called during the VALIDATE stage to check that all
    models meet their tier's quality requirements (coverage, required tests).

    Args:
        models: List of model definitions with columns, tests, and tier info.
        quality_config: Quality configuration from manifest (may be None).

    Returns:
        List of CompilationError for any violations (may be empty).
    """
    if quality_config is None or not quality_config.enabled:
        return []

    gates = quality_config.quality_gates
    errors: list[CompilationError] = []

    for model in models:
        model_errors = _validate_single_model(model, gates)
        errors.extend(model_errors)

    return errors


def _validate_single_model(
    model: dict[str, Any],
    gates: QualityGates,
) -> list[CompilationError]:
    """Validate quality gates for a single model.

    Args:
        model: Model definition with columns, tests, tier.
        gates: Quality gates configuration.

    Returns:
        List of CompilationError for this model's violations.
    """
    errors: list[CompilationError] = []
    coverage_result = calculate_coverage(model)
    model_name = coverage_result.model_name
    tier = coverage_result.tier

    if tier not in ("bronze", "silver", "gold"):
        tier = "bronze"

    try:
        validate_coverage(
            model_name=model_name,
            tier=tier,
            actual_coverage=coverage_result.coverage_percentage,
            gates=gates,
        )
    except QualityCoverageError as e:
        gate_tier = getattr(gates, tier, gates.bronze)
        errors.append(
            CompilationError(
                stage=CompilationStage.VALIDATE,
                code="FLOE-DQ103",
                message=f"Quality gate coverage violation for '{model_name}'",
                suggestion=e.resolution,
                context={
                    "model": model_name,
                    "tier": tier,
                    "actual_coverage": coverage_result.coverage_percentage,
                    "required_coverage": gate_tier.min_test_coverage,
                },
            )
        )

    try:
        validate_required_tests(
            model_name=model_name,
            tier=tier,
            actual_tests=coverage_result.test_types_present,
            gates=gates,
        )
    except QualityMissingTestsError as e:
        errors.append(
            CompilationError(
                stage=CompilationStage.VALIDATE,
                code="FLOE-DQ104",
                message=f"Missing required tests for '{model_name}'",
                suggestion=e.resolution,
                context={
                    "model": model_name,
                    "tier": tier,
                    "missing_tests": e.missing_tests,
                    "actual_tests": list(coverage_result.test_types_present),
                },
            )
        )

    return errors


def raise_if_quality_violations(errors: list[CompilationError]) -> None:
    """Raise CompilationException if any quality violations exist.

    Args:
        errors: List of compilation errors from quality validation.

    Raises:
        CompilationException: If there are any quality violations.
    """
    if not errors:
        return

    dq103_count = sum(1 for e in errors if e.code == "FLOE-DQ103")
    dq104_count = sum(1 for e in errors if e.code == "FLOE-DQ104")

    msg = (
        f"Quality gate validation failed: {dq103_count} coverage violations, "
        f"{dq104_count} missing test violations"
    )
    summary = CompilationError(
        stage=CompilationStage.VALIDATE,
        code="FLOE-DQ100",
        message=msg,
        suggestion="Fix all quality gate violations before compilation can succeed",
        context={
            "total_violations": len(errors),
            "coverage_violations": dq103_count,
            "missing_test_violations": dq104_count,
        },
    )

    raise CompilationException(summary)


__all__ = [
    "raise_if_quality_violations",
    "validate_quality_gates_for_models",
]

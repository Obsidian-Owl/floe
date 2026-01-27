"""Validation and Gate Result Schemas for data quality validation.

This module defines schemas for compile-time validation results and
quality gate validation results.

Contract Version: 0.4.0

See Also:
    - specs/5b-dataquality-plugin/spec.md: Feature specification
    - specs/5b-dataquality-plugin/data-model.md: Entity definitions
    - ADR-0044: Unified Data Quality Plugin
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ValidationResult(BaseModel):
    """Result of compile-time configuration validation.

    Returned by QualityPlugin.validate_config() to indicate whether
    the quality configuration is valid.

    Example:
        >>> result = ValidationResult(
        ...     success=False,
        ...     errors=["Invalid quality provider: 'unknown'"],
        ...     warnings=["No quality checks defined for model 'stg_customers'"],
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    success: bool = Field(..., description="Whether validation passed")

    errors: list[str] = Field(
        default_factory=list,
        description="Error messages (validation failures)",
    )

    warnings: list[str] = Field(
        default_factory=list,
        description="Warning messages (non-blocking issues)",
    )


class GateResult(BaseModel):
    """Result of quality gate validation.

    Returned by QualityPlugin.validate_quality_gates() to indicate whether
    a model meets its tier's quality requirements.

    Example:
        >>> result = GateResult(
        ...     passed=False,
        ...     tier="gold",
        ...     coverage_actual=85.0,
        ...     coverage_required=100.0,
        ...     missing_tests=["relationships"],
        ...     violations=[
        ...         "Coverage 85.0% is below gold tier minimum of 100%",
        ...         "Missing required test type: relationships",
        ...     ],
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool = Field(..., description="Whether all gates passed")

    tier: Literal["bronze", "silver", "gold"] = Field(
        ...,
        description="Evaluated quality tier",
    )

    coverage_actual: Annotated[float, Field(ge=0, le=100)] = Field(
        ...,
        description="Actual test coverage percentage",
    )

    coverage_required: Annotated[float, Field(ge=0, le=100)] = Field(
        ...,
        description="Required test coverage for this tier",
    )

    missing_tests: list[str] = Field(
        default_factory=list,
        description="Required test types that are missing",
    )

    violations: list[str] = Field(
        default_factory=list,
        description="Human-readable descriptions of gate violations",
    )


__all__ = [
    "GateResult",
    "ValidationResult",
]

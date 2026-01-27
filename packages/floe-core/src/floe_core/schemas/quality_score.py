"""Quality Score and Check Result Schemas for data quality validation.

This module defines schemas for quality checks, their results, and
unified quality scoring that combines dbt tests and plugin checks.

Contract Version: 0.4.0

See Also:
    - specs/5b-dataquality-plugin/spec.md: Feature specification
    - specs/5b-dataquality-plugin/data-model.md: Entity definitions
    - ADR-0044: Unified Data Quality Plugin
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from floe_core.schemas.quality_config import Dimension, SeverityLevel


def _utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class QualityCheck(BaseModel):
    """Individual quality check definition.

    Defines a single quality check with dimension mapping and severity.
    Used both at compile-time (in floe.yaml) and runtime (execution).

    Example:
        >>> check = QualityCheck(
        ...     name="customer_id_not_null",
        ...     type="not_null",
        ...     column="customer_id",
        ...     dimension=Dimension.COMPLETENESS,
        ...     severity=SeverityLevel.CRITICAL,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., min_length=1, description="Check identifier (unique within model)")

    type: str = Field(
        ...,
        min_length=1,
        description="Check type (not_null, unique, expect_column_values_to_be_between, etc.)",
    )

    column: str | None = Field(
        default=None,
        description="Target column (None for table-level checks)",
    )

    dimension: Dimension = Field(
        ...,
        description="Quality dimension (completeness, accuracy, validity, consistency, timeliness)",
    )

    severity: SeverityLevel = Field(
        default=SeverityLevel.WARNING,
        description="Check severity (critical, warning, info)",
    )

    custom_weight: Annotated[float | None, Field(ge=0.1, le=10.0)] = None
    """Override severity weight (0.1-10.0). If None, uses severity default."""

    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Check-specific parameters (min_value, max_value, regex, etc.)",
    )

    enabled: bool = Field(default=True, description="Whether check is active")


class QualityCheckResult(BaseModel):
    """Result of a single quality check execution.

    Enhanced to include dimension, severity, and timing information
    for quality scoring calculation.

    Example:
        >>> result = QualityCheckResult(
        ...     check_name="customer_id_not_null",
        ...     passed=True,
        ...     dimension=Dimension.COMPLETENESS,
        ...     severity=SeverityLevel.CRITICAL,
        ...     records_checked=1000,
        ...     records_failed=0,
        ...     execution_time_ms=45.2,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_name: str = Field(..., description="Name of executed check")

    passed: bool = Field(..., description="Whether check passed")

    dimension: Dimension = Field(..., description="Quality dimension")

    severity: SeverityLevel = Field(..., description="Check severity")

    records_checked: Annotated[int, Field(ge=0)] = 0
    """Number of records evaluated."""

    records_failed: Annotated[int, Field(ge=0)] = 0
    """Number of records that failed the check."""

    execution_time_ms: Annotated[float, Field(ge=0)] = 0.0
    """Check execution time in milliseconds."""

    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional result details",
    )

    error_message: str | None = Field(
        default=None,
        description="Error message if check failed",
    )


class QualitySuiteResult(BaseModel):
    """Aggregated result of running a quality suite.

    Enhanced to include model_name, timing, and timestamp for
    tracking and observability.

    Example:
        >>> result = QualitySuiteResult(
        ...     suite_name="dim_customers_quality",
        ...     model_name="dim_customers",
        ...     passed=True,
        ...     checks=[...],
        ...     execution_time_ms=250.5,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    suite_name: str = Field(..., description="Suite identifier")

    model_name: str = Field(..., description="Target dbt model name")

    passed: bool = Field(..., description="Whether all checks passed")

    checks: list[QualityCheckResult] = Field(
        ...,
        description="Individual check results",
    )

    execution_time_ms: Annotated[float, Field(ge=0)] = 0.0
    """Total execution time in milliseconds."""

    summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics (checks_passed, checks_failed, etc.)",
    )

    timestamp: datetime = Field(
        default_factory=_utcnow,
        description="Execution timestamp",
    )


class QualityScore(BaseModel):
    """Unified quality score incorporating dbt tests and plugin checks.

    Combines results from DBTPlugin.test_models() and QualityPlugin.run_checks()
    into a single quality score (0-100).

    Example:
        >>> score = QualityScore(
        ...     overall=87.5,
        ...     dimension_scores={
        ...         Dimension.COMPLETENESS: 100.0,
        ...         Dimension.ACCURACY: 85.0,
        ...         Dimension.VALIDITY: 90.0,
        ...         Dimension.CONSISTENCY: 75.0,
        ...         Dimension.TIMELINESS: 80.0,
        ...     },
        ...     checks_passed=45,
        ...     checks_failed=5,
        ...     dbt_tests_passed=20,
        ...     dbt_tests_failed=2,
        ...     model_name="dim_customers",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall: Annotated[float, Field(ge=0, le=100)] = Field(
        ...,
        description="Overall quality score (0-100)",
    )

    dimension_scores: dict[Dimension, float] = Field(
        ...,
        description="Per-dimension quality scores (0-100 each)",
    )

    checks_passed: Annotated[int, Field(ge=0)] = 0
    """Number of plugin quality checks that passed."""

    checks_failed: Annotated[int, Field(ge=0)] = 0
    """Number of plugin quality checks that failed."""

    dbt_tests_passed: Annotated[int, Field(ge=0)] = 0
    """Number of dbt tests that passed (from DBTRunResult)."""

    dbt_tests_failed: Annotated[int, Field(ge=0)] = 0
    """Number of dbt tests that failed."""

    model_name: str = Field(..., description="Target model name")

    timestamp: datetime = Field(
        default_factory=_utcnow,
        description="Score calculation timestamp",
    )


class QualitySuite(BaseModel):
    """Collection of quality checks for a model.

    Used to define all checks that should execute for a specific model.

    Example:
        >>> suite = QualitySuite(
        ...     model_name="dim_customers",
        ...     checks=[
        ...         QualityCheck(name="id_not_null", type="not_null", ...),
        ...         QualityCheck(name="email_valid", type="expect_column_values_to_match_regex", ...),
        ...     ],
        ...     timeout_seconds=300,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_name: str = Field(..., description="Target dbt model name")

    checks: list[QualityCheck] = Field(
        ...,
        description="Quality checks to execute",
    )

    timeout_seconds: Annotated[int, Field(ge=1, le=3600)] = 300
    """Execution timeout for all checks in this suite."""

    fail_fast: bool = Field(
        default=False,
        description="Stop execution on first failure",
    )


__all__ = [
    "QualityCheck",
    "QualityCheckResult",
    "QualityScore",
    "QualitySuite",
    "QualitySuiteResult",
]

"""Enforcement result models for PolicyEnforcer.

This module defines the result types returned by PolicyEnforcer.enforce():
- Violation: A single policy violation with actionable details
- EnforcementSummary: Statistics about the enforcement run
- EnforcementResult: Top-level result with pass/fail status

These models form the contract between PolicyEnforcer and the compilation pipeline.

Task: T025, T026, T027
Requirements: FR-002 (Pipeline Integration), US1 (Compile-time Enforcement)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Violation(BaseModel):
    """A single policy violation with actionable details.

    Violation represents a specific policy check that failed, providing
    all context needed for data engineers to understand and fix the issue.

    Attributes:
        error_code: FLOE-EXXX format error code for lookup.
        severity: "error" (blocks compilation) or "warning" (advisory).
        policy_type: Category of policy violated (naming, coverage, documentation, semantic, custom).
        model_name: dbt model where violation occurred.
        column_name: Column if applicable (None for model-level violations).
        message: Human-readable description of the violation.
        expected: What the policy expected (pattern, threshold, etc.).
        actual: What was found in the manifest.
        suggestion: Actionable remediation advice.
        documentation_url: Link to detailed documentation.
        downstream_impact: List of downstream models affected (Epic 3B).
        first_detected: When violation was first detected (placeholder, Epic 3B).
        occurrences: Number of times detected (placeholder, Epic 3B).
        override_applied: Override pattern that modified severity (Epic 3B).

    Example:
        >>> violation = Violation(
        ...     error_code="FLOE-E201",
        ...     severity="error",
        ...     policy_type="naming",
        ...     model_name="stg_payments",
        ...     message="Model name violates medallion convention",
        ...     expected="^(bronze|silver|gold)_.*$",
        ...     actual="stg_payments",
        ...     suggestion="Rename to bronze_payments",
        ...     documentation_url="https://floe.dev/docs/naming#medallion",
        ...     downstream_impact=["dim_payments", "fct_transactions"],
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "title": "Violation",
            "description": "A single policy violation with actionable details",
        },
    )

    error_code: str = Field(
        ...,
        description="FLOE-EXXX format error code",
        examples=["FLOE-E201", "FLOE-E210", "FLOE-E220"],
    )
    severity: Literal["error", "warning"] = Field(
        ...,
        description="Severity level: error (blocks compilation) or warning (advisory)",
    )
    policy_type: Literal["naming", "coverage", "documentation", "semantic", "custom"] = Field(
        ...,
        description="Category of policy violated",
    )
    model_name: str = Field(
        ...,
        description="dbt model name where violation occurred",
    )
    column_name: str | None = Field(
        default=None,
        description="Column name if applicable (None for model-level violations)",
    )
    message: str = Field(
        ...,
        description="Human-readable description of the violation",
    )
    expected: str = Field(
        ...,
        description="What the policy expected (pattern, threshold, etc.)",
    )
    actual: str = Field(
        ...,
        description="What was found in the manifest",
    )
    suggestion: str = Field(
        ...,
        description="Actionable remediation advice",
    )
    documentation_url: str = Field(
        ...,
        description="Link to detailed documentation",
    )
    # Epic 3B: Context fields for enhanced violation reporting
    downstream_impact: list[str] | None = Field(
        default=None,
        description="List of downstream models affected by this model (computed from manifest child_map)",
    )
    first_detected: datetime | None = Field(
        default=None,
        description="When this violation was first detected (placeholder for historical tracking)",
    )
    occurrences: int | None = Field(
        default=None,
        ge=1,
        description="Number of times this violation has been detected (placeholder for historical tracking)",
    )
    override_applied: str | None = Field(
        default=None,
        description="Override pattern that modified this violation's severity (e.g., 'legacy_*')",
    )


class EnforcementSummary(BaseModel):
    """Statistics about the enforcement run.

    EnforcementSummary provides aggregate metrics about the validation,
    useful for logging, monitoring, and reporting.

    Attributes:
        total_models: Total number of models in manifest.
        models_validated: Number of models actually validated.
        naming_violations: Count of naming convention violations.
        coverage_violations: Count of test coverage violations.
        documentation_violations: Count of documentation violations.
        duration_ms: Enforcement duration in milliseconds.

    Example:
        >>> summary = EnforcementSummary(
        ...     total_models=50,
        ...     models_validated=48,
        ...     naming_violations=3,
        ...     coverage_violations=5,
        ...     documentation_violations=2,
        ...     duration_ms=123.45,
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "title": "EnforcementSummary",
            "description": "Statistics about the enforcement run",
        },
    )

    total_models: int = Field(
        ...,
        ge=0,
        description="Total number of models in manifest",
    )
    models_validated: int = Field(
        ...,
        ge=0,
        description="Number of models actually validated",
    )
    naming_violations: int = Field(
        default=0,
        ge=0,
        description="Count of naming convention violations",
    )
    coverage_violations: int = Field(
        default=0,
        ge=0,
        description="Count of test coverage violations",
    )
    documentation_violations: int = Field(
        default=0,
        ge=0,
        description="Count of documentation violations",
    )
    duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Enforcement duration in milliseconds",
    )


class EnforcementResult(BaseModel):
    """Top-level result from PolicyEnforcer.enforce().

    EnforcementResult is the primary contract between PolicyEnforcer and the
    compilation pipeline. It contains the pass/fail status, all violations
    found, and summary statistics.

    Attributes:
        passed: True if no blocking violations (respects enforcement level).
        violations: List of all violations found during enforcement.
        summary: Statistics about the enforcement run.
        enforcement_level: Effective enforcement level used.
        manifest_version: dbt manifest version that was validated.
        timestamp: When validation was performed.

    Example:
        >>> result = EnforcementResult(
        ...     passed=True,
        ...     violations=[],
        ...     summary=EnforcementSummary(total_models=10, models_validated=10),
        ...     enforcement_level="strict",
        ...     manifest_version="1.8.0",
        ...     timestamp=datetime.now(timezone.utc),
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "title": "EnforcementResult",
            "description": "Top-level result from PolicyEnforcer.enforce()",
        },
    )

    passed: bool = Field(
        ...,
        description="True if no blocking violations",
    )
    violations: list[Violation] = Field(
        default_factory=list,
        description="All violations found during enforcement",
    )
    summary: EnforcementSummary = Field(
        ...,
        description="Statistics about the enforcement run",
    )
    enforcement_level: Literal["off", "warn", "strict"] = Field(
        ...,
        description="Effective enforcement level used",
    )
    manifest_version: str = Field(
        ...,
        description="dbt manifest version that was validated",
    )
    timestamp: datetime = Field(
        ...,
        description="When validation was performed",
    )

    @property
    def has_errors(self) -> bool:
        """Return True if any violation has severity='error'.

        This is a convenience property for checking if there are blocking errors.
        Not serialized to JSON (computed from violations list).

        Returns:
            True if there are error-severity violations, False otherwise.
        """
        return any(v.severity == "error" for v in self.violations)

    @property
    def warning_count(self) -> int:
        """Return count of warning-severity violations.

        This is a convenience property for counting warnings.
        Not serialized to JSON (computed from violations list).

        Returns:
            Number of violations with severity='warning'.
        """
        return sum(1 for v in self.violations if v.severity == "warning")

    @property
    def error_count(self) -> int:
        """Return count of error-severity violations.

        This is a convenience property for counting errors.
        Not serialized to JSON (computed from violations list).

        Returns:
            Number of violations with severity='error'.
        """
        return sum(1 for v in self.violations if v.severity == "error")

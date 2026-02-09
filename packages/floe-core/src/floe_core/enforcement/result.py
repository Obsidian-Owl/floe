"""Enforcement result models for PolicyEnforcer.

This module defines the result types returned by PolicyEnforcer.enforce():
- Violation: A single policy violation with actionable details
- EnforcementSummary: Statistics about the enforcement run
- EnforcementResult: Top-level result with pass/fail status
- compute_downstream_impact: Helper to compute downstream models from child_map
- create_enforcement_summary: Create EnforcementResultSummary from EnforcementResult

These models form the contract between PolicyEnforcer and the compilation pipeline.

Task: T025, T026, T027, T047, T061, T007, T009 (Epic 3E: Governance integration)
Requirements: FR-002 (Pipeline Integration), US1 (Compile-time Enforcement),
              FR-016 (Enhanced Context), FR-024 (Pipeline Integration)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import EnforcementResultSummary


class Violation(BaseModel):
    """A single policy violation with actionable details.

    Violation represents a specific policy check that failed, providing
    all context needed for data engineers to understand and fix the issue.

    Attributes:
        error_code: FLOE-EXXX format error code for lookup.
        severity: "error" (blocks compilation) or "warning" (advisory).
        policy_type: Category of policy violated
            (naming, coverage, documentation, semantic, custom, data_contract,
            rbac, secret_scanning, network_policy).
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
    policy_type: Literal[
        "naming",
        "coverage",
        "documentation",
        "semantic",
        "custom",
        "data_contract",
        "rbac",
        "secret_scanning",
        "network_policy",
    ] = Field(
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
        description=(
            "List of downstream models affected by this model (computed from manifest child_map)"
        ),
    )
    first_detected: datetime | None = Field(
        default=None,
        description="When this violation was first detected (placeholder for historical tracking)",
    )
    occurrences: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Number of times this violation has been detected (placeholder for historical tracking)"
        ),
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
        semantic_violations: Count of semantic validation violations (Epic 3B).
        custom_rule_violations: Count of custom rule violations (Epic 3B).
        overrides_applied: Count of policy overrides applied (Epic 3B).
        contract_violations: Count of data contract violations (Epic 3C).
        rbac_violations: Count of RBAC policy violations (Epic 3E).
        secret_violations: Count of secret scanning violations (Epic 3E).
        network_policy_violations: Count of network policy violations (Epic 3E).
        duration_ms: Enforcement duration in milliseconds.

    Example:
        >>> summary = EnforcementSummary(
        ...     total_models=50,
        ...     models_validated=48,
        ...     naming_violations=3,
        ...     coverage_violations=5,
        ...     documentation_violations=2,
        ...     semantic_violations=1,
        ...     custom_rule_violations=2,
        ...     overrides_applied=3,
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
    # Epic 3B: New violation counters
    semantic_violations: int = Field(
        default=0,
        ge=0,
        description="Count of semantic validation violations (ref/source, circular deps)",
    )
    custom_rule_violations: int = Field(
        default=0,
        ge=0,
        description="Count of custom rule violations",
    )
    overrides_applied: int = Field(
        default=0,
        ge=0,
        description="Count of policy overrides applied (downgrade/exclude)",
    )
    # Epic 3C: Data contract violations
    contract_violations: int = Field(
        default=0,
        ge=0,
        description="Count of data contract violations (ODCS, SLA, drift)",
    )
    # Epic 3E: Governance integration violation counters
    rbac_violations: int = Field(
        default=0,
        ge=0,
        description="Count of RBAC policy violations",
    )
    secret_violations: int = Field(
        default=0,
        ge=0,
        description="Count of secret scanning violations",
    )
    network_policy_violations: int = Field(
        default=0,
        ge=0,
        description="Count of network policy violations",
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

    @property
    def violations_by_model(self) -> dict[str, list[Violation]]:
        """Return violations grouped by model name.

        This is a convenience property for grouping violations by the model
        that caused them. Useful for generating per-model reports.
        Not serialized to JSON (computed from violations list).

        Returns:
            Dictionary mapping model names to their violations.

        Example:
            >>> result.violations_by_model["stg_customers"]
            [Violation(model_name="stg_customers", ...)]
        """
        grouped: dict[str, list[Violation]] = {}
        for violation in self.violations:
            if violation.model_name not in grouped:
                grouped[violation.model_name] = []
            grouped[violation.model_name].append(violation)
        return grouped


# ==============================================================================
# US4: Enhanced Violation Context Helpers (T047)
# ==============================================================================


def compute_downstream_impact(
    model_name: str,
    child_map: dict[str, list[str]],
    *,
    recursive: bool = False,
) -> list[str]:
    """Compute list of downstream models affected by a model.

    Uses the dbt manifest child_map to find models that depend on the given
    model. Can optionally compute transitive (recursive) dependencies.

    Args:
        model_name: Simple model name (e.g., "bronze_orders").
        child_map: dbt manifest child_map mapping unique_ids to child unique_ids.
        recursive: If True, include transitive dependencies. Default: False.

    Returns:
        List of simple model names that depend on this model. Empty if none.

    Example:
        >>> child_map = {
        ...     "model.project.bronze_orders": ["model.project.silver_orders"],
        ...     "model.project.silver_orders": ["model.project.gold_orders"],
        ... }
        >>> compute_downstream_impact("bronze_orders", child_map)
        ['silver_orders']
        >>> compute_downstream_impact("bronze_orders", child_map, recursive=True)
        ['silver_orders', 'gold_orders']
    """
    # Find the unique_id for this model name
    model_unique_id = _find_unique_id_for_model(model_name, child_map)

    if model_unique_id is None:
        return []

    if recursive:
        return _compute_recursive_children(model_unique_id, child_map)
    return _extract_model_names(child_map.get(model_unique_id, []))


def _find_unique_id_for_model(
    model_name: str,
    child_map: dict[str, list[str]],
) -> str | None:
    """Find unique_id in child_map that matches the model name.

    Args:
        model_name: Simple model name (e.g., "bronze_orders").
        child_map: dbt manifest child_map.

    Returns:
        The unique_id if found, None otherwise.
    """
    # Look for a unique_id ending with the model name
    for unique_id in child_map:
        if unique_id.endswith(f".{model_name}"):
            return unique_id
    return None


def _compute_recursive_children(
    unique_id: str,
    child_map: dict[str, list[str]],
) -> list[str]:
    """Compute all children recursively, handling circular references.

    Args:
        unique_id: Starting model unique_id.
        child_map: dbt manifest child_map.

    Returns:
        List of all descendant model names (deduplicated).
    """
    visited: set[str] = set()
    result: list[str] = []

    def _visit(uid: str) -> None:
        """Depth-first traversal with cycle detection."""
        if uid in visited:
            return
        visited.add(uid)

        children = child_map.get(uid, [])
        for child_uid in children:
            # Add child's model name (not unique_id)
            model_name = _extract_model_name(child_uid)
            if model_name and model_name not in result:
                result.append(model_name)
            # Recurse
            _visit(child_uid)

    # Start traversal from the given unique_id
    _visit(unique_id)

    return result


def _extract_model_names(unique_ids: list[str]) -> list[str]:
    """Extract simple model names from unique_ids.

    Args:
        unique_ids: List of dbt unique_ids (e.g., "model.project.silver_orders").

    Returns:
        List of simple model names (e.g., "silver_orders").
    """
    result: list[str] = []
    for uid in unique_ids:
        name = _extract_model_name(uid)
        if name:
            result.append(name)
    return result


def _extract_model_name(unique_id: str) -> str | None:
    """Extract simple model name from a unique_id.

    Args:
        unique_id: dbt unique_id (e.g., "model.project.silver_orders").

    Returns:
        Simple model name (e.g., "silver_orders"), or None if invalid.
    """
    # unique_id format: "model.project_name.model_name"
    parts = unique_id.split(".")
    if len(parts) >= 3:
        return parts[-1]  # Last part is the model name
    return None


# ==============================================================================
# T061: Create EnforcementResultSummary from EnforcementResult
# ==============================================================================


def create_enforcement_summary(result: EnforcementResult) -> EnforcementResultSummary:
    """Create an EnforcementResultSummary from an EnforcementResult.

    This helper extracts the essential metrics from EnforcementResult for
    inclusion in CompiledArtifacts. The summary is a lightweight representation
    suitable for downstream consumption without the full violation details.

    Task: T061
    Requirements: FR-024 (Pipeline Integration)

    Args:
        result: Full EnforcementResult from PolicyEnforcer.enforce().

    Returns:
        EnforcementResultSummary containing essential metrics.

    Example:
        >>> result = enforcer.enforce(manifest)
        >>> summary = create_enforcement_summary(result)
        >>> summary.passed
        True
        >>> summary.error_count
        0
    """
    # Import here to avoid circular dependency
    from floe_core.schemas.compiled_artifacts import EnforcementResultSummary

    # Collect unique policy types from violations
    policy_types_checked: list[str] = (
        sorted({v.policy_type for v in result.violations}) if result.violations else []
    )

    # If no violations but enforcement ran, include default policy types
    if not policy_types_checked and result.enforcement_level != "off":
        policy_types_checked = ["coverage", "documentation", "naming"]

    return EnforcementResultSummary(
        passed=result.passed,
        error_count=result.error_count,
        warning_count=result.warning_count,
        policy_types_checked=policy_types_checked,
        models_validated=result.summary.models_validated,
        enforcement_level=result.enforcement_level,
        # Epic 3E: Populate governance integration fields from summary counters
        secrets_scanned=result.summary.secret_violations,
    )

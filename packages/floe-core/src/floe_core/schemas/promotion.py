"""Promotion Lifecycle Schemas for Epic 8C.

This module defines Pydantic v2 schemas for artifact promotion through
user-configurable environments with validation gates, signature verification,
rollback support, and audit trails.

Key Components:
    PromotionGate: Validation gate types (policy_compliance, tests, etc.)
    GateStatus: Gate execution result status
    AuditBackend: Audit storage backend types
    GateResult: Individual gate execution result
    EnvironmentConfig: Per-environment promotion configuration
    PromotionConfig: Top-level promotion configuration
    PromotionRecord: Complete promotion event record
    RollbackRecord: Rollback event record

See Also:
    - specs/8c-promotion-lifecycle/spec.md: Feature specification
    - specs/8c-promotion-lifecycle/data-model.md: Entity definitions
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Enums
# =============================================================================


class PromotionGate(str, Enum):
    """Validation gate types for environment promotion.

    Gates are executed during promotion to validate artifacts meet quality
    standards before advancing to the next environment.

    Attributes:
        POLICY_COMPLIANCE: Policy validation via PolicyEnforcer (mandatory, always runs).
        TESTS: External test execution gate.
        SECURITY_SCAN: Security vulnerability scan gate.
        COST_ANALYSIS: Cost estimation validation gate.
        PERFORMANCE_BASELINE: Performance threshold check gate.

    Examples:
        >>> gate = PromotionGate.POLICY_COMPLIANCE
        >>> gate.value
        'policy_compliance'
        >>> str(gate)
        'policy_compliance'
    """

    POLICY_COMPLIANCE = "policy_compliance"
    TESTS = "tests"
    SECURITY_SCAN = "security_scan"
    COST_ANALYSIS = "cost_analysis"
    PERFORMANCE_BASELINE = "performance_baseline"


class GateStatus(str, Enum):
    """Gate execution result status.

    Represents the outcome of a validation gate execution during promotion.
    A FAILED status blocks promotion (except in dry-run mode).

    Attributes:
        PASSED: Gate validation succeeded.
        FAILED: Gate validation failed (blocks promotion).
        SKIPPED: Gate not configured for this environment.
        WARNING: Gate passed with warnings (non-blocking).

    Examples:
        >>> status = GateStatus.PASSED
        >>> status.value
        'passed'
    """

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


class AuditBackend(str, Enum):
    """Audit storage backend types.

    Specifies where promotion and rollback records are stored for audit trails.

    Attributes:
        OCI: OCI annotations only (default). Records stored as manifest annotations.
        S3: S3 append-only log. Records stored as JSON objects in S3.
        DATABASE: Database storage. Records stored in a relational database.

    Examples:
        >>> backend = AuditBackend.OCI
        >>> backend.value
        'oci'
    """

    OCI = "oci"
    S3 = "s3"
    DATABASE = "database"


# =============================================================================
# Pydantic Models
# =============================================================================


class SecurityScanResult(BaseModel):
    """Security gate execution result details.

    Contains vulnerability counts and blocking CVEs from security scans.
    Used as the security_summary field in GateResult for security_scan gates.

    Attributes:
        critical_count: Number of critical severity vulnerabilities found.
        high_count: Number of high severity vulnerabilities found.
        medium_count: Number of medium severity vulnerabilities found.
        low_count: Number of low severity vulnerabilities found.
        blocking_cves: List of CVE IDs that blocked promotion.
        ignored_unfixed: Count of ignored unfixed vulnerabilities.

    Examples:
        >>> result = SecurityScanResult(
        ...     critical_count=0,
        ...     high_count=2,
        ...     medium_count=5,
        ...     low_count=10,
        ...     blocking_cves=["CVE-2024-1234"],
        ... )
        >>> result.total_vulnerabilities
        17
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    critical_count: int = Field(
        ...,
        ge=0,
        description="Number of critical severity vulnerabilities",
    )
    high_count: int = Field(
        ...,
        ge=0,
        description="Number of high severity vulnerabilities",
    )
    medium_count: int = Field(
        ...,
        ge=0,
        description="Number of medium severity vulnerabilities",
    )
    low_count: int = Field(
        ...,
        ge=0,
        description="Number of low severity vulnerabilities",
    )
    blocking_cves: list[str] = Field(
        default_factory=list,
        description="CVE IDs that blocked promotion",
    )
    ignored_unfixed: int = Field(
        default=0,
        ge=0,
        description="Count of ignored unfixed vulnerabilities",
    )

    @property
    def total_vulnerabilities(self) -> int:
        """Total count of all vulnerabilities."""
        return self.critical_count + self.high_count + self.medium_count + self.low_count


class GateResult(BaseModel):
    """Individual gate execution result.

    Records the outcome of a single validation gate execution during promotion.
    A FAILED status blocks promotion (except in dry-run mode).

    Attributes:
        gate: The gate type that was executed.
        status: Execution result status (passed, failed, skipped, warning).
        duration_ms: Execution time in milliseconds.
        error: Error message if gate failed (required when status is FAILED).
        details: Gate-specific output data.
        security_summary: Security scan details (only for security_scan gate).

    Examples:
        >>> result = GateResult(
        ...     gate=PromotionGate.TESTS,
        ...     status=GateStatus.PASSED,
        ...     duration_ms=1500,
        ... )
        >>> result.status
        <GateStatus.PASSED: 'passed'>
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate: PromotionGate = Field(
        ...,
        description="Gate type that was executed",
    )
    status: GateStatus = Field(
        ...,
        description="Execution result status",
    )
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Execution time in milliseconds",
    )
    error: str | None = Field(
        default=None,
        description="Error message if gate failed",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Gate-specific output data",
    )
    security_summary: SecurityScanResult | None = Field(
        default=None,
        description="Security scan details (only for security_scan gate)",
    )


class AuthorizationConfig(BaseModel):
    """Per-environment authorization rules.

    Controls who can promote artifacts to specific environments.
    If both allowed_groups and allowed_operators are None, all authenticated
    operators are allowed.

    Attributes:
        allowed_groups: Groups allowed to promote (e.g., ["platform-admins"]).
        allowed_operators: Specific operators allowed (e.g., ["admin@example.com"]).
        separation_of_duties: Prevent same operator promoting to consecutive environments.

    Examples:
        >>> config = AuthorizationConfig(
        ...     allowed_groups=["release-managers"],
        ...     separation_of_duties=True,
        ... )
        >>> config.separation_of_duties
        True
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed_groups: list[str] | None = Field(
        default=None,
        description="Groups allowed to promote to this environment",
    )
    allowed_operators: list[str] | None = Field(
        default=None,
        description="Specific operators allowed to promote",
    )
    separation_of_duties: bool = Field(
        default=False,
        description="Prevent same operator promoting to consecutive environments",
    )


class EnvironmentLock(BaseModel):
    """Lock state for an environment to prevent promotions.

    When an environment is locked, no promotions can occur until unlocked.
    Typically used during incidents or maintenance windows.

    Attributes:
        locked: Whether the environment is currently locked.
        reason: Why the environment was locked.
        locked_by: Operator who applied the lock.
        locked_at: When the lock was applied (UTC).

    Examples:
        >>> lock = EnvironmentLock(
        ...     locked=True,
        ...     reason="Incident #123",
        ...     locked_by="sre@example.com",
        ...     locked_at=datetime.now(timezone.utc),
        ... )
        >>> lock.locked
        True
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    locked: bool = Field(
        ...,
        description="Whether environment is locked",
    )
    reason: str | None = Field(
        default=None,
        description="Why environment was locked",
    )
    locked_by: str | None = Field(
        default=None,
        description="Operator who locked the environment",
    )
    locked_at: datetime | None = Field(
        default=None,
        description="When lock was applied (UTC)",
    )


# Valid webhook event types
VALID_WEBHOOK_EVENTS = frozenset({"promote", "rollback", "lock", "unlock"})

# Valid security severity levels
VALID_SEVERITY_LEVELS = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"})

# Valid scanner formats
VALID_SCANNER_FORMATS = frozenset({"trivy", "grype"})


class WebhookConfig(BaseModel):
    """Webhook notification configuration.

    Configures HTTP webhooks for promotion lifecycle events.

    Attributes:
        url: Webhook endpoint URL (must be HTTPS in production).
        events: Event types to notify (promote, rollback, lock, unlock).
        headers: Custom headers (e.g., for authentication).
        timeout_seconds: Request timeout in seconds.
        retry_count: Number of retries on failure.

    Examples:
        >>> config = WebhookConfig(
        ...     url="https://hooks.slack.com/services/T00/B00/XXX",
        ...     events=["promote", "rollback"],
        ... )
        >>> config.timeout_seconds
        30
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = Field(
        ...,
        min_length=1,
        description="Webhook endpoint URL",
    )
    events: list[str] = Field(
        ...,
        min_length=1,
        description="Event types to notify",
    )
    headers: dict[str, str] | None = Field(
        default=None,
        description="Custom headers for requests",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Request timeout in seconds",
    )
    retry_count: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retries on failure",
    )

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        """Validate all events are valid webhook event types."""
        invalid = set(v) - VALID_WEBHOOK_EVENTS
        if invalid:
            raise ValueError(
                f"Invalid event types: {invalid}. "
                f"Valid types: {sorted(VALID_WEBHOOK_EVENTS)}"
            )
        return v


class SecurityGateConfig(BaseModel):
    """Security gate configuration for vulnerability scanning.

    Configures how security scans are executed during promotion.

    Attributes:
        command: Scanner command with ${ARTIFACT_REF} placeholder.
        block_on_severity: Severity levels that block promotion.
        ignore_unfixed: Whether to ignore vulnerabilities without fixes.
        scanner_format: Output format (trivy, grype).
        timeout_seconds: Scanner timeout in seconds.

    Examples:
        >>> config = SecurityGateConfig(
        ...     command="trivy image ${ARTIFACT_REF} --format json",
        ...     block_on_severity=["CRITICAL", "HIGH"],
        ... )
        >>> config.scanner_format
        'trivy'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    command: str = Field(
        ...,
        min_length=1,
        description="Scanner command with ${ARTIFACT_REF} placeholder",
    )
    block_on_severity: list[str] = Field(
        default_factory=lambda: ["CRITICAL", "HIGH"],
        description="Severity levels that block promotion",
    )
    ignore_unfixed: bool = Field(
        default=False,
        description="Ignore vulnerabilities without fixes",
    )
    scanner_format: Literal["trivy", "grype"] = Field(
        default="trivy",
        description="Scanner output format",
    )
    timeout_seconds: int = Field(
        default=600,
        ge=30,
        le=3600,
        description="Scanner timeout in seconds",
    )

    @field_validator("block_on_severity")
    @classmethod
    def validate_severity_levels(cls, v: list[str]) -> list[str]:
        """Validate all severity levels are valid."""
        invalid = set(v) - VALID_SEVERITY_LEVELS
        if invalid:
            raise ValueError(
                f"Invalid severity levels: {invalid}. "
                f"Valid levels: {sorted(VALID_SEVERITY_LEVELS)}"
            )
        return v

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
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from floe_core.schemas.signing import VerificationResult

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
        return (
            self.critical_count + self.high_count + self.medium_count + self.low_count
        )


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
                f"Invalid event types: {invalid}. Valid types: {sorted(VALID_WEBHOOK_EVENTS)}"
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
                f"Invalid severity levels: {invalid}. Valid levels: {sorted(VALID_SEVERITY_LEVELS)}"
            )
        return v


class EnvironmentConfig(BaseModel):
    """Per-environment configuration for promotion gates, authorization, and locks.

    Defines what gates must pass for promotion to this environment,
    who is authorized to promote, and whether the environment is locked.

    Attributes:
        name: Environment name (e.g., "dev", "staging", "prod").
        gates: Map of gate types to enabled status. policy_compliance is always true.
        gate_timeout_seconds: Maximum gate execution time (30-3600 seconds).
        authorization: Access control rules for this environment.
        lock: Current lock state (if locked, promotions are blocked).

    Examples:
        >>> config = EnvironmentConfig(
        ...     name="prod",
        ...     gates={PromotionGate.POLICY_COMPLIANCE: True, PromotionGate.TESTS: True},
        ...     authorization=AuthorizationConfig(allowed_groups=["platform-admins"]),
        ... )
        >>> config.name
        'prod'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z][a-z0-9_-]*$",
        description="Environment name (lowercase, alphanumeric with hyphens/underscores)",
    )
    gates: dict[PromotionGate, bool | SecurityGateConfig] = Field(
        ...,
        description="Gate requirements for this environment",
    )
    gate_timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Maximum gate execution time in seconds",
    )
    authorization: AuthorizationConfig | None = Field(
        default=None,
        description="Access control rules for this environment",
    )
    lock: EnvironmentLock | None = Field(
        default=None,
        description="Current lock state",
    )

    @field_validator("gates")
    @classmethod
    def validate_policy_compliance_always_true(
        cls, v: dict[PromotionGate, bool | SecurityGateConfig]
    ) -> dict[PromotionGate, bool | SecurityGateConfig]:
        """Validate that policy_compliance gate is always enabled."""
        policy_gate = v.get(PromotionGate.POLICY_COMPLIANCE)
        if policy_gate is False:
            raise ValueError(
                "policy_compliance gate cannot be disabled - it is mandatory for all environments"
            )
        return v


def _default_environments() -> list[EnvironmentConfig]:
    """Create default environment configurations [dev, staging, prod]."""
    return [
        EnvironmentConfig(
            name="dev",
            gates={PromotionGate.POLICY_COMPLIANCE: True},
        ),
        EnvironmentConfig(
            name="staging",
            gates={
                PromotionGate.POLICY_COMPLIANCE: True,
                PromotionGate.TESTS: True,
            },
        ),
        EnvironmentConfig(
            name="prod",
            gates={
                PromotionGate.POLICY_COMPLIANCE: True,
                PromotionGate.TESTS: True,
                PromotionGate.SECURITY_SCAN: True,
            },
        ),
    ]


class PromotionConfig(BaseModel):
    """Top-level promotion configuration from manifest.yaml.

    Defines the ordered list of environments, audit backend, timeouts,
    and webhook notifications for the promotion workflow.

    Attributes:
        environments: Ordered list of environments (promotion path).
        audit_backend: Where to store promotion/rollback records.
        default_timeout_seconds: Default gate timeout.
        webhooks: Webhook configurations for notifications.
        gate_commands: Custom gate command configurations.

    Examples:
        >>> config = PromotionConfig()
        >>> [env.name for env in config.environments]
        ['dev', 'staging', 'prod']
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    environments: list[EnvironmentConfig] = Field(
        default_factory=_default_environments,
        min_length=1,
        description="Ordered list of environments (promotion path)",
    )
    audit_backend: AuditBackend = Field(
        default=AuditBackend.OCI,
        description="Audit storage backend type",
    )
    default_timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Default gate timeout in seconds",
    )
    webhooks: list[WebhookConfig] | None = Field(
        default=None,
        description="Webhook configurations for notifications",
    )
    gate_commands: dict[str, str | SecurityGateConfig] | None = Field(
        default=None,
        description="Custom gate command configurations",
    )
    signature_enforcement: Literal["enforce", "warn", "off"] = Field(
        default="enforce",
        description=(
            "Signature verification enforcement mode: "
            "'enforce' (block on invalid), 'warn' (log but allow), 'off' (skip)"
        ),
    )
    secondary_registries: list[str] | None = Field(
        default=None,
        description=(
            "Secondary registry URIs for cross-registry sync (FR-028). "
            "Artifacts are synced to these registries after primary promotion. "
            "Format: 'oci://registry.example.com/repo'"
        ),
    )
    verify_secondary_digests: bool = Field(
        default=True,
        description=(
            "Verify digest match across all registries after sync (FR-029). "
            "If False, sync continues without verification."
        ),
    )

    @field_validator("environments")
    @classmethod
    def validate_unique_environment_names(
        cls, v: list[EnvironmentConfig]
    ) -> list[EnvironmentConfig]:
        """Validate that all environment names are unique."""
        names = [env.name for env in v]
        duplicates = [name for name in names if names.count(name) > 1]
        if duplicates:
            raise ValueError(
                f"Environment names must be unique. Duplicates found: {set(duplicates)}"
            )
        return v


# Regex pattern for SHA256 digests
SHA256_DIGEST_PATTERN = r"^sha256:[a-f0-9]{64}$"
"""Regex pattern for valid SHA256 digest format (sha256:<64 hex chars>)."""


class RollbackImpactAnalysis(BaseModel):
    """Pre-rollback analysis showing potential impacts.

    Contains information about breaking changes, affected products,
    and recommendations for operators before executing a rollback.

    Attributes:
        breaking_changes: List of schema/API breaking changes introduced.
        affected_products: Data products that depend on this artifact.
        recommendations: Operator recommendations before proceeding.
        estimated_downtime: Estimated impact duration (e.g., "~5 minutes").

    Examples:
        >>> analysis = RollbackImpactAnalysis(
        ...     breaking_changes=["API endpoint removed"],
        ...     affected_products=["dashboard"],
        ...     recommendations=["Notify API consumers"],
        ... )
        >>> len(analysis.breaking_changes)
        1
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    breaking_changes: list[str] = Field(
        ...,
        description="Schema/API breaking changes in the target version",
    )
    affected_products: list[str] = Field(
        ...,
        description="Data products using this artifact",
    )
    recommendations: list[str] = Field(
        ...,
        description="Operator recommendations before rollback",
    )
    estimated_downtime: str | None = Field(
        default=None,
        description="Estimated impact duration",
    )


class RegistrySyncStatus(BaseModel):
    """Sync status for a single registry in multi-registry promotion (T079/T083).

    Tracks whether artifact sync succeeded for each registry during
    cross-registry promotion (FR-028, FR-030).

    Attributes:
        registry_uri: OCI registry URI.
        synced: Whether sync completed successfully.
        digest: Artifact digest in this registry (for verification).
        error: Error message if sync failed.
        synced_at: Sync completion timestamp.

    Examples:
        >>> status = RegistrySyncStatus(
        ...     registry_uri="oci://secondary.registry.com/repo",
        ...     synced=True,
        ...     digest="sha256:abc...",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    registry_uri: str = Field(
        ...,
        min_length=1,
        description="OCI registry URI",
    )
    synced: bool = Field(
        ...,
        description="Whether sync completed successfully",
    )
    digest: str | None = Field(
        default=None,
        description="Artifact digest in this registry (for FR-029 verification)",
    )
    error: str | None = Field(
        default=None,
        description="Error message if sync failed",
    )
    synced_at: datetime | None = Field(
        default=None,
        description="Sync completion timestamp",
    )


class PromotionRecord(BaseModel):
    """Complete promotion event record for audit trails.

    Records all details of a promotion event including gate results,
    signature verification, and authorization. Stored in OCI annotations
    and optional audit backends.

    Attributes:
        promotion_id: Unique promotion identifier (UUID).
        artifact_digest: SHA256 digest of the artifact.
        artifact_tag: Source tag (e.g., v1.2.3-dev).
        source_environment: Source environment name.
        target_environment: Target environment name.
        gate_results: All gate execution results.
        signature_verified: Whether signature check passed.
        signature_status: Full verification details from signing module.
        operator: Identity of the promoter.
        promoted_at: Promotion timestamp (UTC).
        dry_run: Whether this was a dry-run.
        trace_id: OpenTelemetry trace ID for linking.
        authorization_passed: Authorization check result.
        authorized_via: How authorization was verified (group, operator).
        operator_groups: Groups the operator belonged to at promotion time.

    Examples:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> record = PromotionRecord(
        ...     promotion_id=uuid4(),
        ...     artifact_digest="sha256:abc...",
        ...     artifact_tag="v1.0.0-dev",
        ...     source_environment="dev",
        ...     target_environment="staging",
        ...     gate_results=[],
        ...     signature_verified=True,
        ...     operator="user@example.com",
        ...     promoted_at=datetime.now(timezone.utc),
        ...     dry_run=False,
        ...     trace_id="abc123",
        ...     authorization_passed=True,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    promotion_id: UUID = Field(
        ...,
        description="Unique promotion identifier",
    )
    artifact_digest: str = Field(
        ...,
        pattern=SHA256_DIGEST_PATTERN,
        description="SHA256 digest of artifact",
    )
    artifact_tag: str = Field(
        ...,
        min_length=1,
        description="Source tag (e.g., v1.2.3-dev)",
    )
    source_environment: str = Field(
        ...,
        min_length=1,
        description="Source environment name",
    )
    target_environment: str = Field(
        ...,
        min_length=1,
        description="Target environment name",
    )
    gate_results: list[GateResult] = Field(
        ...,
        description="All gate execution results",
    )
    signature_verified: bool = Field(
        ...,
        description="Signature check passed",
    )
    signature_status: VerificationResult | None = Field(
        default=None,
        description="Full verification details from signing module",
    )
    operator: str = Field(
        ...,
        min_length=1,
        description="Identity of promoter",
    )
    promoted_at: datetime = Field(
        ...,
        description="Promotion timestamp (UTC)",
    )
    dry_run: bool = Field(
        ...,
        description="Was this a dry-run?",
    )
    trace_id: str = Field(
        ...,
        min_length=1,
        description="OpenTelemetry trace ID for linking",
    )
    authorization_passed: bool = Field(
        ...,
        description="Authorization check result",
    )
    authorized_via: str | None = Field(
        default=None,
        description="How authorization was verified (group, operator)",
    )
    operator_groups: list[str] = Field(
        default_factory=list,
        description="Groups the operator belonged to at promotion time (FR-048 audit trail)",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warning messages from promotion (e.g., partial failures)",
    )
    registry_sync_status: list[RegistrySyncStatus] = Field(
        default_factory=list,
        description=(
            "Sync status for each registry in multi-registry promotion (FR-028/FR-030). "
            "Empty list if single-registry promotion."
        ),
    )


class RollbackRecord(BaseModel):
    """Rollback event record for audit trails.

    Records all details of a rollback event including reason,
    impact analysis, and operator identity.

    Attributes:
        rollback_id: Unique rollback identifier (UUID).
        artifact_digest: SHA256 digest of target version.
        environment: Environment being rolled back.
        previous_digest: Digest of current version before rollback.
        reason: Operator-provided reason for rollback.
        operator: Identity of operator performing rollback.
        rolled_back_at: Rollback timestamp (UTC).
        impact_analysis: Pre-rollback analysis (optional).
        trace_id: OpenTelemetry trace ID for linking.

    Examples:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> record = RollbackRecord(
        ...     rollback_id=uuid4(),
        ...     artifact_digest="sha256:abc...",
        ...     environment="prod",
        ...     previous_digest="sha256:def...",
        ...     reason="Critical bug",
        ...     operator="sre@example.com",
        ...     rolled_back_at=datetime.now(timezone.utc),
        ...     trace_id="xyz789",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rollback_id: UUID = Field(
        ...,
        description="Unique rollback identifier",
    )
    artifact_digest: str = Field(
        ...,
        pattern=SHA256_DIGEST_PATTERN,
        description="SHA256 digest of target version",
    )
    environment: str = Field(
        ...,
        min_length=1,
        description="Environment being rolled back",
    )
    previous_digest: str = Field(
        ...,
        pattern=SHA256_DIGEST_PATTERN,
        description="Digest of current version before rollback",
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="Operator-provided reason for rollback",
    )
    operator: str = Field(
        ...,
        min_length=1,
        description="Identity of operator",
    )
    rolled_back_at: datetime = Field(
        ...,
        description="Rollback timestamp (UTC)",
    )
    impact_analysis: RollbackImpactAnalysis | None = Field(
        default=None,
        description="Pre-rollback analysis",
    )
    trace_id: str = Field(
        ...,
        min_length=1,
        description="OpenTelemetry trace ID for linking",
    )


class EnvironmentStatus(BaseModel):
    """Status of an artifact in a specific environment.

    Tracks whether an artifact has been promoted to an environment
    and when the promotion occurred.

    Attributes:
        promoted: Whether the artifact is promoted to this environment.
        promoted_at: When the artifact was promoted (if promoted).
        is_latest: Whether this artifact is the latest in the environment.
        operator: Who performed the promotion (if promoted).

    Examples:
        >>> status = EnvironmentStatus(
        ...     promoted=True,
        ...     promoted_at=datetime.now(timezone.utc),
        ...     is_latest=True,
        ...     operator="ci@example.com",
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    promoted: bool = Field(
        ...,
        description="Whether the artifact is promoted to this environment",
    )
    promoted_at: datetime | None = Field(
        default=None,
        description="When the artifact was promoted",
    )
    is_latest: bool = Field(
        default=False,
        description="Whether this artifact is the latest in the environment",
    )
    operator: str | None = Field(
        default=None,
        description="Who performed the promotion",
    )


class PromotionHistoryEntry(BaseModel):
    """Single entry in promotion history.

    Represents one promotion event in the artifact's history.
    Contains the required fields per FR-027.

    Attributes:
        promotion_id: Unique promotion identifier.
        artifact_digest: SHA256 digest of the artifact.
        source_environment: Source environment.
        target_environment: Target environment.
        operator: Who performed the promotion.
        promoted_at: When the promotion occurred.
        gate_results: Results of gate validations.
        signature_verified: Whether signature was verified.

    Examples:
        >>> entry = PromotionHistoryEntry(
        ...     promotion_id=uuid4(),
        ...     artifact_digest="sha256:abc...",
        ...     source_environment="dev",
        ...     target_environment="staging",
        ...     operator="ci@example.com",
        ...     promoted_at=datetime.now(timezone.utc),
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    promotion_id: UUID | str = Field(
        ...,
        description="Unique promotion identifier",
    )
    artifact_digest: str = Field(
        ...,
        pattern=SHA256_DIGEST_PATTERN,
        description="SHA256 digest of the artifact",
    )
    source_environment: str = Field(
        ...,
        min_length=1,
        description="Source environment",
    )
    target_environment: str = Field(
        ...,
        min_length=1,
        description="Target environment",
    )
    operator: str = Field(
        ...,
        min_length=1,
        description="Who performed the promotion",
    )
    promoted_at: datetime | str = Field(
        ...,
        description="When the promotion occurred",
    )
    gate_results: list[GateResult] = Field(
        default_factory=list,
        description="Results of gate validations",
    )
    signature_verified: bool = Field(
        default=False,
        description="Whether signature was verified",
    )


class PromotionStatusResponse(BaseModel):
    """Response model for get_status() queries.

    Contains complete promotion status information for an artifact,
    including current environment states and promotion history.

    Attributes:
        tag: Artifact tag being queried.
        digest: SHA256 digest of the artifact.
        environments: Status in each configured environment.
        history: List of promotion events (most recent first).
        queried_at: When the status was queried.

    Examples:
        >>> response = PromotionStatusResponse(
        ...     tag="v1.0.0",
        ...     digest="sha256:abc...",
        ...     environments={"dev": EnvironmentStatus(promoted=True)},
        ...     history=[],
        ...     queried_at=datetime.now(timezone.utc),
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tag: str = Field(
        ...,
        min_length=1,
        description="Artifact tag being queried",
    )
    digest: str = Field(
        ...,
        pattern=SHA256_DIGEST_PATTERN,
        description="SHA256 digest of the artifact",
    )
    environments: dict[str, EnvironmentStatus] = Field(
        ...,
        description="Status in each configured environment",
    )
    history: list[PromotionHistoryEntry] = Field(
        default_factory=list,
        description="List of promotion events (most recent first)",
    )
    queried_at: datetime = Field(
        ...,
        description="When the status was queried",
    )
    environment_locks: dict[str, EnvironmentLock] = Field(
        default_factory=dict,
        description="Lock status for each environment",
    )

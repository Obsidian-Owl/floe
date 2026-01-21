"""RBAC Security Audit Models.

This module provides Pydantic models for RBAC security auditing including
findings, severity levels, and audit reports.

Task: T056, T063
User Story: US6 - RBAC Audit and Validation
Requirements: FR-060, FR-061, FR-070

Example:
    >>> from floe_core.schemas.rbac_audit import (
    ...     AuditFinding,
    ...     AuditSeverity,
    ...     AuditFindingType,
    ...     RBACAuditReport,
    ... )
    >>> finding = AuditFinding(
    ...     severity=AuditSeverity.WARNING,
    ...     finding_type=AuditFindingType.WILDCARD_PERMISSION,
    ...     resource_kind="Role",
    ...     resource_name="my-role",
    ...     resource_namespace="default",
    ...     message="Role contains wildcard permission",
    ...     recommendation="Replace '*' with specific resource names",
    ... )
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditSeverity(str, Enum):
    """Severity levels for audit findings.

    Used to classify the urgency and impact of security findings
    discovered during RBAC auditing.
    """

    INFO = "info"
    """Informational finding, no immediate action required."""

    WARNING = "warning"
    """Warning finding, should be reviewed and addressed."""

    ERROR = "error"
    """Error finding, requires attention to fix."""

    CRITICAL = "critical"
    """Critical finding, requires immediate attention."""


class AuditFindingType(str, Enum):
    """Types of audit findings.

    Categorizes the specific security issue detected during auditing.
    """

    WILDCARD_PERMISSION = "wildcard_permission"
    """Role contains wildcard (*) in apiGroups, resources, or verbs."""

    EXCESSIVE_PERMISSIONS = "excessive_permissions"
    """Role grants more permissions than required."""

    MISSING_RESOURCE_NAMES = "missing_resource_names"
    """Rule accessing secrets without resourceNames constraint."""

    CROSS_NAMESPACE_ACCESS = "cross_namespace_access"
    """Role grants access to resources across namespaces."""

    CLUSTER_SCOPE_BINDING = "cluster_scope_binding"
    """ClusterRoleBinding found where RoleBinding would suffice."""

    UNMANAGED_RESOURCE = "unmanaged_resource"
    """RBAC resource not managed by floe but exists in cluster."""

    ORPHANED_BINDING = "orphaned_binding"
    """RoleBinding references non-existent Role or ServiceAccount."""

    TOKEN_AUTOMOUNT_ENABLED = "token_automount_enabled"
    """ServiceAccount has token automounting enabled (security risk)."""


class AuditFinding(BaseModel):
    """A single finding from the RBAC audit.

    Attributes:
        severity: Severity level of the finding.
        finding_type: Type of audit finding.
        resource_kind: K8s resource kind (ServiceAccount, Role, etc.).
        resource_name: Name of the affected resource.
        resource_namespace: Namespace of the affected resource.
        message: Human-readable description of the finding.
        recommendation: Suggested action to remediate.
        details: Additional details about the finding.

    Example:
        >>> finding = AuditFinding(
        ...     severity=AuditSeverity.WARNING,
        ...     finding_type=AuditFindingType.WILDCARD_PERMISSION,
        ...     resource_kind="Role",
        ...     resource_name="my-role",
        ...     resource_namespace="default",
        ...     message="Role contains wildcard permission",
        ...     recommendation="Replace '*' with specific resource names",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: AuditSeverity = Field(
        ...,
        description="Severity level of the finding",
    )
    finding_type: AuditFindingType = Field(
        ...,
        description="Type of audit finding",
    )
    resource_kind: str = Field(
        ...,
        description="K8s resource kind",
    )
    resource_name: str = Field(
        ...,
        description="Name of the affected resource",
    )
    resource_namespace: str | None = Field(
        default=None,
        description="Namespace of the affected resource",
    )
    message: str = Field(
        ...,
        description="Human-readable description",
    )
    recommendation: str = Field(
        default="",
        description="Suggested remediation action",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional details",
    )


class ServiceAccountSummary(BaseModel):
    """Summary of a service account's permissions.

    Attributes:
        name: ServiceAccount name.
        namespace: ServiceAccount namespace.
        roles: List of Role names bound to this account.
        cluster_roles: List of ClusterRole names bound to this account.
        secrets_access: List of secrets this account can access.
        automount_token: Whether token automounting is enabled.
        managed_by_floe: Whether this account is managed by floe.

    Example:
        >>> summary = ServiceAccountSummary(
        ...     name="floe-job-runner",
        ...     namespace="floe-jobs",
        ...     roles=["floe-secret-reader-role"],
        ...     secrets_access=["snowflake-creds"],
        ...     managed_by_floe=True,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="ServiceAccount name")
    namespace: str = Field(..., description="ServiceAccount namespace")
    roles: list[str] = Field(default_factory=list, description="Bound Role names")
    cluster_roles: list[str] = Field(
        default_factory=list, description="Bound ClusterRole names"
    )
    secrets_access: list[str] = Field(
        default_factory=list, description="Accessible secret names"
    )
    automount_token: bool = Field(
        default=False, description="Token automounting enabled"
    )
    managed_by_floe: bool = Field(default=False, description="Managed by floe")


class NamespaceSummary(BaseModel):
    """Summary of a namespace's RBAC configuration.

    Attributes:
        name: Namespace name.
        pss_enforce: Pod Security Standard enforcement level.
        service_accounts: Number of service accounts in namespace.
        roles: Number of roles in namespace.
        role_bindings: Number of role bindings in namespace.
        managed_by_floe: Whether this namespace is managed by floe.

    Example:
        >>> summary = NamespaceSummary(
        ...     name="floe-jobs",
        ...     pss_enforce="restricted",
        ...     service_accounts=2,
        ...     roles=3,
        ...     role_bindings=4,
        ...     managed_by_floe=True,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Namespace name")
    pss_enforce: str | None = Field(default=None, description="PSS enforcement level")
    service_accounts: int = Field(
        default=0, ge=0, description="Number of service accounts"
    )
    roles: int = Field(default=0, ge=0, description="Number of roles")
    role_bindings: int = Field(default=0, ge=0, description="Number of role bindings")
    managed_by_floe: bool = Field(default=False, description="Managed by floe")


class RBACAuditReport(BaseModel):
    """Complete RBAC audit report.

    Attributes:
        generated_at: Timestamp when report was generated.
        cluster_name: Name of the K8s cluster audited.
        namespaces: Summary of namespaces analyzed.
        service_accounts: Summary of service accounts analyzed.
        findings: List of audit findings.
        total_service_accounts: Total number of service accounts.
        total_roles: Total number of roles.
        total_role_bindings: Total number of role bindings.
        floe_managed_count: Number of resources managed by floe.

    Example:
        >>> report = RBACAuditReport(
        ...     cluster_name="my-cluster",
        ...     namespaces=[NamespaceSummary(name="floe-jobs")],
        ...     service_accounts=[ServiceAccountSummary(name="sa1", namespace="default")],
        ...     findings=[],
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="Report generation timestamp",
    )
    cluster_name: str = Field(
        default="unknown",
        description="Name of the K8s cluster",
    )
    namespaces: list[NamespaceSummary] = Field(
        default_factory=list,
        description="Namespace summaries",
    )
    service_accounts: list[ServiceAccountSummary] = Field(
        default_factory=list,
        description="Service account summaries",
    )
    findings: list[AuditFinding] = Field(
        default_factory=list,
        description="Audit findings",
    )
    total_service_accounts: int = Field(
        default=0,
        ge=0,
        description="Total service accounts",
    )
    total_roles: int = Field(
        default=0,
        ge=0,
        description="Total roles",
    )
    total_role_bindings: int = Field(
        default=0,
        ge=0,
        description="Total role bindings",
    )
    floe_managed_count: int = Field(
        default=0,
        ge=0,
        description="Resources managed by floe",
    )

    def has_critical_findings(self) -> bool:
        """Check if report contains critical findings.

        Returns:
            True if any finding has CRITICAL severity.
        """
        return any(f.severity == AuditSeverity.CRITICAL for f in self.findings)

    def has_warnings(self) -> bool:
        """Check if report contains warnings or errors.

        Returns:
            True if any finding has WARNING, ERROR, or CRITICAL severity.
        """
        warning_levels = {
            AuditSeverity.WARNING,
            AuditSeverity.ERROR,
            AuditSeverity.CRITICAL,
        }
        return any(f.severity in warning_levels for f in self.findings)

    def findings_by_severity(self) -> dict[AuditSeverity, list[AuditFinding]]:
        """Group findings by severity level.

        Returns:
            Dictionary mapping severity levels to lists of findings.
        """
        result: dict[AuditSeverity, list[AuditFinding]] = {
            severity: [] for severity in AuditSeverity
        }
        for finding in self.findings:
            result[finding.severity].append(finding)
        return result

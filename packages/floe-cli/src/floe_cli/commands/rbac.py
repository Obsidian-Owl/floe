"""RBAC management CLI commands.

This module provides CLI commands for managing Kubernetes RBAC:
- generate: Generate RBAC manifests from configuration
- validate: Validate manifests against configuration
- audit: Analyze current cluster RBAC state
- diff: Show differences between expected and deployed RBAC

Task: T059, T060, T061, T062, T063
User Story: US6 - RBAC Audit and Validation
Requirements: FR-060, FR-061, FR-062, FR-063, FR-070

Example:
    $ floe rbac generate
    $ floe rbac validate
    $ floe rbac audit
    $ floe rbac diff
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# T056: RBAC Audit Report Models
# =============================================================================


class AuditSeverity(str, Enum):
    """Severity levels for audit findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditFindingType(str, Enum):
    """Types of audit findings."""

    WILDCARD_PERMISSION = "wildcard_permission"
    EXCESSIVE_PERMISSIONS = "excessive_permissions"
    MISSING_RESOURCE_NAMES = "missing_resource_names"
    CROSS_NAMESPACE_ACCESS = "cross_namespace_access"
    CLUSTER_SCOPE_BINDING = "cluster_scope_binding"
    UNMANAGED_RESOURCE = "unmanaged_resource"
    ORPHANED_BINDING = "orphaned_binding"
    TOKEN_AUTOMOUNT_ENABLED = "token_automount_enabled"


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
        ...     recommendation="Replace '*' with specific resource names"
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
        ...     managed_by_floe=True
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="ServiceAccount name")
    namespace: str = Field(..., description="ServiceAccount namespace")
    roles: list[str] = Field(default_factory=list, description="Bound Role names")
    cluster_roles: list[str] = Field(default_factory=list, description="Bound ClusterRole names")
    secrets_access: list[str] = Field(default_factory=list, description="Accessible secret names")
    automount_token: bool = Field(default=False, description="Token automounting enabled")
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
        ...     managed_by_floe=True
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Namespace name")
    pss_enforce: str | None = Field(default=None, description="PSS enforcement level")
    service_accounts: int = Field(default=0, ge=0, description="Number of service accounts")
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
        ...     namespaces=[NamespaceSummary(name="floe-jobs", ...)],
        ...     service_accounts=[ServiceAccountSummary(...)],
        ...     findings=[]
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
        warning_levels = {AuditSeverity.WARNING, AuditSeverity.ERROR, AuditSeverity.CRITICAL}
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


# =============================================================================
# T063: Wildcard Detection
# =============================================================================


def detect_wildcard_permissions(
    rules: list[dict[str, Any]],
    role_name: str,
    namespace: str | None = None,
) -> list[AuditFinding]:
    """Detect wildcard permissions in role rules (FR-070).

    Args:
        rules: List of role rule dictionaries from K8s API.
        role_name: Name of the role being analyzed.
        namespace: Namespace of the role (None for ClusterRole).

    Returns:
        List of AuditFinding objects for any wildcard permissions found.

    Example:
        >>> rules = [{"apiGroups": ["*"], "resources": ["secrets"], "verbs": ["get"]}]
        >>> findings = detect_wildcard_permissions(rules, "my-role", "default")
        >>> len(findings) > 0
        True
    """
    findings: list[AuditFinding] = []

    for i, rule in enumerate(rules):
        api_groups = rule.get("apiGroups", [])
        resources = rule.get("resources", [])
        verbs = rule.get("verbs", [])

        # Check for wildcards in apiGroups
        if "*" in api_groups:
            findings.append(
                AuditFinding(
                    severity=AuditSeverity.CRITICAL,
                    finding_type=AuditFindingType.WILDCARD_PERMISSION,
                    resource_kind="Role" if namespace else "ClusterRole",
                    resource_name=role_name,
                    resource_namespace=namespace,
                    message=f"Rule {i} contains wildcard in apiGroups",
                    recommendation="Replace '*' with specific API groups",
                    details={"rule_index": i, "field": "apiGroups", "value": api_groups},
                )
            )

        # Check for wildcards in resources
        if "*" in resources:
            findings.append(
                AuditFinding(
                    severity=AuditSeverity.CRITICAL,
                    finding_type=AuditFindingType.WILDCARD_PERMISSION,
                    resource_kind="Role" if namespace else "ClusterRole",
                    resource_name=role_name,
                    resource_namespace=namespace,
                    message=f"Rule {i} contains wildcard in resources",
                    recommendation="Replace '*' with specific resource types",
                    details={"rule_index": i, "field": "resources", "value": resources},
                )
            )

        # Check for wildcards in verbs
        if "*" in verbs:
            findings.append(
                AuditFinding(
                    severity=AuditSeverity.CRITICAL,
                    finding_type=AuditFindingType.WILDCARD_PERMISSION,
                    resource_kind="Role" if namespace else "ClusterRole",
                    resource_name=role_name,
                    resource_namespace=namespace,
                    message=f"Rule {i} contains wildcard in verbs",
                    recommendation="Replace '*' with specific verbs (get, list, etc.)",
                    details={"rule_index": i, "field": "verbs", "value": verbs},
                )
            )

    return findings


def check_missing_resource_names(
    rules: list[dict[str, Any]],
    role_name: str,
    namespace: str | None = None,
) -> list[AuditFinding]:
    """Check for rules accessing secrets without resourceNames constraint.

    Args:
        rules: List of role rule dictionaries from K8s API.
        role_name: Name of the role being analyzed.
        namespace: Namespace of the role (None for ClusterRole).

    Returns:
        List of AuditFinding objects for rules missing resourceNames on secrets.

    Example:
        >>> rules = [{"resources": ["secrets"], "verbs": ["get"]}]
        >>> findings = check_missing_resource_names(rules, "my-role", "default")
        >>> len(findings) > 0
        True
    """
    findings: list[AuditFinding] = []

    for i, rule in enumerate(rules):
        resources = rule.get("resources", [])
        resource_names = rule.get("resourceNames", [])

        # Check if rule accesses secrets without resourceNames
        if "secrets" in resources and not resource_names:
            findings.append(
                AuditFinding(
                    severity=AuditSeverity.WARNING,
                    finding_type=AuditFindingType.MISSING_RESOURCE_NAMES,
                    resource_kind="Role" if namespace else "ClusterRole",
                    resource_name=role_name,
                    resource_namespace=namespace,
                    message=f"Rule {i} grants access to all secrets (no resourceNames)",
                    recommendation="Add resourceNames constraint to limit secret access",
                    details={"rule_index": i, "resources": resources},
                )
            )

    return findings


# =============================================================================
# T057: RBAC Validation Models
# =============================================================================


class ValidationStatus(str, Enum):
    """Status of validation result."""

    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"


class ValidationIssueType(str, Enum):
    """Types of validation issues."""

    MISSING_SERVICE_ACCOUNT = "missing_service_account"
    MISSING_ROLE = "missing_role"
    MISSING_ROLE_BINDING = "missing_role_binding"
    MISSING_NAMESPACE = "missing_namespace"
    EXTRA_SERVICE_ACCOUNT = "extra_service_account"
    EXTRA_ROLE = "extra_role"
    EXTRA_ROLE_BINDING = "extra_role_binding"
    INVALID_YAML = "invalid_yaml"
    SCHEMA_MISMATCH = "schema_mismatch"
    SECRET_REFERENCE_MISMATCH = "secret_reference_mismatch"
    RULE_MISMATCH = "rule_mismatch"


class ValidationIssue(BaseModel):
    """A single validation issue.

    Attributes:
        issue_type: Type of validation issue.
        resource_kind: K8s resource kind affected.
        resource_name: Name of the affected resource.
        resource_namespace: Namespace of the affected resource.
        message: Human-readable description of the issue.
        expected: Expected value or state.
        actual: Actual value or state found.

    Example:
        >>> issue = ValidationIssue(
        ...     issue_type=ValidationIssueType.MISSING_ROLE,
        ...     resource_kind="Role",
        ...     resource_name="floe-reader-role",
        ...     resource_namespace="floe-jobs",
        ...     message="Role not found in generated manifests",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_type: ValidationIssueType = Field(
        ...,
        description="Type of validation issue",
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
    expected: str | None = Field(
        default=None,
        description="Expected value or state",
    )
    actual: str | None = Field(
        default=None,
        description="Actual value or state found",
    )


class RBACValidationResult(BaseModel):
    """Result of RBAC manifest validation against configuration.

    Attributes:
        status: Overall validation status.
        config_path: Path to the configuration file validated against.
        manifest_dir: Path to the manifest directory validated.
        issues: List of validation issues found.
        service_accounts_validated: Number of service accounts validated.
        roles_validated: Number of roles validated.
        role_bindings_validated: Number of role bindings validated.
        namespaces_validated: Number of namespaces validated.

    Example:
        >>> result = RBACValidationResult(
        ...     status=ValidationStatus.VALID,
        ...     config_path="/path/to/manifest.yaml",
        ...     manifest_dir="/path/to/target/rbac",
        ... )
        >>> result.is_valid
        True
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ValidationStatus = Field(
        ...,
        description="Overall validation status",
    )
    config_path: str = Field(
        ...,
        description="Path to configuration file",
    )
    manifest_dir: str = Field(
        ...,
        description="Path to manifest directory",
    )
    issues: list[ValidationIssue] = Field(
        default_factory=list,
        description="Validation issues found",
    )
    service_accounts_validated: int = Field(
        default=0,
        ge=0,
        description="Service accounts validated",
    )
    roles_validated: int = Field(
        default=0,
        ge=0,
        description="Roles validated",
    )
    role_bindings_validated: int = Field(
        default=0,
        ge=0,
        description="Role bindings validated",
    )
    namespaces_validated: int = Field(
        default=0,
        ge=0,
        description="Namespaces validated",
    )

    @property
    def is_valid(self) -> bool:
        """Check if validation passed.

        Returns:
            True if status is VALID.
        """
        return self.status == ValidationStatus.VALID

    @property
    def has_errors(self) -> bool:
        """Check if validation has errors (not just warnings).

        Returns:
            True if status is INVALID.
        """
        return self.status == ValidationStatus.INVALID

    def issues_by_type(self) -> dict[ValidationIssueType, list[ValidationIssue]]:
        """Group issues by type.

        Returns:
            Dictionary mapping issue types to lists of issues.
        """
        result: dict[ValidationIssueType, list[ValidationIssue]] = {
            issue_type: [] for issue_type in ValidationIssueType
        }
        for issue in self.issues:
            result[issue.issue_type].append(issue)
        return result


def validate_manifest_against_config(
    manifest_resources: list[dict[str, Any]],
    expected_resources: list[dict[str, Any]],
    resource_kind: str,
) -> list[ValidationIssue]:
    """Validate manifest resources against expected configuration.

    Args:
        manifest_resources: Resources found in generated manifests.
        expected_resources: Resources expected from configuration.
        resource_kind: Kind of resources being validated.

    Returns:
        List of ValidationIssue objects for any mismatches found.

    Example:
        >>> manifests = [{"metadata": {"name": "sa1"}}]
        >>> expected = [{"metadata": {"name": "sa1"}}, {"metadata": {"name": "sa2"}}]
        >>> issues = validate_manifest_against_config(manifests, expected, "ServiceAccount")
        >>> len(issues)
        1
    """
    issues: list[ValidationIssue] = []

    manifest_names = {
        (r.get("metadata", {}).get("name"), r.get("metadata", {}).get("namespace"))
        for r in manifest_resources
    }
    expected_names = {
        (r.get("metadata", {}).get("name"), r.get("metadata", {}).get("namespace"))
        for r in expected_resources
    }

    # Find missing resources (expected but not in manifest)
    missing = expected_names - manifest_names
    for name, namespace in missing:
        issue_type = {
            "ServiceAccount": ValidationIssueType.MISSING_SERVICE_ACCOUNT,
            "Role": ValidationIssueType.MISSING_ROLE,
            "RoleBinding": ValidationIssueType.MISSING_ROLE_BINDING,
            "Namespace": ValidationIssueType.MISSING_NAMESPACE,
        }.get(resource_kind, ValidationIssueType.SCHEMA_MISMATCH)

        issues.append(
            ValidationIssue(
                issue_type=issue_type,
                resource_kind=resource_kind,
                resource_name=name or "unknown",
                resource_namespace=namespace,
                message=f"{resource_kind} '{name}' expected but not found in manifests",
                expected=f"{resource_kind}/{namespace}/{name}" if namespace else f"{resource_kind}/{name}",
                actual=None,
            )
        )

    # Find extra resources (in manifest but not expected)
    extra = manifest_names - expected_names
    for name, namespace in extra:
        issue_type = {
            "ServiceAccount": ValidationIssueType.EXTRA_SERVICE_ACCOUNT,
            "Role": ValidationIssueType.EXTRA_ROLE,
            "RoleBinding": ValidationIssueType.EXTRA_ROLE_BINDING,
        }.get(resource_kind, ValidationIssueType.SCHEMA_MISMATCH)

        issues.append(
            ValidationIssue(
                issue_type=issue_type,
                resource_kind=resource_kind,
                resource_name=name or "unknown",
                resource_namespace=namespace,
                message=f"{resource_kind} '{name}' found in manifests but not expected",
                expected=None,
                actual=f"{resource_kind}/{namespace}/{name}" if namespace else f"{resource_kind}/{name}",
            )
        )

    return issues

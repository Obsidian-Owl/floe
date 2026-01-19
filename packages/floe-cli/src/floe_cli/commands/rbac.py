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
                expected=(
                    f"{resource_kind}/{namespace}/{name}"
                    if namespace
                    else f"{resource_kind}/{name}"
                ),
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
                actual=(
                    f"{resource_kind}/{namespace}/{name}"
                    if namespace
                    else f"{resource_kind}/{name}"
                ),
            )
        )

    return issues


# =============================================================================
# T058: RBAC Diff Models
# =============================================================================


class DiffChangeType(str, Enum):
    """Types of changes in a diff."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class ResourceDiff(BaseModel):
    """A single resource difference between expected and actual state.

    Attributes:
        change_type: Type of change (added, removed, modified, unchanged).
        resource_kind: K8s resource kind (ServiceAccount, Role, etc.).
        resource_name: Name of the resource.
        resource_namespace: Namespace of the resource (None for cluster-scoped).
        expected_value: Expected resource specification.
        actual_value: Actual resource specification from cluster.
        diff_details: List of specific differences found.

    Example:
        >>> diff = ResourceDiff(
        ...     change_type=DiffChangeType.MODIFIED,
        ...     resource_kind="Role",
        ...     resource_name="my-role",
        ...     resource_namespace="default",
        ...     diff_details=["rules[0].verbs: expected ['get'], got ['get', 'list']"]
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    change_type: DiffChangeType = Field(
        ...,
        description="Type of change",
    )
    resource_kind: str = Field(
        ...,
        description="K8s resource kind",
    )
    resource_name: str = Field(
        ...,
        description="Name of the resource",
    )
    resource_namespace: str | None = Field(
        default=None,
        description="Namespace of the resource",
    )
    expected_value: dict[str, Any] | None = Field(
        default=None,
        description="Expected resource specification",
    )
    actual_value: dict[str, Any] | None = Field(
        default=None,
        description="Actual resource specification",
    )
    diff_details: list[str] = Field(
        default_factory=list,
        description="Specific differences found",
    )


class RBACDiffResult(BaseModel):
    """Result of comparing expected vs actual RBAC configuration.

    Attributes:
        generated_at: Timestamp when diff was computed.
        expected_source: Source of expected resources (file path or description).
        actual_source: Source of actual resources (cluster name or file path).
        diffs: List of resource differences.
        added_count: Number of resources to be added.
        removed_count: Number of resources to be removed.
        modified_count: Number of resources that differ.

    Example:
        >>> result = RBACDiffResult(
        ...     expected_source="manifest.yaml",
        ...     actual_source="cluster:my-cluster",
        ...     diffs=[ResourceDiff(...)],
        ...     added_count=1
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="Diff computation timestamp",
    )
    expected_source: str = Field(
        ...,
        description="Source of expected resources",
    )
    actual_source: str = Field(
        ...,
        description="Source of actual resources",
    )
    diffs: list[ResourceDiff] = Field(
        default_factory=list,
        description="List of resource differences",
    )
    added_count: int = Field(
        default=0,
        ge=0,
        description="Resources to be added",
    )
    removed_count: int = Field(
        default=0,
        ge=0,
        description="Resources to be removed",
    )
    modified_count: int = Field(
        default=0,
        ge=0,
        description="Resources that differ",
    )

    def has_differences(self) -> bool:
        """Check if there are any actual differences.

        Returns:
            True if any diff has a non-UNCHANGED change type.
        """
        return any(d.change_type != DiffChangeType.UNCHANGED for d in self.diffs)

    def diffs_by_change_type(self) -> dict[DiffChangeType, list[ResourceDiff]]:
        """Group diffs by change type.

        Returns:
            Dictionary mapping change types to lists of diffs.
        """
        result: dict[DiffChangeType, list[ResourceDiff]] = {
            change_type: [] for change_type in DiffChangeType
        }
        for diff in self.diffs:
            result[diff.change_type].append(diff)
        return result

    def diffs_by_resource_kind(self) -> dict[str, list[ResourceDiff]]:
        """Group diffs by resource kind.

        Returns:
            Dictionary mapping resource kinds to lists of diffs.
        """
        result: dict[str, list[ResourceDiff]] = {}
        for diff in self.diffs:
            if diff.resource_kind not in result:
                result[diff.resource_kind] = []
            result[diff.resource_kind].append(diff)
        return result


# Metadata fields to ignore when comparing resources
_IGNORED_METADATA_FIELDS = frozenset(
    {
        "uid",
        "resourceVersion",
        "creationTimestamp",
        "generation",
        "managedFields",
        "selfLink",
    }
)


def _normalize_resource(resource: dict[str, Any]) -> dict[str, Any]:
    """Normalize a resource by removing non-essential metadata.

    Args:
        resource: K8s resource dictionary.

    Returns:
        Normalized resource dictionary for comparison.
    """
    result = dict(resource)

    # Normalize metadata
    if "metadata" in result:
        metadata = dict(result["metadata"])
        for field in _IGNORED_METADATA_FIELDS:
            metadata.pop(field, None)
        # Also remove annotations that are cluster-specific
        if "annotations" in metadata:
            annotations = dict(metadata["annotations"])
            annotations.pop("kubectl.kubernetes.io/last-applied-configuration", None)
            metadata["annotations"] = annotations if annotations else None
            if not metadata["annotations"]:
                del metadata["annotations"]
        result["metadata"] = metadata

    return result


def _compare_values(
    expected: Any,
    actual: Any,
    path: str = "",
) -> list[str]:
    """Recursively compare two values and return differences.

    Args:
        expected: Expected value.
        actual: Actual value.
        path: Current path in the structure.

    Returns:
        List of difference descriptions.
    """
    differences: list[str] = []

    if type(expected) != type(actual):  # noqa: E721
        differences.append(
            f"{path}: type mismatch (expected {type(expected).__name__}, "
            f"got {type(actual).__name__})"
        )
        return differences

    if isinstance(expected, dict):
        all_keys = set(expected.keys()) | set(actual.keys())
        for key in all_keys:
            new_path = f"{path}.{key}" if path else key
            if key not in expected:
                differences.append(f"{new_path}: unexpected field")
            elif key not in actual:
                differences.append(f"{new_path}: missing field")
            else:
                differences.extend(_compare_values(expected[key], actual[key], new_path))
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            differences.append(
                f"{path}: list length mismatch (expected {len(expected)}, got {len(actual)})"
            )
        else:
            for i, (exp_item, act_item) in enumerate(zip(expected, actual, strict=True)):
                differences.extend(_compare_values(exp_item, act_item, f"{path}[{i}]"))
    elif expected != actual:
        differences.append(f"{path}: expected {expected!r}, got {actual!r}")

    return differences


def compute_resource_diff(
    expected: dict[str, Any] | None,
    actual: dict[str, Any] | None,
    resource_kind: str,
) -> ResourceDiff:
    """Compute the diff between expected and actual resource.

    Args:
        expected: Expected resource specification (None if added).
        actual: Actual resource specification (None if removed).
        resource_kind: K8s resource kind.

    Returns:
        ResourceDiff describing the change.

    Example:
        >>> expected = {"metadata": {"name": "sa1"}}
        >>> actual = {"metadata": {"name": "sa1"}}
        >>> diff = compute_resource_diff(expected, actual, "ServiceAccount")
        >>> diff.change_type
        <DiffChangeType.UNCHANGED: 'unchanged'>
    """
    # Handle added resource (expected but not actual)
    if expected is not None and actual is None:
        metadata = expected.get("metadata", {})
        return ResourceDiff(
            change_type=DiffChangeType.ADDED,
            resource_kind=resource_kind,
            resource_name=metadata.get("name", "unknown"),
            resource_namespace=metadata.get("namespace"),
            expected_value=expected,
            actual_value=None,
            diff_details=["Resource needs to be created"],
        )

    # Handle removed resource (actual but not expected)
    if expected is None and actual is not None:
        metadata = actual.get("metadata", {})
        return ResourceDiff(
            change_type=DiffChangeType.REMOVED,
            resource_kind=resource_kind,
            resource_name=metadata.get("name", "unknown"),
            resource_namespace=metadata.get("namespace"),
            expected_value=None,
            actual_value=actual,
            diff_details=["Resource should be removed"],
        )

    # Both exist - compare them
    if expected is None or actual is None:
        msg = "Both expected and actual cannot be None"
        raise ValueError(msg)

    metadata = expected.get("metadata", {})
    name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace")

    # Normalize for comparison
    norm_expected = _normalize_resource(expected)
    norm_actual = _normalize_resource(actual)

    # Compare
    differences = _compare_values(norm_expected, norm_actual)

    if not differences:
        return ResourceDiff(
            change_type=DiffChangeType.UNCHANGED,
            resource_kind=resource_kind,
            resource_name=name,
            resource_namespace=namespace,
            expected_value=expected,
            actual_value=actual,
            diff_details=[],
        )

    return ResourceDiff(
        change_type=DiffChangeType.MODIFIED,
        resource_kind=resource_kind,
        resource_name=name,
        resource_namespace=namespace,
        expected_value=expected,
        actual_value=actual,
        diff_details=differences,
    )


def compute_rbac_diff(
    expected_resources: list[dict[str, Any]],
    actual_resources: list[dict[str, Any]],
    expected_source: str,
    actual_source: str,
) -> RBACDiffResult:
    """Compute diff between expected and actual RBAC resources.

    Args:
        expected_resources: List of expected K8s resources.
        actual_resources: List of actual K8s resources from cluster.
        expected_source: Description of expected resources source.
        actual_source: Description of actual resources source.

    Returns:
        RBACDiffResult with all differences.

    Example:
        >>> expected = [{"kind": "ServiceAccount", "metadata": {"name": "sa1"}}]
        >>> actual = []
        >>> result = compute_rbac_diff(expected, actual, "file.yaml", "cluster:test")
        >>> result.has_differences()
        True
    """
    diffs: list[ResourceDiff] = []
    added_count = 0
    removed_count = 0
    modified_count = 0

    # Build lookup maps keyed by (kind, namespace, name)
    def resource_key(r: dict[str, Any]) -> tuple[str, str | None, str]:
        kind = r.get("kind", "Unknown")
        metadata = r.get("metadata", {})
        name = metadata.get("name", "unknown")
        namespace = metadata.get("namespace")
        return (kind, namespace, name)

    expected_map = {resource_key(r): r for r in expected_resources}
    actual_map = {resource_key(r): r for r in actual_resources}

    all_keys = set(expected_map.keys()) | set(actual_map.keys())

    for key in sorted(all_keys):
        kind, _namespace, _name = key
        expected_res = expected_map.get(key)
        actual_res = actual_map.get(key)

        diff = compute_resource_diff(expected_res, actual_res, kind)
        diffs.append(diff)

        if diff.change_type == DiffChangeType.ADDED:
            added_count += 1
        elif diff.change_type == DiffChangeType.REMOVED:
            removed_count += 1
        elif diff.change_type == DiffChangeType.MODIFIED:
            modified_count += 1

    return RBACDiffResult(
        expected_source=expected_source,
        actual_source=actual_source,
        diffs=diffs,
        added_count=added_count,
        removed_count=removed_count,
        modified_count=modified_count,
    )

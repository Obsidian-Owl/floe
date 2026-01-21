"""RBAC Validation Functions.

This module provides functions for validating RBAC manifests against
expected configuration.

Task: T057
User Story: US6 - RBAC Audit and Validation
Requirements: FR-061, FR-062

Example:
    >>> from floe_core.rbac.validate import validate_manifest_against_config
    >>> manifests = [{"metadata": {"name": "sa1"}}]
    >>> expected = [{"metadata": {"name": "sa1"}}, {"metadata": {"name": "sa2"}}]
    >>> issues = validate_manifest_against_config(manifests, expected, "ServiceAccount")
    >>> len(issues)
    1
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from floe_core.schemas.rbac_validation import ValidationIssue


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
    from floe_core.schemas.rbac_validation import ValidationIssue, ValidationIssueType

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

"""RBAC Validation Models.

This module provides Pydantic models for RBAC manifest validation including
validation status, issue types, and validation results.

Task: T057
User Story: US6 - RBAC Audit and Validation
Requirements: FR-061, FR-062

Example:
    >>> from floe_core.schemas.rbac_validation import (
    ...     ValidationStatus,
    ...     ValidationIssueType,
    ...     ValidationIssue,
    ...     RBACValidationResult,
    ... )
    >>> result = RBACValidationResult(
    ...     status=ValidationStatus.VALID,
    ...     config_path="/path/to/manifest.yaml",
    ...     manifest_dir="/path/to/target/rbac",
    ... )
    >>> result.is_valid
    True
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ValidationStatus(str, Enum):
    """Status of validation result.

    Used to indicate the overall outcome of RBAC validation.
    """

    VALID = "valid"
    """Validation passed with no issues."""

    INVALID = "invalid"
    """Validation failed with errors."""

    WARNING = "warning"
    """Validation passed with warnings."""


class ValidationIssueType(str, Enum):
    """Types of validation issues.

    Categorizes specific issues found during RBAC validation.
    """

    MISSING_SERVICE_ACCOUNT = "missing_service_account"
    """Expected ServiceAccount not found in manifests."""

    MISSING_ROLE = "missing_role"
    """Expected Role not found in manifests."""

    MISSING_ROLE_BINDING = "missing_role_binding"
    """Expected RoleBinding not found in manifests."""

    MISSING_NAMESPACE = "missing_namespace"
    """Expected Namespace not found in manifests."""

    EXTRA_SERVICE_ACCOUNT = "extra_service_account"
    """ServiceAccount in manifest but not expected."""

    EXTRA_ROLE = "extra_role"
    """Role in manifest but not expected."""

    EXTRA_ROLE_BINDING = "extra_role_binding"
    """RoleBinding in manifest but not expected."""

    INVALID_YAML = "invalid_yaml"
    """Manifest file contains invalid YAML syntax."""

    SCHEMA_MISMATCH = "schema_mismatch"
    """Resource does not match expected schema."""

    SECRET_REFERENCE_MISMATCH = "secret_reference_mismatch"
    """Secret references in manifest don't match configuration."""

    RULE_MISMATCH = "rule_mismatch"
    """Role rules don't match expected permissions."""


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

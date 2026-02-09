"""Unit tests for RBAC validation models.

Tests the RBAC validation models migrated from floe-cli.

Task: T057, Epic 11
User Story: US6 - RBAC Audit and Validation
Requirements: FR-061
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError


class TestValidationIssue:
    """Unit tests for ValidationIssue model."""

    @pytest.mark.requirement("FR-061")
    def test_validation_issue_creation(self) -> None:
        """Test ValidationIssue can be created with required fields."""
        from floe_core.schemas.rbac_validation import (
            ValidationIssue,
            ValidationIssueType,
        )

        issue = ValidationIssue(
            issue_type=ValidationIssueType.MISSING_ROLE,
            resource_kind="Role",
            resource_name="floe-reader-role",
            message="Role not found in generated manifests",
        )

        assert issue.issue_type == ValidationIssueType.MISSING_ROLE
        assert issue.resource_kind == "Role"
        assert issue.resource_name == "floe-reader-role"
        assert issue.message == "Role not found in generated manifests"

    @pytest.mark.requirement("FR-061")
    def test_validation_issue_with_all_fields(self) -> None:
        """Test ValidationIssue with all optional fields populated."""
        from floe_core.schemas.rbac_validation import (
            ValidationIssue,
            ValidationIssueType,
        )

        issue = ValidationIssue(
            issue_type=ValidationIssueType.SCHEMA_MISMATCH,
            resource_kind="Role",
            resource_name="my-role",
            resource_namespace="default",
            message="Role rules don't match expected configuration",
            expected="get, list",
            actual="get, list, delete",
        )

        assert issue.resource_namespace == "default"
        assert issue.expected == "get, list"
        assert issue.actual == "get, list, delete"

    @pytest.mark.requirement("FR-061")
    def test_validation_issue_immutable(self) -> None:
        """Test ValidationIssue is immutable (frozen model)."""
        from floe_core.schemas.rbac_validation import (
            ValidationIssue,
            ValidationIssueType,
        )

        issue = ValidationIssue(
            issue_type=ValidationIssueType.MISSING_ROLE,
            resource_kind="Role",
            resource_name="my-role",
            message="Test message",
        )

        with pytest.raises(ValidationError):
            issue.resource_name = "other-role"  # type: ignore[misc]


class TestValidationIssueTypes:
    """Unit tests for ValidationIssueType enum."""

    @pytest.mark.requirement("FR-061")
    def test_all_issue_types_exist(self) -> None:
        """Test all expected validation issue types exist."""
        from floe_core.schemas.rbac_validation import ValidationIssueType

        expected_types = [
            "MISSING_SERVICE_ACCOUNT",
            "MISSING_ROLE",
            "MISSING_ROLE_BINDING",
            "MISSING_NAMESPACE",
            "EXTRA_SERVICE_ACCOUNT",
            "EXTRA_ROLE",
            "EXTRA_ROLE_BINDING",
            "INVALID_YAML",
            "SCHEMA_MISMATCH",
            "SECRET_REFERENCE_MISMATCH",
            "RULE_MISMATCH",
        ]

        for type_name in expected_types:
            assert hasattr(ValidationIssueType, type_name), f"Missing {type_name}"


class TestRBACValidationResult:
    """Unit tests for RBACValidationResult model."""

    @pytest.mark.requirement("FR-061")
    def test_validation_result_creation(self) -> None:
        """Test RBACValidationResult can be created."""
        from floe_core.schemas.rbac_validation import (
            RBACValidationResult,
            ValidationStatus,
        )

        result = RBACValidationResult(
            status=ValidationStatus.VALID,
            config_path="/path/to/manifest.yaml",
            manifest_dir="/path/to/target/rbac",
        )

        assert result.status == ValidationStatus.VALID
        assert result.config_path == "/path/to/manifest.yaml"
        assert result.manifest_dir == "/path/to/target/rbac"
        assert result.issues == []

    @pytest.mark.requirement("FR-061")
    def test_validation_result_with_issues(self) -> None:
        """Test RBACValidationResult with issues."""
        from floe_core.schemas.rbac_validation import (
            RBACValidationResult,
            ValidationIssue,
            ValidationIssueType,
            ValidationStatus,
        )

        issue = ValidationIssue(
            issue_type=ValidationIssueType.MISSING_ROLE,
            resource_kind="Role",
            resource_name="missing-role",
            message="Role not found",
        )

        result = RBACValidationResult(
            status=ValidationStatus.INVALID,
            config_path="/path/manifest.yaml",
            manifest_dir="/path/rbac",
            issues=[issue],
            roles_validated=1,
        )

        assert len(result.issues) == 1
        assert result.roles_validated == 1

    @pytest.mark.requirement("FR-061")
    def test_is_valid_property(self) -> None:
        """Test is_valid property returns correct value."""
        from floe_core.schemas.rbac_validation import (
            RBACValidationResult,
            ValidationStatus,
        )

        valid_result = RBACValidationResult(
            status=ValidationStatus.VALID,
            config_path="/path/manifest.yaml",
            manifest_dir="/path/rbac",
        )
        assert valid_result.is_valid is True

        invalid_result = RBACValidationResult(
            status=ValidationStatus.INVALID,
            config_path="/path/manifest.yaml",
            manifest_dir="/path/rbac",
        )
        assert invalid_result.is_valid is False

        warning_result = RBACValidationResult(
            status=ValidationStatus.WARNING,
            config_path="/path/manifest.yaml",
            manifest_dir="/path/rbac",
        )
        assert warning_result.is_valid is False

    @pytest.mark.requirement("FR-061")
    def test_has_errors_property(self) -> None:
        """Test has_errors property returns correct value."""
        from floe_core.schemas.rbac_validation import (
            RBACValidationResult,
            ValidationStatus,
        )

        valid_result = RBACValidationResult(
            status=ValidationStatus.VALID,
            config_path="/path/manifest.yaml",
            manifest_dir="/path/rbac",
        )
        assert valid_result.has_errors is False

        invalid_result = RBACValidationResult(
            status=ValidationStatus.INVALID,
            config_path="/path/manifest.yaml",
            manifest_dir="/path/rbac",
        )
        assert invalid_result.has_errors is True

        warning_result = RBACValidationResult(
            status=ValidationStatus.WARNING,
            config_path="/path/manifest.yaml",
            manifest_dir="/path/rbac",
        )
        assert warning_result.has_errors is False

    @pytest.mark.requirement("FR-061")
    def test_issues_by_type(self) -> None:
        """Test issues can be grouped by type."""
        from floe_core.schemas.rbac_validation import (
            RBACValidationResult,
            ValidationIssue,
            ValidationIssueType,
            ValidationStatus,
        )

        issues = [
            ValidationIssue(
                issue_type=ValidationIssueType.MISSING_ROLE,
                resource_kind="Role",
                resource_name="role-1",
                message="Missing role 1",
            ),
            ValidationIssue(
                issue_type=ValidationIssueType.EXTRA_SERVICE_ACCOUNT,
                resource_kind="ServiceAccount",
                resource_name="sa-1",
                message="Extra SA 1",
            ),
            ValidationIssue(
                issue_type=ValidationIssueType.MISSING_ROLE,
                resource_kind="Role",
                resource_name="role-2",
                message="Missing role 2",
            ),
        ]

        result = RBACValidationResult(
            status=ValidationStatus.INVALID,
            config_path="/path/manifest.yaml",
            manifest_dir="/path/rbac",
            issues=issues,
        )

        by_type = result.issues_by_type()

        assert len(by_type[ValidationIssueType.MISSING_ROLE]) == 2
        assert len(by_type[ValidationIssueType.EXTRA_SERVICE_ACCOUNT]) == 1
        assert len(by_type[ValidationIssueType.MISSING_NAMESPACE]) == 0

    @pytest.mark.requirement("FR-061")
    def test_validation_result_serializable(self) -> None:
        """Test RBACValidationResult is JSON serializable."""
        from floe_core.schemas.rbac_validation import (
            RBACValidationResult,
            ValidationIssue,
            ValidationIssueType,
            ValidationStatus,
        )

        issue = ValidationIssue(
            issue_type=ValidationIssueType.MISSING_ROLE,
            resource_kind="Role",
            resource_name="my-role",
            resource_namespace="default",
            message="Role not found",
        )

        result = RBACValidationResult(
            status=ValidationStatus.INVALID,
            config_path="/path/manifest.yaml",
            manifest_dir="/path/rbac",
            issues=[issue],
            service_accounts_validated=2,
            roles_validated=3,
        )

        json_str = result.model_dump_json()
        assert "invalid" in json_str
        assert "my-role" in json_str

        data = result.model_dump(mode="json")
        json_str2 = json.dumps(data)
        assert "MISSING_ROLE" in json_str2 or "missing_role" in json_str2

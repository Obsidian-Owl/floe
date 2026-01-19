"""Unit tests for RBAC validation.

Tests the RBACValidationResult model and validation utilities for
validating generated manifests against configuration.

Task: T057
User Story: US6 - RBAC Audit and Validation
Requirements: FR-061
"""

from __future__ import annotations

import pytest


class TestValidationIssue:
    """Unit tests for ValidationIssue model."""

    @pytest.mark.requirement("FR-061")
    def test_validation_issue_creation(self) -> None:
        """Test ValidationIssue can be created with required fields."""
        from floe_cli.commands.rbac import ValidationIssue, ValidationIssueType

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
        from floe_cli.commands.rbac import ValidationIssue, ValidationIssueType

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
        from floe_cli.commands.rbac import ValidationIssue, ValidationIssueType

        issue = ValidationIssue(
            issue_type=ValidationIssueType.MISSING_ROLE,
            resource_kind="Role",
            resource_name="my-role",
            message="Test message",
        )

        with pytest.raises(Exception):  # ValidationError or AttributeError
            issue.resource_name = "other-role"  # type: ignore[misc]


class TestValidationIssueTypes:
    """Unit tests for ValidationIssueType enum."""

    @pytest.mark.requirement("FR-061")
    def test_all_issue_types_exist(self) -> None:
        """Test all expected validation issue types exist."""
        from floe_cli.commands.rbac import ValidationIssueType

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
        from floe_cli.commands.rbac import RBACValidationResult, ValidationStatus

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
        from floe_cli.commands.rbac import (
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
        from floe_cli.commands.rbac import RBACValidationResult, ValidationStatus

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
        from floe_cli.commands.rbac import RBACValidationResult, ValidationStatus

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
        from floe_cli.commands.rbac import (
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
        import json

        from floe_cli.commands.rbac import (
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

        # Should not raise
        json_str = result.model_dump_json()
        assert "invalid" in json_str
        assert "my-role" in json_str

        # Can also use standard json.dumps
        data = result.model_dump(mode="json")
        json_str2 = json.dumps(data)
        assert "MISSING_ROLE" in json_str2 or "missing_role" in json_str2


class TestValidateManifestAgainstConfig:
    """Unit tests for validate_manifest_against_config function."""

    @pytest.mark.requirement("FR-061")
    def test_validation_finds_missing_resources(self) -> None:
        """Test validation detects missing resources."""
        from floe_cli.commands.rbac import (
            ValidationIssueType,
            validate_manifest_against_config,
        )

        manifest_resources = [
            {"metadata": {"name": "sa1", "namespace": "default"}},
        ]
        expected_resources = [
            {"metadata": {"name": "sa1", "namespace": "default"}},
            {"metadata": {"name": "sa2", "namespace": "default"}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "ServiceAccount"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == ValidationIssueType.MISSING_SERVICE_ACCOUNT
        assert issues[0].resource_name == "sa2"

    @pytest.mark.requirement("FR-061")
    def test_validation_finds_extra_resources(self) -> None:
        """Test validation detects extra resources."""
        from floe_cli.commands.rbac import (
            ValidationIssueType,
            validate_manifest_against_config,
        )

        manifest_resources = [
            {"metadata": {"name": "role1", "namespace": "default"}},
            {"metadata": {"name": "role2", "namespace": "default"}},
        ]
        expected_resources = [
            {"metadata": {"name": "role1", "namespace": "default"}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "Role"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == ValidationIssueType.EXTRA_ROLE
        assert issues[0].resource_name == "role2"

    @pytest.mark.requirement("FR-061")
    def test_validation_no_issues_when_matching(self) -> None:
        """Test validation returns no issues when resources match."""
        from floe_cli.commands.rbac import validate_manifest_against_config

        manifest_resources = [
            {"metadata": {"name": "sa1", "namespace": "ns1"}},
            {"metadata": {"name": "sa2", "namespace": "ns2"}},
        ]
        expected_resources = [
            {"metadata": {"name": "sa1", "namespace": "ns1"}},
            {"metadata": {"name": "sa2", "namespace": "ns2"}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "ServiceAccount"
        )

        assert len(issues) == 0

    @pytest.mark.requirement("FR-061")
    def test_validation_handles_different_resource_kinds(self) -> None:
        """Test validation handles different resource kinds correctly."""
        from floe_cli.commands.rbac import (
            ValidationIssueType,
            validate_manifest_against_config,
        )

        # Test RoleBinding
        manifest_resources: list[dict] = []
        expected_resources = [
            {"metadata": {"name": "binding1", "namespace": "default"}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "RoleBinding"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == ValidationIssueType.MISSING_ROLE_BINDING

        # Test Namespace
        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "Namespace"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == ValidationIssueType.MISSING_NAMESPACE

    @pytest.mark.requirement("FR-061")
    def test_validation_with_empty_lists(self) -> None:
        """Test validation with empty resource lists."""
        from floe_cli.commands.rbac import validate_manifest_against_config

        # Both empty
        issues = validate_manifest_against_config([], [], "Role")
        assert len(issues) == 0

        # Only manifest empty
        expected = [{"metadata": {"name": "role1", "namespace": "ns1"}}]
        issues = validate_manifest_against_config([], expected, "Role")
        assert len(issues) == 1

        # Only expected empty
        manifest = [{"metadata": {"name": "role1", "namespace": "ns1"}}]
        issues = validate_manifest_against_config(manifest, [], "Role")
        assert len(issues) == 1

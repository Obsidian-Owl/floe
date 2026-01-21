"""Unit tests for RBAC validation functions.

Tests the validate_manifest_against_config function migrated from floe-cli.

Task: T063, Epic 11
User Story: US6 - RBAC Audit and Validation
Requirements: FR-061, FR-062
"""

from __future__ import annotations

import pytest


class TestValidateManifestAgainstConfig:
    """Unit tests for validate_manifest_against_config function."""

    @pytest.mark.requirement("FR-061")
    def test_detect_missing_service_account(self) -> None:
        """Test detection of missing ServiceAccount."""
        from floe_core.rbac.validate import validate_manifest_against_config
        from floe_core.schemas.rbac_validation import ValidationIssueType

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
    def test_detect_extra_service_account(self) -> None:
        """Test detection of extra ServiceAccount."""
        from floe_core.rbac.validate import validate_manifest_against_config
        from floe_core.schemas.rbac_validation import ValidationIssueType

        manifest_resources = [
            {"metadata": {"name": "sa1", "namespace": "default"}},
            {"metadata": {"name": "sa2", "namespace": "default"}},
        ]
        expected_resources = [
            {"metadata": {"name": "sa1", "namespace": "default"}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "ServiceAccount"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == ValidationIssueType.EXTRA_SERVICE_ACCOUNT
        assert issues[0].resource_name == "sa2"

    @pytest.mark.requirement("FR-061")
    def test_detect_missing_role(self) -> None:
        """Test detection of missing Role."""
        from floe_core.rbac.validate import validate_manifest_against_config
        from floe_core.schemas.rbac_validation import ValidationIssueType

        manifest_resources: list[dict] = []
        expected_resources = [
            {"metadata": {"name": "my-role", "namespace": "floe-jobs"}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "Role"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == ValidationIssueType.MISSING_ROLE
        assert issues[0].resource_name == "my-role"

    @pytest.mark.requirement("FR-061")
    def test_detect_extra_role(self) -> None:
        """Test detection of extra Role."""
        from floe_core.rbac.validate import validate_manifest_against_config
        from floe_core.schemas.rbac_validation import ValidationIssueType

        manifest_resources = [
            {"metadata": {"name": "extra-role", "namespace": "default"}},
        ]
        expected_resources: list[dict] = []

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "Role"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == ValidationIssueType.EXTRA_ROLE

    @pytest.mark.requirement("FR-061")
    def test_detect_missing_role_binding(self) -> None:
        """Test detection of missing RoleBinding."""
        from floe_core.rbac.validate import validate_manifest_against_config
        from floe_core.schemas.rbac_validation import ValidationIssueType

        manifest_resources: list[dict] = []
        expected_resources = [
            {"metadata": {"name": "my-binding", "namespace": "floe-jobs"}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "RoleBinding"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == ValidationIssueType.MISSING_ROLE_BINDING

    @pytest.mark.requirement("FR-061")
    def test_detect_extra_role_binding(self) -> None:
        """Test detection of extra RoleBinding."""
        from floe_core.rbac.validate import validate_manifest_against_config
        from floe_core.schemas.rbac_validation import ValidationIssueType

        manifest_resources = [
            {"metadata": {"name": "extra-binding", "namespace": "default"}},
        ]
        expected_resources: list[dict] = []

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "RoleBinding"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == ValidationIssueType.EXTRA_ROLE_BINDING

    @pytest.mark.requirement("FR-061")
    def test_no_issues_when_matching(self) -> None:
        """Test no issues when manifests match expected."""
        from floe_core.rbac.validate import validate_manifest_against_config

        manifest_resources = [
            {"metadata": {"name": "sa1", "namespace": "default"}},
            {"metadata": {"name": "sa2", "namespace": "floe-jobs"}},
        ]
        expected_resources = [
            {"metadata": {"name": "sa1", "namespace": "default"}},
            {"metadata": {"name": "sa2", "namespace": "floe-jobs"}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "ServiceAccount"
        )

        assert len(issues) == 0

    @pytest.mark.requirement("FR-061")
    def test_empty_lists_no_issues(self) -> None:
        """Test no issues when both lists are empty."""
        from floe_core.rbac.validate import validate_manifest_against_config

        issues = validate_manifest_against_config([], [], "ServiceAccount")

        assert len(issues) == 0

    @pytest.mark.requirement("FR-061")
    def test_multiple_missing_and_extra(self) -> None:
        """Test detection of multiple missing and extra resources."""
        from floe_core.rbac.validate import validate_manifest_against_config
        from floe_core.schemas.rbac_validation import ValidationIssueType

        manifest_resources = [
            {"metadata": {"name": "deployed1", "namespace": "ns"}},
            {"metadata": {"name": "deployed2", "namespace": "ns"}},
        ]
        expected_resources = [
            {"metadata": {"name": "expected1", "namespace": "ns"}},
            {"metadata": {"name": "expected2", "namespace": "ns"}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "ServiceAccount"
        )

        # Should have 2 missing + 2 extra = 4 issues
        assert len(issues) == 4

        missing = [i for i in issues if i.issue_type == ValidationIssueType.MISSING_SERVICE_ACCOUNT]
        extra = [i for i in issues if i.issue_type == ValidationIssueType.EXTRA_SERVICE_ACCOUNT]

        assert len(missing) == 2
        assert len(extra) == 2

    @pytest.mark.requirement("FR-061")
    def test_issue_includes_resource_namespace(self) -> None:
        """Test issue includes resource namespace."""
        from floe_core.rbac.validate import validate_manifest_against_config

        manifest_resources: list[dict] = []
        expected_resources = [
            {"metadata": {"name": "my-sa", "namespace": "floe-jobs"}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "ServiceAccount"
        )

        assert len(issues) == 1
        assert issues[0].resource_namespace == "floe-jobs"

    @pytest.mark.requirement("FR-061")
    def test_cluster_scoped_resources(self) -> None:
        """Test validation of cluster-scoped resources (no namespace)."""
        from floe_core.rbac.validate import validate_manifest_against_config

        manifest_resources = [
            {"metadata": {"name": "ns1", "namespace": None}},
        ]
        expected_resources = [
            {"metadata": {"name": "ns1", "namespace": None}},
            {"metadata": {"name": "ns2", "namespace": None}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "Namespace"
        )

        assert len(issues) == 1
        assert issues[0].resource_namespace is None

    @pytest.mark.requirement("FR-061")
    def test_issue_message_format(self) -> None:
        """Test issue message contains useful information."""
        from floe_core.rbac.validate import validate_manifest_against_config

        manifest_resources: list[dict] = []
        expected_resources = [
            {"metadata": {"name": "missing-sa", "namespace": "default"}},
        ]

        issues = validate_manifest_against_config(
            manifest_resources, expected_resources, "ServiceAccount"
        )

        assert len(issues) == 1
        assert "missing-sa" in issues[0].message
        assert "expected" in issues[0].message.lower() or "not found" in issues[0].message.lower()


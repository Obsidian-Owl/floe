"""Unit tests for RBAC security audit functions.

Tests the detect_wildcard_permissions and check_missing_resource_names
functions migrated from floe-cli.

Task: T063, Epic 11
User Story: US6 - RBAC Audit and Validation
Requirements: FR-070
"""

from __future__ import annotations

import pytest


class TestDetectWildcardPermissions:
    """Unit tests for detect_wildcard_permissions function."""

    @pytest.mark.requirement("FR-070")
    def test_detect_wildcard_in_api_groups(self) -> None:
        """Test detection of wildcard in apiGroups."""
        from floe_core.rbac.audit import detect_wildcard_permissions
        from floe_core.schemas.rbac_audit import AuditFindingType, AuditSeverity

        rules = [
            {"apiGroups": ["*"], "resources": ["secrets"], "verbs": ["get"]},
        ]

        findings = detect_wildcard_permissions(rules, "test-role", "default")

        assert len(findings) == 1
        assert findings[0].severity == AuditSeverity.CRITICAL
        assert findings[0].finding_type == AuditFindingType.WILDCARD_PERMISSION
        assert "apiGroups" in findings[0].message

    @pytest.mark.requirement("FR-070")
    def test_detect_wildcard_in_resources(self) -> None:
        """Test detection of wildcard in resources."""
        from floe_core.rbac.audit import detect_wildcard_permissions
        from floe_core.schemas.rbac_audit import AuditFindingType, AuditSeverity

        rules = [
            {"apiGroups": [""], "resources": ["*"], "verbs": ["get"]},
        ]

        findings = detect_wildcard_permissions(rules, "test-role", "default")

        assert len(findings) == 1
        assert findings[0].severity == AuditSeverity.CRITICAL
        assert findings[0].finding_type == AuditFindingType.WILDCARD_PERMISSION
        assert "resources" in findings[0].message

    @pytest.mark.requirement("FR-070")
    def test_detect_wildcard_in_verbs(self) -> None:
        """Test detection of wildcard in verbs."""
        from floe_core.rbac.audit import detect_wildcard_permissions
        from floe_core.schemas.rbac_audit import AuditFindingType, AuditSeverity

        rules = [
            {"apiGroups": [""], "resources": ["secrets"], "verbs": ["*"]},
        ]

        findings = detect_wildcard_permissions(rules, "test-role", "default")

        assert len(findings) == 1
        assert findings[0].severity == AuditSeverity.CRITICAL
        assert findings[0].finding_type == AuditFindingType.WILDCARD_PERMISSION
        assert "verbs" in findings[0].message

    @pytest.mark.requirement("FR-070")
    def test_detect_multiple_wildcards(self) -> None:
        """Test detection of wildcards in multiple fields."""
        from floe_core.rbac.audit import detect_wildcard_permissions
        from floe_core.schemas.rbac_audit import AuditFindingType

        rules = [
            {"apiGroups": ["*"], "resources": ["*"], "verbs": ["*"]},
        ]

        findings = detect_wildcard_permissions(rules, "test-role", "default")

        assert len(findings) == 3
        assert all(
            f.finding_type == AuditFindingType.WILDCARD_PERMISSION for f in findings
        )

    @pytest.mark.requirement("FR-070")
    def test_no_wildcards_detected(self) -> None:
        """Test no findings when no wildcards present."""
        from floe_core.rbac.audit import detect_wildcard_permissions

        rules = [
            {
                "apiGroups": [""],
                "resources": ["secrets"],
                "verbs": ["get"],
                "resourceNames": ["my-secret"],
            },
        ]

        findings = detect_wildcard_permissions(rules, "test-role", "default")

        assert len(findings) == 0

    @pytest.mark.requirement("FR-070")
    def test_wildcard_in_multiple_rules(self) -> None:
        """Test detection across multiple rules."""
        from floe_core.rbac.audit import detect_wildcard_permissions

        rules = [
            {"apiGroups": [""], "resources": ["secrets"], "verbs": ["get"]},
            {"apiGroups": ["*"], "resources": ["pods"], "verbs": ["list"]},
            {"apiGroups": [""], "resources": ["configmaps"], "verbs": ["*"]},
        ]

        findings = detect_wildcard_permissions(rules, "test-role", "default")

        assert len(findings) == 2

    @pytest.mark.requirement("FR-070")
    def test_cluster_role_detection(self) -> None:
        """Test findings indicate ClusterRole when namespace is None."""
        from floe_core.rbac.audit import detect_wildcard_permissions

        rules = [
            {"apiGroups": ["*"], "resources": ["secrets"], "verbs": ["get"]},
        ]

        findings = detect_wildcard_permissions(rules, "cluster-admin-role", None)

        assert len(findings) == 1
        assert findings[0].resource_kind == "ClusterRole"
        assert findings[0].resource_namespace is None

    @pytest.mark.requirement("FR-070")
    def test_namespaced_role_detection(self) -> None:
        """Test findings indicate Role when namespace is provided."""
        from floe_core.rbac.audit import detect_wildcard_permissions

        rules = [
            {"apiGroups": ["*"], "resources": ["secrets"], "verbs": ["get"]},
        ]

        findings = detect_wildcard_permissions(rules, "my-role", "floe-jobs")

        assert len(findings) == 1
        assert findings[0].resource_kind == "Role"
        assert findings[0].resource_namespace == "floe-jobs"

    @pytest.mark.requirement("FR-070")
    def test_finding_includes_rule_index(self) -> None:
        """Test finding details include rule index."""
        from floe_core.rbac.audit import detect_wildcard_permissions

        rules = [
            {"apiGroups": [""], "resources": ["pods"], "verbs": ["get"]},
            {"apiGroups": [""], "resources": ["secrets"], "verbs": ["*"]},
        ]

        findings = detect_wildcard_permissions(rules, "test-role", "default")

        assert len(findings) == 1
        assert findings[0].details["rule_index"] == 1

    @pytest.mark.requirement("FR-070")
    def test_finding_includes_recommendation(self) -> None:
        """Test finding includes recommendation."""
        from floe_core.rbac.audit import detect_wildcard_permissions

        rules = [
            {"apiGroups": ["*"], "resources": ["secrets"], "verbs": ["get"]},
        ]

        findings = detect_wildcard_permissions(rules, "test-role", "default")

        assert len(findings) == 1
        assert findings[0].recommendation != ""
        assert (
            "Replace" in findings[0].recommendation
            or "specific" in findings[0].recommendation
        )

    @pytest.mark.requirement("FR-070")
    def test_empty_rules_list(self) -> None:
        """Test no findings with empty rules list."""
        from floe_core.rbac.audit import detect_wildcard_permissions

        findings = detect_wildcard_permissions([], "test-role", "default")

        assert len(findings) == 0


class TestCheckMissingResourceNames:
    """Unit tests for check_missing_resource_names function."""

    @pytest.mark.requirement("FR-070")
    def test_detect_missing_resource_names_on_secrets(self) -> None:
        """Test detection of missing resourceNames on secrets access."""
        from floe_core.rbac.audit import check_missing_resource_names
        from floe_core.schemas.rbac_audit import AuditFindingType, AuditSeverity

        rules = [
            {"resources": ["secrets"], "verbs": ["get"]},
        ]

        findings = check_missing_resource_names(rules, "test-role", "default")

        assert len(findings) == 1
        assert findings[0].severity == AuditSeverity.WARNING
        assert findings[0].finding_type == AuditFindingType.MISSING_RESOURCE_NAMES

    @pytest.mark.requirement("FR-070")
    def test_no_finding_when_resource_names_present(self) -> None:
        """Test no finding when resourceNames is specified."""
        from floe_core.rbac.audit import check_missing_resource_names

        rules = [
            {
                "resources": ["secrets"],
                "verbs": ["get"],
                "resourceNames": ["my-secret"],
            },
        ]

        findings = check_missing_resource_names(rules, "test-role", "default")

        assert len(findings) == 0

    @pytest.mark.requirement("FR-070")
    def test_no_finding_for_non_secret_resources(self) -> None:
        """Test no finding for non-secret resources."""
        from floe_core.rbac.audit import check_missing_resource_names

        rules = [
            {"resources": ["pods"], "verbs": ["get"]},
            {"resources": ["configmaps"], "verbs": ["list"]},
        ]

        findings = check_missing_resource_names(rules, "test-role", "default")

        assert len(findings) == 0

    @pytest.mark.requirement("FR-070")
    def test_finding_for_secrets_among_other_resources(self) -> None:
        """Test finding when secrets is among other resources."""
        from floe_core.rbac.audit import check_missing_resource_names

        rules = [
            {"resources": ["pods", "secrets", "configmaps"], "verbs": ["get"]},
        ]

        findings = check_missing_resource_names(rules, "test-role", "default")

        assert len(findings) == 1

    @pytest.mark.requirement("FR-070")
    def test_empty_resource_names_treated_as_missing(self) -> None:
        """Test empty resourceNames list is treated as missing."""
        from floe_core.rbac.audit import check_missing_resource_names

        rules = [
            {"resources": ["secrets"], "verbs": ["get"], "resourceNames": []},
        ]

        findings = check_missing_resource_names(rules, "test-role", "default")

        assert len(findings) == 1


class TestAuditIntegration:
    """Integration tests for audit detection functions."""

    @pytest.mark.requirement("FR-070")
    def test_combined_wildcard_and_missing_resource_names(self) -> None:
        """Test detecting both wildcards and missing resourceNames."""
        from floe_core.rbac.audit import (
            check_missing_resource_names,
            detect_wildcard_permissions,
        )
        from floe_core.schemas.rbac_audit import AuditFindingType

        rules = [
            {"apiGroups": ["*"], "resources": ["secrets"], "verbs": ["get"]},
        ]

        wildcard_findings = detect_wildcard_permissions(rules, "test-role", "default")
        resource_findings = check_missing_resource_names(rules, "test-role", "default")

        all_findings = wildcard_findings + resource_findings
        finding_types = {f.finding_type for f in all_findings}

        assert AuditFindingType.WILDCARD_PERMISSION in finding_types
        assert AuditFindingType.MISSING_RESOURCE_NAMES in finding_types

    @pytest.mark.requirement("FR-070")
    def test_compliant_role_passes_all_checks(self) -> None:
        """Test a compliant role passes all security checks."""
        from floe_core.rbac.audit import (
            check_missing_resource_names,
            detect_wildcard_permissions,
        )

        rules = [
            {
                "apiGroups": [""],
                "resources": ["secrets"],
                "verbs": ["get"],
                "resourceNames": ["snowflake-creds", "catalog-creds"],
            },
            {
                "apiGroups": ["batch"],
                "resources": ["jobs"],
                "verbs": ["create", "get", "list"],
            },
        ]

        wildcard_findings = detect_wildcard_permissions(
            rules, "compliant-role", "floe-jobs"
        )
        resource_findings = check_missing_resource_names(
            rules, "compliant-role", "floe-jobs"
        )

        assert len(wildcard_findings) == 0
        assert len(resource_findings) == 0

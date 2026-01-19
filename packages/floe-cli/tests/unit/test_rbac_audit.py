"""Unit tests for RBAC audit report generation.

Tests the RBACAuditReport model and related utilities for analyzing
cluster RBAC state and generating audit reports.

Task: T056
User Story: US6 - RBAC Audit and Validation
Requirements: FR-062
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestAuditFinding:
    """Unit tests for AuditFinding model."""

    @pytest.mark.requirement("FR-062")
    def test_audit_finding_creation(self) -> None:
        """Test AuditFinding can be created with required fields."""
        from floe_cli.commands.rbac import (
            AuditFinding,
            AuditFindingType,
            AuditSeverity,
        )

        finding = AuditFinding(
            severity=AuditSeverity.WARNING,
            finding_type=AuditFindingType.WILDCARD_PERMISSION,
            resource_kind="Role",
            resource_name="my-role",
            message="Role contains wildcard permission",
        )

        assert finding.severity == AuditSeverity.WARNING
        assert finding.finding_type == AuditFindingType.WILDCARD_PERMISSION
        assert finding.resource_kind == "Role"
        assert finding.resource_name == "my-role"
        assert finding.message == "Role contains wildcard permission"

    @pytest.mark.requirement("FR-062")
    def test_audit_finding_with_all_fields(self) -> None:
        """Test AuditFinding with all optional fields populated."""
        from floe_cli.commands.rbac import (
            AuditFinding,
            AuditFindingType,
            AuditSeverity,
        )

        finding = AuditFinding(
            severity=AuditSeverity.CRITICAL,
            finding_type=AuditFindingType.EXCESSIVE_PERMISSIONS,
            resource_kind="Role",
            resource_name="my-role",
            resource_namespace="default",
            message="Excessive permissions detected",
            recommendation="Remove unnecessary permissions",
            details={"rule_index": 0, "verbs": ["*"]},
        )

        assert finding.resource_namespace == "default"
        assert finding.recommendation == "Remove unnecessary permissions"
        assert finding.details["rule_index"] == 0

    @pytest.mark.requirement("FR-062")
    def test_audit_finding_immutable(self) -> None:
        """Test AuditFinding is immutable (frozen model)."""
        from floe_cli.commands.rbac import (
            AuditFinding,
            AuditFindingType,
            AuditSeverity,
        )

        finding = AuditFinding(
            severity=AuditSeverity.WARNING,
            finding_type=AuditFindingType.WILDCARD_PERMISSION,
            resource_kind="Role",
            resource_name="my-role",
            message="Test message",
        )

        with pytest.raises(ValidationError):
            finding.severity = AuditSeverity.CRITICAL  # type: ignore[misc]


class TestServiceAccountSummary:
    """Unit tests for ServiceAccountSummary model."""

    @pytest.mark.requirement("FR-062")
    def test_service_account_summary_creation(self) -> None:
        """Test ServiceAccountSummary can be created."""
        from floe_cli.commands.rbac import ServiceAccountSummary

        summary = ServiceAccountSummary(
            name="floe-job-runner",
            namespace="floe-jobs",
            roles=["floe-secret-reader-role"],
            secrets_access=["snowflake-creds"],
            managed_by_floe=True,
        )

        assert summary.name == "floe-job-runner"
        assert summary.namespace == "floe-jobs"
        assert "floe-secret-reader-role" in summary.roles
        assert "snowflake-creds" in summary.secrets_access
        assert summary.managed_by_floe is True

    @pytest.mark.requirement("FR-062")
    def test_service_account_summary_defaults(self) -> None:
        """Test ServiceAccountSummary has sensible defaults."""
        from floe_cli.commands.rbac import ServiceAccountSummary

        summary = ServiceAccountSummary(
            name="test-sa",
            namespace="default",
        )

        assert summary.roles == []
        assert summary.cluster_roles == []
        assert summary.secrets_access == []
        assert summary.automount_token is False
        assert summary.managed_by_floe is False


class TestNamespaceSummary:
    """Unit tests for NamespaceSummary model."""

    @pytest.mark.requirement("FR-062")
    def test_namespace_summary_creation(self) -> None:
        """Test NamespaceSummary can be created."""
        from floe_cli.commands.rbac import NamespaceSummary

        summary = NamespaceSummary(
            name="floe-jobs",
            pss_enforce="restricted",
            service_accounts=2,
            roles=3,
            role_bindings=4,
            managed_by_floe=True,
        )

        assert summary.name == "floe-jobs"
        assert summary.pss_enforce == "restricted"
        assert summary.service_accounts == 2
        assert summary.roles == 3
        assert summary.role_bindings == 4

    @pytest.mark.requirement("FR-062")
    def test_namespace_summary_defaults(self) -> None:
        """Test NamespaceSummary has sensible defaults."""
        from floe_cli.commands.rbac import NamespaceSummary

        summary = NamespaceSummary(name="default")

        assert summary.pss_enforce is None
        assert summary.service_accounts == 0
        assert summary.roles == 0
        assert summary.role_bindings == 0
        assert summary.managed_by_floe is False


class TestRBACAuditReport:
    """Unit tests for RBACAuditReport model."""

    @pytest.mark.requirement("FR-062")
    def test_audit_report_creation(self) -> None:
        """Test RBACAuditReport can be created with defaults."""
        from floe_cli.commands.rbac import RBACAuditReport

        report = RBACAuditReport(cluster_name="test-cluster")

        assert report.cluster_name == "test-cluster"
        assert report.namespaces == []
        assert report.service_accounts == []
        assert report.findings == []
        assert report.generated_at is not None

    @pytest.mark.requirement("FR-062")
    def test_audit_report_with_findings(self) -> None:
        """Test RBACAuditReport with findings included."""
        from floe_cli.commands.rbac import (
            AuditFinding,
            AuditFindingType,
            AuditSeverity,
            RBACAuditReport,
        )

        finding = AuditFinding(
            severity=AuditSeverity.WARNING,
            finding_type=AuditFindingType.MISSING_RESOURCE_NAMES,
            resource_kind="Role",
            resource_name="my-role",
            message="Missing resourceNames constraint",
        )

        report = RBACAuditReport(
            cluster_name="test-cluster",
            findings=[finding],
            total_roles=1,
        )

        assert len(report.findings) == 1
        assert report.findings[0].severity == AuditSeverity.WARNING

    @pytest.mark.requirement("FR-062")
    def test_has_critical_findings_true(self) -> None:
        """Test has_critical_findings returns True when critical findings exist."""
        from floe_cli.commands.rbac import (
            AuditFinding,
            AuditFindingType,
            AuditSeverity,
            RBACAuditReport,
        )

        critical_finding = AuditFinding(
            severity=AuditSeverity.CRITICAL,
            finding_type=AuditFindingType.WILDCARD_PERMISSION,
            resource_kind="Role",
            resource_name="bad-role",
            message="Critical issue found",
        )

        report = RBACAuditReport(
            cluster_name="test-cluster",
            findings=[critical_finding],
        )

        assert report.has_critical_findings() is True

    @pytest.mark.requirement("FR-062")
    def test_has_critical_findings_false(self) -> None:
        """Test has_critical_findings returns False when no critical findings."""
        from floe_cli.commands.rbac import (
            AuditFinding,
            AuditFindingType,
            AuditSeverity,
            RBACAuditReport,
        )

        warning_finding = AuditFinding(
            severity=AuditSeverity.WARNING,
            finding_type=AuditFindingType.MISSING_RESOURCE_NAMES,
            resource_kind="Role",
            resource_name="my-role",
            message="Warning issue",
        )

        report = RBACAuditReport(
            cluster_name="test-cluster",
            findings=[warning_finding],
        )

        assert report.has_critical_findings() is False

    @pytest.mark.requirement("FR-062")
    def test_has_warnings_true(self) -> None:
        """Test has_warnings returns True for warning level and above."""
        from floe_cli.commands.rbac import (
            AuditFinding,
            AuditFindingType,
            AuditSeverity,
            RBACAuditReport,
        )

        warning_finding = AuditFinding(
            severity=AuditSeverity.WARNING,
            finding_type=AuditFindingType.MISSING_RESOURCE_NAMES,
            resource_kind="Role",
            resource_name="my-role",
            message="Warning issue",
        )

        report = RBACAuditReport(
            cluster_name="test-cluster",
            findings=[warning_finding],
        )

        assert report.has_warnings() is True

    @pytest.mark.requirement("FR-062")
    def test_has_warnings_false(self) -> None:
        """Test has_warnings returns False for info-only findings."""
        from floe_cli.commands.rbac import (
            AuditFinding,
            AuditFindingType,
            AuditSeverity,
            RBACAuditReport,
        )

        info_finding = AuditFinding(
            severity=AuditSeverity.INFO,
            finding_type=AuditFindingType.UNMANAGED_RESOURCE,
            resource_kind="ServiceAccount",
            resource_name="unmanaged-sa",
            message="Informational finding",
        )

        report = RBACAuditReport(
            cluster_name="test-cluster",
            findings=[info_finding],
        )

        assert report.has_warnings() is False

    @pytest.mark.requirement("FR-062")
    def test_findings_by_severity(self) -> None:
        """Test findings can be grouped by severity."""
        from floe_cli.commands.rbac import (
            AuditFinding,
            AuditFindingType,
            AuditSeverity,
            RBACAuditReport,
        )

        findings = [
            AuditFinding(
                severity=AuditSeverity.CRITICAL,
                finding_type=AuditFindingType.WILDCARD_PERMISSION,
                resource_kind="Role",
                resource_name="role-1",
                message="Critical 1",
            ),
            AuditFinding(
                severity=AuditSeverity.WARNING,
                finding_type=AuditFindingType.MISSING_RESOURCE_NAMES,
                resource_kind="Role",
                resource_name="role-2",
                message="Warning 1",
            ),
            AuditFinding(
                severity=AuditSeverity.CRITICAL,
                finding_type=AuditFindingType.WILDCARD_PERMISSION,
                resource_kind="Role",
                resource_name="role-3",
                message="Critical 2",
            ),
        ]

        report = RBACAuditReport(
            cluster_name="test-cluster",
            findings=findings,
        )

        by_severity = report.findings_by_severity()

        assert len(by_severity[AuditSeverity.CRITICAL]) == 2
        assert len(by_severity[AuditSeverity.WARNING]) == 1
        assert len(by_severity[AuditSeverity.ERROR]) == 0
        assert len(by_severity[AuditSeverity.INFO]) == 0

    @pytest.mark.requirement("FR-062")
    def test_audit_report_serializable(self) -> None:
        """Test RBACAuditReport is JSON serializable."""
        import json

        from floe_cli.commands.rbac import (
            NamespaceSummary,
            RBACAuditReport,
            ServiceAccountSummary,
        )

        report = RBACAuditReport(
            cluster_name="test-cluster",
            namespaces=[NamespaceSummary(name="default")],
            service_accounts=[ServiceAccountSummary(name="test-sa", namespace="default")],
            total_service_accounts=1,
            total_roles=2,
        )

        # Should not raise
        json_str = report.model_dump_json()
        assert "test-cluster" in json_str
        assert "test-sa" in json_str

        # Can also use standard json.dumps
        data = report.model_dump(mode="json")
        json_str2 = json.dumps(data)
        assert "test-cluster" in json_str2


class TestAuditReportWithSummaries:
    """Integration tests for audit report with full data."""

    @pytest.mark.requirement("FR-062")
    def test_complete_audit_report(self) -> None:
        """Test creating a complete audit report with all data."""
        from floe_cli.commands.rbac import (
            AuditFinding,
            AuditFindingType,
            AuditSeverity,
            NamespaceSummary,
            RBACAuditReport,
            ServiceAccountSummary,
        )

        namespaces = [
            NamespaceSummary(
                name="floe-jobs",
                pss_enforce="restricted",
                service_accounts=2,
                roles=3,
                role_bindings=4,
                managed_by_floe=True,
            ),
            NamespaceSummary(
                name="floe-platform",
                pss_enforce="baseline",
                service_accounts=1,
                roles=2,
                role_bindings=2,
                managed_by_floe=True,
            ),
        ]

        service_accounts = [
            ServiceAccountSummary(
                name="floe-job-runner",
                namespace="floe-jobs",
                roles=["floe-secret-reader-role"],
                secrets_access=["snowflake-creds", "catalog-creds"],
                managed_by_floe=True,
            ),
            ServiceAccountSummary(
                name="floe-dagster",
                namespace="floe-platform",
                roles=["floe-job-creator-role"],
                cluster_roles=["floe-namespace-reader"],
                managed_by_floe=True,
            ),
        ]

        findings = [
            AuditFinding(
                severity=AuditSeverity.INFO,
                finding_type=AuditFindingType.UNMANAGED_RESOURCE,
                resource_kind="ServiceAccount",
                resource_name="default",
                resource_namespace="default",
                message="Unmanaged default service account",
            ),
        ]

        report = RBACAuditReport(
            cluster_name="production-cluster",
            namespaces=namespaces,
            service_accounts=service_accounts,
            findings=findings,
            total_service_accounts=3,
            total_roles=5,
            total_role_bindings=6,
            floe_managed_count=10,
        )

        assert report.cluster_name == "production-cluster"
        assert len(report.namespaces) == 2
        assert len(report.service_accounts) == 2
        assert len(report.findings) == 1
        assert report.total_service_accounts == 3
        assert report.floe_managed_count == 10

        # Validate findings methods work
        assert report.has_critical_findings() is False
        assert report.has_warnings() is False  # Only INFO finding

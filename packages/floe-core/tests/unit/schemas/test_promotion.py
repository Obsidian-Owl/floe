"""Unit tests for promotion schemas.

Tests for Epic 8C (Promotion Lifecycle) schemas including:
- PromotionGate enum
- GateStatus enum
- AuditBackend enum
- GateResult model
- EnvironmentConfig model
- PromotionConfig model
- PromotionRecord model
- RollbackRecord model
"""

from __future__ import annotations

import pytest


class TestPromotionGate:
    """Tests for PromotionGate enum."""

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_gate_enum_values(self) -> None:
        """Test PromotionGate has all required gate types.

        Validates that the enum includes all gate types specified in the data model:
        - policy_compliance (mandatory, always runs)
        - tests
        - security_scan
        - cost_analysis
        - performance_baseline
        """
        from floe_core.schemas.promotion import PromotionGate

        assert PromotionGate.POLICY_COMPLIANCE == "policy_compliance"
        assert PromotionGate.TESTS == "tests"
        assert PromotionGate.SECURITY_SCAN == "security_scan"
        assert PromotionGate.COST_ANALYSIS == "cost_analysis"
        assert PromotionGate.PERFORMANCE_BASELINE == "performance_baseline"

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_gate_is_string_enum(self) -> None:
        """Test PromotionGate inherits from str for JSON serialization."""
        from floe_core.schemas.promotion import PromotionGate

        # String enums serialize to their string value
        assert isinstance(PromotionGate.POLICY_COMPLIANCE, str)
        # .value gives the string value for JSON serialization
        assert PromotionGate.POLICY_COMPLIANCE.value == "policy_compliance"

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_gate_has_five_members(self) -> None:
        """Test PromotionGate has exactly 5 gate types."""
        from floe_core.schemas.promotion import PromotionGate

        assert len(PromotionGate) == 5

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_gate_membership(self) -> None:
        """Test membership checking works correctly."""
        from floe_core.schemas.promotion import PromotionGate

        assert "policy_compliance" in [g.value for g in PromotionGate]
        assert "invalid_gate" not in [g.value for g in PromotionGate]


class TestGateStatus:
    """Tests for GateStatus enum."""

    @pytest.mark.requirement("8C-FR-002")
    def test_gate_status_enum_values(self) -> None:
        """Test GateStatus has all required status values.

        Validates that the enum includes all status types:
        - passed: Gate validation succeeded
        - failed: Gate validation failed (blocks promotion)
        - skipped: Gate not configured for this environment
        - warning: Gate passed with warnings (non-blocking)
        """
        from floe_core.schemas.promotion import GateStatus

        assert GateStatus.PASSED == "passed"
        assert GateStatus.FAILED == "failed"
        assert GateStatus.SKIPPED == "skipped"
        assert GateStatus.WARNING == "warning"

    @pytest.mark.requirement("8C-FR-002")
    def test_gate_status_is_string_enum(self) -> None:
        """Test GateStatus inherits from str for JSON serialization."""
        from floe_core.schemas.promotion import GateStatus

        assert isinstance(GateStatus.PASSED, str)
        assert GateStatus.PASSED.value == "passed"

    @pytest.mark.requirement("8C-FR-002")
    def test_gate_status_has_four_members(self) -> None:
        """Test GateStatus has exactly 4 status values."""
        from floe_core.schemas.promotion import GateStatus

        assert len(GateStatus) == 4

    @pytest.mark.requirement("8C-FR-002")
    def test_gate_status_values_are_lowercase(self) -> None:
        """Test all GateStatus values are lowercase strings."""
        from floe_core.schemas.promotion import GateStatus

        for status in GateStatus:
            assert status.value == status.value.lower()
            assert status.value.isalpha()


class TestAuditBackend:
    """Tests for AuditBackend enum."""

    @pytest.mark.requirement("8C-FR-003")
    def test_audit_backend_enum_values(self) -> None:
        """Test AuditBackend has all required backend types.

        Validates that the enum includes all backend types:
        - oci: OCI annotations only (default)
        - s3: S3 append-only log
        - database: Database storage
        """
        from floe_core.schemas.promotion import AuditBackend

        assert AuditBackend.OCI == "oci"
        assert AuditBackend.S3 == "s3"
        assert AuditBackend.DATABASE == "database"

    @pytest.mark.requirement("8C-FR-003")
    def test_audit_backend_is_string_enum(self) -> None:
        """Test AuditBackend inherits from str for JSON serialization."""
        from floe_core.schemas.promotion import AuditBackend

        assert isinstance(AuditBackend.OCI, str)
        assert AuditBackend.OCI.value == "oci"

    @pytest.mark.requirement("8C-FR-003")
    def test_audit_backend_has_three_members(self) -> None:
        """Test AuditBackend has exactly 3 backend types."""
        from floe_core.schemas.promotion import AuditBackend

        assert len(AuditBackend) == 3


class TestSecurityScanResult:
    """Tests for SecurityScanResult Pydantic model."""

    @pytest.mark.requirement("FR-056")
    def test_security_scan_result_valid(self) -> None:
        """Test SecurityScanResult creation with valid data."""
        from floe_core.schemas.promotion import SecurityScanResult

        result = SecurityScanResult(
            critical_count=2,
            high_count=5,
            medium_count=10,
            low_count=20,
            blocking_cves=["CVE-2024-1234", "CVE-2024-5678"],
            ignored_unfixed=3,
        )
        assert result.critical_count == 2
        assert result.high_count == 5
        assert result.medium_count == 10
        assert result.low_count == 20
        assert result.blocking_cves == ["CVE-2024-1234", "CVE-2024-5678"]
        assert result.ignored_unfixed == 3

    @pytest.mark.requirement("FR-056")
    def test_security_scan_result_defaults(self) -> None:
        """Test SecurityScanResult with default values."""
        from floe_core.schemas.promotion import SecurityScanResult

        result = SecurityScanResult(
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
        )
        assert result.blocking_cves == []
        assert result.ignored_unfixed == 0

    @pytest.mark.requirement("FR-056")
    def test_security_scan_result_total_vulnerabilities(self) -> None:
        """Test SecurityScanResult total_vulnerabilities property."""
        from floe_core.schemas.promotion import SecurityScanResult

        result = SecurityScanResult(
            critical_count=1,
            high_count=2,
            medium_count=3,
            low_count=4,
        )
        assert result.total_vulnerabilities == 10

    @pytest.mark.requirement("FR-056")
    def test_security_scan_result_negative_count_rejected(self) -> None:
        """Test SecurityScanResult rejects negative counts."""
        from pydantic import ValidationError

        from floe_core.schemas.promotion import SecurityScanResult

        with pytest.raises(ValidationError):
            SecurityScanResult(
                critical_count=-1,
                high_count=0,
                medium_count=0,
                low_count=0,
            )


class TestGateResult:
    """Tests for GateResult Pydantic model."""

    @pytest.mark.requirement("8C-FR-004")
    def test_gate_result_valid_passed(self) -> None:
        """Test GateResult creation for passed gate."""
        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        result = GateResult(
            gate=PromotionGate.TESTS,
            status=GateStatus.PASSED,
            duration_ms=1500,
        )
        assert result.gate == PromotionGate.TESTS
        assert result.status == GateStatus.PASSED
        assert result.duration_ms == 1500
        assert result.error is None
        assert result.details == {}

    @pytest.mark.requirement("8C-FR-004")
    def test_gate_result_valid_failed_with_error(self) -> None:
        """Test GateResult creation for failed gate with error message."""
        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        result = GateResult(
            gate=PromotionGate.SECURITY_SCAN,
            status=GateStatus.FAILED,
            duration_ms=5000,
            error="Found 2 critical vulnerabilities",
        )
        assert result.gate == PromotionGate.SECURITY_SCAN
        assert result.status == GateStatus.FAILED
        assert result.error == "Found 2 critical vulnerabilities"

    @pytest.mark.requirement("8C-FR-004")
    def test_gate_result_with_security_summary(self) -> None:
        """Test GateResult with security_summary for security gate."""
        from floe_core.schemas.promotion import (
            GateResult,
            GateStatus,
            PromotionGate,
            SecurityScanResult,
        )

        security_summary = SecurityScanResult(
            critical_count=2,
            high_count=3,
            medium_count=5,
            low_count=10,
            blocking_cves=["CVE-2024-1234", "CVE-2024-5678"],
        )
        result = GateResult(
            gate=PromotionGate.SECURITY_SCAN,
            status=GateStatus.FAILED,
            duration_ms=10000,
            error="Blocked by CVEs",
            security_summary=security_summary,
        )
        assert result.security_summary is not None
        assert result.security_summary.critical_count == 2
        assert len(result.security_summary.blocking_cves) == 2

    @pytest.mark.requirement("8C-FR-004")
    def test_gate_result_negative_duration_rejected(self) -> None:
        """Test GateResult rejects negative duration."""
        from pydantic import ValidationError

        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        with pytest.raises(ValidationError):
            GateResult(
                gate=PromotionGate.TESTS,
                status=GateStatus.PASSED,
                duration_ms=-100,
            )

    @pytest.mark.requirement("8C-FR-004")
    def test_gate_result_with_details(self) -> None:
        """Test GateResult with custom details dict."""
        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        result = GateResult(
            gate=PromotionGate.COST_ANALYSIS,
            status=GateStatus.WARNING,
            duration_ms=2000,
            details={"estimated_cost": 150.50, "budget_limit": 200.00},
        )
        assert result.details["estimated_cost"] == 150.50

    @pytest.mark.requirement("8C-FR-004")
    def test_gate_result_frozen(self) -> None:
        """Test GateResult is immutable (frozen)."""
        from pydantic import ValidationError

        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        result = GateResult(
            gate=PromotionGate.TESTS,
            status=GateStatus.PASSED,
            duration_ms=1000,
        )
        with pytest.raises(ValidationError):
            result.status = GateStatus.FAILED  # type: ignore[misc]


class TestAuthorizationConfig:
    """Tests for AuthorizationConfig Pydantic model."""

    @pytest.mark.requirement("FR-046")
    def test_authorization_config_valid(self) -> None:
        """Test AuthorizationConfig creation with valid data."""
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=["platform-admins", "release-managers"],
            allowed_operators=["admin@example.com"],
            separation_of_duties=True,
        )
        assert config.allowed_groups == ["platform-admins", "release-managers"]
        assert config.allowed_operators == ["admin@example.com"]
        assert config.separation_of_duties is True

    @pytest.mark.requirement("FR-046")
    def test_authorization_config_defaults(self) -> None:
        """Test AuthorizationConfig with default values allows all."""
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig()
        assert config.allowed_groups is None
        assert config.allowed_operators is None
        assert config.separation_of_duties is False

    @pytest.mark.requirement("FR-047")
    def test_authorization_config_separation_of_duties(self) -> None:
        """Test separation_of_duties prevents same operator consecutive promotions."""
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(separation_of_duties=True)
        assert config.separation_of_duties is True


class TestEnvironmentLock:
    """Tests for EnvironmentLock Pydantic model."""

    @pytest.mark.requirement("FR-035")
    def test_environment_lock_locked(self) -> None:
        """Test EnvironmentLock in locked state."""
        from datetime import datetime, timezone

        from floe_core.schemas.promotion import EnvironmentLock

        lock = EnvironmentLock(
            locked=True,
            reason="Incident #123 - Database migration",
            locked_by="sre@example.com",
            locked_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        )
        assert lock.locked is True
        assert lock.reason == "Incident #123 - Database migration"
        assert lock.locked_by == "sre@example.com"

    @pytest.mark.requirement("FR-035")
    def test_environment_lock_unlocked(self) -> None:
        """Test EnvironmentLock in unlocked state."""
        from floe_core.schemas.promotion import EnvironmentLock

        lock = EnvironmentLock(locked=False)
        assert lock.locked is False
        assert lock.reason is None
        assert lock.locked_by is None
        assert lock.locked_at is None


class TestWebhookConfig:
    """Tests for WebhookConfig Pydantic model."""

    @pytest.mark.requirement("FR-040")
    def test_webhook_config_valid(self) -> None:
        """Test WebhookConfig creation with valid data."""
        from floe_core.schemas.promotion import WebhookConfig

        config = WebhookConfig(
            url="https://hooks.slack.com/services/T00/B00/XXX",
            events=["promote", "rollback"],
        )
        assert config.url == "https://hooks.slack.com/services/T00/B00/XXX"
        assert config.events == ["promote", "rollback"]
        assert config.timeout_seconds == 30
        assert config.retry_count == 3

    @pytest.mark.requirement("FR-040")
    def test_webhook_config_with_headers(self) -> None:
        """Test WebhookConfig with custom headers."""
        from floe_core.schemas.promotion import WebhookConfig

        config = WebhookConfig(
            url="https://api.pagerduty.com/webhooks",
            events=["rollback"],
            headers={"Authorization": "Token abc123"},
            timeout_seconds=60,
            retry_count=5,
        )
        assert config.headers == {"Authorization": "Token abc123"}
        assert config.timeout_seconds == 60
        assert config.retry_count == 5

    @pytest.mark.requirement("FR-044")
    def test_webhook_config_invalid_event_rejected(self) -> None:
        """Test WebhookConfig rejects invalid event types."""
        from pydantic import ValidationError

        from floe_core.schemas.promotion import WebhookConfig

        with pytest.raises(ValidationError):
            WebhookConfig(
                url="https://example.com/webhook",
                events=["invalid_event"],
            )


class TestSecurityGateConfig:
    """Tests for SecurityGateConfig Pydantic model."""

    @pytest.mark.requirement("FR-054")
    def test_security_gate_config_valid(self) -> None:
        """Test SecurityGateConfig creation with valid data."""
        from floe_core.schemas.promotion import SecurityGateConfig

        config = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
        )
        assert config.command == "trivy image ${ARTIFACT_REF} --format json"
        assert config.block_on_severity == ["CRITICAL", "HIGH"]
        assert config.ignore_unfixed is False
        assert config.scanner_format == "trivy"
        assert config.timeout_seconds == 600

    @pytest.mark.requirement("FR-055")
    def test_security_gate_config_custom_severity(self) -> None:
        """Test SecurityGateConfig with custom severity blocking."""
        from floe_core.schemas.promotion import SecurityGateConfig

        config = SecurityGateConfig(
            command="grype ${ARTIFACT_REF} -o json",
            block_on_severity=["CRITICAL"],
            ignore_unfixed=True,
            scanner_format="grype",
        )
        assert config.block_on_severity == ["CRITICAL"]
        assert config.ignore_unfixed is True
        assert config.scanner_format == "grype"

    @pytest.mark.requirement("FR-057")
    def test_security_gate_config_invalid_severity_rejected(self) -> None:
        """Test SecurityGateConfig rejects invalid severity levels."""
        from pydantic import ValidationError

        from floe_core.schemas.promotion import SecurityGateConfig

        with pytest.raises(ValidationError):
            SecurityGateConfig(
                command="trivy image ${ARTIFACT_REF}",
                block_on_severity=["INVALID_SEVERITY"],
            )

    @pytest.mark.requirement("FR-054")
    def test_security_gate_config_invalid_scanner_rejected(self) -> None:
        """Test SecurityGateConfig rejects invalid scanner formats."""
        from pydantic import ValidationError

        from floe_core.schemas.promotion import SecurityGateConfig

        with pytest.raises(ValidationError):
            SecurityGateConfig(
                command="scanner ${ARTIFACT_REF}",
                scanner_format="invalid_scanner",
            )

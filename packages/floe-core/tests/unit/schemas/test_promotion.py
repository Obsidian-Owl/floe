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
    """Tests for AuthorizationConfig Pydantic model.

    Tests FR-046 (environment-specific authorization rules) and
    FR-047 (group-based access control).
    """

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

    @pytest.mark.requirement("FR-046")
    def test_authorization_config_frozen(self) -> None:
        """Test AuthorizationConfig is immutable (frozen)."""
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=["platform-admins"],
        )
        with pytest.raises(TypeError):  # Frozen model raises TypeError
            config.separation_of_duties = True  # type: ignore[misc]

    @pytest.mark.requirement("FR-046")
    def test_authorization_config_extra_forbid(self) -> None:
        """Test AuthorizationConfig rejects unknown fields."""
        from pydantic import ValidationError

        from floe_core.schemas.promotion import AuthorizationConfig

        with pytest.raises(ValidationError, match="extra"):
            AuthorizationConfig(
                allowed_groups=["admins"],
                unknown_field="value",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("FR-047")
    def test_authorization_config_groups_only(self) -> None:
        """Test AuthorizationConfig with only allowed_groups."""
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=["platform-admins", "release-managers", "devops"],
        )
        assert config.allowed_groups == ["platform-admins", "release-managers", "devops"]
        assert config.allowed_operators is None
        assert config.separation_of_duties is False

    @pytest.mark.requirement("FR-046")
    def test_authorization_config_operators_only(self) -> None:
        """Test AuthorizationConfig with only allowed_operators."""
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_operators=["alice@example.com", "bob@example.com"],
        )
        assert config.allowed_groups is None
        assert config.allowed_operators == ["alice@example.com", "bob@example.com"]

    @pytest.mark.requirement("FR-047")
    def test_authorization_config_empty_groups_list(self) -> None:
        """Test AuthorizationConfig with empty groups list."""
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=[],
            allowed_operators=None,
        )
        # Empty list is different from None
        assert config.allowed_groups == []
        assert config.allowed_operators is None

    @pytest.mark.requirement("FR-046")
    def test_authorization_config_empty_operators_list(self) -> None:
        """Test AuthorizationConfig with empty operators list."""
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=None,
            allowed_operators=[],
        )
        assert config.allowed_groups is None
        assert config.allowed_operators == []

    @pytest.mark.requirement("FR-047")
    def test_authorization_config_combined_groups_and_operators(self) -> None:
        """Test AuthorizationConfig with both groups and operators (OR semantics)."""
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=["admins"],
            allowed_operators=["special-user@example.com"],
            separation_of_duties=True,
        )
        # Both are set - authorization should check either
        assert config.allowed_groups == ["admins"]
        assert config.allowed_operators == ["special-user@example.com"]
        assert config.separation_of_duties is True

    @pytest.mark.requirement("FR-046")
    def test_authorization_config_json_serialization(self) -> None:
        """Test AuthorizationConfig serializes to JSON correctly."""
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=["platform-admins"],
            separation_of_duties=True,
        )
        json_data = config.model_dump()
        assert json_data == {
            "allowed_groups": ["platform-admins"],
            "allowed_operators": None,
            "separation_of_duties": True,
        }

    @pytest.mark.requirement("FR-046")
    def test_authorization_config_from_dict(self) -> None:
        """Test AuthorizationConfig creation from dict."""
        from floe_core.schemas.promotion import AuthorizationConfig

        data = {
            "allowed_groups": ["release-managers"],
            "allowed_operators": ["admin@example.com"],
            "separation_of_duties": False,
        }
        config = AuthorizationConfig.model_validate(data)
        assert config.allowed_groups == ["release-managers"]
        assert config.allowed_operators == ["admin@example.com"]
        assert config.separation_of_duties is False

    @pytest.mark.requirement("FR-046")
    def test_authorization_config_json_schema_export(self) -> None:
        """Test AuthorizationConfig JSON schema includes all fields."""
        from floe_core.schemas.promotion import AuthorizationConfig

        schema = AuthorizationConfig.model_json_schema()
        properties = schema.get("properties", {})
        assert "allowed_groups" in properties
        assert "allowed_operators" in properties
        assert "separation_of_duties" in properties


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


class TestEnvironmentConfig:
    """Tests for EnvironmentConfig Pydantic model."""

    @pytest.mark.requirement("8C-FR-005")
    def test_environment_config_valid(self) -> None:
        """Test EnvironmentConfig creation with valid data."""
        from floe_core.schemas.promotion import EnvironmentConfig, PromotionGate

        config = EnvironmentConfig(
            name="staging",
            gates={
                PromotionGate.POLICY_COMPLIANCE: True,
                PromotionGate.TESTS: True,
                PromotionGate.SECURITY_SCAN: False,
            },
        )
        assert config.name == "staging"
        assert config.gates[PromotionGate.POLICY_COMPLIANCE] is True
        assert config.gates[PromotionGate.TESTS] is True

    @pytest.mark.requirement("8C-FR-005")
    def test_environment_config_policy_compliance_always_true(self) -> None:
        """Test EnvironmentConfig enforces policy_compliance is always true."""
        from pydantic import ValidationError

        from floe_core.schemas.promotion import EnvironmentConfig, PromotionGate

        with pytest.raises(ValidationError, match="policy_compliance"):
            EnvironmentConfig(
                name="staging",
                gates={
                    PromotionGate.POLICY_COMPLIANCE: False,  # Not allowed!
                },
            )

    @pytest.mark.requirement("8C-FR-005")
    def test_environment_config_with_authorization(self) -> None:
        """Test EnvironmentConfig with authorization config."""
        from floe_core.schemas.promotion import (
            AuthorizationConfig,
            EnvironmentConfig,
            PromotionGate,
        )

        config = EnvironmentConfig(
            name="prod",
            gates={PromotionGate.POLICY_COMPLIANCE: True},
            authorization=AuthorizationConfig(
                allowed_groups=["platform-admins"],
                separation_of_duties=True,
            ),
        )
        assert config.authorization is not None
        assert config.authorization.allowed_groups == ["platform-admins"]

    @pytest.mark.requirement("8C-FR-005")
    def test_environment_config_with_lock(self) -> None:
        """Test EnvironmentConfig with environment lock."""
        from floe_core.schemas.promotion import (
            EnvironmentConfig,
            EnvironmentLock,
            PromotionGate,
        )

        config = EnvironmentConfig(
            name="prod",
            gates={PromotionGate.POLICY_COMPLIANCE: True},
            lock=EnvironmentLock(locked=True, reason="Maintenance"),
        )
        assert config.lock is not None
        assert config.lock.locked is True

    @pytest.mark.requirement("8C-FR-005")
    def test_environment_config_gate_timeout(self) -> None:
        """Test EnvironmentConfig with custom gate timeout."""
        from floe_core.schemas.promotion import EnvironmentConfig, PromotionGate

        config = EnvironmentConfig(
            name="prod",
            gates={PromotionGate.POLICY_COMPLIANCE: True},
            gate_timeout_seconds=600,
        )
        assert config.gate_timeout_seconds == 600

    @pytest.mark.requirement("8C-FR-005")
    def test_environment_config_invalid_timeout_rejected(self) -> None:
        """Test EnvironmentConfig rejects invalid timeout values."""
        from pydantic import ValidationError

        from floe_core.schemas.promotion import EnvironmentConfig, PromotionGate

        with pytest.raises(ValidationError):
            EnvironmentConfig(
                name="prod",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
                gate_timeout_seconds=10,  # Below minimum of 30
            )


class TestPromotionConfig:
    """Tests for PromotionConfig Pydantic model."""

    @pytest.mark.requirement("8C-FR-006")
    def test_promotion_config_default_environments(self) -> None:
        """Test PromotionConfig creates default [dev, staging, prod] environments."""
        from floe_core.schemas.promotion import PromotionConfig

        config = PromotionConfig()
        assert len(config.environments) == 3
        assert config.environments[0].name == "dev"
        assert config.environments[1].name == "staging"
        assert config.environments[2].name == "prod"

    @pytest.mark.requirement("8C-FR-006")
    def test_promotion_config_custom_environments(self) -> None:
        """Test PromotionConfig with custom environments."""
        from floe_core.schemas.promotion import (
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        config = PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="test",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                ),
                EnvironmentConfig(
                    name="production",
                    gates={
                        PromotionGate.POLICY_COMPLIANCE: True,
                        PromotionGate.TESTS: True,
                    },
                ),
            ],
        )
        assert len(config.environments) == 2
        assert config.environments[0].name == "test"
        assert config.environments[1].name == "production"

    @pytest.mark.requirement("8C-FR-006")
    def test_promotion_config_with_webhooks(self) -> None:
        """Test PromotionConfig with webhook configuration."""
        from floe_core.schemas.promotion import PromotionConfig, WebhookConfig

        config = PromotionConfig(
            webhooks=[
                WebhookConfig(
                    url="https://hooks.slack.com/services/T00/B00/XXX",
                    events=["promote", "rollback"],
                ),
            ],
        )
        assert config.webhooks is not None
        assert len(config.webhooks) == 1
        assert config.webhooks[0].url == "https://hooks.slack.com/services/T00/B00/XXX"

    @pytest.mark.requirement("8C-FR-006")
    def test_promotion_config_audit_backend(self) -> None:
        """Test PromotionConfig with custom audit backend."""
        from floe_core.schemas.promotion import AuditBackend, PromotionConfig

        config = PromotionConfig(audit_backend=AuditBackend.S3)
        assert config.audit_backend == AuditBackend.S3

    @pytest.mark.requirement("8C-FR-006")
    def test_promotion_config_default_timeout(self) -> None:
        """Test PromotionConfig default gate timeout."""
        from floe_core.schemas.promotion import PromotionConfig

        config = PromotionConfig()
        assert config.default_timeout_seconds == 300

    @pytest.mark.requirement("8C-FR-006")
    def test_promotion_config_unique_environment_names(self) -> None:
        """Test PromotionConfig enforces unique environment names."""
        from pydantic import ValidationError

        from floe_core.schemas.promotion import (
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        with pytest.raises(ValidationError, match="unique"):
            PromotionConfig(
                environments=[
                    EnvironmentConfig(
                        name="prod",
                        gates={PromotionGate.POLICY_COMPLIANCE: True},
                    ),
                    EnvironmentConfig(
                        name="prod",  # Duplicate!
                        gates={PromotionGate.POLICY_COMPLIANCE: True},
                    ),
                ],
            )


class TestRollbackImpactAnalysis:
    """Tests for RollbackImpactAnalysis Pydantic model."""

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_impact_analysis_valid(self) -> None:
        """Test RollbackImpactAnalysis with valid data."""
        from floe_core.schemas.promotion import RollbackImpactAnalysis

        analysis = RollbackImpactAnalysis(
            breaking_changes=["Schema change: removed column 'old_field'"],
            affected_products=["dashboard-v2", "api-service"],
            recommendations=["Verify API consumers are updated"],
        )
        assert len(analysis.breaking_changes) == 1
        assert len(analysis.affected_products) == 2
        assert len(analysis.recommendations) == 1
        assert analysis.estimated_downtime is None

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_impact_analysis_with_downtime(self) -> None:
        """Test RollbackImpactAnalysis with estimated downtime."""
        from floe_core.schemas.promotion import RollbackImpactAnalysis

        analysis = RollbackImpactAnalysis(
            breaking_changes=[],
            affected_products=[],
            recommendations=[],
            estimated_downtime="~5 minutes",
        )
        assert analysis.estimated_downtime == "~5 minutes"

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_impact_analysis_frozen(self) -> None:
        """Test RollbackImpactAnalysis is immutable (frozen)."""
        from floe_core.schemas.promotion import RollbackImpactAnalysis

        analysis = RollbackImpactAnalysis(
            breaking_changes=[],
            affected_products=[],
            recommendations=[],
        )
        with pytest.raises(TypeError):  # Frozen model raises TypeError
            analysis.estimated_downtime = "10 minutes"  # type: ignore[misc]


class TestPromotionRecord:
    """Tests for PromotionRecord Pydantic model."""

    @pytest.mark.requirement("8C-FR-007")
    def test_promotion_record_valid(self) -> None:
        """Test PromotionRecord with valid data."""
        from datetime import datetime, timezone
        from uuid import UUID

        from floe_core.schemas.promotion import (
            GateResult,
            GateStatus,
            PromotionGate,
            PromotionRecord,
        )

        record = PromotionRecord(
            promotion_id=UUID("12345678-1234-5678-1234-567812345678"),
            artifact_digest="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            artifact_tag="v1.2.3-dev",
            source_environment="dev",
            target_environment="staging",
            gate_results=[
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                ),
            ],
            signature_verified=True,
            operator="user@example.com",
            promoted_at=datetime.now(timezone.utc),
            dry_run=False,
            trace_id="abc123",
            authorization_passed=True,
        )
        assert record.promotion_id == UUID("12345678-1234-5678-1234-567812345678")
        assert record.source_environment == "dev"
        assert record.target_environment == "staging"
        assert record.signature_verified is True

    @pytest.mark.requirement("8C-FR-007")
    def test_promotion_record_with_signature_status(self) -> None:
        """Test PromotionRecord with VerificationResult."""
        from datetime import datetime, timezone
        from uuid import UUID

        from floe_core.schemas.promotion import (
            GateResult,
            GateStatus,
            PromotionGate,
            PromotionRecord,
        )
        from floe_core.schemas.signing import VerificationResult

        verification = VerificationResult(
            status="valid",
            signer_identity="user@example.com",
            verified_at=datetime.now(timezone.utc),
        )
        record = PromotionRecord(
            promotion_id=UUID("12345678-1234-5678-1234-567812345678"),
            artifact_digest="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            artifact_tag="v1.2.3-dev",
            source_environment="dev",
            target_environment="staging",
            gate_results=[
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                ),
            ],
            signature_verified=True,
            signature_status=verification,
            operator="user@example.com",
            promoted_at=datetime.now(timezone.utc),
            dry_run=False,
            trace_id="abc123",
            authorization_passed=True,
        )
        assert record.signature_status is not None
        assert record.signature_status.status == "valid"

    @pytest.mark.requirement("8C-FR-007")
    def test_promotion_record_dry_run(self) -> None:
        """Test PromotionRecord with dry_run=True."""
        from datetime import datetime, timezone
        from uuid import UUID

        from floe_core.schemas.promotion import (
            GateResult,
            GateStatus,
            PromotionGate,
            PromotionRecord,
        )

        record = PromotionRecord(
            promotion_id=UUID("12345678-1234-5678-1234-567812345678"),
            artifact_digest="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            artifact_tag="v1.2.3-dev",
            source_environment="dev",
            target_environment="staging",
            gate_results=[
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.FAILED,  # Allowed in dry run
                    duration_ms=100,
                    error="Policy violation",
                ),
            ],
            signature_verified=False,
            operator="user@example.com",
            promoted_at=datetime.now(timezone.utc),
            dry_run=True,
            trace_id="abc123",
            authorization_passed=True,
        )
        assert record.dry_run is True
        assert record.gate_results[0].status == GateStatus.FAILED

    @pytest.mark.requirement("8C-FR-007")
    def test_promotion_record_with_authorization_via(self) -> None:
        """Test PromotionRecord with authorized_via field."""
        from datetime import datetime, timezone
        from uuid import UUID

        from floe_core.schemas.promotion import (
            GateResult,
            GateStatus,
            PromotionGate,
            PromotionRecord,
        )

        record = PromotionRecord(
            promotion_id=UUID("12345678-1234-5678-1234-567812345678"),
            artifact_digest="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            artifact_tag="v1.2.3-dev",
            source_environment="dev",
            target_environment="staging",
            gate_results=[
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                ),
            ],
            signature_verified=True,
            operator="user@example.com",
            promoted_at=datetime.now(timezone.utc),
            dry_run=False,
            trace_id="abc123",
            authorization_passed=True,
            authorized_via="group:platform-admins",
        )
        assert record.authorized_via == "group:platform-admins"

    @pytest.mark.requirement("8C-FR-007")
    def test_promotion_record_invalid_digest_format(self) -> None:
        """Test PromotionRecord rejects invalid artifact digest format."""
        from datetime import datetime, timezone
        from uuid import UUID

        from pydantic import ValidationError

        from floe_core.schemas.promotion import (
            GateResult,
            GateStatus,
            PromotionGate,
            PromotionRecord,
        )

        with pytest.raises(ValidationError, match="artifact_digest"):
            PromotionRecord(
                promotion_id=UUID("12345678-1234-5678-1234-567812345678"),
                artifact_digest="invalid-digest",  # Invalid format
                artifact_tag="v1.2.3-dev",
                source_environment="dev",
                target_environment="staging",
                gate_results=[
                    GateResult(
                        gate=PromotionGate.POLICY_COMPLIANCE,
                        status=GateStatus.PASSED,
                        duration_ms=100,
                    ),
                ],
                signature_verified=True,
                operator="user@example.com",
                promoted_at=datetime.now(timezone.utc),
                dry_run=False,
                trace_id="abc123",
                authorization_passed=True,
            )

    @pytest.mark.requirement("8C-FR-007")
    def test_promotion_record_frozen(self) -> None:
        """Test PromotionRecord is immutable (frozen)."""
        from datetime import datetime, timezone
        from uuid import UUID

        from floe_core.schemas.promotion import (
            GateResult,
            GateStatus,
            PromotionGate,
            PromotionRecord,
        )

        record = PromotionRecord(
            promotion_id=UUID("12345678-1234-5678-1234-567812345678"),
            artifact_digest="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            artifact_tag="v1.2.3-dev",
            source_environment="dev",
            target_environment="staging",
            gate_results=[
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                ),
            ],
            signature_verified=True,
            operator="user@example.com",
            promoted_at=datetime.now(timezone.utc),
            dry_run=False,
            trace_id="abc123",
            authorization_passed=True,
        )
        with pytest.raises(TypeError):  # Frozen model raises TypeError
            record.dry_run = True  # type: ignore[misc]


class TestRollbackRecord:
    """Tests for RollbackRecord Pydantic model."""

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_record_valid(self) -> None:
        """Test RollbackRecord with valid data."""
        from datetime import datetime, timezone
        from uuid import UUID

        from floe_core.schemas.promotion import RollbackRecord

        record = RollbackRecord(
            rollback_id=UUID("12345678-1234-5678-1234-567812345678"),
            artifact_digest="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            environment="prod",
            previous_digest="sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            reason="Critical bug in v1.3.0",
            operator="sre@example.com",
            rolled_back_at=datetime.now(timezone.utc),
            trace_id="xyz789",
        )
        assert record.rollback_id == UUID("12345678-1234-5678-1234-567812345678")
        assert record.environment == "prod"
        assert record.impact_analysis is None

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_record_with_impact_analysis(self) -> None:
        """Test RollbackRecord with impact analysis."""
        from datetime import datetime, timezone
        from uuid import UUID

        from floe_core.schemas.promotion import RollbackImpactAnalysis, RollbackRecord

        analysis = RollbackImpactAnalysis(
            breaking_changes=["API endpoint removed"],
            affected_products=["frontend-app"],
            recommendations=["Notify API consumers"],
            estimated_downtime="~2 minutes",
        )
        record = RollbackRecord(
            rollback_id=UUID("12345678-1234-5678-1234-567812345678"),
            artifact_digest="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            environment="prod",
            previous_digest="sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            reason="Critical bug in v1.3.0",
            operator="sre@example.com",
            rolled_back_at=datetime.now(timezone.utc),
            trace_id="xyz789",
            impact_analysis=analysis,
        )
        assert record.impact_analysis is not None
        assert record.impact_analysis.estimated_downtime == "~2 minutes"

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_record_invalid_digest_format(self) -> None:
        """Test RollbackRecord rejects invalid artifact digest format."""
        from datetime import datetime, timezone
        from uuid import UUID

        from pydantic import ValidationError

        from floe_core.schemas.promotion import RollbackRecord

        with pytest.raises(ValidationError, match="artifact_digest"):
            RollbackRecord(
                rollback_id=UUID("12345678-1234-5678-1234-567812345678"),
                artifact_digest="not-a-sha256",  # Invalid format
                environment="prod",
                previous_digest="sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                reason="Critical bug",
                operator="sre@example.com",
                rolled_back_at=datetime.now(timezone.utc),
                trace_id="xyz789",
            )

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_record_invalid_previous_digest_format(self) -> None:
        """Test RollbackRecord rejects invalid previous_digest format."""
        from datetime import datetime, timezone
        from uuid import UUID

        from pydantic import ValidationError

        from floe_core.schemas.promotion import RollbackRecord

        with pytest.raises(ValidationError, match="previous_digest"):
            RollbackRecord(
                rollback_id=UUID("12345678-1234-5678-1234-567812345678"),
                artifact_digest="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                environment="prod",
                previous_digest="invalid",  # Invalid format
                reason="Critical bug",
                operator="sre@example.com",
                rolled_back_at=datetime.now(timezone.utc),
                trace_id="xyz789",
            )

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_record_frozen(self) -> None:
        """Test RollbackRecord is immutable (frozen)."""
        from datetime import datetime, timezone
        from uuid import UUID

        from floe_core.schemas.promotion import RollbackRecord

        record = RollbackRecord(
            rollback_id=UUID("12345678-1234-5678-1234-567812345678"),
            artifact_digest="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            environment="prod",
            previous_digest="sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            reason="Critical bug",
            operator="sre@example.com",
            rolled_back_at=datetime.now(timezone.utc),
            trace_id="xyz789",
        )
        with pytest.raises(TypeError):  # Frozen model raises TypeError
            record.reason = "Changed reason"  # type: ignore[misc]

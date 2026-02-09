"""TDD unit tests for GovernanceIntegrator class and OTel span emission.

These tests MUST fail initially (TDD pattern — tests first, implementation later).
Tests cover T023 (GovernanceIntegrator logic) and T024 (OTel span emission).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# This import will fail until T026 implements the GovernanceIntegrator
from floe_core.governance.integrator import GovernanceIntegrator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory import InMemorySpanExporter

from floe_core.enforcement.result import (
    EnforcementResult,
    EnforcementSummary,
    Violation,
)
from floe_core.schemas.governance import RBACConfig, SecretScanningConfig
from floe_core.schemas.manifest import GovernanceConfig


@pytest.fixture
def mock_policy_enforcer() -> MagicMock:
    """Create mock PolicyEnforcer."""
    enforcer = MagicMock()
    enforcer.enforce.return_value = EnforcementResult(
        passed=True,
        violations=[],
        summary=EnforcementSummary(
            total_models=5,
            models_validated=5,
        ),
        enforcement_level="strict",
        manifest_version="1.0.0",
        timestamp=datetime.now(timezone.utc),
    )
    return enforcer


@pytest.fixture
def mock_rbac_checker() -> MagicMock:
    """Create mock RBACChecker."""
    checker = MagicMock()
    checker.check.return_value = []
    return checker


@pytest.fixture
def mock_secret_scanner() -> MagicMock:
    """Create mock SecretScanner."""
    scanner = MagicMock()
    scanner.scan.return_value = []
    return scanner


@pytest.fixture
def mock_identity_plugin() -> MagicMock:
    """Create mock IdentityPlugin."""
    plugin = MagicMock()
    plugin.verify_token.return_value = {"sub": "user@example.com", "role": "engineer"}
    return plugin


@pytest.fixture
def otel_tracer_setup() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Set up OTel tracer with in-memory exporter for testing."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider, exporter


@pytest.fixture
def minimal_governance_config() -> GovernanceConfig:
    """Create minimal GovernanceConfig with no rbac/secrets."""
    return GovernanceConfig(
        policy_enforcement_level="strict",
        pii_encryption="optional",
        audit_logging="enabled",
    )


@pytest.fixture
def rbac_enabled_config() -> GovernanceConfig:
    """Create GovernanceConfig with RBAC enabled."""
    return GovernanceConfig(
        policy_enforcement_level="strict",
        rbac=RBACConfig(
            enabled=True,
            required_role="data-engineer",
            allow_principal_fallback=True,
        ),
    )


@pytest.fixture
def secrets_enabled_config() -> GovernanceConfig:
    """Create GovernanceConfig with secret scanning enabled."""
    return GovernanceConfig(
        policy_enforcement_level="strict",
        secret_scanning=SecretScanningConfig(
            enabled=True,
            exclude_patterns=["*.test"],
            severity="error",
        ),
    )


@pytest.fixture
def full_governance_config() -> GovernanceConfig:
    """Create GovernanceConfig with both RBAC and secret scanning enabled."""
    return GovernanceConfig(
        policy_enforcement_level="strict",
        rbac=RBACConfig(
            enabled=True,
            required_role="data-engineer",
            allow_principal_fallback=True,
        ),
        secret_scanning=SecretScanningConfig(
            enabled=True,
            exclude_patterns=["*.test"],
            severity="error",
        ),
    )


# T023 Test Scenarios: GovernanceIntegrator


@pytest.mark.requirement("3E-FR-001")
@pytest.mark.requirement("3E-FR-004")
@pytest.mark.requirement("3E-FR-005")
def test_integrator_runs_all_checks(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test integrator invokes both RBACChecker and SecretScanner when enabled.

    Given RBAC + secrets enabled in GovernanceConfig
    When run_checks() is called
    Then both RBACChecker.check() and SecretScanner.scan() are invoked
    (collect-all pattern).
    """
    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=full_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",
        )

        # Assert both checkers were invoked
        mock_rbac_checker.check.assert_called_once()
        mock_secret_scanner.scan.assert_called_once()
        mock_policy_enforcer.enforce.assert_called_once()

        # Result should pass (no violations)
        assert result.passed is True
        assert len(result.violations) == 0


@pytest.mark.requirement("3E-FR-001")
@pytest.mark.requirement("3E-FR-006")
def test_integrator_merges_violations(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test integrator merges violations from all checks.

    Given RBAC returns 1 violation and secrets returns 2 violations
    When run_checks() is called
    Then merged result has exactly 3 violations total.
    """
    rbac_violation = Violation(
        error_code="RBAC-001",
        severity="error",
        policy_type="rbac",
        model_name="test_model",
        message="Unauthorized role",
        expected="data-engineer",
        actual="analyst",
        suggestion="Request data-engineer role",
        documentation_url="https://docs.example.com/rbac",
    )

    secret_violation_1 = Violation(
        error_code="SECRET-001",
        severity="error",
        policy_type="secret_scanning",
        model_name="test_model",
        message="AWS access key detected",
        expected="No secrets in code",
        actual="AKIAIOSFODNN7EXAMPLE",
        suggestion="Use environment variables",
        documentation_url="https://docs.example.com/secrets",
    )

    secret_violation_2 = Violation(
        error_code="SECRET-002",
        severity="error",
        policy_type="secret_scanning",
        model_name="test_model",
        message="API key detected",
        expected="No secrets in code",
        actual="api_key=sk-test123",
        suggestion="Use secret manager",
        documentation_url="https://docs.example.com/secrets",
    )

    mock_rbac_checker.check.return_value = [rbac_violation]
    mock_secret_scanner.scan.return_value = [secret_violation_1, secret_violation_2]

    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=full_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",
        )

        # Assert exactly 3 violations merged
        assert len(result.violations) == 3
        assert result.violations[0].error_code == "RBAC-001"
        assert result.violations[1].error_code == "SECRET-001"
        assert result.violations[2].error_code == "SECRET-002"
        assert result.passed is False  # Errors present
        assert result.error_count == 3


@pytest.mark.requirement("3E-FR-001")
@pytest.mark.requirement("3E-FR-031")
def test_integrator_collect_all_pattern(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test integrator never fail-fast — all checks run even if one fails.

    Given RBAC check fails but secret scan hasn't run yet
    When run_checks() is called
    Then SecretScanner.scan() still executes (collect-all pattern).
    """
    rbac_violation = Violation(
        error_code="RBAC-001",
        severity="error",
        policy_type="rbac",
        model_name="test_model",
        message="Unauthorized role",
        expected="data-engineer",
        actual="analyst",
        suggestion="Request data-engineer role",
        documentation_url="https://docs.example.com/rbac",
    )

    mock_rbac_checker.check.return_value = [rbac_violation]
    mock_secret_scanner.scan.return_value = []  # No secrets found

    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=full_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",
        )

        # Both checks MUST have been invoked despite RBAC failure
        mock_rbac_checker.check.assert_called_once()
        mock_secret_scanner.scan.assert_called_once()

        # Only 1 violation from RBAC
        assert len(result.violations) == 1
        assert result.violations[0].error_code == "RBAC-001"
        assert result.passed is False


@pytest.mark.requirement("3E-FR-001")
@pytest.mark.requirement("3E-FR-006")
def test_dry_run_mode_reports_but_passes(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test dry_run mode reports violations but result still passes.

    Given dry_run=True and violations exist
    When run_checks() is called
    Then result.passed is True but violations are still reported.
    """
    rbac_violation = Violation(
        error_code="RBAC-001",
        severity="error",
        policy_type="rbac",
        model_name="test_model",
        message="Unauthorized role",
        expected="data-engineer",
        actual="analyst",
        suggestion="Request data-engineer role",
        documentation_url="https://docs.example.com/rbac",
    )

    mock_rbac_checker.check.return_value = [rbac_violation]
    mock_secret_scanner.scan.return_value = []

    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=full_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=True,  # Dry run mode
            enforcement_level="strict",
        )

        # Violations reported
        assert len(result.violations) == 1
        assert result.violations[0].error_code == "RBAC-001"

        # But result passes in dry run mode
        assert result.passed is True


@pytest.mark.requirement("3E-FR-001")
@pytest.mark.requirement("3E-FR-006")
def test_enforcement_level_off(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test enforcement_level='off' skips all governance checks.

    Given enforcement_level="off"
    When run_checks() is called
    Then no governance checks run and result passes.
    """
    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=full_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="off",  # All checks disabled
        )

        # No checks should have been invoked
        mock_rbac_checker.check.assert_not_called()
        mock_secret_scanner.scan.assert_not_called()
        mock_policy_enforcer.enforce.assert_not_called()

        # Result passes
        assert result.passed is True
        assert len(result.violations) == 0


@pytest.mark.requirement("3E-FR-001")
@pytest.mark.requirement("3E-FR-006")
def test_enforcement_level_warn(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test enforcement_level='warn' downgrades errors to warnings.

    Given enforcement_level="warn" and violations exist
    When run_checks() is called
    Then all violations are downgraded to warnings and result passes.
    """
    rbac_violation = Violation(
        error_code="RBAC-001",
        severity="error",
        policy_type="rbac",
        model_name="test_model",
        message="Unauthorized role",
        expected="data-engineer",
        actual="analyst",
        suggestion="Request data-engineer role",
        documentation_url="https://docs.example.com/rbac",
    )

    mock_rbac_checker.check.return_value = [rbac_violation]
    mock_secret_scanner.scan.return_value = []

    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="warn",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=full_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="warn",  # Warn mode
        )

        # Violations exist but downgraded to warnings
        assert len(result.violations) == 1
        assert result.violations[0].severity == "warning"  # Downgraded from error

        # Result passes (warnings don't fail)
        assert result.passed is True
        assert result.warning_count == 1
        assert result.error_count == 0


@pytest.mark.requirement("3E-FR-001")
@pytest.mark.requirement("3E-FR-006")
def test_enforcement_level_strict(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test enforcement_level='strict' keeps errors as errors.

    Given enforcement_level="strict" and violations exist
    When run_checks() is called
    Then errors remain errors and result fails.
    """
    rbac_violation = Violation(
        error_code="RBAC-001",
        severity="error",
        policy_type="rbac",
        model_name="test_model",
        message="Unauthorized role",
        expected="data-engineer",
        actual="analyst",
        suggestion="Request data-engineer role",
        documentation_url="https://docs.example.com/rbac",
    )

    mock_rbac_checker.check.return_value = [rbac_violation]
    mock_secret_scanner.scan.return_value = []

    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=full_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",  # Strict mode
        )

        # Violations remain errors
        assert len(result.violations) == 1
        assert result.violations[0].severity == "error"

        # Result fails
        assert result.passed is False
        assert result.error_count == 1


@pytest.mark.requirement("3E-FR-004")
def test_rbac_disabled_skips_rbac_check(
    secrets_enabled_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test RBACChecker not invoked when RBAC disabled.

    Given RBACConfig.enabled=False
    When run_checks() is called
    Then RBACChecker.check() is NOT invoked.
    """
    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=secrets_enabled_config,  # RBAC disabled
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",
        )

        # RBAC check NOT invoked
        mock_rbac_checker.check.assert_not_called()

        # Secret scan WAS invoked
        mock_secret_scanner.scan.assert_called_once()

        assert result.passed is True


@pytest.mark.requirement("3E-FR-005")
def test_secret_scanning_disabled_skips_secret_check(
    rbac_enabled_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test SecretScanner not invoked when secret scanning disabled.

    Given SecretScanningConfig.enabled=False
    When run_checks() is called
    Then SecretScanner.scan() is NOT invoked.
    """
    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=rbac_enabled_config,  # Secrets disabled
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",
        )

        # Secret scan NOT invoked
        mock_secret_scanner.scan.assert_not_called()

        # RBAC check WAS invoked
        mock_rbac_checker.check.assert_called_once()

        assert result.passed is True


@pytest.mark.requirement("3E-FR-001")
def test_integrator_with_no_governance_config(
    minimal_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test integrator passes cleanly with minimal config (no rbac/secrets).

    Given minimal GovernanceConfig with no rbac/secrets
    When run_checks() is called
    Then result passes cleanly with no violations.
    """
    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=minimal_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token=None,
            principal=None,
            dry_run=False,
            enforcement_level="strict",
        )

        # Neither RBAC nor secret scan invoked
        mock_rbac_checker.check.assert_not_called()
        mock_secret_scanner.scan.assert_not_called()

        # Only policy enforcement runs
        mock_policy_enforcer.enforce.assert_called_once()

        # Result passes
        assert result.passed is True
        assert len(result.violations) == 0


# T024 Test Scenarios: OTel Span Emission


@pytest.mark.requirement("3E-FR-007")
def test_otel_spans_created_for_each_check(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    otel_tracer_setup: tuple[TracerProvider, InMemorySpanExporter],
    tmp_path: Path,
) -> None:
    """Test OTel spans created for each governance check type.

    Given RBAC + secrets enabled
    When run_checks() is called
    Then OTel tracer creates spans named 'governance.rbac',
    'governance.secrets', and 'governance.policies'.
    """
    _, exporter = otel_tracer_setup

    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=full_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",
        )

        # Get finished spans
        spans = exporter.get_finished_spans()

        # Assert spans were created for each check type
        span_names = {span.name for span in spans}
        assert "governance.rbac" in span_names
        assert "governance.secrets" in span_names
        assert "governance.policies" in span_names


@pytest.mark.requirement("3E-FR-007")
def test_otel_span_includes_timing_attributes(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    otel_tracer_setup: tuple[TracerProvider, InMemorySpanExporter],
    tmp_path: Path,
) -> None:
    """Test OTel spans include timing and result attributes.

    When governance checks run
    Then spans include 'governance.check_type', 'governance.violations_count',
    and 'governance.duration_ms' attributes.
    """
    _, exporter = otel_tracer_setup

    rbac_violation = Violation(
        error_code="RBAC-001",
        severity="error",
        policy_type="rbac",
        model_name="test_model",
        message="Unauthorized role",
        expected="data-engineer",
        actual="analyst",
        suggestion="Request data-engineer role",
        documentation_url="https://docs.example.com/rbac",
    )

    mock_rbac_checker.check.return_value = [rbac_violation]
    mock_secret_scanner.scan.return_value = []

    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=full_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",
        )

        # Get finished spans
        spans = exporter.get_finished_spans()

        # Find RBAC span
        rbac_spans = [span for span in spans if span.name == "governance.rbac"]
        assert len(rbac_spans) == 1

        rbac_span = rbac_spans[0]
        attributes = dict(rbac_span.attributes or {})

        # Assert required attributes present
        assert "governance.check_type" in attributes
        assert attributes["governance.check_type"] == "rbac"
        assert "governance.violations_count" in attributes
        assert attributes["governance.violations_count"] == 1
        assert "governance.duration_ms" in attributes
        assert attributes["governance.duration_ms"] > 0


@pytest.mark.requirement("3E-FR-007")
def test_otel_span_records_errors_on_failure(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    otel_tracer_setup: tuple[TracerProvider, InMemorySpanExporter],
    tmp_path: Path,
) -> None:
    """Test OTel span status set to ERROR when violations occur.

    Given a check produces violations
    When run_checks() is called
    Then span status is set to ERROR with description.
    """
    _, exporter = otel_tracer_setup

    rbac_violation = Violation(
        error_code="RBAC-001",
        severity="error",
        policy_type="rbac",
        model_name="test_model",
        message="Unauthorized role",
        expected="data-engineer",
        actual="analyst",
        suggestion="Request data-engineer role",
        documentation_url="https://docs.example.com/rbac",
    )

    mock_rbac_checker.check.return_value = [rbac_violation]
    mock_secret_scanner.scan.return_value = []

    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
            return_value=mock_rbac_checker,
        ),
        patch(
            "floe_core.governance.integrator.SecretScanner",
            return_value=mock_secret_scanner,
        ),
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=full_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        integrator.run_checks(
            project_dir=tmp_path,
            token="valid-oidc-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",
        )

        # Get finished spans
        spans = exporter.get_finished_spans()

        # Find RBAC span
        rbac_spans = [span for span in spans if span.name == "governance.rbac"]
        assert len(rbac_spans) == 1

        rbac_span = rbac_spans[0]

        # Assert span status is ERROR
        from opentelemetry.trace import StatusCode

        assert rbac_span.status.status_code == StatusCode.ERROR
        assert "violations" in rbac_span.status.description.lower()

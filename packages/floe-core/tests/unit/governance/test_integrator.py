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
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from floe_core.enforcement.result import (
    EnforcementResult,
    EnforcementSummary,
    Violation,
)
from floe_core.governance.types import SecretFinding
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
    scanner.scan_directory.return_value = []
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
    # Reset global tracer provider to allow multiple tests
    from opentelemetry.util._once import Once

    trace._TRACER_PROVIDER_SET_ONCE = Once()
    trace._TRACER_PROVIDER = None  # type: ignore[assignment]

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield provider, exporter
    # Clear spans after each test
    exporter.clear()


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
    Then both RBACChecker.check() and SecretScanner.scan_directory() are invoked
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
        mock_secret_scanner.scan_directory.assert_called_once()
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

    secret_finding_1 = SecretFinding(
        file_path="config.py",
        line_number=10,
        pattern_name="aws_access_key",
        error_code="E601",
        matched_content="AKIA_REDACTED_EXAMPLE",
        severity="error",
    )

    secret_finding_2 = SecretFinding(
        file_path="settings.py",
        line_number=25,
        pattern_name="api_token",
        error_code="E603",
        matched_content="api_key=sk-test123",
        severity="error",
    )

    mock_rbac_checker.check.return_value = [rbac_violation]
    mock_secret_scanner.scan_directory.return_value = [secret_finding_1, secret_finding_2]

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

        # Assert exactly 3 violations merged (1 RBAC + 2 secret findings converted)
        assert len(result.violations) == 3
        assert result.violations[0].error_code == "RBAC-001"
        assert result.violations[1].error_code == "FLOE-E601"
        assert result.violations[2].error_code == "FLOE-E603"
        assert result.violations[1].policy_type == "secret_scanning"
        assert result.violations[2].policy_type == "secret_scanning"
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
    Then SecretScanner.scan_directory() still executes (collect-all pattern).
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
    mock_secret_scanner.scan_directory.return_value = []  # No secrets found

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
        mock_secret_scanner.scan_directory.assert_called_once()

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
    mock_secret_scanner.scan_directory.return_value = []

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
        mock_secret_scanner.scan_directory.assert_not_called()
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
    mock_secret_scanner.scan_directory.return_value = []

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
    mock_secret_scanner.scan_directory.return_value = []

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
        mock_secret_scanner.scan_directory.assert_called_once()

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
    Then SecretScanner.scan_directory() is NOT invoked.
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
        mock_secret_scanner.scan_directory.assert_not_called()

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
        mock_secret_scanner.scan_directory.assert_not_called()

        # Only policy enforcement runs
        mock_policy_enforcer.enforce.assert_called_once()

        # Result passes
        assert result.passed is True
        assert len(result.violations) == 0


@pytest.mark.requirement("003e-FR-015")
@pytest.mark.requirement("003e-FR-019")
def test_integrator_delegates_custom_rules_to_policy_enforcer(
    mock_identity_plugin: MagicMock,
    tmp_path: Path,
) -> None:
    """Test GovernanceIntegrator forwards custom_rules config to PolicyEnforcer.

    Given GovernanceConfig with custom_rules and a dbt_manifest
    When run_checks() is called
    Then PolicyEnforcer receives governance_config with custom_rules
    And enforce() receives the dbt_manifest.
    """
    from floe_core.schemas.governance import RequireTagsForPrefix

    custom_rule = RequireTagsForPrefix(
        type="require_tags_for_prefix",
        prefix="gold_",
        required_tags=["tested", "documented"],
    )
    config_with_rules = GovernanceConfig(
        policy_enforcement_level="strict",
        custom_rules=[custom_rule],
    )

    dbt_manifest = {
        "metadata": {"dbt_version": "1.8.0"},
        "nodes": {
            "model.project.gold_customers": {
                "name": "gold_customers",
                "resource_type": "model",
                "tags": [],
                "meta": {},
            }
        },
    }

    custom_violation = Violation(
        error_code="FLOE-E400",
        severity="error",
        policy_type="custom",
        model_name="gold_customers",
        message="Model gold_customers missing required tags: tested, documented",
        expected="Tags: tested, documented",
        actual="Tags: (none)",
        suggestion="Add required tags to the model",
        documentation_url="https://floe.dev/docs/errors/FLOE-E400",
    )

    with (
        patch(
            "floe_core.governance.integrator.RBACChecker",
        ) as mock_rbac_cls,
        patch(
            "floe_core.governance.integrator.SecretScanner",
        ) as mock_scanner_cls,
        patch(
            "floe_core.governance.integrator.PolicyEnforcer",
        ) as mock_policy_enforcer_cls,
    ):
        mock_rbac = MagicMock()
        mock_rbac.check.return_value = []
        mock_rbac_cls.return_value = mock_rbac

        mock_scanner = MagicMock()
        mock_scanner.scan_directory.return_value = []
        mock_scanner_cls.return_value = mock_scanner

        mock_policy_enforcer = MagicMock()
        mock_policy_enforcer.enforce.return_value = EnforcementResult(
            passed=False,
            violations=[custom_violation],
            summary=EnforcementSummary(
                total_models=1,
                models_validated=1,
                custom_rule_violations=1,
            ),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_policy_enforcer_cls.return_value = mock_policy_enforcer

        integrator = GovernanceIntegrator(
            governance_config=config_with_rules,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token=None,
            principal=None,
            dry_run=False,
            enforcement_level="strict",
            dbt_manifest=dbt_manifest,
        )

        # Verify PolicyEnforcer received the config with custom_rules
        mock_policy_enforcer_cls.assert_called_once_with(
            governance_config=config_with_rules,
        )
        assert len(config_with_rules.custom_rules) == 1

        # Verify enforce() received the dbt_manifest
        mock_policy_enforcer.enforce.assert_called_once_with(dbt_manifest)

        # Verify custom rule violations flow through to final result
        assert len(result.violations) == 1
        assert result.violations[0].error_code == "FLOE-E400"
        assert result.violations[0].policy_type == "custom"
        assert result.violations[0].model_name == "gold_customers"
        assert result.passed is False


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

        # Assert exactly 3 spans created for each check type
        span_names = {span.name for span in spans}
        assert "governance.rbac" in span_names
        assert "governance.secrets" in span_names
        assert "governance.policies" in span_names
        assert len(spans) == 3, f"Expected 3 spans, got {len(spans)}: {[s.name for s in spans]}"


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
    mock_secret_scanner.scan_directory.return_value = []

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
    mock_secret_scanner.scan_directory.return_value = []

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


@pytest.mark.requirement("3E-FR-001")
@pytest.mark.requirement("3E-FR-031")
def test_integrator_handles_rbac_exception(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test integrator handles RBACChecker exception gracefully.

    Given RBAC check raises RuntimeError
    When run_checks() is called
    Then secret scan still runs, FLOE-E500 violation produced, result.passed is False.
    """
    mock_rbac_checker.check.side_effect = RuntimeError("RBAC service unavailable")
    mock_secret_scanner.scan_directory.return_value = []

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

        # Secret scan still runs (collect-all preserved)
        mock_secret_scanner.scan_directory.assert_called_once()

        # FLOE-E500 violation produced
        rbac_error_violations = [
            v for v in result.violations if v.error_code == "FLOE-E500"
        ]
        assert len(rbac_error_violations) == 1
        assert rbac_error_violations[0].policy_type == "rbac"
        assert "RBAC service unavailable" in rbac_error_violations[0].message

        assert result.passed is False


@pytest.mark.requirement("3E-FR-001")
@pytest.mark.requirement("3E-FR-031")
def test_integrator_handles_secret_scan_exception(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test integrator handles SecretScanner exception gracefully.

    Given secret scan raises RuntimeError
    When run_checks() is called
    Then policy enforcer still runs, FLOE-E600 violation produced.
    """
    mock_rbac_checker.check.return_value = []
    mock_secret_scanner.scan_directory.side_effect = RuntimeError("Scanner crashed")

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

        # Policy enforcer still runs
        mock_policy_enforcer.enforce.assert_called_once()

        # FLOE-E600 violation produced with policy_type secret_scanning
        secret_error_violations = [
            v for v in result.violations
            if v.error_code == "FLOE-E600" and v.policy_type == "secret_scanning"
        ]
        assert len(secret_error_violations) == 1
        assert "Scanner crashed" in secret_error_violations[0].message

        assert result.passed is False


@pytest.mark.requirement("3E-FR-001")
@pytest.mark.requirement("3E-FR-031")
def test_integrator_handles_policy_enforcement_exception(
    full_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    mock_rbac_checker: MagicMock,
    mock_secret_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test integrator handles PolicyEnforcer exception gracefully.

    Given policy enforcement raises ValueError
    When run_checks() is called
    Then FLOE-E400 violation produced and result has valid summary.
    """
    mock_rbac_checker.check.return_value = []
    mock_secret_scanner.scan_directory.return_value = []

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
        mock_policy_enforcer.enforce.side_effect = ValueError("Invalid manifest format")
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

        # FLOE-E400 violation produced
        policy_error_violations = [
            v for v in result.violations if v.error_code == "FLOE-E400"
        ]
        assert len(policy_error_violations) == 1
        assert policy_error_violations[0].policy_type == "custom"
        assert "Invalid manifest format" in policy_error_violations[0].message

        assert result.passed is False
        # Summary should still be valid (empty summary fallback)
        assert result.summary is not None


@pytest.mark.requirement("3E-FR-015")
@pytest.mark.requirement("3E-FR-019")
def test_integrator_runs_policy_evaluation_when_policies_configured(
    mock_identity_plugin: MagicMock,
    tmp_path: Path,
) -> None:
    """Test PolicyEvaluator invoked when policies configured in GovernanceConfig.

    Given GovernanceConfig with policies list
    When run_checks() is called with a dbt_manifest
    Then PolicyEvaluator is instantiated with converted PolicyDefinitions
    And violations from PolicyEvaluator are merged into the final result.
    """
    from floe_core.schemas.governance import PolicyDefinitionConfig

    # Create GovernanceConfig with policies
    governance_config = GovernanceConfig(
        policy_enforcement_level="strict",
        pii_encryption="optional",
        policies=[
            PolicyDefinitionConfig(
                name="test_required_tags",
                type="required_tags",
                action="error",
                message="Models must have required tags",
                config={"required_tags": ["tested", "pii"]},
            )
        ],
    )

    # dbt manifest with a model missing tags
    dbt_manifest = {
        "nodes": {
            "model.my_project.my_model": {
                "name": "my_model",
                "resource_type": "model",
                "tags": [],  # Missing required tags
            }
        }
    }

    # Mock PolicyEvaluator to return a violation
    mock_evaluator_violation = Violation(
        error_code="FLOE-E600",
        severity="error",
        policy_type="custom",
        model_name="model.my_project.my_model",
        message="Model missing required tags",
        expected="tags=['tested', 'pii']",
        actual="tags=[]",
        suggestion="Add required tags to model YAML",
        documentation_url="https://docs.floe.dev/governance/policies#required-tags",
    )

    with (
        patch("floe_core.governance.integrator.PolicyEnforcer") as mock_enforcer_cls,
        patch("floe_core.governance.integrator.RBACChecker"),
        patch("floe_core.governance.integrator.SecretScanner"),
        patch("floe_core.governance.integrator.PolicyEvaluator") as mock_evaluator_cls,
    ):
        # PolicyEnforcer returns empty violations
        mock_enforcer = MagicMock()
        mock_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=1,
                models_validated=1,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_enforcer_cls.return_value = mock_enforcer

        # PolicyEvaluator returns one violation
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = [mock_evaluator_violation]
        mock_evaluator_cls.return_value = mock_evaluator

        integrator = GovernanceIntegrator(
            governance_config=governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",
            dbt_manifest=dbt_manifest,
        )

        # Assert PolicyEvaluator was instantiated
        mock_evaluator_cls.assert_called_once()
        # Assert evaluate was called with the manifest
        mock_evaluator.evaluate.assert_called_once()
        call_kwargs = mock_evaluator.evaluate.call_args[1]
        assert call_kwargs["manifest"] == dbt_manifest

        # Assert violations are in the result
        assert len(result.violations) == 1
        assert result.violations[0].error_code == "FLOE-E600"
        assert result.violations[0].policy_type == "custom"
        assert result.passed is False


@pytest.mark.requirement("3E-FR-015")
def test_integrator_skips_policy_evaluation_when_no_policies(
    minimal_governance_config: GovernanceConfig,
    mock_identity_plugin: MagicMock,
    tmp_path: Path,
) -> None:
    """Test PolicyEvaluator NOT invoked when policies is None.

    Given GovernanceConfig with policies=None (default)
    When run_checks() is called
    Then PolicyEvaluator is never instantiated.
    """
    with (
        patch("floe_core.governance.integrator.PolicyEnforcer") as mock_enforcer_cls,
        patch("floe_core.governance.integrator.RBACChecker"),
        patch("floe_core.governance.integrator.SecretScanner"),
        patch("floe_core.governance.integrator.PolicyEvaluator") as mock_evaluator_cls,
    ):
        # PolicyEnforcer returns empty violations
        mock_enforcer = MagicMock()
        mock_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=0,
                models_validated=0,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_enforcer_cls.return_value = mock_enforcer

        integrator = GovernanceIntegrator(
            governance_config=minimal_governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",
            dbt_manifest=None,
        )

        # Assert PolicyEvaluator was NEVER instantiated
        mock_evaluator_cls.assert_not_called()
        assert result.passed is True


@pytest.mark.requirement("3E-FR-015")
@pytest.mark.requirement("3E-FR-031")
def test_integrator_handles_policy_evaluation_exception(
    mock_identity_plugin: MagicMock,
    tmp_path: Path,
) -> None:
    """Test integrator handles PolicyEvaluator exception gracefully.

    Given PolicyEvaluator.evaluate() raises RuntimeError
    When run_checks() is called
    Then FLOE-E450 violation produced, policy_type="custom", and result.passed is False.
    """
    from floe_core.schemas.governance import PolicyDefinitionConfig

    # Create GovernanceConfig with policies
    governance_config = GovernanceConfig(
        policy_enforcement_level="strict",
        pii_encryption="optional",
        policies=[
            PolicyDefinitionConfig(
                name="test_policy",
                type="custom",
                action="error",
                message="Test policy",
                config={},
            )
        ],
    )

    with (
        patch("floe_core.governance.integrator.PolicyEnforcer") as mock_enforcer_cls,
        patch("floe_core.governance.integrator.RBACChecker"),
        patch("floe_core.governance.integrator.SecretScanner"),
        patch("floe_core.governance.integrator.PolicyEvaluator") as mock_evaluator_cls,
    ):
        # PolicyEnforcer returns empty violations
        mock_enforcer = MagicMock()
        mock_enforcer.enforce.return_value = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=0,
                models_validated=0,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        mock_enforcer_cls.return_value = mock_enforcer

        # PolicyEvaluator raises RuntimeError
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.side_effect = RuntimeError("Policy evaluation crashed")
        mock_evaluator_cls.return_value = mock_evaluator

        integrator = GovernanceIntegrator(
            governance_config=governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=tmp_path,
            token="valid-token",
            principal="user@example.com",
            dry_run=False,
            enforcement_level="strict",
            dbt_manifest={},
        )

        # Assert FLOE-E450 violation produced
        e450_violations = [v for v in result.violations if v.error_code == "FLOE-E450"]
        assert len(e450_violations) == 1
        assert e450_violations[0].policy_type == "custom"
        assert "Policy evaluation crashed" in e450_violations[0].message
        assert result.passed is False

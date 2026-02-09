"""Unit tests for governance CLI commands.

Tests FR-024 (status), FR-025 (audit), FR-026 (report format flags).
TDD: Tests written first — must fail until T044-T047 implement commands.

Task: T043
Requirements: FR-024, FR-025, FR-026
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from floe_core.cli.governance import governance_group

from floe_core.enforcement.result import (
    EnforcementResult,
    EnforcementSummary,
    Violation,
)
from floe_core.schemas.governance import (
    NetworkPoliciesConfig,
    RBACConfig,
    SecretScanningConfig,
)
from floe_core.schemas.manifest import GovernanceConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create Click CLI test runner.

    Returns:
        CliRunner with stderr separation enabled.
    """
    return CliRunner()


@pytest.fixture
def passing_result() -> EnforcementResult:
    """Create a passing enforcement result with no violations.

    Returns:
        EnforcementResult where all checks passed.
    """
    return EnforcementResult(
        passed=True,
        violations=[],
        summary=EnforcementSummary(total_models=5, models_validated=5),
        enforcement_level="strict",
        manifest_version="1.0.0",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def failing_result() -> EnforcementResult:
    """Create a failing enforcement result with mixed violations.

    Returns:
        EnforcementResult with RBAC, secret, and naming violations.
    """
    return EnforcementResult(
        passed=False,
        violations=[
            Violation(
                error_code="E601",
                severity="error",
                policy_type="secret_scanning",
                model_name="database_config",
                message="AWS access key detected",
                expected="No hardcoded secrets",
                actual="AKIA pattern matched",
                suggestion="Use environment variables or SecretStr",
                documentation_url="https://docs.floe.dev/governance/secrets",
            ),
            Violation(
                error_code="E501",
                severity="error",
                policy_type="rbac",
                model_name="__global__",
                message="No identity token provided",
                expected="Valid OIDC token",
                actual="No token",
                suggestion="Set FLOE_TOKEN or use --token",
                documentation_url="https://docs.floe.dev/governance/rbac",
            ),
            Violation(
                error_code="E301",
                severity="warning",
                policy_type="naming",
                model_name="orders_raw",
                message="Model name does not follow convention",
                expected="snake_case with prefix",
                actual="orders_raw",
                suggestion="Rename to stg_orders_raw",
                documentation_url="https://docs.floe.dev/governance/naming",
            ),
        ],
        summary=EnforcementSummary(
            total_models=10,
            models_validated=10,
            naming_violations=1,
            rbac_violations=1,
            secret_violations=1,
        ),
        enforcement_level="strict",
        manifest_version="1.0.0",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def config_all_enabled() -> GovernanceConfig:
    """Create GovernanceConfig with all governance checks enabled.

    Returns:
        GovernanceConfig with RBAC, secret scanning, and network policies.
    """
    return GovernanceConfig(
        policy_enforcement_level="strict",
        data_retention_days=None,
        rbac=RBACConfig(enabled=True, required_role="data_engineer"),
        secret_scanning=SecretScanningConfig(enabled=True),
        network_policies=NetworkPoliciesConfig(enabled=True, default_deny=True),
    )


@pytest.fixture
def config_minimal() -> GovernanceConfig:
    """Create GovernanceConfig with no new checks enabled.

    Returns:
        GovernanceConfig with only legacy fields.
    """
    return GovernanceConfig(
        policy_enforcement_level="warn",
        data_retention_days=None,
    )


# ---------------------------------------------------------------------------
# Governance Group Tests
# ---------------------------------------------------------------------------


@pytest.mark.requirement("003e-FR-024")
def test_governance_group_help(cli_runner: CliRunner) -> None:
    """Test governance group --help lists all subcommands."""
    result = cli_runner.invoke(governance_group, ["--help"])

    assert result.exit_code == 0
    output_lower = result.output.lower()
    assert "status" in output_lower
    assert "audit" in output_lower
    assert "report" in output_lower


@pytest.mark.requirement("003e-FR-024")
def test_governance_group_no_subcommand_shows_help(cli_runner: CliRunner) -> None:
    """Test governance group with no subcommand shows usage info."""
    result = cli_runner.invoke(governance_group, [])

    # Should show help/usage, not crash
    output_lower = result.output.lower()
    assert "status" in output_lower or "usage" in output_lower


# ---------------------------------------------------------------------------
# Status Command Tests (FR-024)
# ---------------------------------------------------------------------------

STATUS_CONFIG_PATCH = "floe_core.cli.governance.status.load_governance_config"
STATUS_RESULT_PATCH = "floe_core.cli.governance.status.load_last_enforcement_result"


@pytest.mark.requirement("003e-FR-024")
def test_status_shows_enabled_checks(
    cli_runner: CliRunner,
    config_all_enabled: GovernanceConfig,
) -> None:
    """Test status displays which governance checks are enabled."""
    with (
        patch(STATUS_CONFIG_PATCH, return_value=config_all_enabled),
        patch(STATUS_RESULT_PATCH, return_value=None),
    ):
        result = cli_runner.invoke(governance_group, ["status"])

    assert result.exit_code == 0
    output_lower = result.output.lower()
    assert "rbac" in output_lower
    assert "enabled" in output_lower
    assert "secret" in output_lower
    assert "network" in output_lower


@pytest.mark.requirement("003e-FR-024")
def test_status_shows_disabled_when_unconfigured(
    cli_runner: CliRunner,
    config_minimal: GovernanceConfig,
) -> None:
    """Test status shows disabled state when checks are not configured."""
    with (
        patch(STATUS_CONFIG_PATCH, return_value=config_minimal),
        patch(STATUS_RESULT_PATCH, return_value=None),
    ):
        result = cli_runner.invoke(governance_group, ["status"])

    assert result.exit_code == 0
    output_lower = result.output.lower()
    assert "rbac" in output_lower
    assert "disabled" in output_lower or "not configured" in output_lower


@pytest.mark.requirement("003e-FR-024")
def test_status_shows_violation_counts(
    cli_runner: CliRunner,
    failing_result: EnforcementResult,
    config_all_enabled: GovernanceConfig,
) -> None:
    """Test status displays violation counts from last enforcement result."""
    with (
        patch(STATUS_CONFIG_PATCH, return_value=config_all_enabled),
        patch(STATUS_RESULT_PATCH, return_value=failing_result),
    ):
        result = cli_runner.invoke(governance_group, ["status"])

    assert result.exit_code == 0
    output_lower = result.output.lower()
    # Should mention violation counts or total
    assert "3" in result.output or "violation" in output_lower


@pytest.mark.requirement("003e-FR-024")
def test_status_no_previous_result(
    cli_runner: CliRunner,
    config_all_enabled: GovernanceConfig,
) -> None:
    """Test status handles missing last enforcement result gracefully."""
    with (
        patch(STATUS_CONFIG_PATCH, return_value=config_all_enabled),
        patch(STATUS_RESULT_PATCH, return_value=None),
    ):
        result = cli_runner.invoke(governance_group, ["status"])

    assert result.exit_code == 0
    output_lower = result.output.lower()
    assert "no previous" in output_lower or "not available" in output_lower


@pytest.mark.requirement("003e-FR-024")
def test_status_shows_enforcement_level(
    cli_runner: CliRunner,
    config_all_enabled: GovernanceConfig,
) -> None:
    """Test status displays the configured enforcement level."""
    with (
        patch(STATUS_CONFIG_PATCH, return_value=config_all_enabled),
        patch(STATUS_RESULT_PATCH, return_value=None),
    ):
        result = cli_runner.invoke(governance_group, ["status"])

    assert result.exit_code == 0
    assert "strict" in result.output.lower()


# ---------------------------------------------------------------------------
# Audit Command Tests (FR-025)
# ---------------------------------------------------------------------------

AUDIT_INTEGRATOR_PATCH = "floe_core.cli.governance.audit.create_governance_integrator"


@pytest.mark.requirement("003e-FR-025")
def test_audit_executes_all_checks(
    cli_runner: CliRunner,
    passing_result: EnforcementResult,
) -> None:
    """Test audit invokes GovernanceIntegrator.run_checks."""
    mock_integrator = MagicMock()
    mock_integrator.run_checks.return_value = passing_result

    with patch(AUDIT_INTEGRATOR_PATCH, return_value=mock_integrator):
        result = cli_runner.invoke(
            governance_group,
            ["audit", "--manifest", "manifest.yaml", "--spec", "floe.yaml"],
        )

    assert result.exit_code == 0
    mock_integrator.run_checks.assert_called_once()


@pytest.mark.requirement("003e-FR-025")
def test_audit_displays_violations_on_failure(
    cli_runner: CliRunner,
    failing_result: EnforcementResult,
) -> None:
    """Test audit displays violation details and exits non-zero on failure."""
    mock_integrator = MagicMock()
    mock_integrator.run_checks.return_value = failing_result

    with patch(AUDIT_INTEGRATOR_PATCH, return_value=mock_integrator):
        result = cli_runner.invoke(
            governance_group,
            ["audit", "--manifest", "manifest.yaml", "--spec", "floe.yaml"],
        )

    assert result.exit_code != 0
    output_lower = result.output.lower()
    assert "violation" in output_lower or "failed" in output_lower


@pytest.mark.requirement("003e-FR-025")
def test_audit_clean_pass(
    cli_runner: CliRunner,
    passing_result: EnforcementResult,
) -> None:
    """Test audit exits 0 and reports success when all checks pass."""
    mock_integrator = MagicMock()
    mock_integrator.run_checks.return_value = passing_result

    with patch(AUDIT_INTEGRATOR_PATCH, return_value=mock_integrator):
        result = cli_runner.invoke(
            governance_group,
            ["audit", "--manifest", "manifest.yaml", "--spec", "floe.yaml"],
        )

    assert result.exit_code == 0
    output_lower = result.output.lower()
    assert "pass" in output_lower or "success" in output_lower or "clean" in output_lower


@pytest.mark.requirement("003e-FR-025")
def test_audit_does_not_produce_artifacts(
    cli_runner: CliRunner,
    passing_result: EnforcementResult,
    tmp_path: Path,
) -> None:
    """Test audit does NOT write compiled artifacts to disk."""
    mock_integrator = MagicMock()
    mock_integrator.run_checks.return_value = passing_result

    target_dir = tmp_path / "target"

    with patch(AUDIT_INTEGRATOR_PATCH, return_value=mock_integrator):
        result = cli_runner.invoke(
            governance_group,
            ["audit", "--manifest", "manifest.yaml", "--spec", "floe.yaml"],
        )

    assert result.exit_code == 0
    assert not (target_dir / "compiled_artifacts.json").exists()


@pytest.mark.requirement("003e-FR-025")
def test_audit_respects_enforcement_level(
    cli_runner: CliRunner,
    passing_result: EnforcementResult,
) -> None:
    """Test audit passes --enforcement-level to GovernanceIntegrator."""
    mock_integrator = MagicMock()
    mock_integrator.run_checks.return_value = passing_result

    with patch(AUDIT_INTEGRATOR_PATCH, return_value=mock_integrator):
        result = cli_runner.invoke(
            governance_group,
            [
                "audit",
                "--manifest",
                "manifest.yaml",
                "--spec",
                "floe.yaml",
                "--enforcement-level",
                "warn",
            ],
        )

    assert result.exit_code == 0
    call_kwargs = mock_integrator.run_checks.call_args
    assert call_kwargs is not None
    _, kwargs = call_kwargs
    assert kwargs.get("enforcement_level") == "warn"


@pytest.mark.requirement("003e-FR-025")
def test_audit_dry_run_flag(
    cli_runner: CliRunner,
    passing_result: EnforcementResult,
) -> None:
    """Test audit passes --dry-run flag to GovernanceIntegrator."""
    mock_integrator = MagicMock()
    mock_integrator.run_checks.return_value = passing_result

    with patch(AUDIT_INTEGRATOR_PATCH, return_value=mock_integrator):
        result = cli_runner.invoke(
            governance_group,
            [
                "audit",
                "--manifest",
                "manifest.yaml",
                "--spec",
                "floe.yaml",
                "--dry-run",
            ],
        )

    assert result.exit_code == 0
    call_kwargs = mock_integrator.run_checks.call_args
    assert call_kwargs is not None
    _, kwargs = call_kwargs
    assert kwargs.get("dry_run") is True


# ---------------------------------------------------------------------------
# Report Command Tests (FR-026)
# ---------------------------------------------------------------------------

REPORT_INTEGRATOR_PATCH = "floe_core.cli.governance.report.create_governance_integrator"
REPORT_SARIF_PATCH = "floe_core.cli.governance.report.export_sarif"
REPORT_JSON_PATCH = "floe_core.cli.governance.report.export_json"
REPORT_HTML_PATCH = "floe_core.cli.governance.report.export_html"


@pytest.mark.requirement("003e-FR-026")
def test_report_sarif_format(
    cli_runner: CliRunner,
    failing_result: EnforcementResult,
    tmp_path: Path,
) -> None:
    """Test report --format sarif invokes the SARIF exporter."""
    output_file = tmp_path / "report.sarif"
    mock_integrator = MagicMock()
    mock_integrator.run_checks.return_value = failing_result

    with (
        patch(REPORT_INTEGRATOR_PATCH, return_value=mock_integrator),
        patch(REPORT_SARIF_PATCH, return_value=output_file) as mock_export,
    ):
        result = cli_runner.invoke(
            governance_group,
            [
                "report",
                "--format",
                "sarif",
                "--output",
                str(output_file),
                "--manifest",
                "manifest.yaml",
                "--spec",
                "floe.yaml",
            ],
        )

    assert result.exit_code == 0
    mock_export.assert_called_once()


@pytest.mark.requirement("003e-FR-026")
def test_report_json_format(
    cli_runner: CliRunner,
    failing_result: EnforcementResult,
    tmp_path: Path,
) -> None:
    """Test report --format json invokes the JSON exporter."""
    output_file = tmp_path / "report.json"
    mock_integrator = MagicMock()
    mock_integrator.run_checks.return_value = failing_result

    with (
        patch(REPORT_INTEGRATOR_PATCH, return_value=mock_integrator),
        patch(REPORT_JSON_PATCH, return_value=output_file) as mock_export,
    ):
        result = cli_runner.invoke(
            governance_group,
            [
                "report",
                "--format",
                "json",
                "--output",
                str(output_file),
                "--manifest",
                "manifest.yaml",
                "--spec",
                "floe.yaml",
            ],
        )

    assert result.exit_code == 0
    mock_export.assert_called_once()


@pytest.mark.requirement("003e-FR-026")
def test_report_html_format(
    cli_runner: CliRunner,
    failing_result: EnforcementResult,
    tmp_path: Path,
) -> None:
    """Test report --format html invokes the HTML exporter."""
    output_file = tmp_path / "report.html"
    mock_integrator = MagicMock()
    mock_integrator.run_checks.return_value = failing_result

    with (
        patch(REPORT_INTEGRATOR_PATCH, return_value=mock_integrator),
        patch(REPORT_HTML_PATCH, return_value=output_file) as mock_export,
    ):
        result = cli_runner.invoke(
            governance_group,
            [
                "report",
                "--format",
                "html",
                "--output",
                str(output_file),
                "--manifest",
                "manifest.yaml",
                "--spec",
                "floe.yaml",
            ],
        )

    assert result.exit_code == 0
    mock_export.assert_called_once()


@pytest.mark.requirement("003e-FR-026")
def test_report_invalid_format_rejected(cli_runner: CliRunner) -> None:
    """Test report rejects unsupported format values via Click.Choice."""
    result = cli_runner.invoke(
        governance_group,
        [
            "report",
            "--format",
            "xml",
            "--manifest",
            "manifest.yaml",
            "--spec",
            "floe.yaml",
        ],
    )

    # Click.Choice validation should reject 'xml'
    assert result.exit_code != 0


@pytest.mark.requirement("003e-FR-026")
def test_report_default_output_path(
    cli_runner: CliRunner,
    passing_result: EnforcementResult,
) -> None:
    """Test report uses a default output path when --output is omitted."""
    mock_integrator = MagicMock()
    mock_integrator.run_checks.return_value = passing_result

    with (
        patch(REPORT_INTEGRATOR_PATCH, return_value=mock_integrator),
        patch(REPORT_JSON_PATCH, return_value=Path("target/governance-report.json")) as mock_export,
    ):
        result = cli_runner.invoke(
            governance_group,
            [
                "report",
                "--format",
                "json",
                "--manifest",
                "manifest.yaml",
                "--spec",
                "floe.yaml",
            ],
        )

    assert result.exit_code == 0
    mock_export.assert_called_once()
    # Verify a default path was passed as second arg
    call_args = mock_export.call_args
    assert call_args is not None
    positional_args = call_args[0]
    assert len(positional_args) >= 2
    assert isinstance(positional_args[1], Path)


@pytest.mark.requirement("003e-FR-026")
def test_report_exporter_receives_enforcement_result(
    cli_runner: CliRunner,
    failing_result: EnforcementResult,
    tmp_path: Path,
) -> None:
    """Test report passes the EnforcementResult to the exporter."""
    output_file = tmp_path / "report.json"
    mock_integrator = MagicMock()
    mock_integrator.run_checks.return_value = failing_result

    with (
        patch(REPORT_INTEGRATOR_PATCH, return_value=mock_integrator),
        patch(REPORT_JSON_PATCH, return_value=output_file) as mock_export,
    ):
        result = cli_runner.invoke(
            governance_group,
            [
                "report",
                "--format",
                "json",
                "--output",
                str(output_file),
                "--manifest",
                "manifest.yaml",
                "--spec",
                "floe.yaml",
            ],
        )

    assert result.exit_code == 0
    call_args = mock_export.call_args
    assert call_args is not None
    # First positional arg should be the EnforcementResult
    exported_result = call_args[0][0]
    assert isinstance(exported_result, EnforcementResult)
    assert len(exported_result.violations) == 3
    assert exported_result.passed is False

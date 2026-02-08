"""Unit tests for the `floe sla report` CLI command.

This module tests the SLA compliance report CLI command, verifying:
- Table output formatting
- JSON output formatting
- Contract name filtering
- Time window filtering
- Error handling for empty data

Tasks: T062 (Epic 3D)
Requirements: 3D-FR-039
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from click.testing import CliRunner

from floe_core.cli.sla.report import report
from floe_core.contracts.monitoring.sla import (
    CheckTypeSummary,
    SLAComplianceReport,
    TrendDirection,
)
from floe_core.contracts.monitoring.violations import ViolationType


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create Click CLI test runner.

    Returns:
        Configured CliRunner for testing Click commands.
    """
    return CliRunner()


@pytest.fixture
def sample_report() -> SLAComplianceReport:
    """Create a sample SLA compliance report for testing.

    Returns:
        Sample report with realistic test data.
    """
    now = datetime.now(tz=timezone.utc)
    period_start = now - timedelta(weeks=1)

    check_summaries = [
        CheckTypeSummary(
            check_type=ViolationType.FRESHNESS,
            total_checks=288,
            passed_checks=286,
            failed_checks=2,
            error_checks=0,
            compliance_pct=99.3,
            avg_duration_seconds=0.45,
            violation_count=2,
            trend=TrendDirection.STABLE,
        ),
        CheckTypeSummary(
            check_type=ViolationType.SCHEMA_DRIFT,
            total_checks=24,
            passed_checks=24,
            failed_checks=0,
            error_checks=0,
            compliance_pct=100.0,
            avg_duration_seconds=1.2,
            violation_count=0,
            trend=TrendDirection.IMPROVING,
        ),
    ]

    return SLAComplianceReport(
        contract_name="test_contract",
        period_start=period_start,
        period_end=now,
        overall_compliance_pct=99.5,
        check_summaries=check_summaries,
        total_violations=2,
        total_checks_executed=312,
        monitoring_coverage_pct=98.0,
        generated_at=now,
    )


@pytest.fixture
def empty_report() -> SLAComplianceReport:
    """Create an empty SLA compliance report (no checks executed).

    Returns:
        Report with zero checks and violations.
    """
    now = datetime.now(tz=timezone.utc)
    period_start = now - timedelta(days=1)

    return SLAComplianceReport(
        contract_name="empty_contract",
        period_start=period_start,
        period_end=now,
        overall_compliance_pct=0.0,
        check_summaries=[],
        total_violations=0,
        total_checks_executed=0,
        monitoring_coverage_pct=0.0,
        generated_at=now,
    )


@pytest.mark.requirement("3D-FR-039")
def test_report_table_output_format(
    cli_runner: CliRunner, sample_report: SLAComplianceReport
) -> None:
    """Test SLA report table output format displays correct headers and data.

    Verifies that the table format includes:
    - Contract name header
    - Period dates
    - Overall compliance metrics
    - Check type summary table with correct columns
    - All check types displayed

    Args:
        cli_runner: Click CLI test runner fixture.
        sample_report: Sample compliance report fixture.
    """

    def mock_data_source(**kwargs: str | None) -> SLAComplianceReport:
        """Mock data source returning the sample report.

        Args:
            **kwargs: Ignored arguments.

        Returns:
            Sample report for testing.
        """
        return sample_report

    result = cli_runner.invoke(
        report,
        ["--format", "table"],
        obj={"_data_source": mock_data_source},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify table headers and content
    assert "SLA COMPLIANCE REPORT" in result.output
    assert sample_report.contract_name in result.output
    assert f"Overall Compliance: {sample_report.overall_compliance_pct:.1f}%" in result.output
    assert f"Total Violations: {sample_report.total_violations}" in result.output
    assert f"Total Checks Executed: {sample_report.total_checks_executed}" in result.output

    # Verify check type table headers
    assert "Check Type" in result.output
    assert "Total" in result.output
    assert "Pass" in result.output
    assert "Fail" in result.output
    assert "Compliance" in result.output
    assert "Trend" in result.output

    # Verify check type data
    assert "freshness" in result.output
    assert "schema_drift" in result.output
    assert "99.3%" in result.output
    assert "100.0%" in result.output


@pytest.mark.requirement("3D-FR-039")
def test_report_json_output_format(
    cli_runner: CliRunner, sample_report: SLAComplianceReport
) -> None:
    """Test SLA report JSON output format produces valid JSON with correct fields.

    Verifies that:
    - Output is valid JSON
    - All required fields are present
    - Field values match the report data

    Args:
        cli_runner: Click CLI test runner fixture.
        sample_report: Sample compliance report fixture.
    """

    def mock_data_source(**kwargs: str | None) -> SLAComplianceReport:
        """Mock data source returning the sample report.

        Args:
            **kwargs: Ignored arguments.

        Returns:
            Sample report for testing.
        """
        return sample_report

    result = cli_runner.invoke(
        report,
        ["--format", "json"],
        obj={"_data_source": mock_data_source},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Extract JSON from output (skip log lines)
    # Find the first '{' and extract from there
    start_idx = result.output.find("{")
    assert start_idx >= 0, "No JSON found in output"

    # Find the matching closing '}'
    brace_count = 0
    end_idx = start_idx
    for i, char in enumerate(result.output[start_idx:], start=start_idx):
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break

    json_output = result.output[start_idx:end_idx]

    # Parse JSON output
    data = json.loads(json_output)

    # Verify required fields
    assert data["contract_name"] == sample_report.contract_name
    assert data["overall_compliance_pct"] == pytest.approx(sample_report.overall_compliance_pct)
    assert data["total_violations"] == sample_report.total_violations
    assert data["total_checks_executed"] == sample_report.total_checks_executed
    assert len(data["check_summaries"]) == len(sample_report.check_summaries)

    # Verify check summaries
    for i, summary_data in enumerate(data["check_summaries"]):
        original_summary = sample_report.check_summaries[i]
        assert summary_data["check_type"] == original_summary.check_type.value
        assert summary_data["total_checks"] == original_summary.total_checks
        assert summary_data["compliance_pct"] == pytest.approx(original_summary.compliance_pct)


@pytest.mark.requirement("3D-FR-039")
def test_report_contract_filter(cli_runner: CliRunner, sample_report: SLAComplianceReport) -> None:
    """Test SLA report --contract filter applies to report generation.

    Verifies that the contract filter is passed to the data source and
    the report shows the filtered contract name.

    Args:
        cli_runner: Click CLI test runner fixture.
        sample_report: Sample compliance report fixture.
    """
    contract_name = "orders_v1"

    def mock_data_source(contract_name: str | None = None, **kwargs: str) -> SLAComplianceReport:
        """Mock data source that checks the contract_name parameter.

        Args:
            contract_name: Contract name filter (should match expected).
            **kwargs: Other ignored arguments.

        Returns:
            Modified sample report with the requested contract name.
        """
        # Create a copy with the requested contract name
        return SLAComplianceReport(
            contract_name=contract_name or "default",
            period_start=sample_report.period_start,
            period_end=sample_report.period_end,
            overall_compliance_pct=sample_report.overall_compliance_pct,
            check_summaries=sample_report.check_summaries,
            total_violations=sample_report.total_violations,
            total_checks_executed=sample_report.total_checks_executed,
            monitoring_coverage_pct=sample_report.monitoring_coverage_pct,
            generated_at=sample_report.generated_at,
        )

    result = cli_runner.invoke(
        report,
        ["--contract", contract_name, "--format", "table"],
        obj={"_data_source": mock_data_source},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert contract_name in result.output


@pytest.mark.requirement("3D-FR-039")
def test_report_window_filter_daily(
    cli_runner: CliRunner, sample_report: SLAComplianceReport
) -> None:
    """Test SLA report --window daily filter produces correct time window.

    Args:
        cli_runner: Click CLI test runner fixture.
        sample_report: Sample compliance report fixture.
    """

    def mock_data_source(window: str = "weekly", **kwargs: str | None) -> SLAComplianceReport:
        """Mock data source that verifies window parameter.

        Args:
            window: Time window filter (should be 'daily').
            **kwargs: Other ignored arguments.

        Returns:
            Sample report for testing.
        """
        assert window == "daily", f"Expected window='daily', got '{window}'"
        return sample_report

    result = cli_runner.invoke(
        report,
        ["--window", "daily", "--format", "json"],
        obj={"_data_source": mock_data_source},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"


@pytest.mark.requirement("3D-FR-039")
def test_report_window_filter_weekly(
    cli_runner: CliRunner, sample_report: SLAComplianceReport
) -> None:
    """Test SLA report --window weekly filter produces correct time window.

    Args:
        cli_runner: Click CLI test runner fixture.
        sample_report: Sample compliance report fixture.
    """

    def mock_data_source(window: str = "weekly", **kwargs: str | None) -> SLAComplianceReport:
        """Mock data source that verifies window parameter.

        Args:
            window: Time window filter (should be 'weekly').
            **kwargs: Other ignored arguments.

        Returns:
            Sample report for testing.
        """
        assert window == "weekly", f"Expected window='weekly', got '{window}'"
        return sample_report

    result = cli_runner.invoke(
        report,
        ["--window", "weekly", "--format", "json"],
        obj={"_data_source": mock_data_source},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"


@pytest.mark.requirement("3D-FR-039")
def test_report_window_filter_monthly(
    cli_runner: CliRunner, sample_report: SLAComplianceReport
) -> None:
    """Test SLA report --window monthly filter produces correct time window.

    Args:
        cli_runner: Click CLI test runner fixture.
        sample_report: Sample compliance report fixture.
    """

    def mock_data_source(window: str = "weekly", **kwargs: str | None) -> SLAComplianceReport:
        """Mock data source that verifies window parameter.

        Args:
            window: Time window filter (should be 'monthly').
            **kwargs: Other ignored arguments.

        Returns:
            Sample report for testing.
        """
        assert window == "monthly", f"Expected window='monthly', got '{window}'"
        return sample_report

    result = cli_runner.invoke(
        report,
        ["--window", "monthly", "--format", "json"],
        obj={"_data_source": mock_data_source},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"


@pytest.mark.requirement("3D-FR-039")
def test_report_empty_results(cli_runner: CliRunner, empty_report: SLAComplianceReport) -> None:
    """Test SLA report handles empty results (no checks executed).

    Verifies that the command succeeds and displays appropriate output
    when there are no checks or violations to report.

    Args:
        cli_runner: Click CLI test runner fixture.
        empty_report: Empty compliance report fixture.
    """

    def mock_data_source(**kwargs: str | None) -> SLAComplianceReport:
        """Mock data source returning an empty report.

        Args:
            **kwargs: Ignored arguments.

        Returns:
            Empty report for testing.
        """
        return empty_report

    result = cli_runner.invoke(
        report,
        ["--format", "table"],
        obj={"_data_source": mock_data_source},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify empty report displays correctly
    assert "empty_contract" in result.output
    assert "Total Violations: 0" in result.output
    assert "Total Checks Executed: 0" in result.output


@pytest.mark.requirement("3D-FR-039")
def test_report_default_arguments(
    cli_runner: CliRunner, sample_report: SLAComplianceReport
) -> None:
    """Test SLA report with no arguments uses defaults (weekly, table).

    Args:
        cli_runner: Click CLI test runner fixture.
        sample_report: Sample compliance report fixture.
    """

    def mock_data_source(window: str = "weekly", **kwargs: str | None) -> SLAComplianceReport:
        """Mock data source that checks default window parameter.

        Args:
            window: Time window filter (should default to 'weekly').
            **kwargs: Other ignored arguments.

        Returns:
            Sample report for testing.
        """
        assert window == "weekly", f"Expected default window='weekly', got '{window}'"
        return sample_report

    result = cli_runner.invoke(
        report,
        [],
        obj={"_data_source": mock_data_source},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify table format (default)
    assert "SLA COMPLIANCE REPORT" in result.output
    assert "Check Type" in result.output

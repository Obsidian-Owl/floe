"""SLA compliance report CLI command implementation.

This module implements the `floe sla report` command for generating SLA compliance
reports from contract monitoring data (FR-039).

Tasks: T066 (Epic 3D)
Requirements: FR-039
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable

import click
import structlog

from floe_core.contracts.monitoring.sla import (
    CheckTypeSummary,
    SLAComplianceReport,
    TrendDirection,
)
from floe_core.contracts.monitoring.violations import ViolationType

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


def _generate_sample_report(
    *,
    contract_name: str | None = None,
    window: str = "weekly",
) -> SLAComplianceReport:
    """Generate sample SLA compliance report for demonstration.

    This function generates mock data for the CLI command. In production,
    this would be replaced by a database query to retrieve actual monitoring data.

    Args:
        contract_name: Optional contract name to filter by.
        window: Time window for the report (daily/weekly/monthly).

    Returns:
        Sample SLAComplianceReport with realistic data.
    """
    # Calculate period based on window
    now = datetime.now(tz=timezone.utc)
    if window == "daily":
        period_start = now - timedelta(days=1)
    elif window == "weekly":
        period_start = now - timedelta(weeks=1)
    elif window == "monthly":
        period_start = now - timedelta(days=30)
    else:
        period_start = now - timedelta(weeks=1)

    # Sample check summaries
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
        CheckTypeSummary(
            check_type=ViolationType.QUALITY,
            total_checks=288,
            passed_checks=285,
            failed_checks=3,
            error_checks=0,
            compliance_pct=99.0,
            avg_duration_seconds=2.1,
            violation_count=3,
            trend=TrendDirection.DEGRADING,
        ),
    ]

    return SLAComplianceReport(
        contract_name=contract_name or "sample_contract",
        period_start=period_start,
        period_end=now,
        overall_compliance_pct=99.4,
        check_summaries=check_summaries,
        total_violations=5,
        total_checks_executed=600,
        monitoring_coverage_pct=98.5,
        generated_at=now,
    )


def _format_table(report: SLAComplianceReport) -> str:
    """Format SLA compliance report as a table.

    Args:
        report: SLA compliance report to format.

    Returns:
        Formatted table string suitable for terminal display.
    """
    lines = []
    lines.append("=" * 80)
    lines.append(f"SLA COMPLIANCE REPORT: {report.contract_name}")
    lines.append("=" * 80)
    lines.append(f"Period: {report.period_start.isoformat()} to {report.period_end.isoformat()}")
    lines.append(f"Generated: {report.generated_at.isoformat()}")
    lines.append("")
    lines.append(f"Overall Compliance: {report.overall_compliance_pct:.1f}%")
    lines.append(f"Total Violations: {report.total_violations}")
    lines.append(f"Total Checks Executed: {report.total_checks_executed}")
    lines.append(f"Monitoring Coverage: {report.monitoring_coverage_pct:.1f}%")
    lines.append("")
    lines.append("CHECK TYPE SUMMARY")
    lines.append("-" * 80)
    lines.append(
        f"{'Check Type':<20} {'Total':>8} {'Pass':>8} {'Fail':>8} "
        f"{'Compliance':>12} {'Trend':>12}"
    )
    lines.append("-" * 80)

    for summary in report.check_summaries:
        lines.append(
            f"{summary.check_type.value:<20} "
            f"{summary.total_checks:>8} "
            f"{summary.passed_checks:>8} "
            f"{summary.failed_checks:>8} "
            f"{summary.compliance_pct:>11.1f}% "
            f"{summary.trend.value:>12}"
        )

    lines.append("=" * 80)
    return "\n".join(lines)


def _format_json(report: SLAComplianceReport) -> str:
    """Format SLA compliance report as JSON.

    Args:
        report: SLA compliance report to format.

    Returns:
        JSON string representation of the report.
    """
    # Use Pydantic's model_dump with serialization mode
    return json.dumps(report.model_dump(mode="json"), indent=2, default=str)


@click.command(name="report")
@click.option(
    "--contract",
    type=str,
    default=None,
    help="Filter by contract name (optional, shows all if not specified).",
)
@click.option(
    "--window",
    type=click.Choice(["daily", "weekly", "monthly"], case_sensitive=False),
    default="weekly",
    help="Time window for the report (default: weekly).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (default: table).",
)
@click.pass_context
def report(
    ctx: click.Context,
    contract: str | None,
    window: str,
    output_format: str,
) -> None:
    """Generate SLA compliance report for contract monitoring.

    Generates a compliance report showing:
    - Overall compliance percentage
    - Per-check-type summary statistics
    - Violation counts and trends
    - Monitoring coverage metrics

    Examples:
        floe sla report --contract orders_v1 --window weekly --format table
        floe sla report --format json

    Args:
        ctx: Click context (contains test data source if provided).
        contract: Optional contract name filter.
        window: Time window (daily/weekly/monthly).
        output_format: Output format (table/json).
    """
    logger.info(
        "Generating SLA compliance report",
        contract=contract,
        window=window,
        output_format=output_format,
    )

    try:
        # Get test data source from context if available
        data_source: Callable[..., SLAComplianceReport] | None = ctx.obj.get(
            "_data_source"
        ) if ctx.obj else None

        # Generate report (use test data source if provided, otherwise sample data)
        if data_source is not None:
            compliance_report = data_source(contract_name=contract, window=window)
        else:
            compliance_report = _generate_sample_report(contract_name=contract, window=window)

        # Format output
        if output_format == "json":
            output = _format_json(compliance_report)
        else:
            output = _format_table(compliance_report)

        # Write to stdout
        click.echo(output)

        logger.info("SLA report generated successfully")

    except Exception as e:
        logger.error("Failed to generate SLA report", error=str(e))
        click.echo(f"Error: Failed to generate report: {e}", err=True)
        sys.exit(1)

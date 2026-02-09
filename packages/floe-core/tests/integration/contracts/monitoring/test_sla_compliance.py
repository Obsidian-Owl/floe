"""Integration tests for SLA compliance and incident management.

Tests FR-029 — SLA threshold evaluation and incident creation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from floe_core.contracts.monitoring.incident import (
    SEVERITY_TO_PRIORITY,
    Incident,
    IncidentManager,
    IncidentPriority,
    IncidentStatus,
)
from floe_core.contracts.monitoring.sla import (
    SLAComplianceReport,
    TrendDirection,
    aggregate_daily,
    calculate_compliance,
    compute_trend,
)
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)

# SLA Compliance Tests


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-029")
async def test_calculate_compliance_all_pass() -> None:
    """Test compliance calculation when all checks pass."""
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(hours=1)
    period_end = now

    check_results = [
        {
            "contract_name": "orders_v1",
            "check_type": "freshness",
            "status": "pass",
            "duration_seconds": 0.5,
            "timestamp": period_start + timedelta(minutes=i * 10),
        }
        for i in range(6)
    ]

    report = calculate_compliance(
        check_results=check_results,
        period_start=period_start,
        period_end=period_end,
        contract_name="orders_v1",
    )

    assert isinstance(report, SLAComplianceReport)
    assert report.contract_name == "orders_v1"
    assert report.overall_compliance_pct == pytest.approx(100.0)
    assert report.total_checks_executed == 6
    assert report.total_violations == 0
    assert len(report.check_summaries) == 1
    assert report.check_summaries[0].check_type == ViolationType.FRESHNESS
    assert report.check_summaries[0].compliance_pct == pytest.approx(100.0)
    assert report.check_summaries[0].passed_checks == 6
    assert report.check_summaries[0].failed_checks == 0


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-029")
async def test_calculate_compliance_mixed_results() -> None:
    """Test compliance calculation with mixed pass/fail results."""
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(hours=1)
    period_end = now

    # 8 checks: 6 pass, 2 fail = 75% compliance
    check_results = [
        {
            "contract_name": "customers_v2",
            "check_type": "quality",
            "status": "pass",
            "duration_seconds": 0.3,
            "timestamp": period_start + timedelta(minutes=i * 5),
        }
        for i in range(6)
    ] + [
        {
            "contract_name": "customers_v2",
            "check_type": "quality",
            "status": "fail",
            "duration_seconds": 0.4,
            "timestamp": period_start + timedelta(minutes=(i + 6) * 5),
        }
        for i in range(2)
    ]

    report = calculate_compliance(
        check_results=check_results,
        period_start=period_start,
        period_end=period_end,
        contract_name="customers_v2",
    )

    assert report.contract_name == "customers_v2"
    assert report.overall_compliance_pct == pytest.approx(75.0)
    assert report.total_checks_executed == 8
    assert report.total_violations == 2
    assert len(report.check_summaries) == 1

    summary = report.check_summaries[0]
    assert summary.check_type == ViolationType.QUALITY
    assert summary.total_checks == 8
    assert summary.passed_checks == 6
    assert summary.failed_checks == 2
    assert summary.compliance_pct == pytest.approx(75.0)
    assert summary.avg_duration_seconds == pytest.approx(0.325)  # (6*0.3 + 2*0.4)/8


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-029")
async def test_calculate_compliance_empty_results() -> None:
    """Test compliance calculation with no check results."""
    now = datetime.now(timezone.utc)

    report = calculate_compliance(
        check_results=[],
        period_start=now - timedelta(hours=1),
        period_end=now,
        contract_name="empty_contract",
    )

    assert report.contract_name == "empty_contract"
    assert report.overall_compliance_pct == pytest.approx(0.0)
    assert report.total_checks_executed == 0
    assert report.total_violations == 0
    assert len(report.check_summaries) == 0


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-029")
async def test_aggregate_daily_groups_by_date_and_type() -> None:
    """Test daily aggregation groups results by date and check type."""
    base_date = datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc)

    check_results = [
        # Day 1 - freshness checks
        {
            "timestamp": base_date + timedelta(hours=1),
            "check_type": "freshness",
            "status": "pass",
        },
        {
            "timestamp": base_date + timedelta(hours=2),
            "check_type": "freshness",
            "status": "fail",
        },
        # Day 1 - quality checks
        {
            "timestamp": base_date + timedelta(hours=3),
            "check_type": "quality",
            "status": "pass",
        },
        # Day 2 - freshness checks
        {
            "timestamp": base_date + timedelta(days=1, hours=1),
            "check_type": "freshness",
            "status": "pass",
        },
        {
            "timestamp": base_date + timedelta(days=1, hours=2),
            "check_type": "freshness",
            "status": "pass",
        },
    ]

    aggregated = aggregate_daily(check_results)

    day1_key = base_date.date().isoformat()
    day2_key = (base_date + timedelta(days=1)).date().isoformat()

    assert day1_key in aggregated
    assert day2_key in aggregated

    # Day 1 aggregation
    assert aggregated[day1_key]["freshness"]["total"] == 2
    assert aggregated[day1_key]["freshness"]["passed"] == 1
    assert aggregated[day1_key]["freshness"]["failed"] == 1
    assert aggregated[day1_key]["quality"]["total"] == 1
    assert aggregated[day1_key]["quality"]["passed"] == 1

    # Day 2 aggregation
    assert aggregated[day2_key]["freshness"]["total"] == 2
    assert aggregated[day2_key]["freshness"]["passed"] == 2
    assert aggregated[day2_key]["freshness"]["failed"] == 0


# Trend Tests


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-029")
async def test_compute_trend_improving() -> None:
    """Test trend computation detects improving compliance."""
    daily_compliance = [70.0, 75.0, 80.0, 85.0, 90.0]

    trend = compute_trend(daily_compliance, threshold=2.0)

    assert trend == TrendDirection.IMPROVING


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-029")
async def test_compute_trend_degrading() -> None:
    """Test trend computation detects degrading compliance."""
    daily_compliance = [95.0, 90.0, 85.0, 75.0, 70.0]

    trend = compute_trend(daily_compliance, threshold=2.0)

    assert trend == TrendDirection.DEGRADING


# Incident Tests


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-029")
async def test_incident_creation_from_violation() -> None:
    """Test incident creation from contract violation event."""
    manager = IncidentManager()
    event = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data freshness violated: 48 hours old",
        timestamp=datetime.now(timezone.utc),
        check_duration_seconds=0.5,
    )

    incident, is_new = manager.create_or_correlate(event)

    assert is_new is True
    assert isinstance(incident, Incident)
    assert incident.contract_name == "orders_v1"
    assert incident.violation_type == ViolationType.FRESHNESS
    assert incident.status == IncidentStatus.OPEN
    assert incident.priority == SEVERITY_TO_PRIORITY[ViolationSeverity.ERROR]
    assert incident.priority == IncidentPriority.P2
    assert incident.violation_count == 1
    assert "Freshness" in incident.title


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-029")
async def test_incident_correlation_repeated_violations() -> None:
    """Test repeated violations correlate to existing incident."""
    manager = IncidentManager()
    base_time = datetime.now(timezone.utc)

    event1 = ContractViolationEvent(
        contract_name="customers_v2",
        contract_version="2.0.0",
        violation_type=ViolationType.QUALITY,
        severity=ViolationSeverity.WARNING,
        message="Quality check failed: null values detected",
        timestamp=base_time,
        check_duration_seconds=0.3,
    )

    event2 = ContractViolationEvent(
        contract_name="customers_v2",
        contract_version="2.0.0",
        violation_type=ViolationType.QUALITY,
        severity=ViolationSeverity.WARNING,
        message="Quality check failed: duplicate rows detected",
        timestamp=base_time + timedelta(minutes=5),
        check_duration_seconds=0.4,
    )

    incident1, is_new1 = manager.create_or_correlate(event1)
    incident2, is_new2 = manager.create_or_correlate(event2)

    assert is_new1 is True
    assert is_new2 is False  # Correlated to existing incident
    assert incident1.id == incident2.id  # Same incident
    assert incident2.violation_count == 2  # Count incremented
    assert incident2.updated_at >= incident2.created_at


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-029")
async def test_incident_priority_escalation() -> None:
    """Test incident priority escalates with higher severity violation."""
    manager = IncidentManager()
    base_time = datetime.now(timezone.utc)

    event1 = ContractViolationEvent(
        contract_name="products_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.SCHEMA_DRIFT,
        severity=ViolationSeverity.WARNING,
        message="Schema drift detected: new optional field",
        timestamp=base_time,
        check_duration_seconds=0.2,
    )

    event2 = ContractViolationEvent(
        contract_name="products_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.SCHEMA_DRIFT,
        severity=ViolationSeverity.CRITICAL,
        message="Schema drift detected: required field removed",
        timestamp=base_time + timedelta(minutes=10),
        check_duration_seconds=0.3,
    )

    incident1, is_new1 = manager.create_or_correlate(event1)
    initial_priority = incident1.priority

    incident2, is_new2 = manager.create_or_correlate(event2)
    escalated_priority = incident2.priority

    assert is_new1 is True
    assert is_new2 is False  # Same incident
    assert incident1.id == incident2.id
    assert initial_priority == IncidentPriority.P3  # WARNING -> P3
    assert escalated_priority == IncidentPriority.P1  # CRITICAL -> P1


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-029")
async def test_incident_resolved_prevents_correlation() -> None:
    """Test resolved incident does not receive new correlations."""
    manager = IncidentManager()
    base_time = datetime.now(timezone.utc)

    event1 = ContractViolationEvent(
        contract_name="inventory_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.AVAILABILITY,
        severity=ViolationSeverity.ERROR,
        message="Service unavailable",
        timestamp=base_time,
        check_duration_seconds=1.0,
    )

    # Create and resolve incident
    incident1, _ = manager.create_or_correlate(event1)
    resolved_incident = manager.resolve_incident(incident1.id)
    assert resolved_incident is not None
    assert resolved_incident.status == IncidentStatus.RESOLVED

    # New violation of same type after resolution
    event2 = ContractViolationEvent(
        contract_name="inventory_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.AVAILABILITY,
        severity=ViolationSeverity.ERROR,
        message="Service unavailable again",
        timestamp=base_time + timedelta(hours=1),
        check_duration_seconds=1.5,
    )

    incident2, is_new2 = manager.create_or_correlate(event2)

    assert is_new2 is True  # New incident created
    assert incident1.id != incident2.id  # Different incidents
    assert incident1.status == IncidentStatus.RESOLVED
    assert incident2.status == IncidentStatus.OPEN
    assert incident1.violation_count == 1  # Original unchanged
    assert incident2.violation_count == 1  # New incident starts at 1

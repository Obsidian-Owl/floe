"""Unit tests for incident management.

Tasks: T069 (Epic 3D)
Requirements: FR-040, FR-041, FR-042
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from floe_core.contracts.monitoring.incident import (
    SEVERITY_TO_PRIORITY,
    IncidentManager,
    IncidentPriority,
    IncidentStatus,
)
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)


@pytest.mark.requirement("3D-FR-040")
def test_severity_to_priority_mapping() -> None:
    """Test that all ViolationSeverity values map to IncidentPriority correctly."""
    assert SEVERITY_TO_PRIORITY[ViolationSeverity.CRITICAL] == IncidentPriority.P1
    assert SEVERITY_TO_PRIORITY[ViolationSeverity.ERROR] == IncidentPriority.P2
    assert SEVERITY_TO_PRIORITY[ViolationSeverity.WARNING] == IncidentPriority.P3
    assert SEVERITY_TO_PRIORITY[ViolationSeverity.INFO] == IncidentPriority.P4


@pytest.mark.requirement("3D-FR-040")
def test_create_new_incident() -> None:
    """Test that a new violation creates a new incident with is_new=True."""
    manager = IncidentManager()
    event = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )

    incident, is_new = manager.create_or_correlate(event)

    assert is_new is True
    assert incident.priority == IncidentPriority.P2  # ERROR -> P2
    assert incident.status == IncidentStatus.OPEN
    assert incident.contract_name == "orders_v1"
    assert incident.violation_type == ViolationType.FRESHNESS
    assert incident.violation_count == 1
    assert len(incident.related_violations) == 1
    assert incident.title == "Freshness violation on orders_v1"


@pytest.mark.requirement("3D-FR-041")
def test_correlate_to_existing_incident() -> None:
    """Test that same contract+type correlates to existing incident."""
    manager = IncidentManager()
    event1 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )
    event2 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 3.0 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )

    incident1, is_new1 = manager.create_or_correlate(event1)
    incident2, is_new2 = manager.create_or_correlate(event2)

    assert is_new1 is True
    assert is_new2 is False
    assert incident1.id == incident2.id
    assert incident2.violation_count == 2
    assert len(incident2.related_violations) == 2


@pytest.mark.requirement("3D-FR-041")
def test_no_correlation_different_contract() -> None:
    """Test that different contract_name creates separate incident."""
    manager = IncidentManager()
    event1 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )
    event2 = ContractViolationEvent(
        contract_name="customers_v1",  # Different contract
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )

    incident1, is_new1 = manager.create_or_correlate(event1)
    incident2, is_new2 = manager.create_or_correlate(event2)

    assert is_new1 is True
    assert is_new2 is True
    assert incident1.id != incident2.id


@pytest.mark.requirement("3D-FR-041")
def test_no_correlation_different_type() -> None:
    """Test that different violation_type creates separate incident."""
    manager = IncidentManager()
    event1 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )
    event2 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.SCHEMA_DRIFT,  # Different type
        severity=ViolationSeverity.ERROR,
        message="Schema mismatch detected",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )

    incident1, is_new1 = manager.create_or_correlate(event1)
    incident2, is_new2 = manager.create_or_correlate(event2)

    assert is_new1 is True
    assert is_new2 is True
    assert incident1.id != incident2.id


@pytest.mark.requirement("3D-FR-042")
def test_priority_escalation() -> None:
    """Test that WARNING incident is escalated to ERROR when ERROR violation arrives."""
    manager = IncidentManager()
    event1 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.WARNING,
        message="Data is 1.8 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )
    event2 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )

    incident1, _ = manager.create_or_correlate(event1)
    assert incident1.priority == IncidentPriority.P3  # WARNING -> P3

    incident2, _ = manager.create_or_correlate(event2)
    assert incident2.id == incident1.id
    assert incident2.priority == IncidentPriority.P2  # Escalated to ERROR -> P2


@pytest.mark.requirement("3D-FR-042")
def test_no_priority_downgrade() -> None:
    """Test that ERROR incident stays ERROR when WARNING violation arrives."""
    manager = IncidentManager()
    event1 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )
    event2 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.WARNING,
        message="Data is 1.8 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )

    incident1, _ = manager.create_or_correlate(event1)
    assert incident1.priority == IncidentPriority.P2  # ERROR -> P2

    incident2, _ = manager.create_or_correlate(event2)
    assert incident2.id == incident1.id
    assert incident2.priority == IncidentPriority.P2  # Stays P2


@pytest.mark.requirement("3D-FR-041")
def test_resolved_incident_no_correlation() -> None:
    """Test that resolved incident does NOT correlate, new incident is created."""
    manager = IncidentManager()
    event1 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )

    incident1, _ = manager.create_or_correlate(event1)
    manager.resolve_incident(incident1.id)

    event2 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 3.0 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )

    incident2, is_new2 = manager.create_or_correlate(event2)
    assert is_new2 is True
    assert incident2.id != incident1.id


@pytest.mark.requirement("3D-FR-040")
def test_resolve_incident() -> None:
    """Test that resolve_incident changes status to RESOLVED."""
    manager = IncidentManager()
    event = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )

    incident, _ = manager.create_or_correlate(event)
    assert incident.status == IncidentStatus.OPEN

    resolved = manager.resolve_incident(incident.id)
    assert resolved is not None
    assert resolved.status == IncidentStatus.RESOLVED


@pytest.mark.requirement("3D-FR-040")
def test_get_open_incidents() -> None:
    """Test that get_open_incidents returns only OPEN status incidents."""
    manager = IncidentManager()
    event1 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )
    event2 = ContractViolationEvent(
        contract_name="customers_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.SCHEMA_DRIFT,
        severity=ViolationSeverity.WARNING,
        message="Schema mismatch detected",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )

    incident1, _ = manager.create_or_correlate(event1)
    incident2, _ = manager.create_or_correlate(event2)
    manager.resolve_incident(incident1.id)

    open_incidents = manager.get_open_incidents()
    assert len(open_incidents) == 1
    assert open_incidents[0].id == incident2.id


@pytest.mark.requirement("3D-FR-041")
def test_incident_related_violations() -> None:
    """Test that related_violations list is populated correctly."""
    manager = IncidentManager()
    event1 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.WARNING,
        message="Data is 1.8 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )
    event2 = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.6,
    )

    incident1, _ = manager.create_or_correlate(event1)
    incident2, _ = manager.create_or_correlate(event2)

    assert len(incident2.related_violations) == 2
    assert incident2.related_violations[0]["severity"] == ViolationSeverity.WARNING
    assert incident2.related_violations[0]["message"] == "Data is 1.8 hours old"
    assert incident2.related_violations[1]["severity"] == ViolationSeverity.ERROR
    assert incident2.related_violations[1]["message"] == "Data is 2.5 hours old"

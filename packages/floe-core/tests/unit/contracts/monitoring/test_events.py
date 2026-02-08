"""Unit tests for OpenLineage event emission.

Tests the creation of OpenLineage RunEvents for contract violations,
validating event structure, facet formatting, and field mapping.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

import pytest

from floe_core.contracts.monitoring.events import (
    build_contract_violation_facet,
    create_violation_run_event,
)
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)


def _make_violation(
    *,
    contract_name: str = "test_contract",
    contract_version: str = "1.0.0",
    violation_type: ViolationType = ViolationType.FRESHNESS,
    severity: ViolationSeverity = ViolationSeverity.ERROR,
    message: str = "Test violation",
    element: str | None = None,
    expected_value: str | None = None,
    actual_value: str | None = None,
    affected_consumers: list[str] | None = None,
    check_duration_seconds: float = 0.5,
    metadata: dict[str, str] | None = None,
) -> ContractViolationEvent:
    """Create a test violation event.

    Args:
        contract_name: Name of the contract
        contract_version: Version of the contract
        violation_type: Type of violation
        severity: Severity level
        message: Human-readable message
        element: Optional element identifier
        expected_value: Optional expected value
        actual_value: Optional actual value
        affected_consumers: Optional list of affected consumers
        check_duration_seconds: Duration of the check
        metadata: Optional additional metadata

    Returns:
        ContractViolationEvent instance
    """
    return ContractViolationEvent(
        contract_name=contract_name,
        contract_version=contract_version,
        violation_type=violation_type,
        severity=severity,
        message=message,
        element=element,
        expected_value=expected_value,
        actual_value=actual_value,
        timestamp=datetime.now(tz=timezone.utc),
        affected_consumers=affected_consumers or [],
        check_duration_seconds=check_duration_seconds,
        metadata=metadata or {},
    )


@pytest.mark.requirement("3D-FR-030")
def test_create_violation_run_event_structure() -> None:
    """Test create_violation_run_event returns correct RunEvent structure."""
    violation = _make_violation()

    event = create_violation_run_event(violation)

    # Verify top-level structure
    assert event["eventType"] == "FAIL"
    assert "eventTime" in event
    assert "run" in event
    assert "job" in event
    assert "producer" in event
    assert "inputs" in event
    assert "outputs" in event


@pytest.mark.requirement("3D-FR-030")
def test_create_violation_run_event_fail_type() -> None:
    """Test run event has eventType=FAIL for violations."""
    violation = _make_violation(severity=ViolationSeverity.CRITICAL)

    event = create_violation_run_event(violation)

    assert event["eventType"] == "FAIL"


@pytest.mark.requirement("3D-FR-030")
def test_run_event_has_valid_uuid() -> None:
    """Test run event contains a valid UUID runId."""
    violation = _make_violation()

    event = create_violation_run_event(violation)

    run_id = event["run"]["runId"]
    # Verify it's a valid UUID by parsing it
    parsed_uuid = UUID(run_id)
    assert str(parsed_uuid) == run_id


@pytest.mark.requirement("3D-FR-030")
def test_job_namespace_is_contract_monitor() -> None:
    """Test job namespace is 'floe.contract_monitor'."""
    violation = _make_violation()

    event = create_violation_run_event(violation)

    assert event["job"]["namespace"] == "floe.contract_monitor"


@pytest.mark.requirement("3D-FR-030")
def test_job_name_pattern() -> None:
    """Test job name follows pattern '{contract_name}.{violation_type}'."""
    violation = _make_violation(
        contract_name="orders_contract",
        violation_type=ViolationType.SCHEMA_DRIFT,
    )

    event = create_violation_run_event(violation)

    expected_name = "orders_contract.schema_drift"
    assert event["job"]["name"] == expected_name


@pytest.mark.requirement("3D-FR-030")
def test_job_name_pattern_variations() -> None:
    """Test job name pattern for different violation types."""
    test_cases = [
        ("test_contract", ViolationType.FRESHNESS, "test_contract.freshness"),
        ("orders", ViolationType.QUALITY, "orders.quality"),
        ("users", ViolationType.AVAILABILITY, "users.availability"),
        ("payments", ViolationType.DEPRECATION, "payments.deprecation"),
    ]

    for contract_name, violation_type, expected_name in test_cases:
        violation = _make_violation(
            contract_name=contract_name,
            violation_type=violation_type,
        )
        event = create_violation_run_event(violation)
        assert event["job"]["name"] == expected_name


@pytest.mark.requirement("3D-FR-031")
def test_event_includes_contract_violation_facet() -> None:
    """Test run event includes contractViolation facet."""
    violation = _make_violation()

    event = create_violation_run_event(violation)

    assert "run" in event
    assert "facets" in event["run"]
    assert "contractViolation" in event["run"]["facets"]


@pytest.mark.requirement("3D-FR-031")
def test_build_contract_violation_facet_required_fields() -> None:
    """Test build_contract_violation_facet has all required fields."""
    violation = _make_violation(
        contract_name="test_contract",
        contract_version="2.0.0",
        violation_type=ViolationType.QUALITY,
        severity=ViolationSeverity.WARNING,
        message="Quality check failed",
    )

    facet = build_contract_violation_facet(violation)

    # Verify producer metadata
    assert facet["_producer"] == "https://github.com/obsidian-owl/floe"
    assert "_schemaURL" in facet

    # Verify violation fields
    assert facet["contractName"] == "test_contract"
    assert facet["contractVersion"] == "2.0.0"
    assert facet["violationType"] == "quality"
    assert facet["severity"] == "warning"
    assert facet["message"] == "Quality check failed"
    assert facet["checkDurationSeconds"] == pytest.approx(0.5)
    assert facet["affectedConsumers"] == []


@pytest.mark.requirement("3D-FR-031")
def test_facet_maps_optional_fields() -> None:
    """Test facet correctly maps optional violation fields."""
    violation = _make_violation(
        element="schema.customers.email",
        expected_value="email@example.com",
        actual_value="invalid-email",
        affected_consumers=["dashboard", "analytics"],
    )

    facet = build_contract_violation_facet(violation)

    assert facet["element"] == "schema.customers.email"
    assert facet["expectedValue"] == "email@example.com"
    assert facet["actualValue"] == "invalid-email"
    assert facet["affectedConsumers"] == ["dashboard", "analytics"]


@pytest.mark.requirement("3D-FR-031")
def test_facet_camelcase_field_mapping() -> None:
    """Test facet uses camelCase keys correctly."""
    violation = _make_violation(
        contract_name="test",
        contract_version="1.0.0",
        check_duration_seconds=1.23,
        affected_consumers=["consumer1"],
    )

    facet = build_contract_violation_facet(violation)

    # Verify all keys use camelCase
    expected_keys = {
        "_producer",
        "_schemaURL",
        "contractName",
        "contractVersion",
        "violationType",
        "severity",
        "message",
        "checkDurationSeconds",
        "affectedConsumers",
    }

    # May also have element, expectedValue, actualValue if provided
    for key in expected_keys:
        assert key in facet, f"Missing camelCase key: {key}"

    # Verify specific camelCase mappings
    assert "contractName" in facet
    assert "contractVersion" in facet
    assert "violationType" in facet
    assert "checkDurationSeconds" in facet
    assert "affectedConsumers" in facet
    assert "expectedValue" in facet or violation.expected_value is None
    assert "actualValue" in facet or violation.actual_value is None


@pytest.mark.requirement("3D-FR-030")
def test_event_time_is_iso8601_format() -> None:
    """Test eventTime is in ISO 8601 format."""
    violation = _make_violation()

    event = create_violation_run_event(violation)

    event_time = event["eventTime"]

    # Verify ISO 8601 format (YYYY-MM-DDTHH:MM:SS.ffffffZ)
    iso8601_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"
    assert re.match(
        iso8601_pattern, event_time
    ), f"Invalid ISO 8601 format: {event_time}"

    # Verify it can be parsed back to datetime
    parsed_time = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
    assert parsed_time.tzinfo is not None


@pytest.mark.requirement("3D-FR-030")
def test_producer_url_is_correct() -> None:
    """Test producer URL is correct."""
    violation = _make_violation()

    event = create_violation_run_event(violation)

    expected_producer = "https://github.com/obsidian-owl/floe"
    assert event["producer"] == expected_producer


@pytest.mark.requirement("3D-FR-035")
def test_inputs_outputs_are_empty_lists() -> None:
    """Test inputs and outputs are empty lists for violation events."""
    violation = _make_violation()

    event = create_violation_run_event(violation)

    assert event["inputs"] == []
    assert event["outputs"] == []


@pytest.mark.requirement("3D-FR-031")
def test_facet_schema_url_present() -> None:
    """Test facet includes _schemaURL field."""
    violation = _make_violation()

    facet = build_contract_violation_facet(violation)

    assert "_schemaURL" in facet
    assert isinstance(facet["_schemaURL"], str)
    assert len(facet["_schemaURL"]) > 0


@pytest.mark.requirement("3D-FR-031")
def test_facet_handles_null_optional_fields() -> None:
    """Test facet correctly handles None values for optional fields."""
    violation = _make_violation(
        element=None,
        expected_value=None,
        actual_value=None,
    )

    facet = build_contract_violation_facet(violation)

    # Optional fields should either be absent or null
    # Check that they don't cause errors
    assert "contractName" in facet
    assert "message" in facet

    # Element, expectedValue, actualValue should handle None gracefully
    # (implementation can choose to omit or include as null)


@pytest.mark.requirement("3D-FR-030")
def test_multiple_violations_produce_unique_run_ids() -> None:
    """Test each violation produces a unique run ID."""
    violation1 = _make_violation(message="First violation")
    violation2 = _make_violation(message="Second violation")

    event1 = create_violation_run_event(violation1)
    event2 = create_violation_run_event(violation2)

    run_id1 = event1["run"]["runId"]
    run_id2 = event2["run"]["runId"]

    assert run_id1 != run_id2
    assert UUID(run_id1)  # Valid UUID
    assert UUID(run_id2)  # Valid UUID


@pytest.mark.requirement("3D-FR-031")
def test_facet_includes_check_duration() -> None:
    """Test facet includes check duration in seconds."""
    violation = _make_violation(check_duration_seconds=2.5)

    facet = build_contract_violation_facet(violation)

    assert facet["checkDurationSeconds"] == pytest.approx(2.5)


@pytest.mark.requirement("3D-FR-031")
def test_facet_includes_affected_consumers() -> None:
    """Test facet includes list of affected consumers."""
    consumers = ["dashboard", "analytics", "reporting"]
    violation = _make_violation(affected_consumers=consumers)

    facet = build_contract_violation_facet(violation)

    assert facet["affectedConsumers"] == consumers


@pytest.mark.requirement("3D-FR-030")
def test_event_structure_with_all_optional_fields() -> None:
    """Test event creation with all optional fields populated."""
    violation = _make_violation(
        contract_name="full_contract",
        contract_version="3.0.0",
        violation_type=ViolationType.DEPRECATION,
        severity=ViolationSeverity.CRITICAL,
        message="Column deprecated",
        element="schema.users.old_field",
        expected_value="not_used",
        actual_value="still_in_use",
        affected_consumers=["service_a", "service_b"],
        check_duration_seconds=3.14,
        metadata={"reason": "API v1 sunset"},
    )

    event = create_violation_run_event(violation)

    # Verify basic structure
    assert event["eventType"] == "FAIL"
    assert event["job"]["name"] == "full_contract.deprecation"

    # Verify facet contains all fields
    facet = event["run"]["facets"]["contractViolation"]
    assert facet["contractName"] == "full_contract"
    assert facet["severity"] == "critical"
    assert facet["element"] == "schema.users.old_field"
    assert facet["affectedConsumers"] == ["service_a", "service_b"]
    assert facet["checkDurationSeconds"] == pytest.approx(3.14)

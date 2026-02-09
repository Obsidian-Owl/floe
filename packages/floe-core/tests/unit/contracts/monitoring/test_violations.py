"""Unit tests for contract violation and check result models.

Tests coverage:
- ViolationType enum: values, string serialization, isinstance
- ViolationSeverity enum: values, string serialization, isinstance
- ContractViolationEvent: construction, defaults, frozen, extra="forbid", JSON round-trip
- CheckStatus enum: values, string serialization
- CheckResult: construction, UUID generation, frozen, extra="forbid"

Tasks: T015 (Epic 3D)
Requirements: FR-005, FR-006
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from floe_core.contracts.monitoring.violations import (
    CheckResult,
    CheckStatus,
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)

# ================================
# ViolationType Enum Tests
# ================================


@pytest.mark.requirement("3D-FR-005")
def test_violation_type_all_values_accessible() -> None:
    """Test that all 5 ViolationType values are accessible."""
    assert ViolationType.FRESHNESS.value == "freshness"
    assert ViolationType.SCHEMA_DRIFT.value == "schema_drift"
    assert ViolationType.QUALITY.value == "quality"
    assert ViolationType.AVAILABILITY.value == "availability"
    assert ViolationType.DEPRECATION.value == "deprecation"


@pytest.mark.requirement("3D-FR-005")
def test_violation_type_string_values_are_lowercase() -> None:
    """Test that ViolationType string values are lowercase."""
    for violation_type in ViolationType:
        assert violation_type.value.islower()
        assert "_" in violation_type.value or violation_type.value.isalpha()


@pytest.mark.requirement("3D-FR-005")
def test_violation_type_is_str_enum() -> None:
    """Test that ViolationType instances are str."""
    for violation_type in ViolationType:
        assert isinstance(violation_type, str)
        assert isinstance(violation_type.value, str)


# ================================
# ViolationSeverity Enum Tests
# ================================


@pytest.mark.requirement("3D-FR-005")
def test_violation_severity_all_values_accessible() -> None:
    """Test that all 4 ViolationSeverity values are accessible."""
    assert ViolationSeverity.INFO.value == "info"
    assert ViolationSeverity.WARNING.value == "warning"
    assert ViolationSeverity.ERROR.value == "error"
    assert ViolationSeverity.CRITICAL.value == "critical"


@pytest.mark.requirement("3D-FR-005")
def test_violation_severity_string_values_are_lowercase() -> None:
    """Test that ViolationSeverity string values are lowercase."""
    for severity in ViolationSeverity:
        assert severity.value.islower()
        assert severity.value.isalpha()


@pytest.mark.requirement("3D-FR-005")
def test_violation_severity_is_str_enum() -> None:
    """Test that ViolationSeverity instances are str."""
    for severity in ViolationSeverity:
        assert isinstance(severity, str)
        assert isinstance(severity.value, str)


# ================================
# ContractViolationEvent Tests
# ================================


@pytest.mark.requirement("3D-FR-005")
def test_contract_violation_event_valid_construction_required_fields() -> None:
    """Test ContractViolationEvent construction with all required fields."""
    timestamp = datetime.now(tz=timezone.utc)
    event = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old, SLA threshold is 2 hours",
        timestamp=timestamp,
        check_duration_seconds=0.5,
    )

    assert event.contract_name == "orders_v1"
    assert event.contract_version == "1.0.0"
    assert event.violation_type == ViolationType.FRESHNESS
    assert event.severity == ViolationSeverity.ERROR
    assert event.message == "Data is 2.5 hours old, SLA threshold is 2 hours"
    assert event.timestamp == timestamp
    assert event.check_duration_seconds == pytest.approx(0.5)


@pytest.mark.requirement("3D-FR-005")
def test_contract_violation_event_valid_construction_with_optional_fields() -> None:
    """Test ContractViolationEvent construction with optional fields."""
    timestamp = datetime.now(tz=timezone.utc)
    event = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.SCHEMA_DRIFT,
        severity=ViolationSeverity.WARNING,
        message="Column 'status' type changed",
        element="status",
        expected_value="string",
        actual_value="integer",
        timestamp=timestamp,
        affected_consumers=["reporting", "analytics"],
        check_duration_seconds=0.3,
        metadata={"table": "orders", "environment": "prod"},
    )

    assert event.element == "status"
    assert event.expected_value == "string"
    assert event.actual_value == "integer"
    assert event.affected_consumers == ["reporting", "analytics"]
    assert event.metadata == {"table": "orders", "environment": "prod"}


@pytest.mark.requirement("3D-FR-005")
def test_contract_violation_event_default_values() -> None:
    """Test ContractViolationEvent default values for optional fields."""
    timestamp = datetime.now(tz=timezone.utc)
    event = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.QUALITY,
        severity=ViolationSeverity.INFO,
        message="Quality threshold approaching",
        timestamp=timestamp,
        check_duration_seconds=0.2,
    )

    assert event.element is None
    assert event.expected_value is None
    assert event.actual_value is None
    assert event.affected_consumers == []
    assert event.metadata == {}


@pytest.mark.requirement("3D-FR-005")
def test_contract_violation_event_frozen_immutability() -> None:
    """Test ContractViolationEvent is frozen and fields cannot be reassigned."""
    timestamp = datetime.now(tz=timezone.utc)
    event = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.AVAILABILITY,
        severity=ViolationSeverity.CRITICAL,
        message="Data source unreachable",
        timestamp=timestamp,
        check_duration_seconds=1.0,
    )

    with pytest.raises(ValidationError, match="frozen"):
        event.contract_name = "new_name"  # type: ignore[misc,unused-ignore]

    with pytest.raises(ValidationError, match="frozen"):
        event.severity = ViolationSeverity.INFO  # type: ignore[misc,unused-ignore]


@pytest.mark.requirement("3D-FR-005")
def test_contract_violation_event_extra_forbid() -> None:
    """Test ContractViolationEvent rejects unknown fields (extra='forbid')."""
    timestamp = datetime.now(tz=timezone.utc)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ContractViolationEvent(
            contract_name="orders_v1",
            contract_version="1.0.0",
            violation_type=ViolationType.FRESHNESS,
            severity=ViolationSeverity.ERROR,
            message="Test",
            timestamp=timestamp,
            check_duration_seconds=0.5,
            unknown_field="should_fail",  # type: ignore[call-arg]
        )


@pytest.mark.requirement("3D-FR-005")
def test_contract_violation_event_json_serialization_round_trip() -> None:
    """Test ContractViolationEvent JSON serialization and deserialization."""
    timestamp = datetime.now(tz=timezone.utc)
    original = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old",
        element="created_at",
        expected_value="2 hours",
        actual_value="2.5 hours",
        timestamp=timestamp,
        affected_consumers=["reporting"],
        check_duration_seconds=0.5,
        metadata={"environment": "prod"},
    )

    # Serialize to JSON
    json_str = original.model_dump_json()
    assert isinstance(json_str, str)

    # Deserialize from JSON
    deserialized = ContractViolationEvent.model_validate_json(json_str)

    # Verify all fields match
    assert deserialized.contract_name == original.contract_name
    assert deserialized.contract_version == original.contract_version
    assert deserialized.violation_type == original.violation_type
    assert deserialized.severity == original.severity
    assert deserialized.message == original.message
    assert deserialized.element == original.element
    assert deserialized.expected_value == original.expected_value
    assert deserialized.actual_value == original.actual_value
    assert deserialized.timestamp == original.timestamp
    assert deserialized.affected_consumers == original.affected_consumers
    assert deserialized.check_duration_seconds == pytest.approx(original.check_duration_seconds)
    assert deserialized.metadata == original.metadata


@pytest.mark.requirement("3D-FR-005")
def test_contract_violation_event_enum_fields_serialize_to_strings() -> None:
    """Test that enum fields serialize to string values in JSON."""
    timestamp = datetime.now(tz=timezone.utc)
    event = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.SCHEMA_DRIFT,
        severity=ViolationSeverity.WARNING,
        message="Schema changed",
        timestamp=timestamp,
        check_duration_seconds=0.3,
    )

    json_data = json.loads(event.model_dump_json())

    assert json_data["violation_type"] == "schema_drift"
    assert json_data["severity"] == "warning"


# ================================
# CheckStatus Enum Tests
# ================================


@pytest.mark.requirement("3D-FR-006")
def test_check_status_all_values_accessible() -> None:
    """Test that all 4 CheckStatus values are accessible."""
    assert CheckStatus.PASS.value == "pass"
    assert CheckStatus.FAIL.value == "fail"
    assert CheckStatus.ERROR.value == "error"
    assert CheckStatus.SKIPPED.value == "skipped"


@pytest.mark.requirement("3D-FR-006")
def test_check_status_string_values_are_lowercase() -> None:
    """Test that CheckStatus string values are lowercase."""
    for status in CheckStatus:
        assert status.value.islower()
        assert status.value.isalpha()


@pytest.mark.requirement("3D-FR-006")
def test_check_status_is_str_enum() -> None:
    """Test that CheckStatus instances are str."""
    for status in CheckStatus:
        assert isinstance(status, str)
        assert isinstance(status.value, str)


# ================================
# CheckResult Tests
# ================================


@pytest.mark.requirement("3D-FR-006")
def test_check_result_valid_construction_required_fields() -> None:
    """Test CheckResult construction with all required fields."""
    timestamp = datetime.now(tz=timezone.utc)
    result = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.FRESHNESS,
        status=CheckStatus.PASS,
        duration_seconds=0.3,
        timestamp=timestamp,
    )

    assert result.contract_name == "orders_v1"
    assert result.check_type == ViolationType.FRESHNESS
    assert result.status == CheckStatus.PASS
    assert result.duration_seconds == pytest.approx(0.3)
    assert result.timestamp == timestamp


@pytest.mark.requirement("3D-FR-006")
def test_check_result_id_field_auto_generates_uuid() -> None:
    """Test CheckResult id field auto-generates a UUID."""
    timestamp = datetime.now(tz=timezone.utc)
    result = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.QUALITY,
        status=CheckStatus.PASS,
        duration_seconds=0.2,
        timestamp=timestamp,
    )

    # Verify id is a valid UUID string
    assert result.id is not None
    assert isinstance(result.id, str)
    # Should be able to parse as UUID
    parsed_uuid = uuid.UUID(result.id)
    assert str(parsed_uuid) == result.id


@pytest.mark.requirement("3D-FR-006")
def test_check_result_two_instances_get_different_uuids() -> None:
    """Test that two different CheckResult instances get different UUIDs."""
    timestamp = datetime.now(tz=timezone.utc)
    result1 = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.FRESHNESS,
        status=CheckStatus.PASS,
        duration_seconds=0.3,
        timestamp=timestamp,
    )
    result2 = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.FRESHNESS,
        status=CheckStatus.PASS,
        duration_seconds=0.3,
        timestamp=timestamp,
    )

    assert result1.id != result2.id


@pytest.mark.requirement("3D-FR-006")
def test_check_result_optional_violation_field_defaults_to_none() -> None:
    """Test CheckResult violation field defaults to None."""
    timestamp = datetime.now(tz=timezone.utc)
    result = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.AVAILABILITY,
        status=CheckStatus.PASS,
        duration_seconds=0.1,
        timestamp=timestamp,
    )

    assert result.violation is None


@pytest.mark.requirement("3D-FR-006")
def test_check_result_with_violation_field() -> None:
    """Test CheckResult with a violation event."""
    timestamp = datetime.now(tz=timezone.utc)
    violation = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is stale",
        timestamp=timestamp,
        check_duration_seconds=0.5,
    )
    result = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.FRESHNESS,
        status=CheckStatus.FAIL,
        duration_seconds=0.5,
        timestamp=timestamp,
        violation=violation,
    )

    assert result.violation is not None
    assert result.violation.contract_name == "orders_v1"
    assert result.violation.violation_type == ViolationType.FRESHNESS
    assert result.violation.severity == ViolationSeverity.ERROR


@pytest.mark.requirement("3D-FR-006")
def test_check_result_frozen_immutability() -> None:
    """Test CheckResult is frozen and fields cannot be reassigned."""
    timestamp = datetime.now(tz=timezone.utc)
    result = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.SCHEMA_DRIFT,
        status=CheckStatus.PASS,
        duration_seconds=0.4,
        timestamp=timestamp,
    )

    with pytest.raises(ValidationError, match="frozen"):
        result.contract_name = "new_name"  # type: ignore[misc,unused-ignore]

    with pytest.raises(ValidationError, match="frozen"):
        result.status = CheckStatus.FAIL  # type: ignore[misc,unused-ignore]


@pytest.mark.requirement("3D-FR-006")
def test_check_result_extra_forbid() -> None:
    """Test CheckResult rejects unknown fields (extra='forbid')."""
    timestamp = datetime.now(tz=timezone.utc)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CheckResult(
            contract_name="orders_v1",
            check_type=ViolationType.QUALITY,
            status=CheckStatus.PASS,
            duration_seconds=0.2,
            timestamp=timestamp,
            unknown_field="should_fail",  # type: ignore[call-arg]
        )


@pytest.mark.requirement("3D-FR-006")
def test_check_result_details_field_defaults_to_empty_dict() -> None:
    """Test CheckResult details field defaults to empty dict."""
    timestamp = datetime.now(tz=timezone.utc)
    result = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.DEPRECATION,
        status=CheckStatus.SKIPPED,
        duration_seconds=0.0,
        timestamp=timestamp,
    )

    assert result.details == {}


@pytest.mark.requirement("3D-FR-006")
def test_check_result_with_details_field() -> None:
    """Test CheckResult with details populated."""
    timestamp = datetime.now(tz=timezone.utc)
    result = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.AVAILABILITY,
        status=CheckStatus.ERROR,
        duration_seconds=1.5,
        timestamp=timestamp,
        details={"error": "Connection timeout", "host": "db.example.com"},
    )

    assert result.details == {"error": "Connection timeout", "host": "db.example.com"}


# ================================
# Severity Assignment Logic Tests
# ================================


@pytest.mark.requirement("3D-FR-024")
def test_calculate_severity_info_level() -> None:
    """Test severity calculation returns INFO at 80% threshold."""
    from floe_core.contracts.monitoring.config import SeverityThresholds
    from floe_core.contracts.monitoring.violations import calculate_severity

    thresholds = SeverityThresholds()
    severity = calculate_severity(
        sla_consumption_pct=80.0, violation_count_in_window=0, thresholds=thresholds
    )

    assert severity == ViolationSeverity.INFO


@pytest.mark.requirement("3D-FR-024")
def test_calculate_severity_warning_level() -> None:
    """Test severity calculation returns WARNING at 90% threshold."""
    from floe_core.contracts.monitoring.config import SeverityThresholds
    from floe_core.contracts.monitoring.violations import calculate_severity

    thresholds = SeverityThresholds()
    severity = calculate_severity(
        sla_consumption_pct=90.0, violation_count_in_window=0, thresholds=thresholds
    )

    assert severity == ViolationSeverity.WARNING


@pytest.mark.requirement("3D-FR-024")
def test_calculate_severity_error_level() -> None:
    """Test severity calculation returns ERROR when SLA is breached (100%)."""
    from floe_core.contracts.monitoring.config import SeverityThresholds
    from floe_core.contracts.monitoring.violations import calculate_severity

    thresholds = SeverityThresholds()
    severity = calculate_severity(
        sla_consumption_pct=100.0, violation_count_in_window=0, thresholds=thresholds
    )

    assert severity == ViolationSeverity.ERROR


@pytest.mark.requirement("3D-FR-024")
def test_calculate_severity_critical_escalation() -> None:
    """Test severity escalates to CRITICAL when violation count exceeds threshold."""
    from floe_core.contracts.monitoring.config import SeverityThresholds
    from floe_core.contracts.monitoring.violations import calculate_severity

    thresholds = SeverityThresholds(critical_count=3)
    severity = calculate_severity(
        sla_consumption_pct=50.0, violation_count_in_window=3, thresholds=thresholds
    )

    assert severity == ViolationSeverity.CRITICAL


@pytest.mark.requirement("3D-FR-024")
def test_calculate_severity_critical_overrides_percentage() -> None:
    """Test CRITICAL severity takes priority over percentage-based severity."""
    from floe_core.contracts.monitoring.config import SeverityThresholds
    from floe_core.contracts.monitoring.violations import calculate_severity

    thresholds = SeverityThresholds(critical_count=3)
    # 100% would normally be ERROR, but critical count triggers CRITICAL
    severity = calculate_severity(
        sla_consumption_pct=100.0, violation_count_in_window=3, thresholds=thresholds
    )

    assert severity == ViolationSeverity.CRITICAL


@pytest.mark.requirement("3D-FR-024")
def test_calculate_severity_below_info_threshold() -> None:
    """Test severity returns INFO (minimum) when below all thresholds."""
    from floe_core.contracts.monitoring.config import SeverityThresholds
    from floe_core.contracts.monitoring.violations import calculate_severity

    thresholds = SeverityThresholds()
    severity = calculate_severity(
        sla_consumption_pct=50.0, violation_count_in_window=0, thresholds=thresholds
    )

    assert severity == ViolationSeverity.INFO


@pytest.mark.requirement("3D-FR-024")
def test_calculate_severity_exact_boundaries() -> None:
    """Test severity calculation at exact boundary values."""
    from floe_core.contracts.monitoring.config import SeverityThresholds
    from floe_core.contracts.monitoring.violations import calculate_severity

    thresholds = SeverityThresholds(info_pct=80.0, warning_pct=90.0)

    # Exactly at info_pct boundary
    severity_info = calculate_severity(
        sla_consumption_pct=80.0, violation_count_in_window=0, thresholds=thresholds
    )
    assert severity_info == ViolationSeverity.INFO

    # Exactly at warning_pct boundary
    severity_warning = calculate_severity(
        sla_consumption_pct=90.0, violation_count_in_window=0, thresholds=thresholds
    )
    assert severity_warning == ViolationSeverity.WARNING

    # Exactly at error boundary (100.0)
    severity_error = calculate_severity(
        sla_consumption_pct=100.0, violation_count_in_window=0, thresholds=thresholds
    )
    assert severity_error == ViolationSeverity.ERROR

    # Just below warning_pct (should still be INFO)
    severity_below_warning = calculate_severity(
        sla_consumption_pct=89.9, violation_count_in_window=0, thresholds=thresholds
    )
    assert severity_below_warning == ViolationSeverity.INFO

    # Just above warning_pct (should be WARNING)
    severity_above_warning = calculate_severity(
        sla_consumption_pct=90.1, violation_count_in_window=0, thresholds=thresholds
    )
    assert severity_above_warning == ViolationSeverity.WARNING


@pytest.mark.requirement("3D-FR-024")
def test_calculate_severity_custom_thresholds() -> None:
    """Test severity calculation with custom threshold configuration."""
    from floe_core.contracts.monitoring.config import SeverityThresholds
    from floe_core.contracts.monitoring.violations import calculate_severity

    # Custom thresholds: info at 70%, warning at 85%, critical at 5 violations
    thresholds = SeverityThresholds(info_pct=70.0, warning_pct=85.0, critical_count=5)

    # 70% should trigger INFO
    severity_info = calculate_severity(
        sla_consumption_pct=70.0, violation_count_in_window=0, thresholds=thresholds
    )
    assert severity_info == ViolationSeverity.INFO

    # 85% should trigger WARNING
    severity_warning = calculate_severity(
        sla_consumption_pct=85.0, violation_count_in_window=0, thresholds=thresholds
    )
    assert severity_warning == ViolationSeverity.WARNING

    # 5 violations should trigger CRITICAL
    severity_critical = calculate_severity(
        sla_consumption_pct=50.0, violation_count_in_window=5, thresholds=thresholds
    )
    assert severity_critical == ViolationSeverity.CRITICAL

    # 4 violations (below critical_count) at 85% should be WARNING
    severity_below_critical = calculate_severity(
        sla_consumption_pct=85.0, violation_count_in_window=4, thresholds=thresholds
    )
    assert severity_below_critical == ViolationSeverity.WARNING


@pytest.mark.requirement("3D-FR-024")
def test_calculate_severity_zero_consumption() -> None:
    """Test severity returns INFO for zero SLA consumption."""
    from floe_core.contracts.monitoring.config import SeverityThresholds
    from floe_core.contracts.monitoring.violations import calculate_severity

    thresholds = SeverityThresholds()
    severity = calculate_severity(
        sla_consumption_pct=0.0, violation_count_in_window=0, thresholds=thresholds
    )

    assert severity == ViolationSeverity.INFO

"""Contract test for ContractViolationEvent schema stability.

This test validates that the ContractViolationEvent schema remains stable across versions.
It is the SOLE contract between ContractMonitor and AlertChannelPlugins (Constitution IV —
Contract-Driven Integration). Changes to this schema are breaking changes that affect all
alert channel plugins.

Tasks: T019 (Epic 3D)
Requirements: FR-005, FR-006, Constitution IV
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from floe_core.contracts.monitoring.violations import (
    CheckResult,
    CheckStatus,
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)
from pydantic import ValidationError


@pytest.mark.requirement("3D-FR-005")
def test_violation_event_schema_snapshot() -> None:
    """Test ContractViolationEvent JSON schema snapshot for stability.

    Validates that the schema structure remains stable across versions.
    Required fields and types are the contract between monitor and alert channels.
    """
    schema = ContractViolationEvent.model_json_schema()

    # Verify all required fields
    required_fields = {
        "contract_name",
        "contract_version",
        "violation_type",
        "severity",
        "message",
        "timestamp",
        "check_duration_seconds",
    }
    assert set(schema["required"]) == required_fields

    # Verify optional fields exist in properties
    optional_fields = {
        "element",
        "expected_value",
        "actual_value",
        "affected_consumers",
        "metadata",
    }
    all_fields = required_fields | optional_fields
    assert set(schema["properties"].keys()) == all_fields

    # Verify field count (12 total)
    assert len(schema["properties"]) == 12


@pytest.mark.requirement("3D-FR-005")
def test_violation_event_field_type_stability() -> None:
    """Test ContractViolationEvent field types remain stable.

    Type changes are breaking changes for alert channel plugins.
    """
    schema = ContractViolationEvent.model_json_schema()
    properties = schema["properties"]

    # Verify string fields
    assert properties["contract_name"]["type"] == "string"
    assert properties["contract_version"]["type"] == "string"
    assert properties["message"]["type"] == "string"
    assert properties["element"]["anyOf"][0]["type"] == "string"
    assert properties["expected_value"]["anyOf"][0]["type"] == "string"
    assert properties["actual_value"]["anyOf"][0]["type"] == "string"

    # Verify enum fields reference ViolationType and ViolationSeverity
    assert "$ref" in properties["violation_type"]
    assert "ViolationType" in properties["violation_type"]["$ref"]
    assert "$ref" in properties["severity"]
    assert "ViolationSeverity" in properties["severity"]["$ref"]

    # Verify timestamp is string (datetime serialized to ISO format)
    assert properties["timestamp"]["type"] == "string"
    assert properties["timestamp"]["format"] == "date-time"

    # Verify numeric field
    assert properties["check_duration_seconds"]["type"] == "number"

    # Verify array field
    assert properties["affected_consumers"]["type"] == "array"
    assert properties["affected_consumers"]["items"]["type"] == "string"

    # Verify object field
    assert properties["metadata"]["type"] == "object"
    assert properties["metadata"]["additionalProperties"]["type"] == "string"


@pytest.mark.requirement("3D-FR-006")
def test_violation_event_serialization_round_trip() -> None:
    """Test ContractViolationEvent serialization round-trip preserves all data.

    Alert channels receive JSON-serialized events and must be able to deserialize
    them without data loss.
    """
    # Create event with all fields populated
    timestamp = datetime.now(tz=timezone.utc)
    original = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is 2.5 hours old, SLA threshold is 2 hours",
        element="order_timestamp",
        expected_value="<= 2 hours old",
        actual_value="2.5 hours old",
        timestamp=timestamp,
        affected_consumers=["downstream_pipeline", "reporting_dashboard"],
        check_duration_seconds=0.5,
        metadata={"sla_threshold": "2h", "actual_age": "2.5h"},
    )

    # Serialize to JSON string
    json_str = original.model_dump_json()

    # Deserialize back
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
    assert deserialized.check_duration_seconds == pytest.approx(
        original.check_duration_seconds
    )
    assert deserialized.metadata == original.metadata


@pytest.mark.requirement("3D-FR-006")
def test_violation_event_backward_compatibility_minimal() -> None:
    """Test backward compatibility with minimal JSON (required fields only).

    Old alert channels may only send required fields. New monitor must accept.
    """
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    minimal_json = {
        "contract_name": "orders_v1",
        "contract_version": "1.0.0",
        "violation_type": "freshness",
        "severity": "error",
        "message": "Data is stale",
        "timestamp": timestamp,
        "check_duration_seconds": 0.5,
    }

    # Deserialize minimal JSON
    event = ContractViolationEvent.model_validate(minimal_json)

    # Verify required fields present
    assert event.contract_name == "orders_v1"
    assert event.contract_version == "1.0.0"
    assert event.violation_type == ViolationType.FRESHNESS
    assert event.severity == ViolationSeverity.ERROR
    assert event.message == "Data is stale"
    assert event.check_duration_seconds == pytest.approx(0.5)

    # Verify optional fields have defaults
    assert event.element is None
    assert event.expected_value is None
    assert event.actual_value is None
    assert event.affected_consumers == []
    assert event.metadata == {}


@pytest.mark.requirement("3D-FR-006")
def test_violation_event_backward_compatibility_without_new_fields() -> None:
    """Test backward compatibility when new optional fields are missing.

    Old serialized data without new optional fields must still deserialize.
    """
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    old_json = {
        "contract_name": "orders_v1",
        "contract_version": "1.0.0",
        "violation_type": "schema_drift",
        "severity": "warning",
        "message": "Schema changed unexpectedly",
        "element": "customer_email",
        "timestamp": timestamp,
        "check_duration_seconds": 1.2,
        # Missing: affected_consumers, metadata (added in newer version)
    }

    # Deserialize old JSON
    event = ContractViolationEvent.model_validate(old_json)

    # Verify core fields preserved
    assert event.contract_name == "orders_v1"
    assert event.violation_type == ViolationType.SCHEMA_DRIFT
    assert event.element == "customer_email"

    # Verify missing fields have defaults
    assert event.affected_consumers == []
    assert event.metadata == {}


@pytest.mark.requirement("3D-FR-005")
def test_violation_event_immutability() -> None:
    """Test ContractViolationEvent is frozen (immutable).

    Events must not be modified after creation to prevent bugs in alert channels.
    """
    event = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.QUALITY,
        severity=ViolationSeverity.INFO,
        message="Data quality below threshold",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.3,
    )

    # Attempt to modify field
    with pytest.raises(ValidationError, match="Instance is frozen"):
        event.severity = ViolationSeverity.CRITICAL

    # Attempt to modify via setattr
    with pytest.raises(ValidationError, match="Instance is frozen"):
        event.message = "Modified message"


@pytest.mark.requirement("3D-FR-005")
def test_violation_event_extra_fields_forbidden() -> None:
    """Test ContractViolationEvent rejects extra fields.

    Prevents accidental schema pollution from alert channels.
    """
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    json_with_extra = {
        "contract_name": "orders_v1",
        "contract_version": "1.0.0",
        "violation_type": "freshness",
        "severity": "error",
        "message": "Data is stale",
        "timestamp": timestamp,
        "check_duration_seconds": 0.5,
        "extra_field": "not_allowed",  # Extra field
    }

    # Attempt to deserialize with extra field
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ContractViolationEvent.model_validate(json_with_extra)


@pytest.mark.requirement("3D-FR-005")
def test_violation_event_invalid_enum_values() -> None:
    """Test ContractViolationEvent rejects invalid enum values.

    Prevents alert channels from sending invalid violation types or severities.
    """
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    # Invalid violation_type
    json_invalid_type = {
        "contract_name": "orders_v1",
        "contract_version": "1.0.0",
        "violation_type": "invalid_type",  # Not a valid ViolationType
        "severity": "error",
        "message": "Data is stale",
        "timestamp": timestamp,
        "check_duration_seconds": 0.5,
    }
    with pytest.raises(ValidationError, match="violation_type"):
        ContractViolationEvent.model_validate(json_invalid_type)

    # Invalid severity
    json_invalid_severity = {
        "contract_name": "orders_v1",
        "contract_version": "1.0.0",
        "violation_type": "freshness",
        "severity": "invalid_severity",  # Not a valid ViolationSeverity
        "message": "Data is stale",
        "timestamp": timestamp,
        "check_duration_seconds": 0.5,
    }
    with pytest.raises(ValidationError, match="severity"):
        ContractViolationEvent.model_validate(json_invalid_severity)


@pytest.mark.requirement("3D-FR-006")
def test_check_result_schema_snapshot() -> None:
    """Test CheckResult JSON schema snapshot for stability.

    CheckResult is the internal monitoring record format.
    """
    schema = CheckResult.model_json_schema()

    # Verify required fields
    required_fields = {
        "contract_name",
        "check_type",
        "status",
        "duration_seconds",
        "timestamp",
    }
    assert set(schema["required"]) == required_fields

    # Verify optional fields exist
    optional_fields = {"id", "details", "violation"}
    all_fields = required_fields | optional_fields
    assert set(schema["properties"].keys()) == all_fields

    # Verify field count (8 total)
    assert len(schema["properties"]) == 8


@pytest.mark.requirement("3D-FR-006")
def test_check_result_field_type_stability() -> None:
    """Test CheckResult field types remain stable."""
    schema = CheckResult.model_json_schema()
    properties = schema["properties"]

    # Verify string fields
    assert properties["id"]["type"] == "string"
    assert properties["contract_name"]["type"] == "string"

    # Verify enum fields
    assert "$ref" in properties["check_type"]
    assert "ViolationType" in properties["check_type"]["$ref"]
    assert "$ref" in properties["status"]
    assert "CheckStatus" in properties["status"]["$ref"]

    # Verify numeric field
    assert properties["duration_seconds"]["type"] == "number"

    # Verify timestamp
    assert properties["timestamp"]["type"] == "string"
    assert properties["timestamp"]["format"] == "date-time"

    # Verify details is object
    assert properties["details"]["type"] == "object"

    # Verify violation can be null or ContractViolationEvent
    violation_schema = properties["violation"]
    assert "anyOf" in violation_schema
    types = [s.get("$ref", s.get("type")) for s in violation_schema["anyOf"]]
    assert "null" in types
    assert any("ContractViolationEvent" in str(t) for t in types)


@pytest.mark.requirement("3D-FR-006")
def test_check_result_serialization_round_trip() -> None:
    """Test CheckResult serialization round-trip preserves all data."""
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

    original = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.FRESHNESS,
        status=CheckStatus.FAIL,
        duration_seconds=0.5,
        timestamp=timestamp,
        details={"sla_threshold": "2h", "actual_age": "2.5h"},
        violation=violation,
    )

    # Serialize to JSON string
    json_str = original.model_dump_json()

    # Deserialize back
    deserialized = CheckResult.model_validate_json(json_str)

    # Verify all fields match
    assert deserialized.id == original.id
    assert deserialized.contract_name == original.contract_name
    assert deserialized.check_type == original.check_type
    assert deserialized.status == original.status
    assert deserialized.duration_seconds == pytest.approx(original.duration_seconds)
    assert deserialized.timestamp == original.timestamp
    assert deserialized.details == original.details
    assert deserialized.violation is not None
    assert deserialized.violation.contract_name == violation.contract_name


@pytest.mark.requirement("3D-FR-006")
def test_check_result_immutability() -> None:
    """Test CheckResult is frozen (immutable).

    Check results must not be modified after creation for audit trail integrity.
    """
    result = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.QUALITY,
        status=CheckStatus.PASS,
        duration_seconds=0.3,
        timestamp=datetime.now(tz=timezone.utc),
    )

    # Attempt to modify field
    with pytest.raises(ValidationError, match="Instance is frozen"):
        result.status = CheckStatus.FAIL


@pytest.mark.requirement("3D-FR-006")
def test_check_result_id_has_default() -> None:
    """Test CheckResult id field has UUID default.

    The id field is auto-generated if not provided.
    """
    result = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.SCHEMA_DRIFT,
        status=CheckStatus.PASS,
        duration_seconds=0.2,
        timestamp=datetime.now(tz=timezone.utc),
    )

    # Verify id was auto-generated
    assert result.id is not None
    assert len(result.id) == 36  # UUID format
    assert "-" in result.id


@pytest.mark.requirement("3D-FR-006")
def test_check_result_details_has_default() -> None:
    """Test CheckResult details field has empty dict default."""
    result = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.AVAILABILITY,
        status=CheckStatus.PASS,
        duration_seconds=0.1,
        timestamp=datetime.now(tz=timezone.utc),
    )

    # Verify details defaults to empty dict
    assert result.details == {}


@pytest.mark.requirement("3D-FR-006")
def test_check_result_violation_optional() -> None:
    """Test CheckResult violation field is optional (None for passing checks)."""
    result = CheckResult(
        contract_name="orders_v1",
        check_type=ViolationType.QUALITY,
        status=CheckStatus.PASS,
        duration_seconds=0.2,
        timestamp=datetime.now(tz=timezone.utc),
    )

    # Verify violation is None for passing check
    assert result.violation is None


@pytest.mark.requirement("3D-FR-005")
def test_violation_event_all_enum_values() -> None:
    """Test all ViolationType and ViolationSeverity enum values are valid.

    Alert channels must support all enum values defined in the contract.
    """
    timestamp = datetime.now(tz=timezone.utc)

    # Test all ViolationType values
    for violation_type in ViolationType:
        event = ContractViolationEvent(
            contract_name="test_contract",
            contract_version="1.0.0",
            violation_type=violation_type,
            severity=ViolationSeverity.INFO,
            message=f"Testing {violation_type.value}",
            timestamp=timestamp,
            check_duration_seconds=0.1,
        )
        assert event.violation_type == violation_type

    # Test all ViolationSeverity values
    for severity in ViolationSeverity:
        event = ContractViolationEvent(
            contract_name="test_contract",
            contract_version="1.0.0",
            violation_type=ViolationType.FRESHNESS,
            severity=severity,
            message=f"Testing {severity.value}",
            timestamp=timestamp,
            check_duration_seconds=0.1,
        )
        assert event.severity == severity


@pytest.mark.requirement("3D-FR-006")
def test_check_result_all_status_values() -> None:
    """Test all CheckStatus enum values are valid.

    Monitoring internals must support all check status values.
    """
    timestamp = datetime.now(tz=timezone.utc)

    # Test all CheckStatus values
    for status in CheckStatus:
        result = CheckResult(
            contract_name="test_contract",
            check_type=ViolationType.FRESHNESS,
            status=status,
            duration_seconds=0.1,
            timestamp=timestamp,
        )
        assert result.status == status


# Helper function for converting ContractViolationEvent to OpenLineage facet dict
def _event_to_openlineage_facet(event: ContractViolationEvent) -> dict:
    """Convert ContractViolationEvent to OpenLineage facet dict (camelCase).

    Maps snake_case Pydantic fields to camelCase JSON schema fields.

    Args:
        event: ContractViolationEvent to convert

    Returns:
        Dict with camelCase keys matching OpenLineage facet schema
    """
    return {
        "_producer": "floe",
        "_schemaURL": "https://floe.dev/schemas/contract-violation-facet.json",
        "contractName": event.contract_name,
        "contractVersion": event.contract_version,
        "violationType": event.violation_type.value,
        "severity": event.severity.value,
        "message": event.message,
        "element": event.element,
        "expectedValue": event.expected_value,
        "actualValue": event.actual_value,
        "timestamp": event.timestamp.isoformat(),
    }


@pytest.mark.requirement("3D-FR-047")
def test_openlineage_facet_required_fields() -> None:
    """Test OpenLineage facet has all required fields from JSON schema.

    Validates that emitted facet dict contains all required fields defined
    in the OpenLineage facet schema.
    """
    timestamp = datetime.now(tz=timezone.utc)
    event = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Data is stale",
        timestamp=timestamp,
        check_duration_seconds=0.5,
    )

    # Convert to facet dict
    facet = _event_to_openlineage_facet(event)

    # Verify all required fields present
    required_fields = {
        "_producer",
        "_schemaURL",
        "contractName",
        "contractVersion",
        "violationType",
        "severity",
        "message",
        "timestamp",
    }
    assert set(facet.keys()) >= required_fields

    # Verify required field values
    assert facet["_producer"] == "floe"
    assert (
        facet["_schemaURL"] == "https://floe.dev/schemas/contract-violation-facet.json"
    )
    assert facet["contractName"] == "orders_v1"
    assert facet["contractVersion"] == "1.0.0"
    assert facet["violationType"] == "freshness"
    assert facet["severity"] == "error"
    assert facet["message"] == "Data is stale"
    assert facet["timestamp"] == timestamp.isoformat()


@pytest.mark.requirement("3D-FR-047")
def test_openlineage_facet_violation_type_enum_values() -> None:
    """Test ViolationType enum values match facet schema violationType enum.

    Ensures Python enum values match JSON schema enum values exactly.
    """
    # Expected enum values from JSON schema
    schema_enum_values = {
        "freshness",
        "schema_drift",
        "quality",
        "availability",
        "deprecation",
    }

    # Actual enum values from ViolationType
    actual_enum_values = {vt.value for vt in ViolationType}

    # Must match exactly
    assert actual_enum_values == schema_enum_values


@pytest.mark.requirement("3D-FR-047")
def test_openlineage_facet_severity_enum_values() -> None:
    """Test ViolationSeverity enum values match facet schema severity enum.

    Ensures Python enum values match JSON schema enum values exactly.
    """
    # Expected enum values from JSON schema
    schema_enum_values = {"info", "warning", "error", "critical"}

    # Actual enum values from ViolationSeverity
    actual_enum_values = {vs.value for vs in ViolationSeverity}

    # Must match exactly
    assert actual_enum_values == schema_enum_values


@pytest.mark.requirement("3D-FR-047")
def test_openlineage_facet_validates_against_json_schema() -> None:
    """Test OpenLineage facet validates against JSON schema.

    Uses jsonschema.validate() to ensure emitted facets conform to the
    OpenLineage facet schema specification.
    """
    jsonschema = pytest.importorskip("jsonschema")

    # Load JSON schema
    schema_path = (
        Path(__file__).parent.parent.parent
        / "specs/3d-contract-monitoring/contracts/contract-violation-facet.json"
    )
    schema = json.loads(schema_path.read_text())

    # Create event with all fields
    timestamp = datetime.now(tz=timezone.utc)
    event = ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.2.3",
        violation_type=ViolationType.SCHEMA_DRIFT,
        severity=ViolationSeverity.WARNING,
        message="Schema changed unexpectedly",
        element="customer_email",
        expected_value="string",
        actual_value="null",
        timestamp=timestamp,
        check_duration_seconds=0.5,
    )

    # Convert to facet dict
    facet = _event_to_openlineage_facet(event)

    # Validate against schema (raises ValidationError if invalid)
    jsonschema.validate(instance=facet, schema=schema)


@pytest.mark.requirement("3D-FR-047")
def test_openlineage_facet_rejects_extra_fields() -> None:
    """Test JSON schema rejects facets with extra fields.

    Validates that additionalProperties: false is enforced by the schema.
    """
    jsonschema = pytest.importorskip("jsonschema")

    # Load JSON schema
    schema_path = (
        Path(__file__).parent.parent.parent
        / "specs/3d-contract-monitoring/contracts/contract-violation-facet.json"
    )
    schema = json.loads(schema_path.read_text())

    # Create valid facet with extra field
    timestamp = datetime.now(tz=timezone.utc)
    facet = {
        "_producer": "floe",
        "_schemaURL": "https://floe.dev/schemas/contract-violation-facet.json",
        "contractName": "orders_v1",
        "contractVersion": "1.0.0",
        "violationType": "freshness",
        "severity": "error",
        "message": "Data is stale",
        "timestamp": timestamp.isoformat(),
        "extraField": "not_allowed",  # Extra field
    }

    # Validation must fail
    with pytest.raises(
        jsonschema.ValidationError, match="Additional properties are not allowed"
    ):
        jsonschema.validate(instance=facet, schema=schema)

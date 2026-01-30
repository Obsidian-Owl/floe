"""Contract tests for PromotionRecord schema stability (T038a).

These tests ensure the PromotionRecord schema remains stable and
backward-compatible. Breaking changes should fail these tests.

The PromotionRecord schema is consumed by Epic 9B (Audit Trail) and
stored in OCI annotations for promotion audit trails.

Task: T038a
Requirements: 8C-FR-023, 8C-FR-027

See Also:
    - specs/8c-promotion-lifecycle/spec.md: Feature specification
    - specs/8c-promotion-lifecycle/data-model.md: Entity definitions
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from floe_core.schemas.promotion import (
    GateResult,
    GateStatus,
    PromotionGate,
    PromotionRecord,
)


# OCI annotation key prefix for promotion metadata
OCI_ANNOTATION_PREFIX = "dev.floe.promotion"
"""Standard prefix for OCI annotations containing promotion metadata."""

# Expected OCI annotation keys for PromotionRecord fields
OCI_ANNOTATION_KEYS = {
    "promotion_id": f"{OCI_ANNOTATION_PREFIX}.id",
    "source_environment": f"{OCI_ANNOTATION_PREFIX}.source",
    "target_environment": f"{OCI_ANNOTATION_PREFIX}.target",
    "operator": f"{OCI_ANNOTATION_PREFIX}.operator",
    "promoted_at": f"{OCI_ANNOTATION_PREFIX}.timestamp",
    "trace_id": f"{OCI_ANNOTATION_PREFIX}.trace-id",
    "dry_run": f"{OCI_ANNOTATION_PREFIX}.dry-run",
}
"""Mapping of PromotionRecord fields to OCI annotation keys."""


@pytest.fixture
def minimal_promotion_record() -> PromotionRecord:
    """Create a minimal valid PromotionRecord for testing."""
    return PromotionRecord(
        promotion_id=uuid4(),
        artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        artifact_tag="v1.0.0-dev",
        source_environment="dev",
        target_environment="staging",
        gate_results=[
            GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.PASSED,
                duration_ms=150,
            )
        ],
        signature_verified=True,
        operator="ci@github.com",
        promoted_at=datetime.now(timezone.utc),
        dry_run=False,
        trace_id="abc123def456",
        authorization_passed=True,
    )


class TestPromotionRecordSchemaContract:
    """Contract tests for PromotionRecord schema stability.

    These tests ensure the schema structure remains stable and that
    the contract between floe-core and Epic 9B consumers is maintained.
    """

    @pytest.mark.requirement("8C-FR-023")
    def test_required_fields_for_epic_9b_consumers(self) -> None:
        """Contract: PromotionRecord has all fields required by Epic 9B.

        Epic 9B (Audit Trail) depends on these fields for audit storage.
        Removing any of these fields is a breaking change.
        """
        schema = PromotionRecord.model_json_schema()
        required_fields = set(schema.get("required", []))

        # Core audit trail fields - must be present
        core_audit_fields = {
            "promotion_id",
            "artifact_digest",
            "artifact_tag",
            "source_environment",
            "target_environment",
            "gate_results",
            "signature_verified",
            "operator",
            "promoted_at",
            "dry_run",
            "trace_id",
            "authorization_passed",
        }

        for field in core_audit_fields:
            assert field in required_fields, f"Required field '{field}' missing from schema"

    @pytest.mark.requirement("8C-FR-023")
    def test_schema_properties_exist(self) -> None:
        """Contract: All expected properties exist in the JSON schema.

        This ensures downstream consumers can rely on field definitions.
        """
        schema = PromotionRecord.model_json_schema()
        properties = schema.get("properties", {})

        expected_properties = [
            "promotion_id",
            "artifact_digest",
            "artifact_tag",
            "source_environment",
            "target_environment",
            "gate_results",
            "signature_verified",
            "signature_status",
            "operator",
            "promoted_at",
            "dry_run",
            "trace_id",
            "authorization_passed",
            "authorized_via",
            "warnings",
        ]

        for prop in expected_properties:
            assert prop in properties, f"Property '{prop}' missing from schema"

    @pytest.mark.requirement("8C-FR-027")
    def test_json_schema_export(self) -> None:
        """Contract: PromotionRecord can export valid JSON Schema.

        This enables IDE autocomplete and external validation.
        """
        schema = PromotionRecord.model_json_schema()

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

        # Verify property types
        props = schema["properties"]
        assert "promotion_id" in props
        assert "artifact_digest" in props
        assert "gate_results" in props

    @pytest.mark.requirement("8C-FR-027")
    def test_serialization_round_trip(
        self, minimal_promotion_record: PromotionRecord
    ) -> None:
        """Contract: PromotionRecord serializes to JSON and back.

        This ensures the contract can be passed between processes
        and stored in OCI annotations or audit backends.
        """
        # Serialize to JSON
        json_str = minimal_promotion_record.model_dump_json()
        assert isinstance(json_str, str)

        # Parse back
        data = json.loads(json_str)
        restored = PromotionRecord.model_validate(data)

        # Verify all key fields are preserved
        assert restored.promotion_id == minimal_promotion_record.promotion_id
        assert restored.artifact_digest == minimal_promotion_record.artifact_digest
        assert restored.artifact_tag == minimal_promotion_record.artifact_tag
        assert restored.source_environment == minimal_promotion_record.source_environment
        assert restored.target_environment == minimal_promotion_record.target_environment
        assert restored.signature_verified == minimal_promotion_record.signature_verified
        assert restored.operator == minimal_promotion_record.operator
        assert restored.dry_run == minimal_promotion_record.dry_run
        assert restored.trace_id == minimal_promotion_record.trace_id
        assert restored.authorization_passed == minimal_promotion_record.authorization_passed

    @pytest.mark.requirement("8C-FR-023")
    def test_oci_annotation_key_patterns(self) -> None:
        """Contract: OCI annotation keys follow dev.floe.promotion.* pattern.

        PromotionRecord fields map to standardized OCI annotation keys
        for storage in container registry manifests.
        """
        # Verify all annotation keys use the correct prefix
        for field, key in OCI_ANNOTATION_KEYS.items():
            assert key.startswith(OCI_ANNOTATION_PREFIX), (
                f"Key '{key}' for field '{field}' must start with '{OCI_ANNOTATION_PREFIX}'"
            )

        # Verify key patterns are valid OCI annotation keys (lowercase, dots/hyphens)
        for key in OCI_ANNOTATION_KEYS.values():
            assert key == key.lower(), f"Key '{key}' must be lowercase"
            # OCI annotation keys should be DNS-like labels
            assert all(
                c.isalnum() or c in ".-" for c in key
            ), f"Key '{key}' contains invalid characters"

    @pytest.mark.requirement("8C-FR-027")
    def test_gate_results_list_contract(
        self, minimal_promotion_record: PromotionRecord
    ) -> None:
        """Contract: gate_results is a list of GateResult objects.

        Epic 9B consumers iterate over gate_results for audit display.
        """
        assert isinstance(minimal_promotion_record.gate_results, list)
        assert len(minimal_promotion_record.gate_results) >= 1

        for gate_result in minimal_promotion_record.gate_results:
            assert isinstance(gate_result, GateResult)
            assert hasattr(gate_result, "gate")
            assert hasattr(gate_result, "status")
            assert hasattr(gate_result, "duration_ms")

    @pytest.mark.requirement("8C-FR-023")
    def test_extra_properties_forbidden(self) -> None:
        """Contract: extra='forbid' prevents undocumented fields.

        This ensures the contract is strictly enforced and downstream
        packages don't accidentally rely on undocumented fields.
        """
        with pytest.raises(ValidationError) as exc_info:
            PromotionRecord(
                promotion_id=uuid4(),
                artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                artifact_tag="v1.0.0-dev",
                source_environment="dev",
                target_environment="staging",
                gate_results=[],
                signature_verified=True,
                operator="test@example.com",
                promoted_at=datetime.now(timezone.utc),
                dry_run=False,
                trace_id="abc123",
                authorization_passed=True,
                undocumented_field="should_fail",  # type: ignore[call-arg]
            )
        assert "undocumented_field" in str(exc_info.value)

    @pytest.mark.requirement("8C-FR-023")
    def test_immutability_contract(
        self, minimal_promotion_record: PromotionRecord
    ) -> None:
        """Contract: PromotionRecord is immutable (frozen=True).

        Once created, PromotionRecord should not be modified.
        This ensures audit trails are tamper-evident.
        """
        with pytest.raises(ValidationError):
            minimal_promotion_record.operator = "hacker@example.com"  # type: ignore[misc]

    @pytest.mark.requirement("8C-FR-027")
    def test_artifact_digest_format(self) -> None:
        """Contract: artifact_digest must be valid SHA256 format.

        Format: sha256:<64 hex characters>
        """
        # Valid digest
        valid_digest = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        record = PromotionRecord(
            promotion_id=uuid4(),
            artifact_digest=valid_digest,
            artifact_tag="v1.0.0",
            source_environment="dev",
            target_environment="staging",
            gate_results=[],
            signature_verified=True,
            operator="test@example.com",
            promoted_at=datetime.now(timezone.utc),
            dry_run=False,
            trace_id="abc123",
            authorization_passed=True,
        )
        assert record.artifact_digest == valid_digest

        # Invalid digests must be rejected
        invalid_digests = [
            "sha256:short",  # Too short
            "md5:a1b2c3d4",  # Wrong algorithm
            "notadigest",  # No prefix
            "sha256:UPPERCASE",  # Wrong case
        ]

        for invalid in invalid_digests:
            with pytest.raises(ValidationError):
                PromotionRecord(
                    promotion_id=uuid4(),
                    artifact_digest=invalid,
                    artifact_tag="v1.0.0",
                    source_environment="dev",
                    target_environment="staging",
                    gate_results=[],
                    signature_verified=True,
                    operator="test@example.com",
                    promoted_at=datetime.now(timezone.utc),
                    dry_run=False,
                    trace_id="abc123",
                    authorization_passed=True,
                )

    @pytest.mark.requirement("8C-FR-027")
    def test_warnings_field_default(self) -> None:
        """Contract: warnings field defaults to empty list.

        This allows partial failures to be recorded without breaking.
        """
        record = PromotionRecord(
            promotion_id=uuid4(),
            artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            artifact_tag="v1.0.0",
            source_environment="dev",
            target_environment="staging",
            gate_results=[],
            signature_verified=True,
            operator="test@example.com",
            promoted_at=datetime.now(timezone.utc),
            dry_run=False,
            trace_id="abc123",
            authorization_passed=True,
            # warnings not provided - should default to []
        )
        assert record.warnings == []

    @pytest.mark.requirement("8C-FR-027")
    def test_optional_fields_can_be_none(self) -> None:
        """Contract: Optional fields (signature_status, authorized_via) can be None.

        These fields are optional for backward compatibility.
        """
        record = PromotionRecord(
            promotion_id=uuid4(),
            artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            artifact_tag="v1.0.0",
            source_environment="dev",
            target_environment="staging",
            gate_results=[],
            signature_verified=True,
            operator="test@example.com",
            promoted_at=datetime.now(timezone.utc),
            dry_run=False,
            trace_id="abc123",
            authorization_passed=True,
            # Optional fields not provided
        )
        assert record.signature_status is None
        assert record.authorized_via is None


class TestGateResultContract:
    """Contract tests for GateResult schema used in PromotionRecord."""

    @pytest.mark.requirement("8C-FR-023")
    def test_gate_result_required_fields(self) -> None:
        """Contract: GateResult has gate, status, duration_ms as required."""
        schema = GateResult.model_json_schema()
        required_fields = set(schema.get("required", []))

        assert "gate" in required_fields
        assert "status" in required_fields
        assert "duration_ms" in required_fields

    @pytest.mark.requirement("8C-FR-027")
    def test_gate_result_serialization(self) -> None:
        """Contract: GateResult serializes to JSON and back."""
        result = GateResult(
            gate=PromotionGate.POLICY_COMPLIANCE,
            status=GateStatus.PASSED,
            duration_ms=150,
            details={"policy_version": "1.0.0"},
        )

        json_str = result.model_dump_json()
        data = json.loads(json_str)
        restored = GateResult.model_validate(data)

        assert restored.gate == result.gate
        assert restored.status == result.status
        assert restored.duration_ms == result.duration_ms
        assert restored.details == result.details

    @pytest.mark.requirement("8C-FR-023")
    def test_gate_result_immutable(self) -> None:
        """Contract: GateResult is immutable (frozen=True)."""
        result = GateResult(
            gate=PromotionGate.TESTS,
            status=GateStatus.PASSED,
            duration_ms=100,
        )
        with pytest.raises(ValidationError):
            result.status = GateStatus.FAILED  # type: ignore[misc]


class TestPromotionGateEnumContract:
    """Contract tests for PromotionGate enum values."""

    @pytest.mark.requirement("8C-FR-023")
    def test_promotion_gate_values(self) -> None:
        """Contract: PromotionGate has expected enum values.

        Adding new values is backward-compatible.
        Removing or renaming values is a breaking change.
        """
        expected_gates = {
            "policy_compliance",
            "tests",
            "security_scan",
            "cost_analysis",
            "performance_baseline",
        }

        actual_gates = {gate.value for gate in PromotionGate}

        # All expected gates must exist
        for gate in expected_gates:
            assert gate in actual_gates, f"Gate '{gate}' missing from PromotionGate enum"


class TestGateStatusEnumContract:
    """Contract tests for GateStatus enum values."""

    @pytest.mark.requirement("8C-FR-023")
    def test_gate_status_values(self) -> None:
        """Contract: GateStatus has expected enum values.

        Adding new values is backward-compatible.
        Removing or renaming values is a breaking change.
        """
        expected_statuses = {
            "passed",
            "failed",
            "skipped",
            "warning",
        }

        actual_statuses = {status.value for status in GateStatus}

        # All expected statuses must exist
        for status in expected_statuses:
            assert status in actual_statuses, f"Status '{status}' missing from GateStatus enum"

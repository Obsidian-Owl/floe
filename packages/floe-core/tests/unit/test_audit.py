"""Unit tests for audit logging event structure.

Task: T075
Requirements: FR-060 (Audit logging for secret access operations)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


class TestAuditOperation:
    """Tests for AuditOperation enum."""

    @pytest.mark.requirement("FR-060")
    def test_operation_values(self) -> None:
        """Test that all expected operations are defined."""
        from floe_core.schemas.audit import AuditOperation

        assert AuditOperation.GET.value == "get"
        assert AuditOperation.SET.value == "set"
        assert AuditOperation.LIST.value == "list"
        assert AuditOperation.DELETE.value == "delete"

    @pytest.mark.requirement("FR-060")
    def test_operation_is_string_enum(self) -> None:
        """Test that AuditOperation is a string enum."""
        from floe_core.schemas.audit import AuditOperation

        # Should work as string
        assert str(AuditOperation.GET) == "AuditOperation.GET"
        assert AuditOperation.GET.value == "get"


class TestAuditResult:
    """Tests for AuditResult enum."""

    @pytest.mark.requirement("FR-060")
    def test_result_values(self) -> None:
        """Test that all expected results are defined."""
        from floe_core.schemas.audit import AuditResult

        assert AuditResult.SUCCESS.value == "success"
        assert AuditResult.DENIED.value == "denied"
        assert AuditResult.ERROR.value == "error"


class TestAuditEventModel:
    """Tests for AuditEvent Pydantic model."""

    @pytest.mark.requirement("FR-060")
    def test_create_minimal_event(self) -> None:
        """Test creating an audit event with only required fields."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
        )

        assert event.requester_id == "test-user"
        assert event.secret_path == "/secrets/test"
        assert event.operation == AuditOperation.GET
        assert event.result == AuditResult.SUCCESS
        assert event.source_ip is None
        assert event.trace_id is None
        assert event.plugin_type is None
        assert event.namespace is None
        assert event.metadata is None

    @pytest.mark.requirement("FR-060")
    def test_create_full_event(self) -> None:
        """Test creating an audit event with all fields."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        timestamp = datetime.now(timezone.utc)
        event = AuditEvent(
            timestamp=timestamp,
            requester_id="dagster-worker",
            secret_path="floe/database/credentials",
            operation=AuditOperation.SET,
            result=AuditResult.SUCCESS,
            source_ip="10.0.0.1",
            trace_id="abc123def456",
            plugin_type="k8s",
            namespace="production",
            metadata={"key_count": 3},
        )

        assert event.timestamp == timestamp
        assert event.requester_id == "dagster-worker"
        assert event.secret_path == "floe/database/credentials"
        assert event.operation == AuditOperation.SET
        assert event.result == AuditResult.SUCCESS
        assert event.source_ip == "10.0.0.1"
        assert event.trace_id == "abc123def456"
        assert event.plugin_type == "k8s"
        assert event.namespace == "production"
        assert event.metadata == {"key_count": 3}

    @pytest.mark.requirement("FR-060")
    def test_event_is_frozen(self) -> None:
        """Test that audit events are immutable."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
        )

        with pytest.raises(TypeError):  # Frozen model raises TypeError on assignment
            event.requester_id = "other-user"  # type: ignore[misc]

    @pytest.mark.requirement("FR-060")
    def test_event_forbids_extra_fields(self) -> None:
        """Test that extra fields are rejected."""
        from pydantic import ValidationError

        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        with pytest.raises(ValidationError, match="extra"):
            AuditEvent(
                timestamp=datetime.now(timezone.utc),
                requester_id="test-user",
                secret_path="/secrets/test",
                operation=AuditOperation.GET,
                result=AuditResult.SUCCESS,
                unknown_field="value",  # type: ignore[call-arg]
            )


class TestAuditEventTimestamp:
    """Tests for AuditEvent timestamp handling."""

    @pytest.mark.requirement("FR-060")
    def test_timestamp_from_string(self) -> None:
        """Test creating event with ISO8601 string timestamp."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent(
            timestamp="2026-01-18T12:00:00Z",  # type: ignore[arg-type]
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
        )

        assert event.timestamp.year == 2026
        assert event.timestamp.month == 1
        assert event.timestamp.day == 18
        assert event.timestamp.tzinfo is not None

    @pytest.mark.requirement("FR-060")
    def test_timestamp_naive_becomes_utc(self) -> None:
        """Test that naive datetime becomes UTC."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        naive_dt = datetime(2026, 1, 18, 12, 0, 0)
        event = AuditEvent(
            timestamp=naive_dt,
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
        )

        assert event.timestamp.tzinfo == timezone.utc


class TestAuditEventValidation:
    """Tests for AuditEvent field validation."""

    @pytest.mark.requirement("FR-060")
    def test_requester_id_min_length(self) -> None:
        """Test requester_id minimum length validation."""
        from pydantic import ValidationError

        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        with pytest.raises(ValidationError, match="requester_id"):
            AuditEvent(
                timestamp=datetime.now(timezone.utc),
                requester_id="",
                secret_path="/secrets/test",
                operation=AuditOperation.GET,
                result=AuditResult.SUCCESS,
            )

    @pytest.mark.requirement("FR-060")
    def test_secret_path_min_length(self) -> None:
        """Test secret_path minimum length validation."""
        from pydantic import ValidationError

        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        with pytest.raises(ValidationError, match="secret_path"):
            AuditEvent(
                timestamp=datetime.now(timezone.utc),
                requester_id="test-user",
                secret_path="",
                operation=AuditOperation.GET,
                result=AuditResult.SUCCESS,
            )

    @pytest.mark.requirement("FR-060")
    def test_valid_ipv4_source_ip(self) -> None:
        """Test valid IPv4 source_ip."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
            source_ip="192.168.1.1",
        )

        assert event.source_ip == "192.168.1.1"

    @pytest.mark.requirement("FR-060")
    def test_valid_ipv6_source_ip(self) -> None:
        """Test valid IPv6 source_ip."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
            source_ip="::1",
        )

        assert event.source_ip == "::1"

    @pytest.mark.requirement("FR-060")
    def test_source_ip_unknown(self) -> None:
        """Test 'unknown' as valid source_ip."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
            source_ip="unknown",
        )

        assert event.source_ip == "unknown"

    @pytest.mark.requirement("FR-060")
    def test_invalid_source_ip(self) -> None:
        """Test invalid source_ip is rejected."""
        from pydantic import ValidationError

        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        with pytest.raises(ValidationError, match="Invalid IP"):
            AuditEvent(
                timestamp=datetime.now(timezone.utc),
                requester_id="test-user",
                secret_path="/secrets/test",
                operation=AuditOperation.GET,
                result=AuditResult.SUCCESS,
                source_ip="not-an-ip",
            )


class TestAuditEventToLogDict:
    """Tests for AuditEvent.to_log_dict() method."""

    @pytest.mark.requirement("FR-060")
    def test_to_log_dict_required_fields(self) -> None:
        """Test to_log_dict with only required fields."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent(
            timestamp=datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
        )

        log_dict = event.to_log_dict()

        assert log_dict["timestamp"] == "2026-01-18T12:00:00+00:00"
        assert log_dict["requester_id"] == "test-user"
        assert log_dict["secret_path"] == "/secrets/test"
        assert log_dict["operation"] == "get"
        assert log_dict["result"] == "success"
        assert "source_ip" not in log_dict
        assert "trace_id" not in log_dict

    @pytest.mark.requirement("FR-060")
    def test_to_log_dict_all_fields(self) -> None:
        """Test to_log_dict with all fields populated."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent(
            timestamp=datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
            source_ip="10.0.0.1",
            trace_id="trace123",
            plugin_type="k8s",
            namespace="production",
            metadata={"extra": "data"},
        )

        log_dict = event.to_log_dict()

        assert log_dict["source_ip"] == "10.0.0.1"
        assert log_dict["trace_id"] == "trace123"
        assert log_dict["plugin_type"] == "k8s"
        assert log_dict["namespace"] == "production"
        assert log_dict["metadata"] == {"extra": "data"}


class TestAuditEventFactoryMethods:
    """Tests for AuditEvent factory methods."""

    @pytest.mark.requirement("FR-060")
    def test_create_success(self) -> None:
        """Test create_success factory method."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent.create_success(
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            plugin_type="k8s",
        )

        assert event.result == AuditResult.SUCCESS
        assert event.requester_id == "test-user"
        assert event.secret_path == "/secrets/test"
        assert event.operation == AuditOperation.GET
        assert event.plugin_type == "k8s"
        assert event.timestamp.tzinfo is not None

    @pytest.mark.requirement("FR-060")
    def test_create_denied(self) -> None:
        """Test create_denied factory method."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent.create_denied(
            requester_id="unauthorized-user",
            secret_path="/secrets/admin",
            operation=AuditOperation.GET,
            reason="Insufficient permissions",
        )

        assert event.result == AuditResult.DENIED
        assert event.requester_id == "unauthorized-user"
        assert event.metadata is not None
        assert event.metadata["denial_reason"] == "Insufficient permissions"

    @pytest.mark.requirement("FR-060")
    def test_create_denied_without_reason(self) -> None:
        """Test create_denied without reason."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent.create_denied(
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
        )

        assert event.result == AuditResult.DENIED
        assert event.metadata is None

    @pytest.mark.requirement("FR-060")
    def test_create_error(self) -> None:
        """Test create_error factory method."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        event = AuditEvent.create_error(
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            error="Connection timeout",
            plugin_type="infisical",
        )

        assert event.result == AuditResult.ERROR
        assert event.requester_id == "test-user"
        assert event.plugin_type == "infisical"
        assert event.metadata is not None
        assert event.metadata["error"] == "Connection timeout"

    @pytest.mark.requirement("FR-060")
    def test_factory_methods_set_current_timestamp(self) -> None:
        """Test that factory methods use current UTC timestamp."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation

        before = datetime.now(timezone.utc)
        event = AuditEvent.create_success(
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
        )
        after = datetime.now(timezone.utc)

        assert before <= event.timestamp <= after


class TestAuditEventSerialization:
    """Tests for AuditEvent JSON serialization."""

    @pytest.mark.requirement("FR-060")
    def test_json_round_trip(self) -> None:
        """Test JSON serialization and deserialization."""
        from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

        original = AuditEvent(
            timestamp=datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
            source_ip="10.0.0.1",
            trace_id="trace123",
        )

        json_str = original.model_dump_json()
        restored = AuditEvent.model_validate_json(json_str)

        assert restored == original

    @pytest.mark.requirement("FR-060")
    def test_model_json_schema(self) -> None:
        """Test that JSON schema can be generated."""
        from floe_core.schemas.audit import AuditEvent

        schema = AuditEvent.model_json_schema()

        assert schema["type"] == "object"
        assert "timestamp" in schema["properties"]
        assert "requester_id" in schema["properties"]
        assert "secret_path" in schema["properties"]
        assert "operation" in schema["properties"]
        assert "result" in schema["properties"]
        assert "examples" in schema

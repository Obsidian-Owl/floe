"""Unit tests for RBAC audit logging functionality.

Tests the RBACGenerationAuditEvent model and log_rbac_event function
that track all RBAC manifest generation operations.

Task: T048
User Story: US4 - RBAC Manifest Generation
Requirements: FR-072
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError


class TestRBACGenerationAuditEventCreation:
    """Unit tests for RBACGenerationAuditEvent factory methods."""

    @pytest.mark.requirement("FR-072")
    def test_create_success_event(self) -> None:
        """Test creating a successful generation audit event."""
        from floe_core.rbac.audit import (
            RBACGenerationAuditEvent,
            RBACGenerationResult,
        )

        event = RBACGenerationAuditEvent.create_success(
            service_accounts=1,
            roles=2,
            role_bindings=2,
            namespaces=1,
            output_dir="target/rbac",
            files_generated=[Path("target/rbac/serviceaccounts.yaml")],
            secret_refs_count=3,
            warnings=["Some warning"],
        )

        assert event.result == RBACGenerationResult.SUCCESS
        assert event.service_accounts == 1
        assert event.roles == 2
        assert event.role_bindings == 2
        assert event.namespaces == 1
        assert event.output_dir == "target/rbac"
        assert len(event.files_generated) == 1
        assert event.secret_refs_count == 3
        assert event.warnings == ["Some warning"]
        assert event.errors == []
        assert event.timestamp is not None

    @pytest.mark.requirement("FR-072")
    def test_create_validation_error_event(self) -> None:
        """Test creating a validation error audit event."""
        from floe_core.rbac.audit import (
            RBACGenerationAuditEvent,
            RBACGenerationResult,
        )

        event = RBACGenerationAuditEvent.create_validation_error(
            output_dir="target/rbac",
            errors=["Missing apiVersion", "Invalid kind"],
            warnings=["Some warning"],
        )

        assert event.result == RBACGenerationResult.VALIDATION_ERROR
        assert event.errors == ["Missing apiVersion", "Invalid kind"]
        assert event.warnings == ["Some warning"]
        assert event.output_dir == "target/rbac"

    @pytest.mark.requirement("FR-072")
    def test_create_write_error_event(self) -> None:
        """Test creating a write error audit event."""
        from floe_core.rbac.audit import (
            RBACGenerationAuditEvent,
            RBACGenerationResult,
        )

        event = RBACGenerationAuditEvent.create_write_error(
            output_dir="target/rbac",
            errors=["Permission denied"],
        )

        assert event.result == RBACGenerationResult.WRITE_ERROR
        assert event.errors == ["Permission denied"]
        assert event.output_dir == "target/rbac"

    @pytest.mark.requirement("FR-072")
    def test_create_disabled_event(self) -> None:
        """Test creating a disabled RBAC audit event."""
        from floe_core.rbac.audit import (
            RBACGenerationAuditEvent,
            RBACGenerationResult,
        )

        event = RBACGenerationAuditEvent.create_disabled(
            output_dir="target/rbac",
        )

        assert event.result == RBACGenerationResult.DISABLED
        assert event.output_dir == "target/rbac"
        assert "RBAC generation disabled" in event.warnings[0]


class TestRBACGenerationAuditEventSerialization:
    """Unit tests for audit event serialization."""

    @pytest.mark.requirement("FR-072")
    def test_to_log_dict_includes_all_fields(self) -> None:
        """Test to_log_dict includes all relevant fields."""
        from floe_core.rbac.audit import RBACGenerationAuditEvent

        event = RBACGenerationAuditEvent.create_success(
            service_accounts=1,
            roles=2,
            role_bindings=2,
            namespaces=1,
            output_dir="target/rbac",
            files_generated=[Path("target/rbac/roles.yaml")],
            secret_refs_count=5,
            warnings=["Warning 1"],
            trace_id="trace-123",
        )

        log_dict = event.to_log_dict()

        assert "timestamp" in log_dict
        assert log_dict["result"] == "success"
        assert log_dict["service_accounts"] == 1
        assert log_dict["roles"] == 2
        assert log_dict["role_bindings"] == 2
        assert log_dict["namespaces"] == 1
        assert log_dict["output_dir"] == "target/rbac"
        assert log_dict["total_resources"] == 6
        assert log_dict["files_generated"] == ["target/rbac/roles.yaml"]
        assert log_dict["secret_refs_count"] == 5
        assert log_dict["warnings"] == ["Warning 1"]
        assert log_dict["trace_id"] == "trace-123"

    @pytest.mark.requirement("FR-072")
    def test_to_log_dict_omits_empty_fields(self) -> None:
        """Test to_log_dict omits empty optional fields."""
        from floe_core.rbac.audit import RBACGenerationAuditEvent

        event = RBACGenerationAuditEvent.create_success(
            output_dir="target/rbac",
        )

        log_dict = event.to_log_dict()

        assert "files_generated" not in log_dict
        assert "secret_refs_count" not in log_dict
        assert "errors" not in log_dict
        assert "warnings" not in log_dict
        assert "trace_id" not in log_dict

    @pytest.mark.requirement("FR-072")
    def test_to_log_dict_timestamp_is_iso_format(self) -> None:
        """Test timestamp is formatted as ISO8601."""
        from floe_core.rbac.audit import RBACGenerationAuditEvent

        event = RBACGenerationAuditEvent.create_success(output_dir="target/rbac")

        log_dict = event.to_log_dict()

        # Timestamp should be ISO8601 string
        assert isinstance(log_dict["timestamp"], str)
        # Should be parseable
        datetime.fromisoformat(log_dict["timestamp"])


class TestRBACGenerationAuditEventValidation:
    """Unit tests for audit event validation."""

    @pytest.mark.requirement("FR-072")
    def test_event_is_frozen(self) -> None:
        """Test audit events are immutable."""
        from floe_core.rbac.audit import RBACGenerationAuditEvent

        event = RBACGenerationAuditEvent.create_success(output_dir="target/rbac")

        with pytest.raises(ValidationError):
            event.service_accounts = 10  # type: ignore[misc]

    @pytest.mark.requirement("FR-072")
    def test_event_forbids_extra_fields(self) -> None:
        """Test audit events reject unknown fields."""
        from pydantic import ValidationError

        from floe_core.rbac.audit import (
            RBACGenerationAuditEvent,
            RBACGenerationResult,
        )

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            RBACGenerationAuditEvent(
                timestamp=datetime.now(timezone.utc),
                result=RBACGenerationResult.SUCCESS,
                output_dir="target/rbac",
                unknown_field="value",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("FR-072")
    def test_event_validates_counts_non_negative(self) -> None:
        """Test audit events reject negative counts."""
        from pydantic import ValidationError

        from floe_core.rbac.audit import (
            RBACGenerationAuditEvent,
            RBACGenerationResult,
        )

        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            RBACGenerationAuditEvent(
                timestamp=datetime.now(timezone.utc),
                result=RBACGenerationResult.SUCCESS,
                output_dir="target/rbac",
                service_accounts=-1,
            )


class TestLogRBACEvent:
    """Unit tests for log_rbac_event function."""

    @pytest.mark.requirement("FR-072")
    def test_log_success_uses_info_level(self) -> None:
        """Test successful events are logged at INFO level."""
        from floe_core.rbac.audit import (
            RBACGenerationAuditEvent,
            log_rbac_event,
        )

        event = RBACGenerationAuditEvent.create_success(output_dir="target/rbac")

        with patch("floe_core.rbac.audit.logger") as mock_logger:
            log_rbac_event(event)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "success" in call_args[0][1]

    @pytest.mark.requirement("FR-072")
    def test_log_disabled_uses_info_level(self) -> None:
        """Test disabled events are logged at INFO level."""
        from floe_core.rbac.audit import (
            RBACGenerationAuditEvent,
            log_rbac_event,
        )

        event = RBACGenerationAuditEvent.create_disabled(output_dir="target/rbac")

        with patch("floe_core.rbac.audit.logger") as mock_logger:
            log_rbac_event(event)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "disabled" in call_args[0][1]

    @pytest.mark.requirement("FR-072")
    def test_log_validation_error_uses_error_level(self) -> None:
        """Test validation errors are logged at ERROR level."""
        from floe_core.rbac.audit import (
            RBACGenerationAuditEvent,
            log_rbac_event,
        )

        event = RBACGenerationAuditEvent.create_validation_error(
            output_dir="target/rbac",
            errors=["Invalid manifest"],
        )

        with patch("floe_core.rbac.audit.logger") as mock_logger:
            log_rbac_event(event)

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "validation_error" in call_args[0][1]

    @pytest.mark.requirement("FR-072")
    def test_log_write_error_uses_error_level(self) -> None:
        """Test write errors are logged at ERROR level."""
        from floe_core.rbac.audit import (
            RBACGenerationAuditEvent,
            log_rbac_event,
        )

        event = RBACGenerationAuditEvent.create_write_error(
            output_dir="target/rbac",
            errors=["Permission denied"],
        )

        with patch("floe_core.rbac.audit.logger") as mock_logger:
            log_rbac_event(event)

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "write_error" in call_args[0][1]

    @pytest.mark.requirement("FR-072")
    def test_log_includes_audit_event_in_extra(self) -> None:
        """Test log call includes audit_event in extra dict."""
        from floe_core.rbac.audit import (
            RBACGenerationAuditEvent,
            log_rbac_event,
        )

        event = RBACGenerationAuditEvent.create_success(
            service_accounts=1,
            output_dir="target/rbac",
        )

        with patch("floe_core.rbac.audit.logger") as mock_logger:
            log_rbac_event(event)

            call_kwargs = mock_logger.info.call_args[1]
            assert "extra" in call_kwargs
            assert "audit_event" in call_kwargs["extra"]
            audit_data = call_kwargs["extra"]["audit_event"]
            assert audit_data["service_accounts"] == 1


class TestRBACGenerationResultEnum:
    """Unit tests for RBACGenerationResult enum."""

    @pytest.mark.requirement("FR-072")
    def test_result_enum_values(self) -> None:
        """Test all result enum values exist."""
        from floe_core.rbac.audit import RBACGenerationResult

        assert RBACGenerationResult.SUCCESS.value == "success"
        assert RBACGenerationResult.VALIDATION_ERROR.value == "validation_error"
        assert RBACGenerationResult.WRITE_ERROR.value == "write_error"
        assert RBACGenerationResult.DISABLED.value == "disabled"

    @pytest.mark.requirement("FR-072")
    def test_result_enum_is_string_enum(self) -> None:
        """Test result enum values are strings."""
        from floe_core.rbac.audit import RBACGenerationResult

        # Should be usable as strings
        result: str = RBACGenerationResult.SUCCESS
        assert result == "success"

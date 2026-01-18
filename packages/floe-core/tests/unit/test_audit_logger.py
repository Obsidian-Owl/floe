"""Unit tests for audit logger with OpenTelemetry trace context.

Tests for AuditLogger class and helper functions.

Task: Coverage improvement for 7a-identity-secrets
Requirements: FR-060, CR-006
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from floe_core.audit.logger import (
    AUDIT_LOGGER_NAME,
    AuditLogger,
    _get_trace_context,
    get_audit_logger,
    log_audit_event,
)
from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult


class TestGetTraceContext:
    """Tests for _get_trace_context() helper function."""

    @pytest.mark.requirement("CR-006")
    def test_returns_empty_when_otel_not_available(self) -> None:
        """Test that empty dict is returned when OTel not available."""
        with patch("floe_core.audit.logger._otel_available", False):
            result = _get_trace_context()
            assert result == {}

    @pytest.mark.requirement("CR-006")
    def test_returns_empty_when_trace_module_none(self) -> None:
        """Test that empty dict is returned when trace module is None."""
        with (
            patch("floe_core.audit.logger._otel_available", True),
            patch("floe_core.audit.logger._trace_module", None),
        ):
            result = _get_trace_context()
            assert result == {}

    @pytest.mark.requirement("CR-006")
    def test_returns_empty_when_no_current_span(self) -> None:
        """Test that empty dict is returned when no active span."""
        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = None

        with (
            patch("floe_core.audit.logger._otel_available", True),
            patch("floe_core.audit.logger._trace_module", mock_trace),
        ):
            result = _get_trace_context()
            assert result == {}

    @pytest.mark.requirement("CR-006")
    def test_returns_empty_for_invalid_trace_id(self) -> None:
        """Test that empty dict is returned for invalid trace ID."""
        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 0  # Invalid
        mock_ctx.span_id = 12345
        mock_span.get_span_context.return_value = mock_ctx

        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = mock_span

        with (
            patch("floe_core.audit.logger._otel_available", True),
            patch("floe_core.audit.logger._trace_module", mock_trace),
            patch("floe_core.audit.logger._invalid_trace_id", 0),
            patch("floe_core.audit.logger._invalid_span_id", 0),
        ):
            result = _get_trace_context()
            assert result == {}

    @pytest.mark.requirement("CR-006")
    def test_returns_trace_context_for_valid_span(self) -> None:
        """Test that trace context is returned for valid span."""
        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 0x12345678901234567890123456789012
        mock_ctx.span_id = 0x1234567890123456
        mock_span.get_span_context.return_value = mock_ctx

        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = mock_span

        with (
            patch("floe_core.audit.logger._otel_available", True),
            patch("floe_core.audit.logger._trace_module", mock_trace),
            patch("floe_core.audit.logger._invalid_trace_id", 0),
            patch("floe_core.audit.logger._invalid_span_id", 0),
        ):
            result = _get_trace_context()
            assert "trace_id" in result
            assert "span_id" in result
            assert len(result["trace_id"]) == 32  # 128 bits as hex
            assert len(result["span_id"]) == 16  # 64 bits as hex


class TestAuditLogger:
    """Tests for AuditLogger class."""

    @pytest.mark.requirement("FR-060")
    def test_init_with_default_name(self) -> None:
        """Test logger initialization with default name."""
        logger = AuditLogger()
        assert logger.logger is not None

    @pytest.mark.requirement("FR-060")
    def test_init_with_custom_name(self) -> None:
        """Test logger initialization with custom name."""
        logger = AuditLogger(logger_name="custom.audit")
        assert logger.logger is not None

    @pytest.mark.requirement("FR-060")
    def test_log_event_success(self) -> None:
        """Test logging a success event."""
        logger = AuditLogger()
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
        )

        with patch.object(logger._logger, "info") as mock_info:
            logger.log_event(event)
            mock_info.assert_called_once()
            call_kwargs = mock_info.call_args[1]
            assert call_kwargs["audit_event"] is True

    @pytest.mark.requirement("FR-060")
    def test_log_event_denied(self) -> None:
        """Test logging a denied event."""
        logger = AuditLogger()
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/admin",
            operation=AuditOperation.GET,
            result=AuditResult.DENIED,
        )

        with patch.object(logger._logger, "warning") as mock_warning:
            logger.log_event(event)
            mock_warning.assert_called_once()

    @pytest.mark.requirement("FR-060")
    def test_log_event_error(self) -> None:
        """Test logging an error event."""
        logger = AuditLogger()
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.ERROR,
        )

        with patch.object(logger._logger, "error") as mock_error:
            logger.log_event(event)
            mock_error.assert_called_once()

    @pytest.mark.requirement("FR-060")
    def test_log_event_adds_trace_context(self) -> None:
        """Test that trace context is added when available."""
        logger = AuditLogger()
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
            trace_id=None,  # Not set
        )

        with (
            patch.object(logger._logger, "info") as mock_info,
            patch(
                "floe_core.audit.logger._get_trace_context",
                return_value={"trace_id": "abc123", "span_id": "def456"},
            ),
        ):
            logger.log_event(event)
            call_kwargs = mock_info.call_args[1]
            assert call_kwargs["trace_id"] == "abc123"
            assert call_kwargs["span_id"] == "def456"

    @pytest.mark.requirement("FR-060")
    def test_log_event_preserves_existing_trace_id(self) -> None:
        """Test that existing trace_id is not overwritten."""
        logger = AuditLogger()
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
            trace_id="existing-trace-id",
        )

        with (
            patch.object(logger._logger, "info") as mock_info,
            patch(
                "floe_core.audit.logger._get_trace_context",
                return_value={"trace_id": "new-trace-id", "span_id": "span"},
            ),
        ):
            logger.log_event(event)
            call_kwargs = mock_info.call_args[1]
            # Should NOT be updated because trace_id was already set
            assert call_kwargs.get("trace_id") == "existing-trace-id"

    @pytest.mark.requirement("FR-060")
    def test_log_success(self) -> None:
        """Test log_success convenience method."""
        logger = AuditLogger()

        with patch.object(logger, "log_event") as mock_log:
            event = logger.log_success(
                requester_id="dagster-worker",
                secret_path="/secrets/db",
                operation=AuditOperation.GET,
                plugin_type="k8s",
                namespace="production",
            )

            assert event.result == AuditResult.SUCCESS
            assert event.plugin_type == "k8s"
            assert event.namespace == "production"
            mock_log.assert_called_once_with(event)

    @pytest.mark.requirement("FR-060")
    def test_log_success_with_metadata(self) -> None:
        """Test log_success with metadata parameter."""
        logger = AuditLogger()

        with patch.object(logger, "log_event"):
            event = logger.log_success(
                requester_id="user",
                secret_path="/secrets/test",
                operation=AuditOperation.GET,
                metadata={"key_count": 3},
            )

            assert event.metadata == {"key_count": 3}

    @pytest.mark.requirement("FR-060")
    def test_log_denied(self) -> None:
        """Test log_denied convenience method."""
        logger = AuditLogger()

        with patch.object(logger, "log_event") as mock_log:
            event = logger.log_denied(
                requester_id="unauthorized-user",
                secret_path="/secrets/admin",
                operation=AuditOperation.GET,
                reason="Insufficient permissions",
                plugin_type="infisical",
            )

            assert event.result == AuditResult.DENIED
            assert event.metadata is not None
            assert event.metadata["denial_reason"] == "Insufficient permissions"
            mock_log.assert_called_once_with(event)

    @pytest.mark.requirement("FR-060")
    def test_log_denied_without_reason(self) -> None:
        """Test log_denied without reason parameter."""
        logger = AuditLogger()

        with patch.object(logger, "log_event"):
            event = logger.log_denied(
                requester_id="user",
                secret_path="/secrets/test",
                operation=AuditOperation.GET,
            )

            assert event.result == AuditResult.DENIED
            assert event.metadata is None

    @pytest.mark.requirement("FR-060")
    def test_log_error(self) -> None:
        """Test log_error convenience method."""
        logger = AuditLogger()

        with patch.object(logger, "log_event") as mock_log:
            event = logger.log_error(
                requester_id="dagster-worker",
                secret_path="/secrets/db",
                operation=AuditOperation.GET,
                error="Connection timeout",
                plugin_type="infisical",
                namespace="production",
            )

            assert event.result == AuditResult.ERROR
            assert event.metadata is not None
            assert event.metadata["error"] == "Connection timeout"
            assert event.plugin_type == "infisical"
            mock_log.assert_called_once_with(event)


class TestAuditLoggerSingleton:
    """Tests for singleton audit logger functions."""

    @pytest.mark.requirement("FR-060")
    def test_get_audit_logger_returns_instance(self) -> None:
        """Test that get_audit_logger returns an AuditLogger instance."""
        # Reset singleton for test isolation
        with patch("floe_core.audit.logger._audit_logger", None):
            logger = get_audit_logger()
            assert isinstance(logger, AuditLogger)

    @pytest.mark.requirement("FR-060")
    def test_get_audit_logger_returns_same_instance(self) -> None:
        """Test that get_audit_logger returns the same instance."""
        with patch("floe_core.audit.logger._audit_logger", None):
            logger1 = get_audit_logger()
            logger2 = get_audit_logger()
            assert logger1 is logger2

    @pytest.mark.requirement("FR-060")
    def test_log_audit_event_uses_singleton(self) -> None:
        """Test that log_audit_event uses the singleton logger."""
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            requester_id="test-user",
            secret_path="/secrets/test",
            operation=AuditOperation.GET,
            result=AuditResult.SUCCESS,
        )

        with patch("floe_core.audit.logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            log_audit_event(event)

            mock_logger.log_event.assert_called_once_with(event)


class TestAuditLoggerConstants:
    """Tests for exported constants."""

    @pytest.mark.requirement("FR-060")
    def test_audit_logger_name_constant(self) -> None:
        """Test AUDIT_LOGGER_NAME constant is exported."""
        assert AUDIT_LOGGER_NAME == "floe.audit"

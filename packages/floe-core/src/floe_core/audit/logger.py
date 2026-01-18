"""Audit logger with OpenTelemetry trace context correlation.

This module provides structured logging for audit events with automatic
trace context injection from OpenTelemetry spans.

Task: T079
Requirements: FR-060 (Audit logging), CR-006 (Audit trace context)

Example:
    >>> from floe_core.audit.logger import AuditLogger, get_audit_logger
    >>> logger = get_audit_logger()
    >>> with create_span("secret_access"):
    ...     logger.log_success(
    ...         requester_id="dagster",
    ...         secret_path="/secrets/db",
    ...         operation=AuditOperation.GET,
    ...     )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult

if TYPE_CHECKING:
    pass

# Try to import OpenTelemetry for trace context
_otel_available = False
_invalid_trace_id = 0
_invalid_span_id = 0
_trace_module: Any = None

try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.trace import INVALID_SPAN_ID, INVALID_TRACE_ID

    _otel_available = True
    _trace_module = otel_trace
    _invalid_trace_id = INVALID_TRACE_ID
    _invalid_span_id = INVALID_SPAN_ID
except ImportError:
    pass

# Dedicated audit logger name for filtering
AUDIT_LOGGER_NAME = "floe.audit"


def _get_trace_context() -> dict[str, str]:
    """Get current OpenTelemetry trace context if available.

    Returns:
        Dict with trace_id and span_id if active span exists, empty dict otherwise.
    """
    if not _otel_available or _trace_module is None:
        return {}

    span = _trace_module.get_current_span()
    if span is None:
        return {}

    ctx = span.get_span_context()
    if ctx.trace_id == _invalid_trace_id or ctx.span_id == _invalid_span_id:
        return {}

    return {
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
    }


class AuditLogger:
    """Structured audit logger with OpenTelemetry trace context correlation.

    Provides methods for logging audit events with automatic trace context
    injection from active OpenTelemetry spans.

    The logger emits structured log entries containing:
    - All AuditEvent fields (timestamp, requester_id, secret_path, etc.)
    - OpenTelemetry trace_id and span_id when a span is active
    - Audit event type marker for log filtering

    Attributes:
        logger: The underlying structlog logger instance.

    Example:
        >>> logger = AuditLogger()
        >>> event = AuditEvent.create_success(
        ...     requester_id="user",
        ...     secret_path="/secrets/db",
        ...     operation=AuditOperation.GET,
        ... )
        >>> logger.log_event(event)

        >>> # Or use convenience methods
        >>> logger.log_success(
        ...     requester_id="user",
        ...     secret_path="/secrets/db",
        ...     operation=AuditOperation.GET,
        ... )
    """

    def __init__(self, logger_name: str = AUDIT_LOGGER_NAME) -> None:
        """Initialize audit logger.

        Args:
            logger_name: Name for the structlog logger. Defaults to "floe.audit".
        """
        self._logger = structlog.get_logger(logger_name)

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get the underlying structlog logger."""
        return self._logger

    def log_event(self, event: AuditEvent) -> None:
        """Log an audit event with trace context.

        Args:
            event: The AuditEvent to log.

        Example:
            >>> event = AuditEvent.create_success(...)
            >>> logger.log_event(event)
        """
        # Convert event to log dict
        log_data = event.to_log_dict()

        # Add trace context if available (and not already set)
        if event.trace_id is None:
            trace_ctx = _get_trace_context()
            if trace_ctx:
                log_data.update(trace_ctx)

        # Add audit marker for log filtering
        log_data["audit_event"] = True

        # Log at appropriate level based on result
        if event.result == AuditResult.SUCCESS:
            self._logger.info("audit_event", **log_data)
        elif event.result == AuditResult.DENIED:
            self._logger.warning("audit_event", **log_data)
        else:  # ERROR
            self._logger.error("audit_event", **log_data)

    def log_success(
        self,
        requester_id: str,
        secret_path: str,
        operation: AuditOperation,
        *,
        plugin_type: str | None = None,
        namespace: str | None = None,
        source_ip: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log a successful secret access.

        Args:
            requester_id: Identity of the requester.
            secret_path: Path of the accessed secret.
            operation: Type of operation performed.
            plugin_type: Optional plugin type.
            namespace: Optional namespace.
            source_ip: Optional source IP.
            metadata: Optional additional context.

        Returns:
            The created and logged AuditEvent.

        Example:
            >>> logger.log_success(
            ...     requester_id="dagster-worker",
            ...     secret_path="/secrets/db/password",
            ...     operation=AuditOperation.GET,
            ...     plugin_type="k8s",
            ... )
        """
        # Get trace context before creating event
        trace_ctx = _get_trace_context()
        trace_id = trace_ctx.get("trace_id")

        event = AuditEvent.create_success(
            requester_id=requester_id,
            secret_path=secret_path,
            operation=operation,
            plugin_type=plugin_type,
            namespace=namespace,
            source_ip=source_ip,
            trace_id=trace_id,
            metadata=metadata,
        )

        self.log_event(event)
        return event

    def log_denied(
        self,
        requester_id: str,
        secret_path: str,
        operation: AuditOperation,
        *,
        reason: str | None = None,
        plugin_type: str | None = None,
        namespace: str | None = None,
        source_ip: str | None = None,
    ) -> AuditEvent:
        """Log a denied secret access attempt.

        Args:
            requester_id: Identity of the requester.
            secret_path: Path of the accessed secret.
            operation: Type of operation attempted.
            reason: Optional reason for denial.
            plugin_type: Optional plugin type.
            namespace: Optional namespace.
            source_ip: Optional source IP.

        Returns:
            The created and logged AuditEvent.

        Example:
            >>> logger.log_denied(
            ...     requester_id="unauthorized-user",
            ...     secret_path="/secrets/admin",
            ...     operation=AuditOperation.GET,
            ...     reason="Insufficient permissions",
            ... )
        """
        trace_ctx = _get_trace_context()
        trace_id = trace_ctx.get("trace_id")

        event = AuditEvent.create_denied(
            requester_id=requester_id,
            secret_path=secret_path,
            operation=operation,
            reason=reason,
            plugin_type=plugin_type,
            namespace=namespace,
            source_ip=source_ip,
            trace_id=trace_id,
        )

        self.log_event(event)
        return event

    def log_error(
        self,
        requester_id: str,
        secret_path: str,
        operation: AuditOperation,
        error: str,
        *,
        plugin_type: str | None = None,
        namespace: str | None = None,
        source_ip: str | None = None,
    ) -> AuditEvent:
        """Log a failed secret access due to error.

        Args:
            requester_id: Identity of the requester.
            secret_path: Path of the accessed secret.
            operation: Type of operation attempted.
            error: Error message or description.
            plugin_type: Optional plugin type.
            namespace: Optional namespace.
            source_ip: Optional source IP.

        Returns:
            The created and logged AuditEvent.

        Example:
            >>> logger.log_error(
            ...     requester_id="dagster-worker",
            ...     secret_path="/secrets/db/password",
            ...     operation=AuditOperation.GET,
            ...     error="Connection timeout",
            ...     plugin_type="infisical",
            ... )
        """
        trace_ctx = _get_trace_context()
        trace_id = trace_ctx.get("trace_id")

        event = AuditEvent.create_error(
            requester_id=requester_id,
            secret_path=secret_path,
            operation=operation,
            error=error,
            plugin_type=plugin_type,
            namespace=namespace,
            source_ip=source_ip,
            trace_id=trace_id,
        )

        self.log_event(event)
        return event


# Module-level singleton for convenience
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the singleton audit logger instance.

    Returns:
        The shared AuditLogger instance.

    Example:
        >>> logger = get_audit_logger()
        >>> logger.log_success(...)
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def log_audit_event(event: AuditEvent) -> None:
    """Log an audit event using the singleton logger.

    Convenience function for logging audit events without managing logger instance.

    Args:
        event: The AuditEvent to log.

    Example:
        >>> from floe_core.audit import log_audit_event, AuditEvent
        >>> event = AuditEvent.create_success(...)
        >>> log_audit_event(event)
    """
    get_audit_logger().log_event(event)


__all__ = [
    "AUDIT_LOGGER_NAME",
    "AuditLogger",
    "get_audit_logger",
    "log_audit_event",
]

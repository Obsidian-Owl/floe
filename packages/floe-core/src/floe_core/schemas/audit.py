"""Audit logging models for tracking secret and identity operations.

This module provides Pydantic models for audit events that track all secret
access operations for compliance and security monitoring.

Task: T078
Requirements: FR-060 (Audit logging for secret access operations)

Example:
    >>> from floe_core.schemas.audit import AuditEvent, AuditOperation, AuditResult
    >>> from datetime import datetime, timezone
    >>> event = AuditEvent(
    ...     timestamp=datetime.now(timezone.utc),
    ...     requester_id="user@example.com",
    ...     secret_path="/secrets/database/password",
    ...     operation=AuditOperation.GET,
    ...     result=AuditResult.SUCCESS,
    ... )
    >>> event.to_log_dict()
    {'timestamp': '2026-01-18T...', 'requester_id': 'user@example.com', ...}
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuditOperation(str, Enum):
    """Types of auditable secret operations.

    These operations map to SecretsPlugin ABC methods and track
    all access patterns for compliance reporting.
    """

    GET = "get"
    """Retrieve a secret value."""

    SET = "set"
    """Create or update a secret."""

    LIST = "list"
    """List available secrets (paths only, not values)."""

    DELETE = "delete"
    """Remove a secret."""


class AuditResult(str, Enum):
    """Result of an audited operation.

    Used to track both successful and failed access attempts
    for security monitoring.
    """

    SUCCESS = "success"
    """Operation completed successfully."""

    DENIED = "denied"
    """Operation denied due to authorization failure."""

    ERROR = "error"
    """Operation failed due to system error."""


class AuditEvent(BaseModel):
    """Audit event for tracking secret access operations.

    This model captures all information required for compliance audit trails
    and security monitoring. Events are plugin-agnostic and work across
    all SecretsPlugin implementations (K8s, Infisical, etc.).

    Attributes:
        timestamp: ISO8601 timestamp of the operation.
        requester_id: Identity of the requester (user/service account).
        secret_path: Path or name of the accessed secret.
        operation: Type of operation performed.
        result: Outcome of the operation.
        source_ip: Optional source IP address of the request.
        trace_id: Optional OpenTelemetry trace ID for correlation.
        plugin_type: Type of secrets plugin that handled the request.
        namespace: Optional namespace for multi-tenant isolation.
        metadata: Optional additional context for the operation.

    Example:
        >>> event = AuditEvent(
        ...     timestamp=datetime.now(timezone.utc),
        ...     requester_id="dagster-worker",
        ...     secret_path="floe/database/credentials",
        ...     operation=AuditOperation.GET,
        ...     result=AuditResult.SUCCESS,
        ...     plugin_type="k8s",
        ...     namespace="production",
        ...     trace_id="abc123def456",
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "timestamp": "2026-01-18T12:00:00Z",
                    "requester_id": "dagster-worker",
                    "secret_path": "floe/database/password",
                    "operation": "get",
                    "result": "success",
                    "plugin_type": "k8s",
                    "namespace": "production",
                }
            ]
        },
    )

    timestamp: datetime = Field(
        ...,
        description="ISO8601 timestamp of when the operation occurred",
    )

    requester_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Identity of the requester (user ID, service account, or system identifier)",
    )

    secret_path: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="Path or name of the secret being accessed",
    )

    operation: AuditOperation = Field(
        ...,
        description="Type of secret operation performed",
    )

    result: AuditResult = Field(
        ...,
        description="Outcome of the operation (success, denied, error)",
    )

    source_ip: str | None = Field(
        default=None,
        description="Source IP address of the request, if available",
    )

    trace_id: str | None = Field(
        default=None,
        description="OpenTelemetry trace ID for distributed tracing correlation",
    )

    plugin_type: str | None = Field(
        default=None,
        description="Type of secrets plugin that handled the request (e.g., 'k8s', 'infisical')",
    )

    namespace: str | None = Field(
        default=None,
        description="Namespace or environment for multi-tenant isolation",
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional context about the operation (e.g., error details)",
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime | str) -> datetime:
        """Ensure timestamp is timezone-aware (UTC)."""
        if isinstance(v, str):
            # Parse ISO8601 string
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        # v is datetime at this point
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("source_ip")
    @classmethod
    def validate_source_ip(cls, v: str | None) -> str | None:
        """Validate source IP format if provided."""
        if v is None:
            return None
        # Basic validation - allow IPv4, IPv6, or "unknown"
        if v == "unknown":
            return v
        # Simple check for IP-like format (not full validation)
        if "." in v or ":" in v:
            return v
        msg = f"Invalid IP format: {v}"
        raise ValueError(msg)

    def to_log_dict(self) -> dict[str, Any]:
        """Convert to dictionary suitable for structured logging.

        Returns:
            Dictionary with all non-None fields, timestamp as ISO8601 string.

        Example:
            >>> event.to_log_dict()
            {'timestamp': '2026-01-18T12:00:00+00:00', 'requester_id': '...', ...}
        """
        result: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "requester_id": self.requester_id,
            "secret_path": self.secret_path,
            "operation": self.operation.value,
            "result": self.result.value,
        }

        # Add optional fields only if present
        if self.source_ip is not None:
            result["source_ip"] = self.source_ip
        if self.trace_id is not None:
            result["trace_id"] = self.trace_id
        if self.plugin_type is not None:
            result["plugin_type"] = self.plugin_type
        if self.namespace is not None:
            result["namespace"] = self.namespace
        if self.metadata is not None:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def create_success(
        cls,
        requester_id: str,
        secret_path: str,
        operation: AuditOperation,
        *,
        plugin_type: str | None = None,
        namespace: str | None = None,
        source_ip: str | None = None,
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Create a successful audit event with current timestamp.

        Args:
            requester_id: Identity of the requester.
            secret_path: Path of the accessed secret.
            operation: Type of operation performed.
            plugin_type: Optional plugin type.
            namespace: Optional namespace.
            source_ip: Optional source IP.
            trace_id: Optional trace ID.
            metadata: Optional additional context.

        Returns:
            AuditEvent with SUCCESS result and current UTC timestamp.
        """
        return cls(
            timestamp=datetime.now(timezone.utc),
            requester_id=requester_id,
            secret_path=secret_path,
            operation=operation,
            result=AuditResult.SUCCESS,
            plugin_type=plugin_type,
            namespace=namespace,
            source_ip=source_ip,
            trace_id=trace_id,
            metadata=metadata,
        )

    @classmethod
    def create_denied(
        cls,
        requester_id: str,
        secret_path: str,
        operation: AuditOperation,
        *,
        reason: str | None = None,
        plugin_type: str | None = None,
        namespace: str | None = None,
        source_ip: str | None = None,
        trace_id: str | None = None,
    ) -> AuditEvent:
        """Create a denied audit event with current timestamp.

        Args:
            requester_id: Identity of the requester.
            secret_path: Path of the accessed secret.
            operation: Type of operation attempted.
            reason: Optional reason for denial.
            plugin_type: Optional plugin type.
            namespace: Optional namespace.
            source_ip: Optional source IP.
            trace_id: Optional trace ID.

        Returns:
            AuditEvent with DENIED result and current UTC timestamp.
        """
        metadata = {"denial_reason": reason} if reason else None
        return cls(
            timestamp=datetime.now(timezone.utc),
            requester_id=requester_id,
            secret_path=secret_path,
            operation=operation,
            result=AuditResult.DENIED,
            plugin_type=plugin_type,
            namespace=namespace,
            source_ip=source_ip,
            trace_id=trace_id,
            metadata=metadata,
        )

    @classmethod
    def create_error(
        cls,
        requester_id: str,
        secret_path: str,
        operation: AuditOperation,
        error: str,
        *,
        plugin_type: str | None = None,
        namespace: str | None = None,
        source_ip: str | None = None,
        trace_id: str | None = None,
    ) -> AuditEvent:
        """Create an error audit event with current timestamp.

        Args:
            requester_id: Identity of the requester.
            secret_path: Path of the accessed secret.
            operation: Type of operation attempted.
            error: Error message or description.
            plugin_type: Optional plugin type.
            namespace: Optional namespace.
            source_ip: Optional source IP.
            trace_id: Optional trace ID.

        Returns:
            AuditEvent with ERROR result and current UTC timestamp.
        """
        return cls(
            timestamp=datetime.now(timezone.utc),
            requester_id=requester_id,
            secret_path=secret_path,
            operation=operation,
            result=AuditResult.ERROR,
            plugin_type=plugin_type,
            namespace=namespace,
            source_ip=source_ip,
            trace_id=trace_id,
            metadata={"error": error},
        )

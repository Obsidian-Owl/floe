"""Audit event models for NetworkPolicy operations.

This module provides Pydantic models for audit events that track NetworkPolicy
generation and application operations for compliance and security monitoring.

Task: T018
Epic: 7C - Network and Pod Security
Requirements: FR-071

Example:
    >>> from floe_core.network.audit import NetworkPolicyAuditEvent, PolicyOperation
    >>> from datetime import datetime, timezone
    >>> event = NetworkPolicyAuditEvent(
    ...     timestamp=datetime.now(timezone.utc),
    ...     operation=PolicyOperation.GENERATE,
    ...     policy_name="default-deny-egress",
    ...     namespace="floe-jobs",
    ...     policies_count=3,
    ... )
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PolicyOperation(str, Enum):
    """Types of auditable NetworkPolicy operations."""

    GENERATE = "generate"
    APPLY = "apply"
    DELETE = "delete"
    VALIDATE = "validate"
    DIFF = "diff"


class PolicyAuditResult(str, Enum):
    """Result of an audited policy operation."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"


class NetworkPolicyAuditEvent(BaseModel):
    """Audit event for tracking NetworkPolicy operations.

    This model captures all information required for compliance audit trails
    and security monitoring of NetworkPolicy generation and application.

    Attributes:
        timestamp: ISO8601 timestamp of the operation.
        operation: Type of policy operation performed.
        result: Outcome of the operation.
        policy_name: Name of the affected NetworkPolicy (if single policy).
        namespace: Target namespace for the policy.
        policies_count: Number of policies affected.
        trace_id: Optional OpenTelemetry trace ID for correlation.
        user_id: Optional identity of the user who triggered the operation.
        source: Source of the operation (e.g., "cli", "api", "ci").
        metadata: Optional additional context for the operation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime = Field(
        ...,
        description="ISO8601 timestamp of when the operation occurred",
    )

    operation: PolicyOperation = Field(
        ...,
        description="Type of NetworkPolicy operation performed",
    )

    result: PolicyAuditResult = Field(
        default=PolicyAuditResult.SUCCESS,
        description="Outcome of the operation",
    )

    policy_name: str | None = Field(
        default=None,
        description="Name of the affected NetworkPolicy",
    )

    namespace: str | None = Field(
        default=None,
        description="Target namespace for the policy",
    )

    policies_count: int = Field(
        default=0,
        ge=0,
        description="Number of policies affected by this operation",
    )

    trace_id: str | None = Field(
        default=None,
        description="OpenTelemetry trace ID for distributed tracing correlation",
    )

    user_id: str | None = Field(
        default=None,
        description="Identity of the user who triggered the operation",
    )

    source: str | None = Field(
        default=None,
        description="Source of the operation (cli, api, ci)",
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional context about the operation",
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime | str) -> datetime:
        """Ensure timestamp is timezone-aware (UTC)."""
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    def to_log_dict(self) -> dict[str, Any]:
        """Convert to dictionary suitable for structured logging.

        Returns:
            Dictionary with all non-None fields, timestamp as ISO8601 string.
        """
        result: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation.value,
            "result": self.result.value,
            "policies_count": self.policies_count,
        }

        if self.policy_name is not None:
            result["policy_name"] = self.policy_name
        if self.namespace is not None:
            result["namespace"] = self.namespace
        if self.trace_id is not None:
            result["trace_id"] = self.trace_id
        if self.user_id is not None:
            result["user_id"] = self.user_id
        if self.source is not None:
            result["source"] = self.source
        if self.metadata is not None:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def create_generate_event(
        cls,
        namespace: str,
        policies_count: int,
        *,
        result: PolicyAuditResult = PolicyAuditResult.SUCCESS,
        trace_id: str | None = None,
        user_id: str | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NetworkPolicyAuditEvent:
        """Create an audit event for policy generation.

        Args:
            namespace: Target namespace.
            policies_count: Number of policies generated.
            result: Outcome of generation.
            trace_id: Optional trace ID.
            user_id: Optional user identity.
            source: Optional operation source.
            metadata: Optional additional context.

        Returns:
            NetworkPolicyAuditEvent for generation operation.
        """
        return cls(
            timestamp=datetime.now(timezone.utc),
            operation=PolicyOperation.GENERATE,
            result=result,
            namespace=namespace,
            policies_count=policies_count,
            trace_id=trace_id,
            user_id=user_id,
            source=source,
            metadata=metadata,
        )

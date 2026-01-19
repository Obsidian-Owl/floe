"""Audit logging for RBAC manifest generation operations.

This module provides audit event models and logging utilities for tracking
all RBAC manifest generation operations to support compliance and debugging.

Task: T048
User Story: US4 - RBAC Manifest Generation
Requirements: FR-072

Example:
    >>> from floe_core.rbac.audit import RBACGenerationAuditEvent, log_rbac_event
    >>> event = RBACGenerationAuditEvent.create_success(
    ...     service_accounts=1,
    ...     roles=1,
    ...     role_bindings=1,
    ...     namespaces=1,
    ...     output_dir="target/rbac",
    ... )
    >>> log_rbac_event(event)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Module logger for RBAC audit events
logger = logging.getLogger("floe.rbac.audit")


class RBACGenerationResult(str, Enum):
    """Result of an RBAC generation operation.

    Used to track both successful and failed generation attempts
    for audit and debugging purposes.
    """

    SUCCESS = "success"
    """Generation completed successfully."""

    VALIDATION_ERROR = "validation_error"
    """Generation failed due to manifest validation errors."""

    WRITE_ERROR = "write_error"
    """Generation failed due to file write errors."""

    DISABLED = "disabled"
    """Generation skipped because RBAC is disabled in config."""


class RBACGenerationAuditEvent(BaseModel):
    """Audit event for tracking RBAC manifest generation operations.

    This model captures all information required for compliance audit trails
    and debugging of RBAC manifest generation. Events include counts of
    generated resources, output paths, and any errors encountered.

    Attributes:
        timestamp: ISO8601 timestamp of the operation.
        result: Outcome of the generation operation.
        service_accounts: Number of ServiceAccount manifests generated.
        roles: Number of Role manifests generated.
        role_bindings: Number of RoleBinding manifests generated.
        namespaces: Number of Namespace manifests generated.
        output_dir: Directory where manifests were written.
        files_generated: List of generated file paths.
        secret_refs_count: Number of secret references processed.
        errors: List of error messages if generation failed.
        warnings: List of warning messages from generation.
        trace_id: Optional OpenTelemetry trace ID for correlation.

    Contract:
        - MUST be created for every generate() call (FR-072)
        - MUST include resource counts and output paths
        - MUST include error details on failure
        - MUST be logged via structured logging

    Example:
        >>> event = RBACGenerationAuditEvent(
        ...     timestamp=datetime.now(timezone.utc),
        ...     result=RBACGenerationResult.SUCCESS,
        ...     service_accounts=1,
        ...     roles=1,
        ...     role_bindings=1,
        ...     namespaces=1,
        ...     output_dir="target/rbac",
        ...     files_generated=["serviceaccounts.yaml", "roles.yaml"],
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "timestamp": "2026-01-18T12:00:00Z",
                    "result": "success",
                    "service_accounts": 1,
                    "roles": 2,
                    "role_bindings": 2,
                    "namespaces": 1,
                    "output_dir": "target/rbac",
                    "files_generated": [
                        "serviceaccounts.yaml",
                        "roles.yaml",
                        "rolebindings.yaml",
                        "namespaces.yaml",
                    ],
                }
            ]
        },
    )

    timestamp: datetime = Field(
        ...,
        description="ISO8601 timestamp of when the generation occurred",
    )

    result: RBACGenerationResult = Field(
        ...,
        description="Outcome of the generation operation",
    )

    service_accounts: int = Field(
        default=0,
        ge=0,
        description="Number of ServiceAccount manifests generated",
    )

    roles: int = Field(
        default=0,
        ge=0,
        description="Number of Role manifests generated",
    )

    role_bindings: int = Field(
        default=0,
        ge=0,
        description="Number of RoleBinding manifests generated",
    )

    namespaces: int = Field(
        default=0,
        ge=0,
        description="Number of Namespace manifests generated",
    )

    output_dir: str = Field(
        ...,
        description="Directory where manifests were written",
    )

    files_generated: list[str] = Field(
        default_factory=list,
        description="List of generated file paths",
    )

    secret_refs_count: int = Field(
        default=0,
        ge=0,
        description="Number of secret references processed for aggregation",
    )

    errors: list[str] = Field(
        default_factory=list,
        description="List of error messages if generation failed",
    )

    warnings: list[str] = Field(
        default_factory=list,
        description="List of warning messages from generation",
    )

    trace_id: str | None = Field(
        default=None,
        description="OpenTelemetry trace ID for distributed tracing correlation",
    )

    def to_log_dict(self) -> dict[str, Any]:
        """Convert to dictionary suitable for structured logging.

        Returns:
            Dictionary with all fields formatted for logging.

        Example:
            >>> event.to_log_dict()
            {'timestamp': '2026-01-18T12:00:00+00:00', 'result': 'success', ...}
        """
        result_dict: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "result": self.result.value,
            "service_accounts": self.service_accounts,
            "roles": self.roles,
            "role_bindings": self.role_bindings,
            "namespaces": self.namespaces,
            "output_dir": self.output_dir,
            "total_resources": (
                self.service_accounts + self.roles + self.role_bindings + self.namespaces
            ),
        }

        if self.files_generated:
            result_dict["files_generated"] = self.files_generated
        if self.secret_refs_count > 0:
            result_dict["secret_refs_count"] = self.secret_refs_count
        if self.errors:
            result_dict["errors"] = self.errors
        if self.warnings:
            result_dict["warnings"] = self.warnings
        if self.trace_id:
            result_dict["trace_id"] = self.trace_id

        return result_dict

    @classmethod
    def create_success(
        cls,
        *,
        service_accounts: int = 0,
        roles: int = 0,
        role_bindings: int = 0,
        namespaces: int = 0,
        output_dir: str | Path,
        files_generated: list[Path] | None = None,
        secret_refs_count: int = 0,
        warnings: list[str] | None = None,
        trace_id: str | None = None,
    ) -> RBACGenerationAuditEvent:
        """Create a successful generation audit event.

        Args:
            service_accounts: Number of ServiceAccounts generated.
            roles: Number of Roles generated.
            role_bindings: Number of RoleBindings generated.
            namespaces: Number of Namespaces generated.
            output_dir: Directory where manifests were written.
            files_generated: List of generated file paths.
            secret_refs_count: Number of secret references processed.
            warnings: Optional list of warnings.
            trace_id: Optional trace ID.

        Returns:
            RBACGenerationAuditEvent with SUCCESS result.
        """
        return cls(
            timestamp=datetime.now(timezone.utc),
            result=RBACGenerationResult.SUCCESS,
            service_accounts=service_accounts,
            roles=roles,
            role_bindings=role_bindings,
            namespaces=namespaces,
            output_dir=str(output_dir),
            files_generated=[str(f) for f in (files_generated or [])],
            secret_refs_count=secret_refs_count,
            warnings=warnings or [],
            trace_id=trace_id,
        )

    @classmethod
    def create_validation_error(
        cls,
        *,
        output_dir: str | Path,
        errors: list[str],
        warnings: list[str] | None = None,
        trace_id: str | None = None,
    ) -> RBACGenerationAuditEvent:
        """Create a validation error audit event.

        Args:
            output_dir: Target output directory.
            errors: List of validation error messages.
            warnings: Optional list of warnings.
            trace_id: Optional trace ID.

        Returns:
            RBACGenerationAuditEvent with VALIDATION_ERROR result.
        """
        return cls(
            timestamp=datetime.now(timezone.utc),
            result=RBACGenerationResult.VALIDATION_ERROR,
            output_dir=str(output_dir),
            errors=errors,
            warnings=warnings or [],
            trace_id=trace_id,
        )

    @classmethod
    def create_write_error(
        cls,
        *,
        output_dir: str | Path,
        errors: list[str],
        warnings: list[str] | None = None,
        trace_id: str | None = None,
    ) -> RBACGenerationAuditEvent:
        """Create a write error audit event.

        Args:
            output_dir: Target output directory.
            errors: List of write error messages.
            warnings: Optional list of warnings.
            trace_id: Optional trace ID.

        Returns:
            RBACGenerationAuditEvent with WRITE_ERROR result.
        """
        return cls(
            timestamp=datetime.now(timezone.utc),
            result=RBACGenerationResult.WRITE_ERROR,
            output_dir=str(output_dir),
            errors=errors,
            warnings=warnings or [],
            trace_id=trace_id,
        )

    @classmethod
    def create_disabled(
        cls,
        *,
        output_dir: str | Path,
        warnings: list[str] | None = None,
        trace_id: str | None = None,
    ) -> RBACGenerationAuditEvent:
        """Create an audit event for disabled RBAC.

        Args:
            output_dir: Target output directory.
            warnings: Optional list of warnings.
            trace_id: Optional trace ID.

        Returns:
            RBACGenerationAuditEvent with DISABLED result.
        """
        return cls(
            timestamp=datetime.now(timezone.utc),
            result=RBACGenerationResult.DISABLED,
            output_dir=str(output_dir),
            warnings=warnings or ["RBAC generation disabled in security_config"],
            trace_id=trace_id,
        )


def log_rbac_event(event: RBACGenerationAuditEvent) -> None:
    """Log an RBAC generation audit event.

    Logs the event using structured logging with appropriate log level
    based on the result:
    - SUCCESS/DISABLED: INFO level
    - VALIDATION_ERROR/WRITE_ERROR: ERROR level

    Args:
        event: The audit event to log.

    Contract:
        - MUST log to "floe.rbac.audit" logger (FR-072)
        - MUST use appropriate log level based on result
        - MUST include all event fields in structured format

    Example:
        >>> event = RBACGenerationAuditEvent.create_success(output_dir="target/rbac")
        >>> log_rbac_event(event)
    """
    log_data = event.to_log_dict()

    if event.result in (RBACGenerationResult.SUCCESS, RBACGenerationResult.DISABLED):
        logger.info(
            "RBAC manifest generation %s",
            event.result.value,
            extra={"audit_event": log_data},
        )
    else:
        logger.error(
            "RBAC manifest generation %s",
            event.result.value,
            extra={"audit_event": log_data},
        )

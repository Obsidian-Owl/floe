"""Audit logging module for tracking secret and identity operations.

This module provides audit event creation, logging, and trace context correlation
for compliance and security monitoring.

Task: T079
Requirements: FR-060 (Audit logging), CR-006 (Audit trace context)

Example:
    >>> from floe_core.audit import AuditLogger, AuditEvent, AuditOperation
    >>> logger = AuditLogger()
    >>> event = AuditEvent.create_success(
    ...     requester_id="dagster-worker",
    ...     secret_path="/secrets/db/password",
    ...     operation=AuditOperation.GET,
    ...     plugin_type="k8s",
    ... )
    >>> logger.log_event(event)
"""

from __future__ import annotations

from floe_core.audit.decorator import audit_secret_access
from floe_core.audit.logger import (
    AuditLogger,
    get_audit_logger,
    log_audit_event,
)
from floe_core.schemas.audit import (
    AuditEvent,
    AuditOperation,
    AuditResult,
)

__all__ = [
    # Core models (from schemas)
    "AuditEvent",
    "AuditOperation",
    "AuditResult",
    # Audit decorator
    "audit_secret_access",
    # Audit logger
    "AuditLogger",
    "get_audit_logger",
    "log_audit_event",
]

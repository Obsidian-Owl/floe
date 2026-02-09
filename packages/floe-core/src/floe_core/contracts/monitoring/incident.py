"""Incident management for contract monitoring.

Maps violations to incidents with severity-to-priority mapping
and correlation of repeated violations to existing open incidents.

Tasks: T070, T071 (Epic 3D)
Requirements: FR-040, FR-041, FR-042
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)

logger = structlog.get_logger(__name__)


class IncidentPriority(str, Enum):
    """Priority levels for incidents based on violation severity.

    Mapped from ViolationSeverity:
    - P1 (CRITICAL): Immediate action required, high impact
    - P2 (HIGH): Urgent attention needed, significant impact
    - P3 (MEDIUM): Important but not urgent, moderate impact
    - P4 (LOW): Low priority, minimal impact
    """

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class IncidentStatus(str, Enum):
    """Status of an incident in its lifecycle.

    - OPEN: Incident created, not yet acknowledged
    - ACKNOWLEDGED: Team has acknowledged the incident
    - RESOLVED: Root cause fixed, monitoring for recurrence
    - CLOSED: Incident completely closed, no further action
    """

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    CLOSED = "closed"


# Severity to priority mapping (FR-040)
SEVERITY_TO_PRIORITY: dict[ViolationSeverity, IncidentPriority] = {
    ViolationSeverity.CRITICAL: IncidentPriority.P1,
    ViolationSeverity.ERROR: IncidentPriority.P2,
    ViolationSeverity.WARNING: IncidentPriority.P3,
    ViolationSeverity.INFO: IncidentPriority.P4,
}


class Incident(BaseModel):
    """Mutable Pydantic model tracking a contract monitoring incident.

    Incidents aggregate related violations for the same contract+violation_type.
    Unlike frozen models (ContractViolationEvent, CheckResult), incidents track
    mutable state as violations are correlated and status changes.

    Attributes:
        id: Unique identifier for this incident (UUID).
        title: Human-readable incident title.
        priority: Priority level mapped from violation severity.
        status: Current lifecycle status of the incident.
        contract_name: Name of the affected contract.
        violation_type: Type of violation this incident tracks.
        created_at: When the incident was first created.
        updated_at: Last time the incident was modified.
        violation_count: Total number of violations correlated to this incident.
        related_violations: List of violation details (timestamp, severity, message).

    Example:
        >>> incident = Incident(
        ...     title="Freshness violation on orders_v1",
        ...     priority=IncidentPriority.P2,
        ...     contract_name="orders_v1",
        ...     violation_type=ViolationType.FRESHNESS,
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    priority: IncidentPriority
    status: IncidentStatus = Field(default=IncidentStatus.OPEN)
    contract_name: str
    violation_type: ViolationType
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    violation_count: int = Field(default=1, ge=1)
    related_violations: list[dict[str, Any]] = Field(default_factory=list)


class IncidentManager:
    """Manages incident creation, correlation, and lifecycle.

    The IncidentManager handles:
    - Creating new incidents from violations (FR-040)
    - Correlating repeated violations to existing open incidents (FR-041)
    - Priority escalation when higher-severity violations arrive (FR-042)
    - Preventing correlation to resolved/closed incidents (FR-041)

    Correlation key: "{contract_name}:{violation_type}"
    """

    def __init__(self) -> None:
        """Initialize incident manager with empty state."""
        self._incidents: dict[str, Incident] = {}  # incident_id -> Incident
        self._open_correlation: dict[str, str] = {}  # correlation_key -> incident_id
        self._log = logger.bind(component="incident_manager")

    def _correlation_key(self, event: ContractViolationEvent) -> str:
        """Generate correlation key for violation event.

        Args:
            event: The contract violation event.

        Returns:
            Correlation key: "{contract_name}:{violation_type}"
        """
        return f"{event.contract_name}:{event.violation_type.value}"

    def _generate_title(self, event: ContractViolationEvent) -> str:
        """Generate human-readable incident title.

        Args:
            event: The contract violation event.

        Returns:
            Title in format: "{violation_type} violation on {contract_name}"
        """
        violation_name = event.violation_type.value.replace("_", " ").title()
        return f"{violation_name} violation on {event.contract_name}"

    def create_or_correlate(self, event: ContractViolationEvent) -> tuple[Incident, bool]:
        """Create new incident or correlate to existing open incident.

        Correlation logic (FR-041):
        1. Check if an OPEN incident exists for this correlation key
        2. If yes, add violation to existing incident (increment count, update timestamp)
        3. If no, create new incident

        Priority escalation (FR-042):
        - If new violation has higher priority than existing incident, escalate
        - Never downgrade priority

        Args:
            event: The contract violation event.

        Returns:
            Tuple of (incident, is_new) where is_new=True means new incident created.
        """
        corr_key = self._correlation_key(event)
        now = datetime.now(tz=timezone.utc)

        # Check for existing open incident
        if corr_key in self._open_correlation:
            incident_id = self._open_correlation[corr_key]
            incident = self._incidents[incident_id]

            # Correlate: add violation to existing incident
            incident.violation_count += 1
            incident.updated_at = now
            incident.related_violations.append(
                {
                    "timestamp": event.timestamp.isoformat(),
                    "severity": event.severity,
                    "message": event.message,
                }
            )

            # Priority escalation: upgrade if new violation has higher priority
            event_priority = SEVERITY_TO_PRIORITY[event.severity]
            priority_order = {
                IncidentPriority.P4: 0,
                IncidentPriority.P3: 1,
                IncidentPriority.P2: 2,
                IncidentPriority.P1: 3,
            }
            if priority_order[event_priority] > priority_order[incident.priority]:
                self._log.info(
                    "incident_priority_escalated",
                    incident_id=incident.id,
                    old_priority=incident.priority.value,
                    new_priority=event_priority.value,
                )
                incident.priority = event_priority

            self._log.debug(
                "violation_correlated",
                incident_id=incident.id,
                contract_name=event.contract_name,
                violation_type=event.violation_type.value,
                violation_count=incident.violation_count,
            )

            return (incident, False)

        # Create new incident
        priority = SEVERITY_TO_PRIORITY[event.severity]
        title = self._generate_title(event)

        incident = Incident(
            title=title,
            priority=priority,
            contract_name=event.contract_name,
            violation_type=event.violation_type,
            created_at=now,
            updated_at=now,
            violation_count=1,
            related_violations=[
                {
                    "timestamp": event.timestamp.isoformat(),
                    "severity": event.severity,
                    "message": event.message,
                }
            ],
        )

        self._incidents[incident.id] = incident
        self._open_correlation[corr_key] = incident.id

        self._log.info(
            "incident_created",
            incident_id=incident.id,
            contract_name=event.contract_name,
            violation_type=event.violation_type.value,
            priority=priority.value,
        )

        return (incident, True)

    def get_open_incidents(self) -> list[Incident]:
        """Get all incidents with OPEN status.

        Returns:
            List of open incidents.
        """
        return [
            incident
            for incident in self._incidents.values()
            if incident.status == IncidentStatus.OPEN
        ]

    def resolve_incident(self, incident_id: str) -> Incident | None:
        """Mark an incident as RESOLVED and remove from correlation tracking.

        Once resolved, future violations will create a new incident rather than
        correlating to the resolved one (FR-041).

        Args:
            incident_id: The incident ID to resolve.

        Returns:
            The resolved incident, or None if not found.
        """
        if incident_id not in self._incidents:
            return None

        incident = self._incidents[incident_id]
        incident.status = IncidentStatus.RESOLVED
        incident.updated_at = datetime.now(tz=timezone.utc)

        # Remove from open correlation tracking
        corr_key = f"{incident.contract_name}:{incident.violation_type.value}"
        if corr_key in self._open_correlation:
            del self._open_correlation[corr_key]

        self._log.info(
            "incident_resolved",
            incident_id=incident.id,
            contract_name=incident.contract_name,
        )

        return incident

    def get_incident(self, incident_id: str) -> Incident | None:
        """Get an incident by ID.

        Args:
            incident_id: The incident ID.

        Returns:
            The incident, or None if not found.
        """
        return self._incidents.get(incident_id)

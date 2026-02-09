"""Contract violation and check result models for monitoring.

This module defines the core data models for contract monitoring:
- ViolationType: Types of contract violations (freshness, schema drift, etc.)
- ViolationSeverity: Severity levels for violations (INFO through CRITICAL)
- ContractViolationEvent: Frozen Pydantic model — SOLE interface between monitor and alert channels
- CheckStatus: Outcome of a monitoring check (pass/fail/error/skipped)
- CheckResult: Frozen Pydantic model recording a single check execution

Tasks: T005, T006, T007 (Epic 3D)
Requirements: FR-023, FR-024, FR-025
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from floe_core.contracts.monitoring.config import SeverityThresholds


class ViolationType(str, Enum):
    """Types of contract violations detected by the monitoring system.

    Each type corresponds to a specific monitoring check:
    - FRESHNESS: Data exceeds SLA freshness threshold (FR-007)
    - SCHEMA_DRIFT: Actual schema differs from contract definition (FR-011)
    - QUALITY: Data quality drops below threshold (FR-015)
    - AVAILABILITY: Data source unreachable or degraded (FR-019)
    - DEPRECATION: Contract is deprecated or approaching end-of-life
    """

    FRESHNESS = "freshness"
    SCHEMA_DRIFT = "schema_drift"
    QUALITY = "quality"
    AVAILABILITY = "availability"
    DEPRECATION = "deprecation"


class ViolationSeverity(str, Enum):
    """Severity levels for contract violations.

    Severity is assigned based on configurable SLA consumption thresholds (FR-024):
    - INFO: 80% of SLA threshold consumed (early warning)
    - WARNING: 90% of SLA threshold consumed (approaching breach)
    - ERROR: SLA threshold breached (active violation)
    - CRITICAL: >3 violations of same type/contract within 24h (escalation)
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ContractViolationEvent(BaseModel):
    """Frozen Pydantic model representing a detected contract violation.

    This is the SOLE interface between the ContractMonitor and AlertChannelPlugins
    (Constitution IV — Contract-Driven Integration). Alert channels receive only
    this model and must not depend on monitoring internals.

    FR-025: MUST NOT include PII or sensitive data in messages or payloads.

    Attributes:
        contract_name: Name of the violated contract.
        contract_version: Semantic version of the contract.
        violation_type: Type of violation detected.
        severity: Severity level of the violation.
        message: Human-readable description (no PII).
        element: Optional column/field name involved.
        expected_value: Optional expected value from contract.
        actual_value: Optional actual value observed.
        timestamp: When the violation was detected.
        affected_consumers: List of downstream consumer names.
        check_duration_seconds: How long the check took.
        metadata: Additional key-value metadata.

    Example:
        >>> event = ContractViolationEvent(
        ...     contract_name="orders_v1",
        ...     contract_version="1.0.0",
        ...     violation_type=ViolationType.FRESHNESS,
        ...     severity=ViolationSeverity.ERROR,
        ...     message="Data is 2.5 hours old, SLA threshold is 2 hours",
        ...     timestamp=datetime.now(tz=timezone.utc),
        ...     check_duration_seconds=0.5,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_name: str
    contract_version: str
    violation_type: ViolationType
    severity: ViolationSeverity
    message: str
    element: str | None = None
    expected_value: str | None = None
    actual_value: str | None = None
    timestamp: datetime
    affected_consumers: list[str] = Field(default_factory=list)
    check_duration_seconds: float
    metadata: dict[str, str] = Field(default_factory=dict)


class CheckStatus(str, Enum):
    """Outcome status of a monitoring check execution.

    Attributes:
        PASS: Check completed successfully, no violation detected.
        FAIL: Check completed, violation detected.
        ERROR: Check could not complete due to an error.
        SKIPPED: Check was skipped (e.g., plugin unavailable).
    """

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"


class CheckResult(BaseModel):
    """Frozen Pydantic model recording the outcome of a single monitoring check.

    Each check execution produces exactly one CheckResult. If the check
    detects a violation, the violation field contains the ContractViolationEvent.

    Attributes:
        id: Unique identifier for this check result (UUID).
        contract_name: Name of the contract checked.
        check_type: Type of check performed.
        status: Outcome of the check.
        duration_seconds: How long the check took.
        timestamp: When the check was executed.
        details: Additional check-specific details.
        violation: Violation event if check failed, None otherwise.

    Example:
        >>> result = CheckResult(
        ...     contract_name="orders_v1",
        ...     check_type=ViolationType.FRESHNESS,
        ...     status=CheckStatus.PASS,
        ...     duration_seconds=0.3,
        ...     timestamp=datetime.now(tz=timezone.utc),
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_name: str
    check_type: ViolationType
    status: CheckStatus
    duration_seconds: float
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)
    violation: ContractViolationEvent | None = None


def calculate_severity(
    *,
    sla_consumption_pct: float,
    violation_count_in_window: int,
    thresholds: SeverityThresholds,
) -> ViolationSeverity:
    """Calculate violation severity from SLA consumption and violation history.

    Severity assignment rules (FR-024):
    1. CRITICAL: violation_count_in_window >= thresholds.critical_count
       (takes priority regardless of percentage)
    2. ERROR: sla_consumption_pct >= 100.0 (SLA breached)
    3. WARNING: sla_consumption_pct >= thresholds.warning_pct
    4. INFO: minimum severity for any consumption

    Args:
        sla_consumption_pct: Percentage of SLA threshold consumed (0-100+).
        violation_count_in_window: Number of violations of same type/contract
            within the critical_window_hours.
        thresholds: Configurable severity thresholds.

    Returns:
        The calculated ViolationSeverity level.
    """
    # Critical count check takes highest priority
    if violation_count_in_window >= thresholds.critical_count:
        return ViolationSeverity.CRITICAL

    # Percentage-based checks in descending order
    if sla_consumption_pct >= 100.0:
        return ViolationSeverity.ERROR

    if sla_consumption_pct >= thresholds.warning_pct:
        return ViolationSeverity.WARNING

    if sla_consumption_pct >= thresholds.info_pct:
        return ViolationSeverity.INFO

    # Below all thresholds — INFO is minimum severity
    return ViolationSeverity.INFO

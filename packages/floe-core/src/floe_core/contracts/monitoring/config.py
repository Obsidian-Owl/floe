"""Monitoring configuration models.

This module defines the configuration hierarchy for contract monitoring:
- CheckIntervalConfig: Check scheduling intervals per check type
- SeverityThresholds: Thresholds for severity level assignment
- AlertChannelRoutingRule: Routing rules mapping severity to alert channels
- AlertConfig: Alert routing, deduplication, and rate limiting settings
- MonitoringConfig: Top-level monitoring configuration from platform manifest
- RegisteredContract: Runtime state for a contract being monitored

Tasks: T008, T010 (Epic 3D)
Requirements: FR-003, FR-004, FR-029, FR-030, FR-044, FR-045
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from floe_core.contracts.monitoring.violations import ViolationSeverity


class CheckIntervalConfig(BaseModel):
    """Check scheduling intervals per check type (in minutes).

    Defaults follow FR-003 specification:
    - Freshness: 15 minutes
    - Schema drift: 60 minutes (1 hour)
    - Quality: 360 minutes (6 hours)
    - Availability: 5 minutes

    Attributes:
        freshness_minutes: Interval for freshness checks.
        schema_drift_minutes: Interval for schema drift checks.
        quality_minutes: Interval for quality checks.
        availability_minutes: Interval for availability checks.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    freshness_minutes: int = Field(default=15, ge=1)
    schema_drift_minutes: int = Field(default=60, ge=1)
    quality_minutes: int = Field(default=360, ge=1)
    availability_minutes: int = Field(default=5, ge=1)


class SeverityThresholds(BaseModel):
    """Thresholds for automatic severity assignment (FR-024).

    Severity is assigned based on SLA consumption percentage:
    - INFO: info_pct% of SLA consumed (default 80%)
    - WARNING: warning_pct% of SLA consumed (default 90%)
    - ERROR: SLA breached (100% consumed)
    - CRITICAL: >critical_count violations in critical_window_hours

    Attributes:
        info_pct: Percentage of SLA consumed to trigger INFO severity.
        warning_pct: Percentage of SLA consumed to trigger WARNING severity.
        critical_count: Number of violations to trigger CRITICAL escalation.
        critical_window_hours: Time window for CRITICAL escalation counting.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    info_pct: float = Field(default=80.0, ge=0.0, le=100.0)
    warning_pct: float = Field(default=90.0, ge=0.0, le=100.0)
    critical_count: int = Field(default=3, ge=1)
    critical_window_hours: int = Field(default=24, ge=1)


class AlertChannelRoutingRule(BaseModel):
    """Rule mapping violation severity to an alert channel (FR-028).

    Routes violations at or above min_severity to the named channel.
    Optional contract_filter allows per-contract routing via glob patterns.

    Attributes:
        channel_name: Name of the alert channel plugin to route to.
        min_severity: Minimum severity level to trigger this channel.
        contract_filter: Optional glob pattern to match contract names.

    Example:
        >>> rule = AlertChannelRoutingRule(
        ...     channel_name="slack",
        ...     min_severity=ViolationSeverity.WARNING,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    channel_name: str
    min_severity: ViolationSeverity
    contract_filter: str | None = None


class AlertConfig(BaseModel):
    """Alert routing, deduplication, and rate limiting configuration (FR-029, FR-030).

    Attributes:
        routing_rules: List of severity-to-channel routing rules.
        dedup_window_minutes: Window for alert deduplication (same contract+type).
        rate_limit_per_contract: Max alerts per contract per rate limit window.
        rate_limit_window_minutes: Time window for rate limiting.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    routing_rules: list[AlertChannelRoutingRule] = Field(default_factory=list)
    dedup_window_minutes: int = Field(default=30, ge=1)
    rate_limit_per_contract: int = Field(default=10, ge=1)
    rate_limit_window_minutes: int = Field(default=60, ge=1)


class MonitoringConfig(BaseModel):
    """Top-level monitoring configuration from platform manifest (FR-044).

    Loaded from the monitoring section of manifest.yaml. Defines global
    monitoring behavior including check intervals, severity thresholds,
    alert routing, and data retention.

    Attributes:
        enabled: Whether contract monitoring is enabled.
        mode: Monitoring mode (scheduled, continuous, or on_demand).
        check_intervals: Per-check-type scheduling intervals.
        severity_thresholds: Thresholds for severity assignment.
        alerts: Alert routing and rate limiting configuration.
        retention_days: Days to retain raw monitoring data (FR-002).
        clock_skew_tolerance_seconds: Tolerance for clock skew in freshness checks (FR-010).
        check_timeout_seconds: Default timeout for check execution (FR-022).

    Example:
        >>> config = MonitoringConfig()
        >>> config.check_intervals.freshness_minutes
        15
        >>> config.retention_days
        90
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    mode: str = Field(
        default="scheduled", pattern=r"^(scheduled|continuous|on_demand)$"
    )
    check_intervals: CheckIntervalConfig = Field(default_factory=CheckIntervalConfig)
    severity_thresholds: SeverityThresholds = Field(default_factory=SeverityThresholds)
    alerts: AlertConfig = Field(default_factory=AlertConfig)
    retention_days: int = Field(default=90, ge=1)
    clock_skew_tolerance_seconds: int = Field(default=60, ge=0)
    check_timeout_seconds: int = Field(default=30, ge=1)


class RegisteredContract(BaseModel):
    """Runtime state for a contract being actively monitored (FR-004).

    Unlike other monitoring models, this is NOT frozen because it tracks
    mutable runtime state (last_check_times, active status).

    Attributes:
        contract_name: Unique name of the data contract.
        contract_version: Semantic version of the contract.
        contract_data: Serialized contract data (ODCS v3 format).
        connection_config: Compute/catalog connection parameters.
        monitoring_overrides: Per-contract overrides for MonitoringConfig (FR-045).
        registered_at: When the contract was registered for monitoring.
        last_check_times: Map of check_type -> last execution time.
        active: Whether monitoring is active for this contract.

    Example:
        >>> contract = RegisteredContract(
        ...     contract_name="orders_v1",
        ...     contract_version="1.0.0",
        ...     contract_data={"apiVersion": "v3.1.0"},
        ...     connection_config={"catalog": "polaris"},
        ...     registered_at=datetime.now(tz=timezone.utc),
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    contract_name: str
    contract_version: str
    contract_data: dict[str, Any]
    connection_config: dict[str, Any]
    monitoring_overrides: MonitoringConfig | None = None
    registered_at: datetime
    last_check_times: dict[str, datetime] = Field(default_factory=dict)
    active: bool = True

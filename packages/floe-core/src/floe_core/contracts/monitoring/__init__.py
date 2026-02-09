"""Contract monitoring module for floe data platform.

This module provides runtime monitoring of data contracts, including:
- Freshness checks (SLA violation detection)
- Schema drift detection
- Data quality monitoring
- Availability monitoring
- Alert routing to configured channels
- SLA compliance reporting

Tasks: T001-T090 (Epic 3D)
Requirements: FR-001 through FR-047

Example:
    >>> from floe_core.contracts.monitoring import ContractMonitor, MonitoringConfig
    >>> config = MonitoringConfig()
    >>> monitor = ContractMonitor(config=config)
"""

from __future__ import annotations

from floe_core.contracts.monitoring.alert_router import AlertRouter
from floe_core.contracts.monitoring.checks.availability import AvailabilityCheck
from floe_core.contracts.monitoring.checks.base import BaseCheck
from floe_core.contracts.monitoring.checks.freshness import FreshnessCheck
from floe_core.contracts.monitoring.checks.quality import QualityCheck
from floe_core.contracts.monitoring.checks.schema_drift import SchemaDriftCheck
from floe_core.contracts.monitoring.config import (
    AlertChannelRoutingRule,
    AlertConfig,
    CheckIntervalConfig,
    MonitoringConfig,
    RegisteredContract,
    SeverityThresholds,
)
from floe_core.contracts.monitoring.custom_metrics import (
    CustomMetricDefinition,
    MetricRecorder,
)
from floe_core.contracts.monitoring.enrichment import (
    build_root_cause_context,
    resolve_affected_consumers,
)
from floe_core.contracts.monitoring.incident import (
    Incident,
    IncidentManager,
    IncidentPriority,
    IncidentStatus,
)
from floe_core.contracts.monitoring.monitor import ContractMonitor
from floe_core.contracts.monitoring.scheduler import CheckScheduler
from floe_core.contracts.monitoring.sla import (
    CheckTypeSummary,
    SLAComplianceReport,
    SLAStatus,
    TrendDirection,
)
from floe_core.contracts.monitoring.violations import (
    CheckResult,
    CheckStatus,
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)

__all__ = [
    # Violations
    "ViolationType",
    "ViolationSeverity",
    "ContractViolationEvent",
    "CheckStatus",
    "CheckResult",
    # Config
    "CheckIntervalConfig",
    "SeverityThresholds",
    "AlertChannelRoutingRule",
    "AlertConfig",
    "MonitoringConfig",
    "RegisteredContract",
    # Monitor
    "ContractMonitor",
    # Alert Router
    "AlertRouter",
    # Scheduler
    "CheckScheduler",
    # SLA
    "SLAStatus",
    "TrendDirection",
    "CheckTypeSummary",
    "SLAComplianceReport",
    # Incident
    "IncidentPriority",
    "IncidentStatus",
    "Incident",
    "IncidentManager",
    # Custom Metrics
    "CustomMetricDefinition",
    "MetricRecorder",
    # Enrichment
    "resolve_affected_consumers",
    "build_root_cause_context",
    # Checks
    "BaseCheck",
    "FreshnessCheck",
    "SchemaDriftCheck",
    "QualityCheck",
    "AvailabilityCheck",
]

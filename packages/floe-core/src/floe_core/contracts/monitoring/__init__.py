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

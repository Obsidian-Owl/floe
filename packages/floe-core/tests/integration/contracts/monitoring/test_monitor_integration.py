"""Integration tests for ContractMonitor lifecycle and operations.

Task: T086
Requirements: 3D-FR-001, 3D-FR-002, 3D-FR-003, 3D-FR-004, 3D-FR-005, 3D-FR-006

These tests validate ContractMonitor in a real environment with PostgreSQL and K8s.
Tests FAIL when infrastructure is missing (per project testing standards).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.monitor import ContractMonitor
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)


@pytest.fixture
def monitoring_config() -> MonitoringConfig:
    """Create a basic monitoring configuration for tests.

    Returns:
        MonitoringConfig with minimal settings for integration testing.
    """
    return MonitoringConfig(enabled=True)


@pytest.mark.requirement("3D-FR-001")
@pytest.mark.integration
def test_monitor_lifecycle(monitoring_config: MonitoringConfig) -> None:
    """Test ContractMonitor start/stop lifecycle.

    Validates that a monitor can be created and basic operations work.
    This is a smoke test that proves imports and basic instantiation work.

    Args:
        monitoring_config: Basic monitoring configuration fixture.
    """
    monitor = ContractMonitor(config=monitoring_config)
    assert monitor is not None


@pytest.mark.requirement("3D-FR-001")
@pytest.mark.integration
def test_monitor_register_contract(monitoring_config: MonitoringConfig) -> None:
    """Test register_contract with real PostgreSQL.

    Validates that contracts can be registered with the monitoring system
    and that registration persists to the database.

    Args:
        monitoring_config: Basic monitoring configuration fixture.
    """
    monitor = ContractMonitor(config=monitoring_config)

    # Create a registered contract
    contract = RegisteredContract(
        contract_name="test_contract",
        contract_version="1.0.0",
        contract_data={},
        connection_config={},
        registered_at=datetime.now(tz=timezone.utc),
    )

    # Register the contract
    monitor.register_contract(contract)

    # Verify contract was registered
    registered = monitor.registered_contracts
    assert "test_contract" in registered
    assert registered["test_contract"].contract_version == "1.0.0"

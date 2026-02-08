"""Unit tests for ContractMonitor lifecycle.

Tests contract registration/unregistration, start/stop lifecycle,
health checks, and check execution dispatch.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from floe_core.contracts.monitoring.config import (
    MonitoringConfig,
    RegisteredContract,
)
from floe_core.contracts.monitoring.monitor import ContractMonitor
from floe_core.contracts.monitoring.violations import (
    CheckStatus,
    ViolationType,
)


def _make_contract(
    name: str = "test_contract",
    version: str = "1.0.0",
    active: bool = True,
    monitoring_overrides: MonitoringConfig | None = None,
) -> RegisteredContract:
    """Create a test RegisteredContract.

    Args:
        name: Contract name
        version: Contract version
        active: Whether contract is active
        monitoring_overrides: Optional monitoring config overrides

    Returns:
        RegisteredContract instance
    """
    return RegisteredContract(
        contract_name=name,
        contract_version=version,
        contract_data={"tables": [{"name": "customers"}]},
        connection_config={"type": "iceberg", "catalog": "polaris"},
        monitoring_overrides=monitoring_overrides,
        registered_at=datetime.now(tz=timezone.utc),
        last_check_times={},
        active=active,
    )


@pytest.mark.requirement("3D-FR-001")
def test_monitor_init() -> None:
    """Test ContractMonitor initializes with config."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)

    assert monitor.registered_contracts == {}
    assert monitor.is_running is False


@pytest.mark.requirement("3D-FR-002")
def test_register_contract() -> None:
    """Test registering a contract."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)
    contract = _make_contract(name="test_contract")

    monitor.register_contract(contract=contract)

    assert "test_contract" in monitor.registered_contracts
    assert monitor.registered_contracts["test_contract"] == contract


@pytest.mark.requirement("3D-FR-002")
def test_register_duplicate_contract_raises() -> None:
    """Test registering duplicate contract raises ValueError."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)
    contract = _make_contract(name="test_contract")

    monitor.register_contract(contract=contract)

    with pytest.raises(ValueError, match="already registered"):
        monitor.register_contract(contract=contract)


@pytest.mark.requirement("3D-FR-002")
def test_register_inactive_contract() -> None:
    """Test registering inactive contract."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)
    contract = _make_contract(name="test_contract", active=False)

    monitor.register_contract(contract=contract)

    assert "test_contract" in monitor.registered_contracts
    assert monitor.registered_contracts["test_contract"].active is False


@pytest.mark.requirement("3D-FR-003")
def test_unregister_contract() -> None:
    """Test unregistering a contract."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)
    contract = _make_contract(name="test_contract")

    monitor.register_contract(contract=contract)
    monitor.unregister_contract(contract_name="test_contract")

    assert "test_contract" not in monitor.registered_contracts


@pytest.mark.requirement("3D-FR-003")
def test_unregister_unknown_contract_raises() -> None:
    """Test unregistering unknown contract raises KeyError."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)

    with pytest.raises(KeyError, match="not found"):
        monitor.unregister_contract(contract_name="unknown_contract")


@pytest.mark.requirement("3D-FR-004")
@pytest.mark.asyncio
async def test_start_monitor() -> None:
    """Test starting the monitor."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)

    assert monitor.is_running is False

    await monitor.start()

    assert monitor.is_running is True


@pytest.mark.requirement("3D-FR-004")
@pytest.mark.asyncio
async def test_stop_monitor() -> None:
    """Test stopping the monitor."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)

    await monitor.start()
    assert monitor.is_running is True

    await monitor.stop()

    assert monitor.is_running is False


@pytest.mark.requirement("3D-FR-005")
def test_health_check_healthy() -> None:
    """Test health_check returns healthy status."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)
    contract = _make_contract(name="test_contract")
    monitor.register_contract(contract=contract)

    health: dict[str, Any] = monitor.health_check()

    assert health["status"] == "healthy"
    assert health["registered_contracts"] == 1
    assert health["is_running"] is False


@pytest.mark.requirement("3D-FR-005")
@pytest.mark.asyncio
async def test_health_check_running() -> None:
    """Test health_check reflects running state."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)

    await monitor.start()
    health: dict[str, Any] = monitor.health_check()

    assert health["is_running"] is True

    await monitor.stop()


@pytest.mark.requirement("3D-FR-006")
@pytest.mark.asyncio
async def test_run_check_dispatches_correctly() -> None:
    """Test run_check dispatches to correct check type."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)
    contract = _make_contract(name="test_contract")
    monitor.register_contract(contract=contract)

    result = await monitor.run_check(
        contract_name="test_contract",
        check_type=ViolationType.FRESHNESS,
    )

    assert result.contract_name == "test_contract"
    assert result.check_type == ViolationType.FRESHNESS
    assert result.status in (CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.ERROR)


@pytest.mark.requirement("3D-FR-006")
@pytest.mark.asyncio
async def test_run_check_unknown_contract_raises() -> None:
    """Test run_check with unknown contract raises KeyError."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)

    with pytest.raises(KeyError, match="not registered"):
        await monitor.run_check(
            contract_name="unknown_contract",
            check_type=ViolationType.FRESHNESS,
        )


@pytest.mark.requirement("3D-FR-007")
@pytest.mark.asyncio
async def test_run_check_all_types() -> None:
    """Test run_check can dispatch to all check types."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)
    contract = _make_contract(name="test_contract")
    monitor.register_contract(contract=contract)

    for check_type in ViolationType:
        result = await monitor.run_check(
            contract_name="test_contract",
            check_type=check_type,
        )

        assert result.contract_name == "test_contract"
        assert result.check_type == check_type
        assert isinstance(result.status, CheckStatus)


@pytest.mark.requirement("3D-FR-008")
def test_register_contract_with_monitoring_overrides() -> None:
    """Test registering contract with monitoring config overrides."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)
    overrides = MonitoringConfig(enabled=False, mode="on_demand")
    contract = _make_contract(
        name="test_contract",
        monitoring_overrides=overrides,
    )

    monitor.register_contract(contract=contract)

    registered = monitor.registered_contracts["test_contract"]
    assert registered.monitoring_overrides is not None
    assert registered.monitoring_overrides.enabled is False
    assert registered.monitoring_overrides.mode == "on_demand"


@pytest.mark.requirement("3D-FR-009")
def test_registered_contracts_immutable() -> None:
    """Test registered_contracts returns copy (not mutable reference)."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)
    contract = _make_contract(name="test_contract")
    monitor.register_contract(contract=contract)

    contracts_copy = monitor.registered_contracts
    contracts_copy.pop("test_contract")

    # Original should still have the contract
    assert "test_contract" in monitor.registered_contracts


@pytest.mark.requirement("3D-FR-010")
@pytest.mark.asyncio
async def test_lifecycle_integration() -> None:
    """Test complete lifecycle: register → start → check → stop → unregister."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config)
    contract = _make_contract(name="test_contract")

    # Register
    monitor.register_contract(contract=contract)
    assert "test_contract" in monitor.registered_contracts

    # Start
    await monitor.start()
    assert monitor.is_running is True

    # Run check
    result = await monitor.run_check(
        contract_name="test_contract",
        check_type=ViolationType.FRESHNESS,
    )
    assert result.contract_name == "test_contract"

    # Health check
    health = monitor.health_check()
    assert health["is_running"] is True
    assert health["registered_contracts"] == 1

    # Stop
    await monitor.stop()
    assert monitor.is_running is False

    # Unregister
    monitor.unregister_contract(contract_name="test_contract")
    assert "test_contract" not in monitor.registered_contracts

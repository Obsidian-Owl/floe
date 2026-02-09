"""Integration test for AvailabilityCheck wiring into ContractMonitor.

Tasks: T051 (Epic 3D)
Requirements: FR-019, FR-020
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.monitor import ContractMonitor
from floe_core.contracts.monitoring.violations import CheckStatus, ViolationType


class MockComputePlugin:
    """Mock compute plugin for testing."""

    def __init__(self, *, success: bool = True, latency_ms: float = 10.0) -> None:
        self.success = success
        self.latency_ms = latency_ms

    async def validate_connection(self) -> dict[str, Any]:
        """Mock validate_connection method."""
        return {
            "status": "ok" if self.success else "error",
            "latency_ms": self.latency_ms,
        }


@pytest.mark.requirement("3D-FR-019")
@pytest.mark.asyncio
async def test_monitor_dispatches_availability_check_success() -> None:
    """Test ContractMonitor dispatches AvailabilityCheck and returns PASS."""
    config = MonitoringConfig()
    plugin = MockComputePlugin(success=True, latency_ms=15.0)
    monitor = ContractMonitor(config=config, compute_plugin=plugin)

    now = datetime.now(tz=timezone.utc)
    contract = RegisteredContract(
        contract_name="test_contract",
        contract_version="1.0.0",
        contract_data={
            "apiVersion": "v3.1.0",
            "sla": {"availability": {"threshold_pct": 99.9}},
        },
        connection_config={"catalog": "polaris"},
        registered_at=now - timedelta(hours=1),
    )

    monitor.register_contract(contract)
    result = await monitor.run_check("test_contract", ViolationType.AVAILABILITY)

    assert result.status == CheckStatus.PASS
    assert result.check_type == ViolationType.AVAILABILITY
    assert result.contract_name == "test_contract"
    assert result.violation is None
    assert "latency_ms" in result.details
    assert result.details["latency_ms"] == 15.0


@pytest.mark.requirement("3D-FR-020")
@pytest.mark.asyncio
async def test_monitor_dispatches_availability_check_failure() -> None:
    """Test ContractMonitor dispatches AvailabilityCheck and returns FAIL."""
    config = MonitoringConfig()
    plugin = MockComputePlugin(success=False)
    monitor = ContractMonitor(config=config, compute_plugin=plugin)

    now = datetime.now(tz=timezone.utc)
    contract = RegisteredContract(
        contract_name="test_contract",
        contract_version="1.0.0",
        contract_data={
            "apiVersion": "v3.1.0",
            "sla": {"availability": {"threshold_pct": 99.9}},
        },
        connection_config={"catalog": "polaris"},
        registered_at=now - timedelta(hours=1),
    )

    monitor.register_contract(contract)
    result = await monitor.run_check("test_contract", ViolationType.AVAILABILITY)

    assert result.status == CheckStatus.FAIL
    assert result.check_type == ViolationType.AVAILABILITY
    assert result.violation is not None
    assert result.violation.violation_type == ViolationType.AVAILABILITY


@pytest.mark.requirement("3D-FR-019")
@pytest.mark.asyncio
async def test_monitor_availability_check_skipped_no_plugin() -> None:
    """Test AvailabilityCheck returns SKIPPED when no compute plugin provided."""
    config = MonitoringConfig()
    monitor = ContractMonitor(config=config, compute_plugin=None)

    now = datetime.now(tz=timezone.utc)
    contract = RegisteredContract(
        contract_name="test_contract",
        contract_version="1.0.0",
        contract_data={
            "apiVersion": "v3.1.0",
            "sla": {"availability": {"threshold_pct": 99.9}},
        },
        connection_config={"catalog": "polaris"},
        registered_at=now - timedelta(hours=1),
    )

    monitor.register_contract(contract)
    result = await monitor.run_check("test_contract", ViolationType.AVAILABILITY)

    assert result.status == CheckStatus.SKIPPED
    assert result.check_type == ViolationType.AVAILABILITY
    assert result.violation is None
    assert "plugin" in result.details["reason"].lower()

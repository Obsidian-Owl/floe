"""Integration tests for ContractMonitor orchestrator.

Tests the complete monitoring workflow: check execution, result persistence,
and alert routing with real PostgreSQL and mock alert channels.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from floe_core.contracts.monitoring.alert_router import AlertRouter
from floe_core.contracts.monitoring.config import (
    AlertChannelRoutingRule,
    AlertConfig,
    MonitoringConfig,
    RegisteredContract,
)
from floe_core.contracts.monitoring.db.repository import MonitoringRepository
from floe_core.contracts.monitoring.monitor import ContractMonitor
from floe_core.contracts.monitoring.violations import (
    CheckStatus,
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)
from floe_core.plugins.alert_channel import AlertChannelPlugin


class MockAlertChannel(AlertChannelPlugin):
    """Mock alert channel for testing alert routing."""

    def __init__(self) -> None:
        """Initialize mock channel with event tracking."""
        self.received_events: list[ContractViolationEvent] = []

    @property
    def name(self) -> str:
        """Channel name."""
        return "mock_channel"

    @property
    def version(self) -> str:
        """Channel version."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Supported floe API version."""
        return "1.0"

    async def send_alert(self, event: ContractViolationEvent) -> bool:
        """Record alert event.

        Args:
            event: Violation event to send

        Returns:
            True if alert sent successfully
        """
        self.received_events.append(event)
        return True

    def validate_config(self) -> list[str]:
        """Validate channel configuration.

        Returns:
            Empty list (mock always valid)
        """
        return []


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-027")
async def test_monitor_register_and_run_freshness_check(
    contract_monitor: ContractMonitor,
) -> None:
    """Test monitor can register contract and run freshness check successfully.

    Validates that a contract with fresh data passes the freshness check.
    """
    # Create contract with fresh data (last updated now, threshold 60 min)
    fresh_contract = RegisteredContract(
        contract_name=f"fresh_contract_{uuid.uuid4().hex[:8]}",
        contract_version="1.0.0",
        contract_data={
            "sla": {"freshness": {"threshold_minutes": 60}},
            "dataset": {"last_updated": datetime.now(timezone.utc).isoformat()},
        },
        connection_config={"catalog": "test"},
        registered_at=datetime.now(timezone.utc),
    )

    # Register and run check
    contract_monitor.register_contract(fresh_contract)
    result = await contract_monitor.run_check(
        fresh_contract.contract_name, ViolationType.FRESHNESS
    )

    # Assert check passed
    assert result.status == CheckStatus.PASS
    assert result.check_type == ViolationType.FRESHNESS
    assert result.violation is None


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-027")
async def test_monitor_run_check_persists_result_to_postgres(
    monitoring_repository: MonitoringRepository,
    monitoring_config: MonitoringConfig,
) -> None:
    """Test monitor persists check results and violations to PostgreSQL.

    Validates that failed checks are persisted to the database and can be
    queried back within the same session.
    """
    # Create contract with stale data (2 hours ago, threshold 30 min)
    stale_contract = RegisteredContract(
        contract_name=f"stale_contract_{uuid.uuid4().hex[:8]}",
        contract_version="1.0.0",
        contract_data={
            "sla": {"freshness": {"threshold_minutes": 30}},
            "dataset": {
                "last_updated": (
                    datetime.now(timezone.utc) - timedelta(hours=2)
                ).isoformat()
            },
        },
        connection_config={"catalog": "test"},
        registered_at=datetime.now(timezone.utc),
    )

    # Create monitor with repository
    monitor = ContractMonitor(
        config=monitoring_config, repository=monitoring_repository
    )

    # Register contract and run check
    monitor.register_contract(stale_contract)
    result = await monitor.run_check(
        stale_contract.contract_name, ViolationType.FRESHNESS
    )

    # Assert check failed with violation
    assert result.status == CheckStatus.FAIL
    assert result.violation is not None

    # Query violations from repository (within same session before rollback)
    violations = await monitoring_repository.get_violations(
        contract_name=stale_contract.contract_name
    )

    # Assert violation was persisted
    assert len(violations) == 1
    assert violations[0]["contract_name"] == stale_contract.contract_name
    assert violations[0]["violation_type"] == ViolationType.FRESHNESS.value


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-027")
async def test_monitor_run_check_routes_violation_to_alert_channel(
    monitoring_repository: MonitoringRepository,
    monitoring_config: MonitoringConfig,
) -> None:
    """Test monitor routes violations to alert channels.

    Validates that violations are sent to configured alert channels
    via the AlertRouter.
    """
    # Create mock alert channel
    mock_channel = MockAlertChannel()

    # Create alert config with routing rule
    alert_config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="test_channel",
                min_severity=ViolationSeverity.INFO,
                contract_filter="stale_*",
            )
        ],
    )

    # Create alert router
    alert_router = AlertRouter(
        config=alert_config, channels={"test_channel": mock_channel}
    )

    # Create monitor with alert router and repository
    monitor = ContractMonitor(
        config=monitoring_config,
        repository=monitoring_repository,
        alert_router=alert_router,
    )

    # Create contract with stale data
    stale_contract = RegisteredContract(
        contract_name=f"stale_alert_{uuid.uuid4().hex[:8]}",
        contract_version="1.0.0",
        contract_data={
            "sla": {"freshness": {"threshold_minutes": 30}},
            "dataset": {
                "last_updated": (
                    datetime.now(timezone.utc) - timedelta(hours=2)
                ).isoformat()
            },
        },
        connection_config={"catalog": "test"},
        registered_at=datetime.now(timezone.utc),
    )

    # Register and run check
    monitor.register_contract(stale_contract)
    await monitor.run_check(stale_contract.contract_name, ViolationType.FRESHNESS)

    # Assert alert was sent to mock channel
    assert len(mock_channel.received_events) == 1
    event = mock_channel.received_events[0]
    assert event.contract_name == stale_contract.contract_name
    assert event.violation_type == ViolationType.FRESHNESS


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-027")
async def test_monitor_lifecycle_start_stop(
    contract_monitor: ContractMonitor,
) -> None:
    """Test monitor lifecycle start/stop and health check.

    Validates that the monitor can be started, reports healthy status,
    and can be stopped cleanly.
    """
    # Assert not running initially
    assert not contract_monitor.is_running

    # Start monitor
    await contract_monitor.start()
    assert contract_monitor.is_running

    # Check health
    health = contract_monitor.health_check()
    assert health["is_running"] is True
    assert health["status"] == "healthy"

    # Stop monitor
    await contract_monitor.stop()
    assert not contract_monitor.is_running


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-027")
async def test_monitor_run_check_unregistered_contract_raises(
    contract_monitor: ContractMonitor,
) -> None:
    """Test running check on unregistered contract raises KeyError.

    Validates that attempting to check a non-existent contract fails
    with a clear error.
    """
    with pytest.raises(KeyError, match="nonexistent"):
        await contract_monitor.run_check("nonexistent", ViolationType.FRESHNESS)


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-027")
async def test_monitor_register_duplicate_raises(
    contract_monitor: ContractMonitor,
    sample_contract: RegisteredContract,
) -> None:
    """Test registering duplicate contract raises ValueError.

    Validates that the monitor prevents duplicate contract registration.
    """
    # Register contract
    contract_monitor.register_contract(sample_contract)

    # Attempt to register again
    with pytest.raises(ValueError, match="already registered"):
        contract_monitor.register_contract(sample_contract)

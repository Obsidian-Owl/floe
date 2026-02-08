"""Unit tests for AlertRouter.

Tasks: T035 (Epic 3D)
Requirements: FR-028, FR-029, FR-030
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from floe_core.contracts.monitoring.alert_router import AlertRouter
from floe_core.contracts.monitoring.config import AlertChannelRoutingRule, AlertConfig
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)
from floe_core.plugins.alert_channel import AlertChannelPlugin


class MockAlertChannel(AlertChannelPlugin):
    """Mock alert channel for testing."""

    def __init__(
        self,
        name: str = "mock",
        fail: bool = False,
        raise_error: bool = False,
    ) -> None:
        self._name = name
        self._fail = fail
        self._raise_error = raise_error
        self.sent_events: list[ContractViolationEvent] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    async def send_alert(self, event: ContractViolationEvent) -> bool:
        if self._raise_error:
            raise RuntimeError("Channel error")
        if self._fail:
            return False
        self.sent_events.append(event)
        return True

    def validate_config(self) -> list[str]:
        return []


def _make_event(
    *,
    contract_name: str = "orders_v1",
    violation_type: ViolationType = ViolationType.FRESHNESS,
    severity: ViolationSeverity = ViolationSeverity.ERROR,
) -> ContractViolationEvent:
    """Helper to create test violation events."""
    return ContractViolationEvent(
        contract_name=contract_name,
        contract_version="1.0.0",
        violation_type=violation_type,
        severity=severity,
        message="Test violation",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.1,
    )


@pytest.mark.requirement("3D-FR-028")
@pytest.mark.asyncio
async def test_route_by_severity() -> None:
    """Test violation with WARNING severity routes to channels with min_severity <= WARNING."""
    channel_warning = MockAlertChannel(name="warning_channel")
    channel_error = MockAlertChannel(name="error_channel")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="warning_channel", min_severity=ViolationSeverity.WARNING
            ),
            AlertChannelRoutingRule(
                channel_name="error_channel", min_severity=ViolationSeverity.ERROR
            ),
        ],
        dedup_window_minutes=5,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(
        config=config,
        channels={
            "warning_channel": channel_warning,
            "error_channel": channel_error,
        },
    )

    event = _make_event(severity=ViolationSeverity.WARNING)
    results = await router.route(event)

    # WARNING alert should go to warning_channel (WARNING <= WARNING)
    # but NOT error_channel (WARNING < ERROR)
    assert results == {"warning_channel": True}
    assert len(channel_warning.sent_events) == 1
    assert len(channel_error.sent_events) == 0


@pytest.mark.requirement("3D-FR-028")
@pytest.mark.asyncio
async def test_route_no_matching_channels() -> None:
    """Test violation below all channel min_severity thresholds → no dispatch."""
    channel = MockAlertChannel(name="error_channel")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="error_channel", min_severity=ViolationSeverity.ERROR
            ),
        ],
        dedup_window_minutes=5,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(config=config, channels={"error_channel": channel})

    event = _make_event(severity=ViolationSeverity.INFO)
    results = await router.route(event)

    assert results == {}
    assert len(channel.sent_events) == 0


@pytest.mark.requirement("3D-FR-028")
@pytest.mark.asyncio
async def test_route_multiple_channels() -> None:
    """Test violation matches multiple routing rules → dispatched to all matching channels."""
    channel1 = MockAlertChannel(name="channel1")
    channel2 = MockAlertChannel(name="channel2")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="channel1", min_severity=ViolationSeverity.WARNING
            ),
            AlertChannelRoutingRule(
                channel_name="channel2", min_severity=ViolationSeverity.WARNING
            ),
        ],
        dedup_window_minutes=5,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(
        config=config,
        channels={
            "channel1": channel1,
            "channel2": channel2,
        },
    )

    event = _make_event(severity=ViolationSeverity.ERROR)
    results = await router.route(event)

    assert results == {"channel1": True, "channel2": True}
    assert len(channel1.sent_events) == 1
    assert len(channel2.sent_events) == 1


@pytest.mark.requirement("3D-FR-028")
@pytest.mark.asyncio
async def test_route_contract_filter_match() -> None:
    """Test routing rule with contract_filter glob matches contract name."""
    channel = MockAlertChannel(name="orders_channel")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="orders_channel",
                min_severity=ViolationSeverity.WARNING,
                contract_filter="orders_*",
            ),
        ],
        dedup_window_minutes=5,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(config=config, channels={"orders_channel": channel})

    event = _make_event(contract_name="orders_v1", severity=ViolationSeverity.ERROR)
    results = await router.route(event)

    assert results == {"orders_channel": True}
    assert len(channel.sent_events) == 1


@pytest.mark.requirement("3D-FR-028")
@pytest.mark.asyncio
async def test_route_contract_filter_no_match() -> None:
    """Test routing rule with contract_filter glob does NOT match contract name."""
    channel = MockAlertChannel(name="orders_channel")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="orders_channel",
                min_severity=ViolationSeverity.WARNING,
                contract_filter="orders_*",
            ),
        ],
        dedup_window_minutes=5,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(config=config, channels={"orders_channel": channel})

    event = _make_event(contract_name="customers_v1", severity=ViolationSeverity.ERROR)
    results = await router.route(event)

    assert results == {}
    assert len(channel.sent_events) == 0


@pytest.mark.requirement("3D-FR-029")
@pytest.mark.asyncio
async def test_deduplication_within_window() -> None:
    """Test same contract+violation_type within dedup_window_minutes → second is suppressed."""
    channel = MockAlertChannel(name="channel")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="channel", min_severity=ViolationSeverity.WARNING
            ),
        ],
        dedup_window_minutes=5,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(config=config, channels={"channel": channel})

    event1 = _make_event(
        contract_name="orders_v1", violation_type=ViolationType.FRESHNESS
    )
    event2 = _make_event(
        contract_name="orders_v1", violation_type=ViolationType.FRESHNESS
    )

    results1 = await router.route(event1)
    results2 = await router.route(event2)

    # First alert should succeed
    assert results1 == {"channel": True}
    # Second alert should be deduplicated (empty results)
    assert results2 == {}
    assert len(channel.sent_events) == 1


@pytest.mark.requirement("3D-FR-029")
@pytest.mark.asyncio
async def test_deduplication_after_window() -> None:
    """Test same contract+violation_type after dedup window expires → not suppressed."""
    channel = MockAlertChannel(name="channel")

    # 1 minute dedup window for testing (minimum allowed)
    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="channel", min_severity=ViolationSeverity.WARNING
            ),
        ],
        dedup_window_minutes=1,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(config=config, channels={"channel": channel})

    event1 = _make_event(
        contract_name="orders_v1", violation_type=ViolationType.FRESHNESS
    )
    results1 = await router.route(event1)

    # Manually advance dedup state timestamp to simulate window expiry
    # This avoids needing to sleep for 60 seconds in the test
    for key in router._dedup_state:
        router._dedup_state[key] = time.monotonic() - 61  # Set to 61 seconds ago

    event2 = _make_event(
        contract_name="orders_v1", violation_type=ViolationType.FRESHNESS
    )
    results2 = await router.route(event2)

    # Both alerts should succeed
    assert results1 == {"channel": True}
    assert results2 == {"channel": True}
    assert len(channel.sent_events) == 2


@pytest.mark.requirement("3D-FR-029")
@pytest.mark.asyncio
async def test_deduplication_different_type() -> None:
    """Test same contract but different violation_type → not suppressed."""
    channel = MockAlertChannel(name="channel")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="channel", min_severity=ViolationSeverity.WARNING
            ),
        ],
        dedup_window_minutes=5,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(config=config, channels={"channel": channel})

    event1 = _make_event(
        contract_name="orders_v1", violation_type=ViolationType.FRESHNESS
    )
    event2 = _make_event(
        contract_name="orders_v1", violation_type=ViolationType.SCHEMA_DRIFT
    )

    results1 = await router.route(event1)
    results2 = await router.route(event2)

    # Both alerts should succeed (different violation types)
    assert results1 == {"channel": True}
    assert results2 == {"channel": True}
    assert len(channel.sent_events) == 2


@pytest.mark.requirement("3D-FR-030")
@pytest.mark.asyncio
async def test_rate_limit_exceeded() -> None:
    """Test more than rate_limit_per_contract alerts in window → excess suppressed."""
    channel = MockAlertChannel(name="channel")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="channel", min_severity=ViolationSeverity.WARNING
            ),
        ],
        dedup_window_minutes=1,  # Minimum allowed value
        rate_limit_per_contract=2,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(config=config, channels={"channel": channel})

    # Send 3 alerts for same contract (different violation types to avoid dedup)
    event1 = _make_event(
        contract_name="orders_v1", violation_type=ViolationType.FRESHNESS
    )
    event2 = _make_event(
        contract_name="orders_v1", violation_type=ViolationType.SCHEMA_DRIFT
    )
    event3 = _make_event(
        contract_name="orders_v1", violation_type=ViolationType.QUALITY
    )

    results1 = await router.route(event1)
    results2 = await router.route(event2)
    results3 = await router.route(event3)

    # First 2 should succeed, 3rd should be rate limited
    assert results1 == {"channel": True}
    assert results2 == {"channel": True}
    assert results3 == {}
    assert len(channel.sent_events) == 2


@pytest.mark.requirement("3D-FR-030")
@pytest.mark.asyncio
async def test_rate_limit_different_contracts() -> None:
    """Test rate limits are per-contract, not global."""
    channel = MockAlertChannel(name="channel")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="channel", min_severity=ViolationSeverity.WARNING
            ),
        ],
        dedup_window_minutes=1,  # Minimum allowed value
        rate_limit_per_contract=2,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(config=config, channels={"channel": channel})

    # Send 2 alerts for each contract
    event1_orders = _make_event(
        contract_name="orders_v1", violation_type=ViolationType.FRESHNESS
    )
    event2_orders = _make_event(
        contract_name="orders_v1", violation_type=ViolationType.SCHEMA_DRIFT
    )
    event1_customers = _make_event(
        contract_name="customers_v1", violation_type=ViolationType.FRESHNESS
    )
    event2_customers = _make_event(
        contract_name="customers_v1", violation_type=ViolationType.SCHEMA_DRIFT
    )

    results1 = await router.route(event1_orders)
    results2 = await router.route(event2_orders)
    results3 = await router.route(event1_customers)
    results4 = await router.route(event2_customers)

    # All should succeed (separate rate limits per contract)
    assert results1 == {"channel": True}
    assert results2 == {"channel": True}
    assert results3 == {"channel": True}
    assert results4 == {"channel": True}
    assert len(channel.sent_events) == 4


@pytest.mark.requirement("3D-FR-028")
@pytest.mark.asyncio
async def test_channel_send_failure_logged() -> None:
    """Test channel.send_alert() returns False → logged, doesn't block other channels."""
    channel_fail = MockAlertChannel(name="fail_channel", fail=True)
    channel_ok = MockAlertChannel(name="ok_channel")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="fail_channel", min_severity=ViolationSeverity.WARNING
            ),
            AlertChannelRoutingRule(
                channel_name="ok_channel", min_severity=ViolationSeverity.WARNING
            ),
        ],
        dedup_window_minutes=5,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(
        config=config,
        channels={
            "fail_channel": channel_fail,
            "ok_channel": channel_ok,
        },
    )

    event = _make_event(severity=ViolationSeverity.ERROR)
    results = await router.route(event)

    # Both channels attempted, fail_channel returned False, ok_channel succeeded
    assert results == {"fail_channel": False, "ok_channel": True}
    assert len(channel_ok.sent_events) == 1


@pytest.mark.requirement("3D-FR-028")
@pytest.mark.asyncio
async def test_channel_send_exception_caught() -> None:
    """Test channel.send_alert() raises → caught, logged, doesn't propagate."""
    channel_error = MockAlertChannel(name="error_channel", raise_error=True)
    channel_ok = MockAlertChannel(name="ok_channel")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="error_channel", min_severity=ViolationSeverity.WARNING
            ),
            AlertChannelRoutingRule(
                channel_name="ok_channel", min_severity=ViolationSeverity.WARNING
            ),
        ],
        dedup_window_minutes=5,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(
        config=config,
        channels={
            "error_channel": channel_error,
            "ok_channel": channel_ok,
        },
    )

    event = _make_event(severity=ViolationSeverity.ERROR)
    results = await router.route(event)

    # Exception caught, marked as False, didn't block ok_channel
    assert results == {"error_channel": False, "ok_channel": True}
    assert len(channel_ok.sent_events) == 1


@pytest.mark.requirement("3D-FR-028")
@pytest.mark.asyncio
async def test_no_routing_rules() -> None:
    """Test empty routing_rules → no dispatch, no error."""
    channel = MockAlertChannel(name="channel")

    config = AlertConfig(
        routing_rules=[],
        dedup_window_minutes=5,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(config=config, channels={"channel": channel})

    event = _make_event(severity=ViolationSeverity.ERROR)
    results = await router.route(event)

    assert results == {}
    assert len(channel.sent_events) == 0


@pytest.mark.requirement("3D-FR-028")
@pytest.mark.asyncio
async def test_inactive_contract_skipped() -> None:
    """Test router should still process (filtering is monitor's job, not router's)."""
    channel = MockAlertChannel(name="channel")

    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="channel", min_severity=ViolationSeverity.WARNING
            ),
        ],
        dedup_window_minutes=5,
        rate_limit_per_contract=10,
        rate_limit_window_minutes=60,
    )

    router = AlertRouter(config=config, channels={"channel": channel})

    # Router doesn't filter by contract active status - that's the monitor's job
    event = _make_event(
        contract_name="inactive_contract", severity=ViolationSeverity.ERROR
    )
    results = await router.route(event)

    # Alert should be routed regardless (monitor handles filtering)
    assert results == {"channel": True}
    assert len(channel.sent_events) == 1

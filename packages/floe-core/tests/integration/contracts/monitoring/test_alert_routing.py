"""Integration tests for AlertRouter alert delivery.

Tests FR-030 — alert routing, deduplication, rate limiting, and severity filtering.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from floe_core.contracts.monitoring.alert_router import AlertRouter
from floe_core.contracts.monitoring.config import (
    AlertChannelRoutingRule,
    AlertConfig,
)
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)
from floe_core.plugins.alert_channel import AlertChannelPlugin


class MockAlertChannel(AlertChannelPlugin):
    """Mock alert channel that records delivered events."""

    def __init__(self, *, channel_name: str = "mock") -> None:
        """Initialize mock channel.

        Args:
            channel_name: Name for this channel instance
        """
        self._name = channel_name
        self.received_events: list[ContractViolationEvent] = []

    @property
    def name(self) -> str:
        """Channel name."""
        return self._name

    @property
    def version(self) -> str:
        """Channel version."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Supported floe API version."""
        return "1.0"

    async def send_alert(self, event: ContractViolationEvent) -> bool:
        """Record event and return success.

        Args:
            event: Violation event

        Returns:
            True always
        """
        self.received_events.append(event)
        return True

    def validate_config(self) -> list[str]:
        """No validation needed for mock.

        Returns:
            Empty list
        """
        return []


class FailingAlertChannel(AlertChannelPlugin):
    """Alert channel that always fails delivery."""

    @property
    def name(self) -> str:
        """Channel name."""
        return "failing"

    @property
    def version(self) -> str:
        """Channel version."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Supported floe API version."""
        return "1.0"

    async def send_alert(self, event: ContractViolationEvent) -> bool:
        """Simulate delivery failure.

        Args:
            event: Violation event

        Raises:
            ConnectionError: Always raises
        """
        raise ConnectionError("Webhook endpoint unreachable")

    def validate_config(self) -> list[str]:
        """No validation needed for mock.

        Returns:
            Empty list
        """
        return []


def _make_event(
    *,
    contract_name: str = "orders_v1",
    violation_type: ViolationType = ViolationType.FRESHNESS,
    severity: ViolationSeverity = ViolationSeverity.ERROR,
    message: str = "Data stale",
) -> ContractViolationEvent:
    """Create a ContractViolationEvent with sensible defaults.

    Args:
        contract_name: Contract name
        violation_type: Violation type
        severity: Severity level
        message: Alert message

    Returns:
        ContractViolationEvent instance
    """
    return ContractViolationEvent(
        contract_name=contract_name,
        contract_version="1.0.0",
        violation_type=violation_type,
        severity=severity,
        message=message,
        timestamp=datetime.now(timezone.utc),
        check_duration_seconds=0.5,
    )


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-030")
async def test_alert_routes_to_matching_channel() -> None:
    """Test alert is delivered to channel matching severity rule."""
    channel = MockAlertChannel(channel_name="slack")
    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="slack",
                min_severity=ViolationSeverity.WARNING,
            ),
        ],
    )
    router = AlertRouter(config=config, channels={"slack": channel})

    event = _make_event(severity=ViolationSeverity.ERROR)
    results = await router.route(event)

    assert results == {"slack": True}
    assert len(channel.received_events) == 1
    assert channel.received_events[0].contract_name == "orders_v1"


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-030")
async def test_alert_filtered_by_min_severity() -> None:
    """Test alert below min_severity is not delivered."""
    channel = MockAlertChannel(channel_name="pagerduty")
    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="pagerduty",
                min_severity=ViolationSeverity.CRITICAL,
            ),
        ],
    )
    router = AlertRouter(config=config, channels={"pagerduty": channel})

    event = _make_event(severity=ViolationSeverity.WARNING)
    results = await router.route(event)

    assert results == {}
    assert len(channel.received_events) == 0


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-030")
async def test_alert_filtered_by_contract_glob() -> None:
    """Test alert filtered out by contract_filter glob pattern."""
    channel = MockAlertChannel(channel_name="slack")
    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="slack",
                min_severity=ViolationSeverity.INFO,
                contract_filter="production_*",
            ),
        ],
    )
    router = AlertRouter(config=config, channels={"slack": channel})

    # "orders_v1" does NOT match "production_*"
    event = _make_event(contract_name="orders_v1")
    results = await router.route(event)

    assert results == {}
    assert len(channel.received_events) == 0

    # "production_orders" DOES match
    event2 = _make_event(contract_name="production_orders")
    results2 = await router.route(event2)

    assert results2 == {"slack": True}
    assert len(channel.received_events) == 1


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-030")
async def test_alert_routed_to_multiple_channels() -> None:
    """Test alert routed to multiple matching channels simultaneously."""
    slack = MockAlertChannel(channel_name="slack")
    email = MockAlertChannel(channel_name="email")
    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="slack",
                min_severity=ViolationSeverity.WARNING,
            ),
            AlertChannelRoutingRule(
                channel_name="email",
                min_severity=ViolationSeverity.ERROR,
            ),
        ],
    )
    router = AlertRouter(
        config=config,
        channels={"slack": slack, "email": email},
    )

    event = _make_event(severity=ViolationSeverity.CRITICAL)
    results = await router.route(event)

    assert results == {"slack": True, "email": True}
    assert len(slack.received_events) == 1
    assert len(email.received_events) == 1


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-030")
async def test_alert_deduplication_suppresses_repeat() -> None:
    """Test deduplication suppresses duplicate alerts within window."""
    channel = MockAlertChannel(channel_name="slack")
    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="slack",
                min_severity=ViolationSeverity.INFO,
            ),
        ],
        dedup_window_minutes=30,
    )
    router = AlertRouter(config=config, channels={"slack": channel})

    event = _make_event()

    # First delivery should succeed
    results1 = await router.route(event)
    assert results1 == {"slack": True}

    # Second delivery of same contract+type within window should be deduplicated
    results2 = await router.route(event)
    assert results2 == {}
    assert len(channel.received_events) == 1  # Only first delivery


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-030")
async def test_alert_rate_limiting() -> None:
    """Test rate limiting prevents excess alerts per contract."""
    channel = MockAlertChannel(channel_name="slack")
    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="slack",
                min_severity=ViolationSeverity.INFO,
            ),
        ],
        rate_limit_per_contract=2,
        rate_limit_window_minutes=60,
        dedup_window_minutes=1,  # Tiny dedup window so different types pass dedup
    )
    router = AlertRouter(config=config, channels={"slack": channel})

    # Send 3 alerts with different violation types to bypass dedup
    types = [ViolationType.FRESHNESS, ViolationType.QUALITY, ViolationType.AVAILABILITY]
    for vtype in types:
        event = _make_event(violation_type=vtype)
        await router.route(event)

    # Rate limit is 2, so only 2 should be delivered
    assert len(channel.received_events) == 2


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-030")
async def test_alert_channel_failure_does_not_propagate() -> None:
    """Test channel delivery failure is caught and does not propagate."""
    failing = FailingAlertChannel()
    config = AlertConfig(
        routing_rules=[
            AlertChannelRoutingRule(
                channel_name="failing",
                min_severity=ViolationSeverity.INFO,
            ),
        ],
    )
    router = AlertRouter(config=config, channels={"failing": failing})

    event = _make_event()
    results = await router.route(event)

    # Failure is recorded but not raised
    assert results == {"failing": False}


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-030")
async def test_alert_no_matching_rules_returns_empty() -> None:
    """Test routing with no matching rules returns empty results."""
    channel = MockAlertChannel(channel_name="slack")
    config = AlertConfig(routing_rules=[])  # No rules
    router = AlertRouter(config=config, channels={"slack": channel})

    event = _make_event()
    results = await router.route(event)

    assert results == {}
    assert len(channel.received_events) == 0

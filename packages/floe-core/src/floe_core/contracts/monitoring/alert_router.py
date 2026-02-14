"""Alert routing engine for contract monitoring.

Routes ContractViolationEvents to configured AlertChannelPlugins based on
severity routing rules, with deduplication and rate limiting.

Tasks: T036 (Epic 3D)
Requirements: FR-028, FR-029, FR-030
"""

from __future__ import annotations

import fnmatch
import time
from typing import TYPE_CHECKING

import structlog

from floe_core.contracts.monitoring.config import AlertConfig
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
)

if TYPE_CHECKING:
    from floe_core.plugins.alert_channel import AlertChannelPlugin

logger = structlog.get_logger(__name__)

# Severity ordering for comparison
SEVERITY_ORDER: dict[ViolationSeverity, int] = {
    ViolationSeverity.INFO: 0,
    ViolationSeverity.WARNING: 1,
    ViolationSeverity.ERROR: 2,
    ViolationSeverity.CRITICAL: 3,
}


class AlertRouter:
    """Routes violation alerts to channels based on severity and contract filters.

    Features:
    - Severity-based routing: channels receive alerts >= their min_severity
    - Contract filtering: optional glob pattern per rule to match contract names
    - Deduplication: same contract+violation_type suppressed within dedup window
    - Rate limiting: max N alerts per contract per rate limit window
    - Fire-and-forget: channel failures logged, never propagated

    Args:
        config: AlertConfig with routing_rules, dedup, and rate limit settings
        channels: Dict mapping channel_name to AlertChannelPlugin instance
    """

    def __init__(
        self,
        config: AlertConfig,
        channels: dict[str, AlertChannelPlugin],
    ) -> None:
        self._config = config
        self._channels = channels
        self._dedup_state: dict[str, float] = {}  # "contract:type" -> last_alert_timestamp
        self._rate_state: dict[str, list[float]] = {}  # "contract" -> [timestamps]
        self._log = logger.bind(component="alert_router")

    async def route(self, event: ContractViolationEvent) -> dict[str, bool]:
        """Route a violation event to matching channels.

        Returns dict mapping channel_name -> delivery_success for channels that
        received the alert. Channels filtered out by routing/dedup/rate-limit
        are not included.
        """
        results: dict[str, bool] = {}
        now = time.monotonic()

        # Check deduplication
        dedup_key = f"{event.contract_name}:{event.violation_type.value}"
        dedup_window_secs = self._config.dedup_window_minutes * 60

        if dedup_key in self._dedup_state:
            last_time = self._dedup_state[dedup_key]
            if (now - last_time) < dedup_window_secs:
                self._log.debug(
                    "alert_deduplicated",
                    contract_name=event.contract_name,
                    violation_type=event.violation_type.value,
                )
                return results

        # Check rate limiting
        rate_key = event.contract_name
        rate_window_secs = self._config.rate_limit_window_minutes * 60

        if rate_key not in self._rate_state:
            self._rate_state[rate_key] = []

        # Clean expired entries
        self._rate_state[rate_key] = [
            t for t in self._rate_state[rate_key] if (now - t) < rate_window_secs
        ]

        if len(self._rate_state[rate_key]) >= self._config.rate_limit_per_contract:
            self._log.warning(
                "alert_rate_limited",
                contract_name=event.contract_name,
                limit=self._config.rate_limit_per_contract,
            )
            return results

        # Find matching channels via routing rules
        event_severity_order = SEVERITY_ORDER[event.severity]

        matched_channels: set[str] = set()
        for rule in self._config.routing_rules:
            rule_severity_order = SEVERITY_ORDER[rule.min_severity]

            # Severity check: event severity must be >= rule min_severity
            if event_severity_order < rule_severity_order:
                continue

            # Contract filter check (glob matching)
            if rule.contract_filter is not None:
                if not fnmatch.fnmatch(event.contract_name, rule.contract_filter):
                    continue

            if rule.channel_name in self._channels:
                matched_channels.add(rule.channel_name)

        # Dispatch to matched channels (fire-and-forget)
        for channel_name in matched_channels:
            channel = self._channels[channel_name]
            try:
                success = await channel.send_alert(event)
                results[channel_name] = success
                if not success:
                    self._log.warning(
                        "alert_delivery_failed",
                        channel=channel_name,
                        contract_name=event.contract_name,
                    )
            except Exception as e:
                results[channel_name] = False
                self._log.error(
                    "alert_delivery_error",
                    channel=channel_name,
                    contract_name=event.contract_name,
                    error=str(e),
                )

        # Update dedup and rate state ONLY if we dispatched
        if matched_channels:
            self._dedup_state[dedup_key] = now
            self._rate_state[rate_key].append(now)

        return results

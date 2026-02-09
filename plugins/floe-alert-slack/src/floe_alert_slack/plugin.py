"""Slack alert channel plugin.

Sends contract violation alerts to Slack using Block Kit formatting
via incoming webhooks.

Tasks: T042 (Epic 3D)
Requirements: FR-026, FR-027
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
)
from floe_core.plugins.alert_channel import AlertChannelPlugin

logger = structlog.get_logger(__name__)

SEVERITY_EMOJI: dict[ViolationSeverity, str] = {
    ViolationSeverity.INFO: ":information_source:",
    ViolationSeverity.WARNING: ":warning:",
    ViolationSeverity.ERROR: ":x:",
    ViolationSeverity.CRITICAL: ":rotating_light:",
}


class SlackAlertPlugin(AlertChannelPlugin):
    """Slack incoming webhook alert channel using Block Kit."""

    def __init__(
        self,
        *,
        webhook_url: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._webhook_url = webhook_url
        self._timeout_seconds = timeout_seconds
        self._log = logger.bind(component="slack_alert")

    @property
    def name(self) -> str:
        return "slack"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if not self._webhook_url:
            errors.append("webhook_url is required")
        return errors

    async def send_alert(self, event: ContractViolationEvent) -> bool:
        payload = self._build_payload(event)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._webhook_url,
                    json=payload,
                    timeout=self._timeout_seconds,
                )
                if response.status_code >= 400:
                    self._log.warning(
                        "slack_http_error",
                        status_code=response.status_code,
                        contract_name=event.contract_name,
                    )
                    return False
                return True
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            self._log.warning("slack_connection_error", error=str(e))
            return False
        except Exception as e:
            self._log.error("slack_unexpected_error", error=str(e))
            return False

    def _build_payload(self, event: ContractViolationEvent) -> dict[str, Any]:
        emoji = SEVERITY_EMOJI.get(event.severity, ":grey_question:")
        header_text = f"{emoji} Contract Violation: {event.severity.value.upper()}"

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header_text},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Contract:*\n{event.contract_name}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Type:*\n{event.violation_type.value}",
                    },
                    {"type": "mrkdwn", "text": f"*Severity:*\n{event.severity.value}"},
                    {"type": "mrkdwn", "text": f"*Version:*\n{event.contract_version}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Message:*\n{event.message}"},
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Detected at: {event.timestamp.isoformat()}",
                    },
                ],
            },
        ]

        return {"blocks": blocks}

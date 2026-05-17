"""Slack alert channel plugin.

Sends contract violation alerts to Slack using Block Kit formatting
via incoming webhooks.

Tasks: T042 (Epic 3D)
Requirements: FR-026, FR-027
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
)
from floe_core.plugins.alert_channel import AlertChannelPlugin

from .tracing import TRACER_NAME, alert_span, get_tracer

logger = structlog.get_logger(__name__)

SEVERITY_EMOJI: dict[ViolationSeverity, str] = {
    ViolationSeverity.INFO: ":information_source:",
    ViolationSeverity.WARNING: ":warning:",
    ViolationSeverity.ERROR: ":x:",
    ViolationSeverity.CRITICAL: ":rotating_light:",
}


def _violation_id(event: ContractViolationEvent) -> str:
    return f"{event.contract_name}:{event.contract_version}:{event.violation_type.value}"


def _classify_status(status_code: int) -> str:
    if status_code in {401, 403}:
        return "access_denied"
    if status_code == 404:
        return "not_found"
    if status_code in {408, 429, 500, 502, 503, 504}:
        return "unavailable"
    if status_code == 400:
        return "validation"
    return "unknown"


def _classify_exception(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return "validation"
    if isinstance(exc, httpx.ConnectError | httpx.TimeoutException):
        return "unavailable"
    return "unknown"


def _record_alert_span(
    span: Any,
    *,
    destination_type: str,
    delivery_status: str,
    retry_count: int,
    started_at: float,
    violation_id: str | None = None,
    error_type: str | None = None,
) -> None:
    span.set_attribute("alert.destination_type", destination_type)
    span.set_attribute("alert.delivery_status", delivery_status)
    span.set_attribute("alert.retry_count", retry_count)
    span.set_attribute("alert.duration_ms", (time.perf_counter() - started_at) * 1000)
    if violation_id is not None:
        span.set_attribute("contract.violation_id", violation_id)
    if error_type is not None:
        span.set_attribute("alert.error_type", error_type)


class SlackAlertPlugin(AlertChannelPlugin):
    """Slack incoming webhook alert channel using Block Kit."""

    def __init__(
        self,
        *,
        webhook_url: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        super().__init__()
        self._webhook_url = webhook_url
        self._timeout_seconds = timeout_seconds
        self._log = logger.bind(component="slack_alert")
        self._tracer = get_tracer()

    @property
    def name(self) -> str:
        return "slack"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    @property
    def tracer_name(self) -> str:
        return TRACER_NAME

    def validate_config(self) -> list[str]:
        with alert_span(
            self._tracer,
            "validate_config",
            channel="slack",
        ) as span:
            started_at = time.perf_counter()
            errors: list[str] = []
            if not self._webhook_url:
                errors.append("webhook_url is required")
            _record_alert_span(
                span,
                destination_type="slack",
                delivery_status="validation_failed" if errors else "validated",
                retry_count=0,
                started_at=started_at,
                error_type="validation" if errors else None,
            )
            return errors

    async def send_alert(self, event: ContractViolationEvent) -> bool:
        with alert_span(
            self._tracer,
            "send",
            channel="slack",
            destination="webhook",
        ) as span:
            started_at = time.perf_counter()
            violation_id = _violation_id(event)
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
                        _record_alert_span(
                            span,
                            destination_type="slack",
                            delivery_status="failed",
                            retry_count=0,
                            started_at=started_at,
                            violation_id=violation_id,
                            error_type=_classify_status(response.status_code),
                        )
                        return False
                    _record_alert_span(
                        span,
                        destination_type="slack",
                        delivery_status="delivered",
                        retry_count=0,
                        started_at=started_at,
                        violation_id=violation_id,
                    )
                    return True
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                self._log.warning("slack_connection_error", error=str(e))
                _record_alert_span(
                    span,
                    destination_type="slack",
                    delivery_status="failed",
                    retry_count=0,
                    started_at=started_at,
                    violation_id=violation_id,
                    error_type=_classify_exception(e),
                )
                return False
            except Exception as e:
                self._log.error("slack_unexpected_error", error=str(e))
                _record_alert_span(
                    span,
                    destination_type="slack",
                    delivery_status="failed",
                    retry_count=0,
                    started_at=started_at,
                    violation_id=violation_id,
                    error_type=_classify_exception(e),
                )
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

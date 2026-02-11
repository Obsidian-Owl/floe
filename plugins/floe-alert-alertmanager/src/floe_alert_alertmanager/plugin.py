"""Alertmanager alert channel plugin.

Sends contract violation alerts to Prometheus Alertmanager via its HTTP API.

Tasks: T044 (Epic 3D)
Requirements: FR-026, FR-027
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from floe_core.contracts.monitoring.violations import ContractViolationEvent
from floe_core.plugins.alert_channel import AlertChannelPlugin

from floe_alert_alertmanager.tracing import (
    ATTR_DELIVERY_STATUS,
    TRACER_NAME,
    alert_span,
    get_tracer,
)

logger = structlog.get_logger(__name__)


class AlertmanagerPlugin(AlertChannelPlugin):
    """Prometheus Alertmanager alert channel via /api/v2/alerts."""

    def __init__(
        self,
        *,
        api_url: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._log = logger.bind(component="alertmanager_alert")

    @property
    def name(self) -> str:
        return "alertmanager"

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
        tracer = get_tracer()
        with alert_span(
            tracer,
            "validate_config",
            channel="alertmanager",
            destination=self._api_url,
        ):
            errors: list[str] = []
            if not self._api_url:
                errors.append("api_url is required")
            return errors

    async def send_alert(self, event: ContractViolationEvent) -> bool:
        tracer = get_tracer()
        with alert_span(
            tracer,
            "send_alert",
            channel="alertmanager",
            destination=self._api_url,
            severity=event.severity.value,
        ) as span:
            alerts = self._build_alerts(event)
            url = f"{self._api_url}/api/v2/alerts"
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        json=alerts,
                        timeout=self._timeout_seconds,
                    )
                    if response.status_code >= 400:
                        self._log.warning(
                            "alertmanager_http_error",
                            status_code=response.status_code,
                            contract_name=event.contract_name,
                        )
                        span.set_attribute(ATTR_DELIVERY_STATUS, "failed")
                        return False
                    span.set_attribute(ATTR_DELIVERY_STATUS, "delivered")
                    return True
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                self._log.warning("alertmanager_connection_error", error=str(e))
                span.set_attribute(ATTR_DELIVERY_STATUS, "failed")
                return False
            except Exception as e:
                self._log.error("alertmanager_unexpected_error", error=str(e))
                span.set_attribute(ATTR_DELIVERY_STATUS, "failed")
                return False

    def _build_alerts(self, event: ContractViolationEvent) -> list[dict[str, Any]]:
        return [
            {
                "labels": {
                    "alertname": "ContractViolation",
                    "severity": event.severity.value,
                    "contract": event.contract_name,
                    "contract_version": event.contract_version,
                    "violation_type": event.violation_type.value,
                },
                "annotations": {
                    "summary": event.message,
                    "description": (
                        f"Contract {event.contract_name} v{event.contract_version} "
                        f"has a {event.violation_type.value} violation "
                        f"(severity: {event.severity.value})"
                    ),
                },
                "startsAt": event.timestamp.isoformat(),
            }
        ]

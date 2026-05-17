"""Alertmanager alert channel plugin.

Sends contract violation alerts to Prometheus Alertmanager via its HTTP API.

Tasks: T044 (Epic 3D)
Requirements: FR-026, FR-027
"""

from __future__ import annotations

import time
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
    span.set_attribute(ATTR_DELIVERY_STATUS, delivery_status)
    span.set_attribute("alert.retry_count", retry_count)
    span.set_attribute("alert.duration_ms", (time.perf_counter() - started_at) * 1000)
    if violation_id is not None:
        span.set_attribute("contract.violation_id", violation_id)
    if error_type is not None:
        span.set_attribute("alert.error_type", error_type)


class AlertmanagerPlugin(AlertChannelPlugin):
    """Prometheus Alertmanager alert channel via /api/v2/alerts."""

    def __init__(
        self,
        *,
        api_url: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        super().__init__()
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
            destination="alertmanager",
        ) as span:
            started_at = time.perf_counter()
            errors: list[str] = []
            if not self._api_url:
                errors.append("api_url is required")
            _record_alert_span(
                span,
                destination_type="alertmanager",
                delivery_status="validation_failed" if errors else "validated",
                retry_count=0,
                started_at=started_at,
                error_type="validation" if errors else None,
            )
            return errors

    async def send_alert(self, event: ContractViolationEvent) -> bool:
        tracer = get_tracer()
        with alert_span(
            tracer,
            "send_alert",
            channel="alertmanager",
            destination="alertmanager",
            severity=event.severity.value,
        ) as span:
            started_at = time.perf_counter()
            violation_id = _violation_id(event)
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
                        _record_alert_span(
                            span,
                            destination_type="alertmanager",
                            delivery_status="failed",
                            retry_count=0,
                            started_at=started_at,
                            violation_id=violation_id,
                            error_type=_classify_status(response.status_code),
                        )
                        return False
                    _record_alert_span(
                        span,
                        destination_type="alertmanager",
                        delivery_status="delivered",
                        retry_count=0,
                        started_at=started_at,
                        violation_id=violation_id,
                    )
                    return True
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                self._log.warning("alertmanager_connection_error", error=str(e))
                _record_alert_span(
                    span,
                    destination_type="alertmanager",
                    delivery_status="failed",
                    retry_count=0,
                    started_at=started_at,
                    violation_id=violation_id,
                    error_type=_classify_exception(e),
                )
                return False
            except Exception as e:
                self._log.error("alertmanager_unexpected_error", error=str(e))
                _record_alert_span(
                    span,
                    destination_type="alertmanager",
                    delivery_status="failed",
                    retry_count=0,
                    started_at=started_at,
                    violation_id=violation_id,
                    error_type=_classify_exception(e),
                )
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

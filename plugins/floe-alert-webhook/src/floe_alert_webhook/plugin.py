"""CloudEvents webhook alert channel plugin.

Sends contract violation alerts as CloudEvents v1.0 structured-mode HTTP POST
requests to a configurable webhook URL.

Tasks: T041 (Epic 3D)
Requirements: FR-026, FR-027
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
import structlog
from floe_core.contracts.monitoring.violations import ContractViolationEvent
from floe_core.plugins.alert_channel import AlertChannelPlugin

from .tracing import TRACER_NAME, alert_span, get_tracer

logger = structlog.get_logger(__name__)

CLOUDEVENTS_CONTENT_TYPE = "application/cloudevents+json"


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


def _safe_exception_summary(exc: Exception) -> str:
    """Return a secret-free delivery failure summary for logs."""
    return f"delivery failed ({_classify_exception(exc)})"


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


class WebhookAlertPlugin(AlertChannelPlugin):
    """CloudEvents v1.0 webhook alert channel.

    Sends violation events as CloudEvents structured-mode HTTP POST.

    Configuration:
        webhook_url: Target URL for POST requests (required)
        timeout_seconds: HTTP request timeout (default 10)
    """

    def __init__(
        self,
        *,
        webhook_url: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        """Initialize webhook alert channel.

        Args:
            webhook_url: Target URL for POST requests (required).
            timeout_seconds: HTTP request timeout in seconds (default 10).
        """
        super().__init__()
        self._webhook_url = webhook_url
        self._timeout_seconds = timeout_seconds
        self._log = logger.bind(component="webhook_alert")
        self._tracer = get_tracer()

    @property
    def name(self) -> str:
        """Return plugin name."""
        return "webhook"

    @property
    def version(self) -> str:
        """Return plugin version (semver)."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Return floe API version this plugin implements."""
        return "1.0"

    @property
    def tracer_name(self) -> str:
        """Return OpenTelemetry tracer name."""
        return TRACER_NAME

    def validate_config(self) -> list[str]:
        """Validate webhook configuration.

        Returns:
            List of validation error messages. Empty list means valid.
        """
        with alert_span(
            self._tracer,
            "validate_config",
            channel="webhook",
        ) as span:
            started_at = time.perf_counter()
            errors: list[str] = []
            if not self._webhook_url:
                errors.append("webhook_url is required")
            _record_alert_span(
                span,
                destination_type="webhook",
                delivery_status="validation_failed" if errors else "validated",
                retry_count=0,
                started_at=started_at,
                error_type="validation" if errors else None,
            )
            return errors

    async def send_alert(self, event: ContractViolationEvent) -> bool:
        """Send violation as CloudEvents v1.0 structured-mode POST.

        Args:
            event: Contract violation event to send.

        Returns:
            True if delivery succeeded, False otherwise.
        """
        with alert_span(
            self._tracer,
            "send",
            channel="webhook",
            destination="webhook",
        ) as span:
            started_at = time.perf_counter()
            violation_id = _violation_id(event)
            cloudevent = self._build_cloudevent(event)

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self._webhook_url,
                        json=cloudevent,
                        headers={"Content-Type": CLOUDEVENTS_CONTENT_TYPE},
                        timeout=self._timeout_seconds,
                    )

                    if response.status_code >= 400:
                        self._log.warning(
                            "webhook_http_error",
                            status_code=response.status_code,
                            contract_name=event.contract_name,
                        )
                        _record_alert_span(
                            span,
                            destination_type="webhook",
                            delivery_status="failed",
                            retry_count=0,
                            started_at=started_at,
                            violation_id=violation_id,
                            error_type=_classify_status(response.status_code),
                        )
                        return False

                    _record_alert_span(
                        span,
                        destination_type="webhook",
                        delivery_status="delivered",
                        retry_count=0,
                        started_at=started_at,
                        violation_id=violation_id,
                    )
                    return True

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                self._log.warning(
                    "webhook_connection_error",
                    error_type=_classify_exception(e),
                    error_message=_safe_exception_summary(e),
                    contract_name=event.contract_name,
                )
                _record_alert_span(
                    span,
                    destination_type="webhook",
                    delivery_status="failed",
                    retry_count=0,
                    started_at=started_at,
                    violation_id=violation_id,
                    error_type=_classify_exception(e),
                )
                return False
            except Exception as e:
                self._log.error(
                    "webhook_unexpected_error",
                    error_type=_classify_exception(e),
                    error_message=_safe_exception_summary(e),
                    contract_name=event.contract_name,
                )
                _record_alert_span(
                    span,
                    destination_type="webhook",
                    delivery_status="failed",
                    retry_count=0,
                    started_at=started_at,
                    violation_id=violation_id,
                    error_type=_classify_exception(e),
                )
                return False

    def _build_cloudevent(self, event: ContractViolationEvent) -> dict[str, Any]:
        """Build CloudEvents v1.0 structured-mode envelope.

        Args:
            event: Contract violation event to wrap.

        Returns:
            CloudEvents v1.0 formatted dictionary.
        """
        return {
            "specversion": "1.0",
            "type": "com.floe.contract.violation",
            "source": "/floe/contract-monitor",
            "id": str(uuid.uuid4()),
            "time": event.timestamp.isoformat(),
            "datacontenttype": "application/json",
            "data": {
                "contract_name": event.contract_name,
                "contract_version": event.contract_version,
                "violation_type": event.violation_type.value,
                "severity": event.severity.value,
                "message": event.message,
                "element": event.element,
                "expected_value": event.expected_value,
                "actual_value": event.actual_value,
                "timestamp": event.timestamp.isoformat(),
                "check_duration_seconds": event.check_duration_seconds,
                "metadata": event.metadata,
            },
        }

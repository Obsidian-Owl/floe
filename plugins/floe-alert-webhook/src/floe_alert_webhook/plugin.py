"""CloudEvents webhook alert channel plugin.

Sends contract violation alerts as CloudEvents v1.0 structured-mode HTTP POST
requests to a configurable webhook URL.

Tasks: T041 (Epic 3D)
Requirements: FR-026, FR-027
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import structlog
from floe_core.contracts.monitoring.violations import ContractViolationEvent
from floe_core.plugins.alert_channel import AlertChannelPlugin

logger = structlog.get_logger(__name__)

CLOUDEVENTS_CONTENT_TYPE = "application/cloudevents+json"


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
        self._webhook_url = webhook_url
        self._timeout_seconds = timeout_seconds
        self._log = logger.bind(component="webhook_alert")

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

    def validate_config(self) -> list[str]:
        """Validate webhook configuration.

        Returns:
            List of validation error messages. Empty list means valid.
        """
        errors: list[str] = []
        if not self._webhook_url:
            errors.append("webhook_url is required")
        return errors

    async def send_alert(self, event: ContractViolationEvent) -> bool:
        """Send violation as CloudEvents v1.0 structured-mode POST.

        Args:
            event: Contract violation event to send.

        Returns:
            True if delivery succeeded, False otherwise.
        """
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
                    return False

                return True

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            self._log.warning(
                "webhook_connection_error",
                error=str(e),
                contract_name=event.contract_name,
            )
            return False
        except Exception as e:
            self._log.error(
                "webhook_unexpected_error",
                error=str(e),
                contract_name=event.contract_name,
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

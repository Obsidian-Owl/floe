"""Webhook notification module for promotion lifecycle events (T113).

Task ID: T113
Phase: 11 - Webhooks (US9)
User Story: US9 - Webhook Notifications
Requirements: FR-040, FR-041, FR-042, FR-043

This module implements webhook notifications for promotion events:
- FR-040: Webhook configuration from WebhookConfig
- FR-041: Event type filtering (promote, rollback, lock, unlock)
- FR-042: HTTP delivery with configurable retry
- FR-043: Structured JSON payload formatting

Example:
    >>> from floe_core.oci.webhooks import WebhookNotifier
    >>> from floe_core.schemas.promotion import WebhookConfig
    >>> config = WebhookConfig(
    ...     url="https://hooks.example.com/webhook",
    ...     events=["promote", "rollback"],
    ... )
    >>> notifier = WebhookNotifier(config=config)
    >>> result = await notifier.notify("promote", {"artifact_tag": "v1.0.0"})
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field

from floe_core.schemas.promotion import WebhookConfig

# Exponential backoff configuration
BACKOFF_BASE_SECONDS = 1.0
"""Base delay for exponential backoff (doubles each retry)."""

logger = structlog.get_logger(__name__)


class WebhookNotificationResult(BaseModel):
    """Result of a webhook notification attempt.

    Captures success/failure state, HTTP response details, and retry information.

    Attributes:
        success: Whether the notification was delivered successfully.
        status_code: HTTP response status code (if response received).
        url: Target webhook URL.
        error: Error message if notification failed.
        attempts: Number of delivery attempts made.

    Examples:
        >>> result = WebhookNotificationResult(
        ...     success=True,
        ...     status_code=200,
        ...     url="https://example.com/webhook",
        ... )
        >>> result.success
        True
    """

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(
        ...,
        description="Whether notification delivered successfully",
    )
    status_code: int | None = Field(
        default=None,
        description="HTTP response status code",
    )
    url: str = Field(
        ...,
        description="Target webhook URL",
    )
    error: str | None = Field(
        default=None,
        description="Error message if failed",
    )
    attempts: int = Field(
        default=1,
        ge=1,
        description="Number of delivery attempts",
    )


class WebhookNotifier:
    """Webhook notifier for promotion lifecycle events.

    Sends HTTP POST notifications to configured webhook endpoints when
    promotion events occur. Supports event filtering, custom headers,
    configurable timeout, and retry logic.

    Attributes:
        config: Single WebhookConfig (when initialized with config=).
        configs: List of WebhookConfigs (when initialized with configs=).

    Examples:
        >>> config = WebhookConfig(
        ...     url="https://hooks.slack.com/services/...",
        ...     events=["promote", "rollback"],
        ...     headers={"Authorization": "Bearer token"},
        ... )
        >>> notifier = WebhookNotifier(config=config)
        >>> notifier.should_notify("promote")
        True
        >>> notifier.should_notify("lock")
        False
    """

    def __init__(
        self,
        config: WebhookConfig | None = None,
        configs: list[WebhookConfig] | None = None,
    ) -> None:
        """Initialize WebhookNotifier with configuration.

        Args:
            config: Single webhook configuration.
            configs: Multiple webhook configurations.

        Raises:
            ValueError: If neither config nor configs provided.
        """
        if config is not None:
            self.config = config
            self.configs = [config]
        elif configs is not None:
            self.configs = configs
            self.config = configs[0] if configs else None
        else:
            raise ValueError("Must provide either config or configs")

    def should_notify(self, event_type: str) -> bool:
        """Check if event type should trigger notification.

        Implements FR-041 event filtering based on configuration.

        Args:
            event_type: Event type to check (promote, rollback, lock, unlock).

        Returns:
            True if event type is in config.events, False otherwise.
        """
        if self.config is None:
            return False
        return event_type in self.config.events

    def build_payload(
        self,
        event_type: str,
        event_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Build webhook payload from event data.

        Implements FR-043 payload formatting.

        Args:
            event_type: Type of event (promote, rollback, lock, unlock).
            event_data: Event-specific data to include.

        Returns:
            Formatted payload dictionary with event_type and event data.
        """
        payload = {
            "event_type": event_type,
            **event_data,
        }
        return payload

    async def notify(
        self,
        event_type: str,
        event_data: dict[str, Any],
    ) -> WebhookNotificationResult:
        """Send webhook notification for an event.

        Implements FR-042 HTTP delivery with retry logic.

        Args:
            event_type: Type of event (promote, rollback, lock, unlock).
            event_data: Event-specific data to include in payload.

        Returns:
            WebhookNotificationResult with delivery status.
        """
        if self.config is None:
            return WebhookNotificationResult(
                success=False,
                url="",
                error="No webhook configuration",
            )

        url = self.config.url
        timeout = self.config.timeout_seconds
        retry_count = self.config.retry_count
        headers = self.config.headers or {}

        payload = self.build_payload(event_type, event_data)

        # Retry loop: 1 initial + retry_count retries
        max_attempts = 1 + retry_count
        last_status_code: int | None = None
        last_error: str | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        url=url,
                        json=payload,
                        headers=headers,
                    )

                    last_status_code = response.status_code

                    if response.status_code < 400:
                        logger.info(
                            "webhook_notification_sent",
                            url=url,
                            event_type=event_type,
                            status_code=response.status_code,
                            attempts=attempt,
                        )
                        return WebhookNotificationResult(
                            success=True,
                            status_code=response.status_code,
                            url=url,
                            attempts=attempt,
                        )

                    # Server error - retry with exponential backoff
                    if response.status_code >= 500:
                        last_error = f"Server error: {response.status_code}"
                        if attempt < max_attempts:
                            # Exponential backoff: 1s, 2s, 4s, ...
                            backoff_delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                            logger.warning(
                                "webhook_notification_retry",
                                url=url,
                                event_type=event_type,
                                status_code=response.status_code,
                                attempt=attempt,
                                max_attempts=max_attempts,
                                backoff_seconds=backoff_delay,
                            )
                            await asyncio.sleep(backoff_delay)
                        continue

                    # Client error - don't retry
                    last_error = f"Client error: {response.status_code}"
                    break

            except httpx.TimeoutException:
                last_error = "Request timed out"
                if attempt < max_attempts:
                    backoff_delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "webhook_notification_timeout",
                        url=url,
                        event_type=event_type,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        backoff_seconds=backoff_delay,
                    )
                    await asyncio.sleep(backoff_delay)
                else:
                    logger.warning(
                        "webhook_notification_timeout",
                        url=url,
                        event_type=event_type,
                        attempt=attempt,
                        max_attempts=max_attempts,
                    )
            except httpx.RequestError as e:
                last_error = str(e)
                if attempt < max_attempts:
                    backoff_delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "webhook_notification_error",
                        url=url,
                        event_type=event_type,
                        error=str(e),
                        attempt=attempt,
                        max_attempts=max_attempts,
                        backoff_seconds=backoff_delay,
                    )
                    await asyncio.sleep(backoff_delay)
                else:
                    logger.warning(
                        "webhook_notification_error",
                        url=url,
                        event_type=event_type,
                        error=str(e),
                        attempt=attempt,
                        max_attempts=max_attempts,
                    )

        # All attempts failed
        logger.error(
            "webhook_notification_failed",
            url=url,
            event_type=event_type,
            status_code=last_status_code,
            error=last_error,
            attempts=max_attempts,
        )
        return WebhookNotificationResult(
            success=False,
            status_code=last_status_code,
            url=url,
            error=last_error,
            attempts=max_attempts,
        )


__all__: list[str] = [
    "WebhookNotificationResult",
    "WebhookNotifier",
]

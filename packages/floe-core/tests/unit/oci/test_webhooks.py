"""Unit tests for WebhookNotifier (T112).

Task ID: T112
Phase: 11 - Webhooks (US9)
User Story: US9 - Webhook Notifications
Requirements: FR-040, FR-041, FR-042, FR-043

These tests validate webhook notification functionality:
- FR-040: Webhook configuration
- FR-041: Event type filtering
- FR-042: HTTP delivery with retry
- FR-043: Payload formatting

TDD: Tests written FIRST (T112), implementation follows in T113.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


@pytest.fixture
def webhook_config() -> MagicMock:
    """Create a mock WebhookConfig."""
    from floe_core.schemas.promotion import WebhookConfig

    return WebhookConfig(
        url="https://hooks.example.com/webhook",
        events=["promote", "rollback"],
        headers={"Authorization": "Bearer test-token"},
        timeout_seconds=30,
        retry_count=3,
    )


@pytest.fixture
def promotion_event() -> dict:
    """Create a sample promotion event payload."""
    return {
        "event_type": "promote",
        "artifact_tag": "v1.0.0",
        "artifact_digest": "sha256:abc123",
        "source_environment": "dev",
        "target_environment": "staging",
        "operator": "ci@example.com",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class TestWebhookNotifierCreation:
    """Tests for WebhookNotifier instantiation (FR-040)."""

    @pytest.mark.requirement("FR-040")
    def test_create_notifier_with_config(self, webhook_config: MagicMock) -> None:
        """WebhookNotifier can be created with WebhookConfig."""
        from floe_core.oci.webhooks import WebhookNotifier

        notifier = WebhookNotifier(config=webhook_config)

        assert notifier.config == webhook_config
        assert notifier.config.url == "https://hooks.example.com/webhook"

    @pytest.mark.requirement("FR-040")
    def test_create_notifier_with_multiple_configs(self) -> None:
        """WebhookNotifier can be created with multiple WebhookConfigs."""
        from floe_core.oci.webhooks import WebhookNotifier
        from floe_core.schemas.promotion import WebhookConfig

        configs = [
            WebhookConfig(
                url="https://slack.example.com/webhook",
                events=["promote"],
            ),
            WebhookConfig(
                url="https://pagerduty.example.com/webhook",
                events=["rollback"],
            ),
        ]

        notifier = WebhookNotifier(configs=configs)

        assert len(notifier.configs) == 2


class TestWebhookEventFiltering:
    """Tests for event type filtering (FR-041)."""

    @pytest.mark.requirement("FR-041")
    def test_notifier_filters_events_by_config(
        self, webhook_config: MagicMock
    ) -> None:
        """WebhookNotifier only sends events matching config.events."""
        from floe_core.oci.webhooks import WebhookNotifier

        notifier = WebhookNotifier(config=webhook_config)

        # promote is in config.events
        assert notifier.should_notify("promote") is True
        # rollback is in config.events
        assert notifier.should_notify("rollback") is True
        # lock is NOT in config.events
        assert notifier.should_notify("lock") is False
        # unlock is NOT in config.events
        assert notifier.should_notify("unlock") is False

    @pytest.mark.requirement("FR-041")
    def test_notifier_accepts_all_valid_event_types(self) -> None:
        """WebhookNotifier accepts all valid event types when configured."""
        from floe_core.oci.webhooks import WebhookNotifier
        from floe_core.schemas.promotion import WebhookConfig

        config = WebhookConfig(
            url="https://example.com/webhook",
            events=["promote", "rollback", "lock", "unlock"],
        )
        notifier = WebhookNotifier(config=config)

        assert notifier.should_notify("promote") is True
        assert notifier.should_notify("rollback") is True
        assert notifier.should_notify("lock") is True
        assert notifier.should_notify("unlock") is True


class TestWebhookDelivery:
    """Tests for webhook HTTP delivery (FR-042)."""

    @pytest.mark.requirement("FR-042")
    @pytest.mark.anyio
    async def test_notify_sends_http_post(
        self, webhook_config: MagicMock, promotion_event: dict
    ) -> None:
        """WebhookNotifier sends HTTP POST to configured URL."""
        from floe_core.oci.webhooks import WebhookNotifier

        notifier = WebhookNotifier(config=webhook_config)

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            result = await notifier.notify("promote", promotion_event)

            assert result.success is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args.kwargs["url"] == "https://hooks.example.com/webhook"

    @pytest.mark.requirement("FR-042")
    @pytest.mark.anyio
    async def test_notify_includes_headers(
        self, webhook_config: MagicMock, promotion_event: dict
    ) -> None:
        """WebhookNotifier includes configured headers."""
        from floe_core.oci.webhooks import WebhookNotifier

        notifier = WebhookNotifier(config=webhook_config)

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            await notifier.notify("promote", promotion_event)

            call_args = mock_post.call_args
            headers = call_args.kwargs.get("headers", {})
            assert "Authorization" in headers

    @pytest.mark.requirement("FR-042")
    @pytest.mark.anyio
    async def test_notify_retries_on_failure(
        self, webhook_config: MagicMock, promotion_event: dict
    ) -> None:
        """WebhookNotifier retries on HTTP errors."""
        from floe_core.oci.webhooks import WebhookNotifier

        notifier = WebhookNotifier(config=webhook_config)

        with patch("httpx.AsyncClient.post") as mock_post:
            # First 2 calls fail, third succeeds
            mock_post.side_effect = [
                MagicMock(status_code=500),
                MagicMock(status_code=503),
                MagicMock(status_code=200),
            ]

            result = await notifier.notify("promote", promotion_event)

            assert result.success is True
            assert mock_post.call_count == 3

    @pytest.mark.requirement("FR-042")
    @pytest.mark.anyio
    async def test_notify_returns_failure_after_max_retries(
        self, webhook_config: MagicMock, promotion_event: dict
    ) -> None:
        """WebhookNotifier returns failure after max retries."""
        from floe_core.oci.webhooks import WebhookNotifier

        notifier = WebhookNotifier(config=webhook_config)

        with patch("httpx.AsyncClient.post") as mock_post:
            # All calls fail (retry_count=3, so 4 total attempts)
            mock_post.return_value = MagicMock(status_code=500)

            result = await notifier.notify("promote", promotion_event)

            assert result.success is False
            assert mock_post.call_count == 4  # 1 initial + 3 retries

    @pytest.mark.requirement("FR-042")
    @pytest.mark.anyio
    async def test_notify_uses_exponential_backoff(
        self, webhook_config: MagicMock, promotion_event: dict
    ) -> None:
        """WebhookNotifier uses exponential backoff between retries."""
        from floe_core.oci.webhooks import WebhookNotifier

        notifier = WebhookNotifier(config=webhook_config)

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            # All calls fail to trigger retries
            mock_post.return_value = MagicMock(status_code=500)

            await notifier.notify("promote", promotion_event)

            # Should have 3 sleeps (before each retry, not before initial)
            assert mock_sleep.call_count == 3

            # Verify exponential backoff delays: 1s, 2s, 4s (base=1, 2^0, 2^1, 2^2)
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert sleep_calls[0] == 1.0  # 1 * 2^0 = 1
            assert sleep_calls[1] == 2.0  # 1 * 2^1 = 2
            assert sleep_calls[2] == 4.0  # 1 * 2^2 = 4


class TestWebhookPayload:
    """Tests for webhook payload formatting (FR-043)."""

    @pytest.mark.requirement("FR-043")
    @pytest.mark.anyio
    async def test_payload_includes_event_type(
        self, webhook_config: MagicMock, promotion_event: dict
    ) -> None:
        """Webhook payload includes event_type field."""
        from floe_core.oci.webhooks import WebhookNotifier

        notifier = WebhookNotifier(config=webhook_config)

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            await notifier.notify("promote", promotion_event)

            call_args = mock_post.call_args
            payload = call_args.kwargs.get("json", {})
            assert payload.get("event_type") == "promote"

    @pytest.mark.requirement("FR-043")
    @pytest.mark.anyio
    async def test_payload_includes_artifact_info(
        self, webhook_config: MagicMock, promotion_event: dict
    ) -> None:
        """Webhook payload includes artifact information."""
        from floe_core.oci.webhooks import WebhookNotifier

        notifier = WebhookNotifier(config=webhook_config)

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            await notifier.notify("promote", promotion_event)

            call_args = mock_post.call_args
            payload = call_args.kwargs.get("json", {})
            assert "artifact_tag" in payload
            assert "artifact_digest" in payload


class TestWebhookNotificationResult:
    """Tests for WebhookNotificationResult (FR-042)."""

    @pytest.mark.requirement("FR-042")
    def test_notification_result_success(self) -> None:
        """WebhookNotificationResult captures success state."""
        from floe_core.oci.webhooks import WebhookNotificationResult

        result = WebhookNotificationResult(
            success=True,
            status_code=200,
            url="https://example.com/webhook",
        )

        assert result.success is True
        assert result.status_code == 200

    @pytest.mark.requirement("FR-042")
    def test_notification_result_failure(self) -> None:
        """WebhookNotificationResult captures failure state."""
        from floe_core.oci.webhooks import WebhookNotificationResult

        result = WebhookNotificationResult(
            success=False,
            status_code=500,
            url="https://example.com/webhook",
            error="Internal Server Error",
            attempts=4,
        )

        assert result.success is False
        assert result.error == "Internal Server Error"
        assert result.attempts == 4


__all__: list[str] = [
    "TestWebhookNotifierCreation",
    "TestWebhookEventFiltering",
    "TestWebhookDelivery",
    "TestWebhookPayload",
    "TestWebhookNotificationResult",
]

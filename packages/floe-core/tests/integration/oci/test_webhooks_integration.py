"""Integration tests for WebhookNotifier with mock HTTP transport (T116).

Task ID: T116
Phase: 11 - Webhooks (US9)
User Story: US9 - Webhook Notifications
Requirements: FR-040, FR-041, FR-042, FR-043

These tests validate HTTP webhook delivery using httpx mocking:
- FR-040: Webhook configuration
- FR-041: Event type filtering
- FR-042: HTTP delivery with retry
- FR-043: Payload formatting

Uses unittest.mock to simulate HTTP responses for integration testing.
TDD: Tests written FIRST (T116), implementation already exists from T113.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from floe_core.oci.webhooks import WebhookNotifier
from floe_core.schemas.promotion import WebhookConfig


class TestWebhookIntegration:
    """Integration tests for WebhookNotifier with HTTP transport mocking."""

    @pytest.mark.requirement("FR-042")
    @pytest.mark.anyio
    async def test_webhook_delivers_payload_successfully(
        self,
    ) -> None:
        """Webhook successfully delivers payload via HTTP POST."""
        config = WebhookConfig(
            url="https://hooks.example.com/webhook",
            events=["promote"],
            timeout_seconds=10,
            retry_count=0,
        )
        notifier = WebhookNotifier(config=config)

        event_data = {
            "artifact_tag": "v1.0.0",
            "artifact_digest": "sha256:abc123",
            "target_environment": "staging",
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = httpx.Response(200)

            result = await notifier.notify("promote", event_data)

            assert result.success is True
            assert result.status_code == 200
            mock_post.assert_called_once()

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["url"] == "https://hooks.example.com/webhook"
            assert call_kwargs["json"]["event_type"] == "promote"
            assert call_kwargs["json"]["artifact_tag"] == "v1.0.0"

    @pytest.mark.requirement("FR-043")
    @pytest.mark.anyio
    async def test_webhook_payload_contains_required_fields(
        self,
    ) -> None:
        """Webhook payload contains required fields per FR-043."""
        config = WebhookConfig(
            url="https://hooks.example.com/webhook",
            events=["promote", "rollback"],
        )
        notifier = WebhookNotifier(config=config)

        event_data = {
            "artifact_tag": "v2.0.0",
            "artifact_digest": "sha256:def456",
            "source_environment": "dev",
            "target_environment": "staging",
            "operator": "ci@example.com",
            "timestamp": "2026-01-30T10:00:00Z",
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = httpx.Response(200)

            await notifier.notify("promote", event_data)

            payload = mock_post.call_args.kwargs["json"]

            # Required fields per FR-043
            assert "event_type" in payload
            assert "artifact_tag" in payload
            assert "artifact_digest" in payload
            assert payload["event_type"] == "promote"
            assert payload["artifact_tag"] == "v2.0.0"
            assert payload["operator"] == "ci@example.com"

    @pytest.mark.requirement("FR-040")
    @pytest.mark.anyio
    async def test_webhook_includes_custom_headers(
        self,
    ) -> None:
        """Webhook request includes custom headers from config."""
        config = WebhookConfig(
            url="https://hooks.example.com/webhook",
            events=["promote"],
            headers={
                "Authorization": "Bearer test-token",
                "X-Custom-Header": "custom-value",
            },
        )
        notifier = WebhookNotifier(config=config)

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = httpx.Response(200)

            await notifier.notify("promote", {"artifact_tag": "v1.0.0"})

            headers = mock_post.call_args.kwargs["headers"]
            assert headers.get("Authorization") == "Bearer test-token"
            assert headers.get("X-Custom-Header") == "custom-value"

    @pytest.mark.requirement("FR-042")
    @pytest.mark.anyio
    async def test_webhook_retries_on_server_error(
        self,
    ) -> None:
        """Webhook retries delivery on server error (5xx)."""
        config = WebhookConfig(
            url="https://hooks.example.com/webhook",
            events=["promote"],
            retry_count=2,
        )
        notifier = WebhookNotifier(config=config)

        with patch("httpx.AsyncClient.post") as mock_post:
            # First call returns 500, second returns 200
            mock_post.side_effect = [
                httpx.Response(500),
                httpx.Response(200),
            ]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await notifier.notify("promote", {"artifact_tag": "v1.0.0"})

            assert result.success is True
            assert mock_post.call_count == 2

    @pytest.mark.requirement("FR-042")
    @pytest.mark.anyio
    async def test_webhook_fails_after_max_retries(
        self,
    ) -> None:
        """Webhook fails after exhausting retries."""
        config = WebhookConfig(
            url="https://hooks.example.com/webhook",
            events=["promote"],
            retry_count=2,
        )
        notifier = WebhookNotifier(config=config)

        with patch("httpx.AsyncClient.post") as mock_post:
            # All calls fail with 500
            mock_post.return_value = httpx.Response(500)

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await notifier.notify("promote", {"artifact_tag": "v1.0.0"})

            assert result.success is False
            assert result.status_code == 500
            assert result.attempts == 3  # 1 initial + 2 retries

    @pytest.mark.requirement("FR-041")
    @pytest.mark.anyio
    async def test_webhook_filters_non_subscribed_events(
        self,
    ) -> None:
        """Webhook does not send unsubscribed event types."""
        config = WebhookConfig(
            url="https://hooks.example.com/webhook",
            events=["rollback"],  # Only subscribed to rollback
        )
        notifier = WebhookNotifier(config=config)

        # should_notify should return False for promote
        assert notifier.should_notify("promote") is False
        assert notifier.should_notify("rollback") is True
        assert notifier.should_notify("lock") is False
        assert notifier.should_notify("unlock") is False

    @pytest.mark.requirement("FR-042")
    @pytest.mark.anyio
    async def test_webhook_handles_timeout(
        self,
    ) -> None:
        """Webhook handles timeout and retries."""
        config = WebhookConfig(
            url="https://hooks.example.com/webhook",
            events=["promote"],
            timeout_seconds=5,
            retry_count=1,
        )
        notifier = WebhookNotifier(config=config)

        with patch("httpx.AsyncClient.post") as mock_post:
            # First call times out, second succeeds
            mock_post.side_effect = [
                httpx.TimeoutException("Request timed out"),
                httpx.Response(200),
            ]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await notifier.notify("promote", {"artifact_tag": "v1.0.0"})

            assert result.success is True
            assert mock_post.call_count == 2

    @pytest.mark.requirement("FR-042")
    @pytest.mark.anyio
    async def test_webhook_handles_connection_error(
        self,
    ) -> None:
        """Webhook handles connection error and retries."""
        config = WebhookConfig(
            url="https://hooks.example.com/webhook",
            events=["promote"],
            retry_count=1,
        )
        notifier = WebhookNotifier(config=config)

        with patch("httpx.AsyncClient.post") as mock_post:
            # First call fails with connection error, second succeeds
            mock_post.side_effect = [
                httpx.ConnectError("Connection refused"),
                httpx.Response(200),
            ]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await notifier.notify("promote", {"artifact_tag": "v1.0.0"})

            assert result.success is True
            assert mock_post.call_count == 2


__all__: list[str] = [
    "TestWebhookIntegration",
]

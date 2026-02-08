"""Unit tests for WebhookAlertPlugin.

Tests the CloudEvents v1.0 webhook alert channel plugin, verifying:
- Plugin metadata (name, version, floe_api_version)
- Configuration validation
- CloudEvents v1.0 format compliance
- HTTP delivery success and error handling
- Connection and timeout error handling

Tasks: T037 (Epic 3D)
Requirements: FR-026
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)

from floe_alert_webhook.plugin import CLOUDEVENTS_CONTENT_TYPE, WebhookAlertPlugin


def _make_event(
    *,
    contract_name: str = "orders_v1",
    severity: ViolationSeverity = ViolationSeverity.ERROR,
) -> ContractViolationEvent:
    """Create test ContractViolationEvent."""
    return ContractViolationEvent(
        contract_name=contract_name,
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=severity,
        message="Data is 3 hours stale",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )


@pytest.mark.requirement("3D-FR-026")
def test_webhook_name() -> None:
    """Test plugin name is 'webhook'."""
    plugin = WebhookAlertPlugin(webhook_url="https://example.com/webhook")
    assert plugin.name == "webhook"


@pytest.mark.requirement("3D-FR-026")
def test_webhook_version() -> None:
    """Test plugin version is valid semver string."""
    plugin = WebhookAlertPlugin(webhook_url="https://example.com/webhook")
    version = plugin.version
    # Validate semver format: X.Y.Z
    parts = version.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


@pytest.mark.requirement("3D-FR-026")
def test_webhook_floe_api_version() -> None:
    """Test plugin floe_api_version is '1.0'."""
    plugin = WebhookAlertPlugin(webhook_url="https://example.com/webhook")
    assert plugin.floe_api_version == "1.0"


@pytest.mark.requirement("3D-FR-026")
def test_validate_config_valid() -> None:
    """Test validate_config returns empty list when webhook_url is set."""
    plugin = WebhookAlertPlugin(webhook_url="https://example.com/webhook")
    errors = plugin.validate_config()
    assert errors == []


@pytest.mark.requirement("3D-FR-026")
def test_validate_config_missing_url() -> None:
    """Test validate_config returns error when webhook_url is missing."""
    plugin = WebhookAlertPlugin(webhook_url="")
    errors = plugin.validate_config()
    assert len(errors) == 1
    assert "webhook_url" in errors[0].lower()
    assert "required" in errors[0].lower()


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_send_alert_success() -> None:
    """Test send_alert returns True when HTTP POST succeeds (200)."""
    plugin = WebhookAlertPlugin(webhook_url="https://example.com/webhook")
    event = _make_event()

    mock_response = AsyncMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await plugin.send_alert(event)

        assert result is True
        mock_post.assert_awaited_once()


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_send_alert_cloudevents_format() -> None:
    """Test POST body has CloudEvents v1.0 required fields."""
    plugin = WebhookAlertPlugin(webhook_url="https://example.com/webhook")
    event = _make_event(contract_name="test_contract", severity=ViolationSeverity.WARNING)

    mock_response = AsyncMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        await plugin.send_alert(event)

        # Extract the JSON body from the call
        call_kwargs = mock_post.call_args.kwargs
        body = call_kwargs["json"]

        # Verify CloudEvents v1.0 required fields
        assert body["specversion"] == "1.0"
        assert body["type"] == "com.floe.contract.violation"
        assert body["source"] == "/floe/contract-monitor"
        assert "id" in body
        assert len(body["id"]) > 0
        # Validate ID is a UUID
        uuid.UUID(body["id"])
        assert "time" in body
        # Verify ISO 8601 timestamp
        datetime.fromisoformat(body["time"].replace("Z", "+00:00"))
        assert body["datacontenttype"] == "application/json"

        # Verify data field contains violation details
        assert "data" in body
        data = body["data"]
        assert data["contract_name"] == "test_contract"
        assert data["violation_type"] == ViolationType.FRESHNESS.value
        assert data["severity"] == ViolationSeverity.WARNING.value
        assert data["message"] == "Data is 3 hours stale"


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_send_alert_content_type_header() -> None:
    """Test POST uses Content-Type: application/cloudevents+json."""
    plugin = WebhookAlertPlugin(webhook_url="https://example.com/webhook")
    event = _make_event()

    mock_response = AsyncMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        await plugin.send_alert(event)

        call_kwargs = mock_post.call_args.kwargs
        headers = call_kwargs["headers"]
        assert headers["Content-Type"] == CLOUDEVENTS_CONTENT_TYPE


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_send_alert_http_error() -> None:
    """Test send_alert returns False when HTTP returns 500."""
    plugin = WebhookAlertPlugin(webhook_url="https://example.com/webhook")
    event = _make_event()

    mock_response = AsyncMock()
    mock_response.status_code = 500

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await plugin.send_alert(event)

        assert result is False


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_send_alert_connection_error() -> None:
    """Test send_alert returns False on ConnectError, no exception propagated."""
    plugin = WebhookAlertPlugin(webhook_url="https://example.com/webhook")
    event = _make_event()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        # Should not raise exception
        result = await plugin.send_alert(event)

        assert result is False


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_send_alert_timeout() -> None:
    """Test send_alert returns False on TimeoutException."""
    plugin = WebhookAlertPlugin(webhook_url="https://example.com/webhook")
    event = _make_event()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timeout")

        result = await plugin.send_alert(event)

        assert result is False

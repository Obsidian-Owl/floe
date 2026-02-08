"""Unit tests for Slack alert channel plugin.

Tasks: T038 (Epic 3D)
Requirements: 3D-FR-026
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)
from floe_alert_slack.plugin import SlackAlertPlugin


def _make_event(
    *,
    contract_name: str = "orders_v1",
    severity: ViolationSeverity = ViolationSeverity.ERROR,
) -> ContractViolationEvent:
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
def test_slack_name() -> None:
    plugin = SlackAlertPlugin(webhook_url="https://hooks.slack.com/test")
    assert plugin.name == "slack"


@pytest.mark.requirement("3D-FR-026")
def test_slack_validate_config_valid() -> None:
    plugin = SlackAlertPlugin(webhook_url="https://hooks.slack.com/test")
    assert plugin.validate_config() == []


@pytest.mark.requirement("3D-FR-026")
def test_slack_validate_config_missing_url() -> None:
    plugin = SlackAlertPlugin()
    errors = plugin.validate_config()
    assert len(errors) > 0
    assert any("webhook_url" in e for e in errors)


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_slack_send_alert_success() -> None:
    plugin = SlackAlertPlugin(webhook_url="https://hooks.slack.com/test")
    event = _make_event()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("floe_alert_slack.plugin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await plugin.send_alert(event)

    assert result is True
    mock_client.post.assert_called_once()


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_slack_block_kit_format() -> None:
    """Test that Slack message uses Block Kit format with sections."""
    plugin = SlackAlertPlugin(webhook_url="https://hooks.slack.com/test")
    event = _make_event(severity=ViolationSeverity.CRITICAL)

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("floe_alert_slack.plugin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        await plugin.send_alert(event)

    call_kwargs = mock_client.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert "blocks" in payload
    assert isinstance(payload["blocks"], list)
    assert len(payload["blocks"]) > 0


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_slack_send_alert_http_error() -> None:
    plugin = SlackAlertPlugin(webhook_url="https://hooks.slack.com/test")
    event = _make_event()

    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch("floe_alert_slack.plugin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await plugin.send_alert(event)

    assert result is False


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_slack_send_alert_connection_error() -> None:
    import httpx as httpx_mod

    plugin = SlackAlertPlugin(webhook_url="https://hooks.slack.com/test")
    event = _make_event()

    with patch("floe_alert_slack.plugin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx_mod.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await plugin.send_alert(event)

    assert result is False

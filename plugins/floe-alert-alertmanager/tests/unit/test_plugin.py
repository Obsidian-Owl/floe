"""Unit tests for Alertmanager alert channel plugin.

Tasks: T040 (Epic 3D)
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
from floe_alert_alertmanager.plugin import AlertmanagerPlugin


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
def test_alertmanager_name() -> None:
    plugin = AlertmanagerPlugin(api_url="http://alertmanager:9093")
    assert plugin.name == "alertmanager"


@pytest.mark.requirement("3D-FR-026")
def test_alertmanager_validate_config_valid() -> None:
    plugin = AlertmanagerPlugin(api_url="http://alertmanager:9093")
    assert plugin.validate_config() == []


@pytest.mark.requirement("3D-FR-026")
def test_alertmanager_validate_config_missing_url() -> None:
    plugin = AlertmanagerPlugin()
    errors = plugin.validate_config()
    assert len(errors) > 0
    assert any("api_url" in e for e in errors)


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_alertmanager_send_alert_success() -> None:
    plugin = AlertmanagerPlugin(api_url="http://alertmanager:9093")
    event = _make_event()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("floe_alert_alertmanager.plugin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await plugin.send_alert(event)

    assert result is True


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_alertmanager_api_format() -> None:
    """Test that POST body matches Alertmanager /api/v2/alerts format."""
    plugin = AlertmanagerPlugin(api_url="http://alertmanager:9093")
    event = _make_event()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("floe_alert_alertmanager.plugin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        await plugin.send_alert(event)

    call_kwargs = mock_client.post.call_args
    # Alertmanager expects a list of alert objects
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert isinstance(payload, list)
    assert len(payload) == 1
    alert = payload[0]
    # Required fields
    assert "labels" in alert
    assert "annotations" in alert
    assert alert["labels"]["alertname"] == "ContractViolation"
    assert alert["labels"]["severity"] == event.severity.value
    assert alert["labels"]["contract"] == event.contract_name
    assert alert["labels"]["violation_type"] == event.violation_type.value


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_alertmanager_posts_to_correct_endpoint() -> None:
    """Test that POST goes to /api/v2/alerts."""
    plugin = AlertmanagerPlugin(api_url="http://alertmanager:9093")
    event = _make_event()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("floe_alert_alertmanager.plugin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        await plugin.send_alert(event)

    call_args = mock_client.post.call_args
    url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
    assert url == "http://alertmanager:9093/api/v2/alerts"


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_alertmanager_send_alert_http_error() -> None:
    plugin = AlertmanagerPlugin(api_url="http://alertmanager:9093")
    event = _make_event()

    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch("floe_alert_alertmanager.plugin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await plugin.send_alert(event)

    assert result is False


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_alertmanager_send_alert_connection_error() -> None:
    import httpx as httpx_mod

    plugin = AlertmanagerPlugin(api_url="http://alertmanager:9093")
    event = _make_event()

    with patch("floe_alert_alertmanager.plugin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx_mod.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await plugin.send_alert(event)

    assert result is False

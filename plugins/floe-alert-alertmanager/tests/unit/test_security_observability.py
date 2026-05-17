"""Security-sensitive observability tests for Alertmanager alerts."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)

from floe_alert_alertmanager.plugin import AlertmanagerPlugin


class _Span:
    def __init__(self, name: str, attributes: dict[str, Any] | None) -> None:
        self.name = name
        self.attributes = dict(attributes or {})

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: Any) -> None:
        self.status = status


class _SpanContext(AbstractContextManager[_Span]):
    def __init__(self, span: _Span) -> None:
        self._span = span

    def __enter__(self) -> _Span:
        return self._span

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _Tracer:
    def __init__(self) -> None:
        self.spans: list[_Span] = []

    def start_as_current_span(self, name: str, **kwargs: Any) -> _SpanContext:
        span = _Span(name, kwargs.get("attributes"))
        self.spans.append(span)
        return _SpanContext(span)


def _event() -> ContractViolationEvent:
    return ContractViolationEvent(
        contract_name="orders_v1",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="token=body-secret person@example.com",  # pragma: allowlist secret
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.1,
    )


def _attrs_text(tracer: _Tracer) -> str:
    return repr([span.attributes for span in tracer.spans])


@pytest.mark.asyncio
async def test_send_alert_records_delivery_metadata_without_url_or_body() -> None:
    tracer = _Tracer()
    plugin = AlertmanagerPlugin(
        api_url=(
            "https://user:password@alerts.example.com?token=url-secret"  # pragma: allowlist secret
        )
    )

    with (
        patch("floe_alert_alertmanager.plugin.get_tracer", return_value=tracer),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post,
    ):
        post.return_value = Mock(status_code=202)
        assert await plugin.send_alert(_event()) is True

    attrs = tracer.spans[-1].attributes
    assert tracer.spans[-1].name == "alert.send_alert"
    assert attrs["alert.destination_type"] == "alertmanager"
    assert attrs["alert.delivery_status"] == "delivered"
    assert attrs["alert.retry_count"] == 0
    assert attrs["contract.violation_id"] == "orders_v1:1.0.0:freshness"
    text = _attrs_text(tracer)
    assert "alerts.example.com" not in text
    assert "url-secret" not in text  # pragma: allowlist secret
    assert "body-secret" not in text  # pragma: allowlist secret
    assert "person@example.com" not in text


@pytest.mark.asyncio
async def test_send_alert_classifies_failures() -> None:
    tracer = _Tracer()
    plugin = AlertmanagerPlugin(api_url="https://alerts.example.com")

    with (
        patch("floe_alert_alertmanager.plugin.get_tracer", return_value=tracer),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post,
    ):
        post.return_value = Mock(status_code=403)
        assert await plugin.send_alert(_event()) is False
    assert tracer.spans[-1].attributes["alert.error_type"] == "access_denied"

    with (
        patch("floe_alert_alertmanager.plugin.get_tracer", return_value=tracer),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post,
    ):
        post.return_value = Mock(status_code=404)
        assert await plugin.send_alert(_event()) is False
    assert tracer.spans[-1].attributes["alert.error_type"] == "not_found"

    with (
        patch("floe_alert_alertmanager.plugin.get_tracer", return_value=tracer),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post,
    ):
        post.side_effect = httpx.TimeoutException(
            "unavailable token=leaked"  # pragma: allowlist secret
        )
        assert await plugin.send_alert(_event()) is False
    assert tracer.spans[-1].attributes["alert.error_type"] == "unavailable"

    with patch("floe_alert_alertmanager.plugin.get_tracer", return_value=tracer):
        assert AlertmanagerPlugin(api_url="").validate_config()
    assert tracer.spans[-1].attributes["alert.error_type"] == "validation"

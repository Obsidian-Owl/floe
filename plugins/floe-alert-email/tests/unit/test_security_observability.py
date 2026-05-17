"""Security-sensitive observability tests for email alerts."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)

from floe_alert_email.plugin import EmailAlertPlugin


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
        violation_type=ViolationType.QUALITY,
        severity=ViolationSeverity.ERROR,
        message="password=body-secret person@example.com",  # pragma: allowlist secret
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.1,
    )


def _attrs_text(tracer: _Tracer) -> str:
    return repr([span.attributes for span in tracer.spans])


@pytest.mark.asyncio
async def test_send_alert_records_delivery_metadata_without_email_password_or_body() -> None:
    tracer = _Tracer()
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        from_address="from@example.com",
        to_addresses=["alerts@example.com"],
        username="mailer",
        password="smtp-secret-password",  # pragma: allowlist secret
    )

    with (
        patch("floe_alert_email.plugin.get_tracer", return_value=tracer),
        patch("aiosmtplib.send", new_callable=AsyncMock),
    ):
        assert await plugin.send_alert(_event()) is True

    attrs = tracer.spans[-1].attributes
    assert attrs["alert.destination_type"] == "email"
    assert attrs["alert.delivery_status"] == "delivered"
    assert attrs["alert.retry_count"] == 0
    assert attrs["contract.violation_id"] == "orders_v1:1.0.0:quality"
    text = _attrs_text(tracer)
    assert "alerts@example.com" not in text
    assert "from@example.com" not in text
    assert "smtp-secret-password" not in text  # pragma: allowlist secret
    assert "body-secret" not in text  # pragma: allowlist secret


@pytest.mark.asyncio
async def test_send_alert_and_validation_failures_are_classified() -> None:
    tracer = _Tracer()
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        from_address="from@example.com",
        to_addresses=["alerts@example.com"],
    )

    with (
        patch("floe_alert_email.plugin.get_tracer", return_value=tracer),
        patch("aiosmtplib.send", new_callable=AsyncMock) as send,
    ):
        send.side_effect = TimeoutError(
            "smtp unavailable password=leaked"  # pragma: allowlist secret
        )
        assert await plugin.send_alert(_event()) is False
    assert tracer.spans[-1].attributes["alert.error_type"] == "unavailable"
    assert "leaked" not in _attrs_text(tracer)  # pragma: allowlist secret

    with patch("floe_alert_email.plugin.get_tracer", return_value=tracer):
        assert EmailAlertPlugin().validate_config()
    assert tracer.spans[-1].attributes["alert.error_type"] == "validation"


@pytest.mark.asyncio
async def test_send_alert_classifies_access_denied_and_not_found() -> None:
    tracer = _Tracer()
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        from_address="from@example.com",
        to_addresses=["alerts@example.com"],
    )

    with (
        patch("floe_alert_email.plugin.get_tracer", return_value=tracer),
        patch("aiosmtplib.send", new_callable=AsyncMock) as send,
    ):
        send.side_effect = PermissionError(
            "auth denied password=leaked"  # pragma: allowlist secret
        )
        assert await plugin.send_alert(_event()) is False
    assert tracer.spans[-1].attributes["alert.error_type"] == "access_denied"

    with (
        patch("floe_alert_email.plugin.get_tracer", return_value=tracer),
        patch("aiosmtplib.send", new_callable=AsyncMock) as send,
    ):
        send.side_effect = FileNotFoundError(
            "recipient not found token=leaked"  # pragma: allowlist secret
        )
        assert await plugin.send_alert(_event()) is False
    assert tracer.spans[-1].attributes["alert.error_type"] == "not_found"
    assert "leaked" not in _attrs_text(tracer)  # pragma: allowlist secret

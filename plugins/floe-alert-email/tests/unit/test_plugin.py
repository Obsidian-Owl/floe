"""Unit tests for Email alert channel plugin.

Tasks: T039 (Epic 3D)
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
from floe_alert_email.plugin import EmailAlertPlugin


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
def test_email_name() -> None:
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        smtp_port=587,
        from_address="alerts@example.com",
        to_addresses=["team@example.com"],
    )
    assert plugin.name == "email"


@pytest.mark.requirement("3D-FR-026")
def test_email_version() -> None:
    """Test plugin version is valid semver string."""
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        smtp_port=587,
        from_address="alerts@example.com",
        to_addresses=["team@example.com"],
    )
    version = plugin.version
    # Validate semver format: X.Y.Z
    parts = version.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


@pytest.mark.requirement("3D-FR-026")
def test_email_floe_api_version() -> None:
    """Test plugin floe_api_version is '1.0'."""
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        smtp_port=587,
        from_address="alerts@example.com",
        to_addresses=["team@example.com"],
    )
    assert plugin.floe_api_version == "1.0"


@pytest.mark.requirement("3D-FR-026")
def test_email_validate_config_valid() -> None:
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        smtp_port=587,
        from_address="alerts@example.com",
        to_addresses=["team@example.com"],
    )
    assert plugin.validate_config() == []


@pytest.mark.requirement("3D-FR-026")
def test_email_validate_config_missing_host() -> None:
    plugin = EmailAlertPlugin(
        from_address="alerts@example.com",
        to_addresses=["team@example.com"],
    )
    errors = plugin.validate_config()
    assert len(errors) > 0
    assert any("smtp_host" in e for e in errors)


@pytest.mark.requirement("3D-FR-026")
def test_email_validate_config_missing_recipients() -> None:
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        smtp_port=587,
        from_address="alerts@example.com",
    )
    errors = plugin.validate_config()
    assert len(errors) > 0
    assert any("to_addresses" in e for e in errors)


@pytest.mark.requirement("3D-FR-026")
def test_email_validate_config_missing_from() -> None:
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        smtp_port=587,
        to_addresses=["team@example.com"],
    )
    errors = plugin.validate_config()
    assert len(errors) > 0
    assert any("from_address" in e for e in errors)


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_email_send_alert_success() -> None:
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        smtp_port=587,
        from_address="alerts@example.com",
        to_addresses=["team@example.com"],
    )
    event = _make_event()

    with patch("floe_alert_email.plugin.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock()
        result = await plugin.send_alert(event)

    assert result is True


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_email_send_alert_smtp_error() -> None:
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        smtp_port=587,
        from_address="alerts@example.com",
        to_addresses=["team@example.com"],
    )
    event = _make_event()

    with patch("floe_alert_email.plugin.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock(side_effect=OSError("SMTP connection refused"))
        result = await plugin.send_alert(event)

    assert result is False


@pytest.mark.requirement("3D-FR-026")
@pytest.mark.asyncio
async def test_email_html_content() -> None:
    """Test that email contains HTML formatted violation details."""
    plugin = EmailAlertPlugin(
        smtp_host="smtp.example.com",
        smtp_port=587,
        from_address="alerts@example.com",
        to_addresses=["team@example.com"],
    )
    event = _make_event(severity=ViolationSeverity.CRITICAL)

    with patch("floe_alert_email.plugin.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock()
        await plugin.send_alert(event)

    call_args = mock_smtp.send.call_args
    message = call_args[0][0]  # First positional arg is the MIMEMessage
    # Check it has HTML content
    payload = message.get_payload()
    # For multipart, get HTML part
    if isinstance(payload, list):
        html_parts = [p for p in payload if p.get_content_type() == "text/html"]
        assert len(html_parts) > 0
        html_content = html_parts[0].get_payload(decode=True).decode()
    else:
        html_content = message.get_payload(decode=True).decode()
    assert event.contract_name in html_content
    assert event.severity.value in html_content

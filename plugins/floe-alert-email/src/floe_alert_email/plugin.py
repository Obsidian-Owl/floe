"""Email alert channel plugin.

Sends contract violation alerts via SMTP email with HTML formatting.

Tasks: T043 (Epic 3D)
Requirements: FR-026, FR-027
"""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
import structlog
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
)
from floe_core.plugins.alert_channel import AlertChannelPlugin

logger = structlog.get_logger(__name__)


class EmailAlertPlugin(AlertChannelPlugin):
    """Email (SMTP) alert channel with HTML formatting."""

    def __init__(
        self,
        *,
        smtp_host: str = "",
        smtp_port: int = 587,
        from_address: str = "",
        to_addresses: list[str] | None = None,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._from_address = from_address
        self._to_addresses = to_addresses or []
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._timeout_seconds = timeout_seconds
        self._log = logger.bind(component="email_alert")

    @property
    def name(self) -> str:
        return "email"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if not self._smtp_host:
            errors.append("smtp_host is required")
        if not self._from_address:
            errors.append("from_address is required")
        if not self._to_addresses:
            errors.append("to_addresses is required (at least one recipient)")
        return errors

    async def send_alert(self, event: ContractViolationEvent) -> bool:
        message = self._build_message(event)
        try:
            await aiosmtplib.send(
                message,
                hostname=self._smtp_host,
                port=self._smtp_port,
                username=self._username or None,
                password=self._password or None,
                use_tls=self._use_tls,
                timeout=self._timeout_seconds,
            )
            return True
        except Exception as e:
            self._log.error(
                "email_send_error",
                error=str(e),
                contract_name=event.contract_name,
            )
            return False

    def _build_message(self, event: ContractViolationEvent) -> MIMEMultipart:
        subject = f"[{event.severity.value.upper()}] Contract Violation: {event.contract_name}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from_address
        msg["To"] = ", ".join(self._to_addresses)

        html = self._build_html(event)
        msg.attach(MIMEText(html, "html"))

        return msg

    def _build_html(self, event: ContractViolationEvent) -> str:
        return f"""<html>
<body>
<h2>Contract Violation Alert</h2>
<table border="1" cellpadding="8" cellspacing="0">
<tr><td><b>Contract</b></td><td>{event.contract_name}</td></tr>
<tr><td><b>Version</b></td><td>{event.contract_version}</td></tr>
<tr><td><b>Type</b></td><td>{event.violation_type.value}</td></tr>
<tr><td><b>Severity</b></td><td>{event.severity.value}</td></tr>
<tr><td><b>Message</b></td><td>{event.message}</td></tr>
<tr><td><b>Timestamp</b></td><td>{event.timestamp.isoformat()}</td></tr>
<tr><td><b>Check Duration</b></td><td>{event.check_duration_seconds:.3f}s</td></tr>
</table>
</body>
</html>"""

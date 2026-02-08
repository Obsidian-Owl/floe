# floe-alert-email

Email alert channel plugin for the floe data platform.

Sends contract violation alerts via SMTP email with HTML formatting.

## Installation

```bash
uv add floe-alert-email
```

## Configuration

```python
from floe_alert_email import EmailAlertPlugin

plugin = EmailAlertPlugin(
    smtp_host="smtp.example.com",
    smtp_port=587,
    from_address="alerts@example.com",
    to_addresses=["team@example.com"],
    username="your_username",
    password="your_password",
    use_tls=True,
)
```

## License

Apache-2.0

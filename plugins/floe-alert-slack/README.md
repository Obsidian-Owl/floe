# floe-alert-slack

Slack alert channel plugin for the floe data platform.

Sends contract violation alerts to Slack using Block Kit formatting via incoming webhooks.

## Installation

```bash
uv add floe-alert-slack
```

## Configuration

```python
from floe_alert_slack import SlackAlertPlugin

plugin = SlackAlertPlugin(
    webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    timeout_seconds=10.0,
)
```

## License

Apache-2.0

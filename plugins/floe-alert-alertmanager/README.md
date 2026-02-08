# floe-alert-alertmanager

Alertmanager alert channel plugin for the floe data platform.

Sends contract violation alerts to Prometheus Alertmanager via its HTTP API.

## Installation

```bash
uv add floe-alert-alertmanager
```

## Configuration

```python
from floe_alert_alertmanager import AlertmanagerPlugin

plugin = AlertmanagerPlugin(
    api_url="http://alertmanager:9093",
    timeout_seconds=10.0,
)
```

## License

Apache-2.0

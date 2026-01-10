# floe-telemetry-console

Console telemetry backend plugin for floe - outputs traces to stdout for local development.

## Overview

This plugin provides a `ConsoleTelemetryPlugin` that configures OpenTelemetry to output traces to the console. This is useful for:

- Local development and debugging
- Quick verification of trace instrumentation
- Environments where no OTLP Collector is available

## Installation

```bash
pip install floe-telemetry-console
```

## Usage

### Via manifest.yaml (Recommended)

```yaml
# manifest.yaml
plugins:
  telemetry_backend: console
```

### Programmatic Usage

```python
from floe_telemetry_console import ConsoleTelemetryPlugin

plugin = ConsoleTelemetryPlugin()
# Plugin will be loaded automatically by TelemetryProvider
```

## Configuration

The console plugin uses default settings. Traces are printed to stdout in a human-readable format.

## Requirements

- Python 3.10+
- floe-core >= 0.1.0
- opentelemetry-sdk >= 1.20.0

## License

Apache-2.0

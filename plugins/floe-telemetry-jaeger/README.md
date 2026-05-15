# floe-telemetry-jaeger

> **Alpha release notice:** This `v0.1.0-alpha.1` package is for isolated evaluation only. Do not use Floe alpha packages with production data, production credentials, regulated workloads, customer-facing SLAs, or production-scale loads. Floe is distributed under Apache-2.0 on an "AS IS" basis; see the repository `LICENSE` for full terms.

Jaeger telemetry backend plugin for floe - OTLP exporter for Jaeger distributed tracing.

## Overview

This plugin provides a `JaegerTelemetryPlugin` that configures OpenTelemetry to export traces to Jaeger via OTLP. This is recommended for:

- Production environments requiring distributed tracing
- Visualization of trace data with Jaeger UI
- Integration with existing Jaeger infrastructure

## Installation

```bash
pip install floe-telemetry-jaeger
```

## Usage

### Via manifest.yaml (Recommended)

```yaml
# manifest.yaml
plugins:
  telemetry_backend: jaeger
```

### Programmatic Usage

```python
from floe_telemetry_jaeger import JaegerTelemetryPlugin

plugin = JaegerTelemetryPlugin()
# Plugin will be loaded automatically by TelemetryProvider
```

## Configuration

The Jaeger plugin configures the OTLP exporter to send traces to a Jaeger collector. Default configuration:

- Endpoint: `jaeger-collector:4317` (gRPC)
- Protocol: OTLP/gRPC
- TLS: Disabled for local development

For production, configure via environment variables:
- `OTEL_EXPORTER_OTLP_ENDPOINT`: Jaeger collector endpoint
- `OTEL_EXPORTER_OTLP_INSECURE`: Set to "false" for TLS

## Requirements

- Python 3.10+
- floe-core >= 0.1.0
- opentelemetry-sdk >= 1.20.0
- opentelemetry-exporter-otlp >= 1.20.0

## License

Apache-2.0

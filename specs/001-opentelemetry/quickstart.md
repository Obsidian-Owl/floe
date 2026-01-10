# Quickstart: OpenTelemetry Integration

**Feature**: 001-opentelemetry
**Date**: 2026-01-09

## Overview

This guide helps developers get started with OpenTelemetry integration in Floe. It covers basic telemetry emission, custom span creation, and backend plugin selection.

---

## Prerequisites

- Python 3.10+
- floe-core installed
- OTLP Collector running (or console exporter for local dev)

---

## 1. Basic Telemetry Setup

### Initialize Telemetry Provider

```python
from floe_core.telemetry import TelemetryProvider
from floe_core.telemetry.config import TelemetryConfig, ResourceAttributes

# Create configuration
config = TelemetryConfig(
    enabled=True,
    otlp_endpoint="http://otel-collector:4317",
    resource_attributes=ResourceAttributes(
        service_name="my-data-product",
        service_version="1.0.0",
        deployment_environment="dev",
        floe_namespace="analytics",  # MANDATORY per ADR-0006
        floe_product_name="customer-360",
        floe_product_version="1.0.0",
        floe_mode="dev",
    ),
)

# Initialize provider (call once at startup)
provider = TelemetryProvider(config)
provider.initialize()

# Graceful shutdown (call at exit)
provider.shutdown()
```

### Using Context Manager (Recommended)

```python
from floe_core.telemetry import TelemetryProvider

with TelemetryProvider(config) as provider:
    # Your application code here
    pass
# Automatic shutdown and flush
```

---

## 2. Creating Traces

### Using Decorators (Simplest)

```python
from floe_core.telemetry.tracing import traced

@traced(name="process_customer_data")
def process_customers(customer_ids: list[str]) -> dict:
    """Process customers - automatically traced."""
    results = {}
    for cid in customer_ids:
        results[cid] = transform_customer(cid)
    return results
```

### Using Context Manager

```python
from floe_core.telemetry.tracing import create_span

def process_pipeline():
    with create_span("pipeline_execution") as span:
        span.set_attribute("pipeline.name", "customer-360")

        # Child span created automatically
        with create_span("load_data") as load_span:
            load_span.set_attribute("source", "s3://bucket/data")
            data = load_from_s3()

        # Another child span
        with create_span("transform_data") as transform_span:
            transform_span.set_attribute("row_count", len(data))
            result = transform(data)

    return result
```

### Adding Floe Semantic Attributes

```python
from floe_core.telemetry.conventions import FloeSpanAttributes

# Create Floe-specific attributes
attrs = FloeSpanAttributes(
    namespace="analytics",
    product_name="customer-360",
    product_version="1.0.0",
    mode="prod",
    pipeline_id="run-12345",
    model_name="stg_customers",
)

with create_span("dbt_model_run") as span:
    # Add all Floe attributes at once
    for key, value in attrs.to_otel_dict().items():
        span.set_attribute(key, value)
```

---

## 3. Recording Metrics

```python
from floe_core.telemetry.metrics import MetricRecorder

# Get metric recorder
metrics = MetricRecorder()

# Counter (monotonically increasing)
metrics.increment("pipeline.runs.total", labels={"status": "success"})

# Gauge (point-in-time value)
metrics.set_gauge("pipeline.queue.depth", value=42)

# Histogram (distribution)
metrics.record_histogram("pipeline.duration.seconds", value=12.5)
```

---

## 4. Log Correlation

Logs are automatically correlated with traces via structlog processor.

```python
import structlog

log = structlog.get_logger()

def process_data():
    with create_span("data_processing") as span:
        # Logs automatically include trace_id and span_id
        log.info("processing_started", row_count=1000)

        try:
            result = transform()
            log.info("processing_complete", output_size=len(result))
        except Exception as e:
            log.error("processing_failed", error=str(e))
            raise
```

**Log Output** (JSON):
```json
{
  "event": "processing_started",
  "timestamp": "2026-01-09T10:00:00+00:00",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "row_count": 1000
}
```

---

## 5. Environment-Based Sampling

Sampling is configured per environment to balance observability with cost.

```python
from floe_core.telemetry.config import SamplingConfig

# Default ratios: dev=100%, staging=50%, prod=10%
sampling = SamplingConfig(
    dev=1.0,      # Sample all traces in development
    staging=0.5,  # Sample 50% in staging
    prod=0.1,     # Sample 10% in production
)

config = TelemetryConfig(
    sampling=sampling,
    # ... other config
)
```

---

## 6. Local Development (Console Exporter)

For local development without an OTLP Collector, use the console backend plugin.

```yaml
# manifest.yaml
plugins:
  telemetry_backend: console
```

```python
# Or programmatically
from floe_core.telemetry import TelemetryProvider

config = TelemetryConfig(
    enabled=True,
    otlp_endpoint="",  # Empty for console
    # ... other config
)

# Traces printed to stdout for debugging
```

---

## 7. Selecting a Backend Plugin

Backend selection is done in `manifest.yaml` (Platform Team responsibility).

### Jaeger (Self-Hosted)

```yaml
# manifest.yaml
plugins:
  telemetry_backend: jaeger

telemetry:
  otlp_endpoint: http://jaeger-collector:4317
```

### Datadog (SaaS)

```yaml
# manifest.yaml
plugins:
  telemetry_backend: datadog

telemetry:
  otlp_endpoint: https://intake.datadoghq.com/api/v2/otlp
  authentication:
    auth_type: api_key
    header_name: DD-API-KEY
    # API key loaded from DATADOG_API_KEY environment variable
```

### Grafana Cloud (SaaS)

```yaml
# manifest.yaml
plugins:
  telemetry_backend: grafana-cloud

telemetry:
  otlp_endpoint: https://otlp-gateway-prod-us-central-0.grafana.net/otlp
  authentication:
    auth_type: bearer
    # Token loaded from GRAFANA_CLOUD_TOKEN environment variable
```

---

## 8. Disabling Telemetry

Telemetry can be disabled for testing or when not needed.

```python
# Via configuration
config = TelemetryConfig(
    enabled=False,  # Disables all telemetry
    # ... other config
)

# Via environment variable
# OTEL_SDK_DISABLED=true
```

When disabled, all telemetry operations become no-ops with ~400ns overhead per span.

---

## Common Patterns

### dbt Model Tracing

```python
@traced(name="dbt_run")
def run_dbt_model(model_name: str) -> None:
    """Run a dbt model with tracing."""
    with create_span(f"dbt.model.{model_name}") as span:
        span.set_attribute("floe.dbt.model", model_name)
        span.set_attribute("floe.job.type", "dbt_run")

        dbt_runner.invoke(["run", "--select", model_name])
```

### Dagster Asset Tracing

```python
from dagster import asset
from floe_core.telemetry.tracing import traced

@asset
@traced(name="customers_asset")
def customers() -> pd.DataFrame:
    """Dagster asset with automatic tracing."""
    # Trace automatically includes asset key
    return load_customers()
```

---

## Troubleshooting

### Traces Not Appearing

1. Check OTLP Collector is running: `kubectl get pods -l app=otel-collector`
2. Verify endpoint in config matches collector service
3. Check sampling ratio isn't 0.0 for your environment
4. Verify `enabled=True` in TelemetryConfig

### High Latency

1. Ensure BatchSpanProcessor is used (default)
2. Check queue size isn't overflowing
3. Verify network connectivity to collector
4. Consider increasing batch size or schedule delay

### Missing Attributes

1. Verify all Floe semantic conventions are set
2. Check `floe.namespace` is always present (MANDATORY)
3. Use `FloeSpanAttributes.to_otel_dict()` for consistency

---

## Next Steps

- See [data-model.md](data-model.md) for complete contract definitions
- See [research.md](research.md) for SDK implementation details
- Review ADR-0006 for architecture decisions

# Research: OpenTelemetry Integration

**Feature**: 001-opentelemetry
**Date**: 2026-01-09
**Status**: Complete

## Research Topics

1. SDK Initialization Pattern
2. W3C Trace Context & Baggage Propagation
3. Async Export Configuration
4. No-Op Mode (Zero Overhead)
5. Structlog Integration

---

## 1. SDK Initialization Pattern

### Decision
Use a **single-responsibility initialization module** that sets up TracerProvider, MeterProvider with configurable resource attributes and graceful shutdown.

### Rationale
- Centralized configuration in one place
- Production-ready with environment variable overrides
- Proper service identification across backends
- Graceful shutdown prevents data loss

### Implementation Pattern

```python
from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.sampling import TraceIDRatioBased

def initialize_otel(
    service_name: str,
    service_version: str,
    environment: str,
    otlp_endpoint: str | None = None,
    sampling_ratio: float = 1.0,
) -> tuple[TracerProvider, MeterProvider]:
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": environment,
    })

    tracer_provider = TracerProvider(
        resource=resource,
        sampler=TraceIDRatioBased(sampling_ratio),
    )

    # BatchSpanProcessor for async export
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
    )

    trace.set_tracer_provider(tracer_provider)
    return tracer_provider, meter_provider
```

### Alternatives Considered
- **Per-component initialization**: Rejected - leads to inconsistent configuration
- **Lazy initialization**: Rejected - complicates shutdown handling

---

## 2. W3C Trace Context & Baggage Propagation

### Decision
Configure **W3C Trace Context + Baggage propagators** (default behavior). Use Baggage for `floe.namespace` and pipeline context.

### Rationale
- W3C standards are OpenTelemetry Python default
- Automatic header propagation in HTTP clients/servers
- Baggage carries request-scoped metadata without overhead
- Size limits (8KB total) prevent abuse

### Implementation Pattern

```python
from opentelemetry import baggage, trace
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator

def setup_propagators() -> None:
    set_global_textmap(CompositePropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator(),
    ]))

# Usage: Set floe.namespace in baggage
ctx = baggage.set_baggage("floe.namespace", namespace)
with tracer.start_as_current_span("operation", context=ctx):
    # Baggage automatically propagated to child spans
    pass
```

### Baggage Guidelines

| Attribute | Include in Baggage | Reason |
|-----------|-------------------|--------|
| `floe.namespace` | Yes | Non-sensitive, routing/correlation |
| `floe.pipeline_id` | Yes | Request context |
| `floe.product.name` | Yes | Product identification |
| User email, API keys | **NO** | PII/secrets - security risk |

---

## 3. Async Export Configuration

### Decision
**Always use BatchSpanProcessor** with gRPC OTLP exporter. Configure queue sizes based on throughput.

### Rationale
- Non-blocking: dedicated background thread
- Efficient batching (512 spans/batch, 5s interval)
- Queue buffers spikes; prevents unbounded growth
- Kubernetes-safe with graceful shutdown

### Configuration

```python
BatchSpanProcessor(
    span_exporter=OTLPSpanExporter(endpoint=endpoint),
    max_queue_size=2048,           # Spans buffered in memory
    max_export_batch_size=512,     # Spans per batch
    schedule_delay_millis=5000,    # Export every 5 seconds
    export_timeout_millis=30000,   # Per-batch timeout
)
```

### Queue Sizing by Throughput

| Throughput | Queue Size | Batch Size | Schedule Delay |
|-----------|-----------|-----------|----------------|
| Low (< 100/s) | 512 | 256 | 10s |
| Medium (100-1000/s) | 2048 | 512 | 5s |
| High (1000+/s) | 4096 | 1024 | 2s |

---

## 4. No-Op Mode (Zero Overhead)

### Decision
Use OpenTelemetry API's built-in no-op implementations. When SDK not initialized, zero overhead.

### Rationale
- API provides no-op by default before SDK initialization
- `OTEL_SDK_DISABLED=true` disables entire SDK
- ~400ns total overhead per span in no-op mode (vs ~5-10µs with SDK)

### Implementation

```python
import os
from opentelemetry import trace

def initialize_if_enabled() -> None:
    if os.environ.get("OTEL_SDK_DISABLED") == "true":
        return  # API defaults to no-op

    # Initialize SDK normally
    initialize_otel(...)

# No-op overhead: ~400ns per span
# SDK overhead: ~5-10µs per span (25x difference)
```

### Alternatives Considered
- **Custom no-op wrapper**: Rejected - unnecessary, API handles it
- **Feature flags per-span**: Rejected - adds overhead

---

## 5. Structlog Integration

### Decision
Create **custom structlog processor** that injects `trace_id` and `span_id` from active span.

### Rationale
- No native OpenTelemetry structlog integration exists
- Custom processor is simple (~20 lines)
- JSON output feeds to OTLP Collector directly
- Avoids stdlib logging bridge complexity

### Implementation

```python
import structlog
from opentelemetry import trace

def add_trace_context(logger, method_name, event_dict):
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict

structlog.configure(
    processors=[
        add_trace_context,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)
```

### Output Format

```json
{
  "event": "processing_complete",
  "timestamp": "2026-01-09T10:00:00+00:00",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "result_size": 42
}
```

---

## Summary: Key Decisions

| Component | Decision | Benefit |
|-----------|----------|---------|
| Initialization | Single module with graceful shutdown | Centralized, production-ready |
| Propagation | W3C Trace Context + Baggage | Standard cross-service tracing |
| Export | BatchSpanProcessor (gRPC OTLP) | Non-blocking, efficient |
| No-Op Mode | API defaults + SDK conditional | Zero overhead when disabled |
| Logging | Custom structlog processor | Simple, JSON-native |

## Dependencies Confirmed

```toml
[project.dependencies]
opentelemetry-api = ">=1.20.0"
opentelemetry-sdk = ">=1.20.0"
opentelemetry-exporter-otlp-proto-grpc = ">=1.20.0"
opentelemetry-exporter-otlp-proto-http = ">=1.20.0"
structlog = ">=23.1.0"
```

## References

- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/languages/python/)
- [OTLP Exporter Configuration](https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [Structlog Documentation](https://www.structlog.org/)

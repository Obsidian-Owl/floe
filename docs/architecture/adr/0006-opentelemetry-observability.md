# ADR-0006: Use OpenTelemetry for Observability

## Status

Accepted

## Context

Observability is a first-class requirement for Floe. We need:

- Distributed tracing (request flow across services)
- Metrics (system and business)
- Structured logging
- Correlation between all three
- Namespace context on all telemetry
- Vendor-neutral (avoid lock-in)

Options considered:
- **OpenTelemetry** - Vendor-neutral standard, comprehensive
- **Datadog SDK** - Good UX, but vendor lock-in
- **Jaeger + Prometheus** - Proven, but multiple systems
- **Custom** - Maximum control, huge effort

## Decision

Use **OpenTelemetry** for all observability: traces, metrics, and logs.

## Consequences

### Positive

- **Vendor neutral** - Can switch backends without code changes
- **Single SDK** - One library for traces, metrics, logs
- **Standard propagation** - W3C Trace Context for cross-service correlation
- **Baggage** - Propagate namespace context automatically
- **Rich ecosystem** - Instrumentations for HTTP, DB, etc.
- **Growing adoption** - Industry standard

### Negative

- **More setup** than proprietary SDKs
- **Configuration complexity** - Collector pipelines can be complex
- **Still evolving** - Logs API less mature than traces/metrics
- **Learning curve** - Team needs to understand OTel concepts

### Neutral

- Requires OTel Collector deployment
- Need to choose backend (Grafana Cloud, Jaeger, etc.)
- Custom semantic conventions for Floe attributes

## Implementation Pattern

```go
// Tracer initialization
func InitTracer(cfg TelemetryConfig) (*sdktrace.TracerProvider, error) {
    exporter, _ := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint(cfg.OTLPEndpoint),
    )

    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName(cfg.ServiceName),
            semconv.ServiceVersion(cfg.ServiceVersion),
        )),
        sdktrace.WithSampler(sdktrace.TraceIDRatioBased(cfg.SampleRate)),
    )

    otel.SetTracerProvider(tp)
    otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
        propagation.TraceContext{},
        propagation.Baggage{},
    ))

    return tp, nil
}
```

## Semantic Conventions

```go
// Floe-specific attributes (on every span)
const (
    AttrNamespace      = "floe.namespace"
    AttrProductName    = "floe.product.name"
    AttrProductVersion = "floe.product.version"
    AttrMode           = "floe.mode"
)
```

## Key Principle

**Every span must include `floe.namespace`.** This enables filtering and aggregation by data product.

## Backend Configuration

### Three-Layer Architecture

OpenTelemetry observability in floe follows a three-layer architecture:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: EMISSION (Enforced)                                      │
│                                                                      │
│  OpenTelemetry SDK in data pipelines/jobs                           │
│  - Standard: OpenTelemetry SDK (this ADR)                           │
│  - Enforced: All jobs MUST emit OTLP                                │
│  - Non-negotiable: Vendor-neutral telemetry                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ OTLP (gRPC or HTTP)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: COLLECTION (Enforced)                                    │
│                                                                      │
│  OTLP Collector (deployed in K8s)                                   │
│  - Standard: OTLP Collector                                         │
│  - Enforced: All jobs send to Collector                             │
│  - Function: Batching, sampling, enrichment, routing                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Backend-specific protocol
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 3: BACKEND (Pluggable via ObservabilityPlugin)             │
│                                                                      │
│  Storage and Visualization                                          │
│  - Pluggable: Platform Team selects backend (ADR-0035)              │
│  - Options: Jaeger, Datadog, Grafana Cloud, AWS X-Ray, custom      │
│  - Plugin interface: ObservabilityPlugin ABC                        │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Separation:**
- **Emission (Layer 1)**: Data pipelines/jobs use OpenTelemetry SDK → Enforced (this ADR)
- **Collection (Layer 2)**: OTLP Collector aggregates telemetry → Enforced (this ADR)
- **Backend (Layer 3)**: Storage/visualization platform → Pluggable (ADR-0035)

### Backend Plugin Examples

Platform teams select one observability backend via `plugins.observability` in platform-manifest.yaml:

**Example: Jaeger (self-hosted OSS)**
```yaml
# platform-manifest.yaml
plugins:
  observability: jaeger

# JaegerPlugin generates:
# - OTLP Collector exporter config (jaeger protocol)
# - Helm values for deploying Jaeger to K8s
```

**Example: Datadog (SaaS)**
```yaml
# platform-manifest.yaml
plugins:
  observability: datadog

# DatadogPlugin generates:
# - OTLP Collector exporter config (datadog API)
# - No Helm values (external SaaS)
```

**Example: Grafana Cloud (SaaS)**
```yaml
# platform-manifest.yaml
plugins:
  observability: grafana-cloud

# GrafanaCloudPlugin generates:
# - OTLP Collector exporter config (OTLP HTTP to Grafana Cloud)
# - No Helm values (external SaaS)
```

**Why this matters:**
- **Data engineers**: Always use OpenTelemetry SDK (enforced, vendor-neutral)
- **Platform teams**: Choose backend once (Jaeger, Datadog, etc.) via plugin
- **Backend changes**: Swap plugin, no code changes in data pipelines

**See ADR-0035** for complete ObservabilityPlugin interface specification.

## References

- [ADR-0035: Observability Plugin Interface](0035-observability-plugin-interface.md) - Pluggable backends
- [OpenTelemetry](https://opentelemetry.io/)
- [OTel Go](https://github.com/open-telemetry/opentelemetry-go)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)

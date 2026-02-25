"""Lightweight, env-var-driven OTel tracing initialization for floe-core.

This module provides ensure_telemetry_initialized(), a zero-argument entry
point that bootstraps the OpenTelemetry SDK from environment variables.

Behaviour:
- Reads OTEL_EXPORTER_OTLP_ENDPOINT; if absent/empty/whitespace, does nothing.
- Reads OTEL_SERVICE_NAME; defaults to 'floe-platform' if absent/empty.
- Creates TracerProvider with OTLPSpanExporter + BatchSpanProcessor.
- Registers it globally via trace.set_tracer_provider().
- Calls configure_logging() to wire structlog with trace context.
- Calls reset_tracer() to invalidate any stale cached NoOp tracers.
- Is idempotent: a module-level flag prevents double-initialisation.

Requirements Covered:
- FR-040: OTel tracing initialization
- AC-17.1: Env-var-driven telemetry bootstrap

See Also:
    - specs/001-opentelemetry/: Feature specification
    - docs/architecture/adr/ADR-0006: Telemetry architecture
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from floe_core.telemetry.logging import configure_logging
from floe_core.telemetry.tracer_factory import reset_tracer

# Default service name used when OTEL_SERVICE_NAME is not set or is empty.
_DEFAULT_SERVICE_NAME = "floe-platform"

# Module-level idempotency flag.  Set to True after successful initialisation
# so that subsequent calls return immediately without re-configuring.
_initialized: bool = False


def ensure_telemetry_initialized() -> None:
    """Initialize OTel tracing from environment variables if not already done.

    Reads OTEL_EXPORTER_OTLP_ENDPOINT from the environment.  If the value is
    absent, empty, or whitespace-only, this function is a no-op.  Otherwise it
    configures a TracerProvider with an OTLPSpanExporter backed by a
    BatchSpanProcessor, registers it as the global provider, configures
    structlog with trace context injection, and resets the tracer_factory cache
    so that subsequent get_tracer()/create_span() calls use the new provider.

    The function is idempotent: only the first call with a valid endpoint
    performs initialisation.  Subsequent calls return immediately.

    Environment Variables:
        OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint, e.g.
            ``http://localhost:4317``.  Absent/empty/whitespace → no-op.
        OTEL_SERVICE_NAME: Service name used as ``service.name`` resource
            attribute.  Defaults to ``'floe-platform'``.

    Returns:
        None

    Examples:
        >>> import os
        >>> os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4317"
        >>> ensure_telemetry_initialized()  # configures SDK
        >>> ensure_telemetry_initialized()  # no-op on second call
    """
    global _initialized

    # Idempotency guard: skip if already initialised.
    if _initialized:
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        # No endpoint configured — leave default (NoOp/Proxy) provider in place.
        return

    # Validate endpoint scheme is http or https.
    from urllib.parse import urlparse

    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https"):
        import structlog

        structlog.get_logger(__name__).warning(
            "otel_endpoint_invalid_scheme",
            endpoint=endpoint,
            scheme=parsed.scheme,
        )
        return

    # Resolve service name with fallback to default.
    service_name = os.environ.get("OTEL_SERVICE_NAME", "").strip() or _DEFAULT_SERVICE_NAME

    # Build a Resource identifying this service.
    resource = Resource.create({"service.name": service_name})

    # Create the OTLP exporter pointing at the configured endpoint.
    exporter = OTLPSpanExporter(endpoint=endpoint)

    # Wrap the exporter in a BatchSpanProcessor for async, buffered export.
    processor = BatchSpanProcessor(exporter)

    # Build the TracerProvider with the resource and processor.
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(processor)

    # Register as the global provider.
    trace.set_tracer_provider(provider)

    # Configure structlog to inject trace_id / span_id into log records.
    configure_logging()

    # Invalidate the tracer_factory cache so subsequent tracer requests use
    # the new provider rather than stale cached NoOp tracers.
    reset_tracer()

    _initialized = True


__all__ = ["ensure_telemetry_initialized"]

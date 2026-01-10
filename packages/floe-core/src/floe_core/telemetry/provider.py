"""TelemetryProvider: OpenTelemetry SDK lifecycle management.

This module provides the TelemetryProvider class for managing OpenTelemetry SDK
initialization, shutdown, and telemetry emission.

Contract Version: 1.0.0

Requirements Covered:
- FR-001: Initialize OpenTelemetry SDK with TelemetryConfig
- FR-002: W3C Trace Context propagation (via configure_propagators)
- FR-003: W3C Baggage propagation (via configure_propagators)
- FR-008: OTLP exporter configuration
- FR-009: gRPC protocol selection
- FR-010: HTTP protocol selection
- FR-011: Authentication header injection
- FR-012: Record pipeline run duration as histogram metric
- FR-013: Record asset materialization counts as counter metric
- FR-014: Record error rates by component as counter metric
- FR-024: Configurable BatchSpanProcessor (async, non-blocking export)
- FR-026: All telemetry sent to OTLP Collector (enforced)

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

import logging
import os
from enum import Enum, auto
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter as OTLPMetricExporterGrpc,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter as OTLPMetricExporterHttp,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPHttpSpanExporter,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from floe_core.telemetry.logging import configure_logging
from floe_core.telemetry.propagation import configure_propagators

if TYPE_CHECKING:
    from types import TracebackType

    from floe_core.telemetry.config import TelemetryConfig

logger = logging.getLogger(__name__)


class ProviderState(Enum):
    """TelemetryProvider lifecycle states.

    States:
        UNINITIALIZED: SDK not initialized, API returns no-op
        INITIALIZED: Active telemetry emission
        FLUSHING: Force-flush in progress (graceful shutdown)
        SHUTDOWN: Provider closed, no more telemetry
    """

    UNINITIALIZED = auto()
    INITIALIZED = auto()
    FLUSHING = auto()
    SHUTDOWN = auto()


class TelemetryProvider:
    """OpenTelemetry SDK provider with lifecycle management.

    Manages the OpenTelemetry SDK initialization, configuration, and shutdown.
    Supports context manager protocol for automatic cleanup.

    The provider respects the OTEL_SDK_DISABLED environment variable for no-op mode.

    Attributes:
        config: TelemetryConfig with SDK configuration
        state: Current lifecycle state

    Examples:
        >>> from floe_core.telemetry import TelemetryConfig, ResourceAttributes
        >>> attrs = ResourceAttributes(
        ...     service_name="my-service",
        ...     service_version="1.0.0",
        ...     deployment_environment="dev",
        ...     floe_namespace="analytics",
        ...     floe_product_name="customer-360",
        ...     floe_product_version="1.0.0",
        ...     floe_mode="dev",
        ... )
        >>> config = TelemetryConfig(resource_attributes=attrs)
        >>> with TelemetryProvider(config) as provider:
        ...     # Telemetry is active
        ...     pass

    See Also:
        - TelemetryConfig: Configuration model
        - ADR-0006: Telemetry architecture
    """

    def __init__(self, config: TelemetryConfig) -> None:
        """Initialize TelemetryProvider with configuration.

        Args:
            config: TelemetryConfig containing SDK configuration.
        """
        self._config = config
        self._state = ProviderState.UNINITIALIZED
        self._noop_mode = self._check_noop_mode()
        self._tracer_provider: TracerProvider | None = None
        self._span_processor: BatchSpanProcessor | None = None
        self._meter_provider: MeterProvider | None = None
        self._metric_reader: PeriodicExportingMetricReader | None = None

    @property
    def config(self) -> TelemetryConfig:
        """Get the telemetry configuration."""
        return self._config

    @property
    def state(self) -> ProviderState:
        """Get the current provider state."""
        return self._state

    @property
    def is_noop(self) -> bool:
        """Check if provider is in no-op mode.

        Returns:
            True if telemetry is disabled or in no-op mode.
        """
        return self._noop_mode or not self._config.enabled

    def _check_noop_mode(self) -> bool:
        """Check if OTEL_SDK_DISABLED environment variable is set.

        Per OpenTelemetry specification, OTEL_SDK_DISABLED=true disables the SDK.

        Returns:
            True if SDK should be disabled.
        """
        disabled = os.environ.get("OTEL_SDK_DISABLED", "").lower()
        return disabled in ("true", "1", "yes")

    def initialize(self) -> None:
        """Initialize the OpenTelemetry SDK.

        Configures the SDK with the provided TelemetryConfig.
        In no-op mode, this is a no-op.

        Protocol selection (FR-009, FR-010):
        - gRPC: Creates OTLPSpanExporter with configured endpoint (port 4317)
        - HTTP: Creates OTLPHttpSpanExporter with configured endpoint (port 4318)

        Both protocols:
        - Wrap exporter in BatchSpanProcessor for async export
        - Register TracerProvider as global provider

        Raises:
            RuntimeError: If provider is not in UNINITIALIZED state.
        """
        if self._state != ProviderState.UNINITIALIZED:
            raise RuntimeError(
                f"Cannot initialize provider in state {self._state.name}. "
                "Provider must be in UNINITIALIZED state."
            )

        if self.is_noop:
            logger.info(
                "TelemetryProvider initialized in no-op mode",
                extra={"noop_reason": self._get_noop_reason()},
            )
            self._state = ProviderState.INITIALIZED
            return

        # Configure W3C Trace Context and Baggage propagators (FR-002, FR-003)
        configure_propagators()

        # Create Resource with service attributes (FR-001)
        resource = Resource.create(self._config.resource_attributes.to_otel_dict())

        # Get sampling ratio for environment (FR-023)
        environment = self._config.resource_attributes.deployment_environment
        sampling_ratio = self._config.get_sampling_ratio(environment)

        # Create TracerProvider with resource and sampler
        self._tracer_provider = TracerProvider(
            resource=resource,
            sampler=TraceIdRatioBased(sampling_ratio),
        )

        # Build authentication headers if configured (FR-011)
        headers = self._build_auth_headers()

        # Configure OTLP exporter based on protocol (FR-008, FR-009, FR-010)
        exporter: SpanExporter
        if self._config.otlp_protocol == "grpc":
            exporter = OTLPSpanExporter(
                endpoint=self._config.otlp_endpoint,
                headers=headers,
            )
        else:
            # HTTP protocol (FR-010)
            exporter = OTLPHttpSpanExporter(
                endpoint=self._config.otlp_endpoint,
                headers=headers,
            )

        # Add BatchSpanProcessor for async export (FR-024)
        batch_config = self._config.batch_processor
        self._span_processor = BatchSpanProcessor(
            span_exporter=exporter,
            max_queue_size=batch_config.max_queue_size,
            schedule_delay_millis=batch_config.schedule_delay_millis,
            max_export_batch_size=batch_config.max_export_batch_size,
            export_timeout_millis=batch_config.export_timeout_millis,
        )
        self._tracer_provider.add_span_processor(self._span_processor)

        # Register as global tracer provider
        trace.set_tracer_provider(self._tracer_provider)

        # Configure MeterProvider for metrics (FR-012, FR-013, FR-014)
        self._setup_meter_provider(resource, headers)

        # Configure structured logging with trace context injection (FR-015, FR-016, FR-017, FR-018)
        logging_config = self._config.logging
        configure_logging(
            log_level=logging_config.log_level,
            json_output=logging_config.json_output,
        )

        logger.info(
            "TelemetryProvider initialized",
            extra={
                "endpoint": self._config.otlp_endpoint,
                "protocol": self._config.otlp_protocol,
                "service_name": self._config.resource_attributes.service_name,
                "sampling_ratio": sampling_ratio,
                "metrics_enabled": self._meter_provider is not None,
                "log_level": logging_config.log_level,
            },
        )
        self._state = ProviderState.INITIALIZED

    def _get_noop_reason(self) -> str:
        """Get the reason for no-op mode.

        Returns:
            Human-readable reason for no-op mode.
        """
        if os.environ.get("OTEL_SDK_DISABLED", "").lower() in ("true", "1", "yes"):
            return "OTEL_SDK_DISABLED environment variable set"
        if not self._config.enabled:
            return "TelemetryConfig.enabled is False"
        return "unknown"

    def _build_auth_headers(self) -> dict[str, str] | None:
        """Build authentication headers for OTLP exporter.

        Generates HTTP headers from TelemetryAuth configuration for
        authenticating with SaaS backends (Datadog, Grafana Cloud, etc.).

        Returns:
            Dictionary of header name to value, or None if no auth configured.

        Raises:
            ValueError: If auth is configured but credentials are missing.
        """
        auth = self._config.authentication
        if auth is None:
            return None

        headers: dict[str, str] = {}

        if auth.auth_type == "api_key":
            if auth.api_key is None:
                raise ValueError("api_key is required for api_key auth_type")
            headers[auth.header_name] = auth.api_key.get_secret_value()
        elif auth.auth_type == "bearer":
            if auth.bearer_token is None:
                raise ValueError("bearer_token is required for bearer auth_type")
            headers[auth.header_name] = f"Bearer {auth.bearer_token.get_secret_value()}"

        return headers if headers else None

    def _setup_meter_provider(
        self,
        resource: Resource,
        headers: dict[str, str] | None,
    ) -> None:
        """Set up MeterProvider for metrics collection.

        Configures the MeterProvider with OTLP metric exporter and
        PeriodicExportingMetricReader for async metric export.

        Args:
            resource: OpenTelemetry Resource with service attributes.
            headers: Authentication headers for OTLP exporter, or None.

        Requirements:
            - FR-012: Pipeline run duration as histogram metric
            - FR-013: Asset materialization counts as counter metric
            - FR-014: Error rates by component as counter metric
        """
        # Determine metric endpoint (use same endpoint, different path for HTTP)
        metric_endpoint = self._config.otlp_endpoint

        # For HTTP protocol, append /v1/metrics if not already present
        if self._config.otlp_protocol == "http" and not metric_endpoint.endswith(
            "/v1/metrics"
        ):
            # Replace /v1/traces with /v1/metrics or append
            if metric_endpoint.endswith("/v1/traces"):
                metric_endpoint = metric_endpoint.rsplit("/v1/traces", 1)[0]
            metric_endpoint = metric_endpoint.rstrip("/") + "/v1/metrics"

        # Create OTLP metric exporter based on protocol
        if self._config.otlp_protocol == "grpc":
            metric_exporter = OTLPMetricExporterGrpc(
                endpoint=metric_endpoint,
                headers=headers,
            )
        else:
            metric_exporter = OTLPMetricExporterHttp(
                endpoint=metric_endpoint,
                headers=headers,
            )

        # Create PeriodicExportingMetricReader for async export
        # Default export interval is 60 seconds, can be configured via env vars
        self._metric_reader = PeriodicExportingMetricReader(
            exporter=metric_exporter,
            export_interval_millis=self._config.batch_processor.schedule_delay_millis,
            export_timeout_millis=self._config.batch_processor.export_timeout_millis,
        )

        # Create and register MeterProvider
        self._meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[self._metric_reader],
        )
        metrics.set_meter_provider(self._meter_provider)

        logger.debug(
            "MeterProvider initialized",
            extra={
                "metric_endpoint": metric_endpoint,
                "protocol": self._config.otlp_protocol,
            },
        )

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush all pending telemetry data.

        Args:
            timeout_millis: Maximum time to wait for flush (default 30s).

        Returns:
            True if flush completed successfully, False on timeout.

        Raises:
            RuntimeError: If provider is not in INITIALIZED state.
        """
        if self._state != ProviderState.INITIALIZED:
            raise RuntimeError(
                f"Cannot flush provider in state {self._state.name}. "
                "Provider must be in INITIALIZED state."
            )

        if self.is_noop:
            return True

        self._state = ProviderState.FLUSHING
        try:
            # Call SDK force_flush on tracer provider and meter provider
            result = True
            if self._tracer_provider is not None:
                result = self._tracer_provider.force_flush(timeout_millis) and result
            if self._meter_provider is not None:
                result = self._meter_provider.force_flush(timeout_millis) and result
            logger.debug(
                "TelemetryProvider force_flush completed",
                extra={"timeout_millis": timeout_millis, "success": result},
            )
            return result
        finally:
            self._state = ProviderState.INITIALIZED

    def shutdown(self, timeout_millis: int = 30000) -> None:
        """Shutdown the TelemetryProvider.

        Flushes pending data and releases resources.
        After shutdown, the provider cannot be reused.

        Args:
            timeout_millis: Maximum time to wait for shutdown (default 30s).

        Raises:
            RuntimeError: If provider is not in INITIALIZED state.
        """
        if self._state not in (ProviderState.INITIALIZED, ProviderState.FLUSHING):
            raise RuntimeError(
                f"Cannot shutdown provider in state {self._state.name}. "
                "Provider must be in INITIALIZED or FLUSHING state."
            )

        if not self.is_noop:
            # Force flush before shutdown
            self._state = ProviderState.FLUSHING

            # Shutdown the tracer provider (includes flushing)
            if self._tracer_provider is not None:
                self._tracer_provider.shutdown()

            # Shutdown the meter provider (includes flushing)
            if self._meter_provider is not None:
                self._meter_provider.shutdown()

            logger.info(
                "TelemetryProvider shutdown",
                extra={"timeout_millis": timeout_millis},
            )

        self._state = ProviderState.SHUTDOWN
        self._tracer_provider = None
        self._span_processor = None
        self._meter_provider = None
        self._metric_reader = None

    def __enter__(self) -> TelemetryProvider:
        """Enter context manager, initializing the provider.

        Returns:
            Self for use in with statement.
        """
        self.initialize()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager, shutting down the provider.

        Args:
            exc_type: Exception type if raised in context.
            exc_val: Exception value if raised in context.
            exc_tb: Exception traceback if raised in context.
        """
        if self._state == ProviderState.INITIALIZED:
            self.shutdown()

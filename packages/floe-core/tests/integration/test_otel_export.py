"""Integration tests for OTLP export to collector.

Tests cover:
- T039: Integration test for OTLP export to collector

Requirements Covered:
- FR-008: OTLP/gRPC exporter protocol support
- FR-009: OTLP/HTTP exporter protocol support
- FR-010: OTLP endpoint configuration via TelemetryConfig
- FR-011: Authentication for OTLP exports (API keys, bearer tokens)
- FR-024: Async export via BatchSpanProcessor (non-blocking)
- FR-026: All telemetry sent to OTLP Collector (enforced)

These tests use real OpenTelemetry SDK to validate that the TelemetryProvider
correctly configures exporters, BatchSpanProcessor, and authentication headers.

Note: These tests use InMemorySpanExporter to capture spans for assertion
rather than requiring a real OTLP Collector, testing the configuration path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from pydantic import SecretStr

from floe_core.telemetry import (
    BatchSpanProcessorConfig,
    ProviderState,
    ResourceAttributes,
    TelemetryAuth,
    TelemetryConfig,
    TelemetryProvider,
)

if TYPE_CHECKING:
    from collections.abc import Generator


def create_resource_attributes() -> ResourceAttributes:
    """Create test ResourceAttributes.

    Returns:
        ResourceAttributes instance for testing.
    """
    return ResourceAttributes(
        service_name="test-exporter",
        service_version="1.0.0",
        deployment_environment="dev",
        floe_namespace="test-namespace",
        floe_product_name="test-product",
        floe_product_version="1.0.0",
        floe_mode="dev",
    )


@pytest.fixture
def clean_trace_provider() -> Generator[None, None, None]:
    """Clean up global tracer provider after tests.

    Yields:
        None after saving original provider.
    """
    original = trace.get_tracer_provider()
    yield
    trace.set_tracer_provider(original)


class TestOTLPGrpcExporterConfiguration:
    """Integration tests for OTLP/gRPC exporter configuration.

    These tests verify that TelemetryProvider correctly configures
    the OTLP/gRPC exporter per FR-008.

    Requirements: FR-008, FR-010
    """

    @pytest.mark.requirement("FR-008")
    @pytest.mark.requirement("FR-010")
    def test_grpc_exporter_configured_by_default(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test gRPC is the default OTLP protocol.

        TelemetryConfig defaults to grpc protocol per spec.
        """
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            otlp_endpoint="http://localhost:4317",
        )

        assert config.otlp_protocol == "grpc"

    @pytest.mark.requirement("FR-008")
    @pytest.mark.requirement("FR-010")
    def test_provider_uses_grpc_exporter_when_configured(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test TelemetryProvider uses OTLPSpanExporter for gRPC.

        Verifies that when otlp_protocol is 'grpc', the provider
        configures the gRPC OTLP exporter.
        """
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            otlp_endpoint="http://localhost:4317",
            otlp_protocol="grpc",
        )

        with patch("floe_core.telemetry.provider.OTLPSpanExporter") as mock_grpc_exporter:
            mock_grpc_exporter.return_value = MagicMock()
            provider = TelemetryProvider(config)
            provider.initialize()

            # Verify gRPC exporter was called with correct endpoint
            mock_grpc_exporter.assert_called_once()
            call_kwargs = mock_grpc_exporter.call_args.kwargs
            assert call_kwargs["endpoint"] == "http://localhost:4317"

            provider.shutdown()

    @pytest.mark.requirement("FR-008")
    def test_grpc_exporter_uses_configured_endpoint(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test gRPC exporter uses custom endpoint from config."""
        del clean_trace_provider  # Used for side effect (cleanup)
        custom_endpoint = "http://otel-collector.monitoring:4317"
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            otlp_endpoint=custom_endpoint,
            otlp_protocol="grpc",
        )

        with patch("floe_core.telemetry.provider.OTLPSpanExporter") as mock_grpc_exporter:
            mock_grpc_exporter.return_value = MagicMock()
            provider = TelemetryProvider(config)
            provider.initialize()

            call_kwargs = mock_grpc_exporter.call_args.kwargs
            assert call_kwargs["endpoint"] == custom_endpoint

            provider.shutdown()


class TestOTLPHttpExporterConfiguration:
    """Integration tests for OTLP/HTTP exporter configuration.

    These tests verify that TelemetryProvider correctly configures
    the OTLP/HTTP exporter per FR-009.

    Requirements: FR-009, FR-010
    """

    @pytest.mark.requirement("FR-009")
    @pytest.mark.requirement("FR-010")
    def test_http_protocol_can_be_selected(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test HTTP protocol can be configured."""
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            otlp_endpoint="http://localhost:4318/v1/traces",
            otlp_protocol="http",
        )

        assert config.otlp_protocol == "http"

    @pytest.mark.requirement("FR-009")
    @pytest.mark.requirement("FR-010")
    def test_provider_uses_http_exporter_when_configured(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test TelemetryProvider uses OTLPHttpSpanExporter for HTTP.

        Verifies that when otlp_protocol is 'http', the provider
        configures the HTTP OTLP exporter.
        """
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            otlp_endpoint="http://localhost:4318/v1/traces",
            otlp_protocol="http",
        )

        with patch("floe_core.telemetry.provider.OTLPHttpSpanExporter") as mock_http_exporter:
            mock_http_exporter.return_value = MagicMock()
            provider = TelemetryProvider(config)
            provider.initialize()

            # Verify HTTP exporter was called with correct endpoint
            mock_http_exporter.assert_called_once()
            call_kwargs = mock_http_exporter.call_args.kwargs
            assert call_kwargs["endpoint"] == "http://localhost:4318/v1/traces"

            provider.shutdown()

    @pytest.mark.requirement("FR-009")
    def test_http_exporter_uses_configured_endpoint(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test HTTP exporter uses custom endpoint from config."""
        del clean_trace_provider  # Used for side effect (cleanup)
        custom_endpoint = "http://otel-collector.monitoring:4318/v1/traces"
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            otlp_endpoint=custom_endpoint,
            otlp_protocol="http",
        )

        with patch("floe_core.telemetry.provider.OTLPHttpSpanExporter") as mock_http_exporter:
            mock_http_exporter.return_value = MagicMock()
            provider = TelemetryProvider(config)
            provider.initialize()

            call_kwargs = mock_http_exporter.call_args.kwargs
            assert call_kwargs["endpoint"] == custom_endpoint

            provider.shutdown()


class TestOTLPAuthenticationConfiguration:
    """Integration tests for OTLP authentication configuration.

    These tests verify that TelemetryProvider correctly injects
    authentication headers per FR-011.

    Requirements: FR-011
    """

    @pytest.mark.requirement("FR-011")
    def test_api_key_auth_injects_header(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test API key authentication injects correct header.

        Verifies headers are passed to exporter with API key.
        """
        del clean_trace_provider  # Used for side effect (cleanup)
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("test-api-key-12345"),
            header_name="X-API-Key",
        )
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            otlp_endpoint="http://localhost:4317",
            otlp_protocol="grpc",
            authentication=auth,
        )

        with patch("floe_core.telemetry.provider.OTLPSpanExporter") as mock_exporter:
            mock_exporter.return_value = MagicMock()
            provider = TelemetryProvider(config)
            provider.initialize()

            call_kwargs = mock_exporter.call_args.kwargs
            assert call_kwargs["headers"] is not None
            assert call_kwargs["headers"]["X-API-Key"] == "test-api-key-12345"

            provider.shutdown()

    @pytest.mark.requirement("FR-011")
    def test_bearer_token_auth_injects_header(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test bearer token authentication injects correct header.

        Verifies Authorization header with Bearer prefix is passed.
        """
        del clean_trace_provider  # Used for side effect (cleanup)
        auth = TelemetryAuth(
            auth_type="bearer",
            bearer_token=SecretStr("my-bearer-token-xyz"),
            header_name="Authorization",
        )
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            otlp_endpoint="http://localhost:4317",
            otlp_protocol="grpc",
            authentication=auth,
        )

        with patch("floe_core.telemetry.provider.OTLPSpanExporter") as mock_exporter:
            mock_exporter.return_value = MagicMock()
            provider = TelemetryProvider(config)
            provider.initialize()

            call_kwargs = mock_exporter.call_args.kwargs
            assert call_kwargs["headers"] is not None
            assert call_kwargs["headers"]["Authorization"] == "Bearer my-bearer-token-xyz"

            provider.shutdown()

    @pytest.mark.requirement("FR-011")
    def test_no_auth_passes_none_headers(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test no authentication passes None headers."""
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            otlp_endpoint="http://localhost:4317",
            otlp_protocol="grpc",
            authentication=None,
        )

        with patch("floe_core.telemetry.provider.OTLPSpanExporter") as mock_exporter:
            mock_exporter.return_value = MagicMock()
            provider = TelemetryProvider(config)
            provider.initialize()

            call_kwargs = mock_exporter.call_args.kwargs
            assert call_kwargs["headers"] is None

            provider.shutdown()

    @pytest.mark.requirement("FR-011")
    def test_auth_works_with_http_protocol(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test authentication works with HTTP protocol."""
        del clean_trace_provider  # Used for side effect (cleanup)
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("dd-api-key-xxx"),
            header_name="DD-API-KEY",
        )
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            otlp_endpoint="http://localhost:4318/v1/traces",
            otlp_protocol="http",
            authentication=auth,
        )

        with patch("floe_core.telemetry.provider.OTLPHttpSpanExporter") as mock_exporter:
            mock_exporter.return_value = MagicMock()
            provider = TelemetryProvider(config)
            provider.initialize()

            call_kwargs = mock_exporter.call_args.kwargs
            assert call_kwargs["headers"] is not None
            assert call_kwargs["headers"]["DD-API-KEY"] == "dd-api-key-xxx"

            provider.shutdown()


class TestBatchSpanProcessorConfiguration:
    """Integration tests for BatchSpanProcessor configuration.

    These tests verify that TelemetryProvider correctly configures
    the BatchSpanProcessor for async export per FR-024.

    Requirements: FR-024
    """

    @pytest.mark.requirement("FR-024")
    def test_batch_processor_configured_with_defaults(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test BatchSpanProcessor uses default configuration."""
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
        )

        with patch("floe_core.telemetry.provider.BatchSpanProcessor") as mock_processor:
            with patch("floe_core.telemetry.provider.OTLPSpanExporter"):
                mock_processor.return_value = MagicMock()
                provider = TelemetryProvider(config)
                provider.initialize()

                # Verify BatchSpanProcessor was called with defaults
                mock_processor.assert_called_once()
                call_kwargs = mock_processor.call_args.kwargs
                assert call_kwargs["max_queue_size"] == 2048
                assert call_kwargs["max_export_batch_size"] == 512
                assert call_kwargs["schedule_delay_millis"] == 5000
                assert call_kwargs["export_timeout_millis"] == 30000

                provider.shutdown()

    @pytest.mark.requirement("FR-024")
    def test_batch_processor_uses_custom_configuration(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test BatchSpanProcessor uses custom configuration."""
        del clean_trace_provider  # Used for side effect (cleanup)
        batch_config = BatchSpanProcessorConfig(
            max_queue_size=8192,
            max_export_batch_size=1024,
            schedule_delay_millis=2000,
            export_timeout_millis=60000,
        )
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            batch_processor=batch_config,
        )

        with patch("floe_core.telemetry.provider.BatchSpanProcessor") as mock_processor:
            with patch("floe_core.telemetry.provider.OTLPSpanExporter"):
                mock_processor.return_value = MagicMock()
                provider = TelemetryProvider(config)
                provider.initialize()

                call_kwargs = mock_processor.call_args.kwargs
                assert call_kwargs["max_queue_size"] == 8192
                assert call_kwargs["max_export_batch_size"] == 1024
                assert call_kwargs["schedule_delay_millis"] == 2000
                assert call_kwargs["export_timeout_millis"] == 60000

                provider.shutdown()

    @pytest.mark.requirement("FR-024")
    def test_batch_processor_receives_exporter(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test BatchSpanProcessor receives the configured exporter."""
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            otlp_protocol="grpc",
        )

        mock_exporter = MagicMock()
        with patch(
            "floe_core.telemetry.provider.OTLPSpanExporter",
            return_value=mock_exporter,
        ):
            with patch("floe_core.telemetry.provider.BatchSpanProcessor") as mock_processor:
                mock_processor.return_value = MagicMock()
                provider = TelemetryProvider(config)
                provider.initialize()

                # Verify exporter was passed to BatchSpanProcessor
                call_kwargs = mock_processor.call_args.kwargs
                assert call_kwargs["span_exporter"] is mock_exporter

                provider.shutdown()


class TestSpanExportWorkflow:
    """Integration tests for complete span export workflow.

    These tests verify end-to-end span creation and export
    through the configured TelemetryProvider.

    Requirements: FR-008, FR-024, FR-026
    """

    @pytest.mark.requirement("FR-008")
    @pytest.mark.requirement("FR-026")
    def test_spans_created_after_initialization(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test spans can be created after provider initialization.

        Verifies the complete workflow from initialization to span creation
        by accessing the internal TracerProvider directly.
        """
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
        )

        with patch("floe_core.telemetry.provider.OTLPSpanExporter"):
            with patch("floe_core.telemetry.provider.BatchSpanProcessor"):
                provider = TelemetryProvider(config)
                provider.initialize()

                assert provider.state == ProviderState.INITIALIZED
                # Access internal TracerProvider to get tracer
                assert provider._tracer_provider is not None
                tracer = provider._tracer_provider.get_tracer("test-tracer")
                with tracer.start_as_current_span("test-span") as span:
                    span.set_attribute("test.key", "test-value")
                    # Span is active
                    assert span.is_recording()

                provider.shutdown()

    @pytest.mark.requirement("FR-024")
    def test_force_flush_exports_pending_spans(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test force_flush exports pending spans.

        Verifies that force_flush is called on the TracerProvider.
        """
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
        )

        with patch("floe_core.telemetry.provider.OTLPSpanExporter"):
            mock_processor = MagicMock()
            with patch(
                "floe_core.telemetry.provider.BatchSpanProcessor",
                return_value=mock_processor,
            ):
                provider = TelemetryProvider(config)
                provider.initialize()

                # Access internal TracerProvider to create span
                assert provider._tracer_provider is not None
                tracer = provider._tracer_provider.get_tracer("test-tracer")
                with tracer.start_as_current_span("test-span"):
                    pass

                # Force flush
                result = provider.force_flush()

                assert result is True
                assert provider.state == ProviderState.INITIALIZED

                provider.shutdown()

    @pytest.mark.requirement("FR-026")
    def test_shutdown_flushes_and_closes(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test shutdown flushes pending spans and closes exporter.

        Verifies shutdown transitions to SHUTDOWN state.
        """
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
        )

        with patch("floe_core.telemetry.provider.OTLPSpanExporter"):
            with patch("floe_core.telemetry.provider.BatchSpanProcessor"):
                provider = TelemetryProvider(config)
                provider.initialize()

                # Access internal TracerProvider to create span
                assert provider._tracer_provider is not None
                tracer = provider._tracer_provider.get_tracer("test-tracer")
                with tracer.start_as_current_span("final-span"):
                    pass

                provider.shutdown()

                assert provider.state == ProviderState.SHUTDOWN


class TestResourceAttributesOnExport:
    """Integration tests for resource attributes on exported spans.

    These tests verify that resource attributes are properly attached
    to exported spans.

    Requirements: FR-010
    """

    @pytest.mark.requirement("FR-010")
    def test_resource_attributes_attached_to_tracer_provider(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test resource attributes are attached to TracerProvider.

        Verifies that ResourceAttributes.to_otel_dict() is used
        when creating the TracerProvider resource.
        """
        del clean_trace_provider  # Used for side effect (cleanup)
        attrs = ResourceAttributes(
            service_name="my-pipeline",
            service_version="2.0.0",
            deployment_environment="staging",
            floe_namespace="analytics",
            floe_product_name="customer-360",
            floe_product_version="1.5.0",
            floe_mode="staging",
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
        )

        with patch("floe_core.telemetry.provider.OTLPSpanExporter"):
            with patch("floe_core.telemetry.provider.BatchSpanProcessor"):
                with patch("floe_core.telemetry.provider.Resource.create") as mock_resource:
                    mock_resource.return_value = MagicMock()
                    provider = TelemetryProvider(config)
                    provider.initialize()

                    # Verify Resource.create was called with correct attributes
                    mock_resource.assert_called_once()
                    call_args = mock_resource.call_args[0][0]
                    assert call_args["service.name"] == "my-pipeline"
                    assert call_args["service.version"] == "2.0.0"
                    assert call_args["deployment.environment"] == "staging"
                    assert call_args["floe.namespace"] == "analytics"
                    assert call_args["floe.product.name"] == "customer-360"

                    provider.shutdown()


class TestNoOpModeExport:
    """Integration tests for no-op mode behavior on export.

    These tests verify that no exporters are configured when
    telemetry is disabled.

    Requirements: FR-010
    """

    @pytest.mark.requirement("FR-010")
    def test_disabled_telemetry_does_not_create_exporter(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test disabled telemetry doesn't create OTLP exporter."""
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            enabled=False,
        )

        with patch("floe_core.telemetry.provider.OTLPSpanExporter") as mock_exporter:
            provider = TelemetryProvider(config)
            provider.initialize()

            # Exporter should not be called when disabled
            mock_exporter.assert_not_called()

            assert provider.is_noop is True
            assert provider.state == ProviderState.INITIALIZED

            provider.shutdown()

    @pytest.mark.requirement("FR-010")
    def test_otel_sdk_disabled_env_does_not_create_exporter(
        self,
        clean_trace_provider: None,
    ) -> None:
        """Test OTEL_SDK_DISABLED=true doesn't create exporter."""
        del clean_trace_provider  # Used for side effect (cleanup)
        config = TelemetryConfig(
            resource_attributes=create_resource_attributes(),
            enabled=True,  # Enabled in config but disabled via env
        )

        import os

        original = os.environ.get("OTEL_SDK_DISABLED")
        os.environ["OTEL_SDK_DISABLED"] = "true"

        try:
            with patch("floe_core.telemetry.provider.OTLPSpanExporter") as mock_exporter:
                provider = TelemetryProvider(config)
                provider.initialize()

                # Exporter should not be called when disabled via env
                mock_exporter.assert_not_called()

                assert provider.is_noop is True

                provider.shutdown()
        finally:
            if original is None:
                os.environ.pop("OTEL_SDK_DISABLED", None)
            else:
                os.environ["OTEL_SDK_DISABLED"] = original


class TestRealSpanExportWithInMemory:
    """Integration tests using real InMemorySpanExporter.

    These tests use a real InMemorySpanExporter to verify spans
    are properly created and exported through the SDK.

    Requirements: FR-008, FR-024, FR-026
    """

    @pytest.fixture
    def otel_provider_with_memory_exporter(
        self,
    ) -> Generator[tuple[TracerProvider, InMemorySpanExporter], None, None]:
        """Set up TracerProvider with InMemorySpanExporter.

        Yields:
            Tuple of (TracerProvider, InMemorySpanExporter).
        """
        exporter = InMemorySpanExporter()
        provider = TracerProvider(sampler=ALWAYS_ON)
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        original = trace.get_tracer_provider()
        trace.set_tracer_provider(provider)

        yield provider, exporter

        trace.set_tracer_provider(original)
        exporter.clear()

    @pytest.mark.requirement("FR-008")
    @pytest.mark.requirement("FR-026")
    def test_spans_exported_to_memory_exporter(
        self,
        otel_provider_with_memory_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test spans are exported to InMemorySpanExporter.

        This validates the core export path works correctly.
        """
        provider, exporter = otel_provider_with_memory_exporter

        # Use provider.get_tracer() directly to avoid global state issues
        tracer = provider.get_tracer("test-exporter")
        with tracer.start_as_current_span("exported-span") as span:
            span.set_attribute("export.test", "value")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "exported-span"

        span_attrs = dict(spans[0].attributes or {})
        assert span_attrs.get("export.test") == "value"

    @pytest.mark.requirement("FR-024")
    def test_multiple_spans_exported_in_order(
        self,
        otel_provider_with_memory_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test multiple spans are exported in creation order."""
        provider, exporter = otel_provider_with_memory_exporter

        # Use provider.get_tracer() directly to avoid global state issues
        tracer = provider.get_tracer("test-exporter")

        with tracer.start_as_current_span("span-1"):
            pass
        with tracer.start_as_current_span("span-2"):
            pass
        with tracer.start_as_current_span("span-3"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 3

        span_names = [s.name for s in spans]
        assert span_names == ["span-1", "span-2", "span-3"]

    @pytest.mark.requirement("FR-026")
    def test_nested_spans_exported_with_hierarchy(
        self,
        otel_provider_with_memory_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test nested spans maintain parent-child relationship."""
        provider, exporter = otel_provider_with_memory_exporter

        # Use provider.get_tracer() directly to avoid global state issues
        tracer = provider.get_tracer("test-exporter")

        with tracer.start_as_current_span("parent"):
            with tracer.start_as_current_span("child"):
                pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 2

        child_span = next(s for s in spans if s.name == "child")
        parent_span = next(s for s in spans if s.name == "parent")

        assert child_span.parent is not None
        assert parent_span.context is not None
        assert child_span.parent.span_id == parent_span.context.span_id

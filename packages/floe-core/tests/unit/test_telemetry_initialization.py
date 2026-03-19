"""Unit tests for ensure_telemetry_initialized() function.

Tests cover T26: OTel SDK initialization from environment variables.

This function provides a lightweight, env-var-driven entry point for
initializing OTel tracing. It reads OTEL_EXPORTER_OTLP_ENDPOINT and
OTEL_SERVICE_NAME from environment, configures TracerProvider with
OTLPSpanExporter + BatchSpanProcessor, registers it globally, resets
the tracer_factory cache, and configures structlog with trace context.

Requirements Covered:
- FR-040: OTel tracing initialization
- AC-17.1: Env-var-driven telemetry bootstrap

See Also:
    - packages/floe-core/src/floe_core/telemetry/initialization.py
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import structlog
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider as SdkMeterProvider
from opentelemetry.sdk.trace import TracerProvider


@pytest.fixture(autouse=True)
def _reset_otel_state() -> Generator[None, None, None]:
    """Reset OTel global state and tracer_factory before/after each test.

    Ensures test isolation by:
    1. Resetting the global TracerProvider to a ProxyTracerProvider
    2. Clearing the tracer_factory cache via reset_tracer()
    3. Resetting any module-level initialization flag in initialization.py
    4. Restoring structlog defaults so configure_logging() side effects
       don't leak into subsequent tests.

    Yields:
        None after resetting state.
    """
    from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider

    # Reset TracerProvider before test
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    # None, not ProxyTracerProvider() — avoids recursion in get_tracer()
    trace._TRACER_PROVIDER = None

    # Reset MeterProvider before test
    if hasattr(metrics, "_internal"):
        if hasattr(metrics._internal, "_METER_PROVIDER_SET_ONCE"):
            metrics._internal._METER_PROVIDER_SET_ONCE._done = False
        if hasattr(metrics._internal, "_METER_PROVIDER"):
            metrics._internal._METER_PROVIDER = None
        # Restore proxy so meters auto-upgrade
        if hasattr(metrics._internal, "_PROXY_METER_PROVIDER"):
            metrics._internal._PROXY_METER_PROVIDER = metrics._internal._ProxyMeterProvider()

    from floe_core.telemetry.tracer_factory import reset_tracer

    reset_tracer()

    yield

    # Reset TracerProvider after test - use SDK provider to avoid recursion
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = SdkTracerProvider()

    # Reset MeterProvider after test
    if hasattr(metrics, "_internal"):
        if hasattr(metrics._internal, "_METER_PROVIDER_SET_ONCE"):
            metrics._internal._METER_PROVIDER_SET_ONCE._done = False
        if hasattr(metrics._internal, "_METER_PROVIDER"):
            metrics._internal._METER_PROVIDER = None
        if hasattr(metrics._internal, "_PROXY_METER_PROVIDER"):
            metrics._internal._PROXY_METER_PROVIDER = metrics._internal._ProxyMeterProvider()

    reset_tracer()

    # Reset the initialization module's internal state if it exists
    try:
        import floe_core.telemetry.initialization as init_mod

        if hasattr(init_mod, "_initialized"):
            init_mod._initialized = False
        if hasattr(init_mod, "_meter_provider"):
            init_mod._meter_provider = None
        if hasattr(init_mod, "_logging_configured"):
            init_mod._logging_configured = False
    except (ImportError, AttributeError):
        pass

    # Restore structlog defaults so configure_logging() side effects
    # (LoggerFactory, JSONRenderer, cache_logger_on_first_use) don't
    # leak into other test modules.
    structlog.reset_defaults()


class TestEnsureTelemetryInitializedImport:
    """Test that ensure_telemetry_initialized is importable."""

    @pytest.mark.requirement("001-FR-040")
    def test_function_is_importable_from_initialization_module(self) -> None:
        """Test ensure_telemetry_initialized importable from initialization module.

        This is the most basic test -- the module and function must exist.
        """
        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        assert callable(ensure_telemetry_initialized)

    @pytest.mark.requirement("001-FR-040")
    def test_function_is_importable_from_telemetry_package(self) -> None:
        """Test that ensure_telemetry_initialized is re-exported from floe_core.telemetry.

        The telemetry __init__.py should re-export this for convenience.
        """
        from floe_core.telemetry import ensure_telemetry_initialized

        assert callable(ensure_telemetry_initialized)


class TestInitializationWithEndpoint:
    """Test behavior when OTEL_EXPORTER_OTLP_ENDPOINT is set."""

    @pytest.mark.requirement("001-FR-040")
    def test_sets_real_tracer_provider_when_endpoint_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that calling ensure_telemetry_initialized with endpoint env var
        registers a real SDK TracerProvider (not NoOpTracerProvider).

        A sloppy implementation that does nothing would leave the default
        ProxyTracerProvider/NoOpTracerProvider in place. This test catches that
        by verifying the provider type is opentelemetry.sdk.trace.TracerProvider.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider), (
            f"Expected SDK TracerProvider but got {type(provider).__name__}. "
            "ensure_telemetry_initialized() must call trace.set_tracer_provider() "
            "with a real TracerProvider when OTEL_EXPORTER_OTLP_ENDPOINT is set."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_provider_has_batch_span_processor(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that the TracerProvider is configured with a BatchSpanProcessor.

        A sloppy implementation might create a bare TracerProvider without
        adding a processor. Without a processor, no spans are exported.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

        # TracerProvider stores processors in _active_span_processor
        # which wraps individual processors. Check it has at least one.
        active_processor = provider._active_span_processor
        # The SynchronousMultiSpanProcessor holds a list of _span_processors
        span_processors = getattr(active_processor, "_span_processors", [])
        assert len(span_processors) > 0, (
            "TracerProvider has no span processors. "
            "ensure_telemetry_initialized() must add a BatchSpanProcessor."
        )

        # Verify it's specifically a BatchSpanProcessor
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        processor_types = [type(p).__name__ for p in span_processors]
        assert any(isinstance(p, BatchSpanProcessor) for p in span_processors), (
            f"Expected a BatchSpanProcessor but found: {processor_types}. "
            "ensure_telemetry_initialized() must use BatchSpanProcessor, not "
            "SimpleSpanProcessor or other types."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_provider_uses_otlp_span_exporter(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that the BatchSpanProcessor uses an OTLPSpanExporter.

        A sloppy implementation might use a ConsoleSpanExporter or InMemorySpanExporter
        instead of sending data to an OTLP endpoint.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

        active_processor = provider._active_span_processor
        span_processors = getattr(active_processor, "_span_processors", [])

        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        batch_processors = [p for p in span_processors if isinstance(p, BatchSpanProcessor)]
        assert len(batch_processors) > 0

        # BatchSpanProcessor stores the exporter in span_exporter attribute
        exporter = batch_processors[0].span_exporter
        exporter_type_name = type(exporter).__name__
        assert "OTLP" in exporter_type_name, (
            f"Expected OTLPSpanExporter but got {exporter_type_name}. "
            "ensure_telemetry_initialized() must use OTLPSpanExporter."
        )


class TestNoInitializationWithoutEndpoint:
    """Test behavior when OTEL_EXPORTER_OTLP_ENDPOINT is NOT set."""

    @pytest.mark.requirement("001-FR-040")
    def test_does_nothing_when_endpoint_not_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that ensure_telemetry_initialized is a no-op when OTEL_EXPORTER_OTLP_ENDPOINT
        is not in the environment.

        The provider should remain the default (ProxyTracerProvider or NoOpTracerProvider),
        NOT an SDK TracerProvider.
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert not isinstance(provider, TracerProvider), (
            "Expected NoOp/Proxy provider when OTEL_EXPORTER_OTLP_ENDPOINT is not set, "
            "but got SDK TracerProvider. ensure_telemetry_initialized() must check the "
            "env var before initializing."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_does_nothing_when_endpoint_is_empty_string(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that an empty string for OTEL_EXPORTER_OTLP_ENDPOINT is treated as unset.

        Edge case: env var exists but is empty. Should NOT initialize.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert not isinstance(provider, TracerProvider), (
            "Empty OTEL_EXPORTER_OTLP_ENDPOINT should be treated as unset. "
            "ensure_telemetry_initialized() should NOT initialize with empty endpoint."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_does_nothing_when_endpoint_is_whitespace(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that whitespace-only OTEL_EXPORTER_OTLP_ENDPOINT is treated as unset.

        Edge case: env var is set to spaces/tabs. Should NOT initialize.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "   \t  ")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert not isinstance(provider, TracerProvider), (
            "Whitespace-only OTEL_EXPORTER_OTLP_ENDPOINT should be treated as unset."
        )


class TestIdempotency:
    """Test that ensure_telemetry_initialized is idempotent."""

    @pytest.mark.requirement("AC-17.1")
    def test_calling_twice_does_not_raise(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that calling ensure_telemetry_initialized twice does not raise.

        The function must be safe to call multiple times.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()
        ensure_telemetry_initialized()  # Should not raise

    @pytest.mark.requirement("AC-17.1")
    def test_calling_twice_does_not_set_provider_twice(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that calling twice only calls trace.set_tracer_provider once.

        Without idempotency guard, the second call would attempt to
        set_tracer_provider again, which OTel warns about. A sloppy
        implementation without an _initialized flag would call it twice.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        with patch("floe_core.telemetry.initialization.trace.set_tracer_provider") as mock_set:
            ensure_telemetry_initialized()
            ensure_telemetry_initialized()

            assert mock_set.call_count == 1, (
                f"trace.set_tracer_provider was called {mock_set.call_count} times. "
                "ensure_telemetry_initialized() must be idempotent -- only initialize once."
            )

    @pytest.mark.requirement("AC-17.1")
    def test_second_call_returns_without_reconfiguring(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that the second call does not reconfigure logging or create new processors.

        A correct idempotent implementation checks a flag and returns immediately
        on subsequent calls. We verify configure_logging is called exactly once.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        with patch(
            "floe_core.telemetry.initialization.configure_logging"
        ) as mock_configure_logging:
            ensure_telemetry_initialized()
            ensure_telemetry_initialized()

            assert mock_configure_logging.call_count == 1, (
                f"configure_logging was called {mock_configure_logging.call_count} times. "
                "Idempotent initialization should only configure logging once."
            )

    @pytest.mark.requirement("AC-17.1")
    def test_idempotency_when_no_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that calling twice without endpoint is also safe (trivially idempotent)."""
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()
        ensure_telemetry_initialized()  # Should not raise

        provider = trace.get_tracer_provider()
        assert not isinstance(provider, TracerProvider)


class TestServiceName:
    """Test OTEL_SERVICE_NAME handling."""

    @pytest.mark.requirement("001-FR-040")
    def test_uses_otel_service_name_env_var(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that OTEL_SERVICE_NAME env var is used as the service.name resource attribute.

        A sloppy implementation might hardcode the service name or ignore the env var.
        We verify the Resource on the TracerProvider contains the correct service.name.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "my-custom-service")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

        resource_attrs = dict(provider.resource.attributes)
        assert resource_attrs.get("service.name") == "my-custom-service", (
            f"Expected service.name='my-custom-service' but got "
            f"'{resource_attrs.get('service.name')}'. "
            "ensure_telemetry_initialized() must read OTEL_SERVICE_NAME from env."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_defaults_service_name_to_floe_platform(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that service.name defaults to 'floe-platform' when OTEL_SERVICE_NAME is not set.

        The spec says default should be 'floe-platform'. A sloppy implementation
        might default to empty string, None, or 'unknown_service'.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

        resource_attrs = dict(provider.resource.attributes)
        assert resource_attrs.get("service.name") == "floe-platform", (
            f"Expected default service.name='floe-platform' but got "
            f"'{resource_attrs.get('service.name')}'. "
            "ensure_telemetry_initialized() must default to 'floe-platform'."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_empty_service_name_uses_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that empty OTEL_SERVICE_NAME falls back to default.

        Edge case: env var is set but empty. Should use 'floe-platform'.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

        resource_attrs = dict(provider.resource.attributes)
        assert resource_attrs.get("service.name") == "floe-platform", (
            f"Expected default 'floe-platform' for empty OTEL_SERVICE_NAME but got "
            f"'{resource_attrs.get('service.name')}'."
        )


class TestTracerFactoryReset:
    """Test that ensure_telemetry_initialized resets the tracer_factory cache."""

    @pytest.mark.requirement("AC-17.1")
    def test_calls_reset_tracer(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that ensure_telemetry_initialized calls reset_tracer() from tracer_factory.

        After setting a new global TracerProvider, the tracer_factory cache is stale.
        Cached tracers were created against the old (NoOp) provider. reset_tracer()
        must be called so that subsequent create_span()/get_tracer() calls use the
        new provider.

        A sloppy implementation that skips this step would mean all spans created
        via the tracer_factory would continue using NoOp tracers.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        with patch("floe_core.telemetry.initialization.reset_tracer") as mock_reset:
            ensure_telemetry_initialized()

            mock_reset.assert_called_once()

    @pytest.mark.requirement("AC-17.1")
    def test_reset_tracer_not_called_when_no_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that reset_tracer is NOT called when there is no endpoint (no-op path).

        When we don't initialize, there is no reason to invalidate the cache.
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        with patch("floe_core.telemetry.initialization.reset_tracer") as mock_reset:
            ensure_telemetry_initialized()

            mock_reset.assert_not_called()

    @pytest.mark.requirement("AC-17.1")
    def test_create_span_uses_new_provider_after_init(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that create_span() actually uses the new provider after initialization.

        This is the integration-level check: after ensure_telemetry_initialized(),
        creating a span should produce a real span (not a NoOp span).
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized
        from floe_core.telemetry.tracing import create_span

        ensure_telemetry_initialized()

        with create_span("test_span") as span:
            ctx = span.get_span_context()
            # A real span has a non-zero trace_id; a NoOp span has trace_id == 0
            assert ctx.trace_id != 0, (
                "create_span() returned a NoOp span after ensure_telemetry_initialized(). "
                "The tracer_factory cache was not reset, so cached NoOp tracers are still "
                "being used. ensure_telemetry_initialized() must call reset_tracer()."
            )
            assert ctx.span_id != 0, "Span has zero span_id -- indicates a NoOp span."


class TestConfigureLogging:
    """Test that ensure_telemetry_initialized configures structlog."""

    @pytest.mark.requirement("001-FR-040")
    def test_calls_configure_logging_when_initializing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that configure_logging() is invoked during initialization.

        Structlog must be configured with the add_trace_context processor
        so that log entries include trace_id and span_id.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        with patch("floe_core.telemetry.initialization.configure_logging") as mock_configure:
            ensure_telemetry_initialized()

            mock_configure.assert_called_once()

    @pytest.mark.requirement("001-FR-040")
    def test_configures_logging_even_without_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that configure_logging() IS called even when no endpoint is set.

        Structured logging with trace context injection is useful regardless
        of whether an OTLP exporter is configured — logs get trace_id from
        any active span (including ProxyTracer's NonRecordingSpan).
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        with patch("floe_core.telemetry.initialization.configure_logging") as mock_configure:
            ensure_telemetry_initialized()

            mock_configure.assert_called_once()


class TestReturnValue:
    """Test the return value / signature of ensure_telemetry_initialized."""

    @pytest.mark.requirement("001-FR-040")
    def test_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that ensure_telemetry_initialized returns None.

        It is a side-effect function -- it should not return a value.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        result = ensure_telemetry_initialized()

        assert result is None, f"ensure_telemetry_initialized() should return None, got {result!r}"

    @pytest.mark.requirement("001-FR-040")
    def test_returns_none_on_noop_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that ensure_telemetry_initialized returns None on no-op path."""
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        result = ensure_telemetry_initialized()

        assert result is None

    @pytest.mark.requirement("001-FR-040")
    def test_takes_no_arguments(self) -> None:
        """Test that ensure_telemetry_initialized takes no arguments.

        The function reads everything from environment variables.
        It should have no required parameters.
        """
        import inspect

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        sig = inspect.signature(ensure_telemetry_initialized)
        params = [
            p
            for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        assert len(params) == 0, (
            f"ensure_telemetry_initialized() should take no required arguments, "
            f"but has required params: {[p.name for p in params]}"
        )


class TestEndpointEdgeCases:
    """Test edge cases for the OTEL_EXPORTER_OTLP_ENDPOINT value."""

    @pytest.mark.requirement("001-FR-040")
    def test_endpoint_with_trailing_slash(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that endpoint with trailing slash works correctly.

        Some users set endpoints with trailing slashes. The function should
        handle this gracefully.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317/")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider), (
            "Endpoint with trailing slash should still initialize."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_invalid_scheme_does_not_initialize(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that non-http/https scheme is treated as no-op.

        The implementation validates URL scheme and returns early for
        exotic schemes like ftp://, gopher://, file://, etc. This
        prevents SSRF via the OTLPSpanExporter.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "ftp://collector:4317")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert not isinstance(provider, TracerProvider), (
            "ftp:// scheme should not initialize SDK TracerProvider."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_https_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that HTTPS endpoints are accepted.

        Production environments often use HTTPS. The function should not
        reject or mishandle HTTPS URLs.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otel.prod.example.com:443")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider), (
            "HTTPS endpoint should still initialize TracerProvider."
        )


class TestMeterProviderInitialization:
    """Test MeterProvider initialization alongside TracerProvider.

    AC-1: MeterProvider MUST be created when OTEL_EXPORTER_OTLP_ENDPOINT is set.
    AC-2: MeterProvider MUST NOT be created when endpoint is absent/empty/whitespace.
    AC-3: MeterProvider MUST NOT be created for invalid endpoint schemes.
    AC-4: Calling ensure_telemetry_initialized() twice MUST NOT create duplicate
           MeterProviders.
    """

    @pytest.mark.requirement("001-FR-040")
    def test_meter_provider_created_with_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that an SDK MeterProvider is registered when endpoint is set.

        A sloppy implementation that only creates a TracerProvider but ignores
        MeterProvider would leave the default _ProxyMeterProvider in place.
        This test catches that by verifying the exact type.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        meter_provider = metrics.get_meter_provider()
        assert isinstance(meter_provider, SdkMeterProvider), (
            f"Expected SDK MeterProvider but got {type(meter_provider).__name__}. "
            "ensure_telemetry_initialized() must create and register an SDK "
            "MeterProvider when OTEL_EXPORTER_OTLP_ENDPOINT is set."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_meter_provider_uses_periodic_metric_reader(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that MeterProvider is configured with a PeriodicExportingMetricReader.

        A sloppy implementation might create a bare MeterProvider without any
        metric reader. Without a reader, no metrics are exported. We inspect
        the internal _sdk_config to verify the reader type.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        meter_provider = metrics.get_meter_provider()
        assert isinstance(meter_provider, SdkMeterProvider)

        # SdkMeterProvider stores metric readers in _sdk_config.metric_readers
        # or _measurement_consumer._reader_storages (implementation varies).
        # Check _all_metric_readers or _sdk_config for the reader.
        metric_readers = getattr(meter_provider, "_all_metric_readers", None)
        if metric_readers is None:
            # Fallback: try _sdk_config for older SDK versions
            sdk_config = getattr(meter_provider, "_sdk_config", None)
            metric_readers = getattr(sdk_config, "metric_readers", []) if sdk_config else []

        reader_types = [type(r).__name__ for r in metric_readers]
        assert any(isinstance(r, PeriodicExportingMetricReader) for r in metric_readers), (
            f"Expected a PeriodicExportingMetricReader but found: {reader_types}. "
            "MeterProvider must be configured with PeriodicExportingMetricReader "
            "for metrics to be exported periodically."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_meter_provider_uses_otlp_metric_exporter(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that the metric reader uses an OTLPMetricExporter (gRPC).

        A sloppy implementation might use a ConsoleMetricExporter or
        InMemoryMetricExporter. This test verifies the exporter type
        is OTLP-based, consistent with the TracerProvider's OTLPSpanExporter.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")

        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        meter_provider = metrics.get_meter_provider()
        assert isinstance(meter_provider, SdkMeterProvider)

        metric_readers = getattr(meter_provider, "_all_metric_readers", None)
        if metric_readers is None:
            sdk_config = getattr(meter_provider, "_sdk_config", None)
            metric_readers = getattr(sdk_config, "metric_readers", []) if sdk_config else []

        periodic_readers = [
            r for r in metric_readers if isinstance(r, PeriodicExportingMetricReader)
        ]
        assert len(periodic_readers) > 0, "No PeriodicExportingMetricReader found"

        # PeriodicExportingMetricReader stores the exporter in _exporter
        exporter = getattr(periodic_readers[0], "_exporter", None)
        assert exporter is not None, "PeriodicExportingMetricReader has no _exporter attribute"

        exporter_type_name = type(exporter).__name__
        assert "OTLP" in exporter_type_name, (
            f"Expected OTLPMetricExporter but got {exporter_type_name}. "
            "MeterProvider must use OTLPMetricExporter (gRPC) to export "
            "metrics to the same OTLP endpoint as the TracerProvider."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_meter_provider_not_created_without_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that no SDK MeterProvider is created when endpoint is absent.

        When OTEL_EXPORTER_OTLP_ENDPOINT is not in the environment, the
        meter provider must remain the default _ProxyMeterProvider.
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        meter_provider = metrics.get_meter_provider()
        assert not isinstance(meter_provider, SdkMeterProvider), (
            "Expected default proxy meter provider when OTEL_EXPORTER_OTLP_ENDPOINT "
            f"is not set, but got {type(meter_provider).__name__}. "
            "ensure_telemetry_initialized() must NOT create a MeterProvider "
            "when the endpoint is absent."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_meter_provider_not_created_with_empty_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that empty string endpoint does not create an SDK MeterProvider.

        Edge case: env var exists but is empty. Should NOT initialize metrics.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        meter_provider = metrics.get_meter_provider()
        assert not isinstance(meter_provider, SdkMeterProvider), (
            "Empty OTEL_EXPORTER_OTLP_ENDPOINT should not create an SDK MeterProvider."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_meter_provider_not_created_with_whitespace_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that whitespace-only endpoint does not create an SDK MeterProvider.

        Edge case: env var is spaces/tabs. Should NOT initialize metrics.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "   \t  ")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        meter_provider = metrics.get_meter_provider()
        assert not isinstance(meter_provider, SdkMeterProvider), (
            "Whitespace-only OTEL_EXPORTER_OTLP_ENDPOINT should not create an SDK MeterProvider."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_meter_provider_not_created_invalid_scheme(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that invalid scheme (not http/https) does not create an SDK MeterProvider.

        If the endpoint has an ftp://, gopher://, or other exotic scheme,
        the function should skip MeterProvider creation just as it skips
        TracerProvider creation.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "ftp://invalid:4317")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        meter_provider = metrics.get_meter_provider()
        assert not isinstance(meter_provider, SdkMeterProvider), (
            "ftp:// scheme should not create an SDK MeterProvider. "
            "Only http:// and https:// are valid OTLP endpoint schemes."
        )

    @pytest.mark.requirement("001-FR-040")
    def test_idempotent_no_duplicate_meter_provider(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that calling twice does not register a second MeterProvider.

        The _initialized flag must prevent re-entry. We verify that the
        MeterProvider instance is the same on both calls, and that calling
        twice does not create a new one. We also verify via
        opentelemetry.metrics.set_meter_provider patch that it was called
        exactly once.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        # Patch at the opentelemetry.metrics module level, not at the
        # initialization module level (which may not yet import metrics).
        with patch.object(
            metrics, "set_meter_provider", wraps=metrics.set_meter_provider
        ) as mock_set_meter:
            ensure_telemetry_initialized()
            ensure_telemetry_initialized()

            assert mock_set_meter.call_count == 1, (
                f"metrics.set_meter_provider was called {mock_set_meter.call_count} "
                "times. ensure_telemetry_initialized() must be idempotent — "
                "only set MeterProvider once."
            )


class TestLoggingDecoupling:
    """Test that logging configuration is decoupled from OTLP endpoint.

    Issue #166: configure_logging() must run even without an OTLP endpoint
    so that structlog routes through stdlib logging with trace context.
    """

    @pytest.mark.requirement("FR-045")
    def test_logging_configured_without_otlp_sets_flag(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that _logging_configured flag is set after init without OTLP.

        AC-1: ensure_telemetry_initialized() without OTLP endpoint must still
        call configure_logging() and set the _logging_configured flag.
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        import floe_core.telemetry.initialization as init_mod

        assert init_mod._logging_configured is False, (
            "Precondition: _logging_configured should be False before init"
        )

        init_mod.ensure_telemetry_initialized()

        assert init_mod._logging_configured is True, (
            "_logging_configured must be True after ensure_telemetry_initialized() "
            "even when no OTLP endpoint is set."
        )

    @pytest.mark.requirement("FR-045")
    def test_logging_idempotent_without_otlp(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that configure_logging() is called only once across repeated calls.

        AC-2: The _logging_configured flag prevents redundant configure_logging()
        calls when no OTLP endpoint is set (where _initialized is never set).
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        with patch("floe_core.telemetry.initialization.configure_logging") as mock_configure:
            ensure_telemetry_initialized()
            ensure_telemetry_initialized()
            ensure_telemetry_initialized()

            assert mock_configure.call_count == 1, (
                f"configure_logging was called {mock_configure.call_count} times. "
                "The _logging_configured flag should prevent redundant calls."
            )

    @pytest.mark.requirement("FR-045")
    def test_reset_telemetry_resets_logging_flag(self) -> None:
        """Test that reset_telemetry() clears _logging_configured.

        AC-3: After reset, the next ensure_telemetry_initialized() call must
        re-configure logging (e.g. after test isolation reset).
        """
        import floe_core.telemetry.initialization as init_mod

        init_mod._logging_configured = True

        init_mod.reset_telemetry()

        assert init_mod._logging_configured is False, (
            "reset_telemetry() must set _logging_configured = False "
            "so that logging can be re-configured after reset."
        )

    @pytest.mark.requirement("FR-045")
    def test_reset_allows_logging_reconfiguration(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that after reset, configure_logging is called again.

        AC-3 behavioral: init → reset → init must call configure_logging twice.
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        with patch("floe_core.telemetry.initialization.configure_logging") as mock_configure:
            ensure_telemetry_initialized()
            assert mock_configure.call_count == 1

            from floe_core.telemetry.initialization import reset_telemetry

            reset_telemetry()

            ensure_telemetry_initialized()
            assert mock_configure.call_count == 2, (
                f"configure_logging was called {mock_configure.call_count} times. "
                "After reset_telemetry(), a new ensure_telemetry_initialized() "
                "must re-configure logging."
            )

    @pytest.mark.requirement("FR-045")
    def test_compilation_logs_contain_trace_id_via_stdlib(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Test that compilation logs include trace_id when captured via stdlib.

        AC-4: After ensure_telemetry_initialized(), compile_pipeline() logs
        captured via logging.getLogger("floe_core") contain trace_id in
        32-hex-char format.

        This is the core scenario from issue #166: structlog must route
        through stdlib logging with add_trace_context processor so that
        stdlib handlers capture structured JSON with trace context.

        Note: An OTLP endpoint is set so that ensure_telemetry_initialized()
        creates a real TracerProvider (producing spans with valid trace_id).
        Without a TracerProvider, spans have INVALID (zero) trace_id and
        add_trace_context correctly skips injection.
        """
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        # Reset structlog to clear any cached loggers from previous tests.
        # Module-level loggers (e.g. in stages.py) cache their config on
        # first use; without this reset, they continue using PrintLoggerFactory
        # instead of picking up the stdlib LoggerFactory from configure_logging().
        structlog.reset_defaults()

        from floe_core.telemetry.initialization import (
            ensure_telemetry_initialized,
            reset_telemetry,
        )

        ensure_telemetry_initialized()

        # Set up stdlib handler to capture logs from floe_core namespace
        captured: list[str] = []
        handler = _CaptureHandler(captured)
        handler.setLevel(logging.DEBUG)
        root_logger = logging.getLogger("floe_core")
        original_level = root_logger.level
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.DEBUG)

        try:
            # Write minimal spec and manifest YAML for compile_pipeline
            spec_path = tmp_path / "floe.yaml"
            spec_path.write_text(
                "apiVersion: floe.dev/v1\n"
                "kind: FloeSpec\n"
                "metadata:\n"
                "  name: test-product\n"
                "  version: 1.0.0\n"
                "transforms:\n"
                "  - name: customers\n"
                "    tags: []\n"
            )
            manifest_path = tmp_path / "manifest.yaml"
            manifest_path.write_text(
                "apiVersion: floe.dev/v1\n"
                "kind: Manifest\n"
                "metadata:\n"
                "  name: test-platform\n"
                "  version: 1.0.0\n"
                "  owner: test@example.com\n"
                "plugins:\n"
                "  compute:\n"
                "    type: duckdb\n"
                "  orchestrator:\n"
                "    type: dagster\n"
            )

            # Mock compute plugin (unit test — no real plugin installed)
            mock_plugin = MagicMock()
            mock_plugin.get_config_schema.return_value = None
            mock_plugin.generate_dbt_profile.return_value = {
                "type": "duckdb",
                "path": ":memory:",
            }

            with (
                patch(
                    "floe_core.plugins.loader.is_compatible",
                    return_value=True,
                ),
                patch(
                    "floe_core.compilation.dbt_profiles.get_compute_plugin",
                    return_value=mock_plugin,
                ),
            ):
                from floe_core.compilation.stages import compile_pipeline

                artifacts = compile_pipeline(spec_path, manifest_path)
                assert artifacts is not None, "Compilation should succeed"
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(original_level)
            reset_telemetry()
            # Clear cached structlog loggers so subsequent tests that
            # configure different logger factories get fresh proxies.
            structlog.reset_defaults()
            # structlog.reset_defaults() resets global config but does NOT
            # invalidate BoundLoggerLazyProxy instances that cached their
            # `bind` method (via cache_logger_on_first_use).  The cached
            # closure holds a reference to the old stdlib-backed logger,
            # so later tests that reconfigure with PrintLoggerFactory get
            # no output.  Delete the instance-level `bind` override to
            # restore the class method, which re-reads _CONFIG on next call.
            _clear_structlog_proxy_caches()

        # Parse captured log lines and look for trace_id
        trace_id_pattern = r"^[0-9a-f]{32}$"
        non_json_count = 0
        lines_with_trace_id: list[str] = []
        for raw_line in captured:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
                tid = parsed.get("trace_id", "")
                if re.match(trace_id_pattern, tid):
                    lines_with_trace_id.append(tid)
            except (json.JSONDecodeError, TypeError):
                non_json_count += 1
                continue

        assert len(lines_with_trace_id) > 0, (
            "No compilation log lines contain trace_id in 32-hex-char format. "
            "ensure_telemetry_initialized() must configure structlog with "
            "add_trace_context processor and stdlib LoggerFactory so that "
            "stdlib handlers capture trace context. "
            f"Captured {len(captured)} lines total, {non_json_count} non-JSON."
        )

        # All trace_ids from a single compilation should be identical
        # (propagated from the parent compile.pipeline span).
        unique_trace_ids = set(lines_with_trace_id)
        assert len(unique_trace_ids) == 1, (
            f"Expected all trace_ids to match (single parent span) but got "
            f"{len(unique_trace_ids)} distinct values: {unique_trace_ids}"
        )


def _clear_structlog_proxy_caches() -> None:
    """Clear cached ``bind`` overrides on structlog ``BoundLoggerLazyProxy`` instances.

    When ``cache_logger_on_first_use=True``, structlog replaces each proxy's
    ``bind`` method with a closure that returns the already-assembled logger.
    ``structlog.reset_defaults()`` resets the global config but does NOT
    invalidate these instance-level overrides.  Deleting the override restores
    the class-level ``bind`` which re-reads ``_CONFIG`` on the next call.
    """
    import sys

    for mod in list(sys.modules.values()):
        try:
            attrs = vars(mod)
        except TypeError:
            continue
        for attr in attrs.values():
            if getattr(type(attr), "__name__", "") == "BoundLoggerLazyProxy" and "bind" in getattr(
                attr, "__dict__", {}
            ):
                del attr.__dict__["bind"]


class _CaptureHandler(logging.Handler):
    """Logging handler that appends formatted messages to a list.

    Used in tests to capture log output in-memory for assertion
    without interfering with pytest's log capturing.
    """

    def __init__(self, target: list[str]) -> None:
        super().__init__()
        self._target = target

    def emit(self, record: logging.LogRecord) -> None:
        """Format and append log record to target list."""
        self._target.append(self.format(record))

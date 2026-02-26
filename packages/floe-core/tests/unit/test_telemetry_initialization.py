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

from collections.abc import Generator
from unittest.mock import patch

import pytest
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import ProxyTracerProvider


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

    # Reset before test
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = ProxyTracerProvider()

    from floe_core.telemetry.tracer_factory import reset_tracer

    reset_tracer()

    yield

    # Reset after test - use SDK provider to avoid recursion
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = SdkTracerProvider()

    reset_tracer()

    # Reset the initialization module's internal state if it exists
    try:
        import floe_core.telemetry.initialization as init_mod

        if hasattr(init_mod, "_initialized"):
            init_mod._initialized = False
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
    def test_does_not_configure_logging_when_no_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that configure_logging() is NOT called when no endpoint is set.

        No-op path should not configure logging. It would be a side effect
        unrelated to the no-op decision.
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        with patch("floe_core.telemetry.initialization.configure_logging") as mock_configure:
            ensure_telemetry_initialized()

            mock_configure.assert_not_called()


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

"""Unit tests for reset_telemetry() function.

Tests cover T1 RED phase for AC-35.1 and AC-35.6:
- AC-35.1: reset_telemetry() is exported from initialization module and telemetry package
- AC-35.6: reset_telemetry() calls provider.shutdown() before clearing _initialized,
  and a subsequent ensure_telemetry_initialized() creates a fresh provider

Requirements Covered:
- AC-35.1: reset_telemetry export and basic contract
- AC-35.6: Shutdown ordering and fresh provider creation

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


@pytest.fixture(autouse=True)
def _reset_otel_state() -> Generator[None, None, None]:
    """Reset OTel global state and module-level flags before/after each test.

    Ensures test isolation by:
    1. Resetting the global TracerProvider to a ProxyTracerProvider
    2. Clearing the tracer_factory cache via reset_tracer()
    3. Resetting the _initialized flag in initialization.py
    4. Restoring structlog defaults

    Yields:
        None after resetting state.
    """
    from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider

    from floe_core.telemetry.tracer_factory import reset_tracer

    # Reset before test
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    # None, not ProxyTracerProvider() — avoids recursion in get_tracer()
    trace._TRACER_PROVIDER = None
    reset_tracer()

    yield

    # Reset after test
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = SdkTracerProvider()
    reset_tracer()

    # Reset the initialization module's internal state
    import floe_core.telemetry.initialization as init_mod

    init_mod._initialized = False

    structlog.reset_defaults()


class TestResetTelemetryImport:
    """Test that reset_telemetry is importable from expected locations."""

    @pytest.mark.requirement("AC-35.1")
    def test_reset_telemetry_importable(self) -> None:
        """Test that reset_telemetry can be imported from initialization module.

        This is the most basic test -- the function must exist in the module.
        A missing function causes ImportError, which is the expected RED failure.
        """
        from floe_core.telemetry.initialization import reset_telemetry

        assert callable(reset_telemetry)

    @pytest.mark.requirement("AC-35.1")
    def test_reset_telemetry_in_all(self) -> None:
        """Test that reset_telemetry is listed in initialization.__all__.

        The function must be explicitly exported. A function that exists
        but is not in __all__ would not be part of the public API.
        """
        import floe_core.telemetry.initialization as init_mod

        assert "reset_telemetry" in init_mod.__all__, (
            f"reset_telemetry not found in initialization.__all__. "
            f"Current __all__ = {init_mod.__all__}"
        )

    @pytest.mark.requirement("AC-35.1")
    def test_reset_telemetry_importable_from_package(self) -> None:
        """Test that reset_telemetry is re-exported from floe_core.telemetry.

        The telemetry package __init__.py must re-export reset_telemetry
        for convenient access, just as it does for ensure_telemetry_initialized.
        """
        from floe_core.telemetry import reset_telemetry

        assert callable(reset_telemetry)

    @pytest.mark.requirement("AC-35.1")
    def test_reset_telemetry_in_package_all(self) -> None:
        """Test that reset_telemetry is in floe_core.telemetry.__all__.

        Being importable is not enough -- it must be in the package's __all__
        so that 'from floe_core.telemetry import *' includes it and
        documentation tools pick it up.
        """
        import floe_core.telemetry as telemetry_pkg

        assert "reset_telemetry" in telemetry_pkg.__all__, (
            "reset_telemetry not found in floe_core.telemetry.__all__. "
            "It must be added to the package's __all__ list."
        )


class TestResetTelemetryClearsFlag:
    """Test that reset_telemetry clears the _initialized flag."""

    @pytest.mark.requirement("AC-35.1")
    def test_reset_telemetry_clears_initialized_flag(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that _initialized is False after reset_telemetry() is called.

        Sequence:
        1. Call ensure_telemetry_initialized() -- sets _initialized = True
        2. Call reset_telemetry() -- must set _initialized = False
        3. Verify the flag is False

        A sloppy implementation that just shuts down the provider but
        forgets to clear the flag would leave _initialized = True,
        preventing re-initialization.
        """
        import floe_core.telemetry.initialization as init_mod

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

        init_mod.ensure_telemetry_initialized()
        assert init_mod._initialized is True, (
            "Precondition failed: _initialized should be True after ensure_telemetry_initialized()"
        )

        init_mod.reset_telemetry()
        assert init_mod._initialized is False, (
            "_initialized flag was not cleared by reset_telemetry(). "
            "The function must set _initialized = False so that a subsequent "
            "ensure_telemetry_initialized() can re-initialize."
        )

    @pytest.mark.requirement("AC-35.6")
    def test_reset_then_reinitialize_creates_new_provider(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that after reset, ensure_telemetry_initialized creates a fresh provider.

        This is the critical behavioral test: the full reset-reinitialize cycle
        must produce a NEW TracerProvider instance, not reuse the old one.

        A sloppy implementation that clears the flag but does not properly
        reset OTel state would either reuse the old provider or fail to
        set a new one.
        """
        import floe_core.telemetry.initialization as init_mod

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "svc-first")

        # First initialization
        init_mod.ensure_telemetry_initialized()
        first_provider = trace.get_tracer_provider()
        assert isinstance(first_provider, TracerProvider), (
            "Precondition: first init must set a real TracerProvider"
        )
        first_id = id(first_provider)

        # Reset OTel set_once guard so a new provider can be registered
        trace._TRACER_PROVIDER_SET_ONCE._done = False

        # Reset telemetry
        init_mod.reset_telemetry()

        # Re-initialize
        init_mod.ensure_telemetry_initialized()
        second_provider = trace.get_tracer_provider()
        assert isinstance(second_provider, TracerProvider), (
            "After reset + re-init, the global provider must be a real "
            "TracerProvider, not a NoOp/Proxy."
        )

        # Verify it is a DIFFERENT provider instance
        second_id = id(second_provider)
        assert first_id != second_id, (
            "After reset_telemetry() + ensure_telemetry_initialized(), "
            "the TracerProvider must be a NEW instance. Got the same "
            f"object (id={first_id}). The old provider was not replaced."
        )


class TestResetTelemetryCallsShutdown:
    """Test that reset_telemetry calls provider.shutdown()."""

    @pytest.mark.requirement("AC-35.6")
    def test_reset_telemetry_calls_provider_shutdown(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that reset_telemetry shuts down the current TracerProvider.

        AC-35.6 requires that provider.shutdown() is called to flush
        pending spans before clearing the _initialized flag.

        A sloppy implementation that just clears the flag without calling
        shutdown() would lose in-flight spans.
        """
        import floe_core.telemetry.initialization as init_mod

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

        init_mod.ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider), "Precondition: must have a real TracerProvider"

        # Patch shutdown on the actual provider instance to track the call
        with patch.object(provider, "shutdown", wraps=provider.shutdown) as mock_shutdown:
            init_mod.reset_telemetry()
            assert mock_shutdown.call_count == 1, (
                "reset_telemetry() must call provider.shutdown() to flush "
                "pending spans before clearing the _initialized flag."
            )

    @pytest.mark.requirement("AC-35.6")
    def test_shutdown_called_before_flag_cleared(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that provider.shutdown() is called BEFORE _initialized is cleared.

        AC-35.6 specifies ordering: shutdown first, then clear flag.
        If the flag is cleared first, a concurrent call to
        ensure_telemetry_initialized() could race and create a new
        provider while the old one is still shutting down.

        We verify ordering by recording when shutdown is called and
        checking that _initialized was still True at that point.
        """
        import floe_core.telemetry.initialization as init_mod

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

        init_mod.ensure_telemetry_initialized()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

        # Record the value of _initialized at the moment shutdown() is called
        flag_at_shutdown: list[bool] = []

        original_shutdown = provider.shutdown

        def recording_shutdown() -> None:
            """Record _initialized state, then call real shutdown."""
            flag_at_shutdown.append(init_mod._initialized)
            original_shutdown()

        with patch.object(provider, "shutdown", side_effect=recording_shutdown):
            init_mod.reset_telemetry()

        assert len(flag_at_shutdown) == 1, (
            "shutdown() was not called exactly once during reset_telemetry()"
        )
        assert flag_at_shutdown[0] is True, (
            "_initialized was already False when shutdown() was called. "
            "AC-35.6 requires shutdown BEFORE clearing the flag. "
            "The implementation must call provider.shutdown() first, "
            "then set _initialized = False."
        )
        # After reset completes, flag must be cleared
        assert init_mod._initialized is False, (
            "_initialized was not cleared after reset_telemetry() completed."
        )


class TestResetTelemetryWithNewServiceName:
    """Test that reset + reinitialize picks up new configuration."""

    @pytest.mark.requirement("AC-35.6")
    def test_reset_telemetry_allows_new_service_name(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that after reset, re-initialization uses new env var values.

        Sequence:
        1. Set OTEL_SERVICE_NAME=svc-a, initialize
        2. Verify provider has service.name=svc-a
        3. Reset telemetry
        4. Set OTEL_SERVICE_NAME=svc-b, re-initialize
        5. Verify provider has service.name=svc-b

        A sloppy implementation that caches configuration or does not
        truly re-read env vars on re-initialization would still show svc-a.
        """
        import floe_core.telemetry.initialization as init_mod

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "svc-a")

        # First initialization
        init_mod.ensure_telemetry_initialized()
        first_provider = trace.get_tracer_provider()
        assert isinstance(first_provider, TracerProvider)
        first_attrs = dict(first_provider.resource.attributes)
        assert first_attrs.get("service.name") == "svc-a", (
            f"Precondition: first provider should have service.name=svc-a, "
            f"got '{first_attrs.get('service.name')}'"
        )

        # Allow OTel to accept a new provider
        trace._TRACER_PROVIDER_SET_ONCE._done = False

        # Reset
        init_mod.reset_telemetry()

        # Change config
        monkeypatch.setenv("OTEL_SERVICE_NAME", "svc-b")

        # Re-initialize
        init_mod.ensure_telemetry_initialized()
        second_provider = trace.get_tracer_provider()
        assert isinstance(second_provider, TracerProvider), (
            "After reset + re-init, must have a real TracerProvider"
        )
        second_attrs = dict(second_provider.resource.attributes)
        assert second_attrs.get("service.name") == "svc-b", (
            f"After reset and re-init with OTEL_SERVICE_NAME=svc-b, "
            f"expected service.name='svc-b' but got "
            f"'{second_attrs.get('service.name')}'. "
            f"reset_telemetry() must fully clear state so that "
            f"ensure_telemetry_initialized() re-reads env vars."
        )

    @pytest.mark.requirement("AC-35.6")
    def test_reset_telemetry_allows_new_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that after reset, re-initialization uses a new endpoint.

        Similar to service name test but verifies the exporter endpoint
        is re-read from the environment, not cached from first init.
        """
        import floe_core.telemetry.initialization as init_mod

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector-a:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

        init_mod.ensure_telemetry_initialized()
        first_provider = trace.get_tracer_provider()
        assert isinstance(first_provider, TracerProvider)

        # Allow OTel to accept a new provider
        trace._TRACER_PROVIDER_SET_ONCE._done = False

        init_mod.reset_telemetry()

        # Change endpoint
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector-b:4317")

        init_mod.ensure_telemetry_initialized()
        second_provider = trace.get_tracer_provider()
        assert isinstance(second_provider, TracerProvider)

        # The providers must be different instances (new exporter config)
        assert first_provider is not second_provider, (
            "After reset + re-init with new endpoint, must create a "
            "new TracerProvider. Got the same instance."
        )


class TestResetTelemetryEdgeCases:
    """Test edge cases for reset_telemetry."""

    @pytest.mark.requirement("AC-35.1")
    def test_reset_telemetry_when_not_initialized(self) -> None:
        """Test that reset_telemetry does not raise when not initialized.

        If ensure_telemetry_initialized was never called (or the no-op
        path was taken), reset_telemetry must be safe to call -- it
        should not crash or raise.
        """
        import floe_core.telemetry.initialization as init_mod

        assert init_mod._initialized is False, (
            "Precondition: _initialized should be False before any init"
        )

        # Must not raise
        init_mod.reset_telemetry()

        # Flag should remain False
        assert init_mod._initialized is False

    @pytest.mark.requirement("AC-35.1")
    def test_reset_telemetry_called_twice(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that calling reset_telemetry twice does not raise.

        Double-reset must be safe (idempotent). The second call should
        be a no-op since there is nothing to shut down.
        """
        import floe_core.telemetry.initialization as init_mod

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        init_mod.ensure_telemetry_initialized()
        init_mod.reset_telemetry()
        init_mod.reset_telemetry()  # Must not raise

        assert init_mod._initialized is False

    @pytest.mark.requirement("AC-35.1")
    def test_reset_telemetry_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that reset_telemetry returns None.

        It is a side-effect function -- it should not return a value.
        """
        import floe_core.telemetry.initialization as init_mod

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        init_mod.ensure_telemetry_initialized()
        result = init_mod.reset_telemetry()

        assert result is None, f"reset_telemetry() should return None, got {result!r}"

    @pytest.mark.requirement("AC-35.6")
    def test_reset_telemetry_full_lifecycle(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test full init-reset-init-reset lifecycle.

        Exercises the complete cycle twice to verify no accumulated state
        corruption. Each cycle must produce a fresh, functional provider.
        """
        import floe_core.telemetry.initialization as init_mod

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SERVICE_NAME", "cycle-1")

        # Cycle 1: init + reset
        init_mod.ensure_telemetry_initialized()
        provider_1 = trace.get_tracer_provider()
        assert isinstance(provider_1, TracerProvider)
        attrs_1 = dict(provider_1.resource.attributes)
        assert attrs_1.get("service.name") == "cycle-1"

        trace._TRACER_PROVIDER_SET_ONCE._done = False
        init_mod.reset_telemetry()
        assert init_mod._initialized is False

        # Cycle 2: init + reset with different config
        monkeypatch.setenv("OTEL_SERVICE_NAME", "cycle-2")
        init_mod.ensure_telemetry_initialized()
        provider_2 = trace.get_tracer_provider()
        assert isinstance(provider_2, TracerProvider)
        attrs_2 = dict(provider_2.resource.attributes)
        assert attrs_2.get("service.name") == "cycle-2", (
            f"Cycle 2 should have service.name='cycle-2', got '{attrs_2.get('service.name')}'"
        )

        trace._TRACER_PROVIDER_SET_ONCE._done = False
        init_mod.reset_telemetry()
        assert init_mod._initialized is False

        # Verify providers were distinct
        assert provider_1 is not provider_2, (
            "Each init cycle must produce a new TracerProvider instance"
        )

    @pytest.mark.requirement("AC-35.1")
    def test_reset_telemetry_takes_no_arguments(self) -> None:
        """Test that reset_telemetry takes no required arguments.

        Like ensure_telemetry_initialized, it should be a zero-argument function.
        """
        import inspect

        from floe_core.telemetry.initialization import reset_telemetry

        sig = inspect.signature(reset_telemetry)
        required_params = [
            p
            for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        assert len(required_params) == 0, (
            f"reset_telemetry() should take no required arguments, "
            f"but has: {[p.name for p in required_params]}"
        )

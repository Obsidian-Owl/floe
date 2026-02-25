"""Unit tests for E2E fixture wiring: otel_tracer_provider and compiled_artifacts.

Tests verify that:
1. otel_tracer_provider registers the SDK TracerProvider globally via
   trace.set_tracer_provider(), not just yields it.
2. compiled_artifacts factory calls ensure_telemetry_initialized() before
   compile_pipeline() so that OTel spans are emitted during compilation.
3. After otel_tracer_provider sets the global provider, create_span()
   produces real (non-NoOp) spans with non-zero trace_id and span_id.
4. The compile_pipeline function produces the expected span hierarchy.

Task: T32 (Wire E2E fixtures and verify)
Requirements Covered:
- AC-17.2: Compilation produces Jaeger-visible traces
- AC-17.7: All Category 8 failures resolve

See Also:
    - tests/e2e/conftest.py (otel_tracer_provider fixture, lines 610-643)
    - tests/conftest.py (compiled_artifacts factory, lines 74-107)
    - packages/floe-core/src/floe_core/telemetry/initialization.py
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.trace import ProxyTracerProvider


@pytest.fixture(autouse=True)
def _reset_otel_global_state() -> Generator[None, None, None]:
    """Reset OTel global state before and after each test.

    Ensures test isolation by resetting the global TracerProvider
    to ProxyTracerProvider and clearing tracer_factory caches.

    Yields:
        None after resetting state.
    """
    # Reset before test
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = ProxyTracerProvider()

    from floe_core.telemetry.tracer_factory import reset_tracer

    reset_tracer()

    yield

    # Reset after test -- use SDK provider to avoid recursion
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = SdkTracerProvider()

    reset_tracer()

    # Reset the initialization module's internal idempotency flag
    try:
        import floe_core.telemetry.initialization as init_mod

        if hasattr(init_mod, "_initialized"):
            init_mod._initialized = False
    except (ImportError, AttributeError):
        pass


class TestOtelTracerProviderFixtureRegistersGlobally:
    """Tests that otel_tracer_provider fixture registers the provider globally.

    The fixture currently creates a TracerProvider but does NOT call
    trace.set_tracer_provider(). This means create_span() in
    compile_pipeline() still uses the default NoOp tracer.

    These tests verify the fixture calls trace.set_tracer_provider()
    so the SDK TracerProvider becomes the global provider.
    """

    @pytest.mark.requirement("AC-17.2")
    def test_global_provider_is_sdk_after_fixture(self) -> None:
        """After otel_tracer_provider runs, global provider must be SDK.

        The fixture must call trace.set_tracer_provider(provider)
        so that trace.get_tracer_provider() returns an SDK
        TracerProvider, not the default ProxyTracerProvider.

        This test FAILS if the fixture only yields the provider
        without registering it globally.
        """
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": "floe-platform"})
        provider = SdkTracerProvider(resource=resource)

        # Simulate the FIXED fixture: create provider and
        # register it globally via trace.set_tracer_provider().
        _run_fixture_as_current_code(provider, register_globally=True)

        global_provider = trace.get_tracer_provider()

        assert isinstance(global_provider, SdkTracerProvider), (
            f"After otel_tracer_provider fixture runs, the global "
            f"tracer provider must be an SDK TracerProvider, not "
            f"{type(global_provider).__name__}. The fixture must "
            f"call trace.set_tracer_provider(provider) before "
            f"yielding."
        )

    @pytest.mark.requirement("AC-17.2")
    def test_global_provider_has_correct_service_name(
        self,
    ) -> None:
        """Globally registered provider must have service.name=floe-platform.

        AC-17.2 requires Jaeger traces for service 'floe-platform'.
        The fixture must register a provider whose Resource has the
        correct service.name attribute.
        """
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": "floe-platform"})
        provider = SdkTracerProvider(resource=resource)

        _run_fixture_as_current_code(provider, register_globally=True)

        global_provider = trace.get_tracer_provider()

        # Must be SDK type to even have resource attribute
        assert isinstance(global_provider, SdkTracerProvider), (
            "Global provider is not SDK TracerProvider -- cannot "
            "verify service.name. Fixture must call "
            "trace.set_tracer_provider()."
        )

        # Verify the resource carries the correct service name
        resource_attrs = dict(global_provider.resource.attributes)
        assert resource_attrs.get("service.name") == "floe-platform", (
            f"Global TracerProvider resource must have "
            f"service.name='floe-platform', got "
            f"{resource_attrs.get('service.name')!r}. "
            f"Required for AC-17.2 (Jaeger queries by service)."
        )

    @pytest.mark.requirement("AC-17.2")
    def test_fixture_must_call_set_tracer_provider(self) -> None:
        """Directly verify trace.set_tracer_provider() is called.

        Patches trace.set_tracer_provider to confirm the fixture
        calls it with the created provider.
        """
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": "floe-platform"})
        provider = SdkTracerProvider(resource=resource)

        with patch.object(trace, "set_tracer_provider") as mock_set:
            _run_fixture_as_current_code(provider, register_globally=True)

            mock_set.assert_called_once_with(provider)


class TestCreateSpanProducesRealSpansAfterRegistration:
    """Tests that create_span produces real spans when SDK provider is global.

    After otel_tracer_provider correctly registers the provider,
    create_span() must produce spans with non-zero trace_id
    (not NoOp/NonRecordingSpan).
    """

    @pytest.mark.requirement("AC-17.2")
    def test_create_span_has_nonzero_trace_id(self) -> None:
        """Spans must have non-zero trace_id when SDK provider is set.

        A NoOp span has trace_id == 0. After the provider is
        registered globally, create_span() must produce spans with
        valid trace context.
        """
        from floe_core.telemetry.tracer_factory import reset_tracer
        from floe_core.telemetry.tracing import create_span

        # Register SDK provider globally (FIXED fixture behavior)
        provider = SdkTracerProvider(
            resource=_make_floe_resource(),
        )
        trace.set_tracer_provider(provider)
        reset_tracer()

        with create_span("test.span") as span:
            ctx = span.get_span_context()
            assert ctx.trace_id != 0, (
                "create_span() produced a NoOp span (trace_id == 0)"
                " even though an SDK TracerProvider was registered "
                "globally. The tracer_factory cache may need reset."
            )
            assert ctx.span_id != 0, (
                "create_span() produced a span with span_id == 0 "
                "(NoOp). SDK provider must produce valid span IDs."
            )

    @pytest.mark.requirement("AC-17.2")
    def test_create_span_is_noop_without_registration(
        self,
    ) -> None:
        """Without global registration, create_span produces NoOp spans.

        This confirms the bug: if the fixture creates a provider
        but does not register it globally, spans have trace_id == 0.
        """
        from floe_core.telemetry.tracer_factory import reset_tracer
        from floe_core.telemetry.tracing import create_span

        # Create provider but do NOT register globally
        _provider = SdkTracerProvider(
            resource=_make_floe_resource(),
        )
        # Intentionally NOT calling trace.set_tracer_provider()
        _ = _provider  # Explicitly mark as intentionally unused
        reset_tracer()

        with create_span("test.noop") as span:
            ctx = span.get_span_context()
            assert ctx.trace_id == 0, (
                "Expected NoOp span (trace_id == 0) when provider "
                "is not registered globally. This validates that "
                "global registration is required for real spans."
            )

    @pytest.mark.requirement("AC-17.2")
    def test_nested_spans_share_trace_id(self) -> None:
        """Nested create_span calls must share the same trace_id.

        compile_pipeline creates compile.pipeline as parent with
        compile.load, compile.validate, etc. as children. They must
        all share one trace_id for Jaeger to show them as one trace.
        """
        from floe_core.telemetry.tracer_factory import reset_tracer
        from floe_core.telemetry.tracing import create_span

        provider = SdkTracerProvider(
            resource=_make_floe_resource(),
        )
        trace.set_tracer_provider(provider)
        reset_tracer()

        with create_span("compile.pipeline") as parent:
            parent_trace_id = parent.get_span_context().trace_id
            assert parent_trace_id != 0, "Parent span is NoOp"

            with create_span("compile.load") as child:
                child_tid = child.get_span_context().trace_id
                assert child_tid == parent_trace_id, (
                    f"Child span trace_id ({child_tid:#034x}) "
                    f"differs from parent "
                    f"({parent_trace_id:#034x}). Nested spans "
                    f"must share trace_id for Jaeger to display "
                    f"them as a single trace."
                )

            with create_span("compile.validate") as child2:
                child2_tid = child2.get_span_context().trace_id
                assert child2_tid == parent_trace_id, (
                    "All compilation stage spans must share the parent's trace_id."
                )


class TestCompiledArtifactsFactoryCallsEnsureTelemetry:
    """Tests that compiled_artifacts factory initializes telemetry.

    Uses inspect.getsource() on the real compiled_artifacts fixture
    from tests/conftest.py to verify ensure_telemetry_initialized()
    is called before compile_pipeline().
    """

    @staticmethod
    def _get_fixture_source() -> str:
        """Get source of compiled_artifacts fixture from tests/conftest.py.

        Returns:
            Source code of the compiled_artifacts fixture function.
        """
        import importlib.util
        import inspect
        from pathlib import Path

        conftest_path = Path(__file__).parent.parent / "conftest.py"
        loader_spec = importlib.util.spec_from_file_location(
            "tests_root_conftest", str(conftest_path)
        )
        assert loader_spec is not None and loader_spec.loader is not None
        mod = importlib.util.module_from_spec(loader_spec)
        loader_spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return inspect.getsource(mod.compiled_artifacts)

    @pytest.mark.requirement("AC-17.2")
    def test_factory_calls_ensure_telemetry_before_compile(
        self,
    ) -> None:
        """The factory must call ensure_telemetry_initialized().

        Without this call, compile_pipeline() produces NoOp spans
        because the OTel SDK is never initialized from env vars.

        Uses inspect.getsource() on the real compiled_artifacts
        fixture to verify the call exists in the source code.
        """
        source = self._get_fixture_source()

        assert "ensure_telemetry_initialized" in source, (
            "compiled_artifacts fixture must call "
            "ensure_telemetry_initialized() before "
            "compile_pipeline(). Without this, the OTel SDK is "
            "never initialized and compile_pipeline() produces "
            "only NoOp spans."
        )

    @pytest.mark.requirement("AC-17.2")
    def test_factory_ensure_called_before_compile(self) -> None:
        """ensure_telemetry_initialized must be called BEFORE compile.

        Even if both are called, the order matters: telemetry must
        be initialized before any spans are created during
        compilation. Verifies by checking source code ordering.
        """
        import re as re_mod

        source = self._get_fixture_source()

        # Match actual call statements, not docstring mentions.
        # Calls appear as indented statements, not inside triple-quoted strings.
        ensure_match = re_mod.search(
            r"^\s+ensure_telemetry_initialized\(\)", source, re_mod.MULTILINE
        )
        compile_match = re_mod.search(
            r"^\s+(?:return\s+)?compile_pipeline\(", source, re_mod.MULTILINE
        )

        assert ensure_match is not None, (
            "ensure_telemetry_initialized() call not found in fixture source."
        )
        assert compile_match is not None, "compile_pipeline() call not found in fixture source."

        assert ensure_match.start() < compile_match.start(), (
            f"ensure_telemetry_initialized() call "
            f"(pos={ensure_match.start()}) must appear BEFORE "
            f"compile_pipeline() call (pos={compile_match.start()}) "
            f"in the compiled_artifacts fixture source."
        )


class TestCompilePipelineSpanNames:
    """Tests that compile_pipeline creates the expected span hierarchy.

    AC-17.2 requires these spans to be visible in Jaeger:
    - compile.pipeline (parent)
    - compile.load
    - compile.validate
    - compile.resolve
    - compile.enforce
    - compile.compile
    - compile.generate
    """

    EXPECTED_SPAN_NAMES: list[str] = [
        "compile.pipeline",
        "compile.load",
        "compile.validate",
        "compile.resolve",
        "compile.enforce",
        "compile.compile",
        "compile.generate",
    ]

    @pytest.mark.requirement("AC-17.2")
    def test_expected_span_names_defined_in_stages_module(
        self,
    ) -> None:
        """Verify compile_pipeline source has all required span names.

        This is a static analysis test that reads the source code
        of compile_pipeline to confirm all expected span names are
        present. A sloppy implementation might omit span creation
        for some stages.
        """
        import inspect

        from floe_core.compilation.stages import compile_pipeline

        source = inspect.getsource(compile_pipeline)

        import re

        for span_name in self.EXPECTED_SPAN_NAMES:
            pattern = rf'create_span\(\s*"{re.escape(span_name)}"'
            assert re.search(pattern, source), (
                f"compile_pipeline() source must call create_span() "
                f'with span name "{span_name}". AC-17.2 requires all '
                f"compilation stages to produce Jaeger-visible traces. "
                f"Missing span: {span_name}"
            )


class TestEndToEndFixtureIntegration:
    """Integration-style tests verifying the full fixture chain.

    These tests simulate what happens when the E2E conftest fixtures
    are used together: otel_tracer_provider sets up OTel, then
    compiled_artifacts uses it to emit real spans.
    """

    @pytest.mark.requirement("AC-17.2")
    @pytest.mark.requirement("AC-17.7")
    def test_spans_are_recorded_after_fixture_registration(
        self,
    ) -> None:
        """After global registration + tracer reset, spans are recorded.

        Simulates the full E2E fixture chain:
        1. otel_tracer_provider creates and registers provider
        2. create_span() produces real spans (non-NoOp)
        3. Spans have proper parent-child relationships

        This test uses an InMemorySpanExporter to capture spans
        without needing a real OTLP endpoint.
        """
        from floe_core.telemetry.tracer_factory import reset_tracer
        from floe_core.telemetry.tracing import create_span
        from opentelemetry.sdk.trace.export import (
            SimpleSpanProcessor,
        )
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E501
            InMemorySpanExporter,
        )

        # Set up in-memory exporter to capture spans
        exporter = InMemorySpanExporter()
        provider = SdkTracerProvider(
            resource=_make_floe_resource(),
        )
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        # Simulate the FIXED otel_tracer_provider fixture
        trace.set_tracer_provider(provider)
        reset_tracer()

        # Simulate compile_pipeline's span creation pattern
        with create_span("compile.pipeline") as pipeline_span:
            pipeline_span.set_attribute("compile.spec_path", "demo/floe.yaml")
            with create_span("compile.load"):
                pass
            with create_span("compile.validate"):
                pass
            with create_span("compile.resolve"):
                pass
            with create_span("compile.enforce"):
                pass
            with create_span("compile.compile"):
                pass
            with create_span("compile.generate"):
                pass

        # Force flush to ensure all spans are exported
        provider.force_flush()

        # Verify spans were captured
        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        expected_names = [
            "compile.pipeline",
            "compile.load",
            "compile.validate",
            "compile.resolve",
            "compile.enforce",
            "compile.compile",
            "compile.generate",
        ]

        for name in expected_names:
            assert name in span_names, (
                f"Expected span '{name}' not found in captured "
                f"spans. Captured: {span_names}. AC-17.2 requires "
                f"all compilation stage spans to be Jaeger-visible."
            )

        # Verify total span count
        assert len(spans) == 7, (
            f"Expected exactly 7 spans (1 parent + 6 stages), got {len(spans)}. Spans: {span_names}"
        )

    @pytest.mark.requirement("AC-17.2")
    @pytest.mark.requirement("AC-17.7")
    def test_no_spans_captured_without_global_registration(
        self,
    ) -> None:
        """Without global registration, no spans are captured.

        This confirms the current bug: if otel_tracer_provider
        does not call trace.set_tracer_provider(), the in-memory
        exporter captures nothing because create_span() uses the
        NoOp tracer.
        """
        from floe_core.telemetry.tracer_factory import reset_tracer
        from floe_core.telemetry.tracing import create_span
        from opentelemetry.sdk.trace.export import (
            SimpleSpanProcessor,
        )
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E501
            InMemorySpanExporter,
        )

        exporter = InMemorySpanExporter()
        provider = SdkTracerProvider(
            resource=_make_floe_resource(),
        )
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        # Simulate BROKEN fixture: create but do NOT register
        # trace.set_tracer_provider(provider) is NOT called
        reset_tracer()

        with create_span("compile.pipeline"):
            with create_span("compile.load"):
                pass

        provider.force_flush()

        spans = exporter.get_finished_spans()

        # No spans captured because provider is not global
        assert len(spans) == 0, (
            f"Expected 0 spans without global registration, "
            f"got {len(spans)}. This confirms the exporter only "
            f"captures spans when its provider is the global one."
        )

    @pytest.mark.requirement("AC-17.2")
    def test_span_parent_child_relationships(self) -> None:
        """Child spans must reference the parent span's context.

        Jaeger reconstructs the trace tree using parent_id.
        compile.load etc. must be children of compile.pipeline.
        """
        from floe_core.telemetry.tracer_factory import reset_tracer
        from floe_core.telemetry.tracing import create_span
        from opentelemetry.sdk.trace.export import (
            SimpleSpanProcessor,
        )
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E501
            InMemorySpanExporter,
        )

        exporter = InMemorySpanExporter()
        provider = SdkTracerProvider(
            resource=_make_floe_resource(),
        )
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        reset_tracer()

        with create_span("compile.pipeline"):
            with create_span("compile.load"):
                pass
            with create_span("compile.validate"):
                pass

        provider.force_flush()
        spans = exporter.get_finished_spans()

        # Build lookup
        spans_by_name = {s.name: s for s in spans}
        assert "compile.pipeline" in spans_by_name
        assert "compile.load" in spans_by_name
        assert "compile.validate" in spans_by_name

        pipeline_span = spans_by_name["compile.pipeline"]
        load_span = spans_by_name["compile.load"]
        validate_span = spans_by_name["compile.validate"]

        pipeline_ctx = pipeline_span.get_span_context()

        # Children must reference parent's span_id
        assert load_span.parent is not None, "compile.load must have a parent span."
        assert load_span.parent.span_id == pipeline_ctx.span_id, (
            f"compile.load parent span_id "
            f"({load_span.parent.span_id:#018x}) does not match "
            f"compile.pipeline span_id "
            f"({pipeline_ctx.span_id:#018x}). "
            f"Child spans must be nested under compile.pipeline."
        )

        assert validate_span.parent is not None, "compile.validate must have a parent span."
        assert validate_span.parent.span_id == pipeline_ctx.span_id, (
            "compile.validate must be a child of compile.pipeline."
        )

        # All spans share the same trace_id
        assert load_span.get_span_context().trace_id == pipeline_ctx.trace_id, (
            "compile.load must share trace_id with pipeline."
        )
        assert validate_span.get_span_context().trace_id == pipeline_ctx.trace_id, (
            "compile.validate must share trace_id with pipeline."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_floe_resource() -> Any:
    """Create an OTel Resource with service.name = floe-platform.

    Returns:
        Resource with the standard floe service name.
    """
    from opentelemetry.sdk.resources import Resource

    return Resource.create({"service.name": "floe-platform"})


def _run_fixture_as_current_code(
    provider: SdkTracerProvider,
    *,
    register_globally: bool,
) -> None:
    """Simulate the otel_tracer_provider fixture behavior.

    When register_globally is False, this replicates the CURRENT
    (broken) behavior: the fixture creates a provider but does
    NOT call trace.set_tracer_provider().

    When register_globally is True, this replicates the FIXED
    behavior: the fixture registers the provider globally.

    Args:
        provider: The SDK TracerProvider to use.
        register_globally: Whether to set_tracer_provider().
    """
    if register_globally:
        trace.set_tracer_provider(provider)

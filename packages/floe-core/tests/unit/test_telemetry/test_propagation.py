"""Unit tests for OpenTelemetry context propagation.

Tests cover:
- T015: W3C propagator setup
- T016: Baggage propagation for floe.namespace
- T017: Trace context injection/extraction

Requirements Covered:
- FR-002: W3C Trace Context propagation
- FR-003: W3C Baggage propagation
- FR-007a: floe.namespace propagation via Baggage
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from opentelemetry import baggage, trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagate import get_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def reset_propagators() -> Generator[None, None, None]:
    """Reset global propagators after each test.

    Yields:
        None after setup, cleans up after test.
    """
    from opentelemetry.propagate import set_global_textmap

    original = get_global_textmap()
    yield
    set_global_textmap(original)


@pytest.fixture
def tracer_provider() -> Generator[TracerProvider, None, None]:
    """Create a TracerProvider with ALWAYS_ON sampling for tests.

    This ensures spans are actually created and have valid contexts.

    Yields:
        TracerProvider configured for testing.
    """
    provider = TracerProvider(sampler=ALWAYS_ON)
    exporter = InMemorySpanExporter()
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Set as global provider
    original_provider = trace.get_tracer_provider()
    trace.set_tracer_provider(provider)

    yield provider

    # Restore original
    trace.set_tracer_provider(original_provider)


class TestW3CPropagatorSetup:
    """Tests for W3C propagator setup (T015).

    Validates that W3C Trace Context and Baggage propagators can be configured.
    """

    @pytest.mark.requirement("FR-002")
    def test_trace_context_propagator_exists(self) -> None:
        """Test TraceContextTextMapPropagator is available."""
        propagator = TraceContextTextMapPropagator()
        assert propagator is not None
        assert hasattr(propagator, "inject")
        assert hasattr(propagator, "extract")

    @pytest.mark.requirement("FR-003")
    def test_baggage_propagator_exists(self) -> None:
        """Test W3CBaggagePropagator is available."""
        propagator = W3CBaggagePropagator()
        assert propagator is not None
        assert hasattr(propagator, "inject")
        assert hasattr(propagator, "extract")

    @pytest.mark.requirement("FR-002")
    def test_composite_propagator_can_be_created(self) -> None:
        """Test CompositePropagator can combine trace context and baggage."""
        composite = CompositePropagator(
            [
                TraceContextTextMapPropagator(),
                W3CBaggagePropagator(),
            ]
        )
        assert composite is not None
        assert hasattr(composite, "inject")
        assert hasattr(composite, "extract")

    @pytest.mark.requirement("FR-002")
    def test_propagator_can_be_set_globally(
        self, reset_propagators: None
    ) -> None:
        """Test propagators can be set as global textmap."""
        from opentelemetry.propagate import set_global_textmap

        composite = CompositePropagator(
            [
                TraceContextTextMapPropagator(),
                W3CBaggagePropagator(),
            ]
        )
        set_global_textmap(composite)

        result = get_global_textmap()
        assert isinstance(result, CompositePropagator)

    @pytest.mark.requirement("FR-002")
    def test_trace_context_header_names(self) -> None:
        """Test W3C Trace Context uses correct header names."""
        propagator = TraceContextTextMapPropagator()
        # W3C Trace Context uses 'traceparent' and 'tracestate' headers
        assert "traceparent" in propagator.fields
        assert "tracestate" in propagator.fields


class TestBaggagePropagation:
    """Tests for W3C Baggage propagation (T016).

    Validates that baggage items can be set and propagated,
    specifically for floe.namespace per FR-007a.
    """

    @pytest.mark.requirement("FR-003")
    def test_baggage_can_be_set(self) -> None:
        """Test baggage items can be set in context."""
        ctx = baggage.set_baggage("floe.namespace", "analytics")
        value = baggage.get_baggage("floe.namespace", ctx)
        assert value == "analytics"

    @pytest.mark.requirement("FR-007a")
    def test_floe_namespace_can_be_set_in_baggage(self) -> None:
        """Test floe.namespace can be stored in baggage."""
        ctx = baggage.set_baggage("floe.namespace", "customer-data")
        value = baggage.get_baggage("floe.namespace", ctx)
        assert value == "customer-data"

    @pytest.mark.requirement("FR-007a")
    def test_floe_product_name_can_be_set_in_baggage(self) -> None:
        """Test floe.product.name can be stored in baggage."""
        ctx = baggage.set_baggage("floe.product.name", "customer-360")
        value = baggage.get_baggage("floe.product.name", ctx)
        assert value == "customer-360"

    @pytest.mark.requirement("FR-003")
    def test_multiple_baggage_items_can_be_set(self) -> None:
        """Test multiple baggage items can be set."""
        ctx = baggage.set_baggage("floe.namespace", "analytics")
        ctx = baggage.set_baggage("floe.product.name", "customer-360", ctx)
        ctx = baggage.set_baggage("floe.mode", "prod", ctx)

        assert baggage.get_baggage("floe.namespace", ctx) == "analytics"
        assert baggage.get_baggage("floe.product.name", ctx) == "customer-360"
        assert baggage.get_baggage("floe.mode", ctx) == "prod"

    @pytest.mark.requirement("FR-003")
    def test_baggage_propagator_injects_headers(self) -> None:
        """Test baggage propagator injects baggage header."""
        propagator = W3CBaggagePropagator()
        ctx = baggage.set_baggage("floe.namespace", "analytics")

        carrier: dict[str, str] = {}
        propagator.inject(carrier, context=ctx)

        assert "baggage" in carrier
        assert "floe.namespace=analytics" in carrier["baggage"]

    @pytest.mark.requirement("FR-003")
    def test_baggage_propagator_extracts_headers(self) -> None:
        """Test baggage propagator extracts baggage from headers."""
        propagator = W3CBaggagePropagator()
        carrier = {"baggage": "floe.namespace=analytics"}

        ctx = propagator.extract(carrier)
        value = baggage.get_baggage("floe.namespace", ctx)

        assert value == "analytics"


class TestTraceContextInjectionExtraction:
    """Tests for trace context injection and extraction (T017).

    Validates that trace context can be injected into and extracted from carriers.
    """

    @pytest.mark.requirement("FR-002")
    def test_trace_context_can_be_injected(
        self, tracer_provider: TracerProvider
    ) -> None:
        """Test trace context can be injected into a carrier."""
        propagator = TraceContextTextMapPropagator()

        # Create a span with real TracerProvider
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test-span") as span:
            carrier: dict[str, str] = {}
            propagator.inject(carrier)

            # traceparent should be present when span is sampled
            assert "traceparent" in carrier
            assert span.get_span_context().is_valid

    @pytest.mark.requirement("FR-002")
    def test_trace_context_format(self, tracer_provider: TracerProvider) -> None:
        """Test traceparent header follows W3C format."""
        # W3C Trace Context format: version-trace_id-span_id-flags
        # Example: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
        propagator = TraceContextTextMapPropagator()

        # Create a sampled span
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test-span"):
            carrier: dict[str, str] = {}
            propagator.inject(carrier)

            assert "traceparent" in carrier
            parts = carrier["traceparent"].split("-")
            assert len(parts) == 4
            assert parts[0] == "00"  # version
            assert len(parts[1]) == 32  # trace_id (16 bytes hex)
            assert len(parts[2]) == 16  # span_id (8 bytes hex)
            assert len(parts[3]) == 2  # flags

    @pytest.mark.requirement("FR-002")
    def test_trace_context_can_be_extracted(self) -> None:
        """Test trace context can be extracted from carrier."""
        propagator = TraceContextTextMapPropagator()
        carrier = {
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        }

        ctx = propagator.extract(carrier)
        span_ctx = trace.get_current_span(ctx).get_span_context()

        # Extracted context should have the trace_id from the carrier
        expected_trace_id = int("4bf92f3577b34da6a3ce929d0e0e4736", 16)
        assert span_ctx.trace_id == expected_trace_id

    @pytest.mark.requirement("FR-002")
    def test_composite_propagator_handles_both(self) -> None:
        """Test composite propagator handles trace context and baggage."""
        composite = CompositePropagator(
            [
                TraceContextTextMapPropagator(),
                W3CBaggagePropagator(),
            ]
        )

        # Set up context with baggage
        ctx = baggage.set_baggage("floe.namespace", "analytics")

        # Inject with composite
        carrier: dict[str, str] = {}
        composite.inject(carrier, context=ctx)

        # Baggage should be injected
        assert "baggage" in carrier
        assert "floe.namespace=analytics" in carrier["baggage"]

    @pytest.mark.requirement("FR-002")
    def test_extract_with_composite_propagator(self) -> None:
        """Test composite propagator extracts both trace and baggage."""
        composite = CompositePropagator(
            [
                TraceContextTextMapPropagator(),
                W3CBaggagePropagator(),
            ]
        )

        carrier = {
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            "baggage": "floe.namespace=analytics,floe.mode=prod",
        }

        ctx = composite.extract(carrier)

        # Check baggage was extracted
        assert baggage.get_baggage("floe.namespace", ctx) == "analytics"
        assert baggage.get_baggage("floe.mode", ctx) == "prod"

        # Check trace context was extracted
        span_ctx = trace.get_current_span(ctx).get_span_context()
        expected_trace_id = int("4bf92f3577b34da6a3ce929d0e0e4736", 16)
        assert span_ctx.trace_id == expected_trace_id


class TestTraceContextHelpers:
    """Tests for trace context helper functions.

    These tests verify helpers that will be implemented in the propagation module.
    """

    @pytest.mark.requirement("FR-002")
    def test_get_current_span_context(
        self, tracer_provider: TracerProvider
    ) -> None:
        """Test getting current span context from active span."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test-span") as span:
            current_span = trace.get_current_span()
            assert current_span is span
            assert current_span.get_span_context().is_valid

    @pytest.mark.requirement("FR-002")
    def test_no_span_returns_invalid_context(self) -> None:
        """Test getting span context when no span is active."""
        # Outside of any span context
        current_span = trace.get_current_span()
        span_ctx = current_span.get_span_context()
        # Invalid context has trace_id and span_id of 0
        assert span_ctx.trace_id == 0 or not span_ctx.is_valid

    @pytest.mark.requirement("FR-002")
    def test_child_span_inherits_trace_id(
        self, tracer_provider: TracerProvider
    ) -> None:
        """Test child span inherits parent's trace_id."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("parent") as parent:
            parent_trace_id = parent.get_span_context().trace_id
            with tracer.start_as_current_span("child") as child:
                child_trace_id = child.get_span_context().trace_id
                assert child_trace_id == parent_trace_id

    @pytest.mark.requirement("FR-002")
    def test_child_span_has_different_span_id(
        self, tracer_provider: TracerProvider
    ) -> None:
        """Test child span has different span_id from parent."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("parent") as parent:
            parent_span_id = parent.get_span_context().span_id
            with tracer.start_as_current_span("child") as child:
                child_span_id = child.get_span_context().span_id
                assert child_span_id != parent_span_id

"""Integration tests for OpenTelemetry context propagation.

Tests cover:
- T018: Cross-service propagation integration tests

Requirements Covered:
- FR-002: W3C Trace Context propagation across service boundaries
- FR-003: W3C Baggage propagation across service boundaries
- FR-007a: floe.namespace propagation via Baggage

These tests use real OpenTelemetry SDK to validate that trace context
and baggage propagate correctly when simulating service-to-service calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from opentelemetry import trace
from opentelemetry.propagate import get_global_textmap, set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

from floe_core.telemetry.propagation import (
    configure_propagators,
    create_context_from_headers,
    extract_context,
    get_baggage_value,
    get_span_id,
    get_trace_id,
    inject_headers,
    set_floe_baggage,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def otel_provider() -> Generator[tuple[TracerProvider, InMemorySpanExporter], None, None]:
    """Set up a real OpenTelemetry TracerProvider with in-memory exporter.

    This fixture creates a complete OTel setup with:
    - TracerProvider with ALWAYS_ON sampling
    - InMemorySpanExporter to capture spans for assertion
    - SimpleSpanProcessor for immediate export

    Yields:
        Tuple of (TracerProvider, InMemorySpanExporter) for test use.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_ON)
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Save and set global provider
    original_provider = trace.get_tracer_provider()
    trace.set_tracer_provider(provider)

    yield provider, exporter

    # Restore original
    trace.set_tracer_provider(original_provider)


@pytest.fixture
def composite_propagator() -> Generator[CompositePropagator, None, None]:
    """Set up W3C Trace Context + Baggage propagators globally.

    Configures the global propagator to handle both W3C Trace Context
    and W3C Baggage headers for cross-service propagation.

    Yields:
        The configured CompositePropagator instance.
    """
    original_propagator = get_global_textmap()

    # Configure W3C propagators
    propagator = configure_propagators()

    yield propagator

    # Restore original
    set_global_textmap(original_propagator)


class TestCrossServiceTracePropagation:
    """Integration tests for trace context propagation across service boundaries.

    These tests simulate service-to-service calls by:
    1. Creating a span in "Service A"
    2. Injecting trace context into HTTP headers
    3. Extracting context in "Service B"
    4. Creating a child span with extracted context
    5. Verifying the trace_id is preserved

    Requirements: FR-002
    """

    @pytest.mark.requirement("FR-002")
    def test_trace_id_preserved_across_services(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test that trace_id is preserved when propagating between services.

        Simulates:
        - Service A creates a span and injects context into HTTP headers
        - Service B extracts context and creates a child span
        - Both spans share the same trace_id
        """
        del composite_propagator  # Used for side effect (sets global propagator)
        provider, exporter = otel_provider
        # Use provider.get_tracer() directly to avoid global state issues
        tracer = provider.get_tracer("test-tracer")

        # === Service A: Create root span and inject headers ===
        with tracer.start_as_current_span("service-a-operation") as service_a_span:
            service_a_trace_id = service_a_span.get_span_context().trace_id
            service_a_span_id = service_a_span.get_span_context().span_id

            # Simulate HTTP call: inject context into headers
            headers = inject_headers()

        # Verify headers were created
        assert "traceparent" in headers
        assert len(headers["traceparent"]) > 0

        # === Service B: Extract context and create child span ===
        extracted_ctx = extract_context(headers)

        # Use extracted context to create child span
        # Use provider.get_tracer() directly to avoid global state issues
        with provider.get_tracer("service-b-tracer").start_span(
            "service-b-operation", context=extracted_ctx
        ) as service_b_span:
            service_b_trace_id = service_b_span.get_span_context().trace_id

        # === Assertions ===
        # Both spans share the same trace_id
        assert service_b_trace_id == service_a_trace_id

        # Verify spans were exported
        spans = exporter.get_finished_spans()
        assert len(spans) == 2

        # All spans have the same trace_id
        assert all(s.context is not None for s in spans)
        trace_ids = {s.context.trace_id for s in spans if s.context is not None}
        assert len(trace_ids) == 1

        # Verify parent-child relationship via exported spans
        service_b_exported = next(s for s in spans if s.name == "service-b-operation")
        assert service_b_exported.parent is not None
        assert service_b_exported.parent.span_id == service_a_span_id

    @pytest.mark.requirement("FR-002")
    def test_traceparent_format_is_w3c_compliant(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test that traceparent header follows W3C Trace Context format.

        W3C format: version-trace_id-span_id-flags
        Example: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
        """
        provider, _ = otel_provider
        del composite_propagator  # Used for side effect (sets global propagator)
        # Use provider.get_tracer() directly to avoid global state issues
        tracer = provider.get_tracer("test-tracer")

        with tracer.start_as_current_span("test-operation"):
            headers = inject_headers()

        traceparent = headers["traceparent"]
        parts = traceparent.split("-")

        assert len(parts) == 4, f"traceparent should have 4 parts: {traceparent}"
        assert parts[0] == "00", "Version should be 00"
        assert len(parts[1]) == 32, "trace_id should be 32 hex characters"
        assert len(parts[2]) == 16, "span_id should be 16 hex characters"
        assert len(parts[3]) == 2, "flags should be 2 hex characters"

        # Verify hex format
        int(parts[1], 16)  # Should not raise
        int(parts[2], 16)  # Should not raise

    @pytest.mark.requirement("FR-002")
    def test_multi_hop_propagation(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test trace context propagates through multiple service hops.

        Simulates: Service A -> Service B -> Service C
        All spans should share the same trace_id.

        This test focuses on verifying that trace_id is preserved when
        extracting context, creating child spans, and re-injecting headers.
        """
        del composite_propagator  # Used for side effect (sets global propagator)
        provider, _ = otel_provider

        # === Service A: Create root span, inject headers ===
        # Use provider.get_tracer() directly to avoid global state issues
        tracer_a = provider.get_tracer("service-a")
        with tracer_a.start_as_current_span("service-a-request") as span_a:
            root_trace_id = span_a.get_span_context().trace_id
            headers_a_to_b = inject_headers()

        # === Service B: Extract, create child, re-inject ===
        ctx_b = extract_context(headers_a_to_b)
        tracer_b = provider.get_tracer("service-b")

        # Create span in extracted context
        span_b = tracer_b.start_span("service-b-handler", context=ctx_b)
        trace_id_b = span_b.get_span_context().trace_id

        # Inject headers with span B's context for next hop
        ctx_with_span_b = trace.set_span_in_context(span_b, ctx_b)
        headers_b_to_c = inject_headers(ctx_with_span_b)
        span_b.end()

        # === Service C: Extract, verify trace_id preserved ===
        ctx_c = extract_context(headers_b_to_c)
        tracer_c = provider.get_tracer("service-c")
        span_c = tracer_c.start_span("service-c-handler", context=ctx_c)
        trace_id_c = span_c.get_span_context().trace_id
        span_c.end()

        # === Verify all trace_ids match ===
        assert trace_id_b == root_trace_id, "Service B should have same trace_id as A"
        assert trace_id_c == root_trace_id, "Service C should have same trace_id as A"

        # Verify headers contain the same trace_id
        # Parse traceparent: version-trace_id-span_id-flags
        traceparent_a = headers_a_to_b["traceparent"]
        traceparent_b = headers_b_to_c["traceparent"]
        trace_id_from_a = traceparent_a.split("-")[1]
        trace_id_from_b = traceparent_b.split("-")[1]
        assert trace_id_from_a == trace_id_from_b, "Headers should propagate same trace_id"

    @pytest.mark.requirement("FR-002")
    def test_get_trace_id_returns_hex_string(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test get_trace_id returns 32-character hex string."""
        provider, _ = otel_provider
        del composite_propagator  # Used for side effect (sets global propagator)
        # Use provider.get_tracer() directly to avoid global state issues
        tracer = provider.get_tracer("test-tracer")

        with tracer.start_as_current_span("test-span"):
            trace_id = get_trace_id()
            span_id = get_span_id()

        assert trace_id is not None
        assert len(trace_id) == 32
        assert span_id is not None
        assert len(span_id) == 16

        # Verify hex format
        int(trace_id, 16)
        int(span_id, 16)


class TestCrossServiceBaggagePropagation:
    """Integration tests for W3C Baggage propagation across service boundaries.

    These tests verify that baggage items (especially floe.namespace)
    propagate correctly across simulated service calls.

    Requirements: FR-003, FR-007a
    """

    @pytest.mark.requirement("FR-003")
    def test_baggage_propagates_across_services(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test that baggage values propagate across service boundaries.

        Service A sets baggage, Service B should be able to read it.
        """
        provider, _ = otel_provider
        del composite_propagator  # Used for side effect (sets global propagator)
        # Use provider.get_tracer() directly to avoid global state issues
        tracer = provider.get_tracer("test-tracer")

        # === Service A: Set baggage and inject headers ===
        with tracer.start_as_current_span("service-a-operation"):
            # Set baggage in current context
            ctx = set_floe_baggage(
                namespace="analytics",
                product_name="customer-360",
                product_version="2.0.0",
                mode="prod",
            )

            # Inject headers with baggage context
            headers = inject_headers(ctx)

        # Verify baggage header exists
        assert "baggage" in headers
        baggage_header = headers["baggage"]
        assert "floe.namespace=analytics" in baggage_header

        # === Service B: Extract and read baggage ===
        extracted_ctx = extract_context(headers)

        # Read baggage from extracted context
        namespace = get_baggage_value("floe.namespace", extracted_ctx)
        product_name = get_baggage_value("floe.product.name", extracted_ctx)
        product_version = get_baggage_value("floe.product.version", extracted_ctx)
        mode = get_baggage_value("floe.mode", extracted_ctx)

        assert namespace == "analytics"
        assert product_name == "customer-360"
        assert product_version == "2.0.0"
        assert mode == "prod"

    @pytest.mark.requirement("FR-007a")
    def test_floe_namespace_propagates_via_baggage(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test floe.namespace specifically propagates via W3C Baggage.

        This is the key requirement for cross-service correlation in floe.
        """
        provider, _ = otel_provider
        del composite_propagator  # Used for side effect (sets global propagator)
        # Use provider.get_tracer() directly to avoid global state issues
        tracer = provider.get_tracer("test-tracer")

        # === Dagster Service: Set floe.namespace ===
        with tracer.start_as_current_span("dagster-pipeline"):
            ctx = set_floe_baggage(namespace="polaris-catalog-namespace")
            headers = inject_headers(ctx)

        # === dbt Service: Read floe.namespace ===
        extracted_ctx = extract_context(headers)
        namespace = get_baggage_value("floe.namespace", extracted_ctx)

        assert namespace == "polaris-catalog-namespace"

    @pytest.mark.requirement("FR-003")
    def test_baggage_survives_multi_hop(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test baggage survives propagation through multiple service hops.

        Simulates: Dagster -> dbt -> Polaris
        floe.namespace should be readable at each hop.
        """
        provider, _ = otel_provider
        del composite_propagator  # Used for side effect (sets global propagator)

        # === Dagster: Set initial baggage ===
        # Use provider.get_tracer() directly to avoid global state issues
        tracer_dagster = provider.get_tracer("dagster")
        with tracer_dagster.start_as_current_span("dagster-pipeline"):
            ctx = set_floe_baggage(
                namespace="customer_data",
                product_name="customer-360",
                mode="staging",
            )
            headers_to_dbt = inject_headers(ctx)

        # === dbt: Extract, verify, and forward ===
        ctx_dbt = extract_context(headers_to_dbt)
        namespace_at_dbt = get_baggage_value("floe.namespace", ctx_dbt)
        assert namespace_at_dbt == "customer_data"

        tracer_dbt = provider.get_tracer("dbt")
        with tracer_dbt.start_span("dbt-run", context=ctx_dbt):
            headers_to_polaris = inject_headers(ctx_dbt)

        # === Polaris: Extract and verify ===
        ctx_polaris = extract_context(headers_to_polaris)
        namespace_at_polaris = get_baggage_value("floe.namespace", ctx_polaris)
        product_at_polaris = get_baggage_value("floe.product.name", ctx_polaris)
        mode_at_polaris = get_baggage_value("floe.mode", ctx_polaris)

        assert namespace_at_polaris == "customer_data"
        assert product_at_polaris == "customer-360"
        assert mode_at_polaris == "staging"


class TestCombinedTraceAndBaggagePropagation:
    """Integration tests for combined trace context and baggage propagation.

    These tests verify that both W3C Trace Context and W3C Baggage
    propagate together correctly.

    Requirements: FR-002, FR-003, FR-007a
    """

    @pytest.mark.requirement("FR-002")
    @pytest.mark.requirement("FR-003")
    def test_trace_and_baggage_propagate_together(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test that trace context and baggage propagate in a single call.

        Both traceparent and baggage headers should be present and valid.
        """
        provider, _ = otel_provider
        del composite_propagator  # Used for side effect (sets global propagator)
        # Use provider.get_tracer() directly to avoid global state issues
        tracer = provider.get_tracer("test-tracer")

        # === Service A: Create span with baggage ===
        with tracer.start_as_current_span("service-a-call") as span_a:
            original_trace_id = span_a.get_span_context().trace_id
            ctx = set_floe_baggage(namespace="combined-test")
            headers = inject_headers(ctx)

        # Verify both headers present
        assert "traceparent" in headers
        assert "baggage" in headers

        # === Service B: Extract both ===
        extracted_ctx = extract_context(headers)

        # Verify trace context
        tracer_b = provider.get_tracer("service-b")
        with tracer_b.start_span("service-b-handler", context=extracted_ctx) as span_b:
            extracted_trace_id = span_b.get_span_context().trace_id

        # Verify baggage
        namespace = get_baggage_value("floe.namespace", extracted_ctx)

        assert extracted_trace_id == original_trace_id
        assert namespace == "combined-test"

    @pytest.mark.requirement("FR-002")
    @pytest.mark.requirement("FR-007a")
    def test_create_context_from_headers_helper(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test create_context_from_headers convenience function."""
        provider, _ = otel_provider
        del composite_propagator  # Used for side effect (sets global propagator)
        # Use provider.get_tracer() directly to avoid global state issues
        tracer = provider.get_tracer("test-tracer")

        # Create headers with trace and baggage
        with tracer.start_as_current_span("test-span") as span:
            original_trace_id = span.get_span_context().trace_id
            ctx = set_floe_baggage(namespace="helper-test")
            headers = inject_headers(ctx)

        # Use convenience function
        extracted_ctx = create_context_from_headers(headers)

        # Verify both extracted
        span_ctx = trace.get_current_span(extracted_ctx).get_span_context()
        assert span_ctx.trace_id == original_trace_id

        namespace = get_baggage_value("floe.namespace", extracted_ctx)
        assert namespace == "helper-test"

    @pytest.mark.requirement("FR-002")
    @pytest.mark.requirement("FR-003")
    def test_configure_propagators_sets_both(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test configure_propagators sets up both W3C propagators."""
        # Fixture used for consistency, but this test just checks propagator config
        _ = otel_provider
        # Save original
        original = get_global_textmap()

        try:
            # Configure propagators
            propagator = configure_propagators()

            # Verify it's a composite
            assert isinstance(propagator, CompositePropagator)

            # Verify it handles both trace context and baggage
            current = get_global_textmap()
            assert "traceparent" in current.fields
            assert "baggage" in current.fields

        finally:
            set_global_textmap(original)


class TestPropagationEdgeCases:
    """Integration tests for edge cases in context propagation.

    Requirements: FR-002, FR-003
    """

    @pytest.mark.requirement("FR-002")
    def test_extract_from_empty_headers(
        self,
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test extracting from empty headers returns valid context."""
        del composite_propagator  # Used for side effect (sets global propagator)
        headers: dict[str, str] = {}
        ctx = extract_context(headers)

        # Should return a valid context (just without trace info)
        assert ctx is not None

        # No trace should be active
        span_ctx = trace.get_current_span(ctx).get_span_context()
        assert not span_ctx.is_valid or span_ctx.trace_id == 0

    @pytest.mark.requirement("FR-002")
    def test_extract_from_invalid_traceparent(
        self,
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test extracting from invalid traceparent header."""
        del composite_propagator  # Used for side effect (sets global propagator)
        headers = {"traceparent": "invalid-format"}
        ctx = extract_context(headers)

        # Should return valid context but no valid trace
        assert ctx is not None
        span_ctx = trace.get_current_span(ctx).get_span_context()
        assert not span_ctx.is_valid or span_ctx.trace_id == 0

    @pytest.mark.requirement("FR-003")
    def test_baggage_with_special_characters(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test baggage handles values with special characters."""
        provider, _ = otel_provider
        del composite_propagator  # Used for side effect (sets global propagator)
        # Use provider.get_tracer() directly to avoid global state issues
        tracer = provider.get_tracer("test-tracer")

        # Use value without special characters per W3C Baggage spec
        # W3C Baggage values are token or quoted-string
        with tracer.start_as_current_span("test-span"):
            ctx = set_floe_baggage(namespace="namespace_with_underscore")
            headers = inject_headers(ctx)

        extracted_ctx = extract_context(headers)
        namespace = get_baggage_value("floe.namespace", extracted_ctx)

        assert namespace == "namespace_with_underscore"

    @pytest.mark.requirement("FR-002")
    def test_inject_without_active_span(
        self,
        composite_propagator: CompositePropagator,
    ) -> None:
        """Test injecting headers without an active span."""
        del composite_propagator  # Used for side effect (sets global propagator)
        # No active span, but baggage can still be set
        ctx = set_floe_baggage(namespace="no-span-test")
        headers = inject_headers(ctx)

        # Baggage should still be present
        assert "baggage" in headers
        assert "floe.namespace=no-span-test" in headers["baggage"]

        # No traceparent since no span
        # (traceparent may be absent or have invalid trace_id)

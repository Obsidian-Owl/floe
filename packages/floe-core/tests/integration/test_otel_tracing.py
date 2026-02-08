"""Integration tests for OpenTelemetry span creation.

Tests cover:
- T028: Integration test for span creation with real OTel SDK

Requirements Covered:
- FR-004: Spans for compilation operations
- FR-005: Spans for dbt operations
- FR-006: Spans for Dagster asset materializations
- FR-007: floe.namespace attribute on ALL spans
- FR-007b: floe.product.name attribute
- FR-007c: floe.product.version attribute
- FR-007d: floe.mode attribute
- FR-019: OpenTelemetry semantic conventions
- FR-020: Resource attributes on tracer
- FR-022: Error recording with exception details

These tests use real OpenTelemetry SDK to validate that spans are created
correctly with proper attributes, parent-child relationships, and error recording.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace import StatusCode

from floe_core.telemetry.conventions import (
    FLOE_DAGSTER_ASSET,
    FLOE_DBT_MODEL,
    FLOE_JOB_TYPE,
    FLOE_MODE,
    FLOE_NAMESPACE,
    FLOE_PIPELINE_ID,
    FLOE_PRODUCT_NAME,
    FLOE_PRODUCT_VERSION,
    FloeSpanAttributes,
)
from floe_core.telemetry.tracing import create_span, set_tracer, traced

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def otel_provider() -> (
    Generator[tuple[TracerProvider, InMemorySpanExporter], None, None]
):
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

    # Configure module-level tracer to use this provider
    test_tracer = provider.get_tracer("floe_core.telemetry.test")
    set_tracer(test_tracer)

    yield provider, exporter

    # Restore original
    trace.set_tracer_provider(original_provider)
    set_tracer(None)
    exporter.clear()


class TestTracedDecoratorIntegration:
    """Integration tests for @traced decorator with real OTel SDK.

    These tests verify that the @traced decorator creates real spans
    that are properly exported and contain expected attributes.

    Requirements: FR-004, FR-005, FR-006, FR-019
    """

    @pytest.mark.requirement("FR-004")
    def test_traced_creates_span_with_function_name(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced decorator creates span named after function.

        Validates that the decorator uses the function name as the span name
        when no custom name is provided.
        """
        _, exporter = otel_provider

        @traced
        def compile_spec() -> str:
            return "compiled"

        result = compile_spec()

        assert result == "compiled"
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "compile_spec"

    @pytest.mark.requirement("FR-005")
    def test_traced_creates_span_with_custom_name(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced decorator uses custom span name when provided.

        Validates dbt operation naming pattern.
        """
        _, exporter = otel_provider

        @traced(name="dbt.run")
        def run_dbt_models() -> None:
            pass

        run_dbt_models()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "dbt.run"

    @pytest.mark.requirement("FR-019")
    def test_traced_sets_custom_attributes(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced decorator sets custom attributes on span.

        Validates OpenTelemetry semantic conventions support.
        """
        _, exporter = otel_provider

        @traced(
            name="db.query",
            attributes={"db.system": "postgresql", "db.operation": "SELECT"},
        )
        def query_database() -> dict[str, str]:
            return {"status": "ok"}

        result = query_database()

        assert result == {"status": "ok"}
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span_attrs = dict(spans[0].attributes or {})
        assert span_attrs.get("db.system") == "postgresql"
        assert span_attrs.get("db.operation") == "SELECT"

    @pytest.mark.requirement("FR-022")
    def test_traced_records_exception_on_error(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced decorator records exceptions on span.

        Validates error recording per FR-022.
        """
        _, exporter = otel_provider

        @traced
        def failing_operation() -> None:
            raise ValueError("Compilation failed: invalid spec")

        with pytest.raises(ValueError, match="Compilation failed"):
            failing_operation()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.status.status_code == StatusCode.ERROR
        assert "Compilation failed" in (span.status.description or "")

        # Verify exception was recorded as event
        events = span.events
        assert len(events) >= 1
        # Find the exception event (may have additional events)
        exception_event = next((e for e in events if e.name == "exception"), None)
        assert exception_event is not None
        event_attrs = dict(exception_event.attributes or {})
        assert event_attrs.get("exception.type") == "ValueError"
        assert "Compilation failed" in str(event_attrs.get("exception.message", ""))

    @pytest.mark.requirement("FR-006")
    def test_traced_creates_parent_child_relationship(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test nested @traced decorators create parent-child spans.

        Validates Dagster asset materialization pattern with nested operations.
        """
        _, exporter = otel_provider

        @traced(name="dagster.asset.materialize")
        def materialize_asset() -> str:
            return load_source_data()

        @traced(name="dagster.asset.load_source")
        def load_source_data() -> str:
            return "data loaded"

        result = materialize_asset()

        assert result == "data loaded"
        spans = exporter.get_finished_spans()
        assert len(spans) == 2

        # Spans are in reverse order (child finishes first)
        child_span = next(s for s in spans if s.name == "dagster.asset.load_source")
        parent_span = next(s for s in spans if s.name == "dagster.asset.materialize")

        # Verify parent-child relationship
        assert child_span.parent is not None
        assert parent_span.context is not None
        assert child_span.context is not None
        assert child_span.parent.span_id == parent_span.context.span_id
        assert child_span.context.trace_id == parent_span.context.trace_id


class TestCreateSpanIntegration:
    """Integration tests for create_span() context manager with real OTel SDK.

    Requirements: FR-004, FR-019, FR-022
    """

    @pytest.mark.requirement("FR-004")
    def test_create_span_creates_named_span(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span creates a span with the given name."""
        _, exporter = otel_provider

        with create_span("compilation.validate_spec"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "compilation.validate_spec"

    @pytest.mark.requirement("FR-019")
    def test_create_span_sets_attributes(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span sets attributes on the span."""
        _, exporter = otel_provider

        with create_span(
            "http.request",
            attributes={"http.method": "GET", "http.url": "https://api.example.com"},
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span_attrs = dict(spans[0].attributes or {})
        assert span_attrs.get("http.method") == "GET"
        assert span_attrs.get("http.url") == "https://api.example.com"

    @pytest.mark.requirement("FR-022")
    def test_create_span_records_exception(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span records exception when raised."""
        _, exporter = otel_provider

        with pytest.raises(RuntimeError, match="Connection failed"):
            with create_span("database.connect"):
                raise RuntimeError("Connection failed")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.status.status_code == StatusCode.ERROR
        assert "Connection failed" in (span.status.description or "")

        events = span.events
        assert len(events) >= 1
        # Find the exception event (may have additional events)
        exception_event = next((e for e in events if e.name == "exception"), None)
        assert exception_event is not None

    @pytest.mark.requirement("FR-004")
    def test_create_span_nested_creates_hierarchy(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test nested create_span calls create parent-child hierarchy."""
        _, exporter = otel_provider

        with create_span("parent.operation") as parent:
            parent.set_attribute("level", "parent")
            with create_span("child.operation") as child:
                child.set_attribute("level", "child")
                with create_span("grandchild.operation") as grandchild:
                    grandchild.set_attribute("level", "grandchild")

        spans = exporter.get_finished_spans()
        assert len(spans) == 3

        grandchild_span = next(s for s in spans if s.name == "grandchild.operation")
        child_span = next(s for s in spans if s.name == "child.operation")
        parent_span = next(s for s in spans if s.name == "parent.operation")

        # Verify contexts are valid
        assert grandchild_span.context is not None
        assert child_span.context is not None
        assert parent_span.context is not None

        # Verify three-level hierarchy
        assert grandchild_span.parent is not None
        assert grandchild_span.parent.span_id == child_span.context.span_id

        assert child_span.parent is not None
        assert child_span.parent.span_id == parent_span.context.span_id

        assert parent_span.parent is None  # Root span

        # All share same trace_id
        assert grandchild_span.context.trace_id == child_span.context.trace_id
        assert child_span.context.trace_id == parent_span.context.trace_id


class TestFloeSpanAttributesIntegration:
    """Integration tests for FloeSpanAttributes injection with real OTel SDK.

    Requirements: FR-007, FR-007b, FR-007c, FR-007d
    """

    @pytest.mark.requirement("FR-007")
    @pytest.mark.requirement("FR-007b")
    @pytest.mark.requirement("FR-007c")
    @pytest.mark.requirement("FR-007d")
    def test_traced_with_floe_attributes(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced injects FloeSpanAttributes onto span.

        Validates all mandatory Floe semantic attributes are present.
        """
        _, exporter = otel_provider

        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="2.1.0",
            mode="prod",
        )

        @traced(name="pipeline.execute", floe_attributes=attrs)
        def execute_pipeline() -> str:
            return "executed"

        result = execute_pipeline()

        assert result == "executed"
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span_attrs = dict(spans[0].attributes or {})
        assert span_attrs.get(FLOE_NAMESPACE) == "analytics"
        assert span_attrs.get(FLOE_PRODUCT_NAME) == "customer-360"
        assert span_attrs.get(FLOE_PRODUCT_VERSION) == "2.1.0"
        assert span_attrs.get(FLOE_MODE) == "prod"

    @pytest.mark.requirement("FR-007")
    def test_create_span_with_floe_attributes(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span injects FloeSpanAttributes onto span."""
        _, exporter = otel_provider

        attrs = FloeSpanAttributes(
            namespace="warehouse",
            product_name="inventory-sync",
            product_version="1.0.0",
            mode="staging",
        )

        with create_span("sync.execute", floe_attributes=attrs):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span_attrs = dict(spans[0].attributes or {})
        assert span_attrs.get(FLOE_NAMESPACE) == "warehouse"
        assert span_attrs.get(FLOE_PRODUCT_NAME) == "inventory-sync"
        assert span_attrs.get(FLOE_PRODUCT_VERSION) == "1.0.0"
        assert span_attrs.get(FLOE_MODE) == "staging"

    @pytest.mark.requirement("FR-007")
    def test_floe_attributes_with_optional_fields(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test FloeSpanAttributes includes optional fields when provided."""
        _, exporter = otel_provider

        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="2.0.0",
            mode="dev",
            pipeline_id="run-abc123",
            job_type="dbt_run",
            model_name="stg_customers",
            asset_key="raw_customers",
        )

        with create_span("dbt.model.run", floe_attributes=attrs):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span_attrs = dict(spans[0].attributes or {})
        # Mandatory
        assert span_attrs.get(FLOE_NAMESPACE) == "analytics"
        assert span_attrs.get(FLOE_PRODUCT_NAME) == "customer-360"
        assert span_attrs.get(FLOE_PRODUCT_VERSION) == "2.0.0"
        assert span_attrs.get(FLOE_MODE) == "dev"
        # Optional
        assert span_attrs.get(FLOE_PIPELINE_ID) == "run-abc123"
        assert span_attrs.get(FLOE_JOB_TYPE) == "dbt_run"
        assert span_attrs.get(FLOE_DBT_MODEL) == "stg_customers"
        assert span_attrs.get(FLOE_DAGSTER_ASSET) == "raw_customers"

    @pytest.mark.requirement("FR-007")
    def test_custom_attributes_override_floe_attributes(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test custom attributes can override floe attributes if needed."""
        _, exporter = otel_provider

        floe_attrs = FloeSpanAttributes(
            namespace="original-namespace",
            product_name="product",
            product_version="1.0.0",
            mode="dev",
        )

        with create_span(
            "test.operation",
            floe_attributes=floe_attrs,
            attributes={FLOE_NAMESPACE: "overridden-namespace"},
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span_attrs = dict(spans[0].attributes or {})
        # Custom attribute overrides floe attribute
        assert span_attrs.get(FLOE_NAMESPACE) == "overridden-namespace"


class TestMixedTracingPatterns:
    """Integration tests for mixed @traced and create_span usage.

    Requirements: FR-004, FR-005, FR-006
    """

    @pytest.mark.requirement("FR-004")
    @pytest.mark.requirement("FR-005")
    def test_traced_calling_create_span(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced function using create_span internally."""
        _, exporter = otel_provider

        @traced(name="compilation.full")
        def compile_project() -> str:
            with create_span("compilation.parse"):
                pass
            with create_span("compilation.validate"):
                pass
            with create_span("compilation.generate"):
                pass
            return "compiled"

        result = compile_project()

        assert result == "compiled"
        spans = exporter.get_finished_spans()
        assert len(spans) == 4

        # Verify parent-child relationships
        parent_span = next(s for s in spans if s.name == "compilation.full")
        child_spans = [s for s in spans if s.name != "compilation.full"]

        assert parent_span.context is not None
        for child in child_spans:
            assert child.parent is not None
            assert child.parent.span_id == parent_span.context.span_id

    @pytest.mark.requirement("FR-005")
    @pytest.mark.requirement("FR-006")
    def test_complex_pipeline_tracing(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test complex pipeline with mixed tracing patterns.

        Simulates: Dagster -> dbt -> multiple models
        """
        _, exporter = otel_provider

        floe_attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="prod",
        )

        @traced(name="dagster.asset.customers", floe_attributes=floe_attrs)
        def materialize_customers() -> str:
            return run_dbt()

        @traced(name="dbt.run", floe_attributes=floe_attrs)
        def run_dbt() -> str:
            with create_span("dbt.model.stg_customers", floe_attributes=floe_attrs):
                pass
            with create_span("dbt.model.int_customers", floe_attributes=floe_attrs):
                pass
            with create_span("dbt.model.fct_customers", floe_attributes=floe_attrs):
                pass
            return "models executed"

        result = materialize_customers()

        assert result == "models executed"
        spans = exporter.get_finished_spans()
        assert len(spans) == 5

        # Verify all spans have floe.namespace
        for span in spans:
            span_attrs = dict(span.attributes or {})
            assert span_attrs.get(FLOE_NAMESPACE) == "analytics"
            assert span_attrs.get(FLOE_PRODUCT_NAME) == "customer-360"

        # Verify hierarchy: dagster -> dbt -> models
        dagster_span = next(s for s in spans if s.name == "dagster.asset.customers")
        dbt_span = next(s for s in spans if s.name == "dbt.run")
        model_spans = [s for s in spans if s.name.startswith("dbt.model")]

        assert dagster_span.context is not None
        assert dbt_span.context is not None
        assert dbt_span.parent is not None
        assert dbt_span.parent.span_id == dagster_span.context.span_id

        for model_span in model_spans:
            assert model_span.parent is not None
            assert model_span.parent.span_id == dbt_span.context.span_id


class TestSpanLifecycle:
    """Integration tests for span lifecycle and timing.

    Requirements: FR-019, FR-020
    """

    @pytest.mark.requirement("FR-019")
    def test_span_has_valid_timestamps(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test spans have valid start and end timestamps."""
        _, exporter = otel_provider

        with create_span("timed.operation"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.start_time is not None
        assert span.end_time is not None
        assert span.end_time >= span.start_time

    @pytest.mark.requirement("FR-019")
    def test_span_has_valid_context(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test spans have valid trace and span IDs."""
        _, exporter = otel_provider

        with create_span("context.test"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.context is not None
        assert span.context.trace_id != 0
        assert span.context.span_id != 0
        assert span.context.is_valid

    @pytest.mark.requirement("FR-020")
    def test_multiple_spans_share_tracer_resource(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test multiple spans share the same tracer resource."""
        _, exporter = otel_provider

        with create_span("span.one"):
            pass
        with create_span("span.two"):
            pass
        with create_span("span.three"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 3

        # All spans should have the same resource (from same tracer)
        resources = {span.resource for span in spans}
        assert len(resources) == 1

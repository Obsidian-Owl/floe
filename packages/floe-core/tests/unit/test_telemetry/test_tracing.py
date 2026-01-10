"""Unit tests for OpenTelemetry tracing utilities.

Tests cover:
- T024: @traced decorator functionality (TestTracedDecorator, TestTracedDecoratorMethods,
        TestTracedDecoratorPreservesFunctionMetadata)
- T025: create_span() context manager (TestCreateSpanContextManager)
- T027: Error recording on spans (covered in both T024 and T025 test classes)
- T033: Floe semantic attribute injection (TestFloeAttributeInjection)

Requirements Covered:
- FR-004: Spans for compilation operations
- FR-005: Spans for dbt operations
- FR-006: Spans for Dagster asset materializations
- FR-007: floe.namespace attribute on ALL spans
- FR-007b: floe.product.name attribute
- FR-007c: floe.product.version attribute
- FR-007d: floe.mode attribute
- FR-019: OpenTelemetry semantic conventions
- FR-020: Resource attributes
- FR-022: Error recording with exception details
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace import StatusCode

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def tracer_provider_with_exporter() -> Generator[
    tuple[TracerProvider, InMemorySpanExporter], None, None
]:
    """Create a TracerProvider with InMemorySpanExporter for testing.

    Injects the tracer into the tracing module for testing purposes.

    Yields:
        Tuple of (TracerProvider, InMemorySpanExporter) for test assertions.
    """
    from floe_core.telemetry.tracing import set_tracer

    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_ON)

    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Inject the test tracer into the tracing module
    test_tracer = provider.get_tracer("test_tracing")
    set_tracer(test_tracer)

    yield provider, exporter

    # Reset to None so next test can set its own tracer
    set_tracer(None)
    exporter.clear()


class TestTracedDecorator:
    """Tests for @traced decorator (T024).

    The @traced decorator should:
    - Create a span with the function name
    - Support custom span names
    - Pass through function arguments and return values
    - Handle async functions
    - Record exceptions automatically
    """

    @pytest.mark.requirement("FR-004")
    def test_traced_creates_span_with_function_name(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced creates span named after the decorated function."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        @traced
        def my_operation() -> str:
            return "result"

        result = my_operation()

        assert result == "result"
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "my_operation"

    @pytest.mark.requirement("FR-004")
    def test_traced_with_custom_span_name(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced allows custom span name via parameter."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        @traced(name="custom_operation_name")
        def my_function() -> None:
            pass

        my_function()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "custom_operation_name"

    @pytest.mark.requirement("FR-004")
    def test_traced_preserves_function_arguments(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced passes through all function arguments."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        @traced
        def add_numbers(a: int, b: int, *, multiplier: int = 1) -> int:
            return (a + b) * multiplier

        result = add_numbers(2, 3, multiplier=2)

        assert result == 10
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

    @pytest.mark.requirement("FR-004")
    def test_traced_preserves_return_value(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced returns the decorated function's return value."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        expected = {"key": "value", "nested": {"a": 1}}

        @traced
        def return_dict() -> dict[str, object]:
            return expected

        result = return_dict()

        assert result == expected
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

    @pytest.mark.requirement("FR-022")
    def test_traced_records_exception_on_error(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced records exception details when function raises."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        @traced
        def failing_operation() -> None:
            raise ValueError("Something went wrong")

        with pytest.raises(ValueError, match="Something went wrong"):
            failing_operation()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]

        # Span should have error status
        assert span.status.status_code == StatusCode.ERROR
        assert "Something went wrong" in (span.status.description or "")

        # Exception should be recorded as event
        events = span.events
        assert len(events) >= 1
        exception_event = next((e for e in events if e.name == "exception"), None)
        assert exception_event is not None

    @pytest.mark.requirement("FR-022")
    def test_traced_reraises_exception(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced re-raises the original exception after recording."""
        from floe_core.telemetry.tracing import traced

        @traced
        def raise_custom_error() -> None:
            raise RuntimeError("Custom error message")

        with pytest.raises(RuntimeError, match="Custom error message"):
            raise_custom_error()

    @pytest.mark.requirement("FR-004")
    def test_traced_span_has_ok_status_on_success(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced span has OK status when function succeeds."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        @traced
        def successful_operation() -> str:
            return "success"

        successful_operation()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        # UNSET is the default for successful operations per OTel spec
        assert spans[0].status.status_code in (StatusCode.UNSET, StatusCode.OK)

    @pytest.mark.requirement("FR-019")
    def test_traced_with_attributes(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced allows setting span attributes."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        @traced(attributes={"operation.type": "compilation", "operation.id": "123"})
        def compile_spec() -> None:
            pass

        compile_spec()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})
        assert attrs.get("operation.type") == "compilation"
        assert attrs.get("operation.id") == "123"

    @pytest.mark.requirement("FR-004")
    def test_traced_creates_child_spans(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test nested @traced functions create parent-child span relationship."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        @traced
        def inner_operation() -> str:
            return "inner"

        @traced
        def outer_operation() -> str:
            return inner_operation()

        outer_operation()

        spans = exporter.get_finished_spans()
        assert len(spans) == 2

        # Find spans by name
        inner_span = next(s for s in spans if s.name == "inner_operation")
        outer_span = next(s for s in spans if s.name == "outer_operation")

        # Inner span should have outer span as parent
        assert inner_span.parent is not None
        assert inner_span.parent.span_id == outer_span.context.span_id

        # Both should share the same trace ID
        assert inner_span.context.trace_id == outer_span.context.trace_id


class TestTracedDecoratorMethods:
    """Tests for @traced decorator on class methods."""

    @pytest.mark.requirement("FR-004")
    def test_traced_instance_method(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced works on instance methods."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        class MyService:
            @traced
            def process(self, data: str) -> str:
                return f"processed: {data}"

        service = MyService()
        result = service.process("input")

        assert result == "processed: input"
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "process"

    @pytest.mark.requirement("FR-004")
    def test_traced_class_method(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced works on class methods."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        class MyFactory:
            @classmethod
            @traced
            def create(cls) -> str:
                return "created"

        result = MyFactory.create()

        assert result == "created"
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

    @pytest.mark.requirement("FR-004")
    def test_traced_static_method(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced works on static methods."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        class MyUtils:
            @staticmethod
            @traced
            def helper(x: int) -> int:
                return x * 2

        result = MyUtils.helper(5)

        assert result == 10
        spans = exporter.get_finished_spans()
        assert len(spans) == 1


class TestTracedDecoratorPreservesFunctionMetadata:
    """Tests that @traced preserves decorated function metadata."""

    @pytest.mark.requirement("FR-004")
    def test_traced_preserves_function_name(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced preserves __name__ attribute."""
        from floe_core.telemetry.tracing import traced

        @traced
        def my_documented_function() -> None:
            """This is the docstring."""
            pass

        assert my_documented_function.__name__ == "my_documented_function"

    @pytest.mark.requirement("FR-004")
    def test_traced_preserves_docstring(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced preserves __doc__ attribute."""
        from floe_core.telemetry.tracing import traced

        @traced
        def documented_function() -> None:
            """This is the original docstring."""
            pass

        assert documented_function.__doc__ == "This is the original docstring."

    @pytest.mark.requirement("FR-004")
    def test_traced_preserves_module(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced preserves __module__ attribute."""
        from floe_core.telemetry.tracing import traced

        @traced
        def function_with_module() -> None:
            pass

        assert function_with_module.__module__ == __name__


class TestCreateSpanContextManager:
    """Tests for create_span() context manager (T025).

    The create_span() context manager should:
    - Create a span with the given name
    - Return the span for attribute setting
    - Automatically end the span when exiting
    - Create child spans when nested
    - Record exceptions when raised
    """

    @pytest.mark.requirement("FR-004")
    def test_create_span_creates_span_with_name(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span creates a span with the specified name."""
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        with create_span("test_operation"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test_operation"

    @pytest.mark.requirement("FR-004")
    def test_create_span_returns_span(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span yields the span for attribute setting."""
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        with create_span("test_operation") as span:
            span.set_attribute("test.key", "test_value")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})
        assert attrs.get("test.key") == "test_value"

    @pytest.mark.requirement("FR-004")
    def test_create_span_ends_span_on_exit(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span automatically ends the span when exiting."""
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        with create_span("test_operation"):
            # Span should not be finished yet
            assert len(exporter.get_finished_spans()) == 0

        # Span should be finished after exiting
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

    @pytest.mark.requirement("FR-004")
    def test_create_span_creates_child_spans(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test nested create_span creates parent-child relationship."""
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        with create_span("parent_operation"):
            with create_span("child_operation"):
                pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 2

        # Find spans by name
        parent_span = next(s for s in spans if s.name == "parent_operation")
        child_span = next(s for s in spans if s.name == "child_operation")

        # Child span should have parent span as parent
        assert child_span.parent is not None
        assert child_span.parent.span_id == parent_span.context.span_id

        # Both should share the same trace ID
        assert child_span.context.trace_id == parent_span.context.trace_id

    @pytest.mark.requirement("FR-022")
    def test_create_span_records_exception(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span records exception when raised inside context."""
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        with pytest.raises(ValueError, match="Test error"):
            with create_span("failing_operation"):
                raise ValueError("Test error")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]

        # Span should have error status
        assert span.status.status_code == StatusCode.ERROR
        assert "Test error" in (span.status.description or "")

        # Exception should be recorded as event
        events = span.events
        assert len(events) >= 1
        exception_event = next((e for e in events if e.name == "exception"), None)
        assert exception_event is not None

    @pytest.mark.requirement("FR-022")
    def test_create_span_reraises_exception(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span re-raises the original exception."""
        from floe_core.telemetry.tracing import create_span

        with pytest.raises(RuntimeError, match="Original error"):
            with create_span("failing_operation"):
                raise RuntimeError("Original error")

    @pytest.mark.requirement("FR-019")
    def test_create_span_with_attributes(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span allows setting attributes via parameter."""
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        with create_span(
            "test_operation",
            attributes={"operation.type": "test", "operation.id": "123"},
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})
        assert attrs.get("operation.type") == "test"
        assert attrs.get("operation.id") == "123"

    @pytest.mark.requirement("FR-004")
    def test_create_span_with_multiple_children(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span supports multiple sequential child spans."""
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        with create_span("parent_operation"):
            with create_span("child_1"):
                pass
            with create_span("child_2"):
                pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 3

        # Find spans by name
        parent_span = next(s for s in spans if s.name == "parent_operation")
        child_1 = next(s for s in spans if s.name == "child_1")
        child_2 = next(s for s in spans if s.name == "child_2")

        # Both children should have parent span as parent
        assert child_1.parent is not None
        assert child_1.parent.span_id == parent_span.context.span_id
        assert child_2.parent is not None
        assert child_2.parent.span_id == parent_span.context.span_id

    @pytest.mark.requirement("FR-004")
    def test_create_span_ok_status_on_success(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span has OK/UNSET status on successful completion."""
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        with create_span("successful_operation"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        # UNSET is the default for successful operations per OTel spec
        assert spans[0].status.status_code in (StatusCode.UNSET, StatusCode.OK)


class TestFloeAttributeInjection:
    """Tests for Floe semantic attribute injection (T033).

    Tests that @traced and create_span() support FloeSpanAttributes
    for automatic injection of Floe semantic conventions.

    Requirements Covered:
    - FR-007: floe.namespace attribute on ALL spans
    - FR-007b: floe.product.name attribute
    - FR-007c: floe.product.version attribute
    - FR-007d: floe.mode attribute
    - FR-019: OpenTelemetry semantic conventions
    """

    @pytest.mark.requirement("FR-007")
    def test_traced_with_floe_attributes(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced decorator accepts FloeSpanAttributes."""
        from floe_core.telemetry.conventions import FloeSpanAttributes
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        floe_attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="2.1.0",
            mode="prod",
        )

        @traced(floe_attributes=floe_attrs)
        def compile_spec() -> None:
            pass

        compile_spec()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})

        assert attrs.get("floe.namespace") == "analytics"
        assert attrs.get("floe.product.name") == "customer-360"
        assert attrs.get("floe.product.version") == "2.1.0"
        assert attrs.get("floe.mode") == "prod"

    @pytest.mark.requirement("FR-007")
    def test_traced_with_floe_attributes_and_custom_attributes(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced combines FloeSpanAttributes with custom attributes."""
        from floe_core.telemetry.conventions import FloeSpanAttributes
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        floe_attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="dev",
        )

        @traced(
            floe_attributes=floe_attrs,
            attributes={"custom.key": "custom_value"},
        )
        def my_operation() -> None:
            pass

        my_operation()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})

        # Both floe and custom attributes should be present
        assert attrs.get("floe.namespace") == "analytics"
        assert attrs.get("custom.key") == "custom_value"

    @pytest.mark.requirement("FR-007")
    def test_traced_with_floe_attributes_optional_fields(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced includes optional FloeSpanAttributes fields."""
        from floe_core.telemetry.conventions import FloeSpanAttributes
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        floe_attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="2.1.0",
            mode="prod",
            pipeline_id="run-12345",
            job_type="dbt_run",
            model_name="stg_customers",
            asset_key="customers/raw",
        )

        @traced(floe_attributes=floe_attrs)
        def run_dbt() -> None:
            pass

        run_dbt()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})

        # All 8 attributes should be present
        assert attrs.get("floe.namespace") == "analytics"
        assert attrs.get("floe.product.name") == "customer-360"
        assert attrs.get("floe.product.version") == "2.1.0"
        assert attrs.get("floe.mode") == "prod"
        assert attrs.get("floe.pipeline.id") == "run-12345"
        assert attrs.get("floe.job.type") == "dbt_run"
        assert attrs.get("floe.dbt.model") == "stg_customers"
        assert attrs.get("floe.dagster.asset") == "customers/raw"

    @pytest.mark.requirement("FR-007")
    def test_create_span_with_floe_attributes(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span accepts FloeSpanAttributes."""
        from floe_core.telemetry.conventions import FloeSpanAttributes
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        floe_attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="2.1.0",
            mode="staging",
        )

        with create_span("pipeline_run", floe_attributes=floe_attrs):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})

        assert attrs.get("floe.namespace") == "analytics"
        assert attrs.get("floe.product.name") == "customer-360"
        assert attrs.get("floe.product.version") == "2.1.0"
        assert attrs.get("floe.mode") == "staging"

    @pytest.mark.requirement("FR-007")
    def test_create_span_with_floe_attributes_and_custom_attributes(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span combines FloeSpanAttributes with custom attributes."""
        from floe_core.telemetry.conventions import FloeSpanAttributes
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        floe_attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="dev",
        )

        with create_span(
            "my_operation",
            floe_attributes=floe_attrs,
            attributes={"custom.key": "custom_value"},
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})

        # Both floe and custom attributes should be present
        assert attrs.get("floe.namespace") == "analytics"
        assert attrs.get("custom.key") == "custom_value"

    @pytest.mark.requirement("FR-007")
    def test_create_span_with_floe_attributes_optional_fields(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span includes optional FloeSpanAttributes fields."""
        from floe_core.telemetry.conventions import FloeSpanAttributes
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        floe_attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="2.1.0",
            mode="prod",
            pipeline_id="run-54321",
            job_type="dagster_asset",
            model_name="dim_customers",
            asset_key="analytics/dim_customers",
        )

        with create_span("materialize_asset", floe_attributes=floe_attrs):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})

        # All 8 attributes should be present
        assert attrs.get("floe.namespace") == "analytics"
        assert attrs.get("floe.product.name") == "customer-360"
        assert attrs.get("floe.product.version") == "2.1.0"
        assert attrs.get("floe.mode") == "prod"
        assert attrs.get("floe.pipeline.id") == "run-54321"
        assert attrs.get("floe.job.type") == "dagster_asset"
        assert attrs.get("floe.dbt.model") == "dim_customers"
        assert attrs.get("floe.dagster.asset") == "analytics/dim_customers"

    @pytest.mark.requirement("FR-022")
    def test_traced_with_floe_attributes_records_exception(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced with FloeSpanAttributes still records exceptions."""
        from floe_core.telemetry.conventions import FloeSpanAttributes
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        floe_attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="failing-product",
            product_version="1.0.0",
            mode="dev",
        )

        @traced(floe_attributes=floe_attrs)
        def failing_operation() -> None:
            raise ValueError("Something went wrong")

        with pytest.raises(ValueError, match="Something went wrong"):
            failing_operation()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]

        # Floe attributes should be present
        attrs = dict(span.attributes or {})
        assert attrs.get("floe.namespace") == "analytics"

        # Exception should be recorded
        assert span.status.status_code == StatusCode.ERROR

    @pytest.mark.requirement("FR-022")
    def test_create_span_with_floe_attributes_records_exception(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test create_span with FloeSpanAttributes still records exceptions."""
        from floe_core.telemetry.conventions import FloeSpanAttributes
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_provider_with_exporter

        floe_attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="failing-product",
            product_version="1.0.0",
            mode="dev",
        )

        with pytest.raises(ValueError, match="Test failure"):
            with create_span("failing_op", floe_attributes=floe_attrs):
                raise ValueError("Test failure")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]

        # Floe attributes should be present
        attrs = dict(span.attributes or {})
        assert attrs.get("floe.namespace") == "analytics"

        # Exception should be recorded
        assert span.status.status_code == StatusCode.ERROR

    @pytest.mark.requirement("FR-005")
    def test_traced_async_with_floe_attributes(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test @traced works with async functions and FloeSpanAttributes."""
        import asyncio

        from floe_core.telemetry.conventions import FloeSpanAttributes
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_provider_with_exporter

        floe_attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="async-product",
            product_version="1.0.0",
            mode="dev",
        )

        @traced(floe_attributes=floe_attrs)
        async def async_operation() -> str:
            return "async_result"

        result = asyncio.run(async_operation())

        assert result == "async_result"
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})
        assert attrs.get("floe.namespace") == "analytics"
        assert attrs.get("floe.product.name") == "async-product"

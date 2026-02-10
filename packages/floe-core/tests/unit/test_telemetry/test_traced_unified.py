"""Unit tests for unified @traced decorator (T006).

Tests the new attributes_fn capability and sanitized error recording
added to the floe-core @traced decorator as part of the unification
with floe-iceberg's local @traced.

Requirements Covered:
- 6C-FR-008: Unified @traced with attributes_fn and sanitized errors
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace import StatusCode

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def tracer_with_exporter() -> Generator[
    tuple[TracerProvider, InMemorySpanExporter], None, None
]:
    """Create a TracerProvider with InMemorySpanExporter for testing.

    Injects the tracer into the tracing module for test purposes.

    Yields:
        Tuple of (TracerProvider, InMemorySpanExporter) for assertions.
    """
    from floe_core.telemetry.tracing import set_tracer

    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_ON)
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    test_tracer = provider.get_tracer("test_traced_unified")
    set_tracer(test_tracer)

    yield provider, exporter

    set_tracer(None)
    exporter.clear()


class TestAttributesFn:
    """Tests for the attributes_fn parameter on @traced."""

    @pytest.mark.requirement("6C-FR-008")
    def test_attributes_fn_receives_correct_args(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Verify attributes_fn receives the function's positional and keyword args."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_with_exporter

        captured: dict[str, Any] = {}

        def capture_args(table_id: str, namespace: str = "default") -> dict[str, str]:
            captured["table_id"] = table_id
            captured["namespace"] = namespace
            return {"table_id": table_id, "namespace": namespace}

        @traced(attributes_fn=capture_args)
        def load_table(table_id: str, namespace: str = "default") -> str:
            return f"{namespace}.{table_id}"

        result = load_table("customers", namespace="bronze")

        assert result == "bronze.customers"
        assert captured["table_id"] == "customers"
        assert captured["namespace"] == "bronze"

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})
        assert attrs.get("table_id") == "customers"
        assert attrs.get("namespace") == "bronze"

    @pytest.mark.requirement("6C-FR-008")
    def test_attributes_fn_failure_logged_not_fatal(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When attributes_fn raises, function executes normally and warning is logged."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_with_exporter

        def bad_extractor(*args: Any, **kwargs: Any) -> dict[str, str]:
            msg = "extraction failed"
            raise RuntimeError(msg)

        @traced(attributes_fn=bad_extractor)
        def do_work() -> str:
            return "success"

        with caplog.at_level(logging.WARNING, logger="floe_core.telemetry.tracing"):
            result = do_work()

        assert result == "success"
        assert any("attributes_fn failed" in record.message for record in caplog.records)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        # Span still completed normally (UNSET = success)
        assert spans[0].status.status_code in (StatusCode.UNSET, StatusCode.OK)

    @pytest.mark.requirement("6C-FR-008")
    def test_attributes_fn_with_static_attributes_compose(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Both attributes_fn and static attributes set on span."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_with_exporter

        def dynamic_attrs(table_id: str) -> dict[str, str]:
            return {"table_id": table_id}

        @traced(
            attributes={"operation": "load"},
            attributes_fn=dynamic_attrs,
        )
        def load_table(table_id: str) -> str:
            return table_id

        load_table("orders")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})
        # Static attribute
        assert attrs.get("operation") == "load"
        # Dynamic attribute
        assert attrs.get("table_id") == "orders"

    @pytest.mark.requirement("6C-FR-008")
    def test_attributes_fn_with_floe_attributes_compose(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """All three (floe_attributes, attributes, attributes_fn) compose on span."""
        from floe_core.telemetry.conventions import FloeSpanAttributes
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_with_exporter

        floe_attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="dev",
        )

        def dynamic_attrs(table_id: str) -> dict[str, str]:
            return {"table_id": table_id}

        @traced(
            floe_attributes=floe_attrs,
            attributes={"operation": "scan"},
            attributes_fn=dynamic_attrs,
        )
        def scan_table(table_id: str) -> str:
            return table_id

        scan_table("products")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})
        # Floe semantic attributes
        assert attrs.get("floe.namespace") == "analytics"
        assert attrs.get("floe.product.name") == "customer-360"
        # Static attributes
        assert attrs.get("operation") == "scan"
        # Dynamic attributes
        assert attrs.get("table_id") == "products"

    @pytest.mark.requirement("6C-FR-008")
    def test_async_with_attributes_fn(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Async function with attributes_fn works correctly."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_with_exporter

        def dynamic_attrs(query: str) -> dict[str, str]:
            return {"query": query}

        @traced(attributes_fn=dynamic_attrs)
        async def async_query(query: str) -> str:
            return f"result: {query}"

        result = asyncio.run(async_query("SELECT 1"))

        assert result == "result: SELECT 1"
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})
        assert attrs.get("query") == "SELECT 1"

    @pytest.mark.requirement("6C-FR-008")
    def test_nested_spans_with_attributes_fn(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Nested traced functions with attributes_fn preserve parent-child."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_with_exporter

        def outer_attrs(name: str) -> dict[str, str]:
            return {"outer.name": name}

        def inner_attrs(value: int) -> dict[str, str]:
            return {"inner.value": str(value)}

        @traced(attributes_fn=inner_attrs)
        def inner_op(value: int) -> int:
            return value * 2

        @traced(attributes_fn=outer_attrs)
        def outer_op(name: str) -> int:
            return inner_op(42)

        result = outer_op("pipeline")

        assert result == 84
        spans = exporter.get_finished_spans()
        assert len(spans) == 2

        inner_span = next(s for s in spans if s.name == "inner_op")
        outer_span = next(s for s in spans if s.name == "outer_op")

        # Parent-child relationship
        assert inner_span.parent is not None
        assert inner_span.parent.span_id == outer_span.context.span_id

        # Each span has its own dynamic attributes
        outer_attrs_dict = dict(outer_span.attributes or {})
        inner_attrs_dict = dict(inner_span.attributes or {})
        assert outer_attrs_dict.get("outer.name") == "pipeline"
        assert inner_attrs_dict.get("inner.value") == "42"


class TestSanitizedErrorRecording:
    """Tests for sanitized error recording in @traced."""

    @pytest.mark.requirement("6C-FR-008")
    def test_error_recording_uses_sanitized_message(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """When function raises with credentials in error, message is sanitized."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_with_exporter

        @traced
        def connect_db() -> None:
            raise ConnectionError(
                "Failed to connect: password=secret123 at host"  # pragma: allowlist secret
            )

        with pytest.raises(ConnectionError):
            connect_db()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]

        # Status description should be sanitized
        assert span.status.status_code == StatusCode.ERROR
        description = span.status.description or ""
        assert "secret123" not in description
        assert "<REDACTED>" in description

        # Exception attributes should be sanitized
        attrs = dict(span.attributes or {})
        assert attrs.get("exception.type") == "ConnectionError"
        exc_msg = attrs.get("exception.message", "")
        assert "secret123" not in exc_msg
        assert "<REDACTED>" in exc_msg

    @pytest.mark.requirement("6C-FR-008")
    def test_async_error_recording_uses_sanitized_message(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Async function error recording also uses sanitized messages."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_with_exporter

        @traced
        async def async_connect() -> None:
            raise ConnectionError(
                "auth failed: api_key=sk-12345 for endpoint"  # pragma: allowlist secret
            )

        with pytest.raises(ConnectionError):
            asyncio.run(async_connect())

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]

        attrs = dict(span.attributes or {})
        assert attrs.get("exception.type") == "ConnectionError"
        exc_msg = attrs.get("exception.message", "")
        assert "sk-12345" not in exc_msg
        assert "<REDACTED>" in exc_msg

    @pytest.mark.requirement("6C-FR-008")
    def test_create_span_error_recording_sanitized(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """create_span() also uses sanitized error recording."""
        from floe_core.telemetry.tracing import create_span

        _, exporter = tracer_with_exporter

        with pytest.raises(ValueError):
            with create_span("db_operation"):
                raise ValueError(
                    "Connection string: ://admin:supersecret@db:5432"  # pragma: allowlist secret
                )

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]

        attrs = dict(span.attributes or {})
        assert attrs.get("exception.type") == "ValueError"
        exc_msg = attrs.get("exception.message", "")
        assert "supersecret" not in exc_msg
        assert "<REDACTED>" in exc_msg

    @pytest.mark.requirement("6C-FR-008")
    def test_error_without_credentials_preserved(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Error messages without credentials are preserved unchanged."""
        from floe_core.telemetry.tracing import traced

        _, exporter = tracer_with_exporter

        @traced
        def failing_op() -> None:
            raise ValueError("Table not found: analytics.customers")

        with pytest.raises(ValueError):
            failing_op()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]

        description = span.status.description or ""
        assert "Table not found: analytics.customers" in description
        attrs = dict(span.attributes or {})
        assert attrs.get("exception.message") == "Table not found: analytics.customers"
        # No REDACTED markers since no credentials present
        assert "<REDACTED>" not in description

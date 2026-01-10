"""Unit tests for OpenTelemetry log correlation with structlog.

Tests cover:
- T057: structlog trace context processor (TestAddTraceContextProcessor)
- T058: trace_id injection (TestTraceIdInjection)
- T059: span_id injection (TestSpanIdInjection)

Requirements Covered:
- FR-015: Inject trace_id into all log records when a trace is active
- FR-016: Inject span_id into all log records when a span is active
- FR-017: Support structured logging format with trace context as fields
- FR-018: Support configurable log levels
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def tracer_provider_with_exporter() -> (
    Generator[tuple[TracerProvider, InMemorySpanExporter], None, None]
):
    """Create a TracerProvider with InMemorySpanExporter for testing.

    Yields:
        Tuple of (TracerProvider, InMemorySpanExporter) for test assertions.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_ON)

    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Set as global tracer provider for tests
    trace.set_tracer_provider(provider)

    yield provider, exporter

    exporter.clear()


class TestAddTraceContextProcessor:
    """Tests for add_trace_context structlog processor (T057).

    The add_trace_context processor should:
    - Add trace_id to event_dict when active span exists
    - Add span_id to event_dict when active span exists
    - Return event_dict unchanged when no active span
    - Format IDs as 32-char hex (trace_id) and 16-char hex (span_id)
    """

    @pytest.mark.requirement("FR-015")
    @pytest.mark.requirement("FR-016")
    def test_add_trace_context_adds_trace_id_and_span_id(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test add_trace_context adds both trace_id and span_id when span is active."""
        from floe_core.telemetry.logging import add_trace_context

        provider, _ = tracer_provider_with_exporter
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("test_span"):
            event_dict: dict[str, Any] = {"event": "test message"}
            result = add_trace_context(None, "info", event_dict)

            assert "trace_id" in result
            assert "span_id" in result
            # trace_id should be 32 hex chars
            assert len(result["trace_id"]) == 32
            assert all(c in "0123456789abcdef" for c in result["trace_id"])
            # span_id should be 16 hex chars
            assert len(result["span_id"]) == 16
            assert all(c in "0123456789abcdef" for c in result["span_id"])

    @pytest.mark.requirement("FR-015")
    def test_add_trace_context_no_ids_without_span(self) -> None:
        """Test add_trace_context does not add IDs when no span is active."""
        from floe_core.telemetry.logging import add_trace_context

        event_dict: dict[str, Any] = {"event": "test message"}
        result = add_trace_context(None, "info", event_dict)

        assert "trace_id" not in result
        assert "span_id" not in result
        assert result["event"] == "test message"

    @pytest.mark.requirement("FR-017")
    def test_add_trace_context_preserves_existing_fields(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test add_trace_context preserves existing event_dict fields."""
        from floe_core.telemetry.logging import add_trace_context

        provider, _ = tracer_provider_with_exporter
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("test_span"):
            event_dict: dict[str, Any] = {
                "event": "test message",
                "user_id": "12345",
                "action": "create",
            }
            result = add_trace_context(None, "info", event_dict)

            assert result["event"] == "test message"
            assert result["user_id"] == "12345"
            assert result["action"] == "create"
            assert "trace_id" in result
            assert "span_id" in result

    @pytest.mark.requirement("FR-015")
    @pytest.mark.requirement("FR-016")
    def test_add_trace_context_returns_event_dict(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test add_trace_context returns the modified event_dict."""
        from floe_core.telemetry.logging import add_trace_context

        provider, _ = tracer_provider_with_exporter
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("test_span"):
            event_dict: dict[str, Any] = {"event": "test"}
            result = add_trace_context(None, "info", event_dict)

            # Should return the same dict (or modified version)
            assert isinstance(result, dict)
            assert "event" in result


class TestTraceIdInjection:
    """Tests for trace_id injection into logs (T058).

    Validates FR-015: System MUST inject trace_id into all log records
    when a trace is active.
    """

    @pytest.mark.requirement("FR-015")
    def test_trace_id_format_is_hex_string(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test trace_id is formatted as 32-character hex string."""
        from floe_core.telemetry.logging import add_trace_context

        provider, _ = tracer_provider_with_exporter
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("test_span"):
            event_dict: dict[str, Any] = {"event": "test"}
            result = add_trace_context(None, "info", event_dict)

            trace_id = result["trace_id"]
            assert isinstance(trace_id, str)
            assert len(trace_id) == 32
            # Verify it's valid hex
            int(trace_id, 16)

    @pytest.mark.requirement("FR-015")
    def test_trace_id_matches_active_span(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test trace_id matches the active span's trace ID."""
        from floe_core.telemetry.logging import add_trace_context

        provider, exporter = tracer_provider_with_exporter
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("test_span"):
            event_dict: dict[str, Any] = {"event": "test"}
            result = add_trace_context(None, "info", event_dict)

        # Get the span's trace_id from the exporter (span is now finished)
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.context is not None
        expected_trace_id = format(span.context.trace_id, "032x")
        assert result["trace_id"] == expected_trace_id

    @pytest.mark.requirement("FR-015")
    def test_trace_id_consistent_across_child_spans(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test trace_id is consistent across parent and child spans."""
        from floe_core.telemetry.logging import add_trace_context

        provider, _ = tracer_provider_with_exporter
        tracer = provider.get_tracer("test")

        parent_trace_id = None
        child_trace_id = None

        with tracer.start_as_current_span("parent_span"):
            event_dict: dict[str, Any] = {"event": "parent"}
            result = add_trace_context(None, "info", event_dict)
            parent_trace_id = result["trace_id"]

            with tracer.start_as_current_span("child_span"):
                event_dict = {"event": "child"}
                result = add_trace_context(None, "info", event_dict)
                child_trace_id = result["trace_id"]

        assert parent_trace_id == child_trace_id


class TestSpanIdInjection:
    """Tests for span_id injection into logs (T059).

    Validates FR-016: System MUST inject span_id into all log records
    when a span is active.
    """

    @pytest.mark.requirement("FR-016")
    def test_span_id_format_is_hex_string(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test span_id is formatted as 16-character hex string."""
        from floe_core.telemetry.logging import add_trace_context

        provider, _ = tracer_provider_with_exporter
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("test_span"):
            event_dict: dict[str, Any] = {"event": "test"}
            result = add_trace_context(None, "info", event_dict)

            span_id = result["span_id"]
            assert isinstance(span_id, str)
            assert len(span_id) == 16
            # Verify it's valid hex
            int(span_id, 16)

    @pytest.mark.requirement("FR-016")
    def test_span_id_matches_active_span(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test span_id matches the active span's span ID."""
        from floe_core.telemetry.logging import add_trace_context

        provider, exporter = tracer_provider_with_exporter
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("test_span"):
            event_dict: dict[str, Any] = {"event": "test"}
            result = add_trace_context(None, "info", event_dict)

        # Get the span's span_id from the exporter (span is now finished)
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.context is not None
        expected_span_id = format(span.context.span_id, "016x")
        assert result["span_id"] == expected_span_id

    @pytest.mark.requirement("FR-016")
    def test_span_id_differs_between_spans(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test span_id is different for different spans in the same trace."""
        from floe_core.telemetry.logging import add_trace_context

        provider, _ = tracer_provider_with_exporter
        tracer = provider.get_tracer("test")

        parent_span_id = None
        child_span_id = None

        with tracer.start_as_current_span("parent_span"):
            event_dict: dict[str, Any] = {"event": "parent"}
            result = add_trace_context(None, "info", event_dict)
            parent_span_id = result["span_id"]

            with tracer.start_as_current_span("child_span"):
                event_dict = {"event": "child"}
                result = add_trace_context(None, "info", event_dict)
                child_span_id = result["span_id"]

        assert parent_span_id != child_span_id

    @pytest.mark.requirement("FR-016")
    def test_span_id_updates_with_context(
        self,
        tracer_provider_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test span_id updates when entering/exiting spans."""
        from floe_core.telemetry.logging import add_trace_context

        provider, _ = tracer_provider_with_exporter
        tracer = provider.get_tracer("test")

        span_ids: list[str] = []

        with tracer.start_as_current_span("span_1"):
            event_dict: dict[str, Any] = {"event": "in span_1"}
            result = add_trace_context(None, "info", event_dict)
            span_ids.append(str(result["span_id"]))

        with tracer.start_as_current_span("span_2"):
            event_dict = {"event": "in span_2"}
            result = add_trace_context(None, "info", event_dict)
            span_ids.append(str(result["span_id"]))

        # Each span should have a unique span_id
        assert len(set(span_ids)) == 2


class TestConfigureLogging:
    """Tests for configure_logging() function.

    Validates FR-017 and FR-018 requirements for structured logging
    configuration with trace context injection.
    """

    @pytest.mark.requirement("FR-017")
    def test_configure_logging_sets_up_structlog(self) -> None:
        """Test configure_logging sets up structlog with trace context processor."""
        from floe_core.telemetry.logging import configure_logging

        # Should not raise
        configure_logging()

    @pytest.mark.requirement("FR-018")
    def test_configure_logging_accepts_log_level(self) -> None:
        """Test configure_logging accepts log level parameter."""
        from floe_core.telemetry.logging import configure_logging

        # Should accept log level without raising
        configure_logging(log_level="DEBUG")
        configure_logging(log_level="INFO")
        configure_logging(log_level="WARNING")
        configure_logging(log_level="ERROR")

    @pytest.mark.requirement("FR-017")
    def test_configure_logging_enables_json_output(self) -> None:
        """Test configure_logging can enable JSON output format."""
        from floe_core.telemetry.logging import configure_logging

        # Should accept json_output parameter
        configure_logging(json_output=True)
        configure_logging(json_output=False)


class TestLogLevelConfiguration:
    """Tests for log level configuration support (part of T065).

    Validates FR-018: Support configurable log levels.
    """

    @pytest.mark.requirement("FR-018")
    def test_valid_log_levels_accepted(self) -> None:
        """Test all standard log levels are accepted."""
        from floe_core.telemetry.logging import configure_logging

        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            # Should not raise for valid levels
            configure_logging(log_level=level)

    @pytest.mark.requirement("FR-018")
    def test_log_level_case_insensitive(self) -> None:
        """Test log level configuration is case insensitive."""
        from floe_core.telemetry.logging import configure_logging

        # Should accept lowercase
        configure_logging(log_level="debug")
        configure_logging(log_level="info")
        configure_logging(log_level="warning")

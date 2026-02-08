"""Integration tests for OpenTelemetry log-trace correlation.

Tests cover:
- T060: Integration test for log-trace correlation

Requirements Covered:
- FR-015: Inject trace_id into all log records when a trace is active
- FR-016: Inject span_id into all log records when a span is active
- FR-017: Support structured logging format with trace context as fields
- FR-018: Support configurable log levels

These tests use real OpenTelemetry SDK and structlog to validate that log
entries are correctly enriched with trace context when within traced operations.
"""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING

import pytest
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def otel_provider() -> (
    Generator[tuple[TracerProvider, InMemorySpanExporter], None, None]
):
    """Set up a real OpenTelemetry TracerProvider with in-memory exporter.

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
    exporter.clear()


@pytest.fixture
def log_output() -> io.StringIO:
    """Create a StringIO buffer to capture log output.

    Returns:
        StringIO buffer for capturing log output.
    """
    return io.StringIO()


@pytest.fixture
def configured_structlog(
    log_output: io.StringIO,
) -> Generator[structlog.BoundLogger, None, None]:
    """Configure structlog with trace context processor and JSON output.

    This fixture sets up structlog with:
    - add_trace_context processor for trace/span ID injection
    - JSON renderer for structured output
    - StringIO writer for capturing output

    Args:
        log_output: StringIO buffer for capturing output.

    Yields:
        Configured structlog logger.
    """
    from floe_core.telemetry.logging import add_trace_context

    # Create a PrintLogger wrapper that writes to our StringIO
    class StringIOLogger:
        """Logger that writes to StringIO."""

        def __init__(self, stream: io.StringIO) -> None:
            self._stream = stream

        def msg(self, message: str) -> None:
            """Write message to stream."""
            self._stream.write(message + "\n")

        # structlog calls these methods based on log level
        debug = info = warning = error = critical = msg

    # Configure structlog with trace context processor
    structlog.configure(
        processors=[
            add_trace_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=lambda: StringIOLogger(log_output),
        cache_logger_on_first_use=False,
    )

    yield structlog.get_logger()

    # Reset structlog configuration
    structlog.reset_defaults()


class TestLogTraceCorrelation:
    """Integration tests for log-trace correlation (T060).

    Tests verify that logs contain trace_id and span_id when emitted
    within a traced context, using real structlog and OpenTelemetry.
    """

    @pytest.mark.requirement("FR-015")
    @pytest.mark.requirement("FR-016")
    def test_log_contains_trace_and_span_ids_in_traced_context(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        log_output: io.StringIO,
        configured_structlog: structlog.BoundLogger,
    ) -> None:
        """Test logs contain trace_id and span_id when within traced context."""
        provider, _ = otel_provider
        tracer = provider.get_tracer("test")
        log = configured_structlog

        with tracer.start_as_current_span("test_operation"):
            log.info("processing data")

        # Parse the JSON log output
        log_output.seek(0)
        log_line = log_output.read().strip()
        log_entry = json.loads(log_line)

        assert "trace_id" in log_entry
        assert "span_id" in log_entry
        assert log_entry["event"] == "processing data"

    @pytest.mark.requirement("FR-015")
    def test_trace_id_is_valid_hex_string(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        log_output: io.StringIO,
        configured_structlog: structlog.BoundLogger,
    ) -> None:
        """Test trace_id in log is a valid 32-character hex string."""
        provider, _ = otel_provider
        tracer = provider.get_tracer("test")
        log = configured_structlog

        with tracer.start_as_current_span("test_operation"):
            log.info("test message")

        log_output.seek(0)
        log_entry = json.loads(log_output.read().strip())

        trace_id = log_entry["trace_id"]
        assert isinstance(trace_id, str)
        assert len(trace_id) == 32
        # Verify it's valid hex
        int(trace_id, 16)

    @pytest.mark.requirement("FR-016")
    def test_span_id_is_valid_hex_string(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        log_output: io.StringIO,
        configured_structlog: structlog.BoundLogger,
    ) -> None:
        """Test span_id in log is a valid 16-character hex string."""
        provider, _ = otel_provider
        tracer = provider.get_tracer("test")
        log = configured_structlog

        with tracer.start_as_current_span("test_operation"):
            log.info("test message")

        log_output.seek(0)
        log_entry = json.loads(log_output.read().strip())

        span_id = log_entry["span_id"]
        assert isinstance(span_id, str)
        assert len(span_id) == 16
        # Verify it's valid hex
        int(span_id, 16)

    @pytest.mark.requirement("FR-015")
    @pytest.mark.requirement("FR-016")
    def test_trace_id_matches_active_span(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        log_output: io.StringIO,
        configured_structlog: structlog.BoundLogger,
    ) -> None:
        """Test trace_id in log matches the active span's trace ID."""
        provider, exporter = otel_provider
        tracer = provider.get_tracer("test")
        log = configured_structlog

        with tracer.start_as_current_span("test_operation"):
            log.info("test message")

        # Get span from exporter
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.context is not None

        # Parse log
        log_output.seek(0)
        log_entry = json.loads(log_output.read().strip())

        expected_trace_id = format(span.context.trace_id, "032x")
        expected_span_id = format(span.context.span_id, "016x")

        assert log_entry["trace_id"] == expected_trace_id
        assert log_entry["span_id"] == expected_span_id

    @pytest.mark.requirement("FR-015")
    @pytest.mark.requirement("FR-016")
    def test_no_trace_context_outside_span(
        self,
        log_output: io.StringIO,
        configured_structlog: structlog.BoundLogger,
    ) -> None:
        """Test logs do not contain trace context when outside a span."""
        log = configured_structlog

        log.info("message outside span")

        log_output.seek(0)
        log_entry = json.loads(log_output.read().strip())

        assert "trace_id" not in log_entry
        assert "span_id" not in log_entry
        assert log_entry["event"] == "message outside span"


class TestNestedSpanLogging:
    """Tests for logging within nested span contexts."""

    @pytest.mark.requirement("FR-015")
    def test_trace_id_consistent_in_nested_spans(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        log_output: io.StringIO,
        configured_structlog: structlog.BoundLogger,
    ) -> None:
        """Test trace_id is consistent across parent and child spans."""
        provider, _ = otel_provider
        tracer = provider.get_tracer("test")
        log = configured_structlog

        with tracer.start_as_current_span("parent"):
            log.info("parent message")
            with tracer.start_as_current_span("child"):
                log.info("child message")

        log_output.seek(0)
        lines = [json.loads(line) for line in log_output.read().strip().split("\n")]

        assert len(lines) == 2
        parent_trace_id = lines[0]["trace_id"]
        child_trace_id = lines[1]["trace_id"]

        # Same trace ID across parent and child
        assert parent_trace_id == child_trace_id

    @pytest.mark.requirement("FR-016")
    def test_span_id_differs_in_nested_spans(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        log_output: io.StringIO,
        configured_structlog: structlog.BoundLogger,
    ) -> None:
        """Test span_id is different for parent and child spans."""
        provider, _ = otel_provider
        tracer = provider.get_tracer("test")
        log = configured_structlog

        with tracer.start_as_current_span("parent"):
            log.info("parent message")
            with tracer.start_as_current_span("child"):
                log.info("child message")

        log_output.seek(0)
        lines = [json.loads(line) for line in log_output.read().strip().split("\n")]

        assert len(lines) == 2
        parent_span_id = lines[0]["span_id"]
        child_span_id = lines[1]["span_id"]

        # Different span IDs for parent and child
        assert parent_span_id != child_span_id


class TestStructuredLoggingFormat:
    """Tests for structured logging format with trace context (FR-017)."""

    @pytest.mark.requirement("FR-017")
    def test_json_output_contains_all_fields(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        log_output: io.StringIO,
        configured_structlog: structlog.BoundLogger,
    ) -> None:
        """Test JSON output contains event, level, timestamp, and trace context."""
        provider, _ = otel_provider
        tracer = provider.get_tracer("test")
        log = configured_structlog

        with tracer.start_as_current_span("test_operation"):
            log.info("structured message", custom_field="custom_value")

        log_output.seek(0)
        log_entry = json.loads(log_output.read().strip())

        # Standard structlog fields
        assert "event" in log_entry
        assert "level" in log_entry
        assert "timestamp" in log_entry

        # Trace context fields
        assert "trace_id" in log_entry
        assert "span_id" in log_entry

        # Custom field preserved
        assert log_entry["custom_field"] == "custom_value"

    @pytest.mark.requirement("FR-017")
    def test_custom_fields_preserved(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        log_output: io.StringIO,
        configured_structlog: structlog.BoundLogger,
    ) -> None:
        """Test custom log fields are preserved alongside trace context."""
        provider, _ = otel_provider
        tracer = provider.get_tracer("test")
        log = configured_structlog

        with tracer.start_as_current_span("test_operation"):
            log.info(
                "operation completed",
                user_id="user_123",
                duration_ms=150,
                status="success",
            )

        log_output.seek(0)
        log_entry = json.loads(log_output.read().strip())

        assert log_entry["user_id"] == "user_123"
        assert log_entry["duration_ms"] == 150
        assert log_entry["status"] == "success"
        assert "trace_id" in log_entry
        assert "span_id" in log_entry


class TestLogLevelSupport:
    """Tests for log level configuration support (FR-018)."""

    @pytest.mark.requirement("FR-018")
    def test_different_log_levels_include_trace_context(
        self,
        otel_provider: tuple[TracerProvider, InMemorySpanExporter],
        log_output: io.StringIO,
        configured_structlog: structlog.BoundLogger,
    ) -> None:
        """Test all log levels include trace context when in traced context."""
        provider, _ = otel_provider
        tracer = provider.get_tracer("test")
        log = configured_structlog

        with tracer.start_as_current_span("test_operation"):
            log.debug("debug message")
            log.info("info message")
            log.warning("warning message")
            log.error("error message")

        log_output.seek(0)
        lines = [json.loads(line) for line in log_output.read().strip().split("\n")]

        # All log entries should have trace context
        for line in lines:
            assert "trace_id" in line
            assert "span_id" in line

        # Verify log levels are preserved
        levels = [line["level"] for line in lines]
        assert "debug" in levels
        assert "info" in levels
        assert "warning" in levels
        assert "error" in levels

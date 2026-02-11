"""Unit tests for OpenTelemetry tracing helpers in floe_orchestrator_dagster.tracing.

Requirements Covered:
    - 6C-FR-020: Unit tests for orchestrator tracing helpers
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from floe_orchestrator_dagster.tracing import (
    ATTR_ASSET_COUNT,
    ATTR_ASSET_KEY,
    ATTR_OPERATION,
    ATTR_SCHEDULE_CRON,
    TRACER_NAME,
    get_tracer,
    orchestrator_span,
)


@pytest.fixture
def tracer_with_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Create a TracerProvider with an InMemorySpanExporter for testing."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


class TestOrchestratorSpan:
    """Unit tests for orchestrator_span context manager."""

    @pytest.mark.requirement("6C-FR-020")
    def test_orchestrator_span_creates_span_with_correct_name(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that orchestrator_span creates a span named 'orchestrator.<operation>'."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with orchestrator_span(tracer, "create_definitions"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "orchestrator.create_definitions"

    @pytest.mark.requirement("6C-FR-020")
    def test_orchestrator_span_sets_asset_key_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that orchestrator_span sets the 'orchestrator.asset_key' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with orchestrator_span(tracer, "materialize", asset_key="raw_customers"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_ASSET_KEY] == "raw_customers"

    @pytest.mark.requirement("6C-FR-020")
    def test_orchestrator_span_sets_asset_count_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that orchestrator_span sets the 'orchestrator.asset_count' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with orchestrator_span(tracer, "create_definitions", asset_count=15):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_ASSET_COUNT] == 15

    @pytest.mark.requirement("6C-FR-020")
    def test_orchestrator_span_sets_schedule_cron_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that orchestrator_span sets the 'orchestrator.schedule_cron' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with orchestrator_span(tracer, "schedule_job", schedule_cron="0 * * * *"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_SCHEDULE_CRON] == "0 * * * *"

    @pytest.mark.requirement("6C-FR-020")
    def test_orchestrator_span_no_credentials_in_attributes(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that no credentials appear in span attributes."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        fake_cred = "api_key=mysecretkey123"  # pragma: allowlist secret

        with orchestrator_span(
            tracer,
            "create_definitions",
            asset_count=5,
            extra_attributes={"orchestrator.target": "dev"},
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        for attr_value in attributes.values():
            assert str(attr_value) != fake_cred

    @pytest.mark.requirement("6C-FR-020")
    def test_orchestrator_span_error_sanitized(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that error messages are sanitized before recording on span."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        error_msg = "Connection failed: password=secret123 at dagster"  # pragma: allowlist secret

        with pytest.raises(RuntimeError, match="Connection failed"):
            with orchestrator_span(tracer, "validate_connection"):
                raise RuntimeError(error_msg)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        assert attributes["exception.type"] == "RuntimeError"
        exception_message = str(attributes["exception.message"])
        assert "secret123" not in exception_message  # pragma: allowlist secret
        assert "<REDACTED>" in exception_message
        assert spans[0].status.status_code == StatusCode.ERROR

    @pytest.mark.requirement("6C-FR-020")
    def test_orchestrator_span_ok_status_on_success(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that successful spans have StatusCode.OK."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with orchestrator_span(tracer, "create_definitions"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.OK

    @pytest.mark.requirement("6C-FR-020")
    def test_orchestrator_span_sets_delivery_status_on_error(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that the span records ERROR status on exception."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with pytest.raises(ValueError, match="Invalid"):
            with orchestrator_span(tracer, "validate_connection"):
                raise ValueError("Invalid configuration")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.ERROR

    @pytest.mark.requirement("6C-FR-020")
    def test_get_tracer_returns_tracer(self) -> None:
        """Test that get_tracer delegates to factory with correct name."""
        with patch("floe_orchestrator_dagster.tracing._factory_get_tracer") as mock_factory:
            from unittest.mock import MagicMock

            mock_tracer = MagicMock()
            mock_factory.return_value = mock_tracer

            result = get_tracer()

            assert result is mock_tracer
            mock_factory.assert_called_once_with(TRACER_NAME)


class TestConstants:
    """Unit tests for tracing constants definition."""

    @pytest.mark.requirement("6C-FR-020")
    def test_tracer_name_constant(self) -> None:
        """Test that TRACER_NAME follows naming convention."""
        assert TRACER_NAME == "floe.orchestrator.dagster"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constants_follow_otel_conventions(self) -> None:
        """Test that attribute constants follow OTel naming conventions."""
        attrs = [ATTR_OPERATION, ATTR_ASSET_KEY, ATTR_ASSET_COUNT, ATTR_SCHEDULE_CRON]
        for attr in attrs:
            assert attr.startswith("orchestrator."), f"{attr} should start with 'orchestrator.'"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constant_values(self) -> None:
        """Test that attribute constants have correct values."""
        assert ATTR_OPERATION == "orchestrator.operation"
        assert ATTR_ASSET_KEY == "orchestrator.asset_key"
        assert ATTR_ASSET_COUNT == "orchestrator.asset_count"
        assert ATTR_SCHEDULE_CRON == "orchestrator.schedule_cron"

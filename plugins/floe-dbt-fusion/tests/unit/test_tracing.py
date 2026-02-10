"""Unit tests for OpenTelemetry tracing helpers in floe_dbt_fusion.tracing.

Requirements Covered:
    - 6C-FR-020: Unit tests for dbt-fusion tracing helpers
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from floe_dbt_fusion.tracing import (
    ATTR_FALLBACK,
    ATTR_MODE,
    ATTR_MODEL_COUNT,
    ATTR_OPERATION,
    TRACER_NAME,
    dbt_fusion_span,
    get_tracer,
)


@pytest.fixture
def tracer_with_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Create a TracerProvider with an InMemorySpanExporter for testing."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


class TestDbtFusionSpan:
    """Unit tests for dbt_fusion_span context manager."""

    @pytest.mark.requirement("6C-FR-020")
    def test_dbt_fusion_span_creates_span_with_correct_name(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that dbt_fusion_span creates a span named 'dbt_fusion.<operation>'."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with dbt_fusion_span(tracer, "compile"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "dbt_fusion.compile"

    @pytest.mark.requirement("6C-FR-020")
    def test_dbt_fusion_span_sets_mode_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that dbt_fusion_span sets the 'dbt_fusion.mode' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with dbt_fusion_span(tracer, "run", mode="core"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_MODE] == "core"

    @pytest.mark.requirement("6C-FR-020")
    def test_dbt_fusion_span_sets_fallback_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that dbt_fusion_span sets the 'dbt_fusion.fallback' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with dbt_fusion_span(tracer, "run", fallback=True):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_FALLBACK] is True

    @pytest.mark.requirement("6C-FR-020")
    def test_dbt_fusion_span_sets_model_count_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that dbt_fusion_span sets the 'dbt_fusion.model_count' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with dbt_fusion_span(tracer, "compile", model_count=25):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_MODEL_COUNT] == 25

    @pytest.mark.requirement("6C-FR-020")
    def test_dbt_fusion_span_no_sql_in_attributes(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that no SQL content appears in span attributes."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with dbt_fusion_span(
            tracer,
            "compile",
            mode="fusion",
            model_count=5,
            extra_attributes={"dbt_fusion.target": "dev"},
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        # Verify no SQL content in attributes
        for attr_value in attributes.values():
            assert "SELECT" not in str(attr_value)
            assert "INSERT" not in str(attr_value)

    @pytest.mark.requirement("6C-FR-020")
    def test_dbt_fusion_span_error_sanitized(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that error messages are sanitized before recording on span."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        error_msg = "Compilation failed: password=secret123 in profiles"  # pragma: allowlist secret

        with pytest.raises(RuntimeError, match="Compilation failed"):
            with dbt_fusion_span(tracer, "compile", mode="fusion"):
                raise RuntimeError(error_msg)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        assert attributes["exception.type"] == "RuntimeError"
        exception_message = attributes["exception.message"]
        assert "secret123" not in exception_message  # pragma: allowlist secret
        assert "<REDACTED>" in exception_message
        assert spans[0].status.status_code == StatusCode.ERROR

    @pytest.mark.requirement("6C-FR-020")
    def test_dbt_fusion_span_ok_status_on_success(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that successful spans have StatusCode.OK."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with dbt_fusion_span(tracer, "test", mode="core"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.OK

    @pytest.mark.requirement("6C-FR-020")
    def test_get_tracer_returns_tracer(self) -> None:
        """Test that get_tracer delegates to factory with correct name."""
        with patch("floe_dbt_fusion.tracing._factory_get_tracer") as mock_factory:
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
        assert TRACER_NAME == "floe.dbt.fusion"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constants_follow_otel_conventions(self) -> None:
        """Test that attribute constants follow OTel naming conventions."""
        attrs = [ATTR_MODE, ATTR_OPERATION, ATTR_FALLBACK, ATTR_MODEL_COUNT]
        for attr in attrs:
            assert attr.startswith("dbt_fusion."), f"{attr} should start with 'dbt_fusion.'"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constant_values(self) -> None:
        """Test that attribute constants have correct values."""
        assert ATTR_MODE == "dbt_fusion.mode"
        assert ATTR_OPERATION == "dbt_fusion.operation"
        assert ATTR_FALLBACK == "dbt_fusion.fallback"
        assert ATTR_MODEL_COUNT == "dbt_fusion.model_count"

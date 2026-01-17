"""Unit tests for floe_iceberg.telemetry module.

Tests the @traced decorator for OpenTelemetry instrumentation.

Note:
    No __init__.py files in test directories - pytest uses importlib mode
    which causes namespace collisions with __init__.py files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_tracer() -> Generator[MagicMock, None, None]:
    """Create a mock tracer for testing.

    Yields:
        MagicMock tracer with span context manager.
    """
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=None)
    mock_span.set_attribute = MagicMock()
    mock_span.set_status = MagicMock()
    mock_span.record_exception = MagicMock()

    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span = MagicMock(return_value=mock_span)

    with patch(
        "floe_iceberg.telemetry.get_tracer", return_value=mock_tracer
    ) as mock_get_tracer:
        mock_get_tracer.return_value = mock_tracer
        yield mock_tracer


# =============================================================================
# traced Decorator Tests
# =============================================================================


class TestTracedDecorator:
    """Tests for the @traced decorator."""

    @pytest.mark.requirement("FR-041")
    def test_traced_creates_span(self, mock_tracer: MagicMock) -> None:
        """Test @traced decorator creates OTel span for decorated function.

        Acceptance criteria from T069:
        - @traced decorator creates OTel span for decorated function
        """
        from floe_iceberg.telemetry import traced

        @traced
        def my_function() -> str:
            return "result"

        result = my_function()

        assert result == "result"
        mock_tracer.start_as_current_span.assert_called_once()
        # Span name should be the function name
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[0][0] == "my_function"

    @pytest.mark.requirement("FR-041")
    def test_traced_includes_operation_name_attribute(
        self, mock_tracer: MagicMock
    ) -> None:
        """Test span includes operation name attribute.

        Acceptance criteria from T069:
        - Span includes operation name and attributes
        """
        from floe_iceberg.telemetry import traced

        @traced
        def create_table() -> None:
            pass

        create_table()

        mock_span = mock_tracer.start_as_current_span.return_value
        mock_span.__enter__.return_value.set_attribute.assert_any_call(
            "floe.iceberg.operation", "create_table"
        )

    @pytest.mark.requirement("FR-041")
    def test_traced_with_custom_operation_name(self, mock_tracer: MagicMock) -> None:
        """Test @traced accepts custom operation name.

        Verifies decorator parameter for custom span name.
        """
        from floe_iceberg.telemetry import traced

        @traced(operation_name="custom_operation")
        def my_function() -> None:
            pass

        my_function()

        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[0][0] == "custom_operation"

    @pytest.mark.requirement("FR-042")
    def test_traced_with_extra_attributes(self, mock_tracer: MagicMock) -> None:
        """Test @traced supports optional extra attributes via decorator parameter.

        Acceptance criteria from T069:
        - Supports optional extra attributes via decorator parameter
        """
        from floe_iceberg.telemetry import traced

        @traced(attributes={"table": "customers", "namespace": "bronze"})
        def write_data() -> None:
            pass

        write_data()

        mock_span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        mock_span.set_attribute.assert_any_call("table", "customers")
        mock_span.set_attribute.assert_any_call("namespace", "bronze")

    @pytest.mark.requirement("FR-041")
    def test_traced_preserves_function_return_value(
        self, mock_tracer: MagicMock
    ) -> None:
        """Test @traced preserves decorated function's return value."""
        from floe_iceberg.telemetry import traced

        @traced
        def calculate() -> dict[str, int]:
            return {"count": 42, "total": 100}

        result = calculate()

        assert result == {"count": 42, "total": 100}

    @pytest.mark.requirement("FR-041")
    def test_traced_preserves_function_arguments(self, mock_tracer: MagicMock) -> None:
        """Test @traced preserves arguments passed to decorated function."""
        from floe_iceberg.telemetry import traced

        captured_args: dict[str, Any] = {}

        @traced
        def process_data(data: list[int], multiplier: int = 2) -> list[int]:
            captured_args["data"] = data
            captured_args["multiplier"] = multiplier
            return [x * multiplier for x in data]

        result = process_data([1, 2, 3], multiplier=10)

        assert result == [10, 20, 30]
        assert captured_args["data"] == [1, 2, 3]
        assert captured_args["multiplier"] == 10

    @pytest.mark.requirement("FR-042")
    def test_traced_handles_nested_spans(self, mock_tracer: MagicMock) -> None:
        """Test @traced handles nested spans correctly.

        Acceptance criteria from T069:
        - Handles nested spans correctly
        """
        from floe_iceberg.telemetry import traced

        call_order: list[str] = []

        @traced
        def outer_function() -> str:
            call_order.append("outer_start")
            result = inner_function()
            call_order.append("outer_end")
            return f"outer({result})"

        @traced
        def inner_function() -> str:
            call_order.append("inner")
            return "inner_result"

        result = outer_function()

        assert result == "outer(inner_result)"
        assert call_order == ["outer_start", "inner", "outer_end"]
        # Both functions should create spans
        assert mock_tracer.start_as_current_span.call_count == 2

    @pytest.mark.requirement("FR-041")
    def test_traced_records_exception_on_error(self, mock_tracer: MagicMock) -> None:
        """Test @traced records exception when function raises."""
        from floe_iceberg.telemetry import traced

        @traced
        def failing_function() -> None:
            msg = "Something went wrong"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Something went wrong"):
            failing_function()

        mock_span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        mock_span.record_exception.assert_called_once()

    @pytest.mark.requirement("FR-041")
    def test_traced_sets_error_status_on_exception(
        self, mock_tracer: MagicMock
    ) -> None:
        """Test @traced sets span status to error when exception occurs."""
        from opentelemetry.trace import StatusCode

        from floe_iceberg.telemetry import traced

        @traced
        def failing_function() -> None:
            msg = "Error"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError):
            failing_function()

        mock_span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        # Check set_status was called with error status
        mock_span.set_status.assert_called()
        status_call = mock_span.set_status.call_args[0][0]
        assert status_call.status_code == StatusCode.ERROR

    @pytest.mark.requirement("FR-041")
    def test_traced_uses_global_tracer_provider(self) -> None:
        """Test @traced uses opentelemetry-api tracer from GlobalTracerProvider.

        Acceptance criteria from T069:
        - Uses opentelemetry-api (tracer from GlobalTracerProvider)
        """
        from floe_iceberg.telemetry import get_tracer

        tracer = get_tracer()

        # Verify tracer is from opentelemetry
        assert tracer is not None
        assert hasattr(tracer, "start_as_current_span")

    @pytest.mark.requirement("FR-041")
    def test_traced_preserves_function_metadata(self, mock_tracer: MagicMock) -> None:
        """Test @traced preserves function name and docstring."""
        from floe_iceberg.telemetry import traced

        @traced
        def documented_function() -> None:
            """This is the docstring."""
            pass

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is the docstring."

    @pytest.mark.requirement("FR-042")
    def test_traced_with_dynamic_attributes_callable(
        self, mock_tracer: MagicMock
    ) -> None:
        """Test @traced supports callable for dynamic attributes from function args."""
        from floe_iceberg.telemetry import traced

        def extract_attributes(
            table_id: str, namespace: str, **kwargs: Any
        ) -> dict[str, str]:
            return {"table_id": table_id, "namespace": namespace}

        @traced(attributes_fn=extract_attributes)
        def load_table(table_id: str, namespace: str) -> str:
            return f"{namespace}.{table_id}"

        result = load_table("customers", "bronze")

        assert result == "bronze.customers"
        mock_span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        mock_span.set_attribute.assert_any_call("table_id", "customers")
        mock_span.set_attribute.assert_any_call("namespace", "bronze")


# =============================================================================
# Tracer Name Tests
# =============================================================================


class TestTracerConfiguration:
    """Tests for tracer configuration."""

    @pytest.mark.requirement("FR-041")
    def test_tracer_has_correct_name(self) -> None:
        """Test tracer uses floe-iceberg as instrumentation name."""
        from floe_iceberg.telemetry import TRACER_NAME

        # Verify the tracer name constant
        assert TRACER_NAME == "floe-iceberg"

    @pytest.mark.requirement("FR-041")
    def test_get_tracer_returns_tracer_with_correct_name(self) -> None:
        """Test get_tracer returns tracer from trace.get_tracer with correct name."""
        with patch("floe_iceberg.telemetry.trace.get_tracer") as mock_get_tracer:
            # Reset the cached tracer
            import floe_iceberg.telemetry

            floe_iceberg.telemetry._tracer = None

            mock_tracer = MagicMock()
            mock_get_tracer.return_value = mock_tracer

            from floe_iceberg.telemetry import get_tracer

            result = get_tracer()

            mock_get_tracer.assert_called_once_with("floe-iceberg")
            assert result == mock_tracer

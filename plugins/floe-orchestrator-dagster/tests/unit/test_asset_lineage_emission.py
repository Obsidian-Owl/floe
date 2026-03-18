"""Unit tests for lineage emission wiring in _asset_fn().

These tests verify that _asset_fn() — the inner function created by
_create_asset_for_transform() — correctly calls lineage emission methods
before, during, and after dbt.run_models().

Requirements Covered:
    AC-1: emit_start called BEFORE dbt.run_models with correct args
    AC-2: emit_complete called on successful dbt run
    AC-3: emit_fail called on dbt exception, exception re-raised
    AC-4/AC-8: extract_dbt_model_lineage called, events emitted via emit_event
    AC-11: lineage emission failure does not prevent dbt execution
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from floe_core.plugins.orchestrator import TransformConfig

# ---------------------------------------------------------------------------
# Constants to avoid duplicate string literals
# ---------------------------------------------------------------------------
MODEL_NAME = "stg_customers"
_PLUGIN_MODULE = "floe_orchestrator_dagster.plugin"
_EXTRACT_FN = f"{_PLUGIN_MODULE}.extract_dbt_model_lineage"
_TRACE_CORRELATION_BUILDER = f"{_PLUGIN_MODULE}.TraceCorrelationFacetBuilder"
AC_1 = "AC-1"
AC_2 = "AC-2"
AC_3 = "AC-3"
AC_4 = "AC-4"
AC_8 = "AC-8"
AC_11 = "AC-11"
DBT_PROJECT_DIR = "/tmp/dbt_project"
FAKE_RUN_ID = uuid4()
FAKE_NAMESPACE = "test-namespace"
TRACE_CORRELATION_FACET = {"traceId": "abc123", "spanId": "def456"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_dbt_result_success() -> MagicMock:
    """Create a mock successful dbt run result.

    Returns:
        MagicMock with success=True and project_dir set.
    """
    result = MagicMock()
    result.success = True
    result.models_run = 1
    result.failures = 0
    result.project_dir = Path(DBT_PROJECT_DIR)
    return result


@pytest.fixture
def mock_dbt_result_failure() -> MagicMock:
    """Create a mock failed dbt run result.

    Returns:
        MagicMock with success=False.
    """
    result = MagicMock()
    result.success = False
    result.models_run = 1
    result.failures = 1
    result.project_dir = Path(DBT_PROJECT_DIR)
    return result


@pytest.fixture
def mock_dbt_resource(mock_dbt_result_success: MagicMock) -> MagicMock:
    """Create a mock dbt resource that returns a successful run result.

    Args:
        mock_dbt_result_success: The successful dbt result to return.

    Returns:
        MagicMock with run_models configured.
    """
    dbt = MagicMock()
    dbt.run_models.return_value = mock_dbt_result_success
    return dbt


@pytest.fixture
def mock_lineage_resource() -> MagicMock:
    """Create a mock lineage resource with the full lineage API.

    Returns:
        MagicMock with emit_start, emit_complete, emit_fail, emit_event, namespace.
    """
    lineage = MagicMock()
    lineage.emit_start.return_value = FAKE_RUN_ID
    lineage.namespace = FAKE_NAMESPACE
    return lineage


@pytest.fixture
def mock_context(mock_lineage_resource: MagicMock) -> MagicMock:
    """Create a mock Dagster AssetExecutionContext.

    Args:
        mock_lineage_resource: The mock lineage resource to wire into context.

    Returns:
        MagicMock that mimics AssetExecutionContext with resources.lineage.
    """
    context = MagicMock()
    context.resources.lineage = mock_lineage_resource
    context.log = MagicMock()
    return context


@pytest.fixture
def sample_transform() -> TransformConfig:
    """Create a sample TransformConfig for the asset under test.

    Returns:
        TransformConfig with name 'stg_customers'.
    """
    return TransformConfig(
        name=MODEL_NAME,
        path="models/staging/stg_customers.sql",
        schema_name="staging",
        materialization="view",
        compute="duckdb",
    )


@pytest.fixture
def sample_lineage_events() -> list[MagicMock]:
    """Create mock lineage events for extract_dbt_model_lineage to return.

    Returns:
        List of 2 mock LineageEvent objects.
    """
    event1 = MagicMock(name="lineage_event_start")
    event2 = MagicMock(name="lineage_event_complete")
    return [event1, event2]


def _invoke_asset_fn(
    dagster_plugin: Any,
    transform: TransformConfig,
    context: MagicMock,
    dbt: MagicMock,
) -> None:
    """Helper to create an asset and invoke its inner _asset_fn.

    Creates an asset via _create_asset_for_transform() and calls the
    underlying compute function with the given context and dbt resource.

    Args:
        dagster_plugin: DagsterOrchestratorPlugin instance.
        transform: TransformConfig defining the asset.
        context: Mock Dagster context.
        dbt: Mock dbt resource.
    """
    asset_def = dagster_plugin._create_asset_for_transform(
        transform=transform,
        deps=[],
        metadata={"compute": "duckdb"},
    )
    # The @asset decorator wraps _asset_fn in a DecoratedOpFunction namedtuple.
    # The original function is accessible via .decorated_fn on the compute_fn.
    inner_fn = asset_def.op.compute_fn.decorated_fn
    inner_fn(context, dbt)


# ---------------------------------------------------------------------------
# AC-1: emit_start called BEFORE dbt.run_models with correct args
# ---------------------------------------------------------------------------


class TestEmitStartBeforeDbt:
    """Tests verifying emit_start is called before dbt.run_models (AC-1).

    AC-1: _asset_fn() calls lineage.emit_start(job_name, run_facets=...)
    BEFORE dbt.run_models(). The job_name is the model name. The
    TraceCorrelation facet comes from TraceCorrelationFacetBuilder.from_otel_context().
    """

    @pytest.mark.requirement(AC_1)
    def test_emit_start_called_before_dbt_run(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test emit_start is invoked before dbt.run_models via call ordering.

        Uses side_effect on dbt.run_models to assert that emit_start was
        already called when dbt.run_models executes. This proves ordering,
        not just that both were called.
        """
        call_order: list[str] = []

        original_emit_start = mock_lineage_resource.emit_start

        def track_emit_start(*args: Any, **kwargs: Any) -> UUID:
            call_order.append("emit_start")
            return original_emit_start(*args, **kwargs)

        mock_lineage_resource.emit_start.side_effect = track_emit_start

        original_run_models = mock_dbt_resource.run_models.return_value

        def track_run_models(*args: Any, **kwargs: Any) -> Any:
            call_order.append("run_models")
            return original_run_models

        mock_dbt_resource.run_models.side_effect = track_run_models

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        assert "emit_start" in call_order, "emit_start was never called"
        assert "run_models" in call_order, "dbt.run_models was never called"
        assert call_order.index("emit_start") < call_order.index("run_models"), (
            f"emit_start must be called BEFORE dbt.run_models, but call order was: {call_order}"
        )

    @pytest.mark.requirement(AC_1)
    def test_emit_start_receives_model_name_as_job_name(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test emit_start is called with the model name as job_name.

        The first positional argument to emit_start must be the dbt model
        name (e.g., 'stg_customers'), not a generic name or empty string.
        """
        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_lineage_resource.emit_start.assert_called_once()
        call_args = mock_lineage_resource.emit_start.call_args
        # job_name is the first positional arg
        actual_job_name = call_args.args[0] if call_args.args else call_args.kwargs.get("job_name")
        assert actual_job_name == MODEL_NAME, (
            f"emit_start job_name must be '{MODEL_NAME}', got '{actual_job_name}'"
        )

    @pytest.mark.requirement(AC_1)
    def test_emit_start_includes_trace_correlation_facet(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test emit_start passes TraceCorrelation facet from OTel context.

        When TraceCorrelationFacetBuilder.from_otel_context() returns a non-None
        facet, it MUST appear in run_facets under the 'traceCorrelation' key.
        """
        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(
                f"{_TRACE_CORRELATION_BUILDER}.from_otel_context",
                return_value=TRACE_CORRELATION_FACET,
            ),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_lineage_resource.emit_start.assert_called_once()
        call_kwargs = mock_lineage_resource.emit_start.call_args.kwargs
        run_facets = call_kwargs.get("run_facets", {})
        assert "traceCorrelation" in run_facets, (
            f"emit_start run_facets must contain 'traceCorrelation' key, "
            f"got keys: {list(run_facets.keys())}"
        )
        assert run_facets["traceCorrelation"] == TRACE_CORRELATION_FACET, (
            f"traceCorrelation facet must be the value from "
            f"TraceCorrelationFacetBuilder.from_otel_context(), "
            f"got: {run_facets['traceCorrelation']}"
        )

    @pytest.mark.requirement(AC_1)
    def test_emit_start_omits_trace_correlation_when_none(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test emit_start handles None from TraceCorrelationFacetBuilder gracefully.

        When from_otel_context() returns None (no active OTel span), the
        run_facets should either be empty or omit traceCorrelation, but
        emit_start MUST still be called.
        """
        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_lineage_resource.emit_start.assert_called_once()
        call_kwargs = mock_lineage_resource.emit_start.call_args.kwargs
        run_facets = call_kwargs.get("run_facets")
        # When None, either run_facets is None/empty or lacks traceCorrelation
        if run_facets is not None:
            assert run_facets.get("traceCorrelation") is None, (
                "When from_otel_context() returns None, traceCorrelation must not be set"
            )

    @pytest.mark.requirement(AC_1)
    def test_emit_start_called_with_different_model_names(
        self,
        dagster_plugin: Any,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test emit_start uses the specific model name, not a hardcoded value.

        Creates two different assets and verifies emit_start receives the
        correct model name for each. This catches hardcoded return values.
        """
        models = ["dim_orders", "fct_revenue"]
        received_names: list[str] = []

        def capture_job_name(job_name: str, **kwargs: Any) -> UUID:
            received_names.append(job_name)
            return uuid4()

        mock_lineage_resource.emit_start.side_effect = capture_job_name

        for model_name in models:
            mock_lineage_resource.emit_start.reset_mock()
            received_names.clear()

            transform = TransformConfig(name=model_name, compute="duckdb")
            with (
                patch(_EXTRACT_FN, return_value=[]),
                patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
            ):
                _invoke_asset_fn(dagster_plugin, transform, mock_context, mock_dbt_resource)

            assert len(received_names) == 1, (
                f"emit_start should be called once for model '{model_name}'"
            )
            assert received_names[0] == model_name, (
                f"emit_start job_name for model '{model_name}' was '{received_names[0]}'"
            )


# ---------------------------------------------------------------------------
# AC-2: emit_complete called on successful dbt run
# ---------------------------------------------------------------------------


class TestEmitCompleteOnSuccess:
    """Tests verifying emit_complete is called on successful dbt run (AC-2).

    AC-2: On successful dbt run (result.success=True), _asset_fn() calls
    lineage.emit_complete(run_id, job_name) with the run_id from emit_start().
    """

    @pytest.mark.requirement(AC_2)
    def test_emit_complete_called_on_success(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test emit_complete is called when dbt run succeeds."""
        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_lineage_resource.emit_complete.assert_called_once()

    @pytest.mark.requirement(AC_2)
    def test_emit_complete_receives_run_id_from_emit_start(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test emit_complete receives the exact run_id returned by emit_start.

        This verifies that the implementation correctly threads the run_id
        from emit_start to emit_complete, not a hardcoded or new UUID.
        """
        specific_run_id = uuid4()
        mock_lineage_resource.emit_start.return_value = specific_run_id

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_lineage_resource.emit_complete.assert_called_once()
        complete_args = mock_lineage_resource.emit_complete.call_args
        actual_run_id = (
            complete_args.args[0] if complete_args.args else complete_args.kwargs.get("run_id")
        )
        assert actual_run_id == specific_run_id, (
            f"emit_complete run_id must be {specific_run_id} (from emit_start), got {actual_run_id}"
        )

    @pytest.mark.requirement(AC_2)
    def test_emit_complete_receives_correct_job_name(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test emit_complete receives the model name as job_name."""
        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        complete_args = mock_lineage_resource.emit_complete.call_args
        actual_job_name = (
            complete_args.args[1]
            if len(complete_args.args) > 1
            else complete_args.kwargs.get("job_name")
        )
        assert actual_job_name == MODEL_NAME, (
            f"emit_complete job_name must be '{MODEL_NAME}', got '{actual_job_name}'"
        )

    @pytest.mark.requirement(AC_2)
    def test_emit_fail_not_called_on_success(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test emit_fail is NOT called when dbt run succeeds.

        A sloppy implementation might call both emit_complete and emit_fail.
        """
        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_lineage_resource.emit_fail.assert_not_called()


# ---------------------------------------------------------------------------
# AC-3: emit_fail called on dbt exception, exception re-raised
# ---------------------------------------------------------------------------


class TestEmitFailOnException:
    """Tests verifying emit_fail on dbt exceptions (AC-3).

    AC-3: When dbt raises an exception, _asset_fn() calls
    lineage.emit_fail(run_id, job_name, error_message=...) BEFORE
    re-raising the exception.
    """

    @pytest.mark.requirement(AC_3)
    def test_emit_fail_called_when_dbt_raises(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
        mock_dbt_result_failure: MagicMock,
    ) -> None:
        """Test emit_fail is called when dbt.run_models result indicates failure.

        The current code raises RuntimeError on result.success=False.
        emit_fail MUST be called before re-raising.
        """
        mock_dbt_resource.run_models.return_value = mock_dbt_result_failure

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
            pytest.raises(RuntimeError),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_lineage_resource.emit_fail.assert_called_once()

    @pytest.mark.requirement(AC_3)
    def test_emit_fail_called_when_dbt_run_models_throws(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test emit_fail is called when dbt.run_models raises an exception.

        Covers the case where run_models itself throws (not just returns failure).
        """
        mock_dbt_resource.run_models.side_effect = RuntimeError("dbt crashed")

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
            pytest.raises(RuntimeError, match="dbt crashed"),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_lineage_resource.emit_fail.assert_called_once()

    @pytest.mark.requirement(AC_3)
    def test_emit_fail_receives_run_id_from_emit_start(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
        mock_dbt_result_failure: MagicMock,
    ) -> None:
        """Test emit_fail receives the exact run_id returned by emit_start."""
        specific_run_id = uuid4()
        mock_lineage_resource.emit_start.return_value = specific_run_id
        mock_dbt_resource.run_models.return_value = mock_dbt_result_failure

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
            pytest.raises(RuntimeError),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        fail_args = mock_lineage_resource.emit_fail.call_args
        actual_run_id = fail_args.args[0] if fail_args.args else fail_args.kwargs.get("run_id")
        assert actual_run_id == specific_run_id, (
            f"emit_fail run_id must be {specific_run_id} (from emit_start), got {actual_run_id}"
        )

    @pytest.mark.requirement(AC_3)
    def test_emit_fail_receives_correct_job_name(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
        mock_dbt_result_failure: MagicMock,
    ) -> None:
        """Test emit_fail receives the model name as job_name."""
        mock_dbt_resource.run_models.return_value = mock_dbt_result_failure

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
            pytest.raises(RuntimeError),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        fail_args = mock_lineage_resource.emit_fail.call_args
        actual_job_name = (
            fail_args.args[1] if len(fail_args.args) > 1 else fail_args.kwargs.get("job_name")
        )
        assert actual_job_name == MODEL_NAME, (
            f"emit_fail job_name must be '{MODEL_NAME}', got '{actual_job_name}'"
        )

    @pytest.mark.requirement(AC_3)
    def test_emit_fail_includes_error_message(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
        mock_dbt_result_failure: MagicMock,
    ) -> None:
        """Test emit_fail includes error_message kwarg.

        The error_message should contain meaningful failure info, not be
        empty or None.
        """
        mock_dbt_resource.run_models.return_value = mock_dbt_result_failure

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
            pytest.raises(RuntimeError),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        fail_kwargs = mock_lineage_resource.emit_fail.call_args.kwargs
        error_msg = fail_kwargs.get("error_message")
        assert error_msg is not None, "emit_fail must include error_message kwarg"
        assert len(error_msg) > 0, "emit_fail error_message must not be empty"

    @pytest.mark.requirement(AC_3)
    def test_exception_is_reraised_after_emit_fail(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
        mock_dbt_result_failure: MagicMock,
    ) -> None:
        """Test the original exception is re-raised after emit_fail.

        The exception must propagate to the caller, not be swallowed.
        """
        mock_dbt_resource.run_models.return_value = mock_dbt_result_failure

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="failed"):
                _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

    @pytest.mark.requirement(AC_3)
    def test_emit_complete_not_called_on_failure(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
        mock_dbt_result_failure: MagicMock,
    ) -> None:
        """Test emit_complete is NOT called when dbt run fails.

        A sloppy implementation might call both emit_complete and emit_fail.
        """
        mock_dbt_resource.run_models.return_value = mock_dbt_result_failure

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
            pytest.raises(RuntimeError),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_lineage_resource.emit_complete.assert_not_called()


# ---------------------------------------------------------------------------
# AC-4/AC-8: extract_dbt_model_lineage called, events emitted
# ---------------------------------------------------------------------------


class TestExtractAndEmitLineageEvents:
    """Tests verifying dbt model lineage extraction and emission (AC-4/AC-8).

    AC-4/AC-8: After dbt.run_models() returns (before success check),
    extract_dbt_model_lineage() is called and each returned event is
    emitted via lineage.emit_event(event).
    """

    @pytest.mark.requirement(AC_4)
    def test_extract_dbt_model_lineage_called_after_dbt_run(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test extract_dbt_model_lineage is called after dbt.run_models."""
        with (
            patch(_EXTRACT_FN, return_value=[]) as mock_extract,
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_extract.assert_called_once()

    @pytest.mark.requirement(AC_4)
    def test_extract_receives_correct_project_dir(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test extract_dbt_model_lineage receives dbt project_dir from result."""
        with (
            patch(_EXTRACT_FN, return_value=[]) as mock_extract,
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        call_args = mock_extract.call_args
        actual_project_dir = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("project_dir")
        )
        assert actual_project_dir == Path(DBT_PROJECT_DIR), (
            f"extract_dbt_model_lineage project_dir must be {DBT_PROJECT_DIR}, "
            f"got {actual_project_dir}"
        )

    @pytest.mark.requirement(AC_4)
    def test_extract_receives_run_id_from_emit_start(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test extract receives the parent_run_id from emit_start."""
        specific_run_id = uuid4()
        mock_lineage_resource.emit_start.return_value = specific_run_id

        with (
            patch(_EXTRACT_FN, return_value=[]) as mock_extract,
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        call_args = mock_extract.call_args
        actual_parent_run_id = (
            call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("parent_run_id")
        )
        assert actual_parent_run_id == specific_run_id, (
            f"extract parent_run_id must be {specific_run_id}, got {actual_parent_run_id}"
        )

    @pytest.mark.requirement(AC_4)
    def test_extract_receives_model_name_as_parent_job_name(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test extract receives model name as parent_job_name."""
        with (
            patch(_EXTRACT_FN, return_value=[]) as mock_extract,
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        call_args = mock_extract.call_args
        actual_parent_job = (
            call_args.args[2]
            if len(call_args.args) > 2
            else call_args.kwargs.get("parent_job_name")
        )
        assert actual_parent_job == MODEL_NAME, (
            f"extract parent_job_name must be '{MODEL_NAME}', got '{actual_parent_job}'"
        )

    @pytest.mark.requirement(AC_4)
    def test_extract_receives_namespace_from_lineage_resource(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test extract receives the namespace from lineage.namespace."""
        with (
            patch(_EXTRACT_FN, return_value=[]) as mock_extract,
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        call_args = mock_extract.call_args
        actual_namespace = (
            call_args.args[3] if len(call_args.args) > 3 else call_args.kwargs.get("namespace")
        )
        assert actual_namespace == FAKE_NAMESPACE, (
            f"extract namespace must be '{FAKE_NAMESPACE}', got '{actual_namespace}'"
        )

    @pytest.mark.requirement(AC_8)
    def test_each_extracted_event_emitted_via_emit_event(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
        sample_lineage_events: list[MagicMock],
    ) -> None:
        """Test each event from extract_dbt_model_lineage is emitted via emit_event.

        Verifies that emit_event is called once per extracted event, with the
        exact event objects returned by the extractor.
        """
        with (
            patch(_EXTRACT_FN, return_value=sample_lineage_events),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        assert mock_lineage_resource.emit_event.call_count == len(sample_lineage_events), (
            f"emit_event should be called {len(sample_lineage_events)} times, "
            f"got {mock_lineage_resource.emit_event.call_count}"
        )

        # Verify the exact event objects were passed
        for i, expected_event in enumerate(sample_lineage_events):
            actual_event = mock_lineage_resource.emit_event.call_args_list[i].args[0]
            assert actual_event is expected_event, (
                f"emit_event call {i} should receive event {expected_event}, got {actual_event}"
            )

    @pytest.mark.requirement(AC_8)
    def test_no_emit_event_when_extract_returns_empty(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test emit_event is not called when extractor returns empty list."""
        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_lineage_resource.emit_event.assert_not_called()

    @pytest.mark.requirement(AC_4)
    def test_extract_called_even_on_dbt_failure(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
        mock_dbt_result_failure: MagicMock,
    ) -> None:
        """Test extract_dbt_model_lineage is called even when dbt run fails.

        The extraction happens after dbt.run_models returns (regardless of
        success), before the success check that raises RuntimeError.
        """
        mock_dbt_resource.run_models.return_value = mock_dbt_result_failure

        with (
            patch(_EXTRACT_FN, return_value=[]) as mock_extract,
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
            pytest.raises(RuntimeError),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        mock_extract.assert_called_once()


# ---------------------------------------------------------------------------
# AC-11: Lineage emission failure does not prevent dbt execution
# ---------------------------------------------------------------------------


class TestLineageFailureDoesNotBlockDbt:
    """Tests verifying lineage failures are non-fatal (AC-11).

    AC-11: If lineage emission fails (emit_start raises), the asset
    execution MUST continue normally -- dbt still runs, result still
    returned/raised.
    """

    @pytest.mark.requirement(AC_11)
    def test_dbt_runs_when_emit_start_raises(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test dbt.run_models is called even when emit_start raises.

        Lineage emission failure must not prevent the core dbt execution.
        This test verifies both that emit_start WAS attempted (so the
        failure path is exercised) AND that dbt still ran.
        """
        mock_lineage_resource.emit_start.side_effect = RuntimeError("lineage backend down")

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        # Verify emit_start was attempted (not skipped)
        mock_lineage_resource.emit_start.assert_called_once()
        # Verify dbt still ran despite lineage failure
        mock_dbt_resource.run_models.assert_called_once()

    @pytest.mark.requirement(AC_11)
    def test_dbt_result_still_returned_when_emit_start_raises(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test asset completes normally when emit_start fails.

        The asset function should NOT propagate the lineage exception.
        It should complete as if lineage was not configured. Verifies
        emit_start was attempted so this isn't vacuously passing.
        """
        mock_lineage_resource.emit_start.side_effect = RuntimeError("lineage backend down")

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            # Should not raise — lineage failure is swallowed
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        # Verify emit_start was actually attempted (not just skipped)
        mock_lineage_resource.emit_start.assert_called_once()

    @pytest.mark.requirement(AC_11)
    def test_dbt_failure_still_raises_when_emit_start_fails(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
        mock_dbt_result_failure: MagicMock,
    ) -> None:
        """Test dbt failure still raises RuntimeError even when lineage is broken.

        Both emit_start fails AND dbt fails. The dbt RuntimeError must still
        propagate, not be masked by lineage error handling. Verifies
        emit_start was attempted first.
        """
        mock_lineage_resource.emit_start.side_effect = RuntimeError("lineage backend down")
        mock_dbt_resource.run_models.return_value = mock_dbt_result_failure

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="failed"):
                _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        # Verify emit_start was actually attempted
        mock_lineage_resource.emit_start.assert_called_once()

    @pytest.mark.requirement(AC_11)
    def test_emit_complete_failure_does_not_crash_asset(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test asset completes normally when emit_complete raises.

        Verifies emit_complete was actually attempted (so the failure
        path is exercised), then swallowed.
        """
        mock_lineage_resource.emit_complete.side_effect = RuntimeError("emit_complete failed")

        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            # Should not raise — emit_complete failure is swallowed
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        # Verify emit_complete was actually attempted (not just skipped)
        mock_lineage_resource.emit_complete.assert_called_once()

    @pytest.mark.requirement(AC_11)
    def test_emit_event_failure_does_not_crash_asset(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
        sample_lineage_events: list[MagicMock],
    ) -> None:
        """Test asset completes normally when emit_event raises.

        Verifies emit_event was actually attempted with events, so
        this isn't vacuously passing because events were never emitted.
        """
        mock_lineage_resource.emit_event.side_effect = RuntimeError("emit_event failed")

        with (
            patch(_EXTRACT_FN, return_value=sample_lineage_events),
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            # Should not raise — emit_event failure is swallowed
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        # Verify emit_event was actually attempted (not just skipped)
        assert mock_lineage_resource.emit_event.call_count >= 1, (
            "emit_event must be attempted at least once to exercise the failure path"
        )

    @pytest.mark.requirement(AC_11)
    def test_extract_dbt_model_lineage_failure_does_not_crash_asset(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test asset completes normally when extract_dbt_model_lineage raises.

        Verifies the extraction was actually attempted (patched with side_effect)
        so this isn't vacuously passing because extraction was never called.
        """
        with (
            patch(_EXTRACT_FN, side_effect=RuntimeError("extraction failed")) as mock_extract,
            patch(f"{_TRACE_CORRELATION_BUILDER}.from_otel_context", return_value=None),
        ):
            # Should not raise — extraction failure is swallowed
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        # Verify extraction was actually attempted
        mock_extract.assert_called_once()

    @pytest.mark.requirement(AC_11)
    def test_trace_correlation_builder_failure_does_not_crash_asset(
        self,
        dagster_plugin: Any,
        sample_transform: TransformConfig,
        mock_context: MagicMock,
        mock_dbt_resource: MagicMock,
        mock_lineage_resource: MagicMock,
    ) -> None:
        """Test asset completes when TraceCorrelationFacetBuilder.from_otel_context raises.

        Verifies from_otel_context was actually called (so the failure path
        is exercised) AND that dbt still ran AND that emit_start was still
        attempted (possibly without the facet).
        """
        with (
            patch(_EXTRACT_FN, return_value=[]),
            patch(
                f"{_TRACE_CORRELATION_BUILDER}.from_otel_context",
                side_effect=RuntimeError("otel broken"),
            ) as mock_otel,
        ):
            # Should not raise — OTel failure is swallowed
            _invoke_asset_fn(dagster_plugin, sample_transform, mock_context, mock_dbt_resource)

        # Verify from_otel_context was actually attempted
        mock_otel.assert_called_once()
        # dbt should still have been called
        mock_dbt_resource.run_models.assert_called_once()
        # emit_start should still have been attempted (possibly without facet)
        mock_lineage_resource.emit_start.assert_called_once()

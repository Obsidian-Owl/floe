"""Unit tests for OpenLineage emission wiring into compile_pipeline().

Tests for AC-17.3 (OpenLineage events emitted after compile_pipeline runs)
and AC-17.5 (run facets include trace_id for trace-lineage correlation).

These tests verify that compile_pipeline():
- Emits START and COMPLETE events for the pipeline-level job
- Emits FAIL events when compilation raises an exception
- Emits per-model START/COMPLETE events during the COMPILE stage
- Includes trace correlation facets in run_facets
- Is a no-op when MARQUEZ_URL is not set
- Calls emitter.close() at the end of the pipeline
- Uses correct job naming conventions
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# --- Constants for repeated strings (ruff: no duplicate literals) ---
LOADER_MODULE = "floe_core.compilation.loader"
RESOLVER_MODULE = "floe_core.compilation.resolver"
BUILDER_MODULE = "floe_core.compilation.builder"
DBT_PROFILES_MODULE = "floe_core.compilation.dbt_profiles"
AUDIT_MODULE = "floe_core.telemetry.audit"
EMITTER_MODULE = "floe_core.lineage.emitter"
FACETS_MODULE = "floe_core.lineage.facets"
STAGES_MODULE = "floe_core.compilation.stages"
MARQUEZ_URL_ENV_KEY = "MARQUEZ_URL"
MARQUEZ_URL_VALUE = "http://localhost:5000/api/v1/lineage"
PIPELINE_JOB_SUBSTRING = "pipeline"


def _make_mock_spec() -> MagicMock:
    """Create a mock FloeSpec with realistic attributes."""
    spec = MagicMock()
    spec.metadata.name = "customer-360"
    spec.destinations = None
    spec.governance = None
    return spec


def _make_mock_manifest() -> MagicMock:
    """Create a mock PlatformManifest with realistic attributes."""
    manifest = MagicMock()
    manifest.plugins.quality = None
    manifest.approved_sinks = None
    manifest.governance = None
    return manifest


def _make_mock_plugins() -> MagicMock:
    """Create a mock ResolvedPlugins."""
    plugins = MagicMock()
    plugins.compute.type = "duckdb"
    plugins.orchestrator.type = "dagster"
    return plugins


def _make_mock_transforms() -> MagicMock:
    """Create a mock ResolvedTransforms with model names."""
    transforms = MagicMock()
    model_a = MagicMock()
    model_a.name = "stg_customers"
    model_b = MagicMock()
    model_b.name = "fct_orders"
    model_c = MagicMock()
    model_c.name = "dim_products"
    transforms.models = [model_a, model_b, model_c]
    return transforms


def _make_mock_artifacts() -> MagicMock:
    """Create a mock CompiledArtifacts."""
    artifacts = MagicMock()
    artifacts.version = "0.3.0"
    return artifacts


def _base_patches() -> dict[str, MagicMock]:
    """Build patch targets for compile_pipeline internal imports.

    These target the source modules where the functions are defined,
    since compile_pipeline uses local imports from those modules.
    """
    return {
        f"{LOADER_MODULE}.load_floe_spec": MagicMock(
            return_value=_make_mock_spec(),
        ),
        f"{LOADER_MODULE}.load_manifest": MagicMock(
            return_value=_make_mock_manifest(),
        ),
        f"{RESOLVER_MODULE}.resolve_manifest_inheritance": MagicMock(
            return_value=_make_mock_manifest(),
        ),
        f"{RESOLVER_MODULE}.resolve_plugins": MagicMock(
            return_value=_make_mock_plugins(),
        ),
        f"{RESOLVER_MODULE}.resolve_transform_compute": MagicMock(
            return_value=_make_mock_transforms(),
        ),
        f"{DBT_PROFILES_MODULE}.generate_dbt_profiles": MagicMock(
            return_value={"customer-360": {"target": "dev"}},
        ),
        f"{BUILDER_MODULE}.build_artifacts": MagicMock(
            return_value=_make_mock_artifacts(),
        ),
        f"{AUDIT_MODULE}.verify_plugin_instrumentation": MagicMock(
            return_value=[],
        ),
        f"{STAGES_MODULE}._discover_plugins_for_audit": MagicMock(
            return_value=[],
        ),
    }


@pytest.fixture
def mock_emitter() -> MagicMock:
    """Create a mock LineageEmitter with async methods.

    The mock has emit_start, emit_complete, emit_fail as AsyncMocks,
    and close as a regular MagicMock. emit_start returns a UUID.

    Returns:
        Mock LineageEmitter instance.
    """
    emitter = MagicMock()
    run_id = uuid4()
    emitter.emit_start = AsyncMock(return_value=run_id)
    emitter.emit_complete = AsyncMock(return_value=None)
    emitter.emit_fail = AsyncMock(return_value=None)
    emitter.close = MagicMock()
    emitter.default_namespace = "default"
    return emitter


@pytest.fixture
def compilation_patches() -> dict[str, MagicMock]:
    """Provide patch targets for compile_pipeline internal dependencies.

    Returns:
        Dictionary mapping patch target strings to MagicMock objects.
    """
    return _base_patches()


def _run_pipeline_with_patches(
    patches: dict[str, MagicMock],
    extra_patches: dict[str, Any] | None = None,
) -> Any:
    """Run compile_pipeline with all internal dependencies mocked.

    Args:
        patches: Base compilation patches from _base_patches.
        extra_patches: Additional patches to apply (e.g., emitter factory).

    Returns:
        The result of compile_pipeline.
    """
    from floe_core.compilation.stages import compile_pipeline

    all_patches = {**patches}
    if extra_patches:
        all_patches.update(extra_patches)

    with contextlib.ExitStack() as stack:
        for target, mock_obj in all_patches.items():
            stack.enter_context(patch(target, mock_obj))
        return compile_pipeline(
            Path("floe.yaml"),
            Path("manifest.yaml"),
        )


class TestPipelineLevelEmission:
    """Tests verifying pipeline-level OpenLineage START/COMPLETE emission."""

    @pytest.mark.requirement("AC-17.3")
    def test_emit_start_called_for_pipeline_job(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify emit_start() is called with a job_name containing 'pipeline'.

        When MARQUEZ_URL is set, compile_pipeline must emit a START event
        for the pipeline-level job before executing compilation stages.
        The job_name must contain 'pipeline' to be discoverable by Marquez
        queries in the E2E test.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": MagicMock(
                    return_value=mock_emitter,
                ),
            },
        )

        mock_emitter.emit_start.assert_called()
        start_calls = mock_emitter.emit_start.call_args_list
        pipeline_start_calls = [
            c for c in start_calls if c.args and PIPELINE_JOB_SUBSTRING in c.args[0]
        ]
        assert len(pipeline_start_calls) >= 1, (
            f"Expected at least one emit_start call with "
            f"'{PIPELINE_JOB_SUBSTRING}' in job_name. "
            f"Actual calls: {start_calls}"
        )

    @pytest.mark.requirement("AC-17.3")
    def test_emit_complete_called_for_pipeline_job(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify emit_complete() is called after successful compilation.

        After all 6 stages succeed, compile_pipeline must emit a COMPLETE
        event for the pipeline-level job with the same run_id from START.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)
        pipeline_run_id = uuid4()
        mock_emitter.emit_start = AsyncMock(
            return_value=pipeline_run_id,
        )

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": MagicMock(
                    return_value=mock_emitter,
                ),
            },
        )

        mock_emitter.emit_complete.assert_called()
        complete_calls = mock_emitter.emit_complete.call_args_list
        pipeline_complete_calls = [
            c for c in complete_calls if len(c.args) > 1 and PIPELINE_JOB_SUBSTRING in c.args[1]
        ]
        assert len(pipeline_complete_calls) >= 1, (
            f"Expected at least one emit_complete call with "
            f"'{PIPELINE_JOB_SUBSTRING}' in job_name. "
            f"Actual calls: {complete_calls}"
        )

    @pytest.mark.requirement("AC-17.3")
    def test_pipeline_start_and_complete_share_run_id(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify pipeline START and COMPLETE use the same run_id.

        The run_id returned by emit_start must be passed to emit_complete
        so that Marquez can correlate the lifecycle events.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)
        pipeline_run_id = uuid4()
        mock_emitter.emit_start = AsyncMock(
            return_value=pipeline_run_id,
        )

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": MagicMock(
                    return_value=mock_emitter,
                ),
            },
        )

        complete_calls = mock_emitter.emit_complete.call_args_list
        pipeline_complete_calls = [
            c for c in complete_calls if len(c.args) > 1 and PIPELINE_JOB_SUBSTRING in c.args[1]
        ]
        assert len(pipeline_complete_calls) >= 1
        complete_call = pipeline_complete_calls[0]
        assert complete_call.args[0] == pipeline_run_id, (
            f"Pipeline COMPLETE call must use run_id={pipeline_run_id} "
            f"from START. Actual run_id: {complete_call.args[0]}"
        )

    @pytest.mark.requirement("AC-17.3")
    def test_emit_start_called_before_emit_complete(
        self,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify emit_start is called before emit_complete.

        START must precede COMPLETE to ensure correct lifecycle ordering
        in Marquez. Verified by recording call order.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        call_order: list[str] = []
        emitter = MagicMock()
        pipeline_run_id = uuid4()

        async def mock_start(*args: Any, **kwargs: Any) -> UUID:
            call_order.append("start")
            return pipeline_run_id

        async def mock_complete(*args: Any, **kwargs: Any) -> None:
            call_order.append("complete")

        emitter.emit_start = AsyncMock(side_effect=mock_start)
        emitter.emit_complete = AsyncMock(side_effect=mock_complete)
        emitter.emit_fail = AsyncMock()
        emitter.close = MagicMock()
        emitter.default_namespace = "default"

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": MagicMock(
                    return_value=emitter,
                ),
            },
        )

        assert "start" in call_order, "emit_start was never called"
        assert "complete" in call_order, "emit_complete was never called"
        first_start = call_order.index("start")
        last_complete = len(call_order) - 1 - call_order[::-1].index("complete")
        assert first_start < last_complete, (
            f"emit_start (index {first_start}) must be called before "
            f"emit_complete (index {last_complete}). "
            f"Call order: {call_order}"
        )


class TestPipelineFailEmission:
    """Tests verifying FAIL event emission on compilation errors."""

    @pytest.mark.requirement("AC-17.3")
    def test_emit_fail_called_on_compilation_error(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify emit_fail() is called when compilation raises.

        If any compilation stage raises, compile_pipeline must emit a
        FAIL event with the pipeline run_id and error message before
        re-raising.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)
        pipeline_run_id = uuid4()
        mock_emitter.emit_start = AsyncMock(
            return_value=pipeline_run_id,
        )

        compilation_patches[f"{LOADER_MODULE}.load_floe_spec"] = MagicMock(
            side_effect=ValueError("YAML parse error: invalid syntax"),
        )

        with pytest.raises(ValueError, match="YAML parse error"):
            _run_pipeline_with_patches(
                compilation_patches,
                extra_patches={
                    f"{EMITTER_MODULE}.create_emitter": MagicMock(
                        return_value=mock_emitter,
                    ),
                },
            )

        mock_emitter.emit_fail.assert_called()
        fail_calls = mock_emitter.emit_fail.call_args_list
        assert len(fail_calls) >= 1, "emit_fail must be called at least once on error"

    @pytest.mark.requirement("AC-17.3")
    def test_emit_fail_includes_error_message(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify emit_fail includes the error message from the exception.

        The error_message parameter must contain information about what
        went wrong so it appears in Marquez ErrorMessageRunFacet.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)
        pipeline_run_id = uuid4()
        mock_emitter.emit_start = AsyncMock(
            return_value=pipeline_run_id,
        )

        error_text = "Validation failed: missing required field"
        compilation_patches[f"{LOADER_MODULE}.load_floe_spec"] = MagicMock(
            side_effect=ValueError(error_text),
        )

        with pytest.raises(ValueError):
            _run_pipeline_with_patches(
                compilation_patches,
                extra_patches={
                    f"{EMITTER_MODULE}.create_emitter": MagicMock(
                        return_value=mock_emitter,
                    ),
                },
            )

        fail_call = mock_emitter.emit_fail.call_args
        error_msg = fail_call.kwargs.get("error_message", "")
        assert "missing required" in error_msg, (
            f"emit_fail must include error message. Got error_message: {error_msg!r}"
        )

    @pytest.mark.requirement("AC-17.3")
    def test_emit_complete_not_called_on_error(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify emit_complete is NOT called when compilation fails.

        On error, only FAIL should be emitted for the pipeline job,
        never COMPLETE.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        compilation_patches[f"{LOADER_MODULE}.load_floe_spec"] = MagicMock(
            side_effect=RuntimeError("stage failure"),
        )

        with pytest.raises(RuntimeError):
            _run_pipeline_with_patches(
                compilation_patches,
                extra_patches={
                    f"{EMITTER_MODULE}.create_emitter": MagicMock(
                        return_value=mock_emitter,
                    ),
                },
            )

        # Precondition: emit_start WAS called (emitter is wired in)
        mock_emitter.emit_start.assert_called()

        complete_calls = mock_emitter.emit_complete.call_args_list
        pipeline_complete_calls = [
            c for c in complete_calls if len(c.args) > 1 and PIPELINE_JOB_SUBSTRING in c.args[1]
        ]
        assert len(pipeline_complete_calls) == 0, (
            "emit_complete must NOT be called for pipeline job on "
            f"error. Found: {pipeline_complete_calls}"
        )

    @pytest.mark.requirement("AC-17.3")
    def test_original_exception_propagates_on_fail(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify the original exception is re-raised after emit_fail.

        Lineage emission must not swallow compilation errors.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        compilation_patches[f"{LOADER_MODULE}.load_floe_spec"] = MagicMock(
            side_effect=RuntimeError("original error"),
        )

        with pytest.raises(RuntimeError, match="original error"):
            _run_pipeline_with_patches(
                compilation_patches,
                extra_patches={
                    f"{EMITTER_MODULE}.create_emitter": MagicMock(
                        return_value=mock_emitter,
                    ),
                },
            )


class TestPerModelEmission:
    """Tests verifying per-model (dbt) OpenLineage emission."""

    @pytest.mark.requirement("AC-17.3")
    def test_emit_start_called_for_each_model(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify emit_start is called for each dbt model in transforms.

        During the COMPILE stage, per-model START events must be emitted
        so Marquez sees jobs with 'dbt' or 'model' in the name.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": MagicMock(
                    return_value=mock_emitter,
                ),
            },
        )

        start_calls = mock_emitter.emit_start.call_args_list
        # At least 4 start calls:
        # 1 pipeline-level + 3 per-model
        assert len(start_calls) >= 4, (
            f"Expected >= 4 emit_start calls "
            f"(1 pipeline + 3 models). "
            f"Got {len(start_calls)}: {start_calls}"
        )

    @pytest.mark.requirement("AC-17.3")
    def test_model_job_names_contain_model_identifiers(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify per-model job names include the dbt model name.

        Job names for model-level emissions must contain the model name
        (e.g., 'stg_customers') so the E2E test can find them by
        searching for 'dbt' or 'model' in job names.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": MagicMock(
                    return_value=mock_emitter,
                ),
            },
        )

        start_calls = mock_emitter.emit_start.call_args_list
        job_names = [c.args[0] for c in start_calls if c.args]

        expected_models = [
            "stg_customers",
            "fct_orders",
            "dim_products",
        ]
        for model_name in expected_models:
            assert any(model_name in jn for jn in job_names), (
                f"Expected model name '{model_name}' in emit_start "
                f"job_names. Actual job_names: {job_names}"
            )

    @pytest.mark.requirement("AC-17.3")
    def test_emit_complete_called_for_each_model(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify emit_complete is called for each dbt model.

        Each model must have both START and COMPLETE events for the E2E
        test to find both lifecycle states in Marquez.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": MagicMock(
                    return_value=mock_emitter,
                ),
            },
        )

        complete_calls = mock_emitter.emit_complete.call_args_list
        # At least 4 complete calls:
        # 1 pipeline-level + 3 per-model
        assert len(complete_calls) >= 4, (
            f"Expected >= 4 emit_complete calls "
            f"(1 pipeline + 3 models). "
            f"Got {len(complete_calls)}: {complete_calls}"
        )

    @pytest.mark.requirement("AC-17.3")
    def test_per_model_start_complete_share_run_ids(
        self,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify each model START run_id matches its COMPLETE run_id.

        Each per-model run_id returned by emit_start must be passed to
        the corresponding emit_complete call.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        emitter = MagicMock()
        model_run_ids: dict[str, UUID] = {}

        async def track_start(job_name: str, *args: Any, **kwargs: Any) -> UUID:
            rid = uuid4()
            model_run_ids[job_name] = rid
            return rid

        emitter.emit_start = AsyncMock(side_effect=track_start)
        emitter.emit_complete = AsyncMock(return_value=None)
        emitter.emit_fail = AsyncMock(return_value=None)
        emitter.close = MagicMock()
        emitter.default_namespace = "default"

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": MagicMock(
                    return_value=emitter,
                ),
            },
        )

        complete_calls = emitter.emit_complete.call_args_list
        # Precondition: there must be complete calls to verify
        assert len(complete_calls) >= 4, (
            f"Expected >= 4 emit_complete calls to verify run_id "
            f"matching. Got {len(complete_calls)}"
        )
        for c in complete_calls:
            run_id_in_call = c.args[0] if c.args else c.kwargs.get("run_id")
            job_name_in_call = c.args[1] if len(c.args) > 1 else c.kwargs.get("job_name")
            if run_id_in_call is not None and job_name_in_call is not None:
                expected_id = model_run_ids.get(job_name_in_call)
                if expected_id is not None:
                    assert run_id_in_call == expected_id, (
                        f"Mismatched run_id for job "
                        f"'{job_name_in_call}': "
                        f"START returned {expected_id}, "
                        f"COMPLETE got {run_id_in_call}"
                    )


class TestTraceCorrelation:
    """Tests verifying trace-lineage correlation (AC-17.5)."""

    @pytest.mark.requirement("AC-17.5")
    def test_run_facets_include_trace_correlation(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify run_facets include trace correlation facet.

        When OTel context is active, from_otel_context() should be
        called and its result included in run_facets of emitted events,
        enabling trace-to-lineage correlation per AC-17.5.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        fake_trace_facet = {
            "_producer": "floe",
            "_schemaURL": ("https://floe.dev/lineage/facets/v1/TraceCorrelationFacet.json"),
            "trace_id": "0" * 32,
            "span_id": "0" * 16,
        }

        with patch(
            f"{FACETS_MODULE}.TraceCorrelationFacetBuilder.from_otel_context",
            return_value=fake_trace_facet,
        ):
            _run_pipeline_with_patches(
                compilation_patches,
                extra_patches={
                    f"{EMITTER_MODULE}.create_emitter": MagicMock(
                        return_value=mock_emitter,
                    ),
                },
            )

        start_calls = mock_emitter.emit_start.call_args_list
        found_trace_facet = False
        for c in start_calls:
            run_facets = c.kwargs.get("run_facets")
            if not run_facets and len(c.args) > 4:
                run_facets = c.args[4]
            if run_facets and "trace_id" in str(run_facets):
                found_trace_facet = True
                break

        assert found_trace_facet, (
            "No emit_start call included trace correlation facet "
            f"in run_facets. Calls: {start_calls}"
        )

    @pytest.mark.requirement("AC-17.5")
    def test_trace_facet_contains_specific_trace_id(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify trace correlation facet has real trace_id and span_id.

        The facet must have non-empty trace_id and span_id fields so
        that given a trace_id from Jaeger, the corresponding OpenLineage
        run can be found.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        specific_trace_id = "a1b2c3d4e5f60718a1b2c3d4e5f60718"
        specific_span_id = "1234567890abcdef"
        fake_trace_facet = {
            "_producer": "floe",
            "_schemaURL": ("https://floe.dev/lineage/facets/v1/TraceCorrelationFacet.json"),
            "trace_id": specific_trace_id,
            "span_id": specific_span_id,
        }

        with patch(
            f"{FACETS_MODULE}.TraceCorrelationFacetBuilder.from_otel_context",
            return_value=fake_trace_facet,
        ):
            _run_pipeline_with_patches(
                compilation_patches,
                extra_patches={
                    f"{EMITTER_MODULE}.create_emitter": MagicMock(
                        return_value=mock_emitter,
                    ),
                },
            )

        all_calls = (
            mock_emitter.emit_start.call_args_list + mock_emitter.emit_complete.call_args_list
        )
        found_trace_id = False
        for c in all_calls:
            run_facets = c.kwargs.get("run_facets")
            if isinstance(run_facets, dict):
                facet = run_facets.get("traceCorrelation")
                if isinstance(facet, dict) and facet.get("trace_id") == specific_trace_id:
                    found_trace_id = True
                    break
        assert found_trace_id, (
            f"trace_id '{specific_trace_id}' not found in any emit call run_facets."
        )

    @pytest.mark.requirement("AC-17.5")
    def test_no_trace_facet_when_otel_context_absent(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify no crash when OTel context is absent (returns None).

        When from_otel_context() returns None, compile_pipeline must
        still succeed and emit events without trace correlation facets.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        with patch(
            f"{FACETS_MODULE}.TraceCorrelationFacetBuilder.from_otel_context",
            return_value=None,
        ):
            result = _run_pipeline_with_patches(
                compilation_patches,
                extra_patches={
                    f"{EMITTER_MODULE}.create_emitter": MagicMock(
                        return_value=mock_emitter,
                    ),
                },
            )

        assert result.version == "0.3.0"
        mock_emitter.emit_start.assert_called()
        mock_emitter.emit_complete.assert_called()


class TestNoOpWhenMarquezAbsent:
    """Tests verifying no-op behavior when MARQUEZ_URL is not set."""

    @pytest.mark.requirement("AC-17.3")
    def test_no_http_emitter_without_marquez_url(
        self,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify no HTTP transport emitter when MARQUEZ_URL unset.

        When the MARQUEZ_URL environment variable is absent,
        compile_pipeline must not create an HTTP emitter or make any
        HTTP calls.
        """
        monkeypatch.delenv(MARQUEZ_URL_ENV_KEY, raising=False)

        mock_create = MagicMock()
        mock_create.return_value = MagicMock(
            emit_start=AsyncMock(return_value=uuid4()),
            emit_complete=AsyncMock(),
            emit_fail=AsyncMock(),
            close=MagicMock(),
            default_namespace="default",
        )

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": mock_create,
            },
        )

        mock_create.assert_not_called()

    @pytest.mark.requirement("AC-17.3")
    def test_compilation_succeeds_without_marquez_url(
        self,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify compile_pipeline completes without MARQUEZ_URL.

        The absence of MARQUEZ_URL must not cause any errors or change
        the compilation result.
        """
        monkeypatch.delenv(MARQUEZ_URL_ENV_KEY, raising=False)

        result = _run_pipeline_with_patches(compilation_patches)

        assert result is not None
        assert result.version == "0.3.0"


class TestEmitterLifecycle:
    """Tests verifying emitter resource management."""

    @pytest.mark.requirement("AC-17.3")
    def test_emitter_close_called_on_success(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify emitter.close() is called after successful compilation.

        The emitter must be properly closed to flush any pending events
        and release transport resources.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": MagicMock(
                    return_value=mock_emitter,
                ),
            },
        )

        mock_emitter.close.assert_called_once()

    @pytest.mark.requirement("AC-17.3")
    def test_emitter_close_called_on_failure(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify emitter.close() called even when compilation fails.

        close() must be in a finally block to ensure cleanup regardless
        of compilation outcome.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        compilation_patches[f"{LOADER_MODULE}.load_floe_spec"] = MagicMock(
            side_effect=RuntimeError("boom"),
        )

        with pytest.raises(RuntimeError, match="boom"):
            _run_pipeline_with_patches(
                compilation_patches,
                extra_patches={
                    f"{EMITTER_MODULE}.create_emitter": MagicMock(
                        return_value=mock_emitter,
                    ),
                },
            )

        mock_emitter.close.assert_called_once()

    @pytest.mark.requirement("AC-17.3")
    def test_emitter_error_does_not_crash_pipeline(
        self,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify emitter errors do not crash the pipeline.

        If emit_start or emit_complete raises, the pipeline must still
        complete successfully. Lineage is best-effort.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        broken_emitter = MagicMock()
        broken_emitter.emit_start = AsyncMock(
            side_effect=ConnectionError("Marquez unreachable"),
        )
        broken_emitter.emit_complete = AsyncMock(
            side_effect=ConnectionError("Marquez unreachable"),
        )
        broken_emitter.emit_fail = AsyncMock()
        broken_emitter.close = MagicMock()
        broken_emitter.default_namespace = "default"

        mock_create = MagicMock(return_value=broken_emitter)

        result = _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": mock_create,
            },
        )

        # Precondition: emitter factory was called (wiring exists)
        mock_create.assert_called_once()
        # Pipeline must still succeed despite emitter errors
        assert result is not None
        assert result.version == "0.3.0"


class TestJobNaming:
    """Tests verifying OpenLineage job naming conventions."""

    @pytest.mark.requirement("AC-17.3")
    def test_pipeline_job_name_contains_pipeline(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify the pipeline-level job name contains 'pipeline'.

        The E2E test searches for jobs with 'pipeline' in the name.
        The job_name argument to emit_start must include this.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": MagicMock(
                    return_value=mock_emitter,
                ),
            },
        )

        start_calls = mock_emitter.emit_start.call_args_list
        job_names: list[str] = []
        for c in start_calls:
            jn = c.args[0] if c.args else c.kwargs.get("job_name", "")
            job_names.append(str(jn))

        pipeline_jobs = [jn for jn in job_names if PIPELINE_JOB_SUBSTRING in jn.lower()]
        assert len(pipeline_jobs) >= 1, (
            f"No job_name containing '{PIPELINE_JOB_SUBSTRING}' "
            f"found in emit_start calls. Job names: {job_names}"
        )

    @pytest.mark.requirement("AC-17.3")
    def test_model_job_names_discoverable_by_e2e(
        self,
        mock_emitter: MagicMock,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify model job names findable by 'dbt' or 'model' search.

        The E2E test checks for jobs where 'dbt' or 'model' appears in
        the name. Per-model job names must satisfy this condition.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": MagicMock(
                    return_value=mock_emitter,
                ),
            },
        )

        start_calls = mock_emitter.emit_start.call_args_list
        job_names: list[str] = []
        for c in start_calls:
            jn = c.args[0] if c.args else c.kwargs.get("job_name", "")
            job_names.append(str(jn))

        non_pipeline_jobs = [jn for jn in job_names if PIPELINE_JOB_SUBSTRING not in jn.lower()]

        # Precondition: there must be per-model jobs to check
        assert len(non_pipeline_jobs) >= 3, (
            f"Expected >= 3 non-pipeline job names. "
            f"Got {len(non_pipeline_jobs)}: {non_pipeline_jobs}"
        )

        expected_model_names = [
            "stg_customers",
            "fct_orders",
            "dim_products",
        ]
        for jn in non_pipeline_jobs:
            has_dbt = "dbt" in jn.lower()
            has_model = "model" in jn.lower()
            has_name = any(m in jn for m in expected_model_names)
            assert has_dbt or has_model or has_name, (
                f"Model job name '{jn}' not discoverable by E2E. "
                f"Must contain 'dbt', 'model', or model name."
            )


class TestEmitterCreation:
    """Tests verifying emitter factory called with correct config."""

    @pytest.mark.requirement("AC-17.3")
    def test_create_emitter_with_http_config_when_url_set(
        self,
        compilation_patches: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify create_emitter receives HTTP config from env var.

        When MARQUEZ_URL is set, create_emitter must be called with
        a transport_config that includes the URL for HTTP transport.
        """
        monkeypatch.setenv(MARQUEZ_URL_ENV_KEY, MARQUEZ_URL_VALUE)

        mock_create = MagicMock()
        dummy_emitter = MagicMock()
        dummy_emitter.emit_start = AsyncMock(return_value=uuid4())
        dummy_emitter.emit_complete = AsyncMock()
        dummy_emitter.emit_fail = AsyncMock()
        dummy_emitter.close = MagicMock()
        dummy_emitter.default_namespace = "default"
        mock_create.return_value = dummy_emitter

        _run_pipeline_with_patches(
            compilation_patches,
            extra_patches={
                f"{EMITTER_MODULE}.create_emitter": mock_create,
            },
        )

        mock_create.assert_called_once()
        create_call = mock_create.call_args
        transport_config = (
            create_call.args[0] if create_call.args else create_call.kwargs.get("transport_config")
        )
        assert isinstance(transport_config, dict), (
            f"create_emitter first arg must be a dict. Got: {type(transport_config)}"
        )
        assert transport_config.get("url") == MARQUEZ_URL_VALUE, (
            f"create_emitter transport_config must contain MARQUEZ_URL. Got: {transport_config}"
        )

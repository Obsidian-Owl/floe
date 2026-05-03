"""Tests for compile_pipeline() OpenLineage integration (AC-5, AC-6, AC-7).

Verifies that compile_pipeline() correctly creates a sync lineage emitter
from manifest config and emits START/COMPLETE/FAIL events at the right
lifecycle points.

Requirements:
    - AC-OLC-5: emit_start() called after LOAD with correct job_name and run_facets
    - AC-OLC-6: emit_complete() called before return with run_id from emit_start()
    - AC-OLC-7: emit_fail() called on exception with type(exc).__name__
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Constants (deduplicate string literals per code-quality rules)
# ---------------------------------------------------------------------------
# Patch at the source module -- compile_pipeline() will add a local import
# from floe_core.lineage.emitter. Patching the source ensures interception
# regardless of how the local import is structured.
EMITTER_MODULE = "floe_core.lineage.emitter"
CREATE_SYNC_EMITTER_PATH = f"{EMITTER_MODULE}.create_sync_emitter"
FACETS_MODULE = "floe_core.lineage.facets"
TRACE_FACET_PATH = f"{FACETS_MODULE}.TraceCorrelationFacetBuilder"
# compile_pipeline() uses local imports from these resolver functions
RESOLVER_MODULE = "floe_core.compilation.resolver"
RESOLVE_PLUGINS_PATH = f"{RESOLVER_MODULE}.resolve_plugins"
PRODUCT_NAME = "test-product"

# ---------------------------------------------------------------------------
# Manifest YAML variants
# ---------------------------------------------------------------------------
MANIFEST_WITH_LINEAGE_YAML = """\
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
observability:
  lineage:
    enabled: true
    transport: http
    endpoint: http://marquez:5000/api/v1/lineage
"""

MANIFEST_LINEAGE_DISABLED_YAML = """\
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
observability:
  lineage:
    enabled: false
    transport: http
    endpoint: http://marquez:5000/api/v1/lineage
"""

MANIFEST_NO_OBSERVABILITY_YAML = """\
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
"""

MANIFEST_LINEAGE_CONSOLE_YAML = """\
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
observability:
  lineage:
    enabled: true
    transport: console
"""

MINIMAL_SPEC_YAML = """\
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
    tags: []
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def spec_path(tmp_path: Path) -> Path:
    """Write minimal spec YAML and return its path."""
    path = tmp_path / "floe.yaml"
    path.write_text(MINIMAL_SPEC_YAML)
    return path


@pytest.fixture
def lineage_manifest_path(tmp_path: Path) -> Path:
    """Write manifest with lineage enabled and return its path."""
    path = tmp_path / "manifest.yaml"
    path.write_text(MANIFEST_WITH_LINEAGE_YAML)
    return path


@pytest.fixture
def lineage_disabled_manifest_path(tmp_path: Path) -> Path:
    """Write manifest with lineage disabled and return its path."""
    path = tmp_path / "manifest.yaml"
    path.write_text(MANIFEST_LINEAGE_DISABLED_YAML)
    return path


@pytest.fixture
def no_observability_manifest_path(tmp_path: Path) -> Path:
    """Write manifest without observability and return its path."""
    path = tmp_path / "manifest.yaml"
    path.write_text(MANIFEST_NO_OBSERVABILITY_YAML)
    return path


@pytest.fixture
def console_lineage_manifest_path(tmp_path: Path) -> Path:
    """Write manifest with console lineage transport and return its path."""
    path = tmp_path / "manifest.yaml"
    path.write_text(MANIFEST_LINEAGE_CONSOLE_YAML)
    return path


@pytest.fixture
def mock_emitter() -> MagicMock:
    """Create a mock SyncLineageEmitter with realistic return values."""
    emitter = MagicMock()
    emitter.emit_start.return_value = uuid4()
    emitter.emit_complete.return_value = None
    emitter.emit_fail.return_value = None
    emitter.close.return_value = None
    return emitter


@pytest.fixture
def mock_trace_facet() -> dict[str, Any]:
    """Known trace correlation facet for test verification."""
    return {
        "_producer": "floe",
        "_schemaURL": "https://floe.dev/lineage/facets/v1/TraceCorrelationFacet.json",
        "trace_id": "0" * 32,
        "span_id": "0" * 16,
    }


def _get_arg(call_args: Any, positional_index: int, keyword_name: str) -> Any:
    """Extract an argument from mock call_args by position or keyword.

    Args:
        call_args: The call_args from a mock invocation.
        positional_index: Index for positional args.
        keyword_name: Keyword name fallback.

    Returns:
        The argument value.
    """
    if call_args[0] and len(call_args[0]) > positional_index:
        return call_args[0][positional_index]
    return call_args[1].get(keyword_name)


class TestCompilePipelineLineageStart:
    """AC-OLC-5: compile_pipeline() emits START event at pipeline open."""

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("AC-OLC-5")
    def test_create_sync_emitter_called_with_http_config(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """create_sync_emitter() receives transport config derived from manifest lineage.

        The manifest lineage config has transport=http and endpoint=<url>.
        The factory must be called with a dict containing type=http and
        url=<endpoint> (note: 'endpoint' is mapped to 'url' key).
        """
        from floe_core.compilation.stages import compile_pipeline

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter) as mock_factory:
            compile_pipeline(spec_path, lineage_manifest_path)

        mock_factory.assert_called_once()
        config_arg = _get_arg(mock_factory.call_args, 0, "transport_config")
        assert config_arg is not None, "transport_config must not be None for enabled lineage"
        assert config_arg["type"] == "http"
        assert config_arg["url"] == "http://marquez:5000/api/v1/lineage"

    @pytest.mark.requirement("AC-OLC-5")
    def test_create_sync_emitter_called_with_console_config(
        self,
        spec_path: Path,
        console_lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """create_sync_emitter() receives console transport config when transport=console."""
        from floe_core.compilation.stages import compile_pipeline

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter) as mock_factory:
            compile_pipeline(spec_path, console_lineage_manifest_path)

        mock_factory.assert_called_once()
        config_arg = _get_arg(mock_factory.call_args, 0, "transport_config")
        assert config_arg is not None
        assert config_arg["type"] == "console"

    @pytest.mark.requirement("AC-OLC-5")
    def test_noop_emitter_when_observability_none(
        self,
        spec_path: Path,
        no_observability_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """NoOp emitter used when manifest.observability is None.

        When observability config is absent, create_sync_emitter must be called
        with None transport_config (producing a NoOp emitter).
        """
        from floe_core.compilation.stages import compile_pipeline

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter) as mock_factory:
            compile_pipeline(spec_path, no_observability_manifest_path)

        mock_factory.assert_called_once()
        config_arg = _get_arg(mock_factory.call_args, 0, "transport_config")
        assert config_arg is None, "transport_config must be None when observability is absent"

    @pytest.mark.requirement("AC-OLC-5")
    def test_noop_emitter_when_lineage_disabled(
        self,
        spec_path: Path,
        lineage_disabled_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """NoOp emitter used when lineage.enabled is False.

        Even if observability config exists with a valid endpoint,
        create_sync_emitter must receive None config when enabled=False.
        """
        from floe_core.compilation.stages import compile_pipeline

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter) as mock_factory:
            compile_pipeline(spec_path, lineage_disabled_manifest_path)

        mock_factory.assert_called_once()
        config_arg = _get_arg(mock_factory.call_args, 0, "transport_config")
        assert config_arg is None, "transport_config must be None when lineage.enabled is False"

    @pytest.mark.requirement("AC-OLC-5")
    def test_emit_start_called_with_job_name(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """emit_start() is called with job_name matching spec.metadata.name.

        The job_name must be the product name from the spec, not a hardcoded
        value or some other identifier.
        """
        from floe_core.compilation.stages import compile_pipeline

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter):
            compile_pipeline(spec_path, lineage_manifest_path)

        # Pipeline-level emit_start must be called (per-model calls also present)
        pipeline_start_calls = [
            c
            for c in mock_emitter.emit_start.call_args_list
            if _get_arg(c, 0, "job_name") == PRODUCT_NAME
        ]
        assert len(pipeline_start_calls) == 1, (
            f"emit_start must be called once with job_name='{PRODUCT_NAME}', "
            f"found {len(pipeline_start_calls)} pipeline-level calls"
        )

    @pytest.mark.requirement("AC-OLC-5")
    def test_emit_start_includes_trace_correlation_facet(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
        mock_trace_facet: dict[str, Any],
    ) -> None:
        """emit_start() includes TraceCorrelationFacetBuilder.from_otel_context() in run_facets.

        The run_facets dict passed to emit_start must contain the trace
        correlation facet from the current OTel context.
        """
        from floe_core.compilation.stages import compile_pipeline

        with (
            patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter),
            patch(TRACE_FACET_PATH) as mock_builder_cls,
        ):
            mock_builder_cls.from_otel_context.return_value = mock_trace_facet
            compile_pipeline(spec_path, lineage_manifest_path)

        mock_builder_cls.from_otel_context.assert_called_once()
        # Pipeline-level emit_start carries the trace facet
        pipeline_start_calls = [
            c
            for c in mock_emitter.emit_start.call_args_list
            if _get_arg(c, 0, "job_name") == PRODUCT_NAME
        ]
        assert len(pipeline_start_calls) == 1
        run_facets = _get_arg(pipeline_start_calls[0], 4, "run_facets")
        assert run_facets is not None, "emit_start must be called with run_facets"
        # The trace facet must be present in the run_facets dict under some key
        assert isinstance(run_facets, dict), f"run_facets must be a dict, got {type(run_facets)}"
        # Check the facet content is present (either as a nested value or the dict itself)
        facet_values = list(run_facets.values()) if isinstance(run_facets, dict) else []
        assert mock_trace_facet in facet_values or run_facets == mock_trace_facet, (
            f"run_facets must contain the trace correlation facet, got: {run_facets}"
        )

    @pytest.mark.requirement("AC-OLC-5")
    def test_emit_start_failure_does_not_block_compilation(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """If emit_start() raises, compilation still succeeds.

        The emit call is wrapped in try/except -- failure logs a warning
        but does not propagate to the caller.
        """
        from floe_core.compilation.stages import compile_pipeline
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        mock_emitter.emit_start.side_effect = RuntimeError("Marquez unreachable")

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter):
            result = compile_pipeline(spec_path, lineage_manifest_path)

        # Verify pipeline-level emit_start was attempted (side_effect fired)
        pipeline_start_calls = [
            c
            for c in mock_emitter.emit_start.call_args_list
            if _get_arg(c, 0, "job_name") == PRODUCT_NAME
        ]
        assert len(pipeline_start_calls) == 1
        assert isinstance(result, CompiledArtifacts)
        assert result.metadata.product_name == PRODUCT_NAME

    @pytest.mark.requirement("AC-OLC-5")
    def test_emit_start_failure_skips_per_model_lineage_noise(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """A failed pipeline START marks compile-time lineage unavailable.

        If the backend is not reachable before deployment, every per-model
        event would fail for the same reason. Compilation should emit one
        pipeline-level warning and skip per-model lineage instead of producing
        repeated model warnings.
        """
        from floe_core.compilation.stages import compile_pipeline

        mock_emitter.emit_start.side_effect = ConnectionError("Marquez unavailable")

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter):
            compile_pipeline(spec_path, lineage_manifest_path)

        model_start_calls = [
            c
            for c in mock_emitter.emit_start.call_args_list
            if str(_get_arg(c, 0, "job_name")).startswith("model.")
        ]
        assert model_start_calls == []

    @pytest.mark.requirement("AC-OLC-5")
    def test_emit_lineage_false_uses_noop_transport_config(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """Offline compilation can preserve manifest lineage without HTTP emission.

        Pre-deploy packaging generates artifacts before Marquez exists. It must
        not attempt the manifest HTTP endpoint, but artifacts still need lineage
        enabled so runtime Dagster/OpenLineage behavior remains configured.
        """
        from floe_core.compilation.stages import compile_pipeline

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter) as mock_factory:
            artifacts = compile_pipeline(
                spec_path,
                lineage_manifest_path,
                emit_lineage=False,
            )

        mock_factory.assert_called_once()
        config_arg = _get_arg(mock_factory.call_args, 0, "transport_config")
        assert config_arg is None
        assert artifacts.observability.lineage is True


class TestCompilePipelineLineageComplete:
    """AC-OLC-6: compile_pipeline() emits COMPLETE event at pipeline close."""

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("AC-OLC-6")
    def test_emit_complete_called_with_run_id_from_start(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """emit_complete() receives the exact run_id returned by emit_start().

        This ensures the START and COMPLETE events are correlated by the
        same run_id, not independent UUIDs.
        """
        from floe_core.compilation.stages import compile_pipeline

        known_run_id = uuid4()
        mock_emitter.emit_start.return_value = known_run_id

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter):
            compile_pipeline(spec_path, lineage_manifest_path)

        # Pipeline-level emit_complete must use the run_id from pipeline emit_start
        pipeline_complete_calls = [
            c
            for c in mock_emitter.emit_complete.call_args_list
            if _get_arg(c, 1, "job_name") == PRODUCT_NAME
        ]
        assert len(pipeline_complete_calls) == 1, (
            f"Expected 1 pipeline-level emit_complete, got {len(pipeline_complete_calls)}"
        )
        actual_run_id = _get_arg(pipeline_complete_calls[0], 0, "run_id")
        assert actual_run_id == known_run_id, (
            f"emit_complete must use run_id from emit_start ({known_run_id}), got {actual_run_id}"
        )

    @pytest.mark.requirement("AC-OLC-6")
    def test_emit_complete_called_with_job_name(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """emit_complete() is called with job_name matching spec.metadata.name."""
        from floe_core.compilation.stages import compile_pipeline

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter):
            compile_pipeline(spec_path, lineage_manifest_path)

        # Pipeline-level emit_complete must use pipeline job_name
        pipeline_complete_calls = [
            c
            for c in mock_emitter.emit_complete.call_args_list
            if _get_arg(c, 1, "job_name") == PRODUCT_NAME
        ]
        assert len(pipeline_complete_calls) == 1

    @pytest.mark.requirement("AC-OLC-6")
    def test_emit_complete_failure_does_not_block_return(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """If emit_complete() raises, compile_pipeline() still returns artifacts.

        The emit call is wrapped in try/except -- failure logs a warning
        but does not prevent returning the compiled artifacts.
        """
        from floe_core.compilation.stages import compile_pipeline
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Make all emit_complete calls raise (both per-model and pipeline)
        mock_emitter.emit_complete.side_effect = ConnectionError("Marquez down")

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter):
            result = compile_pipeline(spec_path, lineage_manifest_path)

        # Verify pipeline-level emit_complete was attempted
        pipeline_complete_calls = [
            c
            for c in mock_emitter.emit_complete.call_args_list
            if _get_arg(c, 1, "job_name") == PRODUCT_NAME
        ]
        assert len(pipeline_complete_calls) == 1
        assert isinstance(result, CompiledArtifacts)
        assert result.metadata.product_name == PRODUCT_NAME

    @pytest.mark.requirement("AC-OLC-6")
    def test_emitter_close_called_on_success(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """emitter.close() is called in finally block after successful compilation."""
        from floe_core.compilation.stages import compile_pipeline

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter):
            compile_pipeline(spec_path, lineage_manifest_path)

        mock_emitter.close.assert_called_once()

    @pytest.mark.requirement("AC-OLC-6")
    def test_emitter_close_called_on_failure(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """emitter.close() is called in finally block even when compilation fails.

        This verifies the close() is in a finally block, not just on the
        happy path.
        """
        from floe_core.compilation.stages import compile_pipeline

        with (
            patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter),
            patch(
                RESOLVE_PLUGINS_PATH,
                side_effect=RuntimeError("resolution failed"),
            ),
        ):
            with pytest.raises(RuntimeError, match="resolution failed"):
                compile_pipeline(spec_path, lineage_manifest_path)

        mock_emitter.close.assert_called_once()

    @pytest.mark.requirement("AC-OLC-6")
    def test_emit_complete_called_before_return(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """emit_complete() is called before the function returns artifacts.

        Verify the ordering: emit_start -> ... -> emit_complete -> return.
        We use call ordering on the mock to verify emit_complete happens
        after emit_start.
        """
        from floe_core.compilation.stages import compile_pipeline

        call_order: list[str] = []
        mock_emitter.emit_start.side_effect = lambda *a, **kw: (
            call_order.append("emit_start"),
            uuid4(),
        )[-1]
        mock_emitter.emit_complete.side_effect = lambda *a, **kw: call_order.append("emit_complete")
        mock_emitter.close.side_effect = lambda *a, **kw: call_order.append("close")

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter):
            compile_pipeline(spec_path, lineage_manifest_path)

        # With per-model emission (1 model in minimal spec), lifecycle is:
        # pipeline emit_start, per-model emit_start, per-model emit_complete,
        # pipeline emit_complete, close
        assert call_order[0] == "emit_start", f"First call must be emit_start, got {call_order}"
        assert call_order[-1] == "close", f"Last call must be close, got {call_order}"
        # Pipeline-level emit_complete must be second-to-last (just before close)
        assert call_order[-2] == "emit_complete", (
            f"Pipeline emit_complete must be second-to-last (before close), got {call_order}"
        )


class TestCompilePipelineLineageFail:
    """AC-OLC-7: compile_pipeline() emits FAIL event on exception."""

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("AC-OLC-7")
    def test_emit_fail_called_on_compilation_error(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """emit_fail() is called when a compilation stage throws.

        The error_message must be derived from the exception using
        type(exc).__name__ (not str(exc) per CWE-532).
        """
        from floe_core.compilation.stages import compile_pipeline

        known_run_id = uuid4()
        mock_emitter.emit_start.return_value = known_run_id

        with (
            patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter),
            patch(
                RESOLVE_PLUGINS_PATH,
                side_effect=ValueError("bad plugin config"),
            ),
        ):
            with pytest.raises(ValueError, match="bad plugin config"):
                compile_pipeline(spec_path, lineage_manifest_path)

        mock_emitter.emit_fail.assert_called_once()

        # Verify run_id matches emit_start return
        actual_run_id = _get_arg(mock_emitter.emit_fail.call_args, 0, "run_id")
        assert actual_run_id == known_run_id

        # Verify error_message is type name, not str(exc) (CWE-532)
        actual_error = _get_arg(mock_emitter.emit_fail.call_args, 2, "error_message")
        assert actual_error == "ValueError", (
            f"error_message must be type(exc).__name__ ('ValueError'), got '{actual_error}'"
        )

    @pytest.mark.requirement("AC-OLC-7")
    def test_emit_fail_includes_job_name(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """emit_fail() is called with job_name matching spec.metadata.name."""
        from floe_core.compilation.stages import compile_pipeline

        mock_emitter.emit_start.return_value = uuid4()

        with (
            patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter),
            patch(
                RESOLVE_PLUGINS_PATH,
                side_effect=RuntimeError("boom"),
            ),
        ):
            with pytest.raises(RuntimeError):
                compile_pipeline(spec_path, lineage_manifest_path)

        mock_emitter.emit_fail.assert_called_once()
        actual_job_name = _get_arg(mock_emitter.emit_fail.call_args, 1, "job_name")
        assert actual_job_name == PRODUCT_NAME

    @pytest.mark.requirement("AC-OLC-7")
    def test_emit_fail_skipped_when_run_id_none(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """emit_fail() is NOT called when emit_start() itself failed.

        If emit_start() raises (making run_id None), and then compilation
        also fails, emit_fail() must be skipped because there is no valid
        run_id to reference.
        """
        from floe_core.compilation.stages import compile_pipeline

        mock_emitter.emit_start.side_effect = ConnectionError("Cannot reach Marquez")

        with (
            patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter),
            patch(
                RESOLVE_PLUGINS_PATH,
                side_effect=RuntimeError("compilation also failed"),
            ),
        ):
            with pytest.raises(RuntimeError, match="compilation also failed"):
                compile_pipeline(spec_path, lineage_manifest_path)

        # emit_start was attempted but raised
        mock_emitter.emit_start.assert_called_once()
        # emit_fail must NOT be called because run_id is None
        mock_emitter.emit_fail.assert_not_called()

    @pytest.mark.requirement("AC-OLC-7")
    def test_original_exception_reraised_after_emit_fail(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """The original compilation exception is always re-raised after emit_fail().

        emit_fail() must not swallow the original exception. The caller
        must see the same exception type and message.
        """
        from floe_core.compilation.stages import compile_pipeline

        mock_emitter.emit_start.return_value = uuid4()

        class CustomCompilationError(Exception):
            """Custom error to verify exact exception type is preserved."""

        with (
            patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter),
            patch(
                RESOLVE_PLUGINS_PATH,
                side_effect=CustomCompilationError("specific error"),
            ),
        ):
            with pytest.raises(CustomCompilationError, match="specific error"):
                compile_pipeline(spec_path, lineage_manifest_path)

        # Verify emit_fail was called (not skipped due to exception swallowing)
        mock_emitter.emit_fail.assert_called_once()

    @pytest.mark.requirement("AC-OLC-7")
    def test_emit_fail_error_uses_type_name_not_str(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """error_message uses type(exc).__name__, not str(exc).

        CWE-532: str(exc) could leak sensitive information from exception
        messages. Only the exception type name should be used.
        """
        from floe_core.compilation.stages import compile_pipeline

        mock_emitter.emit_start.return_value = uuid4()

        # Use a message that would be problematic if leaked
        secret_message = (
            "password=s3cret in config at /etc/floe/creds.yaml"  # pragma: allowlist secret
        )

        with (
            patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter),
            patch(
                RESOLVE_PLUGINS_PATH,
                side_effect=TypeError(secret_message),
            ),
        ):
            with pytest.raises(TypeError):
                compile_pipeline(spec_path, lineage_manifest_path)

        mock_emitter.emit_fail.assert_called_once()
        actual_error = _get_arg(mock_emitter.emit_fail.call_args, 2, "error_message")

        # Must be type name only -- NOT the secret-containing message
        assert actual_error == "TypeError"
        assert "password" not in (actual_error or "")
        assert "s3cret" not in (actual_error or "")

    @pytest.mark.requirement("AC-OLC-7")
    def test_emit_fail_failure_does_not_mask_original_exception(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """If emit_fail() itself raises, the original exception is still re-raised.

        The emit_fail call is wrapped in try/except -- its own failure
        must not mask the original compilation error.
        """
        from floe_core.compilation.stages import compile_pipeline

        mock_emitter.emit_start.return_value = uuid4()
        mock_emitter.emit_fail.side_effect = ConnectionError("Marquez truly dead")

        with (
            patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter),
            patch(
                RESOLVE_PLUGINS_PATH,
                side_effect=ValueError("original compilation error"),
            ),
        ):
            # Must see the ORIGINAL error, not the emit_fail ConnectionError
            with pytest.raises(ValueError, match="original compilation error"):
                compile_pipeline(spec_path, lineage_manifest_path)

        # emit_fail was attempted (even though it raised)
        mock_emitter.emit_fail.assert_called_once()

    @pytest.mark.requirement("AC-OLC-7")
    def test_emitter_close_called_after_emit_fail(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """emitter.close() is called in finally block after emit_fail().

        Even on the error path, the emitter must be properly closed.
        """
        from floe_core.compilation.stages import compile_pipeline

        call_order: list[str] = []
        mock_emitter.emit_start.side_effect = lambda *a, **kw: (
            call_order.append("emit_start"),
            uuid4(),
        )[-1]
        mock_emitter.emit_fail.side_effect = lambda *a, **kw: call_order.append("emit_fail")
        mock_emitter.close.side_effect = lambda *a, **kw: call_order.append("close")

        with (
            patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter),
            patch(
                RESOLVE_PLUGINS_PATH,
                side_effect=RuntimeError("boom"),
            ),
        ):
            with pytest.raises(RuntimeError):
                compile_pipeline(spec_path, lineage_manifest_path)

        assert call_order == ["emit_start", "emit_fail", "close"], (
            f"Expected error lifecycle order [emit_start, emit_fail, close], got {call_order}"
        )


class TestCompilePipelineLineageEdgeCases:
    """Edge cases for lineage integration that cut across AC-5/6/7."""

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("AC-OLC-5")
    def test_lifecycle_invoked_even_when_lineage_disabled(
        self,
        spec_path: Path,
        lineage_disabled_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """When lineage is disabled, emit_start/complete must still be called on NoOp emitter.

        The factory returns a NoOp emitter, but the pipeline still calls
        emit_start/emit_complete on it (the NoOp transport silently discards).
        This test verifies the emitter lifecycle is invoked regardless.
        """
        from floe_core.compilation.stages import compile_pipeline

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter) as mock_factory:
            compile_pipeline(spec_path, lineage_disabled_manifest_path)

        # The factory must be called (even if with None config -> NoOp)
        mock_factory.assert_called_once()
        # Pipeline-level lifecycle calls still happen (NoOp emitter handles them silently)
        # Per-model calls also present, so filter for pipeline-level
        pipeline_start_calls = [
            c
            for c in mock_emitter.emit_start.call_args_list
            if _get_arg(c, 0, "job_name") == PRODUCT_NAME
        ]
        pipeline_complete_calls = [
            c
            for c in mock_emitter.emit_complete.call_args_list
            if _get_arg(c, 1, "job_name") == PRODUCT_NAME
        ]
        assert len(pipeline_start_calls) == 1
        assert len(pipeline_complete_calls) == 1
        mock_emitter.close.assert_called_once()

    @pytest.mark.requirement("AC-OLC-5")
    def test_per_model_lineage_uses_product_dbt_project_identity(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """Compilation model lineage must use product-derived dbt project identity."""
        from floe_core.compilation.stages import compile_pipeline

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter):
            compile_pipeline(spec_path, lineage_manifest_path)

        model_start_jobs = {
            _get_arg(call_args, 0, "job_name")
            for call_args in mock_emitter.emit_start.call_args_list
            if str(_get_arg(call_args, 0, "job_name")).startswith("model.")
        }
        assert "model.test_product.customers" in model_start_jobs
        assert "model.floe.customers" not in model_start_jobs

    @pytest.mark.requirement("AC-OLC-5")
    @pytest.mark.requirement("AC-OLC-6")
    def test_create_sync_emitter_invoked_by_compile_pipeline(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
    ) -> None:
        """compile_pipeline actually imports and calls create_sync_emitter.

        This test verifies that compile_pipeline uses the factory function.
        If stages.py doesn't import it, the tracking wrapper won't fire.
        """
        from floe_core.compilation.stages import compile_pipeline
        from floe_core.lineage.emitter import create_sync_emitter as real_factory

        invoked: list[bool] = []

        def tracking_factory(*args: Any, **kwargs: Any) -> Any:
            invoked.append(True)
            return real_factory(*args, **kwargs)

        with patch(CREATE_SYNC_EMITTER_PATH, side_effect=tracking_factory):
            compile_pipeline(spec_path, lineage_manifest_path)

        assert invoked, "compile_pipeline must call create_sync_emitter"

    @pytest.mark.requirement("AC-OLC-5")
    def test_endpoint_mapped_to_url_key(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
        mock_emitter: MagicMock,
    ) -> None:
        """The manifest 'endpoint' field is mapped to 'url' key in transport config.

        This catches a bug where someone passes endpoint= instead of url=
        to the transport config dict.
        """
        from floe_core.compilation.stages import compile_pipeline

        with patch(CREATE_SYNC_EMITTER_PATH, return_value=mock_emitter) as mock_factory:
            compile_pipeline(spec_path, lineage_manifest_path)

        mock_factory.assert_called_once()
        config_arg = _get_arg(mock_factory.call_args, 0, "transport_config")
        assert config_arg is not None, "transport_config must not be None for enabled lineage"
        assert "url" in config_arg, "Config dict must use 'url' key (not 'endpoint')"
        assert "endpoint" not in config_arg, "Config dict must NOT have 'endpoint' key -- use 'url'"

    @pytest.mark.requirement("AC-OLC-5")
    def test_emitter_construction_failure_does_not_crash_compilation(
        self,
        spec_path: Path,
        lineage_manifest_path: Path,
    ) -> None:
        """If create_sync_emitter() raises, compilation falls back to NoOp emitter.

        Verifies that a bad lineage config (e.g. invalid URL scheme) does not
        crash compile_pipeline() — lineage must never block compilation.
        """
        from floe_core.compilation.stages import compile_pipeline

        with patch(
            CREATE_SYNC_EMITTER_PATH,
            side_effect=[ValueError("bad URL scheme"), MagicMock()],
        ):
            # Must not raise — falls back to NoOp emitter
            result = compile_pipeline(spec_path, lineage_manifest_path)

        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        assert isinstance(result, CompiledArtifacts)
        assert result.metadata.product_name == PRODUCT_NAME

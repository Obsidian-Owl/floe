"""Integration test for compile_pipeline() → create_sync_emitter() wiring.

Verifies the integration seam: the config dict produced by
_build_lineage_config() is passed to create_sync_emitter() unchanged,
and that per-model lineage events are emitted during compilation.

Task: OpenLineage env var override, per-model lineage emission
Requirements: AC-1 (env var override wiring), AC-1/AC-2/AC-3 (per-model emission)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

ENV_VAR_ENDPOINT = "http://override.example.com:5100/api/v1/lineage"
"""OPENLINEAGE_URL env var value used in override tests."""

# Known model names from demo/customer-360/floe.yaml
DEMO_MODEL_NAMES: list[str] = [
    "stg_crm_customers",
    "stg_transactions",
    "stg_support_tickets",
    "int_customer_orders",
    "int_customer_support",
    "mart_customer_360",
]
"""All model names in the demo customer-360 spec, for per-model emission tests."""

MODEL_JOB_NAME_PREFIX = "model.floe."
"""Job name prefix for per-model lineage events (AC-2)."""


class TestCompilePipelineLineageWiring:
    """Tests that compile_pipeline() wires _build_lineage_config() to create_sync_emitter().

    Verifies the integration seam: the config dict produced by
    _build_lineage_config() is passed to create_sync_emitter() unchanged.
    """

    @pytest.mark.requirement("AC-1")
    def test_compile_pipeline_passes_lineage_config_to_emitter(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """compile_pipeline() passes _build_lineage_config() result to create_sync_emitter().

        Patches create_sync_emitter to capture its arguments, then verifies
        that the config dict includes the env-var-overridden URL.
        """
        monkeypatch.setenv("OPENLINEAGE_URL", ENV_VAR_ENDPOINT)
        # Ensure OTel endpoint is unset so we don't need a real collector
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        root = Path(__file__).parent.parent.parent.parent.parent
        spec_path = root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = root / "demo" / "manifest.yaml"

        if not spec_path.exists() or not manifest_path.exists():
            pytest.fail(
                f"Demo spec files not found at {spec_path} / {manifest_path}.\n"
                "These files are required for the wiring integration test.\n"
                "Ensure the demo/ directory is present in the repository root."
            )

        captured_configs: list[Any] = []

        from floe_core.lineage.emitter import create_sync_emitter as original_create

        def _capturing_create(
            transport_config: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> Any:
            captured_configs.append(transport_config)
            # Use NoOp transport to avoid network calls
            return original_create(None, **kwargs)

        with patch(
            "floe_core.lineage.emitter.create_sync_emitter",
            side_effect=_capturing_create,
        ):
            from floe_core.compilation.stages import compile_pipeline

            compile_pipeline(spec_path, manifest_path)

        assert len(captured_configs) >= 1, (
            "create_sync_emitter was never called during compile_pipeline()"
        )
        config = captured_configs[0]
        assert config is not None, (
            "create_sync_emitter received None config — "
            "_build_lineage_config() result was not passed through"
        )
        assert config.get("url") == ENV_VAR_ENDPOINT, (
            f"Expected emitter config url {ENV_VAR_ENDPOINT!r}, "
            f"got {config.get('url')!r}. "
            "compile_pipeline() must pass _build_lineage_config() result "
            "to create_sync_emitter()."
        )
        assert config.get("type") == "http", (
            f"Expected emitter config type 'http', got {config.get('type')!r}"
        )


def _get_demo_paths() -> tuple[Path, Path]:
    """Return (spec_path, manifest_path) for the demo customer-360 spec.

    Calls pytest.fail if demo files are missing.

    Returns:
        Tuple of (spec_path, manifest_path).
    """
    root = Path(__file__).parent.parent.parent.parent.parent
    spec_path = root / "demo" / "customer-360" / "floe.yaml"
    manifest_path = root / "demo" / "manifest.yaml"

    if not spec_path.exists() or not manifest_path.exists():
        pytest.fail(
            f"Demo spec files not found at {spec_path} / {manifest_path}.\n"
            "These files are required for integration tests.\n"
            "Ensure the demo/ directory is present in the repository root."
        )
    return spec_path, manifest_path


def _make_tracking_emitter() -> tuple[Any, MagicMock, MagicMock]:
    """Create a NoOp emitter with tracked emit_start and emit_complete calls.

    Returns a real SyncLineageEmitter (NoOp transport) but wraps emit_start
    and emit_complete so we can inspect all calls. The pipeline-level call
    (emit_start with the spec name) will also be captured — tests must filter
    for per-model calls.

    Returns:
        Tuple of (emitter, emit_start_mock, emit_complete_mock).
    """
    from floe_core.lineage.emitter import create_sync_emitter as real_create

    emitter = real_create(None, default_namespace="floe.compilation")

    original_start = emitter.emit_start
    original_complete = emitter.emit_complete

    start_mock = MagicMock(side_effect=original_start)
    complete_mock = MagicMock(side_effect=original_complete)

    emitter.emit_start = start_mock  # type: ignore[method-assign]
    emitter.emit_complete = complete_mock  # type: ignore[method-assign]

    return emitter, start_mock, complete_mock


class TestPerModelLineageEmission:
    """Tests that compile_pipeline() emits per-model START+COMPLETE lineage events.

    Verifies AC-1 (emit for each model), AC-2 (job name format), and
    AC-3 (failure isolation and CWE-532 logging).

    These tests MUST FAIL until per-model emission is implemented in
    compile_pipeline() (between enforcement and GENERATE stage).
    """

    @pytest.mark.requirement("AC-1")
    def test_per_model_emit_start_and_complete_called(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """After compile_pipeline(), emit_start and emit_complete are called for each model.

        Verifies that the emitter's emit_start is called once per model in
        transforms.models, and emit_complete is called once per model.
        Pipeline-level calls (for spec.metadata.name) are excluded from the count.
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENLINEAGE_URL", raising=False)
        spec_path, manifest_path = _get_demo_paths()

        emitter, start_mock, complete_mock = _make_tracking_emitter()

        def _factory(
            transport_config: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> Any:
            return emitter

        with patch(
            "floe_core.lineage.emitter.create_sync_emitter",
            side_effect=_factory,
        ):
            from floe_core.compilation.stages import compile_pipeline

            compile_pipeline(spec_path, manifest_path)

        # Filter for per-model calls (job_name starts with "model.floe.")
        model_start_calls = [
            c
            for c in start_mock.call_args_list
            if c.kwargs.get("job_name", c.args[0] if c.args else "").startswith(
                MODEL_JOB_NAME_PREFIX
            )
        ]
        model_complete_calls = [
            c
            for c in complete_mock.call_args_list
            if (
                c.kwargs.get("job_name") is not None
                and str(c.kwargs.get("job_name", "")).startswith(MODEL_JOB_NAME_PREFIX)
            )
            or (len(c.args) >= 2 and str(c.args[1]).startswith(MODEL_JOB_NAME_PREFIX))
        ]

        expected_model_count = len(DEMO_MODEL_NAMES)

        assert len(model_start_calls) == expected_model_count, (
            f"Expected {expected_model_count} per-model emit_start calls "
            f"(one per model in transforms.models), got {len(model_start_calls)}. "
            f"Total emit_start calls: {len(start_mock.call_args_list)}. "
            "compile_pipeline() must emit START for each model."
        )
        assert len(model_complete_calls) == expected_model_count, (
            f"Expected {expected_model_count} per-model emit_complete calls, "
            f"got {len(model_complete_calls)}. "
            "compile_pipeline() must emit COMPLETE for each model."
        )

    @pytest.mark.requirement("AC-2")
    def test_per_model_job_name_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Per-model emit_start job_name follows model.floe.{name} convention.

        Verifies that each model name from transforms.models results in
        an emit_start call with job_name == f"model.floe.{model.name}".
        This catches implementations that use a different naming convention
        (e.g., bare model name, or "floe.model.{name}").
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENLINEAGE_URL", raising=False)
        spec_path, manifest_path = _get_demo_paths()

        emitter, start_mock, complete_mock = _make_tracking_emitter()

        def _factory(
            transport_config: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> Any:
            return emitter

        with patch(
            "floe_core.lineage.emitter.create_sync_emitter",
            side_effect=_factory,
        ):
            from floe_core.compilation.stages import compile_pipeline

            compile_pipeline(spec_path, manifest_path)

        # Extract all job_name values from emit_start calls
        start_job_names: list[str] = []
        for c in start_mock.call_args_list:
            job_name = c.kwargs.get("job_name", c.args[0] if c.args else None)
            if job_name is not None:
                start_job_names.append(str(job_name))

        # Filter to per-model calls
        model_job_names = [n for n in start_job_names if n.startswith(MODEL_JOB_NAME_PREFIX)]

        # Every demo model must have an exact match
        expected_job_names = sorted(f"{MODEL_JOB_NAME_PREFIX}{name}" for name in DEMO_MODEL_NAMES)
        actual_job_names = sorted(model_job_names)

        assert actual_job_names == expected_job_names, (
            f"Per-model job names do not match expected format.\n"
            f"Expected: {expected_job_names}\n"
            f"Actual:   {actual_job_names}\n"
            "Job names must follow 'model.floe.{{name}}' convention."
        )

    @pytest.mark.requirement("AC-2")
    def test_per_model_complete_uses_same_job_name_as_start(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """emit_complete for each model uses the same job_name as emit_start.

        Guards against an implementation that starts with model.floe.{name}
        but completes with a different name (e.g., bare model name).
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENLINEAGE_URL", raising=False)
        spec_path, manifest_path = _get_demo_paths()

        emitter, start_mock, complete_mock = _make_tracking_emitter()

        def _factory(
            transport_config: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> Any:
            return emitter

        with patch(
            "floe_core.lineage.emitter.create_sync_emitter",
            side_effect=_factory,
        ):
            from floe_core.compilation.stages import compile_pipeline

            compile_pipeline(spec_path, manifest_path)

        # Extract per-model start job names
        start_model_names: list[str] = []
        for c in start_mock.call_args_list:
            job_name = c.kwargs.get("job_name", c.args[0] if c.args else None)
            if job_name and str(job_name).startswith(MODEL_JOB_NAME_PREFIX):
                start_model_names.append(str(job_name))

        # Extract per-model complete job names (second arg or kwarg)
        complete_model_names: list[str] = []
        for c in complete_mock.call_args_list:
            job_name = c.kwargs.get("job_name")
            if job_name is None and len(c.args) >= 2:
                job_name = c.args[1]
            if job_name and str(job_name).startswith(MODEL_JOB_NAME_PREFIX):
                complete_model_names.append(str(job_name))

        # Guard against vacuous pass when no per-model calls exist
        assert len(start_model_names) == len(DEMO_MODEL_NAMES), (
            f"Expected {len(DEMO_MODEL_NAMES)} per-model emit_start calls, "
            f"got {len(start_model_names)}. "
            "Cannot verify name consistency without per-model emissions."
        )
        assert sorted(start_model_names) == sorted(complete_model_names), (
            f"Per-model emit_complete job names don't match emit_start job names.\n"
            f"Start:    {sorted(start_model_names)}\n"
            f"Complete: {sorted(complete_model_names)}\n"
            "Each model's COMPLETE event must use the same job_name as its START."
        )

    @pytest.mark.requirement("AC-3")
    def test_per_model_emission_failure_non_blocking(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Failure emitting for one model must not prevent others or abort compilation.

        Configures emit_start to raise on one specific model. Verifies that:
        1. compile_pipeline() still returns a CompiledArtifacts (no exception)
        2. Other models still get emit_start/emit_complete calls
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENLINEAGE_URL", raising=False)
        spec_path, manifest_path = _get_demo_paths()

        failing_model = DEMO_MODEL_NAMES[0]  # stg_crm_customers
        failing_job_name = f"{MODEL_JOB_NAME_PREFIX}{failing_model}"
        successful_models = [m for m in DEMO_MODEL_NAMES if m != failing_model]

        from floe_core.lineage.emitter import create_sync_emitter as real_create

        emitter = real_create(None, default_namespace="floe.compilation")

        original_start = emitter.emit_start
        start_mock = MagicMock()
        complete_mock = MagicMock(side_effect=emitter.emit_complete)

        def _selective_failing_start(job_name: str, **kwargs: Any) -> UUID:
            """Raise on the failing model, delegate to real for others."""
            start_mock(job_name=job_name, **kwargs)
            if job_name == failing_job_name:
                raise ConnectionError("simulated transport failure")
            return original_start(job_name=job_name, **kwargs)

        emitter.emit_start = _selective_failing_start  # type: ignore[method-assign]
        emitter.emit_complete = complete_mock  # type: ignore[method-assign]

        def _factory(
            transport_config: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> Any:
            return emitter

        with patch(
            "floe_core.lineage.emitter.create_sync_emitter",
            side_effect=_factory,
        ):
            from floe_core.compilation.stages import compile_pipeline

            # Must not raise — compilation must succeed despite emission failure
            result = compile_pipeline(spec_path, manifest_path)

        # Compilation must produce a valid result
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        assert isinstance(result, CompiledArtifacts), (
            "compile_pipeline() must return CompiledArtifacts after model emission failure"
        )
        assert result.metadata.product_name is not None, "Result missing product_name"

        # The failing model should have had emit_start attempted
        failing_start_calls = [
            c for c in start_mock.call_args_list if c.kwargs.get("job_name") == failing_job_name
        ]
        assert len(failing_start_calls) == 1, (
            f"emit_start should have been attempted for {failing_job_name}"
        )

        # Other models must still get emit_complete calls
        other_complete_calls = [
            c
            for c in complete_mock.call_args_list
            if (
                c.kwargs.get("job_name") is not None
                and str(c.kwargs.get("job_name", "")).startswith(MODEL_JOB_NAME_PREFIX)
                and str(c.kwargs.get("job_name", "")) != failing_job_name
            )
            or (
                len(c.args) >= 2
                and str(c.args[1]).startswith(MODEL_JOB_NAME_PREFIX)
                and str(c.args[1]) != failing_job_name
            )
        ]
        assert len(other_complete_calls) >= len(successful_models), (
            f"Expected emit_complete for at least {len(successful_models)} "
            f"non-failing models, got {len(other_complete_calls)}. "
            "A failure on one model must not prevent emission for others."
        )

    @pytest.mark.requirement("AC-3")
    def test_per_model_emission_error_logs_type_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When per-model emission fails, log contains lineage_model_emit_failed with type only.

        Verifies CWE-532 compliance: the log message includes the exception
        type name (e.g., 'ConnectionError') but NOT the exception message
        (which may contain credential-bearing URLs).
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENLINEAGE_URL", raising=False)
        spec_path, manifest_path = _get_demo_paths()

        failing_model = DEMO_MODEL_NAMES[2]  # stg_support_tickets
        failing_job_name = f"{MODEL_JOB_NAME_PREFIX}{failing_model}"
        secret_url = "http://secret-key:password@lineage.internal/api"

        from floe_core.lineage.emitter import create_sync_emitter as real_create

        emitter = real_create(None, default_namespace="floe.compilation")

        original_start = emitter.emit_start

        def _failing_start(job_name: str, **kwargs: Any) -> UUID:
            if job_name == failing_job_name:
                raise ConnectionError(f"Failed to connect to {secret_url}")
            return original_start(job_name=job_name, **kwargs)

        emitter.emit_start = _failing_start  # type: ignore[method-assign]

        def _factory(
            transport_config: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> Any:
            return emitter

        from structlog.testing import capture_logs

        with capture_logs() as cap_logs:
            with patch(
                "floe_core.lineage.emitter.create_sync_emitter",
                side_effect=_factory,
            ):
                from floe_core.compilation.stages import compile_pipeline

                compile_pipeline(spec_path, manifest_path)

        # Find the lineage_model_emit_failed log entries
        fail_events = [e for e in cap_logs if e.get("event") == "lineage_model_emit_failed"]

        # Must contain the event
        assert len(fail_events) >= 1, (
            "Expected 'lineage_model_emit_failed' in captured logs "
            f"when emit_start fails for model {failing_model}. "
            f"Captured events: {[e.get('event') for e in cap_logs]}"
        )
        # Must contain model name for debugging
        model_event = [e for e in fail_events if e.get("model") == failing_model]
        assert len(model_event) >= 1, f"Log missing event for model '{failing_model}'"
        # Must contain exception type name (CWE-532: type only)
        assert model_event[0].get("error") == "ConnectionError", (
            f"Expected error='ConnectionError', got {model_event[0].get('error')!r}"
        )
        # Must NOT contain the secret URL (CWE-532 violation)
        event_str = str(model_event[0])
        assert secret_url not in event_str, (
            "CWE-532 VIOLATION: Log event contains credential-bearing URL"
        )
        assert "password" not in event_str.lower(), (
            "CWE-532 VIOLATION: Log event may contain credentials"
        )

    @pytest.mark.requirement("AC-1")
    def test_per_model_emission_uses_run_id_from_start(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """emit_complete for each model passes the run_id returned by emit_start.

        Guards against an implementation that ignores the run_id from
        emit_start or uses a different/hardcoded run_id for emit_complete.
        """
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENLINEAGE_URL", raising=False)
        spec_path, manifest_path = _get_demo_paths()

        from floe_core.lineage.emitter import create_sync_emitter as real_create

        emitter = real_create(None, default_namespace="floe.compilation")

        # Track start return values keyed by job_name
        start_run_ids: dict[str, UUID] = {}
        original_start = emitter.emit_start
        original_complete = emitter.emit_complete
        complete_calls: list[tuple[UUID, str]] = []

        def _tracking_start(job_name: str, **kwargs: Any) -> UUID:
            run_id = original_start(job_name=job_name, **kwargs)
            if job_name.startswith(MODEL_JOB_NAME_PREFIX):
                start_run_ids[job_name] = run_id
            return run_id

        def _tracking_complete(run_id: UUID, job_name: str, **kwargs: Any) -> None:
            if job_name.startswith(MODEL_JOB_NAME_PREFIX):
                complete_calls.append((run_id, job_name))
            return original_complete(run_id, job_name, **kwargs)

        emitter.emit_start = _tracking_start  # type: ignore[method-assign]
        emitter.emit_complete = _tracking_complete  # type: ignore[method-assign]

        def _factory(
            transport_config: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> Any:
            return emitter

        with patch(
            "floe_core.lineage.emitter.create_sync_emitter",
            side_effect=_factory,
        ):
            from floe_core.compilation.stages import compile_pipeline

            compile_pipeline(spec_path, manifest_path)

        # Must have per-model start calls
        assert len(start_run_ids) == len(DEMO_MODEL_NAMES), (
            f"Expected {len(DEMO_MODEL_NAMES)} per-model emit_start calls, got {len(start_run_ids)}"
        )

        # Each complete call must use the run_id from the corresponding start
        for complete_run_id, complete_job_name in complete_calls:
            expected_run_id = start_run_ids.get(complete_job_name)
            assert expected_run_id is not None, (
                f"emit_complete called for {complete_job_name} but no "
                "corresponding emit_start was recorded"
            )
            assert complete_run_id == expected_run_id, (
                f"emit_complete for {complete_job_name} used run_id "
                f"{complete_run_id}, but emit_start returned {expected_run_id}. "
                "emit_complete must use the run_id from emit_start."
            )

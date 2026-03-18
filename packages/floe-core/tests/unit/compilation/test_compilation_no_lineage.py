"""Tests verifying lineage emission is absent from compile_pipeline().

After T1 removes compilation-time lineage emission from stages.py,
compile_pipeline() must:
- NOT call create_emitter or any lineage emission functions
- NOT read MARQUEZ_URL from the environment
- Still produce valid CompiledArtifacts with OTel spans
- NOT import from floe_core.lineage at module or function level

These tests are written to FAIL against the current code (which still
has lineage emission) and PASS after the lineage code is removed.

Requirements:
    - AC-1: ALL lineage emission code removed from compile_pipeline()
    - AC-2: OTel span emission preserved
    - AC-9: No MARQUEZ_URL dependency in compilation path
    - AC-10: Unused lineage imports removed from stages.py
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Constants (deduplicate string literals per code-quality rules)
# ---------------------------------------------------------------------------
STAGES_MODULE_PATH = "floe_core.compilation.stages"
CREATE_EMITTER_PATH = "floe_core.lineage.emitter.create_emitter"
MARQUEZ_URL_KEY = "MARQUEZ_URL"
MARQUEZ_URL_VALUE = "http://localhost:5000/api/v1/lineage"
OTEL_CREATE_SPAN_PATH = "floe_core.telemetry.tracing.create_span"


class TestCompilePipelineNoLineage:
    """Verify that compile_pipeline() contains no lineage emission code."""

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    # ------------------------------------------------------------------
    # AC-1: compile_pipeline does NOT call create_emitter even when
    #        MARQUEZ_URL is set.
    # ------------------------------------------------------------------
    @pytest.mark.requirement("AC-1")
    def test_compile_pipeline_does_not_call_create_emitter(
        self, spec_path: Path, manifest_path: Path
    ) -> None:
        """Compile with MARQUEZ_URL set must NOT call create_emitter.

        The current code creates a lineage emitter when MARQUEZ_URL is set.
        After T1, this code path is removed entirely, so create_emitter
        must never be invoked regardless of env vars.
        """
        from floe_core.compilation.stages import compile_pipeline

        mock_emitter = MagicMock()
        mock_emitter.emit_start = MagicMock(return_value=MagicMock())
        mock_emitter.emit_complete = MagicMock(return_value=None)
        mock_emitter.emit_fail = MagicMock(return_value=None)
        mock_emitter.close = MagicMock()
        mock_emitter.transport = MagicMock()
        mock_emitter.transport.close_async = MagicMock(return_value=MagicMock())

        with (
            patch.dict("os.environ", {MARQUEZ_URL_KEY: MARQUEZ_URL_VALUE}),
            patch(CREATE_EMITTER_PATH, return_value=mock_emitter) as mock_create,
        ):
            result = compile_pipeline(spec_path, manifest_path)

        # After T1, create_emitter must NEVER be called
        mock_create.assert_not_called()

        # Compilation must still succeed
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        assert isinstance(result, CompiledArtifacts)
        assert result.metadata.product_name == "test-product"

    # ------------------------------------------------------------------
    # AC-1: No emit_start / emit_complete / emit_fail calls
    # ------------------------------------------------------------------
    @pytest.mark.requirement("AC-1")
    def test_compile_pipeline_no_lineage_emission_calls(
        self, spec_path: Path, manifest_path: Path
    ) -> None:
        """Compilation must not invoke any lineage emission methods.

        Even if an emitter were somehow constructed, compile_pipeline()
        must not call emit_start, emit_complete, or emit_fail.  We
        monkey-patch the emitter module to detect any such calls.
        """
        from floe_core.compilation.stages import compile_pipeline

        spy_emitter = MagicMock()
        spy_emitter.transport = MagicMock()
        spy_emitter.transport.close_async = MagicMock(return_value=MagicMock())

        with (
            patch.dict("os.environ", {MARQUEZ_URL_KEY: MARQUEZ_URL_VALUE}),
            patch(CREATE_EMITTER_PATH, return_value=spy_emitter),
        ):
            compile_pipeline(spec_path, manifest_path)

        # After T1, no lineage methods should have been called
        spy_emitter.emit_start.assert_not_called()
        spy_emitter.emit_complete.assert_not_called()
        spy_emitter.emit_fail.assert_not_called()
        spy_emitter.close.assert_not_called()

    # ------------------------------------------------------------------
    # AC-9: compile_pipeline must NOT read MARQUEZ_URL from env
    # ------------------------------------------------------------------
    @pytest.mark.requirement("AC-9")
    def test_compile_pipeline_does_not_read_marquez_url(
        self, spec_path: Path, manifest_path: Path
    ) -> None:
        """Compilation must not access MARQUEZ_URL from os.environ.

        After T1, the compilation path has zero dependency on MARQUEZ_URL.
        We inspect the source code of compile_pipeline for any reference
        to the MARQUEZ_URL string, which is a robust detection method that
        does not depend on runtime mocking of os.environ.
        """
        from floe_core.compilation.stages import compile_pipeline

        source = inspect.getsource(compile_pipeline)

        assert MARQUEZ_URL_KEY not in source, (
            "compile_pipeline() source contains a reference to 'MARQUEZ_URL' — "
            "this env var dependency must be removed (AC-9)"
        )

    # ------------------------------------------------------------------
    # AC-2: OTel span emission is preserved after lineage removal
    # ------------------------------------------------------------------
    @pytest.mark.requirement("AC-2")
    def test_compile_pipeline_still_emits_otel_spans(
        self, spec_path: Path, manifest_path: Path
    ) -> None:
        """OTel spans for all 6 compilation stages must still be created.

        After T1, the only observability mechanism in compile_pipeline()
        is OTel tracing.  Verify that create_span is called with the
        expected stage span names.
        """
        from floe_core.compilation.stages import compile_pipeline

        span_names: list[str] = []

        # Import the real create_span so we can wrap it
        from contextlib import contextmanager

        from floe_core.telemetry.tracing import create_span as real_create_span

        @contextmanager
        def tracking_create_span(name: str, **kwargs: Any) -> Any:  # type: ignore[misc]
            span_names.append(name)
            with real_create_span(name, **kwargs) as span:
                yield span

        with patch(
            "floe_core.compilation.stages.create_span",
            side_effect=tracking_create_span,
        ):
            compile_pipeline(spec_path, manifest_path)

        # The 6 stages plus the pipeline parent span
        expected_span_names = {
            "compile.pipeline",
            "compile.load",
            "compile.validate",
            "compile.resolve",
            "compile.enforce",
            "compile.compile",
            "compile.generate",
        }
        actual_span_names = set(span_names)

        assert expected_span_names.issubset(actual_span_names), (
            f"Missing OTel spans after lineage removal. "
            f"Expected: {expected_span_names}, Got: {actual_span_names}"
        )

    # ------------------------------------------------------------------
    # AC-10: stages.py source must not reference floe_core.lineage
    # ------------------------------------------------------------------
    @pytest.mark.requirement("AC-10")
    def test_stages_module_has_no_lineage_imports(self) -> None:
        """The stages module source must not import from floe_core.lineage.

        After T1, all lineage imports (both top-level and inline) are
        removed from stages.py. This test inspects the actual source
        code to catch any remaining references.
        """
        import floe_core.compilation.stages as stages_mod

        source = inspect.getsource(stages_mod)

        lineage_import_patterns = [
            "from floe_core.lineage",
            "import floe_core.lineage",
            "floe_core.lineage.emitter",
            "floe_core.lineage.facets",
        ]

        violations: list[str] = []
        for pattern in lineage_import_patterns:
            if pattern in source:
                violations.append(pattern)

        assert not violations, (
            f"stages.py still contains lineage references that must be removed (AC-10): "
            f"{violations}"
        )

    # ------------------------------------------------------------------
    # AC-10: stages.py must not import asyncio (only used for lineage)
    # ------------------------------------------------------------------
    @pytest.mark.requirement("AC-10")
    def test_stages_module_no_asyncio_import(self) -> None:
        """The stages module must not import asyncio after lineage removal.

        The asyncio module was only used to create a persistent event
        loop for lineage emission. With lineage removed, asyncio is
        unused and its import should be cleaned up.
        """
        import floe_core.compilation.stages as stages_mod

        source = inspect.getsource(stages_mod)

        # Check for top-level 'import asyncio' statement
        # We look for the pattern at the start of a line to avoid matching
        # occurrences in comments or strings
        lines = source.splitlines()
        asyncio_import_lines = [
            (i + 1, line) for i, line in enumerate(lines) if line.strip() == "import asyncio"
        ]

        assert not asyncio_import_lines, (
            f"stages.py still imports asyncio (only needed for lineage, now removed). "
            f"Found at line(s): {asyncio_import_lines}"
        )

    # ------------------------------------------------------------------
    # AC-1 + AC-9: compile_pipeline succeeds with NO MARQUEZ_URL set
    #              and returns valid artifacts (regression guard)
    # ------------------------------------------------------------------
    @pytest.mark.requirement("AC-1")
    def test_compile_pipeline_without_marquez_url_returns_valid_artifacts(
        self, spec_path: Path, manifest_path: Path
    ) -> None:
        """Compilation without MARQUEZ_URL produces valid CompiledArtifacts.

        This is a regression guard: after lineage removal, the happy-path
        must still work. We verify specific fields to prevent a sloppy
        implementation that returns an empty/default object.
        """
        from floe_core.compilation.stages import compile_pipeline
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

        # Ensure MARQUEZ_URL is absent
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop(MARQUEZ_URL_KEY, None)
            result = compile_pipeline(spec_path, manifest_path)

        assert isinstance(result, CompiledArtifacts)
        assert result.version == COMPILED_ARTIFACTS_VERSION
        assert result.metadata.product_name == "test-product"
        assert result.plugins.compute.type == "duckdb"
        assert result.plugins.orchestrator.type == "dagster"
        assert result.dbt_profiles is not None
        assert "test-product" in result.dbt_profiles

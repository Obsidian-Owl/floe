"""Unit tests for compilation stages module.

Tests the compile_pipeline orchestrator and CompilationStage enum.

Requirements:
    - FR-031: 6-stage compilation pipeline
    - FR-032: Structured logging for each stage
    - AC-9.4: Governance wiring from manifest to CompiledArtifacts
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

# YAML constants for governance tests - manifests WITH and WITHOUT governance
MANIFEST_WITH_GOVERNANCE_YAML = """\
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
governance:
  policy_enforcement_level: strict
  audit_logging: enabled
  data_retention_days: 30
  pii_encryption: required
"""

MANIFEST_WITH_PARTIAL_GOVERNANCE_YAML = """\
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
governance:
  policy_enforcement_level: warn
"""


class TestCompilationStage:
    """Tests for CompilationStage enum."""

    @pytest.mark.requirement("FR-031")
    def test_stage_exit_codes(self) -> None:
        """Test that validation stages return exit code 1, others return 2."""
        from floe_core.compilation.stages import CompilationStage

        # Validation stages (input problems)
        assert CompilationStage.LOAD.exit_code == 1
        assert CompilationStage.VALIDATE.exit_code == 1

        # Compilation stages (processing problems)
        assert CompilationStage.RESOLVE.exit_code == 2
        assert CompilationStage.ENFORCE.exit_code == 2
        assert CompilationStage.COMPILE.exit_code == 2
        assert CompilationStage.GENERATE.exit_code == 2

    @pytest.mark.requirement("FR-031")
    def test_stage_descriptions(self) -> None:
        """Test that all stages have unique descriptions."""
        from floe_core.compilation.stages import CompilationStage

        descriptions = [stage.description for stage in CompilationStage]
        for desc in descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0

        # W5: Verify descriptions are unique
        assert len(set(descriptions)) == len(descriptions), "Stage descriptions must be unique"

    @pytest.mark.requirement("FR-031")
    def test_all_six_stages_exist(self) -> None:
        """Test that all 6 compilation stages exist."""
        from floe_core.compilation.stages import CompilationStage

        expected = {"LOAD", "VALIDATE", "RESOLVE", "ENFORCE", "COMPILE", "GENERATE"}
        actual = {stage.value for stage in CompilationStage}
        assert actual == expected


class TestCompilePipeline:
    """Tests for compile_pipeline orchestrator function."""

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("FR-031")
    def test_compile_pipeline_returns_compiled_artifacts(
        self, spec_path: Path, manifest_path: Path
    ) -> None:
        """Test that compile_pipeline returns CompiledArtifacts."""
        from floe_core.compilation.stages import compile_pipeline
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        result = compile_pipeline(spec_path, manifest_path)

        assert isinstance(result, CompiledArtifacts)
        # I22: Verify actual content, not just type
        assert result.metadata.product_name == "test-product"

    @pytest.mark.requirement("FR-031")
    def test_compile_pipeline_version(self, spec_path: Path, manifest_path: Path) -> None:
        """Test that compile_pipeline produces correct version artifacts."""
        from floe_core.compilation.stages import compile_pipeline

        result = compile_pipeline(spec_path, manifest_path)

        assert result.version == COMPILED_ARTIFACTS_VERSION

    @pytest.mark.requirement("FR-031")
    def test_compile_pipeline_has_plugins(self, spec_path: Path, manifest_path: Path) -> None:
        """Test that compile_pipeline produces resolved plugins."""
        from floe_core.compilation.stages import compile_pipeline

        result = compile_pipeline(spec_path, manifest_path)

        assert result.plugins.compute.type == "duckdb"
        assert result.plugins.orchestrator.type == "dagster"

    @pytest.mark.requirement("FR-031")
    def test_compile_pipeline_has_transforms(self, tmp_path: Path) -> None:
        """Test that compile_pipeline produces resolved transforms."""
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
    tags: [raw]
  - name: orders
    tags: [staging]
    dependsOn: [customers]
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
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
""")

        result = compile_pipeline(spec_path, manifest_path)

        assert result.transforms is not None
        assert len(result.transforms.models) == 2
        assert result.transforms.models[0].name == "customers"
        assert result.transforms.models[1].name == "orders"

    @pytest.mark.requirement("FR-031")
    def test_compile_pipeline_has_dbt_profiles(self, spec_path: Path, manifest_path: Path) -> None:
        """Test that compile_pipeline generates dbt profiles."""
        from floe_core.compilation.stages import compile_pipeline

        result = compile_pipeline(spec_path, manifest_path)

        assert result.dbt_profiles is not None
        # Profile is named after the product (test-product)
        assert "test-product" in result.dbt_profiles
        assert result.dbt_profiles["test-product"]["target"] == "dev"

    @pytest.mark.requirement("FR-031")
    def test_compile_pipeline_file_not_found(self, tmp_path: Path) -> None:
        """Test that compile_pipeline raises error for missing spec."""
        from floe_core.compilation.errors import CompilationException
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "nonexistent.yaml"
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
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
""")

        with pytest.raises(CompilationException) as exc_info:
            compile_pipeline(spec_path, manifest_path)

        assert exc_info.value.error.code == "E001"

    @pytest.mark.requirement("FR-031")
    def test_compile_pipeline_missing_compute_plugin(self, tmp_path: Path) -> None:
        """Test that compile_pipeline fails without compute plugin."""
        from floe_core.compilation.errors import CompilationException
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
    tags: []
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  orchestrator:
    type: dagster
""")

        with pytest.raises(CompilationException) as exc_info:
            compile_pipeline(spec_path, manifest_path)

        assert exc_info.value.error.code == "E201"
        assert "compute" in exc_info.value.error.message.lower()


class TestEnforcementResult:
    """Tests for enforcement result in compilation pipeline."""

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("FR-031")
    def test_compile_pipeline_produces_enforcement_result(
        self, spec_path: Path, manifest_path: Path
    ) -> None:
        """Test that compile_pipeline produces non-None enforcement_result.

        The ENFORCE stage builds an EnforcementResultSummary from
        pre-manifest policy checks (plugin instrumentation, sink whitelist).
        """
        from floe_core.compilation.stages import compile_pipeline

        result = compile_pipeline(spec_path, manifest_path)

        # W6: Remove redundant `is not None` -- access attributes directly
        assert result.enforcement_result.passed is True
        assert result.enforcement_result.error_count == 0
        assert "plugin_instrumentation" in result.enforcement_result.policy_types_checked
        assert result.enforcement_result.enforcement_level == "warn"

    @pytest.mark.requirement("FR-031")
    def test_enforcement_result_counts_audit_warnings(
        self, spec_path: Path, manifest_path: Path
    ) -> None:
        """Test that enforcement_result warning_count reflects instrumentation audit.

        B2: Monkeypatch _discover_plugins_for_audit with known instrumented/uninstrumented
        plugins, then assert exact warning count == 1.
        """
        from floe_core.compilation import stages as stages_mod
        from floe_core.compilation.stages import compile_pipeline
        from floe_core.plugin_types import PluginType

        instrumented = MagicMock()
        type(instrumented).tracer_name = PropertyMock(return_value="my.tracer")
        uninstrumented = MagicMock()
        type(uninstrumented).tracer_name = PropertyMock(return_value=None)

        with patch.object(
            stages_mod,
            "_discover_plugins_for_audit",
            return_value=[
                (PluginType.COMPUTE, instrumented),
                (PluginType.CATALOG, uninstrumented),
            ],
        ):
            result = compile_pipeline(spec_path, manifest_path)

        assert result.enforcement_result.warning_count == 1


class TestOpenTelemetryTracing:
    """Tests for OpenTelemetry tracing in compilation pipeline (FR-013)."""

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("FR-013")
    def test_compile_pipeline_creates_parent_span(
        self, spec_path: Path, manifest_path: Path
    ) -> None:
        """Test that compile_pipeline creates a parent span for the pipeline."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        from floe_core.telemetry.tracing import set_tracer

        # Set up in-memory span exporter
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        set_tracer(provider.get_tracer("floe_core.telemetry"))

        try:
            compile_pipeline = __import__(
                "floe_core.compilation.stages", fromlist=["compile_pipeline"]
            ).compile_pipeline
            compile_pipeline(spec_path, manifest_path)

            # Get exported spans
            spans = exporter.get_finished_spans()
            span_names = [span.name for span in spans]

            # Verify parent span exists
            assert "compile.pipeline" in span_names

            # Verify all stage spans exist
            assert "compile.load" in span_names
            assert "compile.validate" in span_names
            assert "compile.resolve" in span_names
            assert "compile.enforce" in span_names
            assert "compile.compile" in span_names
            assert "compile.generate" in span_names

        finally:
            # Reset tracer
            set_tracer(None)

    @pytest.mark.requirement("FR-013")
    def test_compile_pipeline_span_attributes(self, spec_path: Path, manifest_path: Path) -> None:
        """Test that compilation spans have correct attributes."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        from floe_core.compilation.stages import compile_pipeline
        from floe_core.telemetry.tracing import set_tracer

        # Set up in-memory span exporter
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        set_tracer(provider.get_tracer("floe_core.telemetry"))

        try:
            compile_pipeline(spec_path, manifest_path)

            spans = exporter.get_finished_spans()

            # Find the pipeline span
            pipeline_span = next((s for s in spans if s.name == "compile.pipeline"), None)
            assert pipeline_span is not None
            assert "compile.product_name" in dict(pipeline_span.attributes)
            assert pipeline_span.attributes["compile.product_name"] == "test-product"

            # Find the resolve span
            resolve_span = next((s for s in spans if s.name == "compile.resolve"), None)
            assert resolve_span is not None
            assert resolve_span.attributes["compile.stage"] == "RESOLVE"
            assert resolve_span.attributes["compile.compute_plugin"] == "duckdb"

        finally:
            set_tracer(None)


class TestTimingLogging:
    """Tests for timing information logging in compilation pipeline (T067)."""

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("SC-001")
    def test_compile_pipeline_logs_duration_ms(
        self,
        spec_path: Path,
        manifest_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that compile_pipeline logs duration_ms for each stage."""
        import structlog

        from floe_core.compilation.stages import compile_pipeline

        # Configure structlog to use standard logging for capture
        structlog.configure(
            processors=[
                structlog.processors.KeyValueRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(0),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Capture stdout where structlog prints
        import io
        import sys

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured

        try:
            compile_pipeline(spec_path, manifest_path)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()

        # Check that duration_ms appears in output for each stage
        assert "duration_ms=" in output
        # Check total compilation time logged
        assert "total_duration_ms=" in output

    @pytest.mark.requirement("SC-001")
    def test_compile_pipeline_logs_total_duration(
        self,
        spec_path: Path,
        manifest_path: Path,
    ) -> None:
        """Test that compile_pipeline logs total compilation duration."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        from floe_core.compilation.stages import compile_pipeline
        from floe_core.telemetry.tracing import set_tracer

        # Set up tracer to capture span attributes
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        set_tracer(provider.get_tracer("floe_core.telemetry"))

        try:
            compile_pipeline(spec_path, manifest_path)

            spans = exporter.get_finished_spans()
            pipeline_span = next((s for s in spans if s.name == "compile.pipeline"), None)

            assert pipeline_span is not None
            # Check that total duration is captured as attribute
            assert "compile.total_duration_ms" in dict(pipeline_span.attributes)
            duration = pipeline_span.attributes["compile.total_duration_ms"]
            assert isinstance(duration, int | float)
            assert duration > 0

        finally:
            set_tracer(None)


class TestGovernanceFlow:
    """Tests for governance wiring from manifest to CompiledArtifacts (AC-9.4).

    Verifies that the compile_pipeline reads governance settings from the
    manifest (not the spec) and populates artifacts.governance with a
    ResolvedGovernance object containing the correct field values.

    Current state: governance is NEVER wired through -- artifacts.governance
    is always None. These tests MUST FAIL before implementation.
    """

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("AC-9.4")
    def test_compile_pipeline_populates_governance_from_demo_manifest(
        self, spec_path: Path
    ) -> None:
        """Test that compile_pipeline populates governance from demo manifest.

        Uses the real demo manifest which has governance section with:
          policy_enforcement_level: warn
          audit_logging: enabled
          data_retention_days: 1

        Asserts exact values match the demo manifest, not vague truthiness.
        Will FAIL because governance is never wired to build_artifacts().
        """
        from floe_core.compilation.stages import compile_pipeline

        # Use the real demo manifest which has a governance section
        demo_manifest_path = (
            Path(__file__).resolve().parents[5] / "demo" / "manifest.yaml"
        )
        assert demo_manifest_path.exists(), (
            f"Demo manifest not found at {demo_manifest_path}"
        )

        result = compile_pipeline(spec_path, demo_manifest_path)

        # AC-9.4: governance MUST be populated when manifest has governance
        assert result.governance is not None, (
            "artifacts.governance is None but manifest has governance section. "
            "Governance must be wired from manifest through build_artifacts()."
        )
        assert result.governance.policy_enforcement_level == "warn"
        assert result.governance.audit_logging == "enabled"
        assert result.governance.data_retention_days == 1

    @pytest.mark.requirement("AC-9.4")
    def test_compile_pipeline_governance_none_without_manifest_governance(
        self, spec_path: Path, manifest_path: Path
    ) -> None:
        """Test that governance is None when manifest has no governance section.

        The minimal manifest fixture (from conftest.py) has no governance
        section. This test ensures backwards compatibility -- governance should
        be None, not an empty object or a default.

        This currently passes (governance is always None) but serves as a
        regression guard against implementations that unconditionally create
        a ResolvedGovernance.
        """
        from floe_core.compilation.stages import compile_pipeline

        result = compile_pipeline(spec_path, manifest_path)

        assert result.governance is None, (
            "artifacts.governance should be None when manifest has no governance section"
        )

    @pytest.mark.requirement("AC-9.4")
    def test_compile_pipeline_governance_maps_pii_encryption(
        self, spec_path: Path, tmp_path: Path
    ) -> None:
        """Test that pii_encryption from manifest maps to artifacts.governance.

        Creates a manifest with pii_encryption='required' and verifies
        the exact value is preserved in the compiled artifacts.
        Will FAIL because governance is never wired.
        """
        from floe_core.compilation.stages import compile_pipeline

        manifest_with_pii = tmp_path / "manifest.yaml"
        manifest_with_pii.write_text(MANIFEST_WITH_GOVERNANCE_YAML)

        result = compile_pipeline(spec_path, manifest_with_pii)

        assert result.governance is not None, (
            "artifacts.governance is None but manifest has governance section"
        )
        assert result.governance.pii_encryption == "required", (
            "pii_encryption must be mapped from manifest governance to artifacts"
        )

    @pytest.mark.requirement("AC-9.4")
    def test_compile_pipeline_governance_maps_all_fields(
        self, spec_path: Path, tmp_path: Path
    ) -> None:
        """Test that ALL four governance fields are wired from manifest.

        Verifies exact values for every ResolvedGovernance field to prevent
        partial implementations that only wire one or two fields.
        Will FAIL because governance is never wired.
        """
        from floe_core.compilation.stages import compile_pipeline

        manifest_with_gov = tmp_path / "manifest.yaml"
        manifest_with_gov.write_text(MANIFEST_WITH_GOVERNANCE_YAML)

        result = compile_pipeline(spec_path, manifest_with_gov)

        assert result.governance is not None, (
            "artifacts.governance is None but manifest has governance section"
        )
        # Verify ALL four fields, not just one
        assert result.governance.policy_enforcement_level == "strict"
        assert result.governance.audit_logging == "enabled"
        assert result.governance.data_retention_days == 30
        assert result.governance.pii_encryption == "required"

    @pytest.mark.requirement("AC-9.4")
    def test_compile_pipeline_governance_partial_fields(
        self, spec_path: Path, tmp_path: Path
    ) -> None:
        """Test governance with only some fields set in manifest.

        When the manifest has governance but only sets policy_enforcement_level
        (not pii_encryption, audit_logging, or data_retention_days), the
        unset fields should be None -- not defaulted to arbitrary values.
        Will FAIL because governance is never wired.
        """
        from floe_core.compilation.stages import compile_pipeline

        manifest_partial_gov = tmp_path / "manifest.yaml"
        manifest_partial_gov.write_text(MANIFEST_WITH_PARTIAL_GOVERNANCE_YAML)

        result = compile_pipeline(spec_path, manifest_partial_gov)

        assert result.governance is not None, (
            "artifacts.governance is None but manifest has governance section"
        )
        # The one field that IS set must be correct
        assert result.governance.policy_enforcement_level == "warn"
        # Fields NOT set in the manifest must be None, not hardcoded defaults
        assert result.governance.pii_encryption is None
        assert result.governance.audit_logging is None
        assert result.governance.data_retention_days is None

"""Unit tests for compilation stages module.

Tests the compile_pipeline orchestrator and CompilationStage enum.

Requirements:
    - FR-031: 6-stage compilation pipeline
    - FR-032: Structured logging for each stage
    - AC-9.4: Governance wiring from manifest to CompiledArtifacts
    - AC-9.5: Enforcement level precedence rule (stricter wins)
    - AC-9.6: Observability wiring from manifest to CompiledArtifacts
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

    @pytest.mark.requirement("AC-18.1")
    def test_compile_pipeline_runs_enforce_stage_with_models(self, tmp_path: Path) -> None:
        """Test that compile_pipeline calls run_enforce_stage() after COMPILE.

        When manifest has governance config and spec has transforms,
        enforcement must validate models (models_validated > 0).
        AC-18.1: compile_pipeline() calls run_enforce_stage() after COMPILE.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""\
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: bronze_customers
    tags: [raw]
  - name: silver_orders
    tags: [staging]
    dependsOn: [bronze_customers]
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""\
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
""")

        result = compile_pipeline(spec_path, manifest_path)

        assert result.enforcement_result.models_validated > 0, (
            f"Expected models_validated > 0, got {result.enforcement_result.models_validated}. "
            "run_enforce_stage() must be called after COMPILE to validate models."
        )
        assert result.enforcement_result.enforcement_level in ("warn", "strict"), (
            "Enforcement level must reflect governance config"
        )

    @pytest.mark.requirement("AC-18.2")
    def test_enforcement_result_has_policy_types_checked(self, tmp_path: Path) -> None:
        """Test that enforcement result has non-empty policy_types_checked.

        AC-18.2: enforcement_result.policy_types_checked is non-empty.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""\
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: bronze_customers
    tags: [raw]
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""\
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
""")

        result = compile_pipeline(spec_path, manifest_path)

        assert len(result.enforcement_result.policy_types_checked) > 0, (
            "policy_types_checked must be non-empty when governance is enabled"
        )

    @pytest.mark.requirement("AC-18.1")
    def test_enforcement_without_governance_keeps_zero_models(
        self, spec_path: Path, manifest_path: Path
    ) -> None:
        """Test that without governance config, models_validated stays 0.

        When manifest has NO governance section, run_enforce_stage() should
        NOT be called and models_validated remains 0.
        """
        from floe_core.compilation.stages import compile_pipeline

        result = compile_pipeline(spec_path, manifest_path)

        assert result.enforcement_result.models_validated == 0, (
            "Without governance config, models_validated should be 0"
        )


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
        demo_manifest_path = Path(__file__).resolve().parents[5] / "demo" / "manifest.yaml"
        assert demo_manifest_path.exists(), f"Demo manifest not found at {demo_manifest_path}"

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


# ==============================================================================
# YAML constants for enforcement level precedence tests (AC-9.5)
# ==============================================================================

MANIFEST_GOVERNANCE_WARN_YAML = """\
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

MANIFEST_GOVERNANCE_STRICT_YAML = """\
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
"""

MANIFEST_NO_GOVERNANCE_YAML = """\
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

SPEC_NO_GOVERNANCE_YAML = """\
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
    tags: []
"""


class TestEnforcementLevelPrecedence:
    """Tests for enforcement level precedence rule (AC-9.5).

    The "stricter wins" rule governs how enforcement levels from manifest
    and spec are combined:
      - Strength ordering: strict > warn > off
      - Manifest is authoritative; spec can only strengthen, never weaken.
      - Default when neither is set: "warn"

    These tests MUST fail before the implementation is added, because the
    current logic (stages.py lines 339-342) reads enforcement_level from
    spec.governance ONLY and completely ignores manifest.governance.

    Key failing test: test 3 (manifest=strict, spec=warn) -- the current
    code would return "warn" because it reads from spec, but the correct
    answer is "strict" because the manifest sets the floor.
    """

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("AC-9.5")
    def test_manifest_warn_spec_none_produces_warn(self, tmp_path: Path) -> None:
        """Test: manifest=warn, spec=None -> enforcement_level="warn".

        When the manifest sets policy_enforcement_level to "warn" and the
        spec has no governance section, the resulting enforcement_level must
        be "warn". The value MUST come from the manifest, not from the
        hardcoded default.

        This test distinguishes between "warn because of manifest" vs
        "warn because of hardcoded default" by also verifying the
        governance object is populated from the manifest.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_NO_GOVERNANCE_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(MANIFEST_GOVERNANCE_WARN_YAML)

        result = compile_pipeline(spec_path, manifest_path)

        # The enforcement_level must be "warn" -- sourced from manifest
        assert result.enforcement_result is not None, "enforcement_result must be populated"
        assert result.enforcement_result.enforcement_level == "warn", (
            "When manifest sets policy_enforcement_level=warn and spec has no "
            "governance, enforcement_level must be 'warn' from the manifest"
        )
        # Also verify that governance was wired from the manifest,
        # proving the value came from manifest, not hardcoded default
        assert result.governance is not None, (
            "governance must be populated from manifest to prove enforcement_level "
            "came from manifest, not hardcoded default"
        )
        assert result.governance.policy_enforcement_level == "warn", (
            "governance.policy_enforcement_level must mirror the manifest value"
        )

    @pytest.mark.requirement("AC-9.5")
    def test_manifest_warn_spec_strict_produces_strict(self, tmp_path: Path) -> None:
        """Test: manifest=warn, spec=strict -> enforcement_level="strict".

        When the manifest sets policy_enforcement_level to "warn" and the
        spec sets enforcement_level to "strict", the result must be "strict"
        because the spec is strengthening (making stricter) the manifest.

        Since FloeSpec currently has extra="forbid" and no governance field,
        this test patches load_floe_spec to simulate a spec with governance.
        The implementation must either add a governance field to FloeSpec or
        handle spec-level enforcement through another mechanism.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_NO_GOVERNANCE_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(MANIFEST_GOVERNANCE_WARN_YAML)

        # Simulate spec.governance.enforcement_level = "strict"
        # by patching the loaded spec to have a governance attribute.
        # Import the real loader BEFORE patching to avoid recursion.
        from floe_core.compilation.loader import load_floe_spec as real_load

        spec_governance = MagicMock()
        spec_governance.enforcement_level = "strict"

        def _patched_load(path: Path) -> Any:
            """Load spec, then attach governance attribute."""
            spec = real_load(path)
            # FloeSpec is frozen, so we use object.__setattr__
            object.__setattr__(spec, "governance", spec_governance)
            return spec

        with patch(
            "floe_core.compilation.loader.load_floe_spec",
            side_effect=_patched_load,
        ):
            result = compile_pipeline(spec_path, manifest_path)

        assert result.enforcement_result is not None, "enforcement_result must be populated"
        assert result.enforcement_result.enforcement_level == "strict", (
            "When manifest=warn and spec=strict, enforcement_level must be "
            "'strict' because spec strengthens (stricter wins rule)"
        )

    @pytest.mark.requirement("AC-9.5")
    def test_manifest_strict_spec_warn_produces_strict(self, tmp_path: Path) -> None:
        """Test: manifest=strict, spec=warn -> enforcement_level="strict".

        When the manifest sets policy_enforcement_level to "strict" and the
        spec tries to weaken it to "warn", the result MUST be "strict"
        because the manifest sets the floor and specs cannot weaken it.

        THIS IS THE KEY FAILING TEST. The current implementation reads
        enforcement_level from spec.governance only and ignores the manifest.
        With spec.governance.enforcement_level="warn", the current code
        returns "warn" instead of the correct "strict".
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_NO_GOVERNANCE_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(MANIFEST_GOVERNANCE_STRICT_YAML)

        # Simulate spec.governance.enforcement_level = "warn"
        # (attempting to weaken the manifest's "strict" to "warn")
        # Import the real loader BEFORE patching to avoid recursion.
        from floe_core.compilation.loader import load_floe_spec as real_load

        spec_governance = MagicMock()
        spec_governance.enforcement_level = "warn"

        def _patched_load(path: Path) -> Any:
            """Load spec, then attach governance attribute."""
            spec = real_load(path)
            object.__setattr__(spec, "governance", spec_governance)
            return spec

        with patch(
            "floe_core.compilation.loader.load_floe_spec",
            side_effect=_patched_load,
        ):
            result = compile_pipeline(spec_path, manifest_path)

        assert result.enforcement_result is not None, "enforcement_result must be populated"
        assert result.enforcement_result.enforcement_level == "strict", (
            "When manifest=strict and spec=warn, enforcement_level must be "
            "'strict' because manifest sets the floor -- spec cannot weaken "
            "the enforcement level (stricter wins rule)"
        )

    @pytest.mark.requirement("AC-9.5")
    def test_manifest_none_spec_none_produces_warn_default(self, tmp_path: Path) -> None:
        """Test: manifest=None, spec=None -> enforcement_level="warn" (default).

        When neither the manifest nor the spec sets a governance section,
        the enforcement_level must default to "warn". This is a regression
        guard to ensure the default is stable.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_NO_GOVERNANCE_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(MANIFEST_NO_GOVERNANCE_YAML)

        result = compile_pipeline(spec_path, manifest_path)

        assert result.enforcement_result is not None, "enforcement_result must be populated"
        assert result.enforcement_result.enforcement_level == "warn", (
            "When neither manifest nor spec has governance, enforcement_level "
            "must default to 'warn'"
        )

    @pytest.mark.requirement("AC-9.5")
    def test_manifest_strict_spec_none_produces_strict(self, tmp_path: Path) -> None:
        """Test: manifest=strict, spec=None -> enforcement_level="strict".

        When the manifest sets policy_enforcement_level to "strict" and the
        spec has no governance section, the result must be "strict" because
        the manifest is authoritative.

        THIS ALSO FAILS with the current implementation because the code
        reads enforcement_level from spec.governance only (which is None here),
        so it falls through to the hardcoded default "warn" instead of using
        the manifest's "strict".
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_NO_GOVERNANCE_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(MANIFEST_GOVERNANCE_STRICT_YAML)

        result = compile_pipeline(spec_path, manifest_path)

        assert result.enforcement_result is not None, "enforcement_result must be populated"
        assert result.enforcement_result.enforcement_level == "strict", (
            "When manifest sets policy_enforcement_level=strict and spec has "
            "no governance, enforcement_level must be 'strict' from the manifest. "
            "Current bug: code ignores manifest.governance and defaults to 'warn'."
        )

    @pytest.mark.requirement("AC-9.5")
    def test_manifest_off_spec_warn_produces_warn(self, tmp_path: Path) -> None:
        """Test: manifest=off, spec=warn -> enforcement_level="warn".

        When the manifest sets enforcement to "off" and the spec
        strengthens it to "warn", the result must be "warn" because
        the spec can only strengthen, and "warn" is stricter than "off".

        Validates the spec-strengthening path works for all levels,
        not just strict. Also guards against implementations that
        only check strict vs warn and forget about the "off" level.
        """
        from floe_core.compilation.stages import compile_pipeline

        manifest_off_yaml = """\
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
  policy_enforcement_level: "off"
"""
        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_NO_GOVERNANCE_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(manifest_off_yaml)

        # Simulate spec.governance.enforcement_level = "warn"
        # Import the real loader BEFORE patching to avoid recursion.
        from floe_core.compilation.loader import load_floe_spec as real_load

        spec_governance = MagicMock()
        spec_governance.enforcement_level = "warn"

        def _patched_load(path: Path) -> Any:
            """Load spec, then attach governance attribute."""
            spec = real_load(path)
            object.__setattr__(spec, "governance", spec_governance)
            return spec

        with patch(
            "floe_core.compilation.loader.load_floe_spec",
            side_effect=_patched_load,
        ):
            result = compile_pipeline(spec_path, manifest_path)

        assert result.enforcement_result is not None, "enforcement_result must be populated"
        assert result.enforcement_result.enforcement_level == "warn", (
            "When manifest=off and spec=warn, enforcement_level must be "
            "'warn' because spec strengthens (stricter wins: warn > off)"
        )

    @pytest.mark.requirement("AC-9.5")
    def test_manifest_strict_spec_off_produces_strict(self, tmp_path: Path) -> None:
        """Test: manifest=strict, spec=off -> enforcement_level="strict".

        When the manifest sets enforcement to "strict" and the spec tries
        to weaken it to "off", the result must be "strict" because the
        manifest sets the floor and spec cannot weaken it.

        This is the extreme weakening case -- from strict all the way down
        to off. Tests that the floor enforcement from the manifest is always
        respected regardless of how much the spec tries to weaken it.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_NO_GOVERNANCE_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(MANIFEST_GOVERNANCE_STRICT_YAML)

        # Simulate spec.governance.enforcement_level = "off"
        # Import the real loader BEFORE patching to avoid recursion.
        from floe_core.compilation.loader import load_floe_spec as real_load

        spec_governance = MagicMock()
        spec_governance.enforcement_level = "off"

        def _patched_load(path: Path) -> Any:
            """Load spec, then attach governance attribute."""
            spec = real_load(path)
            object.__setattr__(spec, "governance", spec_governance)
            return spec

        with patch(
            "floe_core.compilation.loader.load_floe_spec",
            side_effect=_patched_load,
        ):
            result = compile_pipeline(spec_path, manifest_path)

        assert result.enforcement_result is not None, "enforcement_result must be populated"
        assert result.enforcement_result.enforcement_level == "strict", (
            "When manifest=strict and spec=off, enforcement_level must be "
            "'strict' because manifest sets the floor -- spec cannot weaken "
            "enforcement even to 'off' (stricter wins rule)"
        )


# ==============================================================================
# YAML constant for manifests WITHOUT observability section
# ==============================================================================

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

SPEC_MINIMAL_YAML = """\
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
    tags: []
"""


class TestObservabilityFromManifest:
    """Tests for observability wiring from manifest to CompiledArtifacts (AC-9.6).

    Verifies that compile_pipeline reads observability settings from the
    manifest's observability section (tracing endpoint, lineage endpoint,
    lineage transport) instead of hardcoding defaults in builder.py.

    Current state: builder.py (lines 114-129) hardcodes ObservabilityConfig
    with no reference to manifest.observability. These tests MUST FAIL
    before implementation.

    Mapping from manifest to CompiledArtifacts:
        manifest.observability.tracing.endpoint  -> artifacts.observability.telemetry.otlp_endpoint
        manifest.observability.lineage.enabled   -> artifacts.observability.lineage
        manifest.observability.lineage.endpoint  -> artifacts.observability.lineage_endpoint
        manifest.observability.lineage.transport -> artifacts.observability.lineage_transport
        spec.metadata.name -> artifacts.observability.telemetry
                              .resource_attributes.service_name
    """

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("AC-9.6")
    def test_compile_pipeline_reads_tracing_endpoint_from_manifest(self, spec_path: Path) -> None:
        """Test that tracing endpoint comes from manifest, not hardcoded default.

        The demo manifest has observability.tracing.endpoint =
        'http://floe-platform-otel:4317'. The builder currently hardcodes
        TelemetryConfig() which defaults otlp_endpoint to 'http://localhost:4317'.

        This test MUST FAIL because the builder ignores manifest.observability
        and always uses the TelemetryConfig default.
        """
        from floe_core.compilation.stages import compile_pipeline

        demo_manifest_path = Path(__file__).resolve().parents[5] / "demo" / "manifest.yaml"
        assert demo_manifest_path.exists(), f"Demo manifest not found at {demo_manifest_path}"

        result = compile_pipeline(spec_path, demo_manifest_path)

        # AC-9.6: otlp_endpoint MUST come from manifest.observability.tracing.endpoint
        assert result.observability.telemetry.otlp_endpoint == "http://floe-platform-otel:4317", (
            f"Expected otlp_endpoint from manifest "
            f"('http://floe-platform-otel:4317') but got "
            f"'{result.observability.telemetry.otlp_endpoint}'. "
            f"The builder is hardcoding defaults instead of reading "
            f"from manifest.observability.tracing.endpoint."
        )

    @pytest.mark.requirement("AC-9.6")
    def test_compile_pipeline_reads_lineage_endpoint_from_manifest(self, spec_path: Path) -> None:
        """Test that lineage endpoint comes from manifest.

        The demo manifest has observability.lineage.endpoint =
        'http://floe-platform-marquez:5000/api/v1/lineage'.
        The builder currently does not set lineage_endpoint at all
        (it defaults to None on ObservabilityConfig).

        This test MUST FAIL because the builder ignores
        manifest.observability.lineage.endpoint.
        """
        from floe_core.compilation.stages import compile_pipeline

        demo_manifest_path = Path(__file__).resolve().parents[5] / "demo" / "manifest.yaml"
        assert demo_manifest_path.exists(), f"Demo manifest not found at {demo_manifest_path}"

        result = compile_pipeline(spec_path, demo_manifest_path)

        # AC-9.6: lineage_endpoint MUST come from manifest.observability.lineage.endpoint
        assert result.observability.lineage_endpoint == (
            "http://floe-platform-marquez:5000/api/v1/lineage"
        ), (
            f"Expected lineage_endpoint from manifest "
            f"('http://floe-platform-marquez:5000/api/v1/lineage') but got "
            f"'{result.observability.lineage_endpoint}'. "
            f"The builder does not read manifest.observability.lineage.endpoint."
        )

    @pytest.mark.requirement("AC-9.6")
    def test_compile_pipeline_reads_lineage_transport_from_manifest(self, spec_path: Path) -> None:
        """Test that lineage transport comes from manifest.

        The demo manifest has observability.lineage.transport = 'http'.
        The builder currently does not set lineage_transport at all
        (it defaults to None on ObservabilityConfig).

        This test MUST FAIL because the builder ignores
        manifest.observability.lineage.transport.
        """
        from floe_core.compilation.stages import compile_pipeline

        demo_manifest_path = Path(__file__).resolve().parents[5] / "demo" / "manifest.yaml"
        assert demo_manifest_path.exists(), f"Demo manifest not found at {demo_manifest_path}"

        result = compile_pipeline(spec_path, demo_manifest_path)

        # AC-9.6: lineage_transport MUST come from manifest.observability.lineage.transport
        assert result.observability.lineage_transport == "http", (
            f"Expected lineage_transport from manifest ('http') but got "
            f"'{result.observability.lineage_transport}'. "
            f"The builder does not read manifest.observability.lineage.transport."
        )

    @pytest.mark.requirement("AC-9.6")
    def test_compile_pipeline_reads_lineage_enabled_from_manifest(self, spec_path: Path) -> None:
        """Test that lineage enabled comes from manifest.

        The demo manifest has observability.lineage.enabled = true.
        The builder currently hardcodes lineage=True, so this test passes
        as a regression guard. If someone changes the hardcoded default
        to False, this test will catch it.

        This test is a REGRESSION GUARD -- it currently passes because
        the hardcoded value happens to match the manifest value.
        """
        from floe_core.compilation.stages import compile_pipeline

        demo_manifest_path = Path(__file__).resolve().parents[5] / "demo" / "manifest.yaml"
        assert demo_manifest_path.exists(), f"Demo manifest not found at {demo_manifest_path}"

        result = compile_pipeline(spec_path, demo_manifest_path)

        # AC-9.6: lineage MUST be True (from manifest.observability.lineage.enabled)
        assert result.observability.lineage is True, (
            f"Expected lineage=True from manifest but got {result.observability.lineage!r}"
        )

    @pytest.mark.requirement("AC-9.6")
    def test_compile_pipeline_observability_defaults_without_manifest_section(
        self, tmp_path: Path
    ) -> None:
        """Test observability defaults when manifest has no observability section.

        When the manifest does not include an observability section, the
        builder should use sensible defaults:
          - otlp_endpoint: 'http://localhost:4317' (TelemetryConfig default)
          - lineage: True (ObservabilityConfig default)
          - lineage_endpoint: None (no endpoint configured)
          - lineage_transport: None (no transport configured)

        This test verifies the fallback path. It MUST FAIL because the
        current builder does not distinguish between "manifest has
        observability" and "manifest lacks observability" -- it hardcodes
        everything, so there is no code path that reads the manifest and
        falls back to defaults.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_MINIMAL_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(MANIFEST_NO_OBSERVABILITY_YAML)

        result = compile_pipeline(spec_path, manifest_path)

        # Without manifest observability, otlp_endpoint should be the default
        assert result.observability.telemetry.otlp_endpoint == "http://localhost:4317", (
            f"Without manifest observability section, otlp_endpoint should "
            f"default to 'http://localhost:4317' but got "
            f"'{result.observability.telemetry.otlp_endpoint}'"
        )
        # Without manifest observability, lineage_endpoint should be None
        assert result.observability.lineage_endpoint is None, (
            f"Without manifest observability section, lineage_endpoint should "
            f"be None but got '{result.observability.lineage_endpoint}'"
        )
        # Without manifest observability, lineage_transport should be None
        assert result.observability.lineage_transport is None, (
            f"Without manifest observability section, lineage_transport should "
            f"be None but got '{result.observability.lineage_transport}'"
        )
        # Without manifest observability, lineage should default to True
        assert result.observability.lineage is True, (
            f"Without manifest observability section, lineage should "
            f"default to True but got {result.observability.lineage!r}"
        )

    @pytest.mark.requirement("AC-9.6")
    def test_compile_pipeline_service_name_from_spec_not_manifest(self, spec_path: Path) -> None:
        """Test that service_name always comes from spec, not manifest.

        The resource_attributes.service_name must be populated from
        spec.metadata.name (the data product name), NOT from the manifest.
        This ensures each data product is identified by its own name
        in telemetry regardless of which platform manifest it uses.

        This is a REGRESSION GUARD -- currently passes because the builder
        correctly reads service_name from spec.metadata.name.
        """
        from floe_core.compilation.stages import compile_pipeline

        demo_manifest_path = Path(__file__).resolve().parents[5] / "demo" / "manifest.yaml"
        assert demo_manifest_path.exists(), f"Demo manifest not found at {demo_manifest_path}"

        result = compile_pipeline(spec_path, demo_manifest_path)

        # AC-9.6: service_name must come from spec.metadata.name, not manifest
        assert result.observability.telemetry.resource_attributes.service_name == "test-product", (
            f"Expected service_name from spec.metadata.name ('test-product') "
            f"but got "
            f"'{result.observability.telemetry.resource_attributes.service_name}'. "
            f"service_name must always come from the spec, not the manifest."
        )

    @pytest.mark.requirement("AC-9.6")
    def test_compile_pipeline_tracing_endpoint_not_hardcoded(self, tmp_path: Path) -> None:
        """Test that different manifest endpoints produce different artifact endpoints.

        This test uses a custom manifest with a UNIQUE tracing endpoint to
        ensure the builder actually reads the manifest rather than returning
        a hardcoded value. If the builder hardcodes any specific endpoint,
        this test will catch it because the custom endpoint is deliberately
        different from both the demo manifest and the default.

        This test MUST FAIL because the builder hardcodes observability.
        """
        from floe_core.compilation.stages import compile_pipeline

        custom_endpoint = "http://my-custom-otel-collector:4317"
        custom_lineage_endpoint = "http://my-custom-marquez:5000/api/v1/lineage"

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_MINIMAL_YAML)

        manifest_with_custom_otel = tmp_path / "manifest.yaml"
        manifest_with_custom_otel.write_text(f"""\
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
  tracing:
    enabled: true
    exporter: otlp
    endpoint: {custom_endpoint}
  lineage:
    enabled: true
    transport: http
    endpoint: {custom_lineage_endpoint}
""")

        result = compile_pipeline(spec_path, manifest_with_custom_otel)

        # Verify the custom endpoint is used -- not the default, not the demo value
        assert result.observability.telemetry.otlp_endpoint == custom_endpoint, (
            f"Expected custom otlp_endpoint '{custom_endpoint}' from manifest "
            f"but got '{result.observability.telemetry.otlp_endpoint}'. "
            f"The builder must read the endpoint from manifest.observability."
        )
        assert result.observability.lineage_endpoint == custom_lineage_endpoint, (
            f"Expected custom lineage_endpoint '{custom_lineage_endpoint}' "
            f"from manifest but got '{result.observability.lineage_endpoint}'. "
            f"The builder must read lineage_endpoint from manifest.observability."
        )


# ==============================================================================
# Boundary condition tests for governance + observability flow (BC-9.x)
# ==============================================================================

# YAML constants for boundary condition tests

MANIFEST_EMPTY_OBSERVABILITY_YAML = """\
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
observability: {}
"""

MANIFEST_GOVERNANCE_NO_ENFORCEMENT_YAML = """\
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
  pii_encryption: required
  audit_logging: enabled
"""

MANIFEST_GOVERNANCE_NO_RETENTION_YAML = """\
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
  pii_encryption: optional
"""


class TestBoundaryConditions:
    """Boundary condition tests for governance+observability flow (BC-9.x).

    These tests validate that edge cases in manifest configuration produce
    correct CompiledArtifacts when passed through compile_pipeline. They
    target specific boundary conditions where defaults, missing sections,
    and partial configurations must be handled correctly.

    Each test writes custom YAML manifests to tmp_path and runs the full
    compile_pipeline, asserting exact field values -- not vague truthiness.
    """

    @pytest.fixture(autouse=True)
    def _apply_mocks(self, patch_version_compat: Any, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for compilation tests."""

    @pytest.mark.requirement("BC-9.1")
    def test_empty_observability_section_uses_defaults(self, tmp_path: Path) -> None:
        """Test that observability: {} uses all defaults correctly.

        When the manifest has an empty observability section (observability: {}),
        ObservabilityManifestConfig is instantiated with default_factory sub-sections.
        The builder sees manifest_obs is not None, so it reads from the defaults:
          - tracing.endpoint is None -> otlp_endpoint stays at TelemetryConfig default
          - lineage.enabled is True -> lineage = True
          - lineage.endpoint is None -> lineage_endpoint = None
          - lineage.transport is "http" -> lineage_transport = "http"
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_MINIMAL_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(MANIFEST_EMPTY_OBSERVABILITY_YAML)

        result = compile_pipeline(spec_path, manifest_path)

        # otlp_endpoint must be the TelemetryConfig default since
        # TracingManifestConfig().endpoint is None
        assert result.observability.telemetry.otlp_endpoint == "http://localhost:4317", (
            f"With observability: {{}}, otlp_endpoint should be TelemetryConfig default "
            f"'http://localhost:4317' but got "
            f"'{result.observability.telemetry.otlp_endpoint}'"
        )

        # lineage must be True from LineageManifestConfig default
        assert result.observability.lineage is True, (
            f"With observability: {{}}, lineage should be True "
            f"(LineageManifestConfig.enabled default) but got "
            f"{result.observability.lineage!r}"
        )

        # lineage_endpoint must be None since LineageManifestConfig().endpoint is None
        assert result.observability.lineage_endpoint is None, (
            f"With observability: {{}}, lineage_endpoint should be None "
            f"(no endpoint configured) but got "
            f"'{result.observability.lineage_endpoint}'"
        )

        # lineage_transport should be "http" from LineageManifestConfig default
        # (the builder sets lineage_transport from manifest_obs.lineage.transport
        # when manifest_obs is not None)
        assert result.observability.lineage_transport == "http", (
            f"With observability: {{}}, lineage_transport should be 'http' "
            f"(LineageManifestConfig.transport default) but got "
            f"'{result.observability.lineage_transport}'"
        )

    @pytest.mark.requirement("BC-9.2")
    def test_partial_observability_tracing_only(self, tmp_path: Path) -> None:
        """Test that partial observability with only tracing endpoint works.

        When the manifest specifies only a tracing endpoint and nothing else,
        the tracing endpoint flows through to artifacts while lineage fields
        use their defaults from LineageManifestConfig.
        """
        from floe_core.compilation.stages import compile_pipeline

        custom_tracing_endpoint = "http://custom-otel-collector:4317"

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_MINIMAL_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(f"""\
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
  tracing:
    endpoint: {custom_tracing_endpoint}
""")

        result = compile_pipeline(spec_path, manifest_path)

        # The custom tracing endpoint must flow through
        assert result.observability.telemetry.otlp_endpoint == custom_tracing_endpoint, (
            f"Custom tracing endpoint '{custom_tracing_endpoint}' should flow "
            f"through to otlp_endpoint but got "
            f"'{result.observability.telemetry.otlp_endpoint}'"
        )

        # Lineage fields must use defaults since only tracing was specified
        assert result.observability.lineage is True, (
            f"Lineage should default to True when not specified, "
            f"got {result.observability.lineage!r}"
        )
        assert result.observability.lineage_endpoint is None, (
            f"lineage_endpoint should be None when not specified, "
            f"got '{result.observability.lineage_endpoint}'"
        )
        # lineage_transport comes from LineageManifestConfig default ("http")
        assert result.observability.lineage_transport == "http", (
            f"lineage_transport should be 'http' (default) when not specified, "
            f"got '{result.observability.lineage_transport}'"
        )

    @pytest.mark.requirement("BC-9.3")
    def test_governance_without_enforcement_level(self, tmp_path: Path) -> None:
        """Test governance without policy_enforcement_level produces None.

        When the manifest has governance with pii_encryption and audit_logging
        but no policy_enforcement_level, the ResolvedGovernance must have
        policy_enforcement_level=None -- not a hardcoded default.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_MINIMAL_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(MANIFEST_GOVERNANCE_NO_ENFORCEMENT_YAML)

        result = compile_pipeline(spec_path, manifest_path)

        # governance MUST be populated since manifest has a governance section
        assert result.governance is not None, (
            "artifacts.governance must be populated when manifest has governance section"
        )

        # policy_enforcement_level must be None -- it was not specified
        assert result.governance.policy_enforcement_level is None, (
            f"policy_enforcement_level should be None when not specified in "
            f"manifest, but got '{result.governance.policy_enforcement_level}'"
        )

        # Other governance fields that WERE specified must be correct
        assert result.governance.pii_encryption == "required", (
            f"pii_encryption should be 'required' from manifest but got "
            f"'{result.governance.pii_encryption}'"
        )
        assert result.governance.audit_logging == "enabled", (
            f"audit_logging should be 'enabled' from manifest but got "
            f"'{result.governance.audit_logging}'"
        )

        # data_retention_days was not specified, must be None
        assert result.governance.data_retention_days is None, (
            f"data_retention_days should be None when not specified, "
            f"got {result.governance.data_retention_days!r}"
        )

    @pytest.mark.requirement("BC-9.3")
    def test_governance_without_data_retention_days(self, tmp_path: Path) -> None:
        """Test governance without data_retention_days produces None.

        When the manifest has governance with policy_enforcement_level and
        pii_encryption but no data_retention_days, the ResolvedGovernance
        must have data_retention_days=None.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_MINIMAL_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(MANIFEST_GOVERNANCE_NO_RETENTION_YAML)

        result = compile_pipeline(spec_path, manifest_path)

        # governance MUST be populated since manifest has a governance section
        assert result.governance is not None, (
            "artifacts.governance must be populated when manifest has governance section"
        )

        # data_retention_days must be None -- it was not specified
        assert result.governance.data_retention_days is None, (
            f"data_retention_days should be None when not specified in "
            f"manifest, but got {result.governance.data_retention_days!r}"
        )

        # Fields that WERE specified must be correct
        assert result.governance.policy_enforcement_level == "warn", (
            f"policy_enforcement_level should be 'warn' from manifest but got "
            f"'{result.governance.policy_enforcement_level}'"
        )
        assert result.governance.pii_encryption == "optional", (
            f"pii_encryption should be 'optional' from manifest but got "
            f"'{result.governance.pii_encryption}'"
        )

        # audit_logging was not specified, must be None
        assert result.governance.audit_logging is None, (
            f"audit_logging should be None when not specified, "
            f"got '{result.governance.audit_logging}'"
        )

    @pytest.mark.requirement("BC-9.2")
    def test_lineage_disabled_in_manifest(self, tmp_path: Path) -> None:
        """Test that lineage.enabled: false in manifest produces lineage=False.

        When the manifest explicitly disables lineage, the artifact must
        reflect lineage=False, not the ObservabilityConfig default of True.
        This verifies the builder reads the manifest value, not a hardcoded
        default.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(SPEC_MINIMAL_YAML)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""\
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
""")

        result = compile_pipeline(spec_path, manifest_path)

        # lineage must be False because manifest explicitly disabled it
        assert result.observability.lineage is False, (
            f"lineage should be False when manifest sets lineage.enabled=false, "
            f"but got {result.observability.lineage!r}. "
            f"The builder must read lineage from manifest, not use a hardcoded default."
        )

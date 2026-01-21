"""Unit tests for compilation stages module.

Tests the compile_pipeline orchestrator and CompilationStage enum.

Requirements:
    - FR-031: 6-stage compilation pipeline
    - FR-032: Structured logging for each stage
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    pass


@pytest.fixture(autouse=True)
def patch_version_compat() -> Any:
    """Patch version compatibility to allow DuckDB plugin (1.0) with platform (0.1)."""
    with patch("floe_core.plugin_registry.is_compatible", return_value=True):
        yield


@pytest.fixture(autouse=True)
def mock_compute_plugin() -> Any:
    """Mock get_compute_plugin to return a plugin with no config schema (like DuckDB).

    This allows unit tests to run without the actual DuckDB plugin installed.
    The mock plugin returns None for get_config_schema(), simulating DuckDB's
    behavior of requiring no credentials.
    """
    from unittest.mock import MagicMock

    mock_plugin = MagicMock()
    mock_plugin.get_config_schema.return_value = None  # DuckDB has no required config
    mock_plugin.generate_dbt_profile.return_value = {
        "type": "duckdb",
        "path": ":memory:",
    }

    with patch(
        "floe_core.compilation.dbt_profiles.get_compute_plugin",
        return_value=mock_plugin,
    ):
        yield


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
        """Test that all stages have descriptions."""
        from floe_core.compilation.stages import CompilationStage

        for stage in CompilationStage:
            assert isinstance(stage.description, str)
            assert len(stage.description) > 0

    @pytest.mark.requirement("FR-031")
    def test_all_six_stages_exist(self) -> None:
        """Test that all 6 compilation stages exist."""
        from floe_core.compilation.stages import CompilationStage

        expected = {"LOAD", "VALIDATE", "RESOLVE", "ENFORCE", "COMPILE", "GENERATE"}
        actual = {stage.value for stage in CompilationStage}
        assert actual == expected


class TestCompilePipeline:
    """Tests for compile_pipeline orchestrator function."""

    @pytest.mark.requirement("FR-031")
    def test_compile_pipeline_returns_compiled_artifacts(self, tmp_path: Path) -> None:
        """Test that compile_pipeline returns CompiledArtifacts."""
        from floe_core.compilation.stages import compile_pipeline
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Create minimal valid spec
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

        # Create minimal valid manifest
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

        assert isinstance(result, CompiledArtifacts)

    @pytest.mark.requirement("FR-031")
    def test_compile_pipeline_version(self, tmp_path: Path) -> None:
        """Test that compile_pipeline produces version 0.2.0 artifacts."""
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
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

        result = compile_pipeline(spec_path, manifest_path)

        assert result.version == "0.3.0"

    @pytest.mark.requirement("FR-031")
    def test_compile_pipeline_has_plugins(self, tmp_path: Path) -> None:
        """Test that compile_pipeline produces resolved plugins."""
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
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

        result = compile_pipeline(spec_path, manifest_path)

        assert result.plugins is not None
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
    def test_compile_pipeline_has_dbt_profiles(self, tmp_path: Path) -> None:
        """Test that compile_pipeline generates dbt profiles."""
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
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

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


class TestOpenTelemetryTracing:
    """Tests for OpenTelemetry tracing in compilation pipeline (FR-013)."""

    @pytest.mark.requirement("FR-013")
    def test_compile_pipeline_creates_parent_span(self, tmp_path: Path) -> None:
        """Test that compile_pipeline creates a parent span for the pipeline."""
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
            # Create minimal valid spec
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
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

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
    def test_compile_pipeline_span_attributes(self, tmp_path: Path) -> None:
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
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

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

    @pytest.mark.requirement("SC-001")
    def test_compile_pipeline_logs_duration_ms(
        self,
        tmp_path: Path,
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
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

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
        tmp_path: Path,
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
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

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

"""Unit tests for compilation stages module.

Tests the compile_pipeline orchestrator and CompilationStage enum.

Requirements:
    - FR-031: 6-stage compilation pipeline
    - FR-032: Structured logging for each stage
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


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
    def test_compile_pipeline_returns_compiled_artifacts(
        self, tmp_path: Path
    ) -> None:
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

        assert result.version == "0.2.0"

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
        assert "default" in result.dbt_profiles
        assert result.dbt_profiles["default"]["target"] == "dev"

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
    def test_compile_pipeline_missing_compute_plugin(
        self, tmp_path: Path
    ) -> None:
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

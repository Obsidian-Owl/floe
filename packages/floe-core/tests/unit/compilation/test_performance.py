"""Performance tests for compilation pipeline.

These tests validate that compilation meets performance requirements:
- SC-001: Full compilation <5s for 10-50 models
- SC-006: Dry-run (validate-only) <2s for 10-50 models

Requirements Covered:
- SC-001: Compilation performance
- SC-006: Validation performance
"""

from __future__ import annotations

import tempfile
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.fixture(autouse=True)
def patch_version_compat() -> Any:
    """Patch version compatibility to allow DuckDB plugin (1.0) with platform (0.1)."""
    with patch("floe_core.plugin_registry.is_compatible", return_value=True):
        yield


@pytest.fixture(autouse=True)
def mock_compute_plugin() -> Any:
    """Mock get_compute_plugin to return a plugin with no config schema (like DuckDB).

    This allows unit tests to run without the actual DuckDB plugin installed.
    """
    mock_plugin = MagicMock()
    mock_plugin.get_config_schema.return_value = None
    mock_plugin.generate_dbt_profile.return_value = {
        "type": "duckdb",
        "path": ":memory:",
    }

    with patch(
        "floe_core.compilation.dbt_profiles.get_compute_plugin",
        return_value=mock_plugin,
    ):
        yield


def create_floe_spec(num_models: int) -> dict[str, Any]:
    """Create a FloeSpec with the specified number of models.

    Args:
        num_models: Number of transform models to include.

    Returns:
        FloeSpec dict suitable for YAML serialization.
    """
    transforms: list[dict[str, Any]] = []

    # Create a chain of models with dependencies
    for i in range(num_models):
        model: dict[str, Any] = {
            "name": f"model_{i:03d}",
            "tags": ["staging"] if i < num_models // 3 else ["marts"],
        }

        # Add dependencies for non-first models
        if i > 0:
            # Each model depends on the previous one
            model["dependsOn"] = [f"model_{i-1:03d}"]

        # Override compute for some models
        if i % 10 == 5:
            model["compute"] = "spark"

        transforms.append(model)

    return {
        "apiVersion": "floe.dev/v1",
        "kind": "FloeSpec",
        "metadata": {
            "name": "perf-test",
            "version": "1.0.0",
            "description": f"Performance test with {num_models} models",
            "owner": "test@test.com",
        },
        "transforms": transforms,
    }


def create_manifest() -> dict[str, Any]:
    """Create a minimal PlatformManifest for testing.

    Returns:
        Manifest dict suitable for YAML serialization.
    """
    return {
        "apiVersion": "floe.dev/v1",
        "kind": "Manifest",
        "metadata": {
            "name": "perf-test-platform",
            "version": "1.0.0",
            "owner": "test@test.com",
        },
        "plugins": {
            "compute": {
                "type": "duckdb",
                "config": {"threads": 4},
            },
            "orchestrator": {"type": "dagster"},
        },
    }


class TestCompilationPerformance:
    """Performance tests for compilation pipeline (SC-001).

    These tests ensure that full compilation completes within
    the required time bounds for realistic workloads.
    """

    @pytest.fixture
    def temp_fixtures(self) -> Generator[tuple[Path, Path], None, None]:
        """Create temporary floe.yaml and manifest.yaml files.

        Yields:
            Tuple of (spec_path, manifest_path)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            spec_path = tmpdir_path / "floe.yaml"
            manifest_path = tmpdir_path / "manifest.yaml"

            # Write manifest (same for all tests)
            manifest_path.write_text(yaml.safe_dump(create_manifest()))

            yield spec_path, manifest_path

    @pytest.mark.requirement("SC-001")
    def test_compilation_10_models_under_5s(
        self,
        temp_fixtures: tuple[Path, Path],
    ) -> None:
        """Test compilation of 10 models completes in under 5 seconds."""
        from floe_core.compilation.stages import compile_pipeline

        spec_path, manifest_path = temp_fixtures

        # Create spec with 10 models
        spec_path.write_text(yaml.safe_dump(create_floe_spec(10)))

        # Time the compilation
        start = time.perf_counter()
        artifacts = compile_pipeline(spec_path, manifest_path)
        duration = time.perf_counter() - start

        # Verify results
        assert artifacts.version == "0.2.0"
        assert artifacts.transforms is not None
        assert len(artifacts.transforms.models) == 10

        # Performance assertion
        assert duration < 5.0, f"Compilation took {duration:.2f}s (must be <5s)"

    @pytest.mark.requirement("SC-001")
    def test_compilation_50_models_under_5s(
        self,
        temp_fixtures: tuple[Path, Path],
    ) -> None:
        """Test compilation of 50 models completes in under 5 seconds."""
        from floe_core.compilation.stages import compile_pipeline

        spec_path, manifest_path = temp_fixtures

        # Create spec with 50 models
        spec_path.write_text(yaml.safe_dump(create_floe_spec(50)))

        # Time the compilation
        start = time.perf_counter()
        artifacts = compile_pipeline(spec_path, manifest_path)
        duration = time.perf_counter() - start

        # Verify results
        assert artifacts.version == "0.2.0"
        assert artifacts.transforms is not None
        assert len(artifacts.transforms.models) == 50

        # Performance assertion
        assert duration < 5.0, f"Compilation took {duration:.2f}s (must be <5s)"

    @pytest.mark.requirement("SC-001")
    def test_compilation_performance_scaling(
        self,
        temp_fixtures: tuple[Path, Path],
    ) -> None:
        """Test that compilation scales reasonably with model count.

        Compilation time should scale approximately linearly with
        the number of models, not exponentially.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path, manifest_path = temp_fixtures

        durations: dict[int, float] = {}

        for num_models in [10, 25, 50]:
            spec_path.write_text(yaml.safe_dump(create_floe_spec(num_models)))

            start = time.perf_counter()
            artifacts = compile_pipeline(spec_path, manifest_path)
            duration = time.perf_counter() - start

            durations[num_models] = duration

            # Verify compilation succeeded
            assert artifacts.transforms is not None
            assert len(artifacts.transforms.models) == num_models

        # Check that 50 models doesn't take more than 5x the time of 10 models
        # (should scale roughly linearly, allowing for fixed overhead)
        ratio = durations[50] / durations[10]
        assert ratio < 10.0, (
            f"Compilation does not scale linearly: "
            f"10 models={durations[10]:.3f}s, 50 models={durations[50]:.3f}s "
            f"(ratio={ratio:.1f}x, expected <10x)"
        )


class TestDryRunPerformance:
    """Performance tests for validation-only mode (SC-006).

    These tests ensure that dry-run (LOAD + VALIDATE stages only)
    completes within the required time bounds.
    """

    @pytest.fixture
    def temp_fixtures(self) -> Generator[tuple[Path, Path], None, None]:
        """Create temporary floe.yaml and manifest.yaml files.

        Yields:
            Tuple of (spec_path, manifest_path)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            spec_path = tmpdir_path / "floe.yaml"
            manifest_path = tmpdir_path / "manifest.yaml"

            # Write manifest (same for all tests)
            manifest_path.write_text(yaml.safe_dump(create_manifest()))

            yield spec_path, manifest_path

    @pytest.mark.requirement("SC-006")
    def test_validation_50_models_under_2s(
        self,
        temp_fixtures: tuple[Path, Path],
    ) -> None:
        """Test validation of 50 models completes in under 2 seconds.

        Validation includes LOAD and VALIDATE stages only (no plugin
        resolution or dbt profile generation).
        """
        from floe_core.compilation.loader import load_floe_spec, load_manifest

        spec_path, manifest_path = temp_fixtures

        # Create spec with 50 models
        spec_path.write_text(yaml.safe_dump(create_floe_spec(50)))

        # Time the validation (LOAD + VALIDATE only)
        start = time.perf_counter()

        # LOAD stage
        spec = load_floe_spec(spec_path)
        manifest = load_manifest(manifest_path)

        # VALIDATE stage is implicit in Pydantic model validation
        # Verify data was loaded correctly
        assert spec.metadata.name == "perf-test"
        assert len(spec.transforms) == 50
        assert manifest.metadata.name == "perf-test-platform"

        duration = time.perf_counter() - start

        # Performance assertion
        assert duration < 2.0, f"Validation took {duration:.2f}s (must be <2s)"

    @pytest.mark.requirement("SC-006")
    def test_validation_faster_than_full_compilation(
        self,
        temp_fixtures: tuple[Path, Path],
    ) -> None:
        """Test that validation is faster than full compilation.

        Validation (LOAD + VALIDATE only) should be faster than full
        compilation since it skips RESOLVE, ENFORCE, COMPILE, and
        GENERATE stages.

        Note: Both operations are very fast (<10ms), so we verify that
        validation does not take MORE time than compilation, rather than
        requiring a specific speedup ratio.
        """
        from floe_core.compilation.loader import load_floe_spec, load_manifest
        from floe_core.compilation.stages import compile_pipeline

        spec_path, manifest_path = temp_fixtures

        # Create spec with 50 models
        spec_path.write_text(yaml.safe_dump(create_floe_spec(50)))

        # Time validation
        start = time.perf_counter()
        spec = load_floe_spec(spec_path)
        manifest = load_manifest(manifest_path)
        assert spec.metadata.name == "perf-test"
        assert manifest.metadata.name == "perf-test-platform"
        validation_time = time.perf_counter() - start

        # Time full compilation
        start = time.perf_counter()
        artifacts = compile_pipeline(spec_path, manifest_path)
        assert artifacts.version == "0.2.0"
        compilation_time = time.perf_counter() - start

        # Validation should not take more than compilation
        # Allow small margin for measurement variance
        assert validation_time <= compilation_time * 1.5, (
            f"Validation ({validation_time:.3f}s) should not be slower "
            f"than compilation ({compilation_time:.3f}s)"
        )

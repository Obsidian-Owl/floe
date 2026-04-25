"""Dagster orchestrator plugin performance benchmarks.

Measures critical performance characteristics of DagsterOrchestratorPlugin:
- NFR-001: Plugin load time <500ms
- NFR-002: Definition generation <5s for 500 transforms

These benchmarks track plugin performance for platform boot time and
data engineer productivity during pipeline iteration.

Run with:
    uv run pytest benchmarks/test_dagster_plugin_perf.py --codspeed
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


def _manifest_for_artifacts(artifacts: dict[str, Any]) -> dict[str, Any]:
    """Create a dbt manifest with one model node per compiled transform."""
    package_name = "benchmark_pipeline"
    models = artifacts["transforms"]["models"]
    model_ids = {model["name"]: f"model.{package_name}.{model['name']}" for model in models}
    nodes = {}
    parent_map = {}
    child_map = {unique_id: [] for unique_id in model_ids.values()}

    for model in models:
        name = model["name"]
        unique_id = model_ids[name]
        parent_ids = [
            model_ids[parent_name]
            for parent_name in model.get("depends_on", [])
            if parent_name in model_ids
        ]
        nodes[unique_id] = {
            "resource_type": "model",
            "unique_id": unique_id,
            "package_name": package_name,
            "name": name,
            "alias": name,
            "database": "benchmark",
            "schema": "main",
            "relation_name": f"benchmark.main.{name}",
            "path": f"models/{name}.sql",
            "original_file_path": f"models/{name}.sql",
            "fqn": [package_name, name],
            "tags": model.get("tags", []),
            "depends_on": {"nodes": parent_ids, "macros": []},
            "config": {"materialized": "view"},
        }
        parent_map[unique_id] = parent_ids
        for parent_id in parent_ids:
            child_map[parent_id].append(unique_id)

    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json",
            "dbt_version": "1.7.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "invocation_id": "benchmark-invocation",
        },
        "nodes": nodes,
        "sources": {},
        "exposures": {},
        "metrics": {},
        "groups": {},
        "selectors": {},
        "disabled": [],
        "parent_map": parent_map,
        "child_map": child_map,
        "group_map": {},
        "semantic_models": {},
        "unit_tests": {},
        "saved_queries": {},
    }


def _write_runtime_project(tmp_path: Path, artifacts: dict[str, Any]) -> Path:
    """Write compiled artifacts and manifest for runtime loader benchmarks."""
    project_dir = tmp_path / "benchmark_project"
    target_dir = project_dir / "target"
    target_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "compiled_artifacts.json").write_text(json.dumps(artifacts))
    (target_dir / "manifest.json").write_text(json.dumps(_manifest_for_artifacts(artifacts)))
    return project_dir


def _create_minimal_artifacts() -> dict[str, Any]:
    """Create minimal valid CompiledArtifacts for benchmarking."""
    return {
        "version": "0.2.0",
        "metadata": {
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "floe_version": "0.2.0",
            "source_hash": "sha256:benchmark123",
            "product_name": "benchmark-pipeline",
            "product_version": "1.0.0",
        },
        "identity": {
            "product_id": "default.benchmark_pipeline",
            "domain": "default",
            "repository": "github.com/test/benchmark-pipeline",
        },
        "mode": "simple",
        "observability": {
            "telemetry": {
                "enabled": False,
                "resource_attributes": {
                    "service_name": "benchmark-pipeline",
                    "service_version": "1.0.0",
                    "deployment_environment": "dev",
                    "floe_namespace": "default",
                    "floe_product_name": "benchmark-pipeline",
                    "floe_product_version": "1.0.0",
                    "floe_mode": "dev",
                },
            },
            "lineage": False,
            "lineage_namespace": "benchmark-pipeline",
        },
        "plugins": {
            "compute": {"type": "duckdb", "version": "0.9.0"},
            "orchestrator": {"type": "dagster", "version": "1.5.0"},
        },
        "transforms": {
            "models": [
                {"name": "stg_customers", "compute": "duckdb"},
            ],
            "default_compute": "duckdb",
        },
    }


def _create_artifacts_with_transforms(num_transforms: int) -> dict[str, Any]:
    """Create CompiledArtifacts with specified number of transforms.

    Creates a chain of dependent transforms to simulate realistic
    pipeline graphs.

    Args:
        num_transforms: Number of transform models to create.

    Returns:
        CompiledArtifacts dict with num_transforms models.
    """
    models = []
    for i in range(num_transforms):
        model: dict[str, Any] = {
            "name": f"model_{i:04d}",
            "compute": "duckdb",
            "tags": ["benchmark", f"batch_{i // 50}"],
        }
        # Create dependencies on previous models (chain structure)
        if i > 0:
            model["depends_on"] = [f"model_{i - 1:04d}"]
        models.append(model)

    artifacts = _create_minimal_artifacts()
    artifacts["transforms"]["models"] = models
    return artifacts


def _create_transform_configs(num_transforms: int) -> list[Any]:
    """Create list of TransformConfigs for asset creation benchmarking.

    Args:
        num_transforms: Number of TransformConfigs to create.

    Returns:
        List of TransformConfig instances.
    """
    from floe_core.plugins.orchestrator import TransformConfig

    transforms = []
    for i in range(num_transforms):
        depends_on = [f"model_{i - 1:04d}"] if i > 0 else []
        transform = TransformConfig(
            name=f"model_{i:04d}",
            path=f"models/staging/model_{i:04d}.sql",
            schema_name="staging",
            materialization="view",
            tags=["benchmark", f"batch_{i // 50}"],
            depends_on=depends_on,
            compute="duckdb",
        )
        transforms.append(transform)
    return transforms


# =============================================================================
# NFR-001: Plugin Load Time <500ms
# =============================================================================


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-001")
def test_plugin_import_time() -> None:
    """Benchmark plugin import overhead.

    NFR-001 Target: Plugin should load in <500ms.
    Measures import time for the plugin module.
    """
    # Force reimport by removing from cache
    import sys

    module_name = "floe_orchestrator_dagster"
    if module_name in sys.modules:
        del sys.modules[module_name]

    # Benchmark the import
    import floe_orchestrator_dagster  # noqa: F401


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-001")
def test_plugin_instantiation() -> None:
    """Benchmark plugin instantiation overhead.

    NFR-001 Target: Plugin should instantiate quickly as part of load.
    Measures time to create a new plugin instance.
    """
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    _ = DagsterOrchestratorPlugin()


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-001")
def test_plugin_instantiation_repeated() -> None:
    """Benchmark repeated plugin instantiation.

    Measures if there's caching or state accumulation affecting
    subsequent instantiations.
    """
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    for _ in range(10):
        _ = DagsterOrchestratorPlugin()


# =============================================================================
# NFR-002: Runtime Definition Generation <5s for 500 Transforms
# =============================================================================


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-002")
def test_load_product_definitions_small(tmp_path: Path) -> None:
    """Benchmark runtime definition generation with a small pipeline."""
    from floe_orchestrator_dagster.loader import load_product_definitions

    artifacts = _create_artifacts_with_transforms(10)
    project_dir = _write_runtime_project(tmp_path, artifacts)

    _ = load_product_definitions("benchmark-pipeline", project_dir)


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-002")
def test_load_product_definitions_medium(tmp_path: Path) -> None:
    """Benchmark runtime definition generation with a medium pipeline."""
    from floe_orchestrator_dagster.loader import load_product_definitions

    artifacts = _create_artifacts_with_transforms(100)
    project_dir = _write_runtime_project(tmp_path, artifacts)

    _ = load_product_definitions("benchmark-pipeline", project_dir)


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-002")
def test_load_product_definitions_large(tmp_path: Path) -> None:
    """Benchmark runtime definition generation with a large pipeline.

    NFR-002 Target: runtime Definitions generation should complete in <5s for
    500 compiled transforms.
    """
    from floe_orchestrator_dagster.loader import load_product_definitions

    artifacts = _create_artifacts_with_transforms(500)
    project_dir = _write_runtime_project(tmp_path, artifacts)

    _ = load_product_definitions("benchmark-pipeline", project_dir)


# =============================================================================
# Direct create_definitions Failure-Contract Validation
# =============================================================================


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-002")
def test_create_definitions_direct_failure_small() -> None:
    """Benchmark direct create_definitions failure-contract validation.

    Direct Dagster calls validate artifacts, then fail with the project_dir
    contract. Usable runtime Definitions are loaded through the loader shim.
    """
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()
    artifacts = _create_artifacts_with_transforms(10)
    with pytest.raises(ValueError, match="require project_dir"):
        plugin.create_definitions(artifacts)


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-002")
def test_create_definitions_direct_failure_medium() -> None:
    """Benchmark direct create_definitions failure-contract validation.

    Uses a typical production pipeline size.
    """
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()
    artifacts = _create_artifacts_with_transforms(100)
    with pytest.raises(ValueError, match="require project_dir"):
        plugin.create_definitions(artifacts)


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-002")
def test_create_definitions_direct_failure_large() -> None:
    """Benchmark direct create_definitions failure-contract validation.

    This is not the runtime Definitions generation benchmark; it only measures
    validation before the expected project_dir failure for 500 transforms.
    """
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()
    artifacts = _create_artifacts_with_transforms(500)
    with pytest.raises(ValueError, match="require project_dir"):
        plugin.create_definitions(artifacts)


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-002")
def test_create_assets_from_transforms_small() -> None:
    """Benchmark create_assets_from_transforms with 10 transforms."""
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()
    transforms = _create_transform_configs(10)
    _ = plugin.create_assets_from_transforms(transforms)


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-002")
def test_create_assets_from_transforms_medium() -> None:
    """Benchmark create_assets_from_transforms with 100 transforms."""
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()
    transforms = _create_transform_configs(100)
    _ = plugin.create_assets_from_transforms(transforms)


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-002")
def test_create_assets_from_transforms_large() -> None:
    """Benchmark create_assets_from_transforms with 500 transforms.

    NFR-002 Target: Must scale linearly with number of transforms.
    """
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()
    transforms = _create_transform_configs(500)
    _ = plugin.create_assets_from_transforms(transforms)


# =============================================================================
# Additional Performance Benchmarks
# =============================================================================


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-002")
def test_artifacts_validation_overhead() -> None:
    """Benchmark CompiledArtifacts validation overhead.

    Measures Pydantic validation cost in direct create_definitions before the
    expected Dagster project_dir failure contract.
    """
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()
    artifacts = _create_minimal_artifacts()
    with pytest.raises(ValueError, match="require project_dir"):
        plugin.create_definitions(artifacts)


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-001")
def test_get_helm_values_overhead() -> None:
    """Benchmark get_helm_values method overhead.

    Measures dictionary construction for Helm chart configuration.
    """
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()
    _ = plugin.get_helm_values()


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-001")
def test_get_resource_requirements_overhead() -> None:
    """Benchmark get_resource_requirements method overhead.

    Measures ResourceSpec lookup cost.
    """
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()
    _ = plugin.get_resource_requirements("medium")


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-001")
def test_schedule_job_overhead() -> None:
    """Benchmark schedule_job method overhead.

    Measures ScheduleDefinition creation cost.
    """
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()
    _ = plugin.schedule_job("benchmark_job", "0 8 * * *", "UTC")


@pytest.mark.benchmark
@pytest.mark.requirement("NFR-001")
def test_emit_lineage_event_noop() -> None:
    """Benchmark emit_lineage_event when no backend configured.

    Measures no-op path overhead.
    """
    from floe_core.lineage import LineageDataset, RunState
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()
    inputs = [LineageDataset(namespace="floe", name="input")]
    outputs = [LineageDataset(namespace="floe", name="output")]
    plugin.emit_lineage_event(
        event_type=RunState.START,
        job_name="benchmark_job",
        inputs=inputs,
        outputs=outputs,
    )

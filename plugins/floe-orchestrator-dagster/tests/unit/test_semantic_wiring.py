"""Unit tests for semantic layer runtime Definitions wiring."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION


def _compiled_artifacts(semantic: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create valid CompiledArtifacts with optional semantic plugin config."""
    plugins: dict[str, Any] = {
        "compute": {"type": "duckdb", "version": "0.9.0"},
        "orchestrator": {"type": "dagster", "version": "1.5.0"},
    }
    if semantic is not None:
        plugins["semantic"] = semantic

    return {
        "version": COMPILED_ARTIFACTS_VERSION,
        "metadata": {
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "floe_version": COMPILED_ARTIFACTS_VERSION,
            "source_hash": "sha256:semantic123",
            "product_name": "semantic-test-pipeline",
            "product_version": "1.0.0",
        },
        "identity": {
            "product_id": "default.semantic_test_pipeline",
            "domain": "default",
            "repository": "github.com/test/semantic-test-pipeline",
        },
        "mode": "simple",
        "observability": {
            "telemetry": {
                "enabled": True,
                "resource_attributes": {
                    "service_name": "semantic-test-pipeline",
                    "service_version": "1.0.0",
                    "deployment_environment": "dev",
                    "floe_namespace": "default",
                    "floe_product_name": "semantic-test-pipeline",
                    "floe_product_version": "1.0.0",
                    "floe_mode": "dev",
                },
            },
            "lineage": True,
            "lineage_namespace": "semantic-test-pipeline",
        },
        "plugins": plugins,
        "transforms": {
            "models": [{"name": "test_model", "compute": "duckdb", "tags": ["test"]}],
            "default_compute": "duckdb",
        },
    }


def _write_project(tmp_path: Path, artifacts: dict[str, Any]) -> Path:
    """Write compiled artifacts and minimal dbt manifest for loader-path tests."""
    project_dir = tmp_path / "dbt_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "compiled_artifacts.json").write_text(json.dumps(artifacts))

    target_dir = project_dir / "target"
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json",
            "dbt_version": "1.7.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "invocation_id": "semantic-wiring-test",
        },
        "nodes": {},
        "sources": {},
        "exposures": {},
        "metrics": {},
        "groups": {},
        "selectors": {},
        "disabled": [],
        "parent_map": {},
        "child_map": {},
        "group_map": {},
        "semantic_models": {},
        "unit_tests": {},
        "saved_queries": {},
    }
    (target_dir / "manifest.json").write_text(json.dumps(manifest))
    return project_dir


def _asset_names(definitions: Any) -> set[str]:
    """Collect asset key names from single-asset and multi-asset definitions."""
    names: set[str] = set()
    for asset_def in definitions.assets or []:
        keys = getattr(asset_def, "keys", None)
        if keys:
            names.update(key.path[-1] for key in keys)
            continue
        try:
            names.add(asset_def.key.path[-1])
        except Exception:
            continue
    return names


class TestSemanticDefinitionsWiring:
    """Test semantic resources are wired into runtime Definitions."""

    @pytest.mark.requirement("FR-055")
    def test_loader_definitions_include_semantic_resources(self, tmp_path: Path) -> None:
        """Loader-path Definitions include semantic_layer resource and sync asset."""
        from floe_orchestrator_dagster.loader import load_product_definitions

        artifacts = _compiled_artifacts(
            semantic={
                "type": "cube",
                "version": "0.1.0",
                "config": {"schema_output_dir": "cube/schema"},
            },
        )
        project_dir = _write_project(tmp_path, artifacts)
        semantic_resource = MagicMock()

        with patch(
            "floe_orchestrator_dagster.runtime._create_semantic_resources",
            return_value={"semantic_layer": semantic_resource},
        ):
            definitions = load_product_definitions("semantic-test-pipeline", project_dir)

        assert definitions.resources["semantic_layer"] is semantic_resource
        assert "sync_semantic_schemas" in _asset_names(definitions)

    @pytest.mark.requirement("FR-055")
    def test_loader_definitions_without_semantic_config_has_no_semantic_resources(
        self,
        tmp_path: Path,
    ) -> None:
        """Loader-path Definitions omit semantic_layer when not configured."""
        from floe_orchestrator_dagster.loader import load_product_definitions

        artifacts = _compiled_artifacts(semantic=None)
        project_dir = _write_project(tmp_path, artifacts)

        definitions = load_product_definitions("semantic-test-pipeline", project_dir)

        assert "semantic_layer" not in definitions.resources
        assert "sync_semantic_schemas" not in _asset_names(definitions)


__all__ = [
    "TestSemanticDefinitionsWiring",
]

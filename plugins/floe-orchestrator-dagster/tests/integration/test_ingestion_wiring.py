"""Integration tests for blocked ingestion orchestrator runtime wiring (T032)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION


def _compiled_artifacts(ingestion: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create valid CompiledArtifacts with optional ingestion plugin config."""
    plugins: dict[str, Any] = {
        "compute": {"type": "duckdb", "version": "0.9.0"},
        "orchestrator": {"type": "dagster", "version": "1.5.0"},
    }
    if ingestion is not None:
        plugins["ingestion"] = ingestion

    return {
        "version": COMPILED_ARTIFACTS_VERSION,
        "metadata": {
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "floe_version": COMPILED_ARTIFACTS_VERSION,
            "source_hash": "sha256:ingestion123",
            "product_name": "ingestion-test-pipeline",
            "product_version": "1.0.0",
        },
        "identity": {
            "product_id": "default.ingestion_test_pipeline",
            "domain": "default",
            "repository": "github.com/test/ingestion-test-pipeline",
        },
        "mode": "simple",
        "observability": {
            "telemetry": {
                "enabled": True,
                "resource_attributes": {
                    "service_name": "ingestion-test-pipeline",
                    "service_version": "1.0.0",
                    "deployment_environment": "dev",
                    "floe_namespace": "default",
                    "floe_product_name": "ingestion-test-pipeline",
                    "floe_product_version": "1.0.0",
                    "floe_mode": "dev",
                },
            },
            "lineage": True,
            "lineage_namespace": "ingestion-test-pipeline",
        },
        "plugins": plugins,
        "transforms": {
            "models": [{"name": "stg_customers", "compute": "duckdb"}],
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
            "invocation_id": "ingestion-wiring-test",
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


class TestIngestionWiringIntegration:
    """Integration tests for ingestion wiring through the runtime loader."""

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-059")
    def test_definitions_fail_loudly_with_ingestion_configured(self, tmp_path: Path) -> None:
        """Loader-path Definitions reject ingestion until source construction exists."""
        from floe_orchestrator_dagster.loader import load_product_definitions

        artifacts = _compiled_artifacts(
            ingestion={
                "type": "dlt",
                "version": "0.1.0",
                "config": {
                    "sources": [
                        {
                            "name": "github-events",
                            "source_type": "rest_api",
                            "destination_table": "bronze.github_events",
                        },
                        {
                            "name": "warehouse_users",
                            "source_type": "sql_database",
                            "destination_table": "bronze.users",
                        },
                    ]
                },
            },
        )
        project_dir = _write_project(tmp_path, artifacts)

        with pytest.raises(ValueError, match="Dagster ingestion runtime is not enabled"):
            load_product_definitions("ingestion-test-pipeline", project_dir)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-063")
    def test_definitions_degrade_without_ingestion(self, tmp_path: Path) -> None:
        """Loader-path Definitions omit ingestion resource when not configured."""
        from floe_orchestrator_dagster.loader import load_product_definitions

        artifacts = _compiled_artifacts(ingestion=None)
        project_dir = _write_project(tmp_path, artifacts)

        definitions = load_product_definitions("ingestion-test-pipeline", project_dir)

        assert "ingestion" not in definitions.resources
        assert not any(name.startswith("run_ingestion_") for name in _asset_names(definitions))

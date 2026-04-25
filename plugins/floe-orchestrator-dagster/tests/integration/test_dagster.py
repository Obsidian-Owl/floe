"""Integration tests for DagsterOrchestratorPlugin with real Dagster service.

These tests verify the DagsterOrchestratorPlugin works with a real Dagster
deployment in Kubernetes. Tests require K8s with Dagster deployed.

Requirements Covered:
- SC-002: Plugin consumes CompiledArtifacts correctly
- SC-004: Connection validation works with real Dagster service

Note:
- Tests in this file require K8s infrastructure. Run with: make test-integration
- ABC compliance tests are in tests/unit/test_plugin.py (no K8s required)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from floe_core.schemas.compiled_artifacts import CompiledArtifacts
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION
from testing.base_classes.integration_test_base import IntegrationTestBase


class TestDagsterConnectionValidation(IntegrationTestBase):
    """Integration tests for validate_connection with real Dagster.

    Validates SC-004: Connection validation works with real Dagster service.
    """

    required_services = ["dagster-webserver"]

    @pytest.mark.integration
    @pytest.mark.requirement("SC-004")
    def test_validate_connection_success_with_real_dagster(self) -> None:
        """Test validate_connection succeeds with running Dagster service."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()
        host = self.get_service_host("dagster-webserver")
        dagster_url = f"http://{host}:3000"

        result = plugin.validate_connection(dagster_url=dagster_url, timeout=30.0)

        assert result.success is True, f"Connection failed: {result.message}"
        assert "Successfully connected" in result.message

    @pytest.mark.integration
    @pytest.mark.requirement("SC-004")
    def test_validate_connection_returns_validation_result(self) -> None:
        """Test validate_connection returns proper ValidationResult type."""
        from floe_core.plugins.orchestrator import ValidationResult

        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()
        host = self.get_service_host("dagster-webserver")
        dagster_url = f"http://{host}:3000"

        result = plugin.validate_connection(dagster_url=dagster_url)

        assert isinstance(result, ValidationResult)

    @pytest.mark.integration
    @pytest.mark.requirement("SC-004")
    def test_validate_connection_timeout_parameter_works(self) -> None:
        """Test validate_connection respects timeout parameter."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()
        host = self.get_service_host("dagster-webserver")
        dagster_url = f"http://{host}:3000"

        # Should complete within reasonable timeout
        result = plugin.validate_connection(dagster_url=dagster_url, timeout=60.0)

        # We're testing that timeout doesn't cause issues with a running service
        assert result.success is True


class TestDagsterDefinitionsLoading(IntegrationTestBase):
    """Integration tests for loading generated definitions in Dagster.

    Validates SC-002: Generated definitions can be loaded in Dagster.
    """

    required_services = ["dagster-webserver"]

    def _write_runtime_project(self, tmp_path: Path, artifacts: dict[str, Any]) -> Path:
        """Write compiled artifacts and a minimal dbt manifest for runtime loading."""
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
                "invocation_id": "integration-test",
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

    def _build_runtime_definitions(self, tmp_path: Path, artifacts: dict[str, Any]) -> Any:
        """Build Definitions through the canonical runtime path."""
        from floe_orchestrator_dagster.runtime import build_product_definitions

        validated = CompiledArtifacts.model_validate(artifacts)
        project_dir = self._write_runtime_project(tmp_path, artifacts)
        return build_product_definitions(
            product_name=validated.metadata.product_name,
            artifacts=validated,
            project_dir=project_dir,
        )

    def _asset_key_paths(self, definitions: Any) -> list[list[str]]:
        """Collect accessible asset key paths from runtime Definitions."""
        paths: list[list[str]] = []
        for asset_def in definitions.assets or []:
            keys = getattr(asset_def, "keys", None)
            if keys:
                paths.extend(key.path for key in keys)
                continue
            try:
                paths.append(asset_def.key.path)
            except Exception:
                continue
        return paths

    @pytest.fixture
    def valid_compiled_artifacts(self) -> dict[str, Any]:
        """Create valid CompiledArtifacts for integration testing."""
        return {
            "version": COMPILED_ARTIFACTS_VERSION,
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": COMPILED_ARTIFACTS_VERSION,
                "source_hash": "sha256:integration123",
                "product_name": "integration-test-pipeline",
                "product_version": "1.0.0",
            },
            "identity": {
                "product_id": "default.integration_test_pipeline",
                "domain": "default",
                "repository": "github.com/test/integration-test-pipeline",
            },
            "mode": "simple",
            "observability": {
                "telemetry": {
                    "enabled": True,
                    "resource_attributes": {
                        "service_name": "integration-test-pipeline",
                        "service_version": "1.0.0",
                        "deployment_environment": "dev",
                        "floe_namespace": "default",
                        "floe_product_name": "integration-test-pipeline",
                        "floe_product_version": "1.0.0",
                        "floe_mode": "dev",
                    },
                },
                "lineage": True,
                "lineage_namespace": "integration-test-pipeline",
            },
            "plugins": {
                "compute": {"type": "duckdb", "version": "0.9.0"},
                "orchestrator": {"type": "dagster", "version": "1.5.0"},
            },
            "transforms": {
                "models": [
                    {"name": "stg_customers", "compute": "duckdb"},
                    {
                        "name": "fct_orders",
                        "compute": "duckdb",
                        "depends_on": ["stg_customers"],
                    },
                ],
                "default_compute": "duckdb",
            },
        }

    @pytest.mark.integration
    @pytest.mark.requirement("SC-002")
    def test_create_definitions_requires_project_dir(
        self, valid_compiled_artifacts: dict[str, Any]
    ) -> None:
        """Test direct create_definitions fails until routed through runtime loader."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()

        with pytest.raises(ValueError, match="require project_dir"):
            plugin.create_definitions(valid_compiled_artifacts)

    @pytest.mark.integration
    @pytest.mark.requirement("SC-002")
    def test_runtime_builder_produces_valid_dagster_definitions(
        self,
        tmp_path: Path,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test runtime builder produces valid Dagster Definitions object."""
        from dagster import Definitions

        definitions = self._build_runtime_definitions(tmp_path, valid_compiled_artifacts)

        assert isinstance(definitions, Definitions)
        assert len(definitions.assets) > 0

    @pytest.mark.integration
    @pytest.mark.requirement("SC-002")
    def test_runtime_assets_have_valid_keys(
        self,
        tmp_path: Path,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test runtime-created assets have valid AssetKeys."""

        definitions = self._build_runtime_definitions(tmp_path, valid_compiled_artifacts)

        assets_list = list(definitions.assets)
        asset_key_paths = self._asset_key_paths(definitions)

        assert assets_list
        assert all(path for path in asset_key_paths)

    @pytest.mark.integration
    @pytest.mark.requirement("SC-002")
    def test_runtime_assets_require_dbt_and_lineage_resources(
        self,
        tmp_path: Path,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test runtime dbt asset declares required runtime resources."""
        definitions = self._build_runtime_definitions(tmp_path, valid_compiled_artifacts)

        assets_list = list(definitions.assets)
        assert assets_list

        required_keys = assets_list[0].required_resource_keys
        assert "dbt" in required_keys
        assert "lineage" in required_keys

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

from datetime import datetime, timezone
from typing import Any, ClassVar

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase


class TestDagsterConnectionValidation(IntegrationTestBase):
    """Integration tests for validate_connection with real Dagster.

    Validates SC-004: Connection validation works with real Dagster service.
    """

    required_services: ClassVar[list[tuple[str, int]]] = [("dagster-webserver", 3000)]

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

    required_services: ClassVar[list[tuple[str, int]]] = [("dagster-webserver", 3000)]

    @pytest.fixture
    def valid_compiled_artifacts(self) -> dict[str, Any]:
        """Create valid CompiledArtifacts for integration testing."""
        return {
            "version": "0.3.0",
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": "0.3.0",
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
    def test_create_definitions_produces_valid_dagster_definitions(
        self, valid_compiled_artifacts: dict[str, Any]
    ) -> None:
        """Test create_definitions produces valid Dagster Definitions object."""
        from dagster import Definitions

        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()
        definitions = plugin.create_definitions(valid_compiled_artifacts)

        # Verify we got a valid Definitions object
        assert isinstance(definitions, Definitions)
        assert definitions.assets is not None

    @pytest.mark.integration
    @pytest.mark.requirement("SC-002")
    def test_created_assets_have_valid_keys(self, valid_compiled_artifacts: dict[str, Any]) -> None:
        """Test created assets have valid AssetKeys."""

        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()
        definitions = plugin.create_definitions(valid_compiled_artifacts)

        assets_list = list(definitions.assets)
        asset_keys = [asset.key for asset in assets_list]

        # Verify expected assets exist
        expected_names = {"stg_customers", "fct_orders"}
        actual_names = {key.path[-1] for key in asset_keys}
        assert expected_names == actual_names

    @pytest.mark.integration
    @pytest.mark.requirement("SC-002")
    def test_created_assets_preserve_dependencies(
        self, valid_compiled_artifacts: dict[str, Any]
    ) -> None:
        """Test created assets preserve dependency relationships."""
        from dagster import AssetKey

        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()
        definitions = plugin.create_definitions(valid_compiled_artifacts)

        assets_list = list(definitions.assets)

        # Find fct_orders and verify it depends on stg_customers
        fct_orders = None
        for asset in assets_list:
            if asset.key.path[-1] == "fct_orders":
                fct_orders = asset
                break

        assert fct_orders is not None, "fct_orders asset not found"
        assert AssetKey(["stg_customers"]) in fct_orders.dependency_keys

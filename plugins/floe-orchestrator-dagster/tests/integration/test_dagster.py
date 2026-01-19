"""Integration tests for DagsterOrchestratorPlugin with real Dagster service.

These tests verify the DagsterOrchestratorPlugin works with a real Dagster
deployment in Kubernetes. Tests require K8s with Dagster deployed.

Requirements Covered:
- SC-002: Plugin consumes CompiledArtifacts correctly
- SC-004: Connection validation works with real Dagster service

Note: Tests in this file require K8s infrastructure. Run with:
    make test-integration
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
            "version": "0.2.0",
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": "0.2.0",
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
                        "deployment_environment": "integration",
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
    def test_created_assets_have_valid_keys(
        self, valid_compiled_artifacts: dict[str, Any]
    ) -> None:
        """Test created assets have valid AssetKeys."""
        from dagster import AssetKey

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


class TestDagsterPluginABCComplianceIntegration(IntegrationTestBase):
    """Integration tests for OrchestratorPlugin ABC compliance.

    Validates SC-001: Plugin passes all 7 abstract method compliance tests.
    """

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.mark.integration
    @pytest.mark.requirement("SC-001")
    def test_plugin_inherits_from_orchestrator_plugin(self) -> None:
        """Test plugin inherits from OrchestratorPlugin ABC."""
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()
        assert isinstance(plugin, OrchestratorPlugin)

    @pytest.mark.integration
    @pytest.mark.requirement("SC-001")
    def test_plugin_implements_all_abstract_methods(self) -> None:
        """Test plugin implements all required abstract methods."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()

        # All 7 ABC methods must exist and be callable
        abstract_methods = [
            "create_definitions",
            "create_assets_from_transforms",
            "get_helm_values",
            "validate_connection",
            "get_resource_requirements",
            "emit_lineage_event",
            "schedule_job",
        ]

        for method_name in abstract_methods:
            assert hasattr(plugin, method_name), f"Missing method: {method_name}"
            method = getattr(plugin, method_name)
            assert callable(method), f"Method not callable: {method_name}"

    @pytest.mark.integration
    @pytest.mark.requirement("SC-001")
    def test_plugin_metadata_properties(self) -> None:
        """Test plugin declares required metadata properties."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()

        # Required metadata properties
        assert plugin.name == "dagster"
        assert plugin.version is not None
        assert len(plugin.version.split(".")) == 3  # semver
        assert plugin.floe_api_version is not None
        assert plugin.description is not None
        assert len(plugin.description) > 0

"""Integration tests for semantic layer orchestrator wiring chain.

These tests verify the semantic layer plugin can be discovered via entry points,
loaded by the orchestrator, and wired into Dagster Definitions with resources.

The complete wiring chain tested:
1. Entry point discovery (floe.semantic_layers group)
2. Resource factory (try_create_semantic_resources)
3. Asset availability (sync_semantic_schemas)
4. Definitions wiring (create_definitions with semantic resources)

Requirements Covered:
- FR-054: Semantic layer plugin entry point discovery
- FR-055: Semantic resources wiring into Dagster Definitions

Note:
- Tests require K8s with Dagster deployed. Run with: make test-integration
- Tests use real plugin discovery, no mocks
"""

from __future__ import annotations

import importlib.metadata
from datetime import datetime, timezone
from typing import Any, ClassVar

import pytest
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION
from testing.base_classes.integration_test_base import IntegrationTestBase


class TestSemanticPluginEntryPointDiscovery(IntegrationTestBase):
    """Test semantic layer plugin can be discovered via entry points.

    Validates FR-054: Plugin discovery via floe.semantic_layers entry point.
    """

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.mark.integration
    @pytest.mark.requirement("FR-054")
    def test_semantic_plugin_entry_point_exists(self) -> None:
        """Test semantic layer plugin is discoverable via entry point."""
        # Discover entry points in the floe.semantic_layers group
        entry_points = importlib.metadata.entry_points()

        # Get the semantic_layers group (Python 3.10+ API)
        semantic_eps = entry_points.select(group="floe.semantic_layers")

        # Convert to list to check
        semantic_list = list(semantic_eps)

        assert len(semantic_list) > 0, "No semantic layer plugins found via entry points"

        # Verify 'cube' plugin is present
        cube_found = any(ep.name == "cube" for ep in semantic_list)
        assert cube_found, "Cube semantic plugin not found in entry points"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-054")
    def test_semantic_plugin_can_be_loaded_from_entry_point(self) -> None:
        """Test semantic layer plugin can be loaded via entry point."""
        entry_points = importlib.metadata.entry_points()
        semantic_eps = entry_points.select(group="floe.semantic_layers")

        # Find the cube entry point
        cube_ep = None
        for ep in semantic_eps:
            if ep.name == "cube":
                cube_ep = ep
                break

        assert cube_ep is not None, "Cube entry point not found"

        # Load the plugin class
        plugin_class = cube_ep.load()

        assert plugin_class is not None, "Failed to load plugin class from entry point"
        assert hasattr(plugin_class, "name"), "Plugin class missing 'name' attribute"
        assert hasattr(
            plugin_class, "sync_from_dbt_manifest"
        ), "Plugin class missing 'sync_from_dbt_manifest' method"


class TestSemanticResourceFactory(IntegrationTestBase):
    """Test semantic resource factory creates valid resources.

    Validates FR-055: Resource factory produces valid semantic_layer resource.
    """

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.fixture
    def semantic_plugin_config(self) -> dict[str, Any]:
        """Create minimal semantic plugin configuration."""
        return {
            "semantic": {
                "type": "cube",
                "version": "0.1.0",
                "config": {
                    "schema_output_dir": "cube/schema",
                },
            }
        }

    @pytest.mark.integration
    @pytest.mark.requirement("FR-055")
    def test_try_create_semantic_resources_returns_empty_dict_when_no_plugins(
        self,
    ) -> None:
        """Test try_create_semantic_resources returns empty dict when plugins is None."""
        from floe_orchestrator_dagster.resources.semantic import try_create_semantic_resources

        resources = try_create_semantic_resources(plugins=None)

        assert resources == {}, "Expected empty dict when plugins is None"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-055")
    def test_try_create_semantic_resources_returns_empty_dict_when_semantic_not_configured(
        self,
    ) -> None:
        """Test try_create_semantic_resources returns empty dict when semantic is not configured."""
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.semantic import try_create_semantic_resources

        # Create ResolvedPlugins with no semantic configured (compute and orchestrator required)
        plugins = ResolvedPlugins(
            catalog=None,
            storage=None,
            compute=PluginRef(type="duckdb", version="0.9.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
            semantic=None,
        )

        resources = try_create_semantic_resources(plugins=plugins)

        assert resources == {}, "Expected empty dict when semantic is None"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-055")
    def test_try_create_semantic_resources_produces_valid_resource_dict(self) -> None:
        """Test try_create_semantic_resources produces valid resource dict."""
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.semantic import try_create_semantic_resources

        # Create ResolvedPlugins with semantic configured
        semantic_ref = PluginRef(
            type="cube",
            version="0.1.0",
            config={
                "schema_output_dir": "cube/schema",
            },
        )
        plugins = ResolvedPlugins(
            catalog=None,
            storage=None,
            compute=PluginRef(type="duckdb", version="0.9.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
            semantic=semantic_ref,
        )

        resources = try_create_semantic_resources(plugins=plugins)

        assert "semantic_layer" in resources, "Expected 'semantic_layer' key in resources"
        assert (
            resources["semantic_layer"] is not None
        ), "Expected non-None semantic_layer resource"

        # Verify the resource has expected plugin attributes
        semantic_plugin = resources["semantic_layer"]
        assert hasattr(semantic_plugin, "name"), "Plugin missing 'name' attribute"
        assert hasattr(
            semantic_plugin, "sync_from_dbt_manifest"
        ), "Plugin missing 'sync_from_dbt_manifest' method"


class TestSyncSemanticSchemasAsset(IntegrationTestBase):
    """Test sync_semantic_schemas asset is available for wiring.

    Validates FR-055: Asset can be imported and wired into Definitions.
    """

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.mark.integration
    @pytest.mark.requirement("FR-055")
    def test_sync_semantic_schemas_asset_is_importable(self) -> None:
        """Test sync_semantic_schemas asset can be imported."""
        from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

        assert sync_semantic_schemas is not None, "sync_semantic_schemas asset is None"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-055")
    def test_sync_semantic_schemas_asset_has_required_resource_keys(self) -> None:
        """Test sync_semantic_schemas asset declares semantic_layer resource dependency."""
        from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

        # Asset should be an AssetsDefinition or wrapped in one
        # The asset decorator creates an AssetsDefinition
        assert hasattr(
            sync_semantic_schemas, "required_resource_keys"
        ), "Asset missing required_resource_keys"

        required_keys = sync_semantic_schemas.required_resource_keys
        assert (
            "semantic_layer" in required_keys
        ), "Asset must declare semantic_layer resource dependency"


class TestSemanticDefinitionsWiring(IntegrationTestBase):
    """Test semantic resources are wired into Definitions by create_definitions.

    Validates FR-055: create_definitions produces Definitions with semantic resources.
    """

    required_services: ClassVar[list[tuple[str, int]]] = [("dagster-webserver", 3000)]

    @pytest.fixture
    def compiled_artifacts_with_semantic(self) -> dict[str, Any]:
        """Create CompiledArtifacts with semantic plugin configured."""
        return {
            "version": COMPILED_ARTIFACTS_VERSION,
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": COMPILED_ARTIFACTS_VERSION,
                "source_hash": "sha256:semantic123",
                "product_name": "semantic-test-pipeline",
                "product_version": "1.0.0",
            },
            "transforms": {
                "models": [
                    {
                        "name": "test_model",
                        "compute": "duckdb",
                        "tags": ["test"],
                        "depends_on": [],
                    }
                ]
            },
            "plugins": {
                "semantic": {
                    "type": "cube",
                    "version": "0.1.0",
                    "config": {
                        "schema_output_dir": "cube/schema",
                    },
                }
            },
        }

    @pytest.mark.integration
    @pytest.mark.requirement("FR-055")
    def test_create_definitions_includes_semantic_resources(
        self, compiled_artifacts_with_semantic: dict[str, Any]
    ) -> None:
        """Test create_definitions produces Definitions with semantic_layer resource."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()

        definitions = plugin.create_definitions(compiled_artifacts_with_semantic)

        assert definitions is not None, "create_definitions returned None"

        # Check that resources dict contains semantic_layer
        resources = definitions.resources
        assert resources is not None, "Definitions has no resources"
        assert "semantic_layer" in resources, "semantic_layer not found in Definitions resources"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-055")
    def test_create_definitions_without_semantic_config_has_no_semantic_resources(
        self,
    ) -> None:
        """Test create_definitions produces Definitions without semantic_layer.

        Validates that when semantic plugin is not configured, the Definitions
        object does not include semantic_layer in its resources dict.
        """
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        # Minimal artifacts without semantic plugin
        artifacts = {
            "version": COMPILED_ARTIFACTS_VERSION,
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": COMPILED_ARTIFACTS_VERSION,
                "source_hash": "sha256:nosemantic",
                "product_name": "no-semantic-pipeline",
                "product_version": "1.0.0",
            },
            "transforms": {
                "models": [
                    {
                        "name": "test_model",
                        "compute": "duckdb",
                        "tags": ["test"],
                        "depends_on": [],
                    }
                ]
            },
        }

        plugin = DagsterOrchestratorPlugin()
        definitions = plugin.create_definitions(artifacts)

        assert definitions is not None, "create_definitions returned None"

        # Check that resources dict does NOT contain semantic_layer
        resources = definitions.resources
        assert (
            "semantic_layer" not in resources
        ), "semantic_layer should not be present when not configured"


__all__ = [
    "TestSemanticDefinitionsWiring",
    "TestSemanticPluginEntryPointDiscovery",
    "TestSemanticResourceFactory",
    "TestSyncSemanticSchemasAsset",
]

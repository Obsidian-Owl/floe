"""Unit tests for semantic layer orchestrator wiring chain.

These tests verify the semantic layer plugin can be discovered via entry points,
loaded by the orchestrator, and resource factory produces correct output.

Tests DO NOT require external services (Dagster webserver, K8s, etc.).

The wiring chain tested at unit level:
1. Entry point discovery (floe.semantic_layers group)
2. Resource factory (try_create_semantic_resources)
3. Asset availability (sync_semantic_schemas)

Requirements Covered:
- FR-054: Semantic layer plugin entry point discovery
- FR-055: Semantic resources wiring into Dagster Definitions
"""

from __future__ import annotations

import importlib.metadata
from typing import Any

import pytest
from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins


class TestSemanticPluginEntryPointDiscovery:
    """Test semantic layer plugin can be discovered via entry points.

    Validates FR-054: Plugin discovery via floe.semantic_layers entry point.
    """

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
        assert hasattr(plugin_class, "sync_from_dbt_manifest"), (
            "Plugin class missing 'sync_from_dbt_manifest' method"
        )


class TestSemanticResourceFactory:
    """Test semantic resource factory creates valid resources.

    Validates FR-055: Resource factory produces valid semantic_layer resource.
    """

    @pytest.fixture
    def semantic_plugin_config(self) -> dict[str, Any]:
        """Create minimal semantic plugin configuration."""
        return {
            "semantic": {
                "type": "cube",
                "version": "0.1.0",
                "config": {
                    "api_secret": "test-secret",
                    "database_name": "test_db",
                },
            }
        }

    @pytest.mark.requirement("FR-055")
    def test_try_create_semantic_resources_returns_empty_dict_when_no_plugins(
        self,
    ) -> None:
        """Test try_create_semantic_resources returns empty dict when plugins is None."""
        from floe_orchestrator_dagster.resources.semantic import (
            try_create_semantic_resources,
        )

        resources = try_create_semantic_resources(plugins=None)

        assert resources == {}, "Expected empty dict when plugins is None"

    @pytest.mark.requirement("FR-055")
    def test_try_create_semantic_resources_returns_empty_dict_when_semantic_not_configured(
        self,
    ) -> None:
        """Test try_create_semantic_resources returns empty dict when semantic is not configured."""
        from floe_orchestrator_dagster.resources.semantic import (
            try_create_semantic_resources,
        )

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

    @pytest.mark.requirement("FR-055")
    def test_try_create_semantic_resources_produces_valid_resource_dict(self) -> None:
        """Test try_create_semantic_resources produces valid resource dict."""
        from floe_orchestrator_dagster.resources.semantic import (
            try_create_semantic_resources,
        )

        # Create ResolvedPlugins with semantic configured
        semantic_ref = PluginRef(
            type="cube",
            version="0.1.0",
            config={
                "api_secret": "test-secret",
                "database_name": "test_db",
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
        assert resources["semantic_layer"] is not None, "Expected non-None semantic_layer resource"

        # Verify the resource has expected plugin attributes
        semantic_plugin = resources["semantic_layer"]
        assert hasattr(semantic_plugin, "name"), "Plugin missing 'name' attribute"
        assert hasattr(semantic_plugin, "sync_from_dbt_manifest"), (
            "Plugin missing 'sync_from_dbt_manifest' method"
        )


class TestSyncSemanticSchemasAsset:
    """Test sync_semantic_schemas asset is available for wiring.

    Validates FR-055: Asset can be imported and wired into Definitions.
    """

    @pytest.mark.requirement("FR-055")
    def test_sync_semantic_schemas_asset_is_importable(self) -> None:
        """Test sync_semantic_schemas asset can be imported."""
        from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

        assert sync_semantic_schemas is not None, "sync_semantic_schemas asset is None"

    @pytest.mark.requirement("FR-055")
    def test_sync_semantic_schemas_asset_has_required_resource_keys(self) -> None:
        """Test sync_semantic_schemas asset declares semantic_layer resource dependency."""
        from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

        # Asset should be an AssetsDefinition or wrapped in one
        # The asset decorator creates an AssetsDefinition
        assert hasattr(sync_semantic_schemas, "required_resource_keys"), (
            "Asset missing required_resource_keys"
        )

        required_keys = sync_semantic_schemas.required_resource_keys
        assert "semantic_layer" in required_keys, (
            "Asset must declare semantic_layer resource dependency"
        )


__all__ = [
    "TestSemanticPluginEntryPointDiscovery",
    "TestSemanticResourceFactory",
    "TestSyncSemanticSchemasAsset",
]

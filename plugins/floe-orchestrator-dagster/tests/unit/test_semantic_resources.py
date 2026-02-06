"""Unit tests for semantic layer resource factory.

Tests the try_create_semantic_resources() factory function that loads
SemanticLayerPlugin from CompiledArtifacts and creates Dagster resources.

Requirements:
    T050: Unit tests for semantic resource factory
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from floe_core.plugin_types import PluginType
from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

from floe_orchestrator_dagster.resources.semantic import (
    create_semantic_resources,
    try_create_semantic_resources,
)


@pytest.mark.requirement("T047")
def test_create_semantic_resources_returns_valid_dict() -> None:
    """Test create_semantic_resources returns valid resources dict.

    Validates that the factory function successfully loads a semantic
    plugin and returns it in a dictionary with the expected key.
    """
    # Create a mock semantic plugin
    mock_plugin = MagicMock()
    mock_plugin.name = "cube"
    mock_plugin.version = "0.1.0"

    # Create a PluginRef
    semantic_ref = PluginRef(
        type="cube",
        version="0.1.0",
        config={"api_secret": "test"},
    )

    # Patch the registry at the import location
    with patch("floe_core.plugin_registry.get_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_plugin
        mock_get_registry.return_value = mock_registry

        # Call the factory
        resources = create_semantic_resources(semantic_ref)

        # Verify the resources dict
        assert "semantic_layer" in resources
        assert resources["semantic_layer"] == mock_plugin

        # Verify registry was called correctly
        mock_registry.get.assert_called_once_with(PluginType.SEMANTIC_LAYER, "cube")
        mock_registry.configure.assert_called_once_with(
            PluginType.SEMANTIC_LAYER,
            "cube",
            {"api_secret": "test"},
        )


@pytest.mark.requirement("T047")
def test_try_create_semantic_resources_with_none_plugins() -> None:
    """Test try_create_semantic_resources returns empty dict when plugins is None."""
    resources = try_create_semantic_resources(plugins=None)

    assert resources == {}


@pytest.mark.requirement("T047")
def test_try_create_semantic_resources_with_no_semantic_plugin() -> None:
    """Test try_create_semantic_resources returns empty dict when semantic is None."""
    # Create ResolvedPlugins with no semantic plugin
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="1.0.0", config=None),
        orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
        catalog=None,
        storage=None,
        ingestion=None,
        semantic=None,  # No semantic plugin
    )

    resources = try_create_semantic_resources(plugins)

    assert resources == {}


@pytest.mark.requirement("T047")
def test_try_create_semantic_resources_with_semantic_plugin() -> None:
    """Test try_create_semantic_resources returns valid dict when semantic configured."""
    # Create a mock semantic plugin
    mock_plugin = MagicMock()
    mock_plugin.name = "cube"
    mock_plugin.version = "0.1.0"

    # Create ResolvedPlugins with semantic plugin
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="1.0.0", config=None),
        orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
        catalog=None,
        storage=None,
        ingestion=None,
        semantic=PluginRef(type="cube", version="0.1.0", config=None),
    )

    # Patch the registry at the import location
    with patch("floe_core.plugin_registry.get_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_plugin
        mock_get_registry.return_value = mock_registry

        # Call the factory
        resources = try_create_semantic_resources(plugins)

        # Verify the resources dict
        assert "semantic_layer" in resources
        assert resources["semantic_layer"] == mock_plugin


@pytest.mark.requirement("T047")
def test_create_semantic_resources_configures_plugin() -> None:
    """Test create_semantic_resources configures plugin when config provided."""
    # Create a mock semantic plugin
    mock_plugin = MagicMock()
    mock_plugin.name = "cube"
    mock_plugin.version = "0.1.0"

    # Create a PluginRef with config
    config_dict = {
        "api_url": "http://cube:4000",
        "schema_path": "/cube/schema",
    }
    semantic_ref = PluginRef(
        type="cube",
        version="0.1.0",
        config=config_dict,
    )

    # Patch the registry at the import location
    with patch("floe_core.plugin_registry.get_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_plugin
        mock_get_registry.return_value = mock_registry

        # Call the factory
        resources = create_semantic_resources(semantic_ref)

        # Verify configure was called with the config
        mock_registry.configure.assert_called_once_with(
            PluginType.SEMANTIC_LAYER,
            "cube",
            config_dict,
        )

        assert resources["semantic_layer"] == mock_plugin


@pytest.mark.requirement("T047")
def test_try_create_semantic_resources_handles_plugin_loading_error() -> None:
    """Test try_create_semantic_resources raises when plugin loading fails."""
    # Create ResolvedPlugins with semantic plugin
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="1.0.0", config=None),
        orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
        catalog=None,
        storage=None,
        ingestion=None,
        semantic=PluginRef(type="cube", version="0.1.0", config=None),
    )

    # Patch the registry to raise an error
    with patch("floe_core.plugin_registry.get_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.get.side_effect = RuntimeError("Plugin not found")
        mock_get_registry.return_value = mock_registry

        # Should raise the error (not swallow it)
        with pytest.raises(RuntimeError, match="Plugin not found"):
            try_create_semantic_resources(plugins)

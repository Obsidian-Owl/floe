"""Unit tests for ingestion resource factory.

Tests the try_create_ingestion_resources() factory function that loads
IngestionPlugin from CompiledArtifacts and creates Dagster resources.

Requirements:
    T030: Unit tests for ingestion resource factory
    FR-059: Load ingestion plugin via PluginRegistry
    FR-063: Graceful degradation when ingestion is not configured
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from floe_core.plugin_types import PluginType
from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

from floe_orchestrator_dagster.resources.ingestion import (
    create_ingestion_resources,
    try_create_ingestion_resources,
)


@pytest.mark.requirement("4F-FR-059")
def test_create_ingestion_resources_returns_valid_dict() -> None:
    """Test create_ingestion_resources returns valid resources dict.

    Validates that the factory function successfully loads an ingestion
    plugin and returns it in a dictionary with the expected key.
    """
    # Create a mock ingestion plugin
    mock_plugin = MagicMock()
    mock_plugin.name = "dlt"
    mock_plugin.version = "0.1.0"

    # Create a PluginRef
    ingestion_ref = PluginRef(
        type="dlt",
        version="0.1.0",
        config={"source_type": "postgres"},
    )

    # Patch the registry at the import location
    with patch("floe_core.plugin_registry.get_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_plugin
        mock_get_registry.return_value = mock_registry

        # Call the factory
        resources = create_ingestion_resources(ingestion_ref)

        # Verify the resources dict
        assert "ingestion" in resources
        assert resources["ingestion"] == mock_plugin

        # Verify registry was called correctly
        mock_registry.get.assert_called_once_with(PluginType.INGESTION, "dlt")
        mock_registry.configure.assert_called_once_with(
            PluginType.INGESTION,
            "dlt",
            {"source_type": "postgres"},
        )


@pytest.mark.requirement("4F-FR-063")
def test_try_create_ingestion_resources_with_none_plugins() -> None:
    """Test try_create_ingestion_resources returns empty dict when plugins is None."""
    resources = try_create_ingestion_resources(plugins=None)

    assert resources == {}


@pytest.mark.requirement("4F-FR-063")
def test_try_create_ingestion_resources_with_no_ingestion_plugin() -> None:
    """Test try_create_ingestion_resources returns empty dict when ingestion is None."""
    # Create ResolvedPlugins with no ingestion plugin
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="1.0.0", config=None),
        orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
        catalog=None,
        storage=None,
        ingestion=None,  # No ingestion plugin
        semantic=None,
    )

    resources = try_create_ingestion_resources(plugins)

    assert resources == {}


@pytest.mark.requirement("4F-FR-059")
def test_try_create_ingestion_resources_with_ingestion_plugin() -> None:
    """Test try_create_ingestion_resources returns valid dict when ingestion configured."""
    # Create a mock ingestion plugin
    mock_plugin = MagicMock()
    mock_plugin.name = "dlt"
    mock_plugin.version = "0.1.0"

    # Create ResolvedPlugins with ingestion plugin
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="1.0.0", config=None),
        orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
        catalog=None,
        storage=None,
        ingestion=PluginRef(type="dlt", version="0.1.0", config=None),
        semantic=None,
    )

    # Patch the registry at the import location
    with patch("floe_core.plugin_registry.get_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_plugin
        mock_get_registry.return_value = mock_registry

        # Call the factory
        resources = try_create_ingestion_resources(plugins)

        # Verify the resources dict
        assert "ingestion" in resources
        assert resources["ingestion"] == mock_plugin


@pytest.mark.requirement("4F-FR-059")
def test_create_ingestion_resources_configures_plugin() -> None:
    """Test create_ingestion_resources configures plugin when config provided."""
    # Create a mock ingestion plugin
    mock_plugin = MagicMock()
    mock_plugin.name = "dlt"
    mock_plugin.version = "0.1.0"

    # Create a PluginRef with config
    config_dict = {
        "source_type": "postgres",
        "dataset_name": "raw_data",
    }
    ingestion_ref = PluginRef(
        type="dlt",
        version="0.1.0",
        config=config_dict,
    )

    # Patch the registry at the import location
    with patch("floe_core.plugin_registry.get_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_plugin
        mock_get_registry.return_value = mock_registry

        # Call the factory
        resources = create_ingestion_resources(ingestion_ref)

        # Verify configure was called with the config
        mock_registry.configure.assert_called_once_with(
            PluginType.INGESTION,
            "dlt",
            config_dict,
        )

        assert resources["ingestion"] == mock_plugin


@pytest.mark.requirement("4F-FR-063")
def test_try_create_ingestion_resources_handles_plugin_loading_error() -> None:
    """Test try_create_ingestion_resources returns empty dict on plugin loading error.

    FR-063: Graceful degradation — when ingestion plugin loading fails,
    the function logs the error and returns an empty dict instead of
    propagating the exception.
    """
    # Create ResolvedPlugins with ingestion plugin
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="1.0.0", config=None),
        orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
        catalog=None,
        storage=None,
        ingestion=PluginRef(type="dlt", version="0.1.0", config=None),
        semantic=None,
    )

    # Patch the registry to raise an error
    with patch("floe_core.plugin_registry.get_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.get.side_effect = RuntimeError("Plugin not found")
        mock_get_registry.return_value = mock_registry

        # Should return empty dict (graceful degradation)
        resources = try_create_ingestion_resources(plugins)
        assert resources == {}

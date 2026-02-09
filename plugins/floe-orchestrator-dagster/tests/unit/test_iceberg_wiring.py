"""Unit tests for Iceberg resource wiring in DagsterOrchestratorPlugin.

These tests verify the integration chain:
    PluginRegistry → CatalogPlugin/StoragePlugin →
    IcebergTableManager → IcebergIOManager → Definitions

Tests cover:
- Full wiring chain from registry to Definitions
- Graceful degradation when plugins are not configured
- Edge cases like plugin loading failures

Note: These are unit tests using mocks. Integration tests with real plugins
are in plugins/floe-orchestrator-dagster/tests/integration/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


class TestCreateIcebergResourcesFullWiring:
    """Test create_iceberg_resources() full wiring chain.

    Validates T115: Full wiring chain test.
    """

    @pytest.mark.requirement("004d-FR-115")
    def test_create_iceberg_resources_chains_correctly(self) -> None:
        """Test create_iceberg_resources() chains registry → plugins → manager.

        Validates the complete wiring:
        1. PluginRegistry.get() called for catalog and storage
        2. Plugins configured if config provided
        3. IcebergTableManager created with loaded plugins
        4. IcebergIOManager created with table manager
        5. Returns dict with "iceberg" key
        """
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.iceberg import create_iceberg_resources

        # Create plugin refs with config
        catalog_ref = PluginRef(
            type="mock-catalog",
            version="1.0.0",
            config={"uri": "http://localhost:8181"},
        )
        storage_ref = PluginRef(
            type="mock-storage",
            version="1.0.0",
            config={"bucket": "test-bucket"},
        )

        # Mock the entire chain
        mock_catalog_plugin = MagicMock()
        mock_storage_plugin = MagicMock()
        mock_table_manager = MagicMock()
        mock_io_manager = MagicMock()

        # Patch where imports happen (inside create_iceberg_resources function)
        with (
            patch("floe_core.plugin_registry.get_registry") as mock_get_registry,
            patch("floe_iceberg.IcebergTableManager") as mock_table_manager_cls,
            patch(
                "floe_orchestrator_dagster.io_manager.create_iceberg_io_manager"
            ) as mock_create_io_manager,
        ):
            # Setup mocks
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.side_effect = [mock_catalog_plugin, mock_storage_plugin]
            mock_table_manager_cls.return_value = mock_table_manager
            mock_create_io_manager.return_value = mock_io_manager

            # Execute
            result = create_iceberg_resources(
                catalog_ref=catalog_ref,
                storage_ref=storage_ref,
                default_namespace="test_namespace",
            )

            # Verify registry.get() called for both plugins
            assert mock_registry.get.call_count == 2
            from floe_core.plugin_types import PluginType

            mock_registry.get.assert_any_call(PluginType.CATALOG, "mock-catalog")
            mock_registry.get.assert_any_call(PluginType.STORAGE, "mock-storage")

            # Verify registry.configure() called for both plugins
            assert mock_registry.configure.call_count == 2
            mock_registry.configure.assert_any_call(
                PluginType.CATALOG, "mock-catalog", {"uri": "http://localhost:8181"}
            )
            mock_registry.configure.assert_any_call(
                PluginType.STORAGE, "mock-storage", {"bucket": "test-bucket"}
            )

            # Verify IcebergTableManager created with loaded plugins
            mock_table_manager_cls.assert_called_once_with(
                catalog_plugin=mock_catalog_plugin,
                storage_plugin=mock_storage_plugin,
            )

            # Verify IcebergIOManager created with table manager
            mock_create_io_manager.assert_called_once_with(
                table_manager=mock_table_manager,
                namespace="test_namespace",
            )

            # Verify return value
            assert result == {"iceberg": mock_io_manager}

    @pytest.mark.requirement("004d-FR-115")
    def test_create_iceberg_resources_skips_configure_without_config(self) -> None:
        """Test that registry.configure() is not called when config is None."""
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.iceberg import create_iceberg_resources

        # Create plugin refs without config
        catalog_ref = PluginRef(type="mock-catalog", version="1.0.0", config=None)
        storage_ref = PluginRef(type="mock-storage", version="1.0.0", config=None)

        # Mock the chain (patch where imports happen)
        with (
            patch("floe_core.plugin_registry.get_registry") as mock_get_registry,
            patch("floe_iceberg.IcebergTableManager") as mock_table_manager_cls,
            patch(
                "floe_orchestrator_dagster.io_manager.create_iceberg_io_manager"
            ) as mock_create_io_manager,
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.side_effect = [MagicMock(), MagicMock()]
            mock_table_manager_cls.return_value = MagicMock()
            mock_create_io_manager.return_value = MagicMock()

            # Execute
            create_iceberg_resources(catalog_ref=catalog_ref, storage_ref=storage_ref)

            # Verify configure NOT called
            mock_registry.configure.assert_not_called()


class TestCreateDefinitionsWithIcebergResources:
    """Test create_definitions() returns Definitions with Iceberg resource.

    Validates T116: create_definitions() returns Definitions with "iceberg" resource.
    """

    @pytest.mark.requirement("004d-FR-116")
    def test_create_definitions_includes_iceberg_resource(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts_with_iceberg: dict[str, Any],
    ) -> None:
        """Test that create_definitions() includes "iceberg" resource when plugins configured.

        Validates:
        - _create_iceberg_resources() is called with plugins
        - Returned Definitions has resources dict with "iceberg" key
        """
        from dagster import Definitions

        mock_io_manager = MagicMock()

        with patch(
            "floe_orchestrator_dagster.resources.iceberg.try_create_iceberg_resources"
        ) as mock_try_create:
            mock_try_create.return_value = {"iceberg": mock_io_manager}

            # Execute
            result = dagster_plugin.create_definitions(valid_compiled_artifacts_with_iceberg)

            # Verify result is Definitions
            assert isinstance(result, Definitions)

            # Verify resources dict has "iceberg" key
            assert isinstance(result.resources, dict)
            assert "iceberg" in result.resources
            assert result.resources["iceberg"] == mock_io_manager

    @pytest.mark.requirement("004d-FR-116")
    def test_create_definitions_with_iceberg_and_assets(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts_with_iceberg: dict[str, Any],
    ) -> None:
        """Test that create_definitions() includes both assets and Iceberg resource."""
        from dagster import Definitions

        mock_io_manager = MagicMock()

        with patch(
            "floe_orchestrator_dagster.resources.iceberg.try_create_iceberg_resources"
        ) as mock_try_create:
            mock_try_create.return_value = {"iceberg": mock_io_manager}

            # Execute
            result = dagster_plugin.create_definitions(valid_compiled_artifacts_with_iceberg)

            # Verify has both assets and resources
            assert isinstance(result, Definitions)
            assert len(result.assets) > 0
            assert isinstance(result.resources, dict)
            assert "iceberg" in result.resources


class TestGracefulDegradation:
    """Test graceful degradation when plugins are not configured.

    Validates T117: Graceful degradation tests.
    """

    @pytest.mark.requirement("004d-FR-117")
    def test_try_create_with_no_plugins_returns_empty_dict(self) -> None:
        """Test try_create_iceberg_resources() returns {} when plugins is None."""
        from floe_orchestrator_dagster.resources.iceberg import (
            try_create_iceberg_resources,
        )

        result = try_create_iceberg_resources(plugins=None)

        assert result == {}

    @pytest.mark.requirement("004d-FR-117")
    def test_try_create_with_catalog_but_no_storage_returns_empty_dict(self) -> None:
        """Test try_create_iceberg_resources() returns {} when storage is None."""
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.iceberg import (
            try_create_iceberg_resources,
        )

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=PluginRef(type="mock-catalog", version="1.0.0"),
            storage=None,
        )

        result = try_create_iceberg_resources(plugins=plugins)

        assert result == {}

    @pytest.mark.requirement("004d-FR-117")
    def test_try_create_with_storage_but_no_catalog_returns_empty_dict(self) -> None:
        """Test try_create_iceberg_resources() returns {} when catalog is None."""
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.iceberg import (
            try_create_iceberg_resources,
        )

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=None,
            storage=PluginRef(type="mock-storage", version="1.0.0"),
        )

        result = try_create_iceberg_resources(plugins=plugins)

        assert result == {}

    @pytest.mark.requirement("004d-FR-117")
    def test_try_create_with_both_none_returns_empty_dict(self) -> None:
        """Test try_create_iceberg_resources() returns {} when both catalog and storage are None."""
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.iceberg import (
            try_create_iceberg_resources,
        )

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=None,
            storage=None,
        )

        result = try_create_iceberg_resources(plugins=plugins)

        assert result == {}

    @pytest.mark.requirement("004d-FR-117")
    def test_plugin_loading_exception_propagates(self) -> None:
        """Test try_create_iceberg_resources() raises when plugin loading fails.

        Exceptions are no longer silently swallowed — they propagate so callers
        can handle failures explicitly rather than receiving an empty dict.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.iceberg import (
            try_create_iceberg_resources,
        )

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=PluginRef(type="mock-catalog", version="1.0.0"),
            storage=PluginRef(type="mock-storage", version="1.0.0"),
        )

        with patch(
            "floe_orchestrator_dagster.resources.iceberg.create_iceberg_resources"
        ) as mock_create:
            mock_create.side_effect = Exception("Plugin not found")

            with pytest.raises(Exception, match="Plugin not found"):
                try_create_iceberg_resources(plugins=plugins)

    @pytest.mark.requirement("004d-FR-117")
    def test_create_definitions_without_plugins_omits_iceberg_resource(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test create_definitions() omits "iceberg" resource when plugins not configured.

        Uses valid_compiled_artifacts fixture which has no catalog or storage.
        """
        from dagster import Definitions

        # Execute with artifacts that have no catalog/storage
        result = dagster_plugin.create_definitions(valid_compiled_artifacts)

        # Verify result is Definitions
        assert isinstance(result, Definitions)

        # Verify resources is empty or doesn't contain "iceberg"
        if result.resources:
            assert "iceberg" not in result.resources


class TestTryCreateIcebergResourcesEdgeCases:
    """Test try_create_iceberg_resources() edge cases.

    Validates T118: try_create_iceberg_resources edge cases.
    """

    @pytest.mark.requirement("004d-FR-118")
    def test_complete_resolved_plugins_returns_iceberg_dict(self) -> None:
        """Test try_create_iceberg_resources() returns dict with "iceberg" key when successful."""
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.iceberg import (
            try_create_iceberg_resources,
        )

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=PluginRef(type="mock-catalog", version="1.0.0"),
            storage=PluginRef(type="mock-storage", version="1.0.0"),
        )

        mock_io_manager = MagicMock()

        with patch(
            "floe_orchestrator_dagster.resources.iceberg.create_iceberg_resources"
        ) as mock_create:
            mock_create.return_value = {"iceberg": mock_io_manager}

            result = try_create_iceberg_resources(plugins=plugins)

            # Verify create_iceberg_resources was called
            mock_create.assert_called_once_with(
                catalog_ref=plugins.catalog,
                storage_ref=plugins.storage,
            )

            # Verify result has "iceberg" key
            assert "iceberg" in result
            assert result["iceberg"] == mock_io_manager

    @pytest.mark.requirement("004d-FR-118")
    def test_exception_during_plugin_loading_logs_and_raises(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test try_create_iceberg_resources() logs error and raises when plugin loading fails."""
        import logging

        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.iceberg import (
            try_create_iceberg_resources,
        )

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=PluginRef(type="mock-catalog", version="1.0.0"),
            storage=PluginRef(type="mock-storage", version="1.0.0"),
        )

        with patch(
            "floe_orchestrator_dagster.resources.iceberg.create_iceberg_resources"
        ) as mock_create:
            mock_create.side_effect = RuntimeError("Plugin loading failed")

            with caplog.at_level(logging.ERROR):
                with pytest.raises(RuntimeError, match="Plugin loading failed"):
                    try_create_iceberg_resources(plugins=plugins)

            # Verify error was logged before raising
            assert any(
                "Failed to create Iceberg resources" in record.message for record in caplog.records
            )

    @pytest.mark.requirement("004d-FR-118")
    def test_exception_during_table_manager_creation_propagates(self) -> None:
        """Test try_create_iceberg_resources() raises when IcebergTableManager creation fails.

        Exceptions are no longer silently swallowed — they propagate so callers
        can handle failures explicitly.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.iceberg import (
            try_create_iceberg_resources,
        )

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=PluginRef(type="mock-catalog", version="1.0.0"),
            storage=PluginRef(type="mock-storage", version="1.0.0"),
        )

        # Patch where imports happen
        with (
            patch("floe_core.plugin_registry.get_registry") as mock_get_registry,
            patch("floe_iceberg.IcebergTableManager") as mock_table_manager_cls,
        ):
            # Setup registry mocks
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.side_effect = [MagicMock(), MagicMock()]

            # Simulate IcebergTableManager creation failure
            mock_table_manager_cls.side_effect = ValueError("Invalid catalog")

            with pytest.raises(ValueError, match="Invalid catalog"):
                try_create_iceberg_resources(plugins=plugins)

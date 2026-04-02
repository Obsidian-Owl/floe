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
            mock_validated_catalog_config = MagicMock()
            mock_validated_storage_config = MagicMock()
            mock_registry.get.side_effect = [mock_catalog_plugin, mock_storage_plugin]
            mock_registry.configure.side_effect = [
                mock_validated_catalog_config,
                mock_validated_storage_config,
            ]
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

            # Verify IcebergTableManager created with re-configured plugins
            mock_table_manager_cls.assert_called_once()
            call_kwargs = mock_table_manager_cls.call_args.kwargs
            # After configure(), plugins are re-instantiated with validated config
            assert call_kwargs["catalog_plugin"] is not None
            assert call_kwargs["storage_plugin"] is not None
            assert "config" in call_kwargs

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


class TestGovernanceThreading:
    """Test governance parameter threading through the Iceberg resource call chain.

    Validates AC-5 (T4): create_definitions() → _create_iceberg_resources() →
    try_create_iceberg_resources() → create_iceberg_resources() MUST accept and
    thread an optional governance parameter. create_iceberg_resources() MUST call
    IcebergTableManagerConfig.from_governance(governance) and pass the resulting
    config to IcebergTableManager(config=config).
    """

    @pytest.mark.requirement("AC-5-happy-path")
    def test_create_iceberg_resources_with_governance_passes_config_to_table_manager(
        self,
    ) -> None:
        """Test create_iceberg_resources() with governance creates config via from_governance.

        When governance has lifecycle fields (default_ttl_hours, snapshot_keep_last),
        the factory MUST call IcebergTableManagerConfig.from_governance(governance)
        and pass the resulting config to IcebergTableManager(config=config).

        Asserts specific config values derived from governance, not just that
        config is "truthy" — a lazy implementation that ignores governance would fail.
        """
        import types

        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.iceberg import create_iceberg_resources

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

        # Governance object using duck typing (SimpleNamespace per AC-10)
        governance = types.SimpleNamespace(
            default_ttl_hours=24,
            snapshot_keep_last=3,
        )

        mock_catalog_plugin = MagicMock()
        mock_storage_plugin = MagicMock()

        with (
            patch("floe_core.plugin_registry.get_registry") as mock_get_registry,
            patch("floe_iceberg.IcebergTableManager") as mock_table_manager_cls,
            patch(
                "floe_orchestrator_dagster.io_manager.create_iceberg_io_manager"
            ) as mock_create_io_manager,
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.side_effect = [mock_catalog_plugin, mock_storage_plugin]
            mock_table_manager_cls.return_value = MagicMock()
            mock_create_io_manager.return_value = MagicMock()

            # Act: pass governance to create_iceberg_resources
            create_iceberg_resources(
                catalog_ref=catalog_ref,
                storage_ref=storage_ref,
                default_namespace="test_ns",
                governance=governance,
            )

            # Assert: IcebergTableManager was called with config= keyword
            mock_table_manager_cls.assert_called_once()
            call_kwargs = mock_table_manager_cls.call_args
            assert "config" in call_kwargs.kwargs or (len(call_kwargs.args) > 2), (
                "IcebergTableManager must be called with config= parameter"
            )

            # Extract the config that was passed
            config = call_kwargs.kwargs.get("config")
            assert config is not None, (
                "IcebergTableManager must receive a non-None config when governance is provided"
            )

            # Assert governance-derived values on the config
            assert config.min_snapshots_to_keep == 3, (
                "min_snapshots_to_keep must be set from governance.snapshot_keep_last"
            )

            # 24 hours * 3600 seconds * 1000 milliseconds = 86400000
            assert (
                config.default_table_properties["history.expire.max-snapshot-age-ms"] == "86400000"
            ), "default_ttl_hours must be converted to max-snapshot-age-ms table property"

            # Also verify the min-snapshots-to-keep table property
            assert config.default_table_properties["history.expire.min-snapshots-to-keep"] == "3", (
                "snapshot_keep_last must be set as min-snapshots-to-keep table property"
            )

    @pytest.mark.requirement("AC-5-none-path")
    def test_create_iceberg_resources_with_governance_none_uses_default_config(
        self,
    ) -> None:
        """Test create_iceberg_resources() with governance=None uses default config.

        When governance is None, IcebergTableManager MUST still receive a config
        parameter, but it should have default values (min_snapshots_to_keep == 10).
        This must NOT crash — it preserves current behavior.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.iceberg import create_iceberg_resources

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

        mock_catalog_plugin = MagicMock()
        mock_storage_plugin = MagicMock()

        with (
            patch("floe_core.plugin_registry.get_registry") as mock_get_registry,
            patch("floe_iceberg.IcebergTableManager") as mock_table_manager_cls,
            patch(
                "floe_orchestrator_dagster.io_manager.create_iceberg_io_manager"
            ) as mock_create_io_manager,
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.side_effect = [mock_catalog_plugin, mock_storage_plugin]
            mock_table_manager_cls.return_value = MagicMock()
            mock_create_io_manager.return_value = MagicMock()

            # Act: pass governance=None explicitly
            create_iceberg_resources(
                catalog_ref=catalog_ref,
                storage_ref=storage_ref,
                default_namespace="test_ns",
                governance=None,
            )

            # Assert: IcebergTableManager was called with config=
            mock_table_manager_cls.assert_called_once()
            call_kwargs = mock_table_manager_cls.call_args
            config = call_kwargs.kwargs.get("config")
            assert config is not None, (
                "IcebergTableManager must receive a config even when governance is None"
            )

            # Assert default config values (governance=None means defaults)
            assert config.min_snapshots_to_keep == 10, (
                "Default min_snapshots_to_keep must be 10 when governance is None"
            )

    @pytest.mark.requirement("AC-5-none-path")
    def test_create_iceberg_resources_without_governance_kwarg_uses_default_config(
        self,
    ) -> None:
        """Test create_iceberg_resources() without governance kwarg at all uses defaults.

        The governance parameter must be optional (default None). Calling without
        it must produce the same result as governance=None.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.iceberg import create_iceberg_resources

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

            # Act: call WITHOUT governance keyword — must not crash
            create_iceberg_resources(
                catalog_ref=catalog_ref,
                storage_ref=storage_ref,
            )

            # Assert: IcebergTableManager receives config with defaults
            mock_table_manager_cls.assert_called_once()
            call_kwargs = mock_table_manager_cls.call_args
            config = call_kwargs.kwargs.get("config")
            assert config is not None, (
                "IcebergTableManager must receive config even without governance kwarg"
            )
            assert config.min_snapshots_to_keep == 10, (
                "Default min_snapshots_to_keep must be 10 when governance is omitted"
            )

    @pytest.mark.requirement("AC-5-call-chain")
    def test_try_create_iceberg_resources_threads_governance(self) -> None:
        """Test try_create_iceberg_resources() passes governance to create_iceberg_resources().

        The intermediate function must not swallow or ignore the governance parameter.
        """
        import types

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

        governance = types.SimpleNamespace(
            default_ttl_hours=48,
            snapshot_keep_last=5,
        )

        with patch(
            "floe_orchestrator_dagster.resources.iceberg.create_iceberg_resources"
        ) as mock_create:
            mock_create.return_value = {"iceberg": MagicMock()}

            # Act
            try_create_iceberg_resources(plugins=plugins, governance=governance)

            # Assert governance was forwarded
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            assert call_kwargs.kwargs.get("governance") is governance, (
                "try_create_iceberg_resources must forward the governance object "
                "to create_iceberg_resources, not drop it"
            )

    @pytest.mark.requirement("AC-5-call-chain")
    def test_try_create_iceberg_resources_threads_governance_none(self) -> None:
        """Test try_create_iceberg_resources() passes governance=None correctly."""
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
            mock_create.return_value = {"iceberg": MagicMock()}

            # Act: governance=None (default)
            try_create_iceberg_resources(plugins=plugins, governance=None)

            # Assert governance=None was forwarded
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            assert call_kwargs.kwargs.get("governance") is None, (
                "try_create_iceberg_resources must forward governance=None "
                "to create_iceberg_resources"
            )

    @pytest.mark.requirement("AC-5-call-chain")
    def test_plugin_method_create_iceberg_resources_threads_governance(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test DagsterOrchestratorPlugin._create_iceberg_resources() threads governance.

        The plugin method must forward governance to try_create_iceberg_resources().
        """
        import types

        governance = types.SimpleNamespace(
            default_ttl_hours=72,
            snapshot_keep_last=7,
        )

        with patch(
            "floe_orchestrator_dagster.resources.iceberg.try_create_iceberg_resources"
        ) as mock_try_create:
            mock_try_create.return_value = {"iceberg": MagicMock()}

            # Act: call the plugin's private method with governance
            dagster_plugin._create_iceberg_resources(
                plugins=MagicMock(),
                governance=governance,
            )

            # Assert governance was forwarded
            mock_try_create.assert_called_once()
            call_kwargs = mock_try_create.call_args
            assert call_kwargs.kwargs.get("governance") is governance or (
                len(call_kwargs.args) > 1 and call_kwargs.args[1] is governance
            ), "_create_iceberg_resources must forward governance to try_create_iceberg_resources"

    @pytest.mark.requirement("AC-5-happy-path")
    def test_governance_config_is_real_iceberg_table_manager_config(self) -> None:
        """Test that governance produces a real IcebergTableManagerConfig, not a mock.

        This catches an implementation that passes governance directly instead of
        calling IcebergTableManagerConfig.from_governance().
        """
        import types

        from floe_core.schemas.compiled_artifacts import PluginRef
        from floe_iceberg.models import IcebergTableManagerConfig

        from floe_orchestrator_dagster.resources.iceberg import create_iceberg_resources

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

        governance = types.SimpleNamespace(
            default_ttl_hours=24,
            snapshot_keep_last=3,
        )

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

            create_iceberg_resources(
                catalog_ref=catalog_ref,
                storage_ref=storage_ref,
                governance=governance,
            )

            # Extract config passed to IcebergTableManager
            config = mock_table_manager_cls.call_args.kwargs.get("config")
            assert isinstance(config, IcebergTableManagerConfig), (
                f"config must be an IcebergTableManagerConfig instance, "
                f"got {type(config).__name__}. Implementation must call "
                f"IcebergTableManagerConfig.from_governance(governance)"
            )


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
                governance=None,
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

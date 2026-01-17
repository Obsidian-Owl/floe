"""Contract tests for floe-core public API stability.

These tests validate that the floe-core public API remains stable for consumers.
They test the external interface that plugin packages and orchestration packages
would depend on.

Root-level contract tests focus on:
- Public export availability (what consumers import)
- Plugin ABC inheritance contracts (how plugins extend ABCs)
- Registry integration (how consumers discover and use plugins)

Package-level tests (in floe-core/tests/contract/) test internal contracts.

Requirements Covered:
- FR-001: Plugin registry public API stability
- FR-002: PluginType enum stability for entry point groups
- SC-001: Backward compatibility for plugin implementations
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pydantic import BaseModel


class TestFloeCorePubicExports:
    """Contract tests for floe-core public exports.

    These tests ensure that all documented public exports are available
    and can be imported by consumer packages.
    """

    @pytest.mark.requirement("FR-001")
    def test_core_exports_available(self) -> None:
        """Verify all core exports are importable from floe_core.

        Consumer packages should be able to import these directly:
        - from floe_core import PluginRegistry, get_registry, PluginType
        """
        from floe_core import (
            PluginRegistry,
            PluginType,
            get_registry,
        )

        # Verify they are the correct types
        assert isinstance(PluginRegistry, type)
        assert callable(get_registry)
        # PluginType is an enum class
        assert hasattr(PluginType, "COMPUTE")

    @pytest.mark.requirement("FR-001")
    def test_plugin_metadata_exports_available(self) -> None:
        """Verify plugin metadata exports are importable.

        Consumer packages need these for implementing plugins:
        - PluginMetadata ABC
        - HealthState, HealthStatus for health checks
        """
        from floe_core import (
            HealthState,
            HealthStatus,
            PluginMetadata,
        )

        assert isinstance(PluginMetadata, type)
        assert hasattr(HealthState, "HEALTHY")
        assert hasattr(HealthState, "DEGRADED")
        assert hasattr(HealthState, "UNHEALTHY")
        assert isinstance(HealthStatus, type)

    @pytest.mark.requirement("FR-001")
    def test_error_exports_available(self) -> None:
        """Verify error classes are importable for exception handling.

        Consumer packages need these for proper error handling:
        - PluginError (base class)
        - PluginNotFoundError, PluginIncompatibleError, etc.
        """
        from floe_core import (
            CircularDependencyError,
            DuplicatePluginError,
            MissingDependencyError,
            PluginConfigurationError,
            PluginError,
            PluginIncompatibleError,
            PluginNotFoundError,
            PluginStartupError,
        )

        # All should be Exception subclasses
        assert issubclass(PluginError, Exception)
        assert issubclass(PluginNotFoundError, PluginError)
        assert issubclass(PluginIncompatibleError, PluginError)
        assert issubclass(PluginConfigurationError, PluginError)
        assert issubclass(DuplicatePluginError, PluginError)
        assert issubclass(CircularDependencyError, PluginError)
        assert issubclass(MissingDependencyError, PluginError)
        assert issubclass(PluginStartupError, PluginError)

    @pytest.mark.requirement("FR-001")
    def test_version_compat_exports_available(self) -> None:
        """Verify version compatibility exports are available.

        Consumer packages need these for version checking:
        - FLOE_PLUGIN_API_VERSION
        - is_compatible function
        """
        from floe_core import (
            FLOE_PLUGIN_API_MIN_VERSION,
            FLOE_PLUGIN_API_VERSION,
            is_compatible,
        )

        assert isinstance(FLOE_PLUGIN_API_VERSION, str)
        assert isinstance(FLOE_PLUGIN_API_MIN_VERSION, str)
        assert callable(is_compatible)

    @pytest.mark.requirement("FR-001")
    def test_plugin_abc_exports_available(self) -> None:
        """Verify all 11 plugin ABC exports are available.

        Plugin packages need these for implementing specific plugin types.
        """
        from floe_core import (
            CatalogPlugin,
            ComputePlugin,
            DBTPlugin,
            IdentityPlugin,
            IngestionPlugin,
            LineageBackendPlugin,
            OrchestratorPlugin,
            SecretsPlugin,
            SemanticLayerPlugin,
            StoragePlugin,
            TelemetryBackendPlugin,
        )

        # All should be classes (ABCs)
        plugin_abcs = [
            CatalogPlugin,
            ComputePlugin,
            DBTPlugin,
            IdentityPlugin,
            IngestionPlugin,
            LineageBackendPlugin,
            OrchestratorPlugin,
            SecretsPlugin,
            SemanticLayerPlugin,
            StoragePlugin,
            TelemetryBackendPlugin,
        ]

        for abc in plugin_abcs:
            assert isinstance(abc, type), f"{abc.__name__} should be a class"


class TestPluginImplementationContract:
    """Contract tests for plugin implementation patterns.

    These tests verify that concrete plugins can properly implement
    the plugin ABCs, following the documented patterns.
    """

    @pytest.mark.requirement("SC-001")
    def test_minimal_plugin_implementation(self) -> None:
        """Verify minimal plugin implementation works.

        A plugin with just the required abstract properties should
        be instantiable and functional.
        """
        from floe_core import HealthState, HealthStatus, PluginMetadata

        class MinimalPlugin(PluginMetadata):
            """Minimal concrete plugin implementation."""

            @property
            def name(self) -> str:
                return "minimal-test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        plugin = MinimalPlugin()

        # Required properties work
        assert plugin.name == "minimal-test"
        assert plugin.version == "1.0.0"
        assert plugin.floe_api_version == "1.0"

        # Default implementations work
        assert plugin.description == ""
        assert plugin.dependencies == []
        assert plugin.get_config_schema() is None

        # Lifecycle methods work (no-op)
        plugin.startup()  # Should not raise
        plugin.shutdown()  # Should not raise

        # Health check returns healthy by default
        health = plugin.health_check()
        assert isinstance(health, HealthStatus)
        assert health.state == HealthState.HEALTHY

    @pytest.mark.requirement("SC-001")
    def test_plugin_with_dependencies(self) -> None:
        """Verify plugin with dependencies can declare them.

        Plugins should be able to override the dependencies property
        to declare their dependencies.
        """
        from floe_core import PluginMetadata

        class DependentPlugin(PluginMetadata):
            """Plugin that depends on other plugins."""

            @property
            def name(self) -> str:
                return "dependent"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["base-plugin", "other-plugin"]

        plugin = DependentPlugin()
        assert plugin.dependencies == ["base-plugin", "other-plugin"]

    @pytest.mark.requirement("SC-001")
    def test_plugin_with_config_schema(self) -> None:
        """Verify plugin with Pydantic config schema works.

        Plugins should be able to provide a configuration schema
        for validation.
        """
        from floe_core import PluginMetadata
        from pydantic import BaseModel, Field

        class TestConfig(BaseModel):
            """Test plugin configuration."""

            host: str = Field(default="localhost")
            port: int = Field(default=5432)

        class ConfigurablePlugin(PluginMetadata):
            """Plugin with configuration schema."""

            @property
            def name(self) -> str:
                return "configurable"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_config_schema(self) -> type[BaseModel]:
                return TestConfig

        plugin = ConfigurablePlugin()
        schema = plugin.get_config_schema()

        assert schema is TestConfig
        # Can instantiate the schema
        config = schema(host="example.com", port=8080)
        assert config.host == "example.com"
        assert config.port == 8080


class TestRegistryIntegrationContract:
    """Contract tests for registry integration.

    These tests verify that the registry can properly discover,
    register, and manage plugins.
    """

    @pytest.mark.requirement("FR-001")
    def test_registry_can_register_plugin(self) -> None:
        """Verify plugins can be registered with the registry.

        Consumer packages should be able to manually register
        plugins for testing or custom plugin loading.
        """
        from floe_core import PluginMetadata, PluginRegistry, PluginType

        class TestPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "test-register"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        registry = PluginRegistry()
        plugin = TestPlugin()

        # Register should work
        registry.register(PluginType.COMPUTE, plugin)

        # Should be retrievable
        retrieved = registry.get(PluginType.COMPUTE, "test-register")
        assert retrieved is plugin

    @pytest.mark.requirement("FR-001")
    def test_registry_not_found_error(self) -> None:
        """Verify PluginNotFoundError raised for missing plugins.

        Consumers should be able to catch this specific error.
        """
        from floe_core import PluginNotFoundError, PluginRegistry, PluginType

        registry = PluginRegistry()

        with pytest.raises(PluginNotFoundError) as exc_info:
            registry.get(PluginType.COMPUTE, "nonexistent")

        assert exc_info.value.plugin_type == PluginType.COMPUTE
        assert exc_info.value.name == "nonexistent"

    @pytest.mark.requirement("FR-001")
    def test_registry_configure_with_schema(self) -> None:
        """Verify registry can configure plugins with validation.

        Consumer packages should be able to configure plugins
        using the registry's configure() method.
        """
        from floe_core import PluginMetadata, PluginRegistry, PluginType
        from pydantic import BaseModel, Field

        class PluginConfig(BaseModel):
            threads: int = Field(default=4, ge=1)
            debug: bool = False

        class ConfigTestPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "config-test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_config_schema(self) -> type[BaseModel]:
                return PluginConfig

        registry = PluginRegistry()
        plugin = ConfigTestPlugin()
        registry.register(PluginType.COMPUTE, plugin)

        # Configure should validate and store
        validated = registry.configure(
            PluginType.COMPUTE,
            "config-test",
            {"threads": 8, "debug": True},
        )

        assert validated is not None
        assert validated.threads == 8  # type: ignore[union-attr]
        assert validated.debug is True  # type: ignore[union-attr]

        # Should be retrievable
        stored = registry.get_config(PluginType.COMPUTE, "config-test")
        assert stored is validated

    @pytest.mark.requirement("FR-002")
    def test_plugin_type_entry_points(self) -> None:
        """Verify PluginType entry point groups are stable.

        Plugin packages use these entry point group names in their
        pyproject.toml. Changing them would break plugin discovery.
        """
        from floe_core import PluginType

        # These exact values are part of the public contract
        expected = {
            PluginType.COMPUTE: "floe.computes",
            PluginType.ORCHESTRATOR: "floe.orchestrators",
            PluginType.CATALOG: "floe.catalogs",
            PluginType.STORAGE: "floe.storage",
            PluginType.TELEMETRY_BACKEND: "floe.telemetry_backends",
            PluginType.LINEAGE_BACKEND: "floe.lineage_backends",
            PluginType.DBT: "floe.dbt",
            PluginType.SEMANTIC_LAYER: "floe.semantic_layers",
            PluginType.INGESTION: "floe.ingestion",
            PluginType.SECRETS: "floe.secrets",
            PluginType.IDENTITY: "floe.identity",
        }

        for plugin_type, expected_group in expected.items():
            assert plugin_type.entry_point_group == expected_group, (
                f"{plugin_type.name} entry point changed from "
                f"{expected_group} to {plugin_type.entry_point_group}"
            )

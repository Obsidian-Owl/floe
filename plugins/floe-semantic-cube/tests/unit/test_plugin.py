"""Unit tests for CubeSemanticPlugin.

Tests cover: ABC inheritance, metadata properties, config schema,
API endpoints, Helm values, security context, datasource config,
health check, and lifecycle methods.

Requirements Covered:
    - FR-003: CubeSemanticPlugin implements SemanticLayerPlugin ABC
    - FR-006: Plugin metadata properties
    - FR-008: Error handling
    - FR-009: Health check
    - FR-032: Security context with namespace/roles
    - FR-033: Admin bypass in security context
    - FR-034: API endpoint configuration
"""

from __future__ import annotations

import pytest
from floe_core.plugin_metadata import HealthState, HealthStatus, PluginMetadata
from floe_core.plugins.semantic import SemanticLayerPlugin

from floe_semantic_cube.config import CubeSemanticConfig
from floe_semantic_cube.plugin import CubeSemanticPlugin


@pytest.fixture
def config() -> CubeSemanticConfig:
    """Create a test CubeSemanticConfig."""
    return CubeSemanticConfig(
        server_url="http://localhost:4000",
        api_secret="test-secret",
        database_name="test_analytics",
    )


@pytest.fixture
def plugin(config: CubeSemanticConfig) -> CubeSemanticPlugin:
    """Create a CubeSemanticPlugin instance for testing."""
    return CubeSemanticPlugin(config=config)


class TestCubeSemanticPluginInheritance:
    """Tests for ABC compliance."""

    @pytest.mark.requirement("FR-003")
    def test_inherits_semantic_layer_plugin(self) -> None:
        """Test that CubeSemanticPlugin is a SemanticLayerPlugin."""
        assert issubclass(CubeSemanticPlugin, SemanticLayerPlugin)

    @pytest.mark.requirement("FR-003")
    def test_inherits_plugin_metadata(self) -> None:
        """Test that CubeSemanticPlugin inherits PluginMetadata."""
        assert issubclass(CubeSemanticPlugin, PluginMetadata)

    @pytest.mark.requirement("FR-003")
    def test_is_instantiable(self, plugin: CubeSemanticPlugin) -> None:
        """Test that CubeSemanticPlugin can be instantiated."""
        assert isinstance(plugin, CubeSemanticPlugin)
        assert isinstance(plugin, SemanticLayerPlugin)


class TestCubeSemanticPluginMetadata:
    """Tests for plugin metadata properties."""

    @pytest.mark.requirement("FR-006")
    def test_name(self, plugin: CubeSemanticPlugin) -> None:
        """Test plugin name is 'cube'."""
        assert plugin.name == "cube"

    @pytest.mark.requirement("FR-006")
    def test_version(self, plugin: CubeSemanticPlugin) -> None:
        """Test plugin version is '0.1.0'."""
        assert plugin.version == "0.1.0"

    @pytest.mark.requirement("FR-006")
    def test_floe_api_version(self, plugin: CubeSemanticPlugin) -> None:
        """Test floe API version is '1.0'."""
        assert plugin.floe_api_version == "1.0"

    @pytest.mark.requirement("FR-006")
    def test_description(self, plugin: CubeSemanticPlugin) -> None:
        """Test plugin has a description."""
        assert plugin.description is not None
        assert len(plugin.description) > 0
        assert "cube" in plugin.description.lower() or "semantic" in plugin.description.lower()


class TestCubeSemanticPluginConfigSchema:
    """Tests for get_config_schema()."""

    @pytest.mark.requirement("FR-003")
    def test_get_config_schema_returns_config_class(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test that get_config_schema returns CubeSemanticConfig."""
        schema = plugin.get_config_schema()
        assert schema is CubeSemanticConfig


class TestCubeSemanticPluginApiEndpoints:
    """Tests for get_api_endpoints()."""

    @pytest.mark.requirement("FR-034")
    def test_api_endpoints_dict_structure(self, plugin: CubeSemanticPlugin) -> None:
        """Test that get_api_endpoints returns a dict with expected keys."""
        endpoints = plugin.get_api_endpoints()
        assert isinstance(endpoints, dict)
        assert "rest" in endpoints
        assert "graphql" in endpoints
        assert "sql" in endpoints
        assert "health" in endpoints

    @pytest.mark.requirement("FR-034")
    def test_api_endpoints_contain_server_url(self, plugin: CubeSemanticPlugin) -> None:
        """Test that endpoint URLs contain the configured server URL."""
        endpoints = plugin.get_api_endpoints()
        for endpoint_url in endpoints.values():
            assert endpoint_url.startswith("http://localhost:4000")

    @pytest.mark.requirement("FR-034")
    def test_api_endpoints_with_custom_url(self) -> None:
        """Test endpoints with a custom server URL."""
        config = CubeSemanticConfig(
            server_url="https://cube.prod.example.com",
            api_secret="secret",
        )
        p = CubeSemanticPlugin(config=config)
        endpoints = p.get_api_endpoints()
        assert endpoints["rest"].startswith("https://cube.prod.example.com")


class TestCubeSemanticPluginHelmValues:
    """Tests for get_helm_values_override()."""

    @pytest.mark.requirement("FR-003")
    def test_helm_values_is_dict(self, plugin: CubeSemanticPlugin) -> None:
        """Test that get_helm_values_override returns a dict."""
        values = plugin.get_helm_values_override()
        assert isinstance(values, dict)

    @pytest.mark.requirement("FR-003")
    def test_helm_values_has_cube_key(self, plugin: CubeSemanticPlugin) -> None:
        """Test that Helm values contain 'cube' key."""
        values = plugin.get_helm_values_override()
        assert "cube" in values

    @pytest.mark.requirement("FR-003")
    def test_helm_values_cube_enabled(self, plugin: CubeSemanticPlugin) -> None:
        """Test that Cube is enabled in Helm values."""
        values = plugin.get_helm_values_override()
        assert values["cube"]["enabled"] is True

    @pytest.mark.requirement("FR-003")
    def test_helm_values_database_name(self, plugin: CubeSemanticPlugin) -> None:
        """Test that database name is set in Helm values."""
        values = plugin.get_helm_values_override()
        env = values["cube"]["api"]["env"]
        assert env["CUBEJS_DB_NAME"] == "test_analytics"


class TestCubeSemanticPluginSecurityContext:
    """Tests for get_security_context()."""

    @pytest.mark.requirement("FR-032")
    def test_security_context_basic(self, plugin: CubeSemanticPlugin) -> None:
        """Test security context with basic namespace and roles."""
        context = plugin.get_security_context(
            namespace="tenant_acme",
            roles=["analyst", "viewer"],
        )
        assert context["tenant_id"] == "tenant_acme"
        assert context["allowed_roles"] == ["analyst", "viewer"]

    @pytest.mark.requirement("FR-033")
    def test_security_context_admin_bypass(self, plugin: CubeSemanticPlugin) -> None:
        """Test that admin role enables RLS bypass."""
        context = plugin.get_security_context(
            namespace="tenant_acme",
            roles=["admin"],
        )
        assert context["bypass_rls"] is True

    @pytest.mark.requirement("FR-033")
    def test_security_context_no_admin_no_bypass(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test that non-admin roles do not get RLS bypass."""
        context = plugin.get_security_context(
            namespace="tenant_acme",
            roles=["analyst"],
        )
        assert "bypass_rls" not in context

    @pytest.mark.requirement("FR-032")
    def test_security_context_empty_namespace(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test security context with empty namespace."""
        context = plugin.get_security_context(namespace="", roles=["viewer"])
        assert context["tenant_id"] == ""

    @pytest.mark.requirement("FR-032")
    def test_security_context_special_characters(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test security context with special characters in namespace."""
        context = plugin.get_security_context(
            namespace="tenant-with_special.chars",
            roles=["viewer"],
        )
        assert context["tenant_id"] == "tenant-with_special.chars"

    @pytest.mark.requirement("FR-032")
    def test_security_context_long_namespace(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test security context with very long namespace."""
        long_ns = "a" * 500
        context = plugin.get_security_context(namespace=long_ns, roles=["viewer"])
        assert context["tenant_id"] == long_ns

    @pytest.mark.requirement("FR-032")
    def test_security_context_empty_roles(self, plugin: CubeSemanticPlugin) -> None:
        """Test security context with empty roles list."""
        context = plugin.get_security_context(namespace="tenant_x", roles=[])
        assert context["allowed_roles"] == []


class TestCubeSemanticPluginHealthCheck:
    """Tests for health_check()."""

    @pytest.mark.requirement("FR-009")
    def test_health_check_returns_health_status(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test that health_check returns a HealthStatus."""
        status = plugin.health_check()
        assert isinstance(status, HealthStatus)

    @pytest.mark.requirement("FR-009")
    def test_health_check_default_unhealthy(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test that health check returns UNHEALTHY when not connected."""
        status = plugin.health_check()
        assert status.state == HealthState.UNHEALTHY


class TestCubeSemanticPluginLifecycle:
    """Tests for startup()/shutdown() lifecycle."""

    @pytest.mark.requirement("FR-008")
    def test_startup_does_not_raise(self, plugin: CubeSemanticPlugin) -> None:
        """Test that startup() completes without error."""
        plugin.startup()

    @pytest.mark.requirement("FR-008")
    def test_shutdown_does_not_raise(self, plugin: CubeSemanticPlugin) -> None:
        """Test that shutdown() completes without error."""
        plugin.shutdown()

    @pytest.mark.requirement("FR-008")
    def test_startup_shutdown_lifecycle(self, plugin: CubeSemanticPlugin) -> None:
        """Test full startup/shutdown lifecycle."""
        plugin.startup()
        plugin.shutdown()

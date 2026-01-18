"""Integration tests for Keycloak plugin entry point discovery.

Task: T060
Requirements: 7A-FR-030 (KeycloakPlugin as default OIDC identity provider)
"""

from __future__ import annotations

import sys
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_core.plugins.identity import IdentityPlugin


class TestKeycloakPluginDiscovery:
    """Tests for Keycloak plugin entry point discovery."""

    @pytest.mark.requirement("7A-FR-030")
    def test_plugin_discovered_via_entry_point(self) -> None:
        """Test that plugin is discovered via floe.identity entry point."""
        # Get all identity plugins
        eps = entry_points(group="floe.identity")

        # Find keycloak plugin
        keycloak_eps = [ep for ep in eps if ep.name == "keycloak"]

        assert len(keycloak_eps) == 1, "Keycloak plugin should be registered"
        assert keycloak_eps[0].name == "keycloak"

    @pytest.mark.requirement("7A-FR-030")
    def test_plugin_loads_successfully(self) -> None:
        """Test that plugin loads successfully from entry point."""
        eps = entry_points(group="floe.identity")
        keycloak_eps = [ep for ep in eps if ep.name == "keycloak"]

        assert len(keycloak_eps) == 1, "Keycloak plugin should be registered"

        # Load the plugin class
        plugin_class = keycloak_eps[0].load()

        assert plugin_class is not None
        assert callable(plugin_class)

    @pytest.mark.requirement("7A-FR-030")
    def test_plugin_has_required_metadata(self) -> None:
        """Test that plugin has required metadata (name, version, floe_api_version)."""
        eps = entry_points(group="floe.identity")
        keycloak_eps = [ep for ep in eps if ep.name == "keycloak"]

        assert len(keycloak_eps) == 1

        plugin_class = keycloak_eps[0].load()

        # Check class-level metadata attributes
        assert hasattr(plugin_class, "name")
        assert hasattr(plugin_class, "version")
        assert hasattr(plugin_class, "floe_api_version")

        assert plugin_class.name == "keycloak"
        assert isinstance(plugin_class.version, str)
        assert isinstance(plugin_class.floe_api_version, str)

    @pytest.mark.requirement("7A-FR-030")
    def test_plugin_has_description(self) -> None:
        """Test that plugin has a description."""
        eps = entry_points(group="floe.identity")
        keycloak_eps = [ep for ep in eps if ep.name == "keycloak"]

        assert len(keycloak_eps) == 1

        plugin_class = keycloak_eps[0].load()

        assert hasattr(plugin_class, "description")
        assert isinstance(plugin_class.description, str)
        assert len(plugin_class.description) > 0

    @pytest.mark.requirement("7A-FR-030")
    def test_plugin_implements_identity_interface(self) -> None:
        """Test that plugin implements IdentityPlugin interface."""
        from floe_core.plugins.identity import IdentityPlugin

        eps = entry_points(group="floe.identity")
        keycloak_eps = [ep for ep in eps if ep.name == "keycloak"]

        assert len(keycloak_eps) == 1

        plugin_class = keycloak_eps[0].load()

        # Check that it's a subclass of IdentityPlugin
        assert issubclass(plugin_class, IdentityPlugin)

    @pytest.mark.requirement("7A-FR-030")
    def test_plugin_has_required_methods(self) -> None:
        """Test that plugin has all required methods from IdentityPlugin."""
        eps = entry_points(group="floe.identity")
        keycloak_eps = [ep for ep in eps if ep.name == "keycloak"]

        assert len(keycloak_eps) == 1

        plugin_class = keycloak_eps[0].load()

        # Required methods from IdentityPlugin ABC
        required_methods = [
            "authenticate",
            "get_user_info",
            "validate_token",
            "startup",
            "shutdown",
            "health_check",
        ]

        for method_name in required_methods:
            assert hasattr(plugin_class, method_name), (
                f"Plugin missing required method: {method_name}"
            )

    @pytest.mark.requirement("7A-FR-030")
    def test_plugin_entry_point_module_path(self) -> None:
        """Test that entry point points to correct module path."""
        eps = entry_points(group="floe.identity")
        keycloak_eps = [ep for ep in eps if ep.name == "keycloak"]

        assert len(keycloak_eps) == 1

        ep = keycloak_eps[0]

        # Check module path
        assert "floe_identity_keycloak" in ep.value


class TestKeycloakPluginImport:
    """Tests for direct import of Keycloak plugin."""

    @pytest.mark.requirement("7A-FR-030")
    def test_import_plugin_directly(self) -> None:
        """Test that plugin can be imported directly."""
        from floe_identity_keycloak import KeycloakIdentityPlugin

        assert KeycloakIdentityPlugin is not None

    @pytest.mark.requirement("7A-FR-030")
    def test_import_config_directly(self) -> None:
        """Test that config can be imported directly."""
        from floe_identity_keycloak import KeycloakIdentityConfig

        assert KeycloakIdentityConfig is not None

    @pytest.mark.requirement("7A-FR-030")
    def test_import_from_package_init(self) -> None:
        """Test that all public symbols are exported from __init__."""
        import floe_identity_keycloak

        # Check expected exports
        assert hasattr(floe_identity_keycloak, "KeycloakIdentityPlugin")
        assert hasattr(floe_identity_keycloak, "KeycloakIdentityConfig")


class TestKeycloakPluginInstantiation:
    """Tests for instantiating Keycloak plugin."""

    @pytest.mark.requirement("7A-FR-030")
    def test_plugin_instantiation_with_config(self) -> None:
        """Test that plugin can be instantiated with config."""
        from pydantic import SecretStr

        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)

        assert plugin is not None
        assert plugin.name == "keycloak"

    @pytest.mark.requirement("7A-FR-030")
    def test_plugin_metadata_after_instantiation(self) -> None:
        """Test plugin metadata is accessible after instantiation."""
        from pydantic import SecretStr

        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)

        assert plugin.name == "keycloak"
        assert plugin.version is not None
        assert plugin.floe_api_version is not None
        assert plugin.description is not None

"""Integration tests for Keycloak plugin entry point discovery.

Task: T060, T078
Phase: 7, 10 - US7 (Test Duplication Reduction)
Requirements: 7A-FR-030 (KeycloakPlugin as default OIDC identity provider)

This module inherits from BasePluginDiscoveryTests to reduce test duplication
while adding Keycloak-specific discovery tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import pytest
from pydantic import SecretStr
from testing.base_classes import BasePluginDiscoveryTests

if TYPE_CHECKING:
    pass


class TestKeycloakPluginDiscovery(BasePluginDiscoveryTests):
    """Tests for Keycloak plugin entry point discovery.

    Inherits standard discovery tests from BasePluginDiscoveryTests:
    - test_entry_point_is_registered
    - test_exactly_one_entry_point
    - test_entry_point_module_path
    - test_plugin_loads_successfully
    - test_plugin_can_be_instantiated
    - test_instantiated_plugin_has_correct_name
    - test_plugin_has_required_metadata_attributes
    - test_plugin_metadata_values_not_none
    - test_plugin_inherits_from_expected_abc
    - test_plugin_instance_is_abc_instance
    - test_plugin_has_lifecycle_methods
    """

    entry_point_group: ClassVar[str] = "floe.identity"
    expected_name: ClassVar[str] = "keycloak"
    expected_module_prefix: ClassVar[str] = "floe_identity_keycloak"
    expected_class_name: ClassVar[str] = "KeycloakIdentityPlugin"

    @property
    def expected_plugin_abc(self) -> type[Any]:
        """Return the expected ABC for type checking."""
        from floe_core.plugins.identity import IdentityPlugin

        return IdentityPlugin

    def create_plugin_instance(self, plugin_class: type[Any]) -> Any:
        """Create Keycloak plugin with required configuration.

        Args:
            plugin_class: The KeycloakIdentityPlugin class.

        Returns:
            Configured KeycloakIdentityPlugin instance.
        """
        from floe_identity_keycloak import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("test-secret"),
        )
        return plugin_class(config=config)

    # =========================================================================
    # Identity-Specific Method Tests
    # =========================================================================

    @pytest.mark.requirement("7A-FR-030")
    def test_plugin_has_identity_specific_methods(self) -> None:
        """Test that plugin has IdentityPlugin-specific methods beyond lifecycle."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()

        # IdentityPlugin-specific methods (beyond standard lifecycle)
        identity_methods = [
            "authenticate",
            "get_user_info",
            "validate_token",
        ]

        for method_name in identity_methods:
            assert hasattr(
                plugin_class, method_name
            ), f"Plugin missing IdentityPlugin method: {method_name}"


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

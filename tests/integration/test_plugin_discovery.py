"""Integration tests for plugin discovery across all plugin types.

This module validates that all secrets and identity plugins can be discovered
via entry points in a single test session. These tests ensure the plugin
architecture is correctly configured.

Task: Arch Review Recommendation P-002
Requirements: 7A-FR-002 (SecretsPlugin), 7A-FR-003 (IdentityPlugin)
"""

from __future__ import annotations

from importlib.metadata import entry_points

import pytest


class TestSecretsPluginDiscovery:
    """Tests for secrets plugin discovery via entry points."""

    @pytest.mark.requirement("7A-FR-002")
    def test_k8s_secrets_plugin_discoverable(self) -> None:
        """Test that K8s secrets plugin is discoverable via entry point.

        Validates:
        - Entry point group 'floe.secrets' exists
        - 'k8s' plugin is registered
        - Plugin can be loaded
        """
        eps = entry_points(group="floe.secrets")
        plugin_names = {ep.name for ep in eps}

        assert "k8s" in plugin_names, (
            "K8s secrets plugin not found in 'floe.secrets' entry points. "
            "Ensure floe-secrets-k8s is installed."
        )

        # Load the plugin class
        k8s_ep = next(ep for ep in eps if ep.name == "k8s")
        plugin_class = k8s_ep.load()

        assert plugin_class is not None
        assert plugin_class.__name__ == "K8sSecretsPlugin"

    @pytest.mark.requirement("7A-FR-002")
    def test_infisical_secrets_plugin_discoverable(self) -> None:
        """Test that Infisical secrets plugin is discoverable via entry point.

        Validates:
        - Entry point group 'floe.secrets' exists
        - 'infisical' plugin is registered
        - Plugin can be loaded
        """
        eps = entry_points(group="floe.secrets")
        plugin_names = {ep.name for ep in eps}

        assert "infisical" in plugin_names, (
            "Infisical secrets plugin not found in 'floe.secrets' entry points. "
            "Ensure floe-secrets-infisical is installed."
        )

        # Load the plugin class
        infisical_ep = next(ep for ep in eps if ep.name == "infisical")
        plugin_class = infisical_ep.load()

        assert plugin_class is not None
        assert plugin_class.__name__ == "InfisicalSecretsPlugin"

    @pytest.mark.requirement("7A-FR-002")
    def test_all_secrets_plugins_inherit_from_abc(self) -> None:
        """Test that all secrets plugins inherit from SecretsPlugin ABC.

        Validates plugin architecture compliance for all discovered
        secrets plugins.
        """
        from floe_core.plugins.secrets import SecretsPlugin

        eps = entry_points(group="floe.secrets")

        for ep in eps:
            plugin_class = ep.load()
            assert issubclass(
                plugin_class, SecretsPlugin
            ), f"Plugin '{ep.name}' does not inherit from SecretsPlugin ABC"

    @pytest.mark.requirement("7A-FR-002")
    def test_all_secrets_plugins_have_required_methods(self) -> None:
        """Test that all secrets plugins implement required ABC methods.

        Validates that each plugin implements:
        - get_secret(key) -> str | None
        - set_secret(key, value, metadata) -> None
        - list_secrets(prefix) -> list[str]
        """
        eps = entry_points(group="floe.secrets")
        required_methods = ["get_secret", "set_secret", "list_secrets"]

        for ep in eps:
            plugin_class = ep.load()
            for method in required_methods:
                assert hasattr(
                    plugin_class, method
                ), f"Plugin '{ep.name}' missing required method: {method}"


class TestIdentityPluginDiscovery:
    """Tests for identity plugin discovery via entry points."""

    @pytest.mark.requirement("7A-FR-003")
    def test_keycloak_identity_plugin_discoverable(self) -> None:
        """Test that Keycloak identity plugin is discoverable via entry point.

        Validates:
        - Entry point group 'floe.identity' exists
        - 'keycloak' plugin is registered
        - Plugin can be loaded
        """
        eps = entry_points(group="floe.identity")
        plugin_names = {ep.name for ep in eps}

        assert "keycloak" in plugin_names, (
            "Keycloak identity plugin not found in 'floe.identity' entry points. "
            "Ensure floe-identity-keycloak is installed."
        )

        # Load the plugin class
        keycloak_ep = next(ep for ep in eps if ep.name == "keycloak")
        plugin_class = keycloak_ep.load()

        assert plugin_class is not None
        assert plugin_class.__name__ == "KeycloakIdentityPlugin"

    @pytest.mark.requirement("7A-FR-003")
    def test_all_identity_plugins_inherit_from_abc(self) -> None:
        """Test that all identity plugins inherit from IdentityPlugin ABC.

        Validates plugin architecture compliance for all discovered
        identity plugins.
        """
        from floe_core.plugins.identity import IdentityPlugin

        eps = entry_points(group="floe.identity")

        for ep in eps:
            plugin_class = ep.load()
            assert issubclass(
                plugin_class, IdentityPlugin
            ), f"Plugin '{ep.name}' does not inherit from IdentityPlugin ABC"

    @pytest.mark.requirement("7A-FR-003")
    def test_all_identity_plugins_have_required_methods(self) -> None:
        """Test that all identity plugins implement required ABC methods.

        Validates that each plugin implements:
        - authenticate(credentials) -> str | None
        - get_user_info(token) -> UserInfo | None
        - validate_token(token) -> TokenValidationResult
        """
        eps = entry_points(group="floe.identity")
        required_methods = ["authenticate", "get_user_info", "validate_token"]

        for ep in eps:
            plugin_class = ep.load()
            for method in required_methods:
                assert hasattr(
                    plugin_class, method
                ), f"Plugin '{ep.name}' missing required method: {method}"


class TestCrossPluginDiscovery:
    """Tests for discovering all Epic 7A plugins together."""

    @pytest.mark.requirement("7A-FR-002")
    @pytest.mark.requirement("7A-FR-003")
    def test_all_epic_7a_plugins_discoverable(self) -> None:
        """Test that all three Epic 7A plugins are discoverable.

        This is a combined smoke test ensuring the complete plugin
        system is properly configured.
        """
        secrets_eps = entry_points(group="floe.secrets")
        identity_eps = entry_points(group="floe.identity")

        secrets_names = {ep.name for ep in secrets_eps}
        identity_names = {ep.name for ep in identity_eps}

        # Verify all Epic 7A plugins are present
        expected_secrets = {"k8s", "infisical"}
        expected_identity = {"keycloak"}

        missing_secrets = expected_secrets - secrets_names
        missing_identity = expected_identity - identity_names

        assert not missing_secrets, (
            f"Missing secrets plugins: {missing_secrets}. "
            "Install with: uv pip install floe-secrets-k8s floe-secrets-infisical"
        )
        assert not missing_identity, (
            f"Missing identity plugins: {missing_identity}. "
            "Install with: uv pip install floe-identity-keycloak"
        )

    @pytest.mark.requirement("7A-FR-002")
    @pytest.mark.requirement("7A-FR-003")
    def test_all_plugins_have_metadata(self) -> None:
        """Test that all plugins declare required PluginMetadata.

        Validates that each plugin has:
        - name property
        - version property
        - floe_api_version property
        """
        all_eps = list(entry_points(group="floe.secrets"))
        all_eps.extend(entry_points(group="floe.identity"))

        for ep in all_eps:
            plugin_class = ep.load()

            # Check for required metadata properties
            assert hasattr(
                plugin_class, "name"
            ), f"Plugin '{ep.name}' missing 'name' property"
            assert hasattr(
                plugin_class, "version"
            ), f"Plugin '{ep.name}' missing 'version' property"
            assert hasattr(
                plugin_class, "floe_api_version"
            ), f"Plugin '{ep.name}' missing 'floe_api_version' property"

    @pytest.mark.requirement("7A-FR-002")
    @pytest.mark.requirement("7A-FR-003")
    def test_plugin_entry_point_groups_exist(self) -> None:
        """Test that expected entry point groups exist.

        Validates the plugin architecture is correctly set up with
        the expected entry point groups.
        """
        # These groups should exist (may be empty if plugins not installed)
        secrets_eps = entry_points(group="floe.secrets")
        identity_eps = entry_points(group="floe.identity")

        # Convert to list to check they're iterable
        secrets_list = list(secrets_eps)
        identity_list = list(identity_eps)

        # At minimum, our Epic 7A plugins should be present
        assert (
            len(secrets_list) >= 2
        ), "Expected at least 2 secrets plugins (k8s, infisical)"
        assert len(identity_list) >= 1, "Expected at least 1 identity plugin (keycloak)"

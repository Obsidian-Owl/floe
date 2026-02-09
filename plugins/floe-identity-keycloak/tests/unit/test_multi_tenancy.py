"""Unit tests for Keycloak plugin multi-tenancy support.

Task: T071
Requirements: 7A-FR-032 (Realm-based multi-tenancy for Data Mesh domain isolation)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr


class TestMultiTenancyProperties:
    """Tests for multi-tenancy property accessors."""

    @pytest.mark.requirement("7A-FR-032")
    def test_realm_property(self) -> None:
        """Test that realm property returns configured realm."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="test-realm",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)

        assert plugin.realm == "test-realm"

    @pytest.mark.requirement("7A-FR-032")
    def test_server_url_property(self) -> None:
        """Test that server_url property returns configured URL."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)

        assert plugin.server_url == "https://keycloak.example.com"


class TestGetOIDCConfigMultiRealm:
    """Tests for get_oidc_config with realm override."""

    @pytest.mark.requirement("7A-FR-032")
    def test_get_oidc_config_default_realm(self) -> None:
        """Test get_oidc_config returns config for default realm."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="default-realm",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        oidc_config = plugin.get_oidc_config()

        assert "default-realm" in oidc_config.issuer_url
        assert "default-realm" in oidc_config.discovery_url

    @pytest.mark.requirement("7A-FR-032")
    def test_get_oidc_config_different_realm(self) -> None:
        """Test get_oidc_config with realm override."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="default-realm",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        oidc_config = plugin.get_oidc_config(realm="sales-domain")

        assert "sales-domain" in oidc_config.issuer_url
        assert "sales-domain" in oidc_config.discovery_url
        assert "sales-domain" in oidc_config.token_endpoint

    @pytest.mark.requirement("7A-FR-032")
    def test_get_oidc_config_multiple_realms(self) -> None:
        """Test get_oidc_config for multiple different realms."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="master",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)

        sales_config = plugin.get_oidc_config(realm="sales")
        marketing_config = plugin.get_oidc_config(realm="marketing")
        engineering_config = plugin.get_oidc_config(realm="engineering")

        assert "sales" in sales_config.issuer_url
        assert "marketing" in marketing_config.issuer_url
        assert "engineering" in engineering_config.issuer_url


class TestGetAvailableRealms:
    """Tests for get_available_realms method."""

    @pytest.mark.requirement("7A-FR-032")
    def test_initial_realms_contains_configured(self) -> None:
        """Test that available realms includes configured realm."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="configured-realm",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        realms = plugin.get_available_realms()

        assert "configured-realm" in realms


class TestValidateTokenForRealm:
    """Tests for validate_token_for_realm method."""

    @pytest.mark.requirement("7A-FR-032")
    def test_validate_token_for_realm_not_started(self) -> None:
        """Test that validate_token_for_realm raises if not started."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)

        with pytest.raises(RuntimeError, match="not started"):
            plugin.validate_token_for_realm("token", "other-realm")

    @pytest.mark.requirement("7A-FR-032")
    def test_validate_token_for_realm_caches_validators(self) -> None:
        """Test that validators are cached per realm."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        try:
            # Create validators for different realms
            validator1 = plugin._get_or_create_realm_validator("realm1")
            validator2 = plugin._get_or_create_realm_validator("realm2")
            validator1_again = plugin._get_or_create_realm_validator("realm1")

            # Same realm should return same validator
            assert validator1 is validator1_again
            # Different realms should have different validators
            assert validator1 is not validator2

            # Check available realms
            realms = plugin.get_available_realms()
            assert "realm1" in realms
            assert "realm2" in realms
        finally:
            plugin.shutdown()

    @pytest.mark.requirement("7A-FR-032")
    def test_validate_token_for_default_realm_uses_main_validator(self) -> None:
        """Test that validating for default realm uses main validator."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="default-realm",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        try:
            validator = plugin._get_or_create_realm_validator("default-realm")
            assert validator is plugin._token_validator
        finally:
            plugin.shutdown()


class TestAuthenticateForRealm:
    """Tests for authenticate_for_realm method."""

    @pytest.mark.requirement("7A-FR-032")
    def test_authenticate_for_realm_not_started(self) -> None:
        """Test that authenticate_for_realm raises if not started."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)

        with pytest.raises(RuntimeError, match="not started"):
            plugin.authenticate_for_realm({}, "other-realm")

    @pytest.mark.requirement("7A-FR-032")
    def test_authenticate_for_realm_uses_correct_endpoint(self) -> None:
        """Test that authenticate_for_realm uses realm-specific endpoint."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        try:
            with patch.object(plugin._client, "post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"access_token": "test-token"}
                mock_post.return_value = mock_response

                token = plugin.authenticate_for_realm(
                    {},
                    realm="other-realm",
                )

                # Verify correct endpoint was called
                call_args = mock_post.call_args
                assert "other-realm" in call_args[0][0]
                assert token == "test-token"
        finally:
            plugin.shutdown()

    @pytest.mark.requirement("7A-FR-032")
    def test_authenticate_for_realm_with_custom_client(self) -> None:
        """Test authenticate_for_realm with custom client credentials."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="default-client",
            client_secret=SecretStr("default-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        try:
            with patch.object(plugin._client, "post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"access_token": "custom-token"}
                mock_post.return_value = mock_response

                token = plugin.authenticate_for_realm(
                    {},
                    realm="sales-domain",
                    client_id="sales-client",
                    client_secret="sales-secret",
                )

                # Verify custom client credentials were used
                call_args = mock_post.call_args
                data = call_args[1]["data"]
                assert data["client_id"] == "sales-client"
                assert data["client_secret"] == "sales-secret"
                assert token == "custom-token"
        finally:
            plugin.shutdown()


class TestShutdownClearsRealmValidators:
    """Tests that shutdown properly cleans up realm validators."""

    @pytest.mark.requirement("7A-FR-032")
    def test_shutdown_clears_realm_validators(self) -> None:
        """Test that shutdown clears cached realm validators."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        # Create some realm validators
        plugin._get_or_create_realm_validator("realm1")
        plugin._get_or_create_realm_validator("realm2")
        assert len(plugin._realm_validators) == 2

        plugin.shutdown()

        # Validators should be cleared
        assert len(plugin._realm_validators) == 0

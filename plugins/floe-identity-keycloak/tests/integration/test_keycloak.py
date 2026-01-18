"""Integration tests for Keycloak authentication in Kind cluster.

Task: T061
Requirements: 7A-FR-030, 7A-FR-031, 7A-FR-034

These tests require:
- Kind cluster running
- Keycloak deployed (testing/k8s/services/keycloak.yaml)
- Test realm and client configured
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from pydantic import SecretStr

if TYPE_CHECKING:
    from floe_identity_keycloak import KeycloakIdentityConfig, KeycloakIdentityPlugin


# Environment variable names for Keycloak test credentials
ENV_KEYCLOAK_URL = "KEYCLOAK_URL"
ENV_KEYCLOAK_REALM = "KEYCLOAK_REALM"
ENV_KEYCLOAK_CLIENT_ID = "KEYCLOAK_CLIENT_ID"
ENV_KEYCLOAK_CLIENT_SECRET = "KEYCLOAK_CLIENT_SECRET"
ENV_KEYCLOAK_TEST_USERNAME = "KEYCLOAK_TEST_USERNAME"
ENV_KEYCLOAK_TEST_PASSWORD = "KEYCLOAK_TEST_PASSWORD"


def _keycloak_credentials_available() -> bool:
    """Check if Keycloak credentials are available in environment."""
    return bool(
        os.environ.get(ENV_KEYCLOAK_URL)
        and os.environ.get(ENV_KEYCLOAK_CLIENT_ID)
        and os.environ.get(ENV_KEYCLOAK_CLIENT_SECRET)
    )


@pytest.fixture
def keycloak_config() -> "KeycloakIdentityConfig":
    """Create KeycloakIdentityConfig from environment for live testing.

    Returns:
        KeycloakIdentityConfig with real credentials.

    Raises:
        pytest.skip: If credentials are not available.
    """
    if not _keycloak_credentials_available():
        pytest.fail(
            f"Keycloak credentials not available. "
            f"Set {ENV_KEYCLOAK_URL}, {ENV_KEYCLOAK_CLIENT_ID}, {ENV_KEYCLOAK_CLIENT_SECRET}"
        )

    from floe_identity_keycloak import KeycloakIdentityConfig

    return KeycloakIdentityConfig(
        server_url=os.environ[ENV_KEYCLOAK_URL],
        realm=os.environ.get(ENV_KEYCLOAK_REALM, "floe"),
        client_id=os.environ[ENV_KEYCLOAK_CLIENT_ID],
        client_secret=SecretStr(os.environ[ENV_KEYCLOAK_CLIENT_SECRET]),
    )


@pytest.fixture
def keycloak_plugin(
    keycloak_config: "KeycloakIdentityConfig",
) -> "KeycloakIdentityPlugin":
    """Create KeycloakIdentityPlugin with real Keycloak connection.

    Args:
        keycloak_config: Config with real credentials.

    Yields:
        KeycloakIdentityPlugin connected to real Keycloak.
    """
    from floe_identity_keycloak import KeycloakIdentityPlugin

    plugin = KeycloakIdentityPlugin(config=keycloak_config)
    plugin.startup()

    yield plugin

    plugin.shutdown()


@pytest.fixture
def test_user_credentials() -> dict[str, str]:
    """Get test user credentials from environment.

    Returns:
        Dict with username and password.

    Raises:
        pytest.fail: If test user credentials not available.
    """
    username = os.environ.get(ENV_KEYCLOAK_TEST_USERNAME)
    password = os.environ.get(ENV_KEYCLOAK_TEST_PASSWORD)

    if not username or not password:
        pytest.fail(
            f"Test user credentials not available. "
            f"Set {ENV_KEYCLOAK_TEST_USERNAME}, {ENV_KEYCLOAK_TEST_PASSWORD}"
        )

    return {"username": username, "password": password}


class TestKeycloakAuthentication:
    """Integration tests for Keycloak authentication."""

    @pytest.mark.requirement("7A-FR-030")
    @pytest.mark.integration
    def test_authenticate_with_password_grant(
        self,
        keycloak_plugin: "KeycloakIdentityPlugin",
        test_user_credentials: dict[str, str],
    ) -> None:
        """Test authentication with username/password (password grant)."""
        token = keycloak_plugin.authenticate(test_user_credentials)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.requirement("7A-FR-030")
    @pytest.mark.integration
    def test_authenticate_with_client_credentials(
        self,
        keycloak_plugin: "KeycloakIdentityPlugin",
    ) -> None:
        """Test authentication with client credentials grant."""
        token = keycloak_plugin.authenticate({})

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.requirement("7A-FR-030")
    @pytest.mark.integration
    def test_authenticate_invalid_password_returns_none(
        self,
        keycloak_plugin: "KeycloakIdentityPlugin",
    ) -> None:
        """Test that invalid password returns None."""
        token = keycloak_plugin.authenticate({
            "username": "invalid-user",
            "password": "invalid-password",
        })

        assert token is None


class TestKeycloakTokenValidation:
    """Integration tests for Keycloak token validation."""

    @pytest.mark.requirement("7A-FR-034")
    @pytest.mark.integration
    def test_validate_valid_token(
        self,
        keycloak_plugin: "KeycloakIdentityPlugin",
    ) -> None:
        """Test validation of a valid token."""
        # Get a token first
        token = keycloak_plugin.authenticate({})
        assert token is not None

        # Validate the token
        result = keycloak_plugin.validate_token(token)

        assert result.valid is True
        assert result.user_info is not None
        assert result.error == ""

    @pytest.mark.requirement("7A-FR-034")
    @pytest.mark.integration
    def test_validate_invalid_token(
        self,
        keycloak_plugin: "KeycloakIdentityPlugin",
    ) -> None:
        """Test validation of an invalid token."""
        result = keycloak_plugin.validate_token("invalid.token.here")

        assert result.valid is False
        assert result.error != ""

    @pytest.mark.requirement("7A-FR-034")
    @pytest.mark.integration
    def test_validate_token_extracts_user_info(
        self,
        keycloak_plugin: "KeycloakIdentityPlugin",
        test_user_credentials: dict[str, str],
    ) -> None:
        """Test that token validation extracts user information."""
        # Get a user token
        token = keycloak_plugin.authenticate(test_user_credentials)
        assert token is not None

        # Validate and extract user info
        result = keycloak_plugin.validate_token(token)

        assert result.valid is True
        assert result.user_info is not None
        assert result.user_info.subject != ""


class TestKeycloakUserInfo:
    """Integration tests for Keycloak user info retrieval."""

    @pytest.mark.requirement("7A-FR-033")
    @pytest.mark.integration
    def test_get_user_info_with_valid_token(
        self,
        keycloak_plugin: "KeycloakIdentityPlugin",
        test_user_credentials: dict[str, str],
    ) -> None:
        """Test retrieving user info with valid token."""
        # Get a user token
        token = keycloak_plugin.authenticate(test_user_credentials)
        assert token is not None

        # Get user info
        user_info = keycloak_plugin.get_user_info(token)

        assert user_info is not None
        assert user_info.subject != ""

    @pytest.mark.requirement("7A-FR-033")
    @pytest.mark.integration
    def test_get_user_info_with_invalid_token_returns_none(
        self,
        keycloak_plugin: "KeycloakIdentityPlugin",
    ) -> None:
        """Test that invalid token returns None for user info."""
        user_info = keycloak_plugin.get_user_info("invalid.token")

        assert user_info is None


class TestKeycloakOIDCConfig:
    """Integration tests for OIDC configuration."""

    @pytest.mark.requirement("7A-FR-031")
    @pytest.mark.integration
    def test_get_oidc_config(
        self,
        keycloak_plugin: "KeycloakIdentityPlugin",
    ) -> None:
        """Test getting OIDC configuration."""
        config = keycloak_plugin.get_oidc_config()

        assert config is not None
        assert config.issuer_url != ""
        assert config.discovery_url != ""
        assert config.jwks_uri != ""
        assert config.authorization_endpoint != ""
        assert config.token_endpoint != ""
        assert config.userinfo_endpoint != ""

    @pytest.mark.requirement("7A-FR-032")
    @pytest.mark.integration
    def test_get_oidc_config_with_different_realm(
        self,
        keycloak_plugin: "KeycloakIdentityPlugin",
    ) -> None:
        """Test getting OIDC configuration for a different realm."""
        config = keycloak_plugin.get_oidc_config(realm="master")

        assert config is not None
        assert "master" in config.issuer_url
        assert "master" in config.discovery_url


class TestKeycloakHealthCheck:
    """Integration tests for plugin health check."""

    @pytest.mark.requirement("7A-FR-030")
    @pytest.mark.integration
    def test_health_check_returns_true(
        self,
        keycloak_plugin: "KeycloakIdentityPlugin",
    ) -> None:
        """Test that health check returns True when connected."""
        is_healthy = keycloak_plugin.health_check()

        assert is_healthy is True

    @pytest.mark.requirement("7A-FR-030")
    @pytest.mark.integration
    def test_health_check_before_startup_returns_false(
        self,
        keycloak_config: "KeycloakIdentityConfig",
    ) -> None:
        """Test that health check returns False before startup."""
        from floe_identity_keycloak import KeycloakIdentityPlugin

        plugin = KeycloakIdentityPlugin(config=keycloak_config)
        # Don't call startup()

        is_healthy = plugin.health_check()

        assert is_healthy is False

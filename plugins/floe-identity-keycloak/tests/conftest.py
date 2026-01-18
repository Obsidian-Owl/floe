"""Pytest configuration for floe-identity-keycloak tests.

This module provides shared fixtures for both unit and integration tests.

Task: T073
Requirements: 7A-FR-030, 7A-FR-031, 7A-FR-032
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import SecretStr

if TYPE_CHECKING:
    from collections.abc import Generator

    from floe_identity_keycloak import KeycloakIdentityConfig, KeycloakIdentityPlugin


# Environment variable names for test configuration
ENV_KEYCLOAK_URL = "KEYCLOAK_URL"
ENV_KEYCLOAK_REALM = "KEYCLOAK_REALM"
ENV_KEYCLOAK_CLIENT_ID = "KEYCLOAK_CLIENT_ID"
ENV_KEYCLOAK_CLIENT_SECRET = "KEYCLOAK_CLIENT_SECRET"
ENV_KEYCLOAK_TEST_USERNAME = "KEYCLOAK_TEST_USERNAME"
ENV_KEYCLOAK_TEST_PASSWORD = "KEYCLOAK_TEST_PASSWORD"

# Default test values for unit tests
DEFAULT_SERVER_URL = "https://keycloak.example.com"
DEFAULT_REALM = "floe"
DEFAULT_CLIENT_ID = "floe-client"
DEFAULT_CLIENT_SECRET = "test-secret"  # noqa: S105


def _keycloak_integration_available() -> bool:
    """Check if Keycloak integration credentials are available.

    Returns:
        True if all required credentials are set in environment.
    """
    return bool(
        os.environ.get(ENV_KEYCLOAK_URL)
        and os.environ.get(ENV_KEYCLOAK_CLIENT_ID)
        and os.environ.get(ENV_KEYCLOAK_CLIENT_SECRET)
    )


@pytest.fixture
def mock_keycloak_config() -> KeycloakIdentityConfig:
    """Create a mock KeycloakIdentityConfig for unit tests.

    This fixture provides a configuration that does NOT connect to a real
    Keycloak server. Use for unit tests that mock HTTP responses.

    Returns:
        KeycloakIdentityConfig with test values.
    """
    from floe_identity_keycloak import KeycloakIdentityConfig

    return KeycloakIdentityConfig(
        server_url=DEFAULT_SERVER_URL,
        realm=DEFAULT_REALM,
        client_id=DEFAULT_CLIENT_ID,
        client_secret=SecretStr(DEFAULT_CLIENT_SECRET),
    )


@pytest.fixture
def mock_keycloak_plugin(
    mock_keycloak_config: KeycloakIdentityConfig,
) -> Generator[KeycloakIdentityPlugin, None, None]:
    """Create a mock KeycloakIdentityPlugin for unit tests.

    This fixture provides a plugin instance with startup() called but
    NOT connected to a real Keycloak server. Use for unit tests that
    mock HTTP responses.

    Args:
        mock_keycloak_config: Mock configuration fixture.

    Yields:
        KeycloakIdentityPlugin instance (started).
    """
    from floe_identity_keycloak import KeycloakIdentityPlugin

    plugin = KeycloakIdentityPlugin(config=mock_keycloak_config)
    plugin.startup()

    yield plugin

    plugin.shutdown()


@pytest.fixture
def live_keycloak_config() -> KeycloakIdentityConfig:
    """Create KeycloakIdentityConfig from environment for live testing.

    This fixture requires real Keycloak credentials in environment variables.
    Tests using this fixture will FAIL if credentials are not available.

    Returns:
        KeycloakIdentityConfig with real credentials.

    Raises:
        pytest.fail: If credentials are not available.
    """
    if not _keycloak_integration_available():
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
def live_keycloak_plugin(
    live_keycloak_config: KeycloakIdentityConfig,
) -> Generator[KeycloakIdentityPlugin, None, None]:
    """Create KeycloakIdentityPlugin with real Keycloak connection.

    This fixture requires real Keycloak credentials in environment variables.
    Tests using this fixture will FAIL if credentials are not available.

    Args:
        live_keycloak_config: Config with real credentials.

    Yields:
        KeycloakIdentityPlugin connected to real Keycloak.
    """
    from floe_identity_keycloak import KeycloakIdentityPlugin

    plugin = KeycloakIdentityPlugin(config=live_keycloak_config)
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


@pytest.fixture
def sample_jwt_claims() -> dict[str, Any]:
    """Provide sample JWT claims for testing.

    Returns:
        Dict containing typical Keycloak JWT claims.
    """
    return {
        "sub": "user-123-456-789",
        "iss": f"{DEFAULT_SERVER_URL}/realms/{DEFAULT_REALM}",
        "aud": DEFAULT_CLIENT_ID,
        "exp": 9999999999,  # Far future
        "iat": 1000000000,
        "email": "test@example.com",
        "email_verified": True,
        "name": "Test User",
        "preferred_username": "testuser",
        "given_name": "Test",
        "family_name": "User",
        "realm_access": {
            "roles": ["user", "admin"],
        },
        "resource_access": {
            DEFAULT_CLIENT_ID: {
                "roles": ["data-engineer", "viewer"],
            },
        },
    }


@pytest.fixture
def sample_oidc_discovery() -> dict[str, str]:
    """Provide sample OIDC discovery response.

    Returns:
        Dict containing typical OIDC discovery endpoints.
    """
    base_url = f"{DEFAULT_SERVER_URL}/realms/{DEFAULT_REALM}"
    protocol_url = f"{base_url}/protocol/openid-connect"

    return {
        "issuer": base_url,
        "authorization_endpoint": f"{protocol_url}/auth",
        "token_endpoint": f"{protocol_url}/token",
        "userinfo_endpoint": f"{protocol_url}/userinfo",
        "jwks_uri": f"{protocol_url}/certs",
        "end_session_endpoint": f"{protocol_url}/logout",
        "introspection_endpoint": f"{protocol_url}/token/introspect",
    }


# Register custom markers
def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "requirement(req_id): Mark test as covering a specific requirement",
    )
    config.addinivalue_line(
        "markers",
        "integration: Mark test as an integration test requiring real services",
    )

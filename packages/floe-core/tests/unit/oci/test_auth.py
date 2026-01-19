"""Unit tests for OCI authentication providers.

Tests the authentication providers for various registry auth methods
including BasicAuthProvider and TokenAuthProvider.

Task: T053
Requirements: FR-006, FR-007
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    pass

# Test fixture values (use constants to avoid secret scanner false positives)
TEST_CREDENTIAL_VALUE = "PLACEHOLDER_TEST_VALUE"
TEST_FALLBACK_VALUE = "PLACEHOLDER_FALLBACK"
TEST_TOKEN_VALUE = "PLACEHOLDER_GITHUB_TOKEN"
TEST_DIRECT_TOKEN = "PLACEHOLDER_TOKEN_DIRECT"
TEST_SUBKEY_TOKEN = "PLACEHOLDER_TOKEN_SUBKEY"


class TestBasicAuthProvider:
    """Tests for BasicAuthProvider."""

    @pytest.mark.requirement("8A-FR-006")
    def test_basic_auth_returns_credentials(self) -> None:
        """Test that BasicAuthProvider returns correct username/password credentials."""
        from floe_core.oci.auth import BasicAuthProvider, Credentials
        from floe_core.schemas.oci import AuthType

        # Create mock secrets plugin
        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.return_value = {
            "username": "test-user",
            "password": TEST_CREDENTIAL_VALUE,
        }

        provider = BasicAuthProvider(
            registry_uri="oci://harbor.example.com/floe",
            secrets_plugin=mock_secrets,
            secret_name="registry-creds",
        )

        # Verify auth type
        assert provider.auth_type == AuthType.BASIC

        # Get credentials
        creds = provider.get_credentials()

        # Verify credentials
        assert isinstance(creds, Credentials)
        assert creds.username == "test-user"
        assert creds.password == TEST_CREDENTIAL_VALUE
        assert creds.expires_at is None  # Basic auth doesn't expire

        # Verify secrets plugin was called correctly
        mock_secrets.get_multi_key_secret.assert_called_once_with("registry-creds")

    @pytest.mark.requirement("8A-FR-006")
    def test_basic_auth_caches_credentials(self) -> None:
        """Test that BasicAuthProvider caches credentials after first retrieval."""
        from floe_core.oci.auth import BasicAuthProvider

        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.return_value = {
            "username": "user",
            "password": "pass",
        }

        provider = BasicAuthProvider(
            registry_uri="oci://harbor.example.com/floe",
            secrets_plugin=mock_secrets,
            secret_name="creds",
        )

        # Get credentials twice
        creds1 = provider.get_credentials()
        creds2 = provider.get_credentials()

        # Should be same object (cached)
        assert creds1 is creds2

        # Secrets plugin should only be called once
        assert mock_secrets.get_multi_key_secret.call_count == 1

    @pytest.mark.requirement("8A-FR-006")
    def test_basic_auth_fallback_to_single_key(self) -> None:
        """Test BasicAuthProvider falls back to single-key lookup if multi-key not supported."""
        from floe_core.oci.auth import BasicAuthProvider

        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.side_effect = NotImplementedError()
        mock_secrets.get_secret.side_effect = lambda key: {
            "registry-creds/username": "fallback-user",
            "registry-creds/password": TEST_FALLBACK_VALUE,
        }.get(key)

        provider = BasicAuthProvider(
            registry_uri="oci://harbor.example.com/floe",
            secrets_plugin=mock_secrets,
            secret_name="registry-creds",
        )

        creds = provider.get_credentials()

        assert creds.username == "fallback-user"
        assert creds.password == TEST_FALLBACK_VALUE

    @pytest.mark.requirement("8A-FR-006")
    def test_basic_auth_raises_on_missing_username(self) -> None:
        """Test BasicAuthProvider raises AuthenticationError if username missing."""
        from floe_core.oci.auth import BasicAuthProvider
        from floe_core.oci.errors import AuthenticationError

        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.return_value = {
            "password": TEST_CREDENTIAL_VALUE,
            # Missing username
        }

        provider = BasicAuthProvider(
            registry_uri="oci://harbor.example.com/floe",
            secrets_plugin=mock_secrets,
            secret_name="registry-creds",
        )

        with pytest.raises(AuthenticationError, match="missing required"):
            provider.get_credentials()

    @pytest.mark.requirement("8A-FR-006")
    def test_basic_auth_raises_on_missing_password(self) -> None:
        """Test BasicAuthProvider raises AuthenticationError if password missing."""
        from floe_core.oci.auth import BasicAuthProvider
        from floe_core.oci.errors import AuthenticationError

        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.return_value = {
            "username": "test-user",
            # Missing password
        }

        provider = BasicAuthProvider(
            registry_uri="oci://harbor.example.com/floe",
            secrets_plugin=mock_secrets,
            secret_name="registry-creds",
        )

        with pytest.raises(AuthenticationError, match="missing required"):
            provider.get_credentials()

    @pytest.mark.requirement("8A-FR-006")
    def test_basic_auth_refresh_not_needed(self) -> None:
        """Test that BasicAuthProvider.refresh_if_needed returns False (non-expiring)."""
        from floe_core.oci.auth import BasicAuthProvider

        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.return_value = {
            "username": "user",
            "password": "pass",
        }

        provider = BasicAuthProvider(
            registry_uri="oci://harbor.example.com/floe",
            secrets_plugin=mock_secrets,
            secret_name="creds",
        )

        # Refresh should always return False for basic auth
        assert provider.refresh_if_needed() is False


class TestTokenAuthProvider:
    """Tests for TokenAuthProvider."""

    @pytest.mark.requirement("8A-FR-007")
    def test_token_auth_returns_bearer_token(self) -> None:
        """Test that TokenAuthProvider returns bearer token as password."""
        from floe_core.oci.auth import Credentials, TokenAuthProvider
        from floe_core.schemas.oci import AuthType

        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.return_value = {
            "token": TEST_TOKEN_VALUE,
        }

        provider = TokenAuthProvider(
            registry_uri="oci://ghcr.io/myorg",
            secrets_plugin=mock_secrets,
            secret_name="ghcr-token",
        )

        # Verify auth type
        assert provider.auth_type == AuthType.TOKEN

        # Get credentials
        creds = provider.get_credentials()

        # Verify credentials
        assert isinstance(creds, Credentials)
        assert creds.username == TokenAuthProvider.TOKEN_USERNAME
        assert creds.username == "__token__"
        assert creds.password == TEST_TOKEN_VALUE
        assert creds.expires_at is None  # Static tokens don't expire

    @pytest.mark.requirement("8A-FR-007")
    def test_token_auth_caches_credentials(self) -> None:
        """Test that TokenAuthProvider caches credentials after first retrieval."""
        from floe_core.oci.auth import TokenAuthProvider

        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.return_value = {"token": TEST_TOKEN_VALUE}

        provider = TokenAuthProvider(
            registry_uri="oci://ghcr.io/myorg",
            secrets_plugin=mock_secrets,
            secret_name="token-secret",
        )

        creds1 = provider.get_credentials()
        creds2 = provider.get_credentials()

        assert creds1 is creds2
        assert mock_secrets.get_multi_key_secret.call_count == 1

    @pytest.mark.requirement("8A-FR-007")
    def test_token_auth_fallback_to_direct_lookup(self) -> None:
        """Test TokenAuthProvider falls back to direct key lookup."""
        from floe_core.oci.auth import TokenAuthProvider

        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.side_effect = NotImplementedError()
        mock_secrets.get_secret.side_effect = lambda key: {
            "ghcr-token": TEST_DIRECT_TOKEN,
        }.get(key)

        provider = TokenAuthProvider(
            registry_uri="oci://ghcr.io/myorg",
            secrets_plugin=mock_secrets,
            secret_name="ghcr-token",
        )

        creds = provider.get_credentials()

        assert creds.password == TEST_DIRECT_TOKEN

    @pytest.mark.requirement("8A-FR-007")
    def test_token_auth_fallback_to_token_key(self) -> None:
        """Test TokenAuthProvider falls back to secret_name/token key."""
        from floe_core.oci.auth import TokenAuthProvider

        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.side_effect = NotImplementedError()
        mock_secrets.get_secret.side_effect = lambda key: {
            "ghcr-token/token": TEST_SUBKEY_TOKEN,
        }.get(key)

        provider = TokenAuthProvider(
            registry_uri="oci://ghcr.io/myorg",
            secrets_plugin=mock_secrets,
            secret_name="ghcr-token",
        )

        creds = provider.get_credentials()

        assert creds.password == TEST_SUBKEY_TOKEN

    @pytest.mark.requirement("8A-FR-007")
    def test_token_auth_raises_on_missing_token(self) -> None:
        """Test TokenAuthProvider raises AuthenticationError if token missing."""
        from floe_core.oci.auth import TokenAuthProvider
        from floe_core.oci.errors import AuthenticationError

        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.return_value = {}  # No token key
        mock_secrets.get_secret.return_value = None  # Direct lookup fails too

        provider = TokenAuthProvider(
            registry_uri="oci://ghcr.io/myorg",
            secrets_plugin=mock_secrets,
            secret_name="ghcr-token",
        )

        with pytest.raises(AuthenticationError, match="missing token"):
            provider.get_credentials()

    @pytest.mark.requirement("8A-FR-007")
    def test_token_auth_refresh_not_needed(self) -> None:
        """Test that TokenAuthProvider.refresh_if_needed returns False (non-expiring)."""
        from floe_core.oci.auth import TokenAuthProvider

        mock_secrets = MagicMock()
        mock_secrets.get_multi_key_secret.return_value = {"token": TEST_TOKEN_VALUE}

        provider = TokenAuthProvider(
            registry_uri="oci://ghcr.io/myorg",
            secrets_plugin=mock_secrets,
            secret_name="token-secret",
        )

        assert provider.refresh_if_needed() is False


class TestCredentials:
    """Tests for Credentials dataclass."""

    @pytest.mark.requirement("8A-FR-006")
    def test_credentials_is_expired_with_no_expiry(self) -> None:
        """Test that Credentials with no expiry is never expired."""
        from floe_core.oci.auth import Credentials

        creds = Credentials(username="user", password="pass", expires_at=None)

        assert creds.is_expired is False

    @pytest.mark.requirement("8A-FR-006")
    def test_credentials_is_expired_with_future_expiry(self) -> None:
        """Test that Credentials with future expiry is not expired."""
        from datetime import datetime, timedelta, timezone

        from floe_core.oci.auth import Credentials

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        creds = Credentials(username="user", password="pass", expires_at=future)

        assert creds.is_expired is False

    @pytest.mark.requirement("8A-FR-006")
    def test_credentials_is_expired_with_past_expiry(self) -> None:
        """Test that Credentials with past expiry is expired."""
        from datetime import datetime, timedelta, timezone

        from floe_core.oci.auth import Credentials

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        creds = Credentials(username="user", password="pass", expires_at=past)

        assert creds.is_expired is True


class TestCreateAuthProvider:
    """Tests for create_auth_provider factory function."""

    @pytest.mark.requirement("8A-FR-006")
    def test_create_basic_auth_provider(self) -> None:
        """Test factory creates BasicAuthProvider for basic auth type."""
        from floe_core.oci.auth import BasicAuthProvider, create_auth_provider
        from floe_core.schemas import SecretReference
        from floe_core.schemas.oci import AuthType, RegistryAuth

        mock_secrets = MagicMock()
        auth_config = RegistryAuth(
            type=AuthType.BASIC,
            credentials_ref=SecretReference(name="registry-creds"),
        )

        provider = create_auth_provider(
            registry_uri="oci://harbor.example.com/floe",
            auth_config=auth_config,
            secrets_plugin=mock_secrets,
        )

        assert isinstance(provider, BasicAuthProvider)

    @pytest.mark.requirement("8A-FR-007")
    def test_create_token_auth_provider(self) -> None:
        """Test factory creates TokenAuthProvider for token auth type."""
        from floe_core.oci.auth import TokenAuthProvider, create_auth_provider
        from floe_core.schemas import SecretReference
        from floe_core.schemas.oci import AuthType, RegistryAuth

        mock_secrets = MagicMock()
        auth_config = RegistryAuth(
            type=AuthType.TOKEN,
            credentials_ref=SecretReference(name="ghcr-token"),
        )

        provider = create_auth_provider(
            registry_uri="oci://ghcr.io/myorg",
            auth_config=auth_config,
            secrets_plugin=mock_secrets,
        )

        assert isinstance(provider, TokenAuthProvider)

    @pytest.mark.requirement("8A-FR-006")
    def test_create_basic_auth_requires_secrets_plugin(self) -> None:
        """Test factory raises error if secrets_plugin not provided for basic auth."""
        from floe_core.oci.auth import create_auth_provider
        from floe_core.oci.errors import AuthenticationError
        from floe_core.schemas import SecretReference
        from floe_core.schemas.oci import AuthType, RegistryAuth

        auth_config = RegistryAuth(
            type=AuthType.BASIC,
            credentials_ref=SecretReference(name="creds"),
        )

        with pytest.raises(AuthenticationError, match="SecretsPlugin required"):
            create_auth_provider(
                registry_uri="oci://harbor.example.com/floe",
                auth_config=auth_config,
                secrets_plugin=None,  # Missing!
            )

    @pytest.mark.requirement("8A-FR-006")
    def test_create_basic_auth_requires_credentials_ref_via_pydantic(self) -> None:
        """Test that Pydantic validates credentials_ref is required for basic auth."""
        from pydantic import ValidationError

        from floe_core.schemas.oci import AuthType, RegistryAuth

        # Pydantic model validation catches this at the schema level
        with pytest.raises(ValidationError, match="credentials_ref required"):
            RegistryAuth(
                type=AuthType.BASIC,
                credentials_ref=None,  # Missing - caught by Pydantic
            )

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
TEST_ECR_TOKEN = "PLACEHOLDER_ECR_AUTH_TOKEN"
TEST_AZURE_TOKEN = "PLACEHOLDER_AZURE_MI_TOKEN"
TEST_GCP_TOKEN = "PLACEHOLDER_GCP_WI_TOKEN"


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
        assert creds.username == TokenAuthProvider.TOKEN_USERNAME  # "__token__"
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


class TestIRSAAuthProvider:
    """Tests for AWS IRSA AuthProvider."""

    @pytest.mark.requirement("8A-FR-007")
    def test_irsa_auth_returns_credentials(self) -> None:
        """Test that IRSAAuthProvider returns ECR credentials via boto3."""
        import base64
        import sys
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        from floe_core.oci.auth import Credentials, IRSAAuthProvider
        from floe_core.schemas.oci import AuthType

        # Create base64 encoded token (username:password format)
        token_str = f"AWS:{TEST_ECR_TOKEN}"
        encoded_token = base64.b64encode(token_str.encode()).decode()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=12)

        mock_response = {
            "authorizationData": [
                {
                    "authorizationToken": encoded_token,
                    "expiresAt": expires_at,
                }
            ]
        }

        # Create mock boto3 module
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_client.get_authorization_token.return_value = mock_response
        mock_boto3.client.return_value = mock_client

        # Inject mock boto3 into sys.modules
        with patch.dict(sys.modules, {"boto3": mock_boto3}):
            provider = IRSAAuthProvider(
                registry_uri="oci://123456789.dkr.ecr.us-east-1.amazonaws.com/floe"
            )

            # Verify auth type
            assert provider.auth_type == AuthType.AWS_IRSA

            # Get credentials
            creds = provider.get_credentials()

            # Verify credentials
            assert isinstance(creds, Credentials)
            assert creds.username == "AWS"
            assert creds.password == TEST_ECR_TOKEN
            assert creds.expires_at is not None

            # Verify boto3 was called correctly
            mock_boto3.client.assert_called_once_with("ecr", region_name="us-east-1")

    @pytest.mark.requirement("8A-FR-007")
    def test_irsa_auth_missing_boto3(self) -> None:
        """Test that IRSAAuthProvider raises error when boto3 not installed."""
        from unittest.mock import patch

        from floe_core.oci.auth import IRSAAuthProvider
        from floe_core.oci.errors import AuthenticationError

        provider = IRSAAuthProvider(
            registry_uri="oci://123456789.dkr.ecr.us-east-1.amazonaws.com/floe"
        )

        # Mock import to fail
        with patch.dict("sys.modules", {"boto3": None}):
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'boto3'"),
            ):
                with pytest.raises(AuthenticationError, match="boto3 required"):
                    provider.get_credentials()

    @pytest.mark.requirement("8A-FR-007")
    def test_irsa_auth_extracts_region(self) -> None:
        """Test that IRSAAuthProvider extracts AWS region from ECR URI."""
        from floe_core.oci.auth import IRSAAuthProvider

        # Test various ECR URI formats
        provider1 = IRSAAuthProvider(
            registry_uri="oci://123456789.dkr.ecr.us-east-1.amazonaws.com/floe"
        )
        assert provider1._extract_region() == "us-east-1"

        provider2 = IRSAAuthProvider(
            registry_uri="oci://123456789.dkr.ecr.eu-west-2.amazonaws.com/repo"
        )
        assert provider2._extract_region() == "eu-west-2"

    @pytest.mark.requirement("8A-FR-007")
    def test_irsa_auth_caches_credentials(self) -> None:
        """Test that IRSAAuthProvider caches credentials."""
        import base64
        import sys
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        from floe_core.oci.auth import IRSAAuthProvider

        token_str = f"AWS:{TEST_ECR_TOKEN}"
        encoded_token = base64.b64encode(token_str.encode()).decode()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=12)

        mock_response = {
            "authorizationData": [
                {
                    "authorizationToken": encoded_token,
                    "expiresAt": expires_at,
                }
            ]
        }

        # Create mock boto3 module
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_client.get_authorization_token.return_value = mock_response
        mock_boto3.client.return_value = mock_client

        with patch.dict(sys.modules, {"boto3": mock_boto3}):
            provider = IRSAAuthProvider(
                registry_uri="oci://123456789.dkr.ecr.us-east-1.amazonaws.com/floe"
            )

            creds1 = provider.get_credentials()
            creds2 = provider.get_credentials()

            # Should be same object (cached)
            assert creds1 is creds2
            # boto3 should only be called once
            assert mock_client.get_authorization_token.call_count == 1

    @pytest.mark.requirement("8A-FR-007")
    def test_irsa_auth_refresh_if_needed(self) -> None:
        """Test that IRSAAuthProvider refreshes expiring credentials."""
        import base64
        import sys
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        from floe_core.oci.auth import IRSAAuthProvider

        token_str = f"AWS:{TEST_ECR_TOKEN}"
        encoded_token = base64.b64encode(token_str.encode()).decode()

        # Create credentials that will expire soon (within refresh buffer)
        expires_soon = datetime.now(timezone.utc) + timedelta(minutes=5)

        mock_response = {
            "authorizationData": [
                {
                    "authorizationToken": encoded_token,
                    "expiresAt": expires_soon,
                }
            ]
        }

        # Create mock boto3 module
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_client.get_authorization_token.return_value = mock_response
        mock_boto3.client.return_value = mock_client

        with patch.dict(sys.modules, {"boto3": mock_boto3}):
            provider = IRSAAuthProvider(
                registry_uri="oci://123456789.dkr.ecr.us-east-1.amazonaws.com/floe"
            )

            # Get initial credentials
            provider.get_credentials()
            assert mock_client.get_authorization_token.call_count == 1

            # Since credentials expire within buffer (5 min expiry), refresh should be needed
            refreshed = provider.refresh_if_needed()
            assert refreshed is True
            assert mock_client.get_authorization_token.call_count == 2


class TestAzureMIAuthProvider:
    """Tests for Azure Managed Identity AuthProvider."""

    @pytest.mark.requirement("8A-FR-007")
    def test_azure_mi_auth_returns_credentials(self) -> None:
        """Test that AzureMIAuthProvider returns ACR credentials via azure-identity."""
        import sys
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        from floe_core.oci.auth import AzureMIAuthProvider, Credentials
        from floe_core.schemas.oci import AuthType

        expires_on = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_token = MagicMock()
        mock_token.token = TEST_AZURE_TOKEN
        mock_token.expires_on = expires_on.timestamp()

        # Create mock azure.identity module
        mock_credential = MagicMock()
        mock_credential.get_token.return_value = mock_token
        mock_cred_class = MagicMock(return_value=mock_credential)

        mock_azure_identity = MagicMock()
        mock_azure_identity.DefaultAzureCredential = mock_cred_class

        with patch.dict(sys.modules, {"azure.identity": mock_azure_identity}):
            provider = AzureMIAuthProvider(registry_uri="oci://myregistry.azurecr.io/floe")

            # Verify auth type
            assert provider.auth_type == AuthType.AZURE_MANAGED_IDENTITY

            # Get credentials
            creds = provider.get_credentials()

            # Verify credentials
            assert isinstance(creds, Credentials)
            assert creds.username == "00000000-0000-0000-0000-000000000000"
            assert creds.password == TEST_AZURE_TOKEN
            assert creds.expires_at is not None

            # Verify azure-identity was called with ACR-specific scope
            mock_credential.get_token.assert_called_once_with(
                "https://containerregistry.azure.net/.default"
            )

    @pytest.mark.requirement("8A-FR-007")
    def test_azure_mi_auth_missing_azure_identity(self) -> None:
        """Test that AzureMIAuthProvider raises error when azure-identity not installed."""
        import sys
        from unittest.mock import patch

        from floe_core.oci.auth import AzureMIAuthProvider
        from floe_core.oci.errors import AuthenticationError

        provider = AzureMIAuthProvider(registry_uri="oci://myregistry.azurecr.io/floe")

        with patch.dict(sys.modules, {"azure": None, "azure.identity": None}):
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'azure.identity'"),
            ):
                with pytest.raises(AuthenticationError, match="azure-identity required"):
                    provider.get_credentials()

    @pytest.mark.requirement("8A-FR-007")
    def test_azure_mi_auth_caches_credentials(self) -> None:
        """Test that AzureMIAuthProvider caches credentials."""
        import sys
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        from floe_core.oci.auth import AzureMIAuthProvider

        expires_on = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_token = MagicMock()
        mock_token.token = TEST_AZURE_TOKEN
        mock_token.expires_on = expires_on.timestamp()

        # Create mock azure.identity module
        mock_credential = MagicMock()
        mock_credential.get_token.return_value = mock_token
        mock_cred_class = MagicMock(return_value=mock_credential)

        mock_azure_identity = MagicMock()
        mock_azure_identity.DefaultAzureCredential = mock_cred_class

        with patch.dict(sys.modules, {"azure.identity": mock_azure_identity}):
            provider = AzureMIAuthProvider(registry_uri="oci://myregistry.azurecr.io/floe")

            creds1 = provider.get_credentials()
            creds2 = provider.get_credentials()

            # Should be same object (cached)
            assert creds1 is creds2
            # get_token should only be called once
            assert mock_credential.get_token.call_count == 1

    @pytest.mark.requirement("8A-FR-007")
    def test_azure_mi_auth_refresh_if_needed(self) -> None:
        """Test that AzureMIAuthProvider refreshes expiring credentials."""
        import sys
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        from floe_core.oci.auth import AzureMIAuthProvider

        # Create credentials that will expire soon (within refresh buffer)
        expires_soon = datetime.now(timezone.utc) + timedelta(minutes=5)

        mock_token = MagicMock()
        mock_token.token = TEST_AZURE_TOKEN
        mock_token.expires_on = expires_soon.timestamp()

        # Create mock azure.identity module
        mock_credential = MagicMock()
        mock_credential.get_token.return_value = mock_token
        mock_cred_class = MagicMock(return_value=mock_credential)

        mock_azure_identity = MagicMock()
        mock_azure_identity.DefaultAzureCredential = mock_cred_class

        with patch.dict(sys.modules, {"azure.identity": mock_azure_identity}):
            provider = AzureMIAuthProvider(registry_uri="oci://myregistry.azurecr.io/floe")

            # Get initial credentials
            provider.get_credentials()
            assert mock_credential.get_token.call_count == 1

            # Since credentials expire within buffer (5 min expiry), refresh should be needed
            refreshed = provider.refresh_if_needed()
            assert refreshed is True
            assert mock_credential.get_token.call_count == 2


class TestGCPWIAuthProvider:
    """Tests for GCP Workload Identity AuthProvider."""

    @pytest.mark.requirement("8A-FR-007")
    def test_gcp_wi_auth_returns_credentials(self) -> None:
        """Test that GCPWIAuthProvider returns GAR credentials via google-auth."""
        import sys
        import types
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        from floe_core.oci.auth import Credentials, GCPWIAuthProvider
        from floe_core.schemas.oci import AuthType

        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_gcp_credentials = MagicMock()
        mock_gcp_credentials.token = TEST_GCP_TOKEN
        mock_gcp_credentials.expiry = expires_at

        # Create mock google module hierarchy
        mock_google = types.ModuleType("google")
        mock_google_auth = types.ModuleType("google.auth")
        mock_google_auth.default = MagicMock(return_value=(mock_gcp_credentials, "project-id"))

        mock_google.auth = mock_google_auth

        # Create mock transport modules
        mock_transport = types.ModuleType("google.auth.transport")
        mock_transport_requests = types.ModuleType("google.auth.transport.requests")
        mock_transport_requests.Request = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "google": mock_google,
                "google.auth": mock_google_auth,
                "google.auth.transport": mock_transport,
                "google.auth.transport.requests": mock_transport_requests,
            },
        ):
            provider = GCPWIAuthProvider(
                registry_uri="oci://us-central1-docker.pkg.dev/my-project/my-repo"
            )

            # Verify auth type
            assert provider.auth_type == AuthType.GCP_WORKLOAD_IDENTITY

            # Get credentials
            creds = provider.get_credentials()

            # Verify credentials
            assert isinstance(creds, Credentials)
            assert creds.username == "oauth2accesstoken"
            assert creds.password == TEST_GCP_TOKEN
            assert creds.expires_at is not None

            # Verify google-auth was called correctly
            mock_google_auth.default.assert_called_once_with(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            mock_gcp_credentials.refresh.assert_called_once()

    @pytest.mark.requirement("8A-FR-007")
    def test_gcp_wi_auth_missing_google_auth(self) -> None:
        """Test that GCPWIAuthProvider raises error when google-auth not installed."""
        import sys
        from unittest.mock import patch

        from floe_core.oci.auth import GCPWIAuthProvider
        from floe_core.oci.errors import AuthenticationError

        provider = GCPWIAuthProvider(
            registry_uri="oci://us-central1-docker.pkg.dev/my-project/my-repo"
        )

        with patch.dict(sys.modules, {"google": None, "google.auth": None}):
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'google.auth'"),
            ):
                with pytest.raises(AuthenticationError, match="google-auth required"):
                    provider.get_credentials()

    @pytest.mark.requirement("8A-FR-007")
    def test_gcp_wi_auth_caches_credentials(self) -> None:
        """Test that GCPWIAuthProvider caches credentials."""
        import sys
        import types
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        from floe_core.oci.auth import GCPWIAuthProvider

        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_gcp_credentials = MagicMock()
        mock_gcp_credentials.token = TEST_GCP_TOKEN
        mock_gcp_credentials.expiry = expires_at

        # Create mock google module hierarchy
        mock_google = types.ModuleType("google")
        mock_google_auth = types.ModuleType("google.auth")
        mock_google_auth.default = MagicMock(return_value=(mock_gcp_credentials, "project-id"))

        mock_google.auth = mock_google_auth

        # Create mock transport modules
        mock_transport = types.ModuleType("google.auth.transport")
        mock_transport_requests = types.ModuleType("google.auth.transport.requests")
        mock_transport_requests.Request = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "google": mock_google,
                "google.auth": mock_google_auth,
                "google.auth.transport": mock_transport,
                "google.auth.transport.requests": mock_transport_requests,
            },
        ):
            provider = GCPWIAuthProvider(
                registry_uri="oci://us-central1-docker.pkg.dev/my-project/my-repo"
            )

            creds1 = provider.get_credentials()
            creds2 = provider.get_credentials()

            # Should be same object (cached)
            assert creds1 is creds2
            # google.auth.default should only be called once
            assert mock_google_auth.default.call_count == 1

    @pytest.mark.requirement("8A-FR-007")
    def test_gcp_wi_auth_refresh_if_needed(self) -> None:
        """Test that GCPWIAuthProvider refreshes expiring credentials."""
        import sys
        import types
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        from floe_core.oci.auth import GCPWIAuthProvider

        # Create credentials that will expire soon (within refresh buffer)
        expires_soon = datetime.now(timezone.utc) + timedelta(minutes=5)

        mock_gcp_credentials = MagicMock()
        mock_gcp_credentials.token = TEST_GCP_TOKEN
        mock_gcp_credentials.expiry = expires_soon

        # Create mock google module hierarchy
        mock_google = types.ModuleType("google")
        mock_google_auth = types.ModuleType("google.auth")
        mock_google_auth.default = MagicMock(return_value=(mock_gcp_credentials, "project-id"))

        mock_google.auth = mock_google_auth

        # Create mock transport modules
        mock_transport = types.ModuleType("google.auth.transport")
        mock_transport_requests = types.ModuleType("google.auth.transport.requests")
        mock_transport_requests.Request = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "google": mock_google,
                "google.auth": mock_google_auth,
                "google.auth.transport": mock_transport,
                "google.auth.transport.requests": mock_transport_requests,
            },
        ):
            provider = GCPWIAuthProvider(
                registry_uri="oci://us-central1-docker.pkg.dev/my-project/my-repo"
            )

            # Get initial credentials
            provider.get_credentials()
            assert mock_google_auth.default.call_count == 1

            # Since credentials expire within buffer (5 min expiry), refresh should be needed
            refreshed = provider.refresh_if_needed()
            assert refreshed is True
            assert mock_google_auth.default.call_count == 2


class TestCreateAuthProviderCloud:
    """Tests for create_auth_provider factory with cloud providers."""

    @pytest.mark.requirement("8A-FR-007")
    def test_create_irsa_auth_provider(self) -> None:
        """Test factory creates IRSAAuthProvider for AWS IRSA auth type."""
        from floe_core.oci.auth import IRSAAuthProvider, create_auth_provider
        from floe_core.schemas.oci import AuthType, RegistryAuth

        auth_config = RegistryAuth(type=AuthType.AWS_IRSA)

        provider = create_auth_provider(
            registry_uri="oci://123456789.dkr.ecr.us-east-1.amazonaws.com/floe",
            auth_config=auth_config,
        )

        assert isinstance(provider, IRSAAuthProvider)

    @pytest.mark.requirement("8A-FR-007")
    def test_create_azure_mi_auth_provider(self) -> None:
        """Test factory creates AzureMIAuthProvider for Azure MI auth type."""
        from floe_core.oci.auth import AzureMIAuthProvider, create_auth_provider
        from floe_core.schemas.oci import AuthType, RegistryAuth

        auth_config = RegistryAuth(type=AuthType.AZURE_MANAGED_IDENTITY)

        provider = create_auth_provider(
            registry_uri="oci://myregistry.azurecr.io/floe",
            auth_config=auth_config,
        )

        assert isinstance(provider, AzureMIAuthProvider)

    @pytest.mark.requirement("8A-FR-007")
    def test_create_gcp_wi_auth_provider(self) -> None:
        """Test factory creates GCPWIAuthProvider for GCP WI auth type."""
        from floe_core.oci.auth import GCPWIAuthProvider, create_auth_provider
        from floe_core.schemas.oci import AuthType, RegistryAuth

        auth_config = RegistryAuth(type=AuthType.GCP_WORKLOAD_IDENTITY)

        provider = create_auth_provider(
            registry_uri="oci://us-central1-docker.pkg.dev/my-project/my-repo",
            auth_config=auth_config,
        )

        assert isinstance(provider, GCPWIAuthProvider)

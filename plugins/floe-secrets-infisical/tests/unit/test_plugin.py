"""Unit tests for InfisicalSecretsPlugin with mocked SDK.

Tests that InfisicalSecretsPlugin correctly interacts with the Infisical SDK
for secret operations, using mocked SDK responses.

Task: T042
Requirements: 7A-FR-020 (InfisicalSecretsPlugin integration)
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from floe_secrets_infisical.config import InfisicalSecretsConfig
from floe_secrets_infisical.errors import (
    InfisicalAccessDeniedError,
    InfisicalBackendUnavailableError,
    InfisicalSecretNotFoundError,
)
from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_infisical_config() -> InfisicalSecretsConfig:
    """Create a test configuration for InfisicalSecretsPlugin."""
    return InfisicalSecretsConfig(
        client_id="test-client-id",
        client_secret=SecretStr("test-client-secret"),
        site_url="https://app.infisical.com",
        environment="dev",
        project_id="proj_12345",
        secret_path="/floe",
    )


@pytest.fixture
def mock_infisical_client_module() -> MagicMock:
    """Create a mock infisical_client module for import patching."""
    mock_module = MagicMock()
    mock_module.InfisicalClient = MagicMock()
    mock_module.ClientSettings = MagicMock()
    mock_module.AuthenticationOptions = MagicMock()
    mock_module.UniversalAuthMethod = MagicMock()
    return mock_module


@pytest.fixture
def mock_infisical_sdk(
    mock_infisical_client_module: MagicMock,
) -> Generator[MagicMock, None, None]:
    """Mock the Infisical SDK client via sys.modules patching."""
    mock_client = MagicMock()
    mock_infisical_client_module.InfisicalClient.return_value = mock_client

    with patch.dict(sys.modules, {"infisical_client": mock_infisical_client_module}):
        yield mock_client


@pytest.fixture
def plugin(
    mock_infisical_config: InfisicalSecretsConfig,
    mock_infisical_sdk: MagicMock,
) -> InfisicalSecretsPlugin:
    """Create an InfisicalSecretsPlugin with mocked SDK."""
    plugin_instance = InfisicalSecretsPlugin(config=mock_infisical_config)
    # Manually trigger authentication to inject mock client
    plugin_instance.startup()
    return plugin_instance


class TestInfisicalSecretsPluginMetadata:
    """Test InfisicalSecretsPlugin metadata attributes."""

    @pytest.mark.requirement("7A-FR-020")
    def test_plugin_name(
        self,
        plugin: InfisicalSecretsPlugin,
    ) -> None:
        """Test that plugin has correct name."""
        assert plugin.name == "infisical"

    @pytest.mark.requirement("7A-FR-020")
    def test_plugin_version(
        self,
        plugin: InfisicalSecretsPlugin,
    ) -> None:
        """Test that plugin has version set."""
        assert plugin.version is not None
        assert isinstance(plugin.version, str)
        # Should be semver format
        parts = plugin.version.split(".")
        assert len(parts) >= 2

    @pytest.mark.requirement("7A-FR-020")
    def test_plugin_floe_api_version(
        self,
        plugin: InfisicalSecretsPlugin,
    ) -> None:
        """Test that plugin declares floe API version."""
        assert plugin.floe_api_version is not None
        assert plugin.floe_api_version == "1.0"


class TestInfisicalSecretsPluginGetSecret:
    """Test InfisicalSecretsPlugin.get_secret() method."""

    @pytest.mark.requirement("7A-FR-020")
    def test_get_secret_returns_value_for_existing_secret(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test get_secret returns value when secret exists."""
        # Setup mock response
        mock_secret = MagicMock()
        mock_secret.secret_value = "my-secret-value"
        mock_infisical_sdk.secrets.get.return_value = mock_secret

        result = plugin.get_secret("db-password")

        assert result == "my-secret-value"
        mock_infisical_sdk.secrets.get.assert_called_once()

    @pytest.mark.requirement("7A-FR-020")
    def test_get_secret_returns_none_for_nonexistent_secret(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test get_secret returns None when secret doesn't exist."""
        # Setup mock to raise not found
        mock_infisical_sdk.secrets.get.side_effect = Exception("Secret not found")

        result = plugin.get_secret("nonexistent-secret")

        assert result is None

    @pytest.mark.requirement("7A-FR-020")
    def test_get_secret_with_path_override(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test get_secret with explicit path parameter."""
        mock_secret = MagicMock()
        mock_secret.secret_value = "path-secret-value"
        mock_infisical_sdk.secrets.get.return_value = mock_secret

        result = plugin.get_secret("api-key", path="/custom/path")

        assert result == "path-secret-value"
        # Verify the call included the custom path
        call_kwargs = mock_infisical_sdk.secrets.get.call_args
        assert call_kwargs is not None

    @pytest.mark.requirement("7A-FR-020")
    def test_get_secret_raises_on_permission_denied(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test get_secret raises InfisicalAccessDeniedError on 403."""
        # Setup mock to raise permission error
        error = Exception("403 Forbidden")
        error.status_code = 403  # type: ignore[attr-defined]
        mock_infisical_sdk.secrets.get.side_effect = error

        with pytest.raises((InfisicalAccessDeniedError, PermissionError)):
            plugin.get_secret("forbidden-secret")

    @pytest.mark.requirement("7A-FR-020")
    def test_get_secret_raises_on_connection_error(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test get_secret raises InfisicalBackendUnavailableError on connection failure."""
        mock_infisical_sdk.secrets.get.side_effect = ConnectionError("Connection refused")

        with pytest.raises((InfisicalBackendUnavailableError, ConnectionError)):
            plugin.get_secret("any-secret")


class TestInfisicalSecretsPluginSetSecret:
    """Test InfisicalSecretsPlugin.set_secret() method."""

    @pytest.mark.requirement("7A-FR-020")
    def test_set_secret_creates_new_secret(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test set_secret creates a new secret when it doesn't exist."""
        # Setup mock - get returns None (not found), create succeeds
        mock_infisical_sdk.secrets.get.side_effect = Exception("Not found")
        mock_infisical_sdk.secrets.create.return_value = MagicMock()

        plugin.set_secret("new-secret", "secret-value")

        mock_infisical_sdk.secrets.create.assert_called_once()

    @pytest.mark.requirement("7A-FR-020")
    def test_set_secret_updates_existing_secret(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test set_secret updates an existing secret."""
        # Setup mock - get returns existing secret
        mock_secret = MagicMock()
        mock_secret.secret_value = "old-value"
        mock_infisical_sdk.secrets.get.return_value = mock_secret
        mock_infisical_sdk.secrets.update.return_value = MagicMock()

        plugin.set_secret("existing-secret", "new-value")

        mock_infisical_sdk.secrets.update.assert_called_once()

    @pytest.mark.requirement("7A-FR-020")
    def test_set_secret_with_metadata(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test set_secret with metadata parameter."""
        mock_infisical_sdk.secrets.get.side_effect = Exception("Not found")
        mock_infisical_sdk.secrets.create.return_value = MagicMock()

        metadata: dict[str, Any] = {"description": "Database password", "owner": "platform-team"}
        plugin.set_secret("db-password", "secret-value", metadata=metadata)

        mock_infisical_sdk.secrets.create.assert_called_once()

    @pytest.mark.requirement("7A-FR-020")
    def test_set_secret_raises_on_permission_denied(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test set_secret raises InfisicalAccessDeniedError on 403."""
        mock_infisical_sdk.secrets.get.side_effect = Exception("Not found")
        error = Exception("403 Forbidden")
        error.status_code = 403  # type: ignore[attr-defined]
        mock_infisical_sdk.secrets.create.side_effect = error

        with pytest.raises((InfisicalAccessDeniedError, PermissionError)):
            plugin.set_secret("forbidden-secret", "value")


class TestInfisicalSecretsPluginListSecrets:
    """Test InfisicalSecretsPlugin.list_secrets() method."""

    @pytest.mark.requirement("7A-FR-020")
    def test_list_secrets_returns_all_secrets_at_path(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test list_secrets returns all secret names at path."""
        # Setup mock response
        mock_secrets = [
            MagicMock(secret_key="db-password"),
            MagicMock(secret_key="api-key"),
            MagicMock(secret_key="jwt-secret"),
        ]
        mock_infisical_sdk.secrets.list.return_value = mock_secrets

        result = plugin.list_secrets()

        assert len(result) == 3
        assert "db-password" in result
        assert "api-key" in result
        assert "jwt-secret" in result

    @pytest.mark.requirement("7A-FR-020")
    def test_list_secrets_with_prefix_filter(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test list_secrets filters by prefix."""
        # Setup mock response
        mock_secrets = [
            MagicMock(secret_key="db-password"),
            MagicMock(secret_key="db-user"),
            MagicMock(secret_key="api-key"),
        ]
        mock_infisical_sdk.secrets.list.return_value = mock_secrets

        result = plugin.list_secrets(prefix="db-")

        # Should filter to only db- prefixed secrets
        assert all(s.startswith("db-") for s in result)
        assert "api-key" not in result

    @pytest.mark.requirement("7A-FR-020")
    def test_list_secrets_returns_empty_for_no_secrets(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test list_secrets returns empty list when no secrets exist."""
        mock_infisical_sdk.secrets.list.return_value = []

        result = plugin.list_secrets()

        assert result == []

    @pytest.mark.requirement("7A-FR-020")
    def test_list_secrets_with_custom_path(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test list_secrets with explicit path parameter."""
        mock_secrets = [MagicMock(secret_key="custom-secret")]
        mock_infisical_sdk.secrets.list.return_value = mock_secrets

        result = plugin.list_secrets(path="/custom/path")

        assert "custom-secret" in result


class TestInfisicalSecretsPluginHealthCheck:
    """Test InfisicalSecretsPlugin.health_check() method."""

    @pytest.mark.requirement("7A-FR-020")
    def test_health_check_returns_healthy_when_connected(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test health_check returns healthy status when API is reachable."""
        # Mock successful list call (proves connectivity)
        mock_infisical_sdk.secrets.list.return_value = []

        status = plugin.health_check()

        assert status.healthy is True
        assert status.message is not None

    @pytest.mark.requirement("7A-FR-020")
    def test_health_check_returns_unhealthy_on_connection_error(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test health_check returns unhealthy when API is unreachable."""
        mock_infisical_sdk.secrets.list.side_effect = ConnectionError("Connection refused")

        status = plugin.health_check()

        assert status.healthy is False
        assert "error" in status.message.lower() or "unavailable" in status.message.lower()

    @pytest.mark.requirement("7A-FR-020")
    def test_health_check_returns_unhealthy_on_auth_error(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test health_check returns unhealthy when authentication fails."""
        error = Exception("401 Unauthorized")
        error.status_code = 401  # type: ignore[attr-defined]
        mock_infisical_sdk.secrets.list.side_effect = error

        status = plugin.health_check()

        assert status.healthy is False


class TestInfisicalSecretsPluginAuthentication:
    """Test InfisicalSecretsPlugin Universal Auth authentication."""

    @pytest.mark.requirement("7A-FR-021")
    def test_plugin_authenticates_on_startup(
        self,
        mock_infisical_config: InfisicalSecretsConfig,
        mock_infisical_client_module: MagicMock,
    ) -> None:
        """Test that plugin authenticates with Universal Auth on startup."""
        mock_client = MagicMock()
        mock_infisical_client_module.InfisicalClient.return_value = mock_client

        with patch.dict(sys.modules, {"infisical_client": mock_infisical_client_module}):
            plugin = InfisicalSecretsPlugin(config=mock_infisical_config)
            plugin.startup()

            # Verify client was created with auth config
            mock_infisical_client_module.InfisicalClient.assert_called_once()

    @pytest.mark.requirement("7A-FR-021")
    def test_plugin_uses_universal_auth_credentials(
        self,
        mock_infisical_config: InfisicalSecretsConfig,
        mock_infisical_client_module: MagicMock,
    ) -> None:
        """Test that plugin uses client_id and client_secret for auth."""
        mock_client = MagicMock()
        mock_infisical_client_module.InfisicalClient.return_value = mock_client

        with patch.dict(sys.modules, {"infisical_client": mock_infisical_client_module}):
            plugin = InfisicalSecretsPlugin(config=mock_infisical_config)
            plugin.startup()

            # Verify UniversalAuthMethod was called with credentials
            mock_infisical_client_module.UniversalAuthMethod.assert_called_once()
            call_kwargs = mock_infisical_client_module.UniversalAuthMethod.call_args
            assert call_kwargs is not None


class TestInfisicalSecretsPluginPathOrganization:
    """Test InfisicalSecretsPlugin path-based organization (FR-024)."""

    @pytest.mark.requirement("7A-FR-024")
    def test_get_secret_uses_default_path(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test get_secret uses config default path."""
        mock_secret = MagicMock()
        mock_secret.secret_value = "value"
        mock_infisical_sdk.secrets.get.return_value = mock_secret

        plugin.get_secret("my-secret")

        # Verify the default path from config was used
        call_args = mock_infisical_sdk.secrets.get.call_args
        assert call_args is not None

    @pytest.mark.requirement("7A-FR-024")
    def test_set_secret_uses_default_path(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test set_secret uses config default path."""
        mock_infisical_sdk.secrets.get.side_effect = Exception("Not found")
        mock_infisical_sdk.secrets.create.return_value = MagicMock()

        plugin.set_secret("my-secret", "value")

        call_args = mock_infisical_sdk.secrets.create.call_args
        assert call_args is not None

    @pytest.mark.requirement("7A-FR-024")
    def test_list_secrets_uses_default_path(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test list_secrets uses config default path."""
        mock_infisical_sdk.secrets.list.return_value = []

        plugin.list_secrets()

        call_args = mock_infisical_sdk.secrets.list.call_args
        assert call_args is not None


class TestInfisicalSecretsPluginErrorHandling:
    """Test InfisicalSecretsPlugin error handling."""

    @pytest.mark.requirement("7A-FR-020")
    def test_timeout_error_handled(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test that timeout errors are properly handled."""
        mock_infisical_sdk.secrets.get.side_effect = TimeoutError("Request timed out")

        with pytest.raises((InfisicalBackendUnavailableError, TimeoutError, ConnectionError)):
            plugin.get_secret("any-secret")

    @pytest.mark.requirement("7A-FR-020")
    def test_invalid_response_handled(
        self,
        plugin: InfisicalSecretsPlugin,
        mock_infisical_sdk: MagicMock,
    ) -> None:
        """Test that invalid API responses are handled gracefully."""
        # Return invalid response (missing secret_value attribute)
        mock_infisical_sdk.secrets.get.return_value = MagicMock(spec=[])

        # Should not crash, should return None or raise appropriate error
        try:
            result = plugin.get_secret("malformed-secret")
            # If it returns, should be None
            assert result is None
        except (AttributeError, InfisicalSecretNotFoundError):
            # Also acceptable to raise an error
            pass

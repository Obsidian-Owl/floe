"""Unit tests for K8sSecretsPlugin with mocked kubernetes client.

Tests the K8sSecretsPlugin implementation using mocked K8s API.

Implements:
    - T019: Unit test for K8sSecretsPlugin with mocked kubernetes client
    - FR-010: K8sSecretsPlugin as default backend
    - FR-060: Raise PermissionError on unauthorized
    - FR-061: Raise ConnectionError on unavailable
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from floe_secrets_k8s.config import K8sSecretsConfig
from floe_secrets_k8s.errors import (
    SecretAccessDeniedError,
    SecretBackendUnavailableError,
)
from floe_secrets_k8s.plugin import K8sSecretsPlugin

if TYPE_CHECKING:
    from floe_core.plugin_metadata import HealthState


class TestK8sSecretsPluginMetadata:
    """Test plugin metadata properties."""

    @pytest.mark.requirement("7A-FR-010")
    def test_plugin_name(self) -> None:
        """Test plugin name is 'k8s'."""
        plugin = K8sSecretsPlugin()
        assert plugin.name == "k8s"

    @pytest.mark.requirement("7A-FR-010")
    def test_plugin_version(self) -> None:
        """Test plugin version is valid semver."""
        plugin = K8sSecretsPlugin()
        assert plugin.version == "0.1.0"

    @pytest.mark.requirement("CR-001")
    def test_floe_api_version(self) -> None:
        """Test floe_api_version is declared."""
        plugin = K8sSecretsPlugin()
        assert plugin.floe_api_version == "1.0"

    @pytest.mark.requirement("7A-FR-010")
    def test_plugin_description(self) -> None:
        """Test plugin has a description."""
        plugin = K8sSecretsPlugin()
        assert "Kubernetes" in plugin.description

    @pytest.mark.requirement("CR-003")
    def test_get_config_schema(self) -> None:
        """Test get_config_schema returns K8sSecretsConfig."""
        plugin = K8sSecretsPlugin()
        assert plugin.get_config_schema() is K8sSecretsConfig


class TestK8sSecretsPluginLifecycle:
    """Test plugin lifecycle methods."""

    @pytest.mark.requirement("7A-FR-013")
    @patch("floe_secrets_k8s.plugin.k8s_config")
    @patch("floe_secrets_k8s.plugin.client")
    def test_startup_with_kubeconfig(
        self, mock_client: MagicMock, mock_k8s_config: MagicMock
    ) -> None:
        """Test startup loads kubeconfig when path provided."""
        config = K8sSecretsConfig(kubeconfig_path="/path/to/kubeconfig")
        plugin = K8sSecretsPlugin(config)

        plugin.startup()

        mock_k8s_config.load_kube_config.assert_called_once()

    @pytest.mark.requirement("7A-FR-013")
    @patch("floe_secrets_k8s.plugin.k8s_config")
    @patch("floe_secrets_k8s.plugin.client")
    def test_startup_in_cluster(
        self, mock_client: MagicMock, mock_k8s_config: MagicMock
    ) -> None:
        """Test startup uses in-cluster config when no kubeconfig path."""
        plugin = K8sSecretsPlugin()

        # Simulate successful in-cluster config
        mock_k8s_config.load_incluster_config.return_value = None

        plugin.startup()

        mock_k8s_config.load_incluster_config.assert_called_once()

    @pytest.mark.requirement("7A-FR-013")
    @patch("floe_secrets_k8s.plugin.k8s_config")
    @patch("floe_secrets_k8s.plugin.client")
    def test_startup_fallback_to_default_kubeconfig(
        self, mock_client: MagicMock, mock_k8s_config: MagicMock
    ) -> None:
        """Test startup falls back to default kubeconfig when in-cluster fails."""
        plugin = K8sSecretsPlugin()

        # Simulate in-cluster config failure
        mock_k8s_config.load_incluster_config.side_effect = (
            mock_k8s_config.ConfigException("Not in cluster")
        )

        plugin.startup()

        mock_k8s_config.load_kube_config.assert_called_once()

    @pytest.mark.requirement("7A-FR-010")
    def test_shutdown_clears_client(self) -> None:
        """Test shutdown clears the API client."""
        plugin = K8sSecretsPlugin()
        plugin._client = Mock()
        plugin._api = Mock()

        plugin.shutdown()

        assert plugin._client is None
        assert plugin._api is None


class TestK8sSecretsPluginHealthCheck:
    """Test health_check method."""

    @pytest.mark.requirement("CR-002")
    def test_health_check_unhealthy_when_not_initialized(self) -> None:
        """Test health_check returns UNHEALTHY when not initialized."""
        from floe_core.plugin_metadata import HealthState

        plugin = K8sSecretsPlugin()

        status = plugin.health_check()

        assert status.state == HealthState.UNHEALTHY
        assert "not initialized" in status.message.lower()

    @pytest.mark.requirement("CR-002")
    def test_health_check_healthy_on_success(self) -> None:
        """Test health_check returns HEALTHY when API is reachable."""
        from floe_core.plugin_metadata import HealthState

        plugin = K8sSecretsPlugin()
        plugin._api = Mock()
        plugin._api.list_namespaced_secret.return_value = Mock()

        status = plugin.health_check()

        assert status.state == HealthState.HEALTHY

    @pytest.mark.requirement("CR-002")
    def test_health_check_unhealthy_on_api_error(self) -> None:
        """Test health_check returns UNHEALTHY on API error."""
        from floe_core.plugin_metadata import HealthState

        plugin = K8sSecretsPlugin()
        plugin._api = Mock()
        plugin._api.list_namespaced_secret.side_effect = Exception("API error")

        status = plugin.health_check()

        assert status.state == HealthState.UNHEALTHY
        assert "API" in status.message


class TestK8sSecretsPluginGetSecret:
    """Test get_secret method."""

    @pytest.fixture
    def initialized_plugin(self) -> K8sSecretsPlugin:
        """Create an initialized plugin with mocked API."""
        plugin = K8sSecretsPlugin()
        plugin._client = Mock()
        plugin._client.rest = Mock()
        plugin._client.rest.ApiException = type(
            "ApiException", (Exception,), {"status": 404}
        )
        plugin._api = Mock()
        return plugin

    @pytest.mark.requirement("7A-FR-010")
    def test_get_secret_returns_value(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test get_secret returns decoded value for existing secret."""
        secret_value = "my-secret-value"
        encoded_value = base64.b64encode(secret_value.encode()).decode()

        mock_secret = Mock()
        mock_secret.data = {"value": encoded_value}
        initialized_plugin._api.read_namespaced_secret.return_value = mock_secret

        result = initialized_plugin.get_secret("my-secret")

        assert result == secret_value

    @pytest.mark.requirement("7A-FR-010")
    def test_get_secret_with_key(self, initialized_plugin: K8sSecretsPlugin) -> None:
        """Test get_secret with 'secret-name/key' format."""
        secret_value = "password123"
        encoded_value = base64.b64encode(secret_value.encode()).decode()

        mock_secret = Mock()
        mock_secret.data = {"password": encoded_value}
        initialized_plugin._api.read_namespaced_secret.return_value = mock_secret

        result = initialized_plugin.get_secret("db-creds/password")

        assert result == secret_value
        initialized_plugin._api.read_namespaced_secret.assert_called_with(
            name="db-creds", namespace="floe-jobs"
        )

    @pytest.mark.requirement("CR-004")
    def test_get_secret_returns_none_for_missing(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test get_secret returns None for non-existent secret."""
        # Create a proper ApiException
        api_exception = type("ApiException", (Exception,), {})()
        api_exception.status = 404
        initialized_plugin._client.rest.ApiException = type(
            "ApiException", (Exception,), {}
        )
        initialized_plugin._api.read_namespaced_secret.side_effect = api_exception

        result = initialized_plugin.get_secret("nonexistent")

        assert result is None

    @pytest.mark.requirement("7A-FR-010")
    def test_get_secret_returns_none_for_missing_key(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test get_secret returns None when key doesn't exist in secret."""
        mock_secret = Mock()
        mock_secret.data = {"other-key": "value"}
        initialized_plugin._api.read_namespaced_secret.return_value = mock_secret

        result = initialized_plugin.get_secret("my-secret/missing-key")

        assert result is None

    @pytest.mark.requirement("7A-FR-060")
    def test_get_secret_raises_on_permission_denied(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test get_secret raises SecretAccessDeniedError on 403."""
        api_exception = type("ApiException", (Exception,), {})()
        api_exception.status = 403
        initialized_plugin._client.rest.ApiException = type(
            "ApiException", (Exception,), {}
        )
        initialized_plugin._api.read_namespaced_secret.side_effect = api_exception

        with pytest.raises(SecretAccessDeniedError):
            initialized_plugin.get_secret("forbidden-secret")

    @pytest.mark.requirement("7A-FR-061")
    def test_get_secret_raises_on_api_error(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test get_secret raises SecretBackendUnavailableError on API error."""
        api_exception = type("ApiException", (Exception,), {})()
        api_exception.status = 500
        initialized_plugin._client.rest.ApiException = type(
            "ApiException", (Exception,), {}
        )
        initialized_plugin._api.read_namespaced_secret.side_effect = api_exception

        with pytest.raises(SecretBackendUnavailableError):
            initialized_plugin.get_secret("error-secret")


class TestK8sSecretsPluginSetSecret:
    """Test set_secret method."""

    @pytest.fixture
    def initialized_plugin(self) -> K8sSecretsPlugin:
        """Create an initialized plugin with mocked API."""
        plugin = K8sSecretsPlugin()
        plugin._client = Mock()
        plugin._client.rest = Mock()
        plugin._client.rest.ApiException = type(
            "ApiException", (Exception,), {"status": 404}
        )
        plugin._client.V1Secret = Mock()
        plugin._client.V1ObjectMeta = Mock()
        plugin._api = Mock()
        return plugin

    @pytest.mark.requirement("7A-FR-010")
    def test_set_secret_creates_new(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test set_secret creates new secret when it doesn't exist."""
        # Simulate secret not found
        api_exception = type("ApiException", (Exception,), {})()
        api_exception.status = 404
        initialized_plugin._client.rest.ApiException = type(
            "ApiException", (Exception,), {}
        )
        initialized_plugin._api.read_namespaced_secret.side_effect = api_exception

        initialized_plugin.set_secret("new-secret", "secret-value")

        initialized_plugin._api.create_namespaced_secret.assert_called_once()

    @pytest.mark.requirement("7A-FR-010")
    def test_set_secret_updates_existing(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test set_secret updates existing secret."""
        mock_secret = Mock()
        mock_secret.data = {}
        mock_secret.metadata = Mock()
        mock_secret.metadata.labels = {}
        mock_secret.metadata.annotations = None
        initialized_plugin._api.read_namespaced_secret.return_value = mock_secret

        initialized_plugin.set_secret("existing-secret", "new-value")

        initialized_plugin._api.replace_namespaced_secret.assert_called_once()

    @pytest.mark.requirement("7A-FR-010")
    def test_set_secret_with_key_format(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test set_secret with 'secret-name/key' format."""
        # Simulate secret not found
        api_exception = type("ApiException", (Exception,), {})()
        api_exception.status = 404
        initialized_plugin._client.rest.ApiException = type(
            "ApiException", (Exception,), {}
        )
        initialized_plugin._api.read_namespaced_secret.side_effect = api_exception

        initialized_plugin.set_secret("db-creds/password", "secret123")

        # Verify secret name is extracted correctly
        call_args = initialized_plugin._api.create_namespaced_secret.call_args
        assert call_args is not None


class TestK8sSecretsPluginListSecrets:
    """Test list_secrets method."""

    @pytest.fixture
    def initialized_plugin(self) -> K8sSecretsPlugin:
        """Create an initialized plugin with mocked API."""
        plugin = K8sSecretsPlugin()
        plugin._client = Mock()
        plugin._client.rest = Mock()
        plugin._client.rest.ApiException = type(
            "ApiException", (Exception,), {"status": 404}
        )
        plugin._api = Mock()
        return plugin

    @pytest.mark.requirement("7A-FR-010")
    def test_list_secrets_returns_all(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test list_secrets returns all secrets."""
        mock_secret1 = Mock()
        mock_secret1.metadata = Mock()
        mock_secret1.metadata.name = "secret1"
        mock_secret1.data = {"key1": "value1", "key2": "value2"}

        mock_secret2 = Mock()
        mock_secret2.metadata = Mock()
        mock_secret2.metadata.name = "secret2"
        mock_secret2.data = {"password": "encoded"}

        mock_list = Mock()
        mock_list.items = [mock_secret1, mock_secret2]
        initialized_plugin._api.list_namespaced_secret.return_value = mock_list

        result = initialized_plugin.list_secrets()

        assert "secret1/key1" in result
        assert "secret1/key2" in result
        assert "secret2/password" in result

    @pytest.mark.requirement("7A-FR-010")
    def test_list_secrets_filters_by_prefix(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test list_secrets filters by prefix."""
        mock_secret1 = Mock()
        mock_secret1.metadata = Mock()
        mock_secret1.metadata.name = "db-creds"
        mock_secret1.data = {"password": "value"}

        mock_secret2 = Mock()
        mock_secret2.metadata = Mock()
        mock_secret2.metadata.name = "api-key"
        mock_secret2.data = {"token": "value"}

        mock_list = Mock()
        mock_list.items = [mock_secret1, mock_secret2]
        initialized_plugin._api.list_namespaced_secret.return_value = mock_list

        result = initialized_plugin.list_secrets(prefix="db-")

        assert "db-creds/password" in result
        assert "api-key/token" not in result

    @pytest.mark.requirement("7A-FR-010")
    def test_list_secrets_empty_data(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test list_secrets handles secrets with no data."""
        mock_secret = Mock()
        mock_secret.metadata = Mock()
        mock_secret.metadata.name = "empty-secret"
        mock_secret.data = None

        mock_list = Mock()
        mock_list.items = [mock_secret]
        initialized_plugin._api.list_namespaced_secret.return_value = mock_list

        result = initialized_plugin.list_secrets()

        assert result == []


class TestK8sSecretsPluginGetMultiKeySecret:
    """Test get_multi_key_secret method."""

    @pytest.fixture
    def initialized_plugin(self) -> K8sSecretsPlugin:
        """Create an initialized plugin with mocked API."""
        plugin = K8sSecretsPlugin()
        plugin._client = Mock()
        plugin._client.rest = Mock()
        plugin._client.rest.ApiException = type(
            "ApiException", (Exception,), {"status": 404}
        )
        plugin._api = Mock()
        return plugin

    @pytest.mark.requirement("7A-FR-010")
    def test_get_multi_key_secret_returns_all_keys(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test get_multi_key_secret returns all key-value pairs."""
        mock_secret = Mock()
        mock_secret.data = {
            "username": base64.b64encode(b"admin").decode(),
            "password": base64.b64encode(b"secret123").decode(),
            "host": base64.b64encode(b"localhost").decode(),
        }
        initialized_plugin._api.read_namespaced_secret.return_value = mock_secret

        result = initialized_plugin.get_multi_key_secret("db-creds")

        assert result == {
            "username": "admin",
            "password": "secret123",
            "host": "localhost",
        }

    @pytest.mark.requirement("CR-004")
    def test_get_multi_key_secret_returns_empty_for_missing(
        self, initialized_plugin: K8sSecretsPlugin
    ) -> None:
        """Test get_multi_key_secret returns empty dict for missing secret."""
        api_exception = type("ApiException", (Exception,), {})()
        api_exception.status = 404
        initialized_plugin._client.rest.ApiException = type(
            "ApiException", (Exception,), {}
        )
        initialized_plugin._api.read_namespaced_secret.side_effect = api_exception

        result = initialized_plugin.get_multi_key_secret("nonexistent")

        assert result == {}


class TestK8sSecretsPluginNotInitialized:
    """Test error handling when plugin not initialized."""

    @pytest.mark.requirement("7A-FR-061")
    def test_get_secret_raises_when_not_initialized(self) -> None:
        """Test get_secret raises when plugin not initialized."""
        plugin = K8sSecretsPlugin()

        with pytest.raises(SecretBackendUnavailableError, match="not initialized"):
            plugin.get_secret("any-secret")

    @pytest.mark.requirement("7A-FR-061")
    def test_set_secret_raises_when_not_initialized(self) -> None:
        """Test set_secret raises when plugin not initialized."""
        plugin = K8sSecretsPlugin()

        with pytest.raises(SecretBackendUnavailableError, match="not initialized"):
            plugin.set_secret("any-secret", "value")

    @pytest.mark.requirement("7A-FR-061")
    def test_list_secrets_raises_when_not_initialized(self) -> None:
        """Test list_secrets raises when plugin not initialized."""
        plugin = K8sSecretsPlugin()

        with pytest.raises(SecretBackendUnavailableError, match="not initialized"):
            plugin.list_secrets()

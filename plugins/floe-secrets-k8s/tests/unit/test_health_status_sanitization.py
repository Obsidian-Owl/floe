"""Health/status sanitization tests for K8s secrets plugin."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
from floe_core.plugin_metadata import HealthState

from floe_secrets_k8s.errors import SecretBackendUnavailableError
from floe_secrets_k8s.plugin import K8sSecretsPlugin


@pytest.fixture
def mock_kubernetes_modules() -> MagicMock:
    """Mock the kubernetes module for import-time patching."""
    mock_client = MagicMock()
    mock_config = MagicMock()
    mock_config.ConfigException = type("ConfigException", (Exception,), {})

    mock_kubernetes = MagicMock()
    mock_kubernetes.client = mock_client
    mock_kubernetes.config = mock_config
    return mock_kubernetes


class TestK8sSecretsPluginHealthStatusSanitization:
    """Test health/status surfaces do not expose provider exception details."""

    @pytest.mark.requirement("SEC-OBS-005")
    def test_startup_logs_sanitized_initialization_failure(
        self, mock_kubernetes_modules: MagicMock
    ) -> None:
        toxic_error = RuntimeError(
            "503 https://k8s.example/api?token=raw-token "
            "password=raw-password private_key=raw-key person@example.com"
        )
        mock_kubernetes_modules.config.load_incluster_config.side_effect = toxic_error
        plugin = K8sSecretsPlugin()

        with (
            patch.dict(sys.modules, {"kubernetes": mock_kubernetes_modules}),
            patch("floe_secrets_k8s.plugin.logger") as mock_logger,
            pytest.raises(SecretBackendUnavailableError),
        ):
            plugin.startup()

        mock_logger.exception.assert_not_called()
        log_text = repr(mock_logger.method_calls)
        assert "raw-token" not in log_text
        assert "raw-password" not in log_text
        assert "raw-key" not in log_text
        assert "k8s.example" not in log_text
        assert "person@example.com" not in log_text

    @pytest.mark.requirement("SEC-OBS-005")
    def test_health_check_sanitizes_provider_error_message(self) -> None:
        plugin = K8sSecretsPlugin()
        plugin._api = Mock()
        plugin._api.list_namespaced_secret.side_effect = Exception(
            "503 https://k8s.example/api?token=raw-token "
            "password=raw-password private_key=raw-key person@example.com"
        )

        status = plugin.health_check()

        assert status.state == HealthState.UNHEALTHY
        assert status.message == "K8s API check failed: unavailable"
        assert "raw-token" not in status.message
        assert "raw-password" not in status.message
        assert "raw-key" not in status.message
        assert "k8s.example" not in status.message
        assert "person@example.com" not in status.message

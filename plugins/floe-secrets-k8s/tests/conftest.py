"""Pytest configuration for floe-secrets-k8s tests.

This module provides shared fixtures for both unit and integration tests.

Implements:
    - T033: Test fixtures and conftest.py for floe-secrets-k8s

Fixtures:
    - k8s_config: K8sSecretsConfig with test defaults
    - mock_k8s_client: Mocked kubernetes client module
    - mock_k8s_api: Mocked CoreV1Api
    - k8s_plugin: K8sSecretsPlugin with mocked API (unit tests)
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def k8s_config() -> Any:
    """Create K8sSecretsConfig with test defaults.

    Returns:
        K8sSecretsConfig configured for testing.
    """
    from floe_secrets_k8s.config import K8sSecretsConfig

    return K8sSecretsConfig(
        namespace="floe-test",
        labels={"managed-by": "floe-test"},
    )


@pytest.fixture
def k8s_config_with_kubeconfig(tmp_path: Any) -> Any:
    """Create K8sSecretsConfig with explicit kubeconfig path.

    Args:
        tmp_path: Pytest tmp_path fixture.

    Returns:
        K8sSecretsConfig with kubeconfig path set.
    """
    from floe_secrets_k8s.config import K8sSecretsConfig

    # Create a dummy kubeconfig file
    kubeconfig = tmp_path / "kubeconfig"
    kubeconfig.write_text("# dummy kubeconfig")

    return K8sSecretsConfig(
        namespace="floe-test",
        kubeconfig_path=str(kubeconfig),
        context="test-context",
    )


# =============================================================================
# Mock Fixtures for Unit Tests
# =============================================================================


@pytest.fixture
def mock_k8s_client() -> MagicMock:
    """Create mocked kubernetes client module.

    Returns:
        MagicMock configured as kubernetes client.
    """
    mock_client = MagicMock()

    # Mock V1Secret
    mock_client.V1Secret = MagicMock()
    mock_client.V1ObjectMeta = MagicMock()

    # Mock ApiException
    class MockApiException(Exception):
        """Mock Kubernetes API Exception."""

        def __init__(self, status: int = 500, reason: str = "Error") -> None:
            self.status = status
            self.reason = reason
            super().__init__(f"{status}: {reason}")

    mock_client.rest = MagicMock()
    mock_client.rest.ApiException = MockApiException

    return mock_client


@pytest.fixture
def mock_k8s_api() -> MagicMock:
    """Create mocked CoreV1Api.

    Returns:
        MagicMock configured as CoreV1Api.
    """
    return MagicMock()


@pytest.fixture
def mock_secret_data() -> dict[str, str]:
    """Create sample secret data (base64 encoded).

    Returns:
        Dictionary of base64-encoded secret values.
    """
    return {
        "username": base64.b64encode(b"testuser").decode(),
        "credential": base64.b64encode(b"test-value").decode(),
        "host": base64.b64encode(b"localhost").decode(),
    }


@pytest.fixture
def mock_k8s_secret(mock_secret_data: dict[str, str]) -> Mock:
    """Create a mock K8s Secret object.

    Args:
        mock_secret_data: Base64-encoded secret data.

    Returns:
        Mock V1Secret object.
    """
    secret = Mock()
    secret.metadata = Mock()
    secret.metadata.name = "test-secret"
    secret.metadata.labels = {"managed-by": "floe-test"}
    secret.metadata.annotations = None
    secret.data = mock_secret_data
    return secret


# =============================================================================
# Plugin Fixtures
# =============================================================================


@pytest.fixture
def k8s_plugin_uninitialized(k8s_config: Any) -> Any:
    """Create K8sSecretsPlugin without initialization.

    Useful for testing startup/shutdown behavior.

    Args:
        k8s_config: K8sSecretsConfig fixture.

    Returns:
        Uninitialized K8sSecretsPlugin.
    """
    from floe_secrets_k8s.plugin import K8sSecretsPlugin

    return K8sSecretsPlugin(k8s_config)


@pytest.fixture
def k8s_plugin_mocked(
    k8s_config: Any,
    mock_k8s_client: MagicMock,
    mock_k8s_api: MagicMock,
) -> Any:
    """Create K8sSecretsPlugin with mocked K8s API.

    For unit tests that don't need real K8s connectivity.

    Args:
        k8s_config: K8sSecretsConfig fixture.
        mock_k8s_client: Mocked kubernetes client.
        mock_k8s_api: Mocked CoreV1Api.

    Returns:
        K8sSecretsPlugin with mocked dependencies.
    """
    from floe_secrets_k8s.plugin import K8sSecretsPlugin

    plugin = K8sSecretsPlugin(k8s_config)
    plugin._client = mock_k8s_client
    plugin._api = mock_k8s_api
    return plugin


# =============================================================================
# Secret List Fixtures
# =============================================================================


@pytest.fixture
def mock_secret_list(mock_k8s_secret: Mock) -> Mock:
    """Create a mock V1SecretList.

    Args:
        mock_k8s_secret: Mock secret object.

    Returns:
        Mock V1SecretList with one secret.
    """
    secret_list = Mock()
    secret_list.items = [mock_k8s_secret]
    return secret_list


@pytest.fixture
def mock_empty_secret_list() -> Mock:
    """Create a mock empty V1SecretList.

    Returns:
        Mock V1SecretList with no secrets.
    """
    secret_list = Mock()
    secret_list.items = []
    return secret_list


# =============================================================================
# Exception Fixtures
# =============================================================================


@pytest.fixture
def api_exception_404(mock_k8s_client: MagicMock) -> Any:
    """Create a 404 Not Found API exception.

    Args:
        mock_k8s_client: Mocked kubernetes client.

    Returns:
        ApiException with 404 status.
    """
    return mock_k8s_client.rest.ApiException(status=404, reason="Not Found")


@pytest.fixture
def api_exception_403(mock_k8s_client: MagicMock) -> Any:
    """Create a 403 Forbidden API exception.

    Args:
        mock_k8s_client: Mocked kubernetes client.

    Returns:
        ApiException with 403 status.
    """
    return mock_k8s_client.rest.ApiException(status=403, reason="Forbidden")


@pytest.fixture
def api_exception_500(mock_k8s_client: MagicMock) -> Any:
    """Create a 500 Internal Server Error API exception.

    Args:
        mock_k8s_client: Mocked kubernetes client.

    Returns:
        ApiException with 500 status.
    """
    return mock_k8s_client.rest.ApiException(status=500, reason="Internal Server Error")

"""Pytest configuration for floe-secrets-infisical unit tests.

This module provides fixtures specific to unit tests with mocked dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from floe_secrets_infisical.config import InfisicalSecretsConfig
    from floe_secrets_infisical.plugin import InfisicalSecretsPlugin


@pytest.fixture
def mock_infisical_client() -> Generator[MagicMock, None, None]:
    """Create a mocked Infisical client.

    This fixture patches the InfisicalClient class and returns a mock
    that can be configured for different test scenarios.

    Yields:
        MagicMock representing the Infisical client instance.
    """
    with patch("floe_secrets_infisical.plugin.InfisicalClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_infisical_sdk() -> Generator[dict[str, Any], None, None]:
    """Create mocked Infisical SDK components.

    This fixture patches all Infisical SDK imports and returns a dict
    of mocks for configuration.

    Yields:
        Dictionary with keys: client_class, client, settings_class, auth_class, etc.
    """
    with patch.dict(
        "sys.modules",
        {
            "infisical_client": MagicMock(),
        },
    ):
        with patch(
            "floe_secrets_infisical.plugin.InfisicalClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            yield {
                "client_class": mock_client_class,
                "client": mock_client,
            }


@pytest.fixture
def infisical_plugin_with_mock(
    infisical_config: InfisicalSecretsConfig,
    mock_infisical_client: MagicMock,
) -> InfisicalSecretsPlugin:
    """Create InfisicalSecretsPlugin with a mocked client.

    This fixture creates a plugin instance suitable for unit testing
    where the Infisical SDK is mocked.

    Args:
        infisical_config: Config fixture from parent conftest.
        mock_infisical_client: Mocked client fixture.

    Returns:
        InfisicalSecretsPlugin with mocked dependencies.
    """
    from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

    plugin = InfisicalSecretsPlugin(config=infisical_config)
    # Manually set client to bypass authentication
    plugin._client = mock_infisical_client
    plugin._authenticated = True

    return plugin


@pytest.fixture
def mock_secret_response() -> MagicMock:
    """Create a mock secret response object.

    Returns:
        MagicMock with secret_value and secret_key attributes.
    """
    mock = MagicMock()
    mock.secret_value = "test-secret-value"
    mock.secret_key = "test-secret-key"
    return mock


@pytest.fixture
def mock_secrets_list() -> list[MagicMock]:
    """Create a list of mock secret objects.

    Returns:
        List of MagicMock objects with secret_key attributes.
    """
    secrets = []
    for key in ["db-password", "api-key", "redis-url", "db-username"]:
        mock = MagicMock()
        mock.secret_key = key
        secrets.append(mock)
    return secrets

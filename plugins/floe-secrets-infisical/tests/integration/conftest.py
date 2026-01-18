"""Pytest configuration for floe-secrets-infisical integration tests.

This module provides fixtures specific to integration tests with real Infisical.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

import pytest
from pydantic import SecretStr

if TYPE_CHECKING:
    from collections.abc import Generator

    from floe_secrets_infisical.config import InfisicalSecretsConfig
    from floe_secrets_infisical.plugin import InfisicalSecretsPlugin


# Environment variable names for Infisical credentials
ENV_CLIENT_ID = "INFISICAL_CLIENT_ID"
ENV_CLIENT_SECRET = "INFISICAL_CLIENT_SECRET"
ENV_PROJECT_ID = "INFISICAL_PROJECT_ID"
ENV_SITE_URL = "INFISICAL_SITE_URL"


def _infisical_credentials_available() -> bool:
    """Check if Infisical credentials are available in environment."""
    return bool(
        os.environ.get(ENV_CLIENT_ID)
        and os.environ.get(ENV_CLIENT_SECRET)
        and os.environ.get(ENV_PROJECT_ID)
    )


@pytest.fixture
def unique_test_path() -> str:
    """Generate a unique path for test isolation.

    Returns:
        Unique path like /floe-test-abc12345.
    """
    return f"/floe-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def live_infisical_config(unique_test_path: str) -> InfisicalSecretsConfig:
    """Create InfisicalSecretsConfig from environment for live testing.

    This fixture creates a config using real credentials from environment
    variables. Tests using this fixture will make real API calls.

    Args:
        unique_test_path: Unique path for test isolation.

    Returns:
        InfisicalSecretsConfig with real credentials.

    Raises:
        pytest.fail: If credentials are not available.
    """
    if not _infisical_credentials_available():
        pytest.fail(
            f"Infisical credentials not available. "
            f"Set {ENV_CLIENT_ID}, {ENV_CLIENT_SECRET}, {ENV_PROJECT_ID}"
        )

    from floe_secrets_infisical.config import InfisicalSecretsConfig

    return InfisicalSecretsConfig(
        client_id=os.environ[ENV_CLIENT_ID],
        client_secret=SecretStr(os.environ[ENV_CLIENT_SECRET]),
        project_id=os.environ[ENV_PROJECT_ID],
        site_url=os.environ.get(ENV_SITE_URL, "https://app.infisical.com"),
        environment="dev",
        secret_path=unique_test_path,
    )


@pytest.fixture
def live_infisical_plugin(
    live_infisical_config: InfisicalSecretsConfig,
) -> Generator[InfisicalSecretsPlugin, None, None]:
    """Create InfisicalSecretsPlugin with real Infisical connection.

    This fixture creates a fully functional plugin connected to a real
    Infisical instance. It handles cleanup of test secrets after each test.

    Args:
        live_infisical_config: Config with real credentials.

    Yields:
        InfisicalSecretsPlugin connected to real Infisical.
    """
    from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

    plugin = InfisicalSecretsPlugin(config=live_infisical_config)
    plugin.startup()

    yield plugin

    # Cleanup: delete any secrets created during test
    try:
        secrets = plugin.list_secrets()
        for secret_key in secrets:
            try:
                plugin.delete_secret(secret_key)
            except Exception:
                pass  # Best effort cleanup
    except Exception:
        pass

    plugin.shutdown()


@pytest.fixture
def test_secret_key() -> str:
    """Generate a unique secret key for testing.

    Returns:
        Unique key like test-secret-abc12345.
    """
    return f"test-secret-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_secret_value() -> str:
    """Generate a unique secret value for testing.

    Returns:
        Unique value like test-value-abc12345.
    """
    return f"test-value-{uuid.uuid4().hex}"

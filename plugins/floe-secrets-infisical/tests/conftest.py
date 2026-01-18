"""Pytest configuration for floe-secrets-infisical tests.

This module provides shared fixtures for both unit and integration tests.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from pydantic import SecretStr

if TYPE_CHECKING:
    from floe_secrets_infisical.config import InfisicalSecretsConfig


# Environment variable names for Infisical credentials
ENV_CLIENT_ID = "INFISICAL_CLIENT_ID"
ENV_CLIENT_SECRET = "INFISICAL_CLIENT_SECRET"
ENV_PROJECT_ID = "INFISICAL_PROJECT_ID"
ENV_SITE_URL = "INFISICAL_SITE_URL"


def infisical_credentials_available() -> bool:
    """Check if Infisical credentials are available in environment.

    Returns:
        True if all required credentials are set.
    """
    return bool(
        os.environ.get(ENV_CLIENT_ID)
        and os.environ.get(ENV_CLIENT_SECRET)
        and os.environ.get(ENV_PROJECT_ID)
    )


@pytest.fixture
def infisical_config() -> "InfisicalSecretsConfig":
    """Create a minimal InfisicalSecretsConfig for unit tests.

    This fixture creates a config with test credentials suitable for
    unit tests where the Infisical SDK is mocked.

    Returns:
        InfisicalSecretsConfig with test values.
    """
    from floe_secrets_infisical.config import InfisicalSecretsConfig

    return InfisicalSecretsConfig(
        client_id="test-client-id",
        client_secret=SecretStr("test-client-secret"),
        project_id="test-project-id",
        environment="dev",
        secret_path="/test",
    )


@pytest.fixture
def infisical_config_from_env() -> "InfisicalSecretsConfig":
    """Create InfisicalSecretsConfig from environment variables.

    This fixture creates a config from real environment variables,
    suitable for integration tests against a real Infisical instance.

    Returns:
        InfisicalSecretsConfig with credentials from environment.

    Raises:
        pytest.skip: If credentials are not available.
    """
    if not infisical_credentials_available():
        pytest.skip(
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
        secret_path="/floe-test",
    )


# Register custom markers
def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "requirement(req_id): mark test as covering a specific requirement",
    )
    config.addinivalue_line(
        "markers",
        "infisical: mark test as requiring Infisical credentials",
    )

"""Shared pytest fixtures for floe-catalog-polaris tests.

This conftest.py provides fixtures shared across all test tiers (unit, integration).
Per TESTING.md, test directories should NOT have __init__.py files.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass  # Reserved for future type-only imports


@pytest.fixture
def unique_namespace() -> str:
    """Generate a unique namespace name for test isolation.

    Each test gets a unique namespace to prevent test pollution.
    Format: test_{short_uuid}

    Returns:
        Unique namespace string for the test.
    """
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def unique_table_name() -> str:
    """Generate a unique table name for test isolation.

    Returns:
        Unique table name string for the test.
    """
    return f"test_table_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def sample_oauth2_config() -> dict[str, str]:
    """Provide sample OAuth2 configuration for tests.

    Note: Uses placeholder values. Integration tests should use
    environment variables or test fixtures with real credentials.

    Returns:
        Dictionary with OAuth2 configuration.
    """
    return {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "token_url": "https://polaris.example.com/oauth/token",
        "scope": "PRINCIPAL_ROLE:ALL",
    }


@pytest.fixture
def sample_polaris_config(sample_oauth2_config: dict[str, str]) -> dict[str, object]:
    """Provide sample Polaris catalog configuration for tests.

    Args:
        sample_oauth2_config: OAuth2 configuration from fixture.

    Returns:
        Dictionary with full Polaris configuration.
    """
    return {
        "uri": "https://polaris.example.com/api/catalog",
        "warehouse": "test_warehouse",
        "oauth2": sample_oauth2_config,
        "connect_timeout_seconds": 10,
        "read_timeout_seconds": 30,
        "max_retries": 3,
        "credential_vending_enabled": True,
    }

"""Pytest configuration for floe-identity-keycloak integration tests.

This module provides fixtures specific to integration tests with real Keycloak.
Tests require Keycloak running in the Kind cluster (port 8082).
"""

from __future__ import annotations

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Set default environment variables for Kind cluster Keycloak."""
    # Default to Kind cluster Keycloak instance
    os.environ.setdefault("KEYCLOAK_URL", "http://localhost:8082")
    os.environ.setdefault("KEYCLOAK_REALM", "floe")
    os.environ.setdefault("KEYCLOAK_CLIENT_ID", "floe-client")
    os.environ.setdefault("KEYCLOAK_CLIENT_SECRET", "floe-client-secret")

    # Admin credentials for admin API tests
    os.environ.setdefault("KEYCLOAK_ADMIN_USER", "admin")
    os.environ.setdefault("KEYCLOAK_ADMIN_PASSWORD", "admin-secret-123")


@pytest.fixture
def keycloak_url() -> str:
    """Return Keycloak base URL."""
    return os.environ.get("KEYCLOAK_URL", "http://localhost:8082")


@pytest.fixture
def keycloak_realm() -> str:
    """Return Keycloak realm name."""
    return os.environ.get("KEYCLOAK_REALM", "floe")


@pytest.fixture
def keycloak_client_credentials() -> tuple[str, str]:
    """Return Keycloak client credentials (client_id, client_secret)."""
    return (
        os.environ.get("KEYCLOAK_CLIENT_ID", "floe-client"),
        os.environ.get("KEYCLOAK_CLIENT_SECRET", "floe-client-secret"),
    )


@pytest.fixture
def keycloak_test_user() -> tuple[str, str]:
    """Return test user credentials (username, password)."""
    return ("testuser", "testuser-password")

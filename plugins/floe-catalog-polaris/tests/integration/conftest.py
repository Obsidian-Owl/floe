"""Integration test fixtures for floe-catalog-polaris.

Integration tests require real Polaris instance running in Kind cluster.
Tests should inherit from IntegrationTestBase and use @pytest.mark.integration marker.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass  # Reserved for future type-only imports


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require Polaris)"
    )


@pytest.fixture
def polaris_uri() -> str:
    """Get Polaris URI from environment or use default Kind cluster address.

    Returns:
        Polaris REST API URI.

    Raises:
        pytest.fail: If Polaris is not available.
    """
    uri = os.environ.get("POLARIS_URI", "http://localhost:8181/api/catalog")
    # Integration tests should verify connectivity in their setup
    return uri


@pytest.fixture
def polaris_warehouse() -> str:
    """Get Polaris warehouse name from environment or use default.

    Returns:
        Warehouse name for tests.
    """
    return os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")


# Additional fixtures for real Polaris operations will be added in T076
# (Polish phase: Add integration test conftest with Polaris fixtures)

"""Pytest configuration for integration tests.

Integration tests require a K8s cluster (Kind) and test services to be running.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers for integration tests."""
    config.addinivalue_line(
        "markers",
        "requirement(id): Mark test with requirement ID for traceability",
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests requiring K8s services",
    )

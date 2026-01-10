"""Integration test configuration for floe-telemetry-jaeger.

Provides pytest configuration and fixtures for integration tests
that require a running Jaeger collector.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for integration tests."""
    config.addinivalue_line(
        "markers",
        "requirement(id): Mark test with requirement ID for traceability",
    )
    config.addinivalue_line(
        "markers",
        "integration: Mark test as integration test requiring real services",
    )

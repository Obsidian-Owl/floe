"""Pytest configuration for floe-telemetry-console tests."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "requirement(id): Mark test with requirement ID for traceability",
    )

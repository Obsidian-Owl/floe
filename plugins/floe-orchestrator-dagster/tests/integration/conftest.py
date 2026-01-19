"""Integration test fixtures for floe-orchestrator-dagster.

Integration tests verify plugin discovery and ABC compliance
without requiring external Dagster services.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests",
    )

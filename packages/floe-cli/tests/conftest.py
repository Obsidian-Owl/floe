"""Test configuration for floe-cli tests."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "requirement(id): mark test as validating a specific requirement (FR-XXX)",
    )

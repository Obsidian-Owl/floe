"""Pytest configuration for floe-quality-gx tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def gx_plugin():
    """Provide a GreatExpectationsPlugin instance for testing."""
    from floe_quality_gx import GreatExpectationsPlugin

    return GreatExpectationsPlugin()

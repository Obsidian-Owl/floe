"""Pytest configuration for floe-quality-gx tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_quality_gx import GreatExpectationsPlugin


@pytest.fixture
def gx_plugin() -> GreatExpectationsPlugin:
    """Provide a GreatExpectationsPlugin instance for testing."""
    from floe_quality_gx import GreatExpectationsPlugin

    return GreatExpectationsPlugin()

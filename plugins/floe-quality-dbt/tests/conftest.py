"""Pytest configuration for floe-quality-dbt tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def dbt_plugin():
    """Provide a DBTExpectationsPlugin instance for testing."""
    from floe_quality_dbt import DBTExpectationsPlugin

    return DBTExpectationsPlugin()

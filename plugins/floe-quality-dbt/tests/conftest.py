"""Pytest configuration for floe-quality-dbt tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_quality_dbt import DBTExpectationsPlugin


@pytest.fixture
def dbt_plugin() -> DBTExpectationsPlugin:
    """Provide a DBTExpectationsPlugin instance for testing."""
    from floe_quality_dbt import DBTExpectationsPlugin

    return DBTExpectationsPlugin()

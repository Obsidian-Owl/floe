"""Integration test configuration for floe-dbt-core.

This module configures pytest for integration tests that require:
- Real dbt-core installation
- Real DuckDB execution
- File system access for dbt projects

Integration tests are skipped if dbt-core is not installed.
"""

from __future__ import annotations

import pytest

# Check if dbt-core is available
try:
    from dbt.cli.main import dbtRunner  # noqa: F401

    DBT_AVAILABLE = True
except ImportError:
    DBT_AVAILABLE = False


def pytest_configure(config: pytest.Config) -> None:
    """Configure custom markers for integration tests."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test requiring real dbt",
    )


@pytest.fixture(autouse=True)
def require_dbt() -> None:
    """Fail integration tests if dbt-core is not installed.

    This fixture runs automatically for all integration tests
    in this directory. Tests FAIL (not skip) when infrastructure missing.
    """
    if not DBT_AVAILABLE:
        pytest.fail(
            "dbt-core not installed - integration tests require dbt-core.\n"
            "Install with: pip install dbt-core\n"
            "Or run: uv sync --all-extras"
        )

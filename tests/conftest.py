"""Root-level test configuration for floe.

This conftest.py provides shared fixtures and configuration for all
root-level tests (contract tests, e2e tests).

Note:
    Root-level tests are for cross-package contracts and full platform
    workflows. Package-specific tests belong in their respective
    packages/*/tests/ directories.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "requirement(id): Mark test as covering a specific requirement",
    )

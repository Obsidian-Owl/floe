"""Pytest configuration for extract-manifest-config tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add testing/ci to path so we can import the script as a module
ci_dir = Path(__file__).parent.parent
if str(ci_dir) not in sys.path:
    sys.path.insert(0, str(ci_dir))


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "requirement(id): Mark test with requirement ID for traceability",
    )

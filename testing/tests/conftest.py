"""Pytest configuration for testing module tests.

This conftest.py configures pytest for testing the testing infrastructure itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add testing module to path for imports
testing_root = Path(__file__).parent.parent.parent
if str(testing_root) not in sys.path:
    sys.path.insert(0, str(testing_root))


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "requirement(id): Mark test with requirement ID for traceability",
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests requiring K8s services",
    )
    config.addinivalue_line(
        "markers",
        "e2e: End-to-end tests requiring full stack",
    )

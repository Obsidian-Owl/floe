"""Shared fixtures for structural/source-parsing unit tests.

These tests parse Python source code (AST/regex) to validate patterns in
E2E test files without running the E2E infrastructure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def e2e_test_file() -> Path:
    """Path to the E2E test_data_pipeline.py file."""
    path = REPO_ROOT / "tests" / "e2e" / "test_data_pipeline.py"
    assert path.exists(), f"E2E test file not found at {path}"
    return path


@pytest.fixture(scope="module")
def e2e_conftest_file() -> Path:
    """Path to the E2E conftest.py file."""
    path = REPO_ROOT / "tests" / "e2e" / "conftest.py"
    assert path.exists(), f"E2E conftest not found at {path}"
    return path

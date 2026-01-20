"""Unit test fixtures for the CLI module.

This module provides fixtures specific to CLI unit tests, which:
- Run without external services (no K8s, no databases)
- Use mocks/fakes for compilation dependencies
- Test argument parsing and command execution
- Execute quickly (< 1s per test)

For shared fixtures across all test tiers, see ../conftest.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click CLI test runner.

    Returns:
        CliRunner instance for testing Click commands.
    """
    return CliRunner()


@pytest.fixture
def temp_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a temporary directory for test files.

    Args:
        tmp_path: pytest built-in fixture for temporary paths.

    Yields:
        Path to temporary directory.
    """
    yield tmp_path


@pytest.fixture
def sample_floe_yaml(temp_dir: Path) -> Path:
    """Create a sample floe.yaml file for testing.

    Args:
        temp_dir: Temporary directory fixture.

    Returns:
        Path to the created floe.yaml file.
    """
    content = """
name: test-project
version: "1.0.0"
description: Test project for CLI testing

models:
  - name: customers
    description: Customer master data
    columns:
      - name: id
        description: Primary key
"""
    path = temp_dir / "floe.yaml"
    path.write_text(content)
    return path


@pytest.fixture
def sample_manifest_yaml(temp_dir: Path) -> Path:
    """Create a sample manifest.yaml file for testing.

    Args:
        temp_dir: Temporary directory fixture.

    Returns:
        Path to the created manifest.yaml file.
    """
    content = """
version: "1.0.0"
name: test-platform
description: Test platform manifest

compute:
  plugin: duckdb
  config:
    database: ":memory:"

catalog:
  plugin: polaris
  config:
    uri: "http://localhost:8181"
"""
    path = temp_dir / "manifest.yaml"
    path.write_text(content)
    return path

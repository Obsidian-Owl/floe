"""Integration test fixtures for the CLI module.

This module provides fixtures for CLI integration tests, which:
- Run against real configuration files (not mocks)
- Test full compilation pipeline execution
- Verify output file creation and content
- May interact with real services if available

For shared fixtures across all test tiers, see ../../conftest.py.
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
    """Provide a Click CLI test runner for integration tests.

    Returns:
        CliRunner instance configured for integration testing.
    """
    return CliRunner()


@pytest.fixture
def quickstart_fixtures() -> Path:
    """Provide path to quickstart fixture files.

    Returns:
        Path to the fixtures/quickstart directory containing floe.yaml and manifest.yaml.
    """
    fixture_dir = Path(__file__).parent.parent.parent / "fixtures" / "quickstart"
    if not fixture_dir.exists():
        pytest.fail(
            f"Quickstart fixtures not found at {fixture_dir}. "
            "Ensure packages/floe-core/tests/fixtures/quickstart/ exists."
        )
    return fixture_dir


@pytest.fixture
def quickstart_floe_yaml(quickstart_fixtures: Path) -> Path:
    """Provide path to quickstart floe.yaml fixture.

    Args:
        quickstart_fixtures: Path to quickstart fixture directory.

    Returns:
        Path to floe.yaml file.
    """
    path = quickstart_fixtures / "floe.yaml"
    if not path.exists():
        pytest.fail(f"floe.yaml not found at {path}")
    return path


@pytest.fixture
def quickstart_manifest_yaml(quickstart_fixtures: Path) -> Path:
    """Provide path to quickstart manifest.yaml fixture.

    Args:
        quickstart_fixtures: Path to quickstart fixture directory.

    Returns:
        Path to manifest.yaml file.
    """
    path = quickstart_fixtures / "manifest.yaml"
    if not path.exists():
        pytest.fail(f"manifest.yaml not found at {path}")
    return path


@pytest.fixture
def output_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a temporary directory for test outputs.

    Args:
        tmp_path: pytest built-in fixture for temporary paths.

    Yields:
        Path to temporary output directory.
    """
    output = tmp_path / "output"
    output.mkdir(parents=True, exist_ok=True)
    yield output


__all__: list[str] = [
    "cli_runner",
    "quickstart_fixtures",
    "quickstart_floe_yaml",
    "quickstart_manifest_yaml",
    "output_dir",
]

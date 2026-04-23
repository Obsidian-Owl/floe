"""Tests for validation-boundary configuration."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


def test_pytest_markers_include_validation_boundaries() -> None:
    """The validation stack has explicit boundary markers."""
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    markers = pyproject["tool"]["pytest"]["ini_options"]["markers"]
    marker_names = {entry.split(":", 1)[0] for entry in markers}

    assert {"contract", "bootstrap", "platform_blackbox", "developer_workflow"} <= marker_names


def test_make_test_runs_contract_before_integration() -> None:
    """Top-level test target runs contract tests before integration tests."""
    makefile = Path("Makefile").read_text()

    assert "test: test-unit test-contract test-integration" in makefile
    assert ".PHONY: test-contract" in makefile

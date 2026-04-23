"""Structural tests for validation lane markers."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_registers_validation_lane_markers() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()

    assert '"bootstrap: Marks admin/bootstrap validation"' in pyproject
    assert '"platform_blackbox: Marks in-cluster product validation"' in pyproject
    assert '"developer_workflow: Marks repo-aware host validation"' in pyproject


def test_e2e_conftest_registers_lane_markers() -> None:
    conftest = (REPO_ROOT / "tests" / "e2e" / "conftest.py").read_text()

    assert 'bootstrap: mark test as bootstrap/admin validation' in conftest
    assert 'platform_blackbox: mark test as deployed in-cluster product validation' in conftest
    assert 'developer_workflow: mark test as repo-aware host validation' in conftest


def test_e2e_conftest_defaults_unclassified_items_to_platform_blackbox() -> None:
    conftest = (REPO_ROOT / "tests" / "e2e" / "conftest.py").read_text()

    assert "platform_blackbox" in conftest
    assert "item.add_marker(pytest.mark.platform_blackbox)" in conftest

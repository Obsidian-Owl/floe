"""Regression tests for Polaris JDBC durability cleanup behavior."""

from __future__ import annotations

from pathlib import Path


def test_polaris_jdbc_durability_cleanup_does_not_require_purge_enabled() -> None:
    """The restart durability test must clean up without requiring Polaris purge."""
    source = Path("tests/e2e/tests/test_polaris_jdbc_durability.py").read_text(encoding="utf-8")

    assert ".purge_table(" not in source
    assert "drop_test_namespace(fresh_catalog, ns_name)" in source

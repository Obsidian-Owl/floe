"""Regression tests for destructive E2E service readiness sequencing."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DESTRUCTIVE_E2E = REPO_ROOT / "tests" / "e2e" / "test_service_failure_resilience_e2e.py"


def _function_source(function_name: str) -> str:
    source = DESTRUCTIVE_E2E.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"Function {function_name} not found in {DESTRUCTIVE_E2E}")


def test_destructive_tests_use_shared_http_status_waiter() -> None:
    """Destructive tests should use strict HTTP readiness, not ad hoc one-shot GETs."""
    source = DESTRUCTIVE_E2E.read_text()

    assert "wait_for_http_status" in source


def test_minio_restart_waits_for_polaris_readiness_after_recovery() -> None:
    """MinIO restarts must wait for dependent Polaris readiness before next test."""
    source = _function_source("test_minio_pod_restart_detected")

    assert "wait_for_http_status" in source
    assert "Polaris readiness after MinIO pod restart" in source
    assert source.index("assert_pod_recovery(") < source.index(
        "Polaris readiness after MinIO pod restart"
    )


def test_polaris_restart_preflight_uses_polled_readiness() -> None:
    """Polaris preflight should tolerate transient 503s from previous destructive tests."""
    source = _function_source("test_polaris_pod_restart_detected")

    assert "wait_for_http_status" in source
    assert "Polaris readiness before pod restart" in source
    assert "response = httpx.get" not in source


def test_compilation_outage_cleanup_waits_for_polaris_http_readiness() -> None:
    """Compilation outage cleanup should restore Polaris endpoint readiness, not only pod Ready."""
    source = _function_source("test_compilation_during_service_outage")

    assert "wait_for_http_status" in source
    assert "Polaris readiness after compilation outage test" in source

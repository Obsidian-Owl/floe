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


def test_make_test_e2e_runs_bootstrap_before_product_e2e() -> None:
    """In-cluster E2E make target validates bootstrap before product E2E."""
    makefile = Path("Makefile").read_text()

    bootstrap_index = makefile.index("TEST_SUITE=bootstrap ./testing/ci/test-e2e-cluster.sh")
    e2e_index = makefile.index("SKIP_BUILD=true ./testing/ci/test-e2e-cluster.sh")

    assert bootstrap_index < e2e_index


def test_cluster_runner_supports_bootstrap_suite() -> None:
    """In-cluster runner has an explicit bootstrap suite."""
    script = Path("testing/ci/test-e2e-cluster.sh").read_text()

    assert "TEST_SUITE          Test suite to run: bootstrap|e2e|e2e-destructive" in script
    assert "bootstrap)" in script
    assert 'JOB_NAME="floe-test-bootstrap"' in script
    assert 'JOB_TEMPLATE="tests/job-bootstrap.yaml"' in script
    assert 'RBAC_TEMPLATE="tests/rbac-standard.yaml"' in script


def test_full_e2e_runner_sequences_bootstrap_before_product_e2e() -> None:
    """Full in-cluster runner gates product E2E behind bootstrap success."""
    script = Path("testing/ci/test-e2e-full.sh").read_text()

    bootstrap_index = script.index('TEST_SUITE=bootstrap "${SCRIPT_DIR}/test-e2e-cluster.sh"')
    standard_index = script.index('SKIP_BUILD=true "${SCRIPT_DIR}/test-e2e-cluster.sh"')
    destructive_index = script.index(
        "SKIP_BUILD=true IMAGE_LOAD_METHOD=skip TEST_SUITE=e2e-destructive"
    )

    assert bootstrap_index < standard_index < destructive_index
    assert 'if [[ "${BOOTSTRAP_EXIT}" -ne 0 ]]; then' in script
    assert "Skipping standard E2E tests (bootstrap failed)." in script
    assert "Skipping destructive tests (bootstrap failed)." in script


def test_host_e2e_runner_runs_bootstrap_before_product_e2e() -> None:
    """Legacy host runner runs bootstrap before product E2E tests."""
    script = Path("testing/ci/test-e2e.sh").read_text()

    bootstrap_index = script.index("tests/bootstrap/")
    e2e_index = script.index("tests/e2e/")

    assert bootstrap_index < e2e_index
    assert "-m bootstrap" in script

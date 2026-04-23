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

    assert "Running bootstrap-gated E2E tests in-cluster" in makefile
    assert "@./testing/ci/test-e2e-cluster.sh" in makefile


def test_cluster_runner_supports_bootstrap_suite() -> None:
    """In-cluster runner has an explicit bootstrap suite."""
    script = Path("testing/ci/test-e2e-cluster.sh").read_text()

    assert "TEST_SUITE          Test suite to run: bootstrap|e2e|e2e-destructive" in script
    assert "bootstrap)" in script
    assert 'JOB_NAME="floe-test-bootstrap"' in script
    assert 'JOB_TEMPLATE="tests/job-bootstrap.yaml"' in script
    assert 'RBAC_TEMPLATE="tests/rbac-standard.yaml"' in script


def test_cluster_runner_default_direct_invocation_is_bootstrap_gated() -> None:
    """Direct in-cluster runner use defaults to bootstrap before product E2E."""
    script = Path("testing/ci/test-e2e-cluster.sh").read_text()

    assert 'if [[ -z "${TEST_SUITE+x}" ]]; then' in script
    assert 'FLOE_DIRECT_BOOTSTRAP_GATE="true"' in script
    assert 'TEST_SUITE="bootstrap"' in script
    assert "SKIP_BUILD=true IMAGE_LOAD_METHOD=skip TEST_SUITE=e2e" in script
    assert "Bootstrap passed; running product E2E suite without rebuilding/loading image." in script


def test_cluster_runner_fails_fast_when_job_reaches_failed_condition() -> None:
    """In-cluster runner must not wait for complete timeout after Job failure."""
    script = Path("testing/ci/test-e2e-cluster.sh").read_text()

    assert "wait_for_job_terminal_status()" in script
    assert 'JOB_POLL_INTERVAL="${JOB_POLL_INTERVAL:-5}"' in script
    assert 'grep -qx "Complete=True"' in script
    assert 'grep -qx "Failed=True"' in script
    assert "JOB_STATUS=$(wait_for_job_terminal_status)" in script
    assert "--timeout=10s" not in script


def test_full_e2e_runner_sequences_bootstrap_before_product_e2e() -> None:
    """Full in-cluster runner gates product E2E behind bootstrap success."""
    script = Path("testing/ci/test-e2e-full.sh").read_text()

    bootstrap_index = script.index('TEST_SUITE=bootstrap "${SCRIPT_DIR}/test-e2e-cluster.sh"')
    standard_index = script.index(
        'SKIP_BUILD=true TEST_SUITE=e2e "${SCRIPT_DIR}/test-e2e-cluster.sh"'
    )
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


def test_bootstrap_conftest_has_minimal_flux_helm_safeguards() -> None:
    """Bootstrap validation keeps focused Flux/Helm reconciliation safeguards."""
    conftest = Path("tests/bootstrap/conftest.py").read_text()

    assert "flux_helm_reconciliation_health" in conftest
    assert "source-controller" in conftest
    assert "helm-controller" in conftest
    assert 'flux", "resume", "helmrelease"' in conftest
    assert "--for=condition=Ready" in conftest
    assert "_is_forbidden" in conftest
    assert "missing required RBAC" in conftest
    assert "tests.e2e.conftest" not in conftest


def test_integration_runner_delegates_to_bootstrap_gated_cluster_runner() -> None:
    """Legacy integration runner gates product suites with bootstrap first."""
    script = Path("testing/ci/test-integration.sh").read_text()

    assert 'export JOB_TIMEOUT="${JOB_TIMEOUT:-${WAIT_TIMEOUT}}"' in script
    assert '"${SCRIPT_DIR}/test-e2e-cluster.sh"' in script
    assert 'run_cluster_suite "bootstrap"' in script
    assert 'run_cluster_suite_skip_build "e2e"' in script
    assert 'run_cluster_suite_skip_build "e2e-destructive"' in script
    assert "docker build" not in script
    assert "kubectl apply" not in script


def test_release_and_weekly_workflows_use_bootstrap_gated_integration_steps() -> None:
    """Scheduled/release workflow call sites must not bypass bootstrap gating."""
    release = Path(".github/workflows/release.yml").read_text()
    weekly = Path(".github/workflows/weekly.yml").read_text()

    assert "Run bootstrap-gated integration tests" in release
    assert "Run integration tests" not in release
    assert "run: ./testing/ci/test-integration.sh" in release

    assert "Run bootstrap-gated integration tests" in weekly
    assert "Run bootstrap-gated standard E2E tests" in weekly
    assert "Run bootstrap-gated destructive E2E tests" in weekly
    assert "Run integration tests" not in weekly

# Validation Architecture Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split floe validation into explicit execution lanes so standard in-cluster E2E only validates deployed product behavior, while admin/bootstrap and repo-aware checks run in the correct context.

**Architecture:** Use pytest lane markers plus runner split. `tests/e2e` items default to `platform_blackbox` unless explicitly marked `bootstrap`, `developer_workflow`, or `destructive`, and the shell orchestration runs host-side bootstrap and developer lanes separately from the in-cluster product lane. Strengthen Polaris/Iceberg reset logic so dbt-based product tests fail on real product issues, not stale catalog state.

**Tech Stack:** Python 3.10+, pytest, Bash, Helm templates, Kubernetes Jobs, DevPod/Hetzner, Polaris, Iceberg, dbt, PyIceberg, boto3.

---

## Scope Check

This plan covers one connected subsystem: the validation harness and its supporting dbt reset discipline. It does not attempt the broader contract-layer migration, and it intentionally leaves the OpenLineage `parentRun` defect as a separate product bug after the harness split lands.

## File Structure

Modify lane selection and defaults:

- `pyproject.toml`: register `bootstrap`, `platform_blackbox`, and `developer_workflow` pytest markers.
- `tests/e2e/conftest.py`: register lane markers at runtime, auto-default unclassified E2E items to `platform_blackbox`, and keep destructive tests ordered last.
- `tests/unit/test_validation_boundary_markers.py`: structural tests for marker registration and critical file-level lane assignments.

Modify critical outlier tests:

- `tests/e2e/test_helm_workflow.py`: explicit `bootstrap` lane.
- `tests/e2e/test_platform_bootstrap.py`: explicit `bootstrap` lane.
- `tests/e2e/test_platform_deployment_e2e.py`: explicit `bootstrap` lane.
- `tests/e2e/test_profile_isolation.py`: explicit `developer_workflow` lane.
- `tests/e2e/test_governance.py`: mark `test_pip_audit_clean` as `developer_workflow`.
- `tests/e2e/test_runtime_loader_e2e.py`: replace `127.0.0.1` with service-contract resolution and split function-level lanes.

Split orchestration:

- `charts/floe-platform/templates/tests/job-e2e.yaml`: standard in-cluster runner selects `platform_blackbox and not destructive`.
- `testing/ci/test-e2e-cluster.sh`: keep in-cluster execution for product and destructive lanes, update suite semantics and output.
- `testing/ci/test-e2e-full.sh`: orchestrate `bootstrap`, `platform_blackbox`, `developer_workflow`, then gated `destructive`.
- `testing/ci/test-bootstrap-validation.sh`: host-side bootstrap/admin runner.
- `testing/ci/test-developer-workflow.sh`: host-side repo-aware runner.
- `tests/unit/test_validation_runner_wiring.py`: structural tests for runner commands and chart marker wiring.

Harden reset/idempotency:

- `tests/e2e/dbt_utils.py`: fresh Polaris catalog reset helpers, verified namespace purge, and clearer reset failures.
- `tests/e2e/conftest.py`: shared dbt fixture uses verified namespace reset before and after module-scoped runs.
- `tests/unit/test_dbt_namespace_reset.py`: unit tests for reset semantics and `run_dbt()` preconditions.

Update docs:

- `TESTING.md`: describe the four validation lanes and their execution environments.

## Tasks

### Task 1: Add Validation Lane Markers And Defaulting

**Files:**

- Modify: `pyproject.toml`
- Modify: `tests/e2e/conftest.py`
- Create: `tests/unit/test_validation_boundary_markers.py`

- [ ] **Step 1: Write the failing structural tests**

Create `tests/unit/test_validation_boundary_markers.py`:

```python
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
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_validation_boundary_markers.py -v
```

Expected: FAIL because `pyproject.toml` does not yet declare the new markers and `tests/e2e/conftest.py` does not yet default unclassified E2E items to `platform_blackbox`.

- [ ] **Step 3: Register the new markers in `pyproject.toml`**

Modify the `markers = [` block in `pyproject.toml` to include:

```toml
    "bootstrap: Marks admin/bootstrap validation",
    "platform_blackbox: Marks in-cluster product validation",
    "developer_workflow: Marks repo-aware host validation",
```

Keep the existing `e2e`, `contract`, `integration`, and `benchmark` markers.

- [ ] **Step 4: Default unclassified E2E items to `platform_blackbox`**

Modify `tests/e2e/conftest.py`.

1. Add the new marker registrations inside `pytest_configure()`:

```python
    config.addinivalue_line(
        "markers",
        "bootstrap: mark test as bootstrap/admin validation",
    )
    config.addinivalue_line(
        "markers",
        "platform_blackbox: mark test as deployed in-cluster product validation",
    )
    config.addinivalue_line(
        "markers",
        "developer_workflow: mark test as repo-aware host validation",
    )
```

2. At the top of `pytest_collection_modifyitems()`, add a lane-marker helper:

```python
    lane_markers = {
        "bootstrap",
        "platform_blackbox",
        "developer_workflow",
        "destructive",
    }
```

3. Before the destructive reordering logic, add defaulting for unclassified E2E tests:

```python
    for item in items:
        item_markers = {mark.name for mark in item.iter_markers()}
        if "e2e" not in item_markers:
            continue
        if item_markers.isdisjoint(lane_markers):
            item.add_marker(pytest.mark.platform_blackbox)
```

4. Keep the destructive test reordering logic intact so `destructive` tests still run last when collected.

- [ ] **Step 5: Run the structural tests again**

Run:

```bash
uv run pytest tests/unit/test_validation_boundary_markers.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml tests/e2e/conftest.py tests/unit/test_validation_boundary_markers.py
git commit -m "test: add validation lane markers"
```

### Task 2: Explicitly Reclassify The Current Outlier Tests

**Files:**

- Modify: `tests/e2e/test_helm_workflow.py`
- Modify: `tests/e2e/test_platform_bootstrap.py`
- Modify: `tests/e2e/test_platform_deployment_e2e.py`
- Modify: `tests/e2e/test_profile_isolation.py`
- Modify: `tests/e2e/test_governance.py`
- Modify: `tests/e2e/test_runtime_loader_e2e.py`
- Modify: `tests/unit/test_validation_boundary_markers.py`

- [ ] **Step 1: Extend the structural tests to cover critical lane assignments**

Append these tests to `tests/unit/test_validation_boundary_markers.py`:

```python
def test_bootstrap_modules_are_explicitly_marked() -> None:
    helm_workflow = (REPO_ROOT / "tests" / "e2e" / "test_helm_workflow.py").read_text()
    platform_bootstrap = (REPO_ROOT / "tests" / "e2e" / "test_platform_bootstrap.py").read_text()
    platform_deployment = (
        REPO_ROOT / "tests" / "e2e" / "test_platform_deployment_e2e.py"
    ).read_text()

    assert "pytest.mark.bootstrap" in helm_workflow
    assert "pytest.mark.bootstrap" in platform_bootstrap
    assert "pytest.mark.bootstrap" in platform_deployment


def test_developer_workflow_outliers_are_explicitly_marked() -> None:
    profile_isolation = (REPO_ROOT / "tests" / "e2e" / "test_profile_isolation.py").read_text()
    governance = (REPO_ROOT / "tests" / "e2e" / "test_governance.py").read_text()
    runtime_loader = (REPO_ROOT / "tests" / "e2e" / "test_runtime_loader_e2e.py").read_text()

    assert "pytest.mark.developer_workflow" in profile_isolation
    assert "def test_pip_audit_clean" in governance
    assert "@pytest.mark.developer_workflow" in governance
    assert "pytest.mark.developer_workflow" in runtime_loader


def test_runtime_loader_uses_service_contract_not_localhost_literal() -> None:
    runtime_loader = (REPO_ROOT / "tests" / "e2e" / "test_runtime_loader_e2e.py").read_text()

    assert 'ServiceEndpoint("dagster-webserver")' in runtime_loader
    assert 'DAGSTER_HOST = "127.0.0.1"' not in runtime_loader
```

- [ ] **Step 2: Run the structural tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_validation_boundary_markers.py -v
```

Expected: FAIL because the outlier files are not yet explicitly classified and `test_runtime_loader_e2e.py` still hardcodes `127.0.0.1`.

- [ ] **Step 3: Mark the bootstrap/admin files explicitly**

Add module-level `pytestmark` blocks near the imports of these files:

`tests/e2e/test_helm_workflow.py`

```python
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.bootstrap,
]
```

`tests/e2e/test_platform_bootstrap.py`

```python
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.bootstrap,
]
```

`tests/e2e/test_platform_deployment_e2e.py`

```python
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.bootstrap,
]
```

Keep existing `@pytest.mark.requirement(...)` decorators in place.

- [ ] **Step 4: Mark the repo-aware developer workflow tests explicitly**

1. Add a module-level marker in `tests/e2e/test_profile_isolation.py`:

```python
pytestmark = [pytest.mark.developer_workflow]
```

2. Add `@pytest.mark.developer_workflow` directly above `test_pip_audit_clean()` in `tests/e2e/test_governance.py`:

```python
    @pytest.mark.developer_workflow
    @pytest.mark.e2e
    @pytest.mark.requirement("FR-064")
    def test_pip_audit_clean(self) -> None:
```

3. In `tests/e2e/test_runtime_loader_e2e.py`, mark the functions individually:

```python
@pytest.mark.e2e
@pytest.mark.platform_blackbox
@pytest.mark.requirement("AC-1")
@pytest.mark.requirement("AC-6")
def test_dagster_discovers_code_location(dagster_url: str) -> None:
    ...


@pytest.mark.e2e
@pytest.mark.platform_blackbox
@pytest.mark.requirement("AC-1")
@pytest.mark.requirement("AC-6")
def test_dagster_discovers_assets(dagster_url: str) -> None:
    ...


@pytest.mark.developer_workflow
@pytest.mark.requirement("AC-6")
def test_thin_definitions_are_deployed() -> None:
    ...
```

- [ ] **Step 5: Replace the runtime loader localhost contract with service resolution**

Modify `tests/e2e/test_runtime_loader_e2e.py`.

1. Remove:

```python
DAGSTER_HOST = "127.0.0.1"
DAGSTER_PORT = 3000
```

2. Add these imports and helper logic:

```python
import os

from testing.fixtures.services import ServiceEndpoint
```

```python
    url = os.environ.get("DAGSTER_URL", ServiceEndpoint("dagster-webserver").url)
```

3. Keep the health check against `f"{url}/server_info"` exactly as the fixture entrypoint.

- [ ] **Step 6: Run the structural tests again**

Run:

```bash
uv run pytest tests/unit/test_validation_boundary_markers.py -v
```

Expected: PASS.

- [ ] **Step 7: Run the directly affected tests in their proper lanes**

Run:

```bash
uv run pytest tests/e2e/test_runtime_loader_e2e.py -m "platform_blackbox or developer_workflow" -v
uv run pytest tests/e2e/test_profile_isolation.py tests/e2e/test_governance.py -m developer_workflow -v
uv run pytest tests/e2e/test_helm_workflow.py tests/e2e/test_platform_bootstrap.py tests/e2e/test_platform_deployment_e2e.py -m bootstrap -v
```

Expected: collection succeeds with the new lane markers. Runtime pass/fail depends on environment state, but there should be no marker warnings and no `127.0.0.1` contract left in `test_runtime_loader_e2e.py`.

- [ ] **Step 8: Commit**

```bash
git add \
  tests/e2e/test_helm_workflow.py \
  tests/e2e/test_platform_bootstrap.py \
  tests/e2e/test_platform_deployment_e2e.py \
  tests/e2e/test_profile_isolation.py \
  tests/e2e/test_governance.py \
  tests/e2e/test_runtime_loader_e2e.py \
  tests/unit/test_validation_boundary_markers.py
git commit -m "test: classify validation outliers by execution lane"
```

### Task 3: Split The Runner Orchestration By Lane

**Files:**

- Modify: `charts/floe-platform/templates/tests/job-e2e.yaml`
- Modify: `testing/ci/test-e2e-cluster.sh`
- Modify: `testing/ci/test-e2e-full.sh`
- Create: `testing/ci/test-bootstrap-validation.sh`
- Create: `testing/ci/test-developer-workflow.sh`
- Create: `tests/unit/test_validation_runner_wiring.py`

- [ ] **Step 1: Write failing runner-wiring tests**

Create `tests/unit/test_validation_runner_wiring.py`:

```python
"""Structural tests for validation lane runner wiring."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_chart_standard_runner_selects_platform_blackbox() -> None:
    job_e2e = (
        REPO_ROOT / "charts" / "floe-platform" / "templates" / "tests" / "job-e2e.yaml"
    ).read_text()

    assert '"pytestMarker" "platform_blackbox and not destructive"' in job_e2e


def test_bootstrap_runner_uses_bootstrap_marker() -> None:
    script = (REPO_ROOT / "testing" / "ci" / "test-bootstrap-validation.sh").read_text()

    assert "uv run pytest tests/e2e" in script
    assert '-m "bootstrap"' in script


def test_developer_workflow_runner_uses_developer_marker() -> None:
    script = (REPO_ROOT / "testing" / "ci" / "test-developer-workflow.sh").read_text()

    assert "uv run pytest tests/e2e" in script
    assert '-m "developer_workflow"' in script


def test_full_runner_orchestrates_bootstrap_platform_developer_then_destructive() -> None:
    script = (REPO_ROOT / "testing" / "ci" / "test-e2e-full.sh").read_text()

    assert 'test-bootstrap-validation.sh' in script
    assert 'test-e2e-cluster.sh' in script
    assert 'test-developer-workflow.sh' in script
    assert 'TEST_SUITE=e2e-destructive' in script
```

- [ ] **Step 2: Run the runner-wiring tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_validation_runner_wiring.py -v
```

Expected: FAIL because the host-side lane scripts do not exist and the standard chart runner still uses `not destructive`.

- [ ] **Step 3: Narrow the in-cluster standard Job to the product lane**

Modify `charts/floe-platform/templates/tests/job-e2e.yaml`:

```yaml
{{- include "floe-platform.testJob" (dict
    "context" .
    "suite" "e2e"
    "pytestMarker" "platform_blackbox and not destructive"
    "serviceAccount" (include "floe-platform.testRunner.saName" .)
    "artifactPrefix" "e2e"
    ) }}
```

This keeps the Job name stable while changing the semantic contract of the standard lane.

- [ ] **Step 4: Add the host-side bootstrap runner**

Create `testing/ci/test-bootstrap-validation.sh`:

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"
mkdir -p test-artifacts

uv run pytest tests/e2e \
  -m "bootstrap" \
  --tb=short \
  -v \
  --junitxml=test-artifacts/bootstrap-results.xml
```

Make it executable:

```bash
chmod +x testing/ci/test-bootstrap-validation.sh
```

- [ ] **Step 5: Add the host-side developer-workflow runner**

Create `testing/ci/test-developer-workflow.sh`:

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"
mkdir -p test-artifacts

uv run pytest tests/e2e \
  -m "developer_workflow" \
  --tb=short \
  -v \
  --junitxml=test-artifacts/developer-workflow-results.xml
```

Make it executable:

```bash
chmod +x testing/ci/test-developer-workflow.sh
```

- [ ] **Step 6: Update the full orchestrator**

Modify `testing/ci/test-e2e-full.sh`.

1. Replace the current two-exit-code model with separate lane exits:

```bash
BOOTSTRAP_EXIT=0
PLATFORM_EXIT=0
DEVELOPER_EXIT=0
DESTRUCTIVE_EXIT=0
```

2. Run bootstrap first:

```bash
if "${SCRIPT_DIR}/test-bootstrap-validation.sh"; then
    info "Bootstrap validation PASSED"
else
    BOOTSTRAP_EXIT=$?
    error "Bootstrap validation FAILED (exit code: ${BOOTSTRAP_EXIT})"
fi
```

3. Gate the in-cluster platform lane on bootstrap:

```bash
if [[ "${BOOTSTRAP_EXIT}" -eq 0 ]]; then
    if "${SCRIPT_DIR}/test-e2e-cluster.sh"; then
        info "Platform blackbox validation PASSED"
    else
        PLATFORM_EXIT=$?
        error "Platform blackbox validation FAILED (exit code: ${PLATFORM_EXIT})"
    fi
else
    info "Skipping platform blackbox validation because bootstrap failed."
fi
```

4. Always run the repo-aware developer lane:

```bash
if "${SCRIPT_DIR}/test-developer-workflow.sh"; then
    info "Developer workflow validation PASSED"
else
    DEVELOPER_EXIT=$?
    error "Developer workflow validation FAILED (exit code: ${DEVELOPER_EXIT})"
fi
```

5. Only run destructive if bootstrap and platform both passed, unless `FORCE_DESTRUCTIVE=true`.

6. Update the summary block to print all four lanes explicitly.

- [ ] **Step 7: Update `testing/ci/test-e2e-cluster.sh` comments and suite messaging**

Modify comments and status output so the standard suite is described as:

```bash
# platform-blackbox E2E test runner — runs deployed product validation in-cluster
```

Keep the existing `TEST_SUITE=e2e|e2e-destructive` external interface for now so callers do not break in the same change.

- [ ] **Step 8: Run the structural runner tests**

Run:

```bash
uv run pytest tests/unit/test_validation_runner_wiring.py -v
```

Expected: PASS.

- [ ] **Step 9: Smoke-test the new runners**

Run:

```bash
./testing/ci/test-bootstrap-validation.sh
./testing/ci/test-developer-workflow.sh
./testing/ci/test-e2e-full.sh
```

Expected:

- bootstrap lane runs only `-m bootstrap`
- standard in-cluster lane runs only `platform_blackbox and not destructive`
- developer lane runs only `-m developer_workflow`
- destructive lane stays gated behind bootstrap + platform success unless overridden

- [ ] **Step 10: Commit**

```bash
git add \
  charts/floe-platform/templates/tests/job-e2e.yaml \
  testing/ci/test-e2e-cluster.sh \
  testing/ci/test-e2e-full.sh \
  testing/ci/test-bootstrap-validation.sh \
  testing/ci/test-developer-workflow.sh \
  tests/unit/test_validation_runner_wiring.py
git commit -m "test: split validation runners by execution lane"
```

### Task 4: Harden Polaris And Iceberg Reset Semantics

**Files:**

- Modify: `tests/e2e/dbt_utils.py`
- Modify: `tests/e2e/conftest.py`
- Create: `tests/unit/test_dbt_namespace_reset.py`

- [ ] **Step 1: Write failing reset-contract tests**

Create `tests/unit/test_dbt_namespace_reset.py`:

```python
"""Unit tests for Polaris/Iceberg namespace reset semantics."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import dbt_utils


def test_clear_catalog_cache_drops_cached_catalog() -> None:
    dbt_utils._catalog_cache["catalog"] = object()

    dbt_utils._clear_catalog_cache()

    assert dbt_utils._catalog_cache == {}


def test_purge_namespace_raises_when_namespace_still_contains_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_catalog = Mock()
    fake_catalog.list_tables.return_value = [("customer_360", "stg_customers")]

    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", lambda fresh=False: fake_catalog)
    monkeypatch.setattr(dbt_utils, "_delete_s3_prefix", lambda *args, **kwargs: 0)
    monkeypatch.setattr(dbt_utils.boto3, "client", lambda *args, **kwargs: Mock())

    with pytest.raises(dbt_utils.NamespaceResetError, match="Namespace reset incomplete"):
        dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=1)


def test_run_dbt_resets_raw_namespace_before_seed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_dir = tmp_path / "customer-360"
    project_dir.mkdir()

    purge_calls: list[tuple[str, bool]] = []

    def _record(namespace: str, verify_empty: bool = False, retries: int = 3) -> None:
        purge_calls.append((namespace, verify_empty))

    monkeypatch.setattr(dbt_utils, "_purge_iceberg_namespace", _record)
    monkeypatch.setattr(
        dbt_utils.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    dbt_utils.run_dbt(["seed"], project_dir)

    assert purge_calls == [("customer_360_raw", True)]
```

- [ ] **Step 2: Run the reset-contract tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_dbt_namespace_reset.py -v
```

Expected: FAIL because `_clear_catalog_cache()` and `NamespaceResetError` do not exist, and `run_dbt()` does not yet request verified reset behavior.

- [ ] **Step 3: Add explicit reset helpers and error type**

Modify `tests/e2e/dbt_utils.py`.

1. Add the reset error and cache clearer near the top of the file:

```python
class NamespaceResetError(RuntimeError):
    """Raised when an Iceberg namespace cannot be reset to an empty state."""


def _clear_catalog_cache() -> None:
    """Drop cached Polaris catalog state so each reset can re-auth cleanly."""
    _catalog_cache.clear()
```

2. Change `_get_polaris_catalog()` to accept a freshness flag:

```python
def _get_polaris_catalog(*, fresh: bool = False) -> Any:
    if fresh:
        _clear_catalog_cache()
    if "catalog" in _catalog_cache:
        return _catalog_cache["catalog"]
    ...
```

- [ ] **Step 4: Make namespace purge verified instead of best-effort**

Modify `_purge_iceberg_namespace()` in `tests/e2e/dbt_utils.py`:

```python
def _purge_iceberg_namespace(
    namespace: str,
    verify_empty: bool = False,
    retries: int = 3,
) -> None:
```

Use a fresh Polaris catalog client for the purge path when verified reset is required, and make the verification loop fail closed:

```python
    catalog = _get_polaris_catalog(fresh=verify_empty)
    verification_failure: str | None = None

    if not verify_empty:
        return

    for attempt in range(retries):
        verification_catalog = _get_polaris_catalog(fresh=True)
        if verification_catalog is None:
            verification_failure = "catalog unavailable"
            break

        try:
            remaining = verification_catalog.list_tables(namespace)
        except NoSuchNamespaceError:
            return
        except Exception as exc:
            verification_failure = f"verification failed: {type(exc).__name__}"
            break

        if not remaining:
            return

    if verification_failure is not None:
        raise NamespaceResetError(
            f"Namespace reset verification failed for {namespace}: {verification_failure}"
        )

    raise NamespaceResetError(
        f"Namespace reset incomplete for {namespace}: remaining tables={remaining}"
    )
```

Keep the S3 prefix deletion and namespace drop logic, but make inability to verify a reset failure instead of silently continuing.

When `verify_empty=True`, treat explicit object-store cleanup failures during the purge path as reset failures too. A namespace-only verification is not sufficient if:

- the object-store sweep for a known table prefix failed
- `delete_objects` returned per-object errors
- a table existed but its storage location could not be loaded, preventing the explicit prefix sweep
- the purge-phase catalog lookup itself failed before table locations could be enumerated

- [ ] **Step 5: Require verified reset before dbt seed and run**

Modify `run_dbt()` in `tests/e2e/dbt_utils.py`:

```python
    if args and args[0] == "seed":
        product_name = project_dir.name.replace("-", "_")
        _purge_iceberg_namespace(f"{product_name}_raw", verify_empty=True)
    elif args and args[0] == "run":
        product_name = project_dir.name.replace("-", "_")
        _purge_iceberg_namespace(product_name, verify_empty=True)
```

Modify the module-scoped `dbt_pipeline_result` fixture in `tests/e2e/conftest.py` so setup and teardown use verified reset too:

```python
        _purge_iceberg_namespace(namespace_raw, verify_empty=True)
        _purge_iceberg_namespace(namespace_models, verify_empty=True)
```

If teardown verified-reset fails after an earlier dbt or test failure, preserve the original failure as the primary signal and only log or otherwise surface the teardown reset problem without masking it.

On the no-prior-error path, teardown should still attempt verified reset for both namespaces before raising the first collected reset error.

and in `finally`:

```python
        _purge_iceberg_namespace(namespace_raw, verify_empty=True)
        _purge_iceberg_namespace(namespace_models, verify_empty=True)
```

- [ ] **Step 6: Run the reset tests**

Run:

```bash
uv run pytest tests/unit/test_dbt_namespace_reset.py -v
```

Expected: PASS.

- [ ] **Step 7: Run the dbt-heavy platform tests against the cleaned reset path**

Run:

```bash
uv run pytest tests/e2e/test_dbt_lifecycle_e2e.py tests/e2e/test_data_pipeline.py tests/e2e/test_compile_deploy_materialize_e2e.py -m platform_blackbox -v
```

Expected: stale-state failures should either disappear or collapse into a smaller, real product defect set. If failures remain, they should now fail with a reset-specific message instead of ambiguous stale-metadata noise.

- [ ] **Step 8: Commit**

```bash
git add tests/e2e/dbt_utils.py tests/e2e/conftest.py tests/unit/test_dbt_namespace_reset.py
git commit -m "test: verify Polaris namespace reset before dbt execution"
```

### Task 5: Update Testing Documentation And Final Validation

**Files:**

- Modify: `TESTING.md`

- [ ] **Step 1: Add a failing documentation check**

Append this test to `tests/unit/test_validation_runner_wiring.py`:

```python
def test_testing_guide_describes_validation_lanes() -> None:
    guide = (REPO_ROOT / "TESTING.md").read_text()

    assert "bootstrap" in guide
    assert "platform_blackbox" in guide
    assert "developer_workflow" in guide
    assert "destructive" in guide
```

- [ ] **Step 2: Run the documentation test and verify it fails**

Run:

```bash
uv run pytest tests/unit/test_validation_runner_wiring.py -v
```

Expected: FAIL because `TESTING.md` still describes E2E as a single K8s lane.

- [ ] **Step 3: Update `TESTING.md` to describe the new validation architecture**

Add a new subsection under `## Running Tests` describing:

```md
### Validation Lanes

- `contract`: host-side structural and cross-package validation
- `bootstrap`: host-side admin/deployment validation with real `helm` and `kubectl`
- `platform_blackbox`: standard in-cluster product validation under least-privilege RBAC
- `developer_workflow`: host-side repo-aware checks (`.git`, `.gitignore`, `.vuln-ignore`)
- `destructive`: gated in-cluster disruptive validation after standard product pass
```

Update the E2E section so it no longer claims every E2E-shaped test must execute only in-cluster.

- [ ] **Step 4: Run the structural test suite**

Run:

```bash
uv run pytest \
  tests/unit/test_validation_boundary_markers.py \
  tests/unit/test_validation_runner_wiring.py \
  tests/unit/test_dbt_namespace_reset.py \
  -v
```

Expected: PASS.

- [ ] **Step 5: Run the full validation flow**

Run:

```bash
./testing/ci/test-bootstrap-validation.sh
./testing/ci/test-developer-workflow.sh
./testing/ci/test-e2e-full.sh
```

Expected:

- bootstrap/admin failures report separately
- developer-workflow failures report separately
- standard in-cluster lane contains only `platform_blackbox` product tests
- destructive remains gated
- any remaining red tests are much more likely to be real product defects, with OpenLineage `parentRun` still expected as a separate follow-up

- [ ] **Step 6: Commit**

```bash
git add TESTING.md tests/unit/test_validation_runner_wiring.py
git commit -m "docs: describe validation lanes"
```

## Self-Review

- Spec coverage:
  - lane split: covered by Tasks 1-3
  - current failing outliers: covered by Task 2
  - reset/idempotency: covered by Task 4
  - documentation and execution handoff: covered by Task 5
- Placeholder scan:
  - no `TBD`, `TODO`, or deferred-code placeholders remain inside task steps
- Type consistency:
  - marker names are consistently `bootstrap`, `platform_blackbox`, `developer_workflow`, `destructive`
  - reset error is consistently `NamespaceResetError`
  - standard in-cluster runner keeps `TEST_SUITE=e2e` externally but semantically means the `platform_blackbox` lane

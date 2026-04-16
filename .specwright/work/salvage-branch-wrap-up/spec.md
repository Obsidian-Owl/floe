# Spec: Salvage Branch Wrap-Up

**Work unit**: `salvage-branch-wrap-up` (single unit, flat layout)
**Branch**: `feat/salvage-iceberg-purge-polaris-persistence`
**Goal**: Close the remaining gaps so the salvage branch can merge to main as a single PR.

## Context

Three commits are already on the branch:
- `06574d5` — Helm conditional JDBC block in `templates/configmap-polaris.yaml` + 6 helm unittest cases
- `3aff667` — `values-test.yaml` enabling JDBC persistence + PostgreSQL PVC + init-db scripts
- `3c4e9bb` — `tests/e2e/dbt_utils.py` `purge_table` + S3 sweep + 19 mock unit tests in `tests/e2e/tests/test_iceberg_purge.py`

Both changes are fully implemented and pass their local structural tests (helm unittest 6/6, mock unit tests 19/19). What remains is:
1. Moving the iceberg-purge unit tests to the correct tier (`tests/unit/`)
2. Removing credential duplication in `values-test.yaml`
3. Adding two E2E behavioral proofs that the changes actually work against real Polaris + MinIO
4. Documenting the demo namespace coupling so the purge path is verifiable

## Acceptance Criteria

### AC-1: Iceberg purge unit tests move to the correct tier
**Observable**: The file `tests/e2e/tests/test_iceberg_purge.py` no longer exists. A new file `tests/unit/test_iceberg_purge.py` exists with the same 19 test cases.

**Verification**: 
- `test -f tests/e2e/tests/test_iceberg_purge.py` returns **non-zero** (file gone)
- `test -f tests/unit/test_iceberg_purge.py` returns **zero** (file exists)
- `pytest tests/unit/test_iceberg_purge.py -q` runs from repo root without `INTEGRATION_TEST_HOST` or `--confcutdir` workarounds and reports `19 passed`

**Why this is hard to fake**: The test run must succeed with a bare `pytest tests/unit/test_iceberg_purge.py`. If the tests are still under `tests/e2e/` the autouse infrastructure smoke-check will raise `Exit: Infrastructure unreachable` and no tests will collect. If the move is done but `_DBT_UTILS_PATH` is not updated, the first test will fail with `FileNotFoundError` at `_load_dbt_utils()`.

### AC-2: `_DBT_UTILS_PATH` updated for the new location
**Observable**: In `tests/unit/test_iceberg_purge.py`:
- `_REPO_ROOT = Path(__file__).resolve().parents[2]` (was `parents[3]`)
- The path resolves to an existing file — assertion `_DBT_UTILS_PATH.exists()` is true when the tests collect

**Verification**:
- `grep -n "parents\[2\]" tests/unit/test_iceberg_purge.py` returns at least one match
- `grep -n "parents\[3\]" tests/unit/test_iceberg_purge.py` returns **zero** matches
- The test file includes an explicit fail-fast guard at module load: `assert _DBT_UTILS_PATH.exists(), f"dbt_utils.py not found at {_DBT_UTILS_PATH}"` — if the move breaks the path, collection fails immediately instead of silently swallowing a `FileNotFoundError`

**Why this is hard to fake**: Flipping the index to a wrong value (e.g. `parents[1]`) will fail the assertion at collect time. A silent `try: ... except FileNotFoundError: pass` wrapper around `_DBT_UTILS_PATH.read_text()` would bypass the guard — tester must NOT introduce any such wrapper.

### AC-3: `values-test.yaml` credential duplication removed — `persistence.jdbc.*` is canonical
**Observable**: In `charts/floe-platform/values-test.yaml`, the `polaris.env` list no longer contains entries for `QUARKUS_DATASOURCE_JDBC_URL`, `QUARKUS_DATASOURCE_USERNAME`, `QUARKUS_DATASOURCE_PASSWORD`, or `QUARKUS_DATASOURCE_DB_KIND`. The `polaris.persistence.jdbc.{url,username,password}` entries remain untouched.

**Verification**:
- `grep -c "QUARKUS_DATASOURCE_" charts/floe-platform/values-test.yaml` returns **zero**
- `grep -c "polaris.persistence" charts/floe-platform/values-test.yaml` returns at least one match (or `grep -E "^\s+persistence:" charts/floe-platform/values-test.yaml` under the `polaris:` block)
- After removal, `helm template charts/floe-platform -f charts/floe-platform/values-test.yaml` still renders the Polaris ConfigMap and its `application.properties` contains `polaris.persistence.type=relational-jdbc`, `quarkus.datasource.db-kind=postgresql`, `quarkus.datasource.jdbc.url=jdbc:postgresql://floe-platform-postgresql:5432/polaris`, `quarkus.datasource.username=floe`, and `quarkus.datasource.password=floe-test-password-1234`.

**Why this is hard to fake**: The `helm template` round-trip assertion catches the failure mode where somebody removes one copy but forgets the conditional block in the configmap template would emit the property. If the `persistence.jdbc.*` path were actually inert (the risk D-4 was revised to address), the rendered `application.properties` would NOT contain these lines and the assertion fails.

### AC-4 [tier: e2e]: Polaris JDBC state survives pod restart
**Observable**: After restarting the Polaris deployment, a user-created Iceberg namespace and table (with a UUID suffix so it cannot be confused with bootstrap state) is still present and loadable.

**Test runner**: This test lives under `tests/e2e/tests/test_polaris_jdbc_durability.py` and is collected by `make test-e2e` (see `testing/ci/test-e2e-cluster.sh` and `testing/ci/test-e2e.sh:567` — both invoke pytest against `tests/e2e/`). The E2E autouse smoke-check is satisfied under this runner because real infrastructure is deployed. **This test MUST be executed as part of the wrap-up's own merge gate** — AC-7 covers unit tier; the E2E invocation for AC-4/AC-5 is documented in AC-10 below.

**Verification** (new E2E test `tests/e2e/tests/test_polaris_jdbc_durability.py`):
1. Deploy floe-platform chart with `values-test.yaml` (Polaris in `relational-jdbc` mode)
2. Using PyIceberg REST catalog: create a namespace `restart_probe_<uuid4>` and inside it a table `probe_<uuid4>` with schema `(id: int, value: string)`. Record `table.metadata.table_uuid`.
3. Append at least one row: `table.append(pyarrow_table_with_data)` — ensures at least one Iceberg snapshot exists (not just empty metadata)
4. **Durability pre-check**: `assert loaded.current_snapshot() is not None` before restart — guards against PyIceberg deferred-commit failure mode (W6)
5. Run `kubectl rollout restart deployment/polaris -n <test-ns>` followed by `kubectl rollout status deployment/polaris -n <test-ns> --timeout=180s`
6. Wait for Polaris readiness via `wait_for_condition` polling against `/q/health/ready` with explicit `timeout=180.0` seconds
7. Open a **fresh** PyIceberg catalog client via `load_catalog(...)` directly — do NOT import `dbt_utils` in this file (avoids the module-level `_catalog_cache` entirely — see B2 resolution in decisions.md D-7)
8. Assert:
   - `assert namespace in [ns[0] for ns in catalog.list_namespaces()]` for the probe namespace
   - `loaded = catalog.load_table(f"{namespace}.probe_<uuid4>")`
   - `assert loaded.metadata.table_uuid == recorded_table_uuid`
   - `assert loaded.scan().to_arrow().num_rows >= 1`
9. Mark `@pytest.mark.requirement("salvage-wrap-up-AC-4")`
10. Add an inline test comment recording the negative control was run: `# Negative control: verified test FAILS with persistence.type=in-memory on {date} against commit {sha}` (W1 mitigation)

**Why this is hard to fake**:
- A fresh catalog client defeats the cache-returning-stale-state failure mode
- Asserting on the recorded `table_uuid` defeats the "bootstrap recreated a namespace of the same name" failure mode
- Asserting `num_rows >= 1` defeats the "metadata points at an empty snapshot" failure mode
- The test MUST fail if Polaris is run in in-memory mode — if inverting `persistence.type` to `in-memory` and re-running the test does not fail with `NoSuchNamespaceError` or table UUID mismatch, the test is too weak

**Negative control**: During tester write-up, temporarily set `persistence.type: in-memory` and confirm the test fails. Revert before commit. Document in as-built notes.

### AC-5 [tier: e2e]: `_purge_iceberg_namespace` cleans S3 data prefix (N→0 delta)
**Observable**: Calling `_purge_iceberg_namespace(namespace)` against a populated Iceberg table causes the corresponding S3 data prefix to go from `N > 0` objects to `0` objects.

**Test runner**: Same as AC-4 — file lives under `tests/e2e/tests/test_iceberg_purge_e2e.py`, collected by `make test-e2e`. Runner wiring documented in AC-10.

**Import isolation (B2 resolution)**: The test imports `_purge_iceberg_namespace` via `importlib.util.spec_from_file_location` to obtain a **fresh module instance with its own `_catalog_cache` dict**. This guarantees no cache pollution across test files (cache is per-module-instance, not per-process). Before invoking the function, the test MUST call `module._catalog_cache.clear()` as a defensive belt-and-braces step. The pattern is:
```python
import importlib.util
from pathlib import Path
_spec = importlib.util.spec_from_file_location(
    "dbt_utils_e2e_ac5",  # unique name — not "dbt_utils", to avoid sys.modules collision
    Path(__file__).resolve().parents[1] / "dbt_utils.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_mod._catalog_cache.clear()  # defensive
```

**Verification** (new E2E test `tests/e2e/tests/test_iceberg_purge_e2e.py`):
1. Deploy floe-platform chart with `values-test.yaml`
2. Create a unique namespace `purge_probe_<uuid4>` and table `probe_<uuid4>` via PyIceberg (fresh catalog client — not via `_mod`)
3. Append at least **10** rows so both metadata AND data files exist:
   ```python
   data = pa.table({"id": list(range(10)), "value": [f"row-{i}" for i in range(10)]})
   table.append(data)
   ```
4. Capture `data_prefix = urlparse(table.metadata.location).path.lstrip("/")` and bucket
5. List S3 objects under `data_prefix` via `httpx` ListObjectsV2:
   - `before_count = len(keys_from_response)`
   - **Assert `before_count > 0`** — test MUST fail if the prefix was never populated
6. Call `_mod._purge_iceberg_namespace(namespace)` (the isolated module instance from the import pattern above)
7. List S3 objects under the same prefix again:
   - `after_count = len(keys_from_response)`
   - Assert `after_count == 0`
8. Assert `before_count > 0 and after_count == 0` in one combined expression so a test report shows the N→0 delta
9. Mark `@pytest.mark.requirement("salvage-wrap-up-AC-5")`
10. Add inline comment recording negative control: `# Negative control: verified test FAILS with catalog.purge_table(fqn) commented out on {date} against commit {sha}` (W1 mitigation)

**Why this is hard to fake**:
- The pre-assertion `before_count > 0` catches the "never-populated prefix" failure mode
- The N→0 delta catches the "silent exception swallow" failure mode where `_purge_iceberg_namespace` fails and returns cleanly — a passing test MUST observe a real object deletion
- The test imports `_purge_iceberg_namespace` directly rather than going through `run_dbt` — this isolates the purge code path from dbt-related failures

**Negative control**: During tester write-up, temporarily comment out the `catalog.purge_table(fqn)` line in `_purge_iceberg_namespace` and confirm the test fails because the S3 sweep alone does not clean metadata. Revert before commit. Document in as-built notes.

### AC-6: Existing helm unittest suite continues to pass
**Observable**: `make helm-test-unit` (or the equivalent containerized invocation) runs the updated `tests/polaris_persistence_test.yaml` and reports **`Tests: 6 passed`** — the env-var case is **rewritten in place**, not deleted; the case count remains 6. (W3 mitigation.)

**Verification**:
- `helm unittest charts/floe-platform -f 'tests/polaris_persistence_test.yaml'` exits 0 with `Tests: 6 passed` (no case count reduction)
- The test case originally named "should render JDBC env vars in deployment when polaris.env is set" is **renamed** to "should render JDBC properties in configmap when persistence.type=relational-jdbc" and its assertions repointed from `spec.containers[0].env` on the deployment to `data["application.properties"]` on the polaris configmap — matching `quarkus.datasource.jdbc.url=jdbc:postgresql://` via `matchRegex`
- The test file header comment must reflect the revised D-4 (canonical path = `persistence.jdbc.*`)

**Why this is hard to fake**: `helm unittest` is a structural check with strict assertions. Weakening the assertions to make them pass (e.g. removing the `matchRegex` for `quarkus.datasource.jdbc.url`) is explicitly forbidden by the assertion-integrity rule in `.claude/rules/testing-standards.md` — any weakening must be escalated via `AskUserQuestion`.

### AC-7: `make test-unit` passes end-to-end
**Observable**: `make test-unit` completes successfully and includes `tests/unit/test_iceberg_purge.py` in the collection (all 19 cases run and pass).

**Verification**:
- `make test-unit` exit code 0
- The pytest output includes the line `tests/unit/test_iceberg_purge.py .................` (or equivalent verbose form showing 19 passing tests)
- The unit-tier coverage threshold (configured in `testing/ci/test-unit.sh`) is still met

**Why this is hard to fake**: This is the strongest behavioral gate — proves the move worked end-to-end under the project's real unit test runner, not an ad-hoc pytest invocation. An AC-1 pass plus an AC-7 fail means the move is half-done.

### AC-8: Regression guards (grep-level)
**Observable**: Grep-level invariants prevent silent regressions.

**Verification**:
- `grep -rn "drop_table" tests/e2e/dbt_utils.py` returns **zero** matches (no reversion to `drop_table`)
- `grep -n "httpx" tests/e2e/dbt_utils.py` returns **at least one** match (locks D-3 — S3 sweep stays)
- `grep -n "purge_table" tests/e2e/dbt_utils.py` returns at least one match (line 148 still calls it)
- `grep -rn "QUARKUS_DATASOURCE_" charts/floe-platform/values-test.yaml` returns **zero** matches (AC-3 regression guard)
- `grep -n "boto3" tests/e2e/dbt_utils.py tests/unit/test_iceberg_purge.py` returns **zero** matches (no AWS SDK introduced)

**Why this is hard to fake**: Grep is grep. A `# noqa`-style bypass does not work against these patterns.

### AC-9: Demo namespace coupling documented in as-built notes
**Observable**: The PR description (and `plan.md` as-built notes section) includes a short mapping table showing which Polaris namespace each demo dbt project writes to at runtime, and confirms it matches the `<name.replace("-","_")>_raw` / `<name.replace("-","_")>` convention in `tests/e2e/dbt_utils.py:246,250`.

**Verification**:
- During build phase, run an actual `dbt seed` against one demo project (e.g. `customer-360`) in an E2E session and observe the Polaris namespace(s) that appear via `catalog.list_namespaces()`
- Record the observed namespaces in `plan.md` "As-Built Notes" with at least one confirmed example: `customer-360 → Polaris namespaces: {customer_360_raw, customer_360}` (or whatever is actually observed)
- If the observed namespaces do NOT match the convention, **STOP** and escalate via `AskUserQuestion`. Do not silently rewrite the dbt_utils.py mapping — the mock tests were presumably designed against a working convention, so a mismatch indicates either a regression on main or a bug the original author was working around.

**Why this is hard to fake**: The as-built note must cite an actual observed namespace, not a guess. A reviewer checking the note against a fresh E2E run will catch a fabricated mapping.

**Fallback path (W4 mitigation)** — if no E2E environment is available during the build phase, the tester MAY satisfy AC-9 via a lighter-weight substitute:
1. Grep `demo/*/dbt_project.yml` for the `name:` field in each demo project — this is the string dbt turns into the default schema.
2. Compute the expected Polaris namespace via the same transformation `dbt_utils.py:246,250` uses: `name.replace("-","_")` → `{result}` and `{result}_raw`.
3. Document the derived mapping in as-built notes with a header "Derived (no live E2E)" so a reviewer knows it is not an observed measurement.
4. Open a follow-up backlog item to verify against live E2E.

This fallback is **only acceptable when no E2E env is accessible** — live observation remains the preferred path.

### AC-10: E2E tests for AC-4 and AC-5 are actually executed
**Observable**: The E2E test files created for AC-4 and AC-5 are collected and executed by `make test-e2e` (or `make test-e2e-host` during local dev), and the run passes before the PR is marked ready.

**Verification**:
- `make test-e2e` exit code 0 on at least one session during the build phase
- The pytest output includes both `tests/e2e/tests/test_polaris_jdbc_durability.py::TestPolarisJdbcDurability::test_unique_namespace_and_table_survive_polaris_restart PASSED` and `tests/e2e/tests/test_iceberg_purge_e2e.py::TestIcebergPurgeE2E::test_purge_removes_s3_data_objects_n_to_zero PASSED`
- Evidence of the run is captured in as-built notes (session timestamp, DevPod or Kind cluster name, commit SHA)

**Why this is hard to fake**: Writing an E2E test without running it is the workflow-level Accomplishment Simulator. This AC closes the loop — AC-4/AC-5 are "written AND executed", not just "written and assumed to work". A reviewer inspecting the PR must see the green E2E output (or a session log excerpt) pasted into the PR description.

## Out of Scope (deferred to backlog)

- Polaris `existingSecret` indirection for production deployments (follow-up work unit)
- Fixing the E2E autouse smoke-check so mock tests in `tests/e2e/tests/` are not blocked (pattern P73; separate work unit)
- Full E2E matrix coverage for in-memory vs JDBC Polaris modes
- Removing the S3 sweep once Polaris #1195/#1448 is verified fixed upstream

## WARNs (documented, non-blocking)

- **WARN from critic #6**: Demo namespace coupling is verified via build-phase as-built notes (AC-9), not a dedicated test. If this becomes a source of silent failures, promote to a regression test in a follow-up work unit.
- **WARN from critic #8**: Regression guard for "keep the S3 sweep" is grep-level (`AC-8` checks for `httpx` in `dbt_utils.py`), not a behavioral test. Acceptable because the sweep's behavior is covered by the existing mock tests (`TestS3PrefixDeletion`, `TestS3Pagination`) and AC-5.

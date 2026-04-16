# Design: Wrap Up Salvage Branch

**Branch**: `feat/salvage-iceberg-purge-polaris-persistence`
**Baseline**: `main` (3 commits ahead)
**Question answered**: What is fully implemented + tested vs. partial, and what is needed to ship?

## Summary

The salvage branch carries two independent, trunk-ready changes plus a shared values-test.yaml edit. After running all local verification, **both changes are fully implemented**. The only work needed to "wrap up" is closing a small set of gaps around **integration-level proof, test location hygiene, and one credential-duplication smell** — none of which are architectural.

Recommended wrap-up path: a single work unit delivering the remaining verification + cleanup, then ship as one PR.

## Commits on branch (against main)

| Commit  | Scope                                       | LOC         |
|---------|---------------------------------------------|-------------|
| 06574d5 | Helm: conditional JDBC block in Polaris configmap + helm unittest | +130        |
| 3aff667 | values-test.yaml: enable JDBC persistence + PG PVC + init-db scripts | +27 / -1   |
| 3c4e9bb | E2E: `purge_table` + S3 sweep in dbt_utils; 19 mock unit tests | +768 / -8 |

## Change 1 — Polaris JDBC persistence (commits 06574d5 + 3aff667)

**Intent**: Make Polaris survive pod restarts by moving from in-memory to `relational-jdbc` on PostgreSQL, via opt-in Helm config.

### Fully implemented
- `templates/configmap-polaris.yaml` conditional block renders Quarkus datasource properties only when `polaris.persistence.type=relational-jdbc`. In-memory mode (default) is byte-identical to main.
- `values-test.yaml` enables the new path for the test chart: `persistence.type`, `persistence.jdbc.{url,username,password}`, `polaris.env` Quarkus overrides, `postgresql.persistence.enabled=true` with 1Gi PVC, and `initdb` creating the `polaris` database plus GRANTs.
- The bootstrap Job template renders correctly in JDBC mode (verified by helm unittest AC-5).

### Fully tested (local)
- **`charts/floe-platform/tests/polaris_persistence_test.yaml`** — 6 helm unittest cases covering:
  - AC-2: JDBC properties present when `persistence.type=relational-jdbc`
  - AC-6: JDBC properties **absent** when unset or `in-memory` (backward compatibility)
  - AC-1: `polaris.env` renders `QUARKUS_DATASOURCE_*` vars on deployment
  - AC-5: Bootstrap Job renders with JDBC persistence
  - AC-2 extra: `quarkus.datasource.jdbc.url=<literal>` property assertion
- **Result (just re-run)**: `6 passed, 0 failed`

### Gaps (to wrap up)
1. **No integration-level proof that state actually survives a restart.** Helm unittest only validates template rendering, not runtime behavior. There is no test that: (a) deploys with JDBC enabled, (b) creates a catalog/namespace, (c) restarts the Polaris pod, (d) asserts the namespace is still present.
2. **Credential duplication smell in `values-test.yaml`.** Password appears in both `polaris.persistence.jdbc.password` **and** `polaris.env[QUARKUS_DATASOURCE_PASSWORD]`. Either path works but only one should feed Quarkus — the duplication is an easy foot-gun for future edits.
3. **No `existingSecret` indirection.** Acceptable for `values-test.yaml` (test-only credentials), but there is no documented production path for prod deployments to inject DB credentials via Secret. This does not block this PR but should be captured as a follow-up.

## Change 2 — Iceberg purge (commit 3c4e9bb)

**Intent**: Replace `drop_table` with `purge_table` (which sends `purgeRequested=true` to the Polaris REST catalog) and add a belt-and-suspenders S3 object sweep to work around Polaris bugs #1195/#1448 where server-side purge leaves orphaned metadata files.

### Fully implemented
- `tests/e2e/dbt_utils.py::_purge_iceberg_namespace` fully rewritten:
  - Uses `catalog.purge_table(fqn)` (line 148) — verified by Grep that `drop_table` no longer appears in the file
  - S3 sweep via `httpx.Client` with BasicAuth: ListObjectsV2 with IsTruncated/ContinuationToken pagination, then DeleteObjects XML API
  - All cleanup failures non-fatal and log only `type(exc).__name__` (satisfies Constitution S-VI / CWE-532)
  - Namespace drop preserved after table purge
  - No boto3 dependency introduced; uses existing `httpx`

### Fully tested (local)
- **`tests/e2e/tests/test_iceberg_purge.py`** — 19 mock unit tests across 6 classes:
  1. `TestPurgeTableReplacesDropTable` — purge_table called, drop_table not called
  2. `TestS3PrefixDeletion` — S3 delete happens after purge, prefix derived from table location
  3. `TestS3Pagination` — IsTruncated/ContinuationToken loop
  4. `TestNoAWSDependency` — no boto3, uses httpx.Client
  5. `TestCleanupNonFatal` — exceptions don't propagate
  6. `TestNamespaceDropPreserved` — namespace dropped only after all tables
- **Result (just re-run with `--confcutdir=.` to bypass e2e autouse smoke-check)**: `19 passed in 15.48s`

### Gaps (to wrap up)
1. **Test location anti-pattern (P73 / DIR-004 violation).** These are pure mock unit tests but live in `tests/e2e/tests/`. The E2E autouse conftest blocks them from ordinary `pytest` invocation and from CI paths that don't set `INTEGRATION_TEST_HOST=k8s`. They must move to `tests/unit/` (or a `tests/e2e/unit/` sibling the autouse skips) before this PR can ship without a bespoke CI invocation.
2. **No integration-level proof that `purge_table` actually cleans S3 against real Polaris+MinIO.** The mock tests verify call shape, not end-to-end behavior. An existing E2E test that creates an Iceberg table, calls the purge path, and asserts S3 is empty would close this gap — and the salvage branch already assumes such a test would run at the next E2E sweep.
3. **No regression test that dbt seed/run still succeeds after the purge path runs.** The purge is invoked from `run_dbt` (lines 246, 250 of dbt_utils.py) before every `seed`/`run`. If purge misbehaves, every downstream E2E test fails opaquely.

## Blast Radius

**Touched**:
- `charts/floe-platform/templates/configmap-polaris.yaml` — **local**. Conditional gated on new value; in-memory default path unchanged.
- `charts/floe-platform/tests/polaris_persistence_test.yaml` — **local**. New test file only.
- `charts/floe-platform/values-test.yaml` — **adjacent**. Changes the test chart wiring; any integration/E2E test that assumes in-memory Polaris state resets between deploys will behave differently.
- `tests/e2e/dbt_utils.py` — **adjacent**. Every E2E test that uses `run_dbt` (effectively all of them) hits the new purge path before seed/run.
- `tests/e2e/tests/test_iceberg_purge.py` — **local**. New test file only.

**Failure propagation scope**:
- Polaris configmap conditional failure → isolated to deployments setting `persistence.type`; default path untouched.
- values-test.yaml + PG PVC failure → all E2E runs using this chart values file fail at helm install.
- dbt_utils purge failure → every E2E seed/run run.

**Not changed**:
- Production values files
- Chart templates outside configmap-polaris.yaml
- `testing/fixtures/*` credentials plumbing
- Any Dagster / dbt plugin code
- CI workflow definitions

## Recommendation

Create **one** follow-up work unit, `salvage-wrap-up`, with the following specification — then ship as a single PR. No decomposition needed; total scope is test movement + one integration test + one values cleanup.

### Proposed work-unit ACs (revised after architect critic review)

1. **AC-1**: `test_iceberg_purge.py` moves to `tests/unit/test_iceberg_purge.py`. After move, `pytest tests/unit/test_iceberg_purge.py` runs from repo root without any special env vars or `confcutdir` workaround, and all 19 tests pass.
2. **AC-2**: `_DBT_UTILS_PATH` in the moved file uses `Path(__file__).resolve().parents[2] / "tests" / "e2e" / "dbt_utils.py"` (was `parents[3]`). Assertion-level regression guard: the first test in the file must open `_DBT_UTILS_PATH` successfully, so a broken path fails fast rather than FileNotFoundError-swallowed.
3. **AC-3**: `values-test.yaml` credential duplication removed. **Canonical path = `polaris.persistence.jdbc.*`** (the chart-native path the template renders at `configmap-polaris.yaml:31-46`). Remove the duplicated `QUARKUS_DATASOURCE_*` entries from `polaris.env` **unless** a concrete Quarkus precedence need is documented. See D-4 (revised) for rationale.
4. **AC-4** **[tier: e2e]**: Polaris restart durability test. The test MUST:
   - Deploy the test chart with `persistence.type=relational-jdbc`
   - Create a **unique, non-bootstrap** Iceberg namespace (random suffix, e.g. `restart_probe_<uuid4>`) via PyIceberg REST catalog
   - Create an Iceberg table inside that namespace with at least one `INSERT`-populated row (so metadata + data files exist in S3)
   - Capture the namespace name and table UUID
   - `kubectl rollout restart deployment/polaris -n <test-ns>` and wait for readiness via existing `wait_for_condition` polling
   - Re-open a fresh PyIceberg catalog client (NOT the cached one) and assert both: (a) `list_namespaces()` contains the unique probe namespace, (b) `load_table()` returns the same table UUID
   - This defeats the Accomplishment Simulator failure mode where a bootstrap-recreated `floe-e2e` namespace would pass a naive `list_namespaces()` check.
5. **AC-5** **[tier: e2e]**: Iceberg purge S3 cleanup test. The test MUST:
   - Create an Iceberg table in a unique namespace and INSERT at least 10 rows so the data prefix contains real Parquet files
   - Assert **before purge**: `s3:ListObjectsV2` on the table data prefix returns `object_count > 0`; capture the exact count
   - Invoke `_purge_iceberg_namespace(<namespace>)` directly
   - Assert **after purge**: `s3:ListObjectsV2` on the same prefix returns zero objects (N → 0 delta, not a trivially-empty check)
   - Defeats the swallowed-exception failure mode where purge silently fails and the test passes against a never-populated prefix.
6. **AC-6**: Existing helm unittest suite (`tests/polaris_persistence_test.yaml`) continues to pass: `6 passed`. If AC-3 removes the `polaris.env` duplication, the AC-1 unittest case ("should render JDBC env vars in deployment when polaris.env is set") must be updated to assert the chart-native `persistence.jdbc.*` rendering path instead.
7. **AC-7**: `make test-unit` passes end-to-end (proves the moved file collects under the unit tier with no `confcutdir` workaround). This is the strongest behavioral gate in the list.
8. **AC-8**: Regression guards (grep-level):
   - `grep -rn "drop_table" tests/e2e/dbt_utils.py` returns zero matches
   - `grep -rn "httpx" tests/e2e/dbt_utils.py` returns at least one match (locks D-3 — sweep stays)
9. **AC-9**: Demo namespace coupling verified. For each of `demo/customer-360`, `demo/iot-telemetry`, `demo/financial-risk`, document which Polaris namespace(s) dbt writes to at runtime, and confirm the `<name.replace("-","_")>_raw` / `<name.replace("-","_")>` convention in `dbt_utils.py:246,250` actually matches. If the convention is wrong, purge silently no-ops and the Polaris #1195 stale-metadata bug returns. Verification can be a short doc snippet in `as-built notes`, not necessarily a test.

### Out of critic scope (verified, no AC needed)

- **CI helm unittest auto-discovery**: verified at `.github/workflows/helm-ci.yaml:385` → `make helm-test-unit` → containerized `helm-unittest floe-platform` which auto-discovers all `tests/*_test.yaml` files. New `polaris_persistence_test.yaml` will be picked up automatically.
- **Current branch identity**: `git branch --show-current` confirms we are on `feat/salvage-iceberg-purge-polaris-persistence`. The design targets the correct branch.

### Decision: single PR vs split

**Single PR, single work unit.** The two changes share `values-test.yaml` and both land at the E2E infrastructure boundary. Splitting forces the second PR to rebase over the first's `values-test.yaml` edit and provides no blast-radius isolation (both are gated behind E2E anyway). Recorded in `decisions.md`.

### Out of scope (defer to backlog)

- Polaris `existingSecret` indirection for production deployments
- Full E2E matrix coverage for in-memory vs JDBC Polaris modes
- Fixing the E2E autouse smoke-check so mock tests in `tests/e2e/tests/` don't get blocked (root cause of test-location anti-pattern)

# Assumptions: Salvage Branch Wrap-Up

## ACCEPTED

### A-1: The salvage branch is still needed
**Classification**: Type 2 (reversible — can be revalidated before PR)
**Content**: The work on this branch has not been superseded by newer changes in main. Checked via `git log main..HEAD` and `git show --stat` of each commit — the three touched areas (configmap-polaris.yaml, values-test.yaml, dbt_utils.py) have not been modified on main since the branch was cut.
**Status**: ACCEPTED. Quick re-check before opening the PR is sufficient.

### A-2: Helm unittest is a sufficient structural gate for configmap rendering
**Classification**: Type 2
**Content**: The 6 helm unittest cases validate template rendering for all acceptance criteria in the original polaris-persistence work. Template rendering is the only concern at the chart-unit level; runtime behavior is the E2E concern.
**Status**: ACCEPTED. Confirmed by re-running the suite (`6 passed`).

### A-3: The 19 mock unit tests in test_iceberg_purge.py exercise the contract we care about
**Classification**: Type 2
**Content**: The tests verify call shape (purge_table invoked, drop_table not invoked), S3 API usage (httpx not boto3, IsTruncated handled), and failure isolation (exceptions non-fatal). Runtime integration is out of scope for unit tests.
**Status**: ACCEPTED. Confirmed by running the suite (`19 passed`).

### A-4 (REVISED): Credential duplication — canonical path is `persistence.jdbc.*`
**Classification**: Type 2
**Content**: Verified by reading `templates/configmap-polaris.yaml:31-46`. The chart template renders `quarkus.datasource.password={{ .password }}` into `application.properties` when `persistence.jdbc.password` is set. So the chart-native path is the one the template wires; `polaris.env[QUARKUS_DATASOURCE_*]` is the duplicate escape hatch. See D-4 (revised) for the canonical-path decision.
**Status**: ACCEPTED — resolve by removing `polaris.env[QUARKUS_DATASOURCE_*]` in AC-3. AC-4 (restart durability) is the behavioral gate that validates the removal doesn't break Polaris startup.

## DEFERRED (to backlog)

### A-5: Polaris production deployments need an existingSecret path
**Classification**: Type 1 if applied to prod, Type 2 for the test values file we have now
**Content**: Production deployments should inject Polaris DB credentials via `existingSecret` indirection rather than plaintext values. This salvage branch does not introduce that path but also does not block it — it's an additive follow-up.
**Status**: DEFERRED to backlog. Do not block this PR.

### A-6: The E2E autouse smoke-check should not block pure unit tests
**Classification**: Type 1 structural (affects test organization policy)
**Content**: `tests/e2e/conftest.py` has an autouse fixture that raises "Infrastructure unreachable" for any test collected under `tests/e2e/`. This blocks mock-based unit tests from running even though they need no infrastructure. Pattern P73 captures this as known.
**Status**: DEFERRED. Address in a separate work unit focused on the autouse fixture; this salvage wrap-up will work around it by moving the test file (AC-1).

### A-7: Bootstrap Job does NOT re-run on Polaris pod restart
**Classification**: Type 2 behavioral
**Content**: Critic flagged that AC-4 could pass for the wrong reason if the Polaris bootstrap Job re-runs on pod restart (recreating the bootstrap namespaces). Helm `Job` resources are typically single-execution — a pod restart re-starts the deployment container but does NOT re-run a separate `Job` resource. AC-4's "unique non-bootstrap namespace with UUID suffix" defends against this failure mode regardless: if a new bootstrap run happened, the probe namespace with its UUID suffix would NOT be recreated.
**Status**: ACCEPTED — AC-4 wording is defensive enough that bootstrap re-run does not falsify the test.

### A-8: Demo namespace convention in `dbt_utils.py:246,250` matches actual dbt runtime
**Classification**: Type 2 data
**Content**: The purge code derives the namespace as `project_dir.name.replace("-","_")` — so `customer-360` → `customer_360`, with `customer_360_raw` for seeds. No design-time artifact verifies this matches what dbt writes to Polaris at runtime. The existing mock unit tests verify the call contract but NOT the convention.
**Status**: DEFERRED verification to build phase (AC-9). If build reveals a mismatch, escalate rather than silently "fix" the mapping — the original salvage commits were shipping this and presumably working.

### A-9: `make test-e2e` collects files under `tests/e2e/tests/` and satisfies the autouse smoke-check
**Classification**: Type 2 (verifiable before build)
**Content**: Verified by grep: `testing/ci/test-e2e.sh:567` invokes pytest against `tests/e2e/`, and `testing/ci/test-e2e-cluster.sh` delegates to the same script in-cluster. The autouse smoke-check only fails when real infrastructure is unreachable; under `make test-e2e`, the infra is deployed to a Kind cluster before pytest runs.
**Status**: ACCEPTED. Tester confirms collection by running `make test-e2e --collect-only` equivalent (`uv run pytest tests/e2e/tests/ --collect-only`) in a live session during Task 5.

### A-10: PyIceberg `table.append(...)` commits the snapshot to the catalog before returning
**Classification**: Type 2 (behavioral)
**Content**: PyIceberg's `Transaction.append` flow for `Table` in the REST catalog runs `commit_transaction` synchronously — the catalog HTTP request completes before `append` returns. Confirmed against `pyiceberg` 0.11.0rc2 source. Spec AC-4 adds a `table.current_snapshot() is not None` precondition as a defensive guard in case this assumption weakens in a future version.
**Status**: ACCEPTED — defended by AC-4 step 4.

### A-11: PostgreSQL runs independently of Polaris and survives `kubectl rollout restart deployment/polaris`
**Classification**: Type 2 (integration)
**Content**: `values-test.yaml` deploys postgresql as a separate release (via Bitnami subchart) with its own StatefulSet and PVC. Restarting `deployment/polaris` only cycles the Polaris pod; PG stays up with its data intact. This is the condition that makes AC-4 meaningful — if PG also restarted, "state survives" would conflate JDBC persistence with PG durability.
**Status**: ACCEPTED — confirmed via `values-test.yaml` inspection (postgresql subchart enabled with persistence.enabled=true).

### A-12: `importlib.util.module_from_spec` creates an isolated module instance with its own globals
**Classification**: Type 2 (Python runtime semantics)
**Content**: Per CPython docs, `importlib.util.module_from_spec(spec)` returns a fresh `ModuleType` object; subsequent `spec.loader.exec_module(mod)` executes the source against `mod.__dict__`, creating a fresh copy of all module-level objects (including `_catalog_cache`). Module-level state is NOT shared between instances loaded via different spec objects, even for the same file.
**Status**: ACCEPTED — standard Python semantics; underpins D-7 / B2 resolution.

## Contradictions with ACs

None identified. All AC candidates are verifiable with the current codebase + local tooling, given a live E2E environment for AC-4/AC-5/AC-10 (with AC-9 fallback for offline build phases).

# Plan: test-infra-drift-elimination

**Single work unit, 4 sequential tasks.** Each task ends at a green state
(chart renders cleanly, scripts execute, contract test passes or is not yet
introduced). Task 4 introduces the tripwire; it must be last so earlier tasks
do not fail their own post-conditions against a test they haven't satisfied yet.

**Constitution + CLAUDE.md constraints (carried into every task):**
- S1 tech ownership — chart owns identifiers (this is the point of the work)
- S4 contracts — `CompiledArtifacts` untouched
- S5 K8s-Native Testing — tests still run in Kind cluster, no change to runtime
- S9 Escalation — any decision not already recorded in `decisions.md` is a new
  escalation (via `AskUserQuestion`), not a silent choice
- Test Assertion Integrity — never weaken a failing test to make it pass
- Pre-alpha, no backcompat — deletions are clean, no deprecation window

---

## Task 1 — Chart templates, helpers, values

**Goal**: replace raw test manifests with chart templates gated by `tests.enabled`.
After this task, `helm template` renders the test infrastructure correctly but
nothing yet *uses* the rendered output — the shell scripts still point at the
raw files. That's fine: task 1 only needs its own tests green (chart renders
without error, helm lint passes, helm unittest passes).

### Verification at task start (A6 + A9)

Before writing any code:
1. `grep -rn 'testing/k8s/\(jobs\|rbac\)' .github/workflows/ Makefile` — record
   every hit. Any GitHub Actions workflow reference will need migration in
   task 3; record in `as-built` notes. Any Makefile reference becomes part of
   task 2 or 3.
2. Read `charts/floe-platform/templates/job-polaris-bootstrap.yaml` and
   identify which values key the bootstrap reads for the catalog name. Record
   as `polaris.catalogName` (or discovered name) in decisions.md. This is the
   canonical key for AC-3.

### File change map

| Action | File | Purpose |
|---|---|---|
| CREATE | `charts/floe-platform/templates/tests/job-e2e.yaml` | Rendered form of `testing/k8s/jobs/test-e2e.yaml`. All hardcoded `floe-platform-*` → helper calls. All Secret refs → helper-rendered names. Gated by `{{- if .Values.tests.enabled }}`. |
| CREATE | `charts/floe-platform/templates/tests/job-e2e-destructive.yaml` | Same for destructive Job. |
| CREATE | `charts/floe-platform/templates/tests/rbac-standard.yaml` | SA + Role + RoleBinding for standard test runner. Role must NOT include `list`/`watch` on secrets (security-hardening AC-8). |
| CREATE | `charts/floe-platform/templates/tests/rbac-destructive.yaml` | SA + Role + RoleBinding for destructive test runner. `resourceNames` list read from `.Values.tests.destructive.releaseHistoryNames`. |
| MODIFY | `charts/floe-platform/templates/_helpers.tpl` | Add `floe-platform.testRunner.saName` → `{{fullname}}-test-runner` and `floe-platform.testRunnerDestructive.saName` → `{{fullname}}-test-runner-destructive`. Do not modify existing helpers. |
| MODIFY | `charts/floe-platform/values.yaml` | Add `tests:` section with `enabled: false` (production default) and documented schema for every key the test templates consume. |
| MODIFY | `charts/floe-platform/values-test.yaml` | Add `tests.enabled: true`, `tests.warehouse: floe-e2e` (or alias to `polaris.catalogName`), `tests.image.repository: floe-test-runner`, `tests.image.tag: latest`, `tests.destructive.releaseHistoryNames: [floe-platform-v1..v10]`. Keep existing `fullnameOverride: floe-platform`. |
| MODIFY | `charts/floe-platform/templates/job-polaris-bootstrap.yaml` | Point catalog-create payload at the canonical key identified in "Verification at task start" step 2. If canonical key is `polaris.catalogName` already, no change. If adopting `tests.warehouse`, add a chart-level fail assertion that the two agree when both are set (or route one through the other). |
| CREATE | `charts/floe-platform/tests/test_test_templates.yaml` | helm-unittest suite covering the new templates. Minimum: `tests.enabled=false` renders zero test resources; `tests.enabled=true` renders expected SA/Role/Jobs with helper-rendered names. Follow `P49`/`P50` from MEMORY.md (use `notExists`, explicit `set:` for every asserted value). |

### Definition of done (task 1)

- `helm lint charts/floe-platform` passes with both `values.yaml` and `values-test.yaml`.
- `helm template floe-platform charts/floe-platform -f charts/floe-platform/values-test.yaml --set tests.enabled=true` renders without error and produces: 2 Jobs, 2 ServiceAccounts, 2 Roles, 2 RoleBindings under `templates/tests/`.
- `helm template floe-platform charts/floe-platform -f charts/floe-platform/values.yaml` renders zero documents from `templates/tests/`.
- `make helm-test-unit` passes (includes the new helm-unittest suite).
- Every identifier in the rendered test Jobs (Service names, Secret names, SA names) matches an identifier in the rendered platform (Services, Secrets, ServiceAccounts). Verification can be done by manual `helm template | yq` or spot check — the automated version lives in task 4's contract test.
- Raw files under `testing/k8s/jobs/` and `testing/k8s/rbac/` are still present and untouched at task 1 end. No `git rm` yet.

### Commit

`refactor(chart): move test Jobs and RBAC into floe-platform chart templates`

---

## Task 2 — `testing/ci/common.sh` + shell script migration

**Goal**: every `testing/ci/test-*.sh` script sources `common.sh` and resolves
all K8s identifiers through `FLOE_*` variables and `floe_*` helpers. After
this task, scripts still work against the OLD raw manifests AND the NEW chart
templates — they just rendered-and-apply via `floe_render_test_job` from the
chart, which now exists thanks to task 1.

### File change map

| Action | File | Purpose |
|---|---|---|
| CREATE | `testing/ci/common.sh` | Single source of truth for `FLOE_RELEASE_NAME`, `FLOE_NAMESPACE`, `FLOE_KIND_CLUSTER`, `FLOE_VALUES_FILE`, `FLOE_CHART_DIR`, `floe_render_test_job()`, `floe_service_name()`, `floe_require_cluster()`. Must be compatible with `set -u` strict mode. Must absorb legacy `KIND_CLUSTER` and `KIND_CLUSTER_NAME` without overriding an explicit `FLOE_KIND_CLUSTER`. |
| MODIFY | `testing/ci/test-integration.sh` | Source `common.sh` as first non-comment line. Replace `KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-floe}"` default with use of `$FLOE_KIND_CLUSTER`. Replace `JOB_MANIFEST="testing/k8s/jobs/test-e2e.yaml"` dispatch with `floe_render_test_job tests/job-e2e.yaml | kubectl apply -f -`. Leave `TEST_SUITE=integration` branch repointed at `tests/job-e2e.yaml` or removed — resolved in task 3 per AC-8. |
| MODIFY | `testing/ci/test-e2e-cluster.sh` | Source `common.sh`. Replace `KIND_CLUSTER="${KIND_CLUSTER:-floe}"` default with `$FLOE_KIND_CLUSTER`. Replace direct `kubectl apply -f testing/k8s/jobs/test-e2e.yaml` with `floe_render_test_job tests/job-e2e.yaml | kubectl apply -f -`. Same for destructive variant. Apply the chart-rendered RBAC via `helm template ... -s templates/tests/rbac-standard.yaml | kubectl apply -f -` (replaces `kubectl apply -f testing/k8s/rbac/...` calls). |
| MODIFY | `testing/ci/test-e2e.sh` | Source `common.sh`. Replace every hardcoded `floe-platform-postgresql`, `floe-platform-minio`, `floe-platform-polaris`, `floe-platform-marquez`, `floe-platform-dagster-webserver`, `floe-platform-otel`, `floe-platform-jaeger-*` string in `kubectl port-forward` / `kubectl exec` calls with `"$(floe_service_name <component>)"`. Replace namespace hardcode with `$FLOE_NAMESPACE`. |
| CREATE | `tests/unit/test_ci_common_sh.py` | Unit tests for `common.sh` behavior (AC-6). Tests source the script in a subshell via `bash -c`, capture env + helper output, assert documented behavior. Uses `subprocess.run(..., shell=False)` for each assertion. |

### Definition of done (task 2)

- `bash -n testing/ci/common.sh` and every `test-*.sh` passes syntax check.
- `tests/unit/test_ci_common_sh.py` passes all cases listed in AC-6's falsifying test.
- `make test-e2e` on DevPod+Hetzner launches the test Job successfully. The Job's pod reaches `Running`. No `not found` errors in kubelet events.
- Raw files under `testing/k8s/jobs/` and `testing/k8s/rbac/` still exist (deleted in task 3). They are no longer referenced by any shell script, but the directories are intact — this keeps task 2's blast radius bounded.

### Commit

`refactor(ci): source identifiers from common.sh; render test manifests via helm template`

---

## Task 3 — Delete dead code

**Goal**: remove `test-runner.yaml`, `testing/k8s/jobs/`, `testing/k8s/rbac/`,
and any `TEST_SUITE=integration` branch still pointing at `test-runner.yaml`.
Migrate any GitHub Actions workflow or Makefile target that referenced the
deleted paths. After this task, there is no raw test manifest anywhere in the
repo.

### File change map

| Action | File | Purpose |
|---|---|---|
| DELETE | `testing/k8s/jobs/test-runner.yaml` | Feb 6 stale file. No consumer after task 2 + AC-8 resolution. |
| DELETE | `testing/k8s/jobs/test-e2e.yaml` | Replaced by `charts/floe-platform/templates/tests/job-e2e.yaml`. |
| DELETE | `testing/k8s/jobs/test-e2e-destructive.yaml` | Replaced by chart template. |
| DELETE | `testing/k8s/jobs/` (dir) | Empty after above. `git rm -r`. |
| DELETE | `testing/k8s/rbac/e2e-test-runner.yaml` | Replaced by chart template. |
| DELETE | `testing/k8s/rbac/e2e-destructive-runner.yaml` | Replaced by chart template. |
| DELETE | `testing/k8s/rbac/` (dir) | Empty after above. `git rm -r`. |
| MODIFY | `testing/ci/test-integration.sh` | Per AC-8: either remove the `TEST_SUITE=integration` branch entirely or repoint it to `tests/job-e2e.yaml`. If removed, add explicit error with message when `TEST_SUITE` is empty or `integration`. Document the change in a short comment. |
| MODIFY | `.github/workflows/*.yml` (if any references found in task 1 pre-check) | Migrate any raw-manifest `kubectl apply -f testing/k8s/...` to `floe_render_test_job` (requires sourcing common.sh) or inline `helm template`. If a workflow step cannot source common.sh (e.g. actions/run step without bash), use inline `helm template` with the same values. |
| MODIFY | `Makefile` (if references found) | Any target referencing `testing/k8s/jobs/` or `testing/k8s/rbac/` updated to the new dispatch. Most likely `test-integration`, `test-e2e`, `test-e2e-destructive`. |

### Verification at task start

Run `grep -rnE 'testing/k8s/(jobs|rbac)' .github/ Makefile testing/ tests/ scripts/ charts/ docker/ packages/ plugins/ --include='*.sh' --include='*.yaml' --include='*.yml' --include='*.py' --include='Makefile'` and record all hits. Every hit is a deletion or migration target. If a hit is outside this work unit's scope (e.g. in an unrelated script), escalate via AskUserQuestion before proceeding.

### Definition of done (task 3)

- `testing/k8s/jobs/` and `testing/k8s/rbac/` do not exist.
- `grep -rnE 'testing/k8s/(jobs|rbac)'` over the repo returns zero hits.
- `make test-e2e` still succeeds (re-verification from task 2 — must not regress).
- `test-integration.sh` either has no `test-runner.yaml` reference or has been removed entirely (AC-8).

### Commit

`chore(testing): delete raw K8s test manifests; all rendering via chart`

---

## Task 4 — Contract test `test_test_infra_chart_integrity.py`

**Goal**: lock in the new pattern with a pytest contract test that fails fast
on any future drift. Runs in gate-build, offline, fast.

### File change map

| Action | File | Purpose |
|---|---|---|
| CREATE | `tests/contract/test_test_infra_chart_integrity.py` | Contract test implementing the falsifying tests for AC-1, AC-2, AC-3, AC-4, AC-5, AC-7, AC-9. Reuses the `rendered_manifests` fixture pattern from `tests/contract/test_helm_security_contexts.py` — copy the `helm template` invocation idiom, generalize so the fixture can take a values-file + `--set` overrides argument. Tests marked with `@pytest.mark.requirement("test-infra-drift-elimination-AC-{n}")`. |
| MODIFY | `tests/contract/conftest.py` (if it exists, else CREATE) | Factor out the rendered-manifests fixture so both `test_helm_security_contexts.py` and the new file reuse it. Opportunistic — if the refactor touches >30 lines of the security-contexts file, skip and duplicate the fixture instead (scope discipline). |

### Test structure (for tester reference)

```python
# tests/contract/test_test_infra_chart_integrity.py

@pytest.fixture(scope="module")
def tests_enabled_render() -> list[dict]:
    """helm template ... --set tests.enabled=true, parsed."""
    ...

@pytest.fixture(scope="module")
def tests_disabled_render() -> list[dict]:
    """helm template with values.yaml (tests.enabled=false)."""
    ...

@pytest.mark.requirement("test-infra-drift-elimination-AC-1")
def test_every_job_reference_is_chart_rendered(tests_enabled_render): ...

@pytest.mark.requirement("test-infra-drift-elimination-AC-2")
def test_production_render_has_no_test_resources(tests_disabled_render): ...

@pytest.mark.requirement("test-infra-drift-elimination-AC-3")
def test_warehouse_single_source_of_truth(tests_enabled_render): ...

@pytest.mark.requirement("test-infra-drift-elimination-AC-4")
def test_rbac_only_in_chart(tests_enabled_render): ...

@pytest.mark.requirement("test-infra-drift-elimination-AC-5")
def test_shell_scripts_no_hardcoded_identifiers(): ...

@pytest.mark.requirement("test-infra-drift-elimination-AC-7")
def test_raw_manifest_directories_deleted(): ...

@pytest.mark.requirement("test-infra-drift-elimination-AC-9")
def test_fullname_override_still_pins_test_values(): ...
```

Each test function's docstring cites the AC. Each assertion failure message
cites the offending file:line / resource name / values key. No test uses
`pytest.skip` or weakens an assertion on failure (testing-standards).

### Definition of done (task 4)

- `.venv/bin/pytest tests/contract/test_test_infra_chart_integrity.py -v` — all tests pass.
- Requirement traceability check: `.venv/bin/python -m testing.traceability --pattern test-infra-drift-elimination` shows 100% of contract-tier ACs (1,2,3,4,5,7,9) have a covering test.
- `make test-unit` includes the new contract test in its run (tests/contract/ is usually picked up automatically — verify).
- Deliberate regression sanity check: temporarily re-add one literal `floe-platform-polaris` to `testing/ci/test-e2e.sh` and confirm the contract test fails with a useful error; then revert. This is a local-only check, not a committed change.

### Commit

`test(contract): add chart-integrity tripwire for test infrastructure`

---

## Global verification (after all 4 tasks)

1. `make test-unit` — all unit + contract tests pass.
2. `make check` — lint, type, security all green.
3. `make test-e2e` on DevPod + Hetzner — test Job runs to completion; note that actual E2E test pass/fail is not this work unit's scope (existing flakes are tracked separately). AC-10 only requires no `not found` errors at Job creation time.
4. Final grep sweep: `rg 'floe-platform-' testing/ci/` → only `common.sh`. `rg 'testing/k8s/jobs\|testing/k8s/rbac' .` → zero matches.

---

## Risks & mitigations (planning-level)

| Risk | Mitigation |
|---|---|
| Task 1 chart templates break existing `helm-test-unit` suite | Run `make helm-test-unit` after every template edit in task 1. Fix test expectations only when they're genuinely wrong (P32). |
| Task 2 `common.sh` subtle bash behavior (strict-mode, subshells) | Unit test `tests/unit/test_ci_common_sh.py` exercises `set -eu`, subshells, and legacy env var absorb. Written before the sh code per TDD. |
| Task 3 grep sweep misses a reference | Pre-task grep produces an exhaustive list recorded in `decisions.md`. Contract test AC-7 is the backstop — task 3 is not "done" until task 4's AC-7 test (when written in task 4) would pass against task 3's tree. |
| Task 4 contract test too brittle (fails on unrelated chart edits) | Assertions target semantic properties (identifier provenance), not diff equality. Rendered docs are parsed, not compared textually. |
| Chart render depends on a helper that doesn't exist yet | Task 1 adds the two new helpers (`testRunner.saName`, `testRunnerDestructive.saName`) in `_helpers.tpl` before the new templates reference them. Verify with `helm lint` at each step. |
| `fullnameOverride` interaction with Dagster subchart | Dagster subchart has its own fullname scope. Helpers for dagster components (e.g. `floe-platform-dagster-webserver`) need to continue matching — verify by rendering and grepping for all dagster-* service names before/after. Include in task 1 DoD spot check. |

---

## As-Built Notes

### Task 1 — chart templates
- Implemented as planned. `_helpers.tpl` defines `floe-platform.polaris.warehouse`
  reading `.Values.polaris.bootstrap.catalogName`, used by both the Polaris
  bootstrap Job (catalog payload) and the test Jobs (`POLARIS_WAREHOUSE` env).
  This is the structural single-source-of-truth that AC-3 verifies via
  sentinel-flip.
- Discovery: chart drift sneaked in during Task 1 itself —
  `templates/tests/job-e2e-destructive.yaml` was rendering
  `OTEL_SERVICE_NAME=floe-test-runner-destructive`, contradicting the
  `test_observability_manifests.py` class docstring "Both jobs identify as
  the same service for unified trace querying". Caught during Task 3 when the
  unit test was rewired to render the chart instead of reading raw YAML. Fixed
  at the source (chart) per Test Assertion Integrity, not by weakening the
  test. Lesson: the rewired test caught Task 1's regression on first run —
  exactly the behavior the work unit was designed to enable.

### Task 2 — common.sh migration
- Implemented as planned. `FLOE_KIND_CLUSTER` is the canonical name; legacy
  `KIND_CLUSTER` and `KIND_CLUSTER_NAME` are absorbed via fallback chain in
  `common.sh` for env-var compatibility. (See Task 4 deviation re: alias
  variable removal in test-e2e-cluster.sh.)

### Task 3 — delete raw manifests
- Rewired `tests/unit/test_observability_manifests.py` from raw-YAML loading
  to chart-template rendering via subprocess `helm template -s …
  --set tests.enabled=true`. Multi-doc YAML walked with isinstance/cast for
  type-safe filtering. Pattern matches `test_helm_security_contexts.py`.
- Deleted `testing/k8s/jobs/` and `testing/k8s/rbac/` after confirming both
  consumers (test runner script + observability test) were rewired.
- `testing/Dockerfile` comment updated to reference the chart-rendering
  invocation path (no behavioral change).

### Task 4 — contract tripwire
- 11 tests cover AC-1, AC-2, AC-3, AC-4, AC-5 (×4), AC-7 (×2), AC-9. ACs not
  exclusively contract-tier (AC-6 helm unittest, AC-8 RBAC carry-forward) are
  enforced inline within the existing AC-4 `test_test_runner_rbac_rendered_from_chart`
  case (asserts standard runner secrets verb is `get`-only).
- Sentinel-flip pattern for AC-3: re-renders the chart with
  `--set polaris.bootstrap.catalogName=floe-drift-tripwire-zzz` and asserts
  the sentinel appears in **both** the bootstrap Job catalog payload **and**
  the test Job `POLARIS_WAREHOUSE` env value. Any future divergence breaks
  the test.
- **Deviation from plan / discovery**: AC-5 demanded that *every*
  `testing/ci/test-*.sh` script source `common.sh`. The first contract run
  caught three scripts that did not: `test-unit.sh`, `test-contract.sh`,
  `test-e2e-full.sh`. Per Test Assertion Integrity, **fixed the scripts**
  (added `source "${SCRIPT_DIR}/common.sh"`), did not relax the test.
- **Deviation from plan / discovery**: AC-5 also demanded no legacy
  `KIND_CLUSTER` *assignments* outside `common.sh`. `test-e2e-cluster.sh`
  retained a `KIND_CLUSTER="${FLOE_KIND_CLUSTER}"` alias from Task 2 for
  "compatibility". The contract test rejected this. Per the alias chain
  already living in `common.sh` (which absorbs legacy env vars at source),
  the local alias was redundant. Removed the alias and replaced six
  internal `${KIND_CLUSTER}` references with `${FLOE_KIND_CLUSTER}`.
- AC-7 grep search roots: `.github/`, `Makefile`, `testing/`, `tests/`,
  `scripts/`, `charts/`, `docker/`. Self-path excluded so the contract
  test's own string literals don't trigger it.

### Global verification
- Full unit + contract regression: **940 passed, 1 xfailed** in 231s.
- All 11 contract tripwire tests pass.
- Shell `bash -n` syntax check passes for all four modified scripts.
- All four tasks committed atomically with referenced AC IDs in commit
  messages.

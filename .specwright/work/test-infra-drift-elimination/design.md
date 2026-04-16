# Design: Test Infrastructure Drift Elimination

**Work ID**: test-infra-drift-elimination
**Baseline**: `3d89868582bd4286626e640d7b79072394a18a48`
**Research**: `.specwright/research/test-infra-stability-20260407.md`

## Problem Statement

Kubernetes identifiers used by test infrastructure (Service names, Secret names,
ServiceAccount names, Role names, namespace, cluster name, warehouse name) are
hardcoded independently in at least four places: chart templates, raw job
manifests in `testing/k8s/jobs/`, raw RBAC manifests in `testing/k8s/rbac/`,
and shell scripts in `testing/ci/`. Each copy drifts independently. The
`fullnameOverride: floe-platform` pin in `values-test.yaml` is load-bearing and
invisible — it's the only reason the hardcoded strings happen to match the
rendered chart. We have been chasing the symptoms of this drift for weeks.

## Goal

Make drift structurally impossible. Identifiers live in exactly one place (the
chart) and every other consumer — test jobs, RBAC, shell scripts, contract
tests — resolves them from there, at render time or test start time. A pytest
contract test acts as a belt-and-braces tripwire so that any future regression
fails fast, in CI, before a cluster is ever created.

## Non-goals

- Not redesigning the chart itself. `floe-platform.*.fullname` helpers already exist — we use them.
- Not changing what the test jobs do or what services they need.
- Not touching production deploy values (`values.yaml`).
- Not introducing a new testing framework.
- Not rewriting shell scripts beyond unifying duplicated identifier state.

## Approach

### 1. Test jobs become chart templates

Move `testing/k8s/jobs/test-e2e.yaml` and `testing/k8s/jobs/test-e2e-destructive.yaml`
into `charts/floe-platform/templates/tests/` (new subdirectory) as
`job-e2e.yaml` and `job-e2e-destructive.yaml`. Every hardcoded `floe-platform-*`
string is replaced with the matching helper call:

```yaml
# Before (hardcoded):
POSTGRES_HOST: floe-platform-postgresql
MINIO_HOST: floe-platform-minio
POLARIS_URI: "http://floe-platform-polaris:8181/api/catalog"
serviceAccountName: e2e-test-runner
valueFrom: { secretKeyRef: { name: floe-platform-postgresql, key: postgresql-password } }

# After (rendered):
POSTGRES_HOST: {{ printf "%s-postgresql" (include "floe-platform.fullname" .) }}
MINIO_HOST:    {{ printf "%s-minio" (include "floe-platform.fullname" .) }}
POLARIS_URI:   "http://{{ include "floe-platform.polaris.fullname" . }}:8181/api/catalog"
serviceAccountName: {{ include "floe-platform.testRunner.saName" . }}
valueFrom: { secretKeyRef: { name: {{ include "floe-platform.postgresql.secretName" . }}, key: postgresql-password } }
```

Gated by a new `tests:` section in `values-test.yaml`:
```yaml
tests:
  enabled: true        # false in values.yaml (prod) — test manifests do not render
  image:
    repository: floe-test-runner
    tag: latest
    pullPolicy: IfNotPresent
  warehouse: floe-e2e  # single source — consumed by tests and by bootstrap job
  resources: { ... }
  ttlSecondsAfterFinished: 3600
  # polaris/minio/etc. service names are rendered, not configured
```

Every test template is wrapped in `{{- if .Values.tests.enabled }}...{{- end }}`
so production installs render no test resources. The existing
`job-polaris-bootstrap.yaml` catalog name (`.Values.polaris.catalogName`) is
unified with `.Values.tests.warehouse` — one value, one source, referenced by
both bootstrap and test job env.

### 2. RBAC becomes chart templates

`testing/k8s/rbac/e2e-test-runner.yaml` and `e2e-destructive-runner.yaml` move
to `charts/floe-platform/templates/tests/rbac-standard.yaml` and
`rbac-destructive.yaml`. Two new helpers:
- `floe-platform.testRunner.saName` → `{{fullname}}-test-runner`
- `floe-platform.testRunnerDestructive.saName` → `{{fullname}}-test-runner-destructive`

`resourceNames` lists for destructive RBAC (currently `v1..v5`) stay in values
under `tests.destructive.releaseHistoryNames` so they can be extended without
template edits.

### 3. Shell scripts source a single `common.sh`

New file `testing/ci/common.sh`, sourced at the top of every
`testing/ci/test-*.sh`. Exports:

```bash
# Single source of truth for test infrastructure identifiers.
: "${FLOE_RELEASE_NAME:=floe-platform}"
: "${FLOE_NAMESPACE:=floe-test}"
: "${FLOE_KIND_CLUSTER:=${KIND_CLUSTER:-${KIND_CLUSTER_NAME:-floe}}}"   # absorbs both old env var names
: "${FLOE_VALUES_FILE:=charts/floe-platform/values-test.yaml}"
: "${FLOE_CHART_DIR:=charts/floe-platform}"

# Render a single test template from the chart and pipe to kubectl.
floe_render_test_job() {
    local template="$1"    # e.g. tests/job-e2e.yaml
    helm template "${FLOE_RELEASE_NAME}" "${FLOE_CHART_DIR}" \
        -f "${FLOE_VALUES_FILE}" \
        --set tests.enabled=true \
        --namespace "${FLOE_NAMESPACE}" \
        -s "templates/${template}"
}

# Resolve a service name at runtime by reading the rendered chart.
# Used by port-forward setup so there is exactly one place a name is decided.
floe_service_name() {
    local component="$1"   # postgresql|polaris|minio|dagster-webserver|otel|marquez|jaeger-query
    echo "${FLOE_RELEASE_NAME}-${component}"
}

floe_require_cluster() {
    kind get clusters 2>/dev/null | grep -qx "${FLOE_KIND_CLUSTER}" \
        || { echo "ERROR: Kind cluster '${FLOE_KIND_CLUSTER}' not found" >&2; exit 1; }
}
```

Callers are stripped of hardcoded defaults:

```bash
# test-integration.sh (before)
KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-floe}"
JOB_MANIFEST="testing/k8s/jobs/test-e2e.yaml"
kubectl apply -f "$JOB_MANIFEST"

# test-integration.sh (after)
source "$(dirname "$0")/common.sh"
floe_require_cluster
floe_render_test_job "tests/job-e2e.yaml" | kubectl apply -f -
```

Port-forwards in `test-e2e.sh` call `floe_service_name polaris` etc. instead
of hardcoding `floe-platform-polaris`. The `fullnameOverride: floe-platform` in
`values-test.yaml` stays (it pins the release-name-independent prefix) but is
no longer invisibly load-bearing — `floe_service_name` documents and respects it.

### 4. Delete dead code

- `testing/k8s/jobs/test-runner.yaml` — DELETE. Three stale Jobs, no live
  consumer once step 3 repoints `test-integration.sh`.
- `TEST_SUITE=integration` code path in `test-integration.sh` — delete the
  branch (integration tests run via `test-e2e.sh` in the existing `e2e` suite,
  or via the new chart-rendered path).
- `testing/k8s/jobs/` directory — becomes empty. Delete it. All job manifests
  now live in the chart.
- `testing/k8s/rbac/` directory — becomes empty. Delete it.
- Hardcoded `POLARIS_HOST`/`MINIO_HOST`/`DAGSTER_HOST` env-var workaround list
  in test jobs (~10 env vars per job) — these existed because "Helm names != short names".
  Once Jobs are rendered from the chart using `floe-platform.*.fullname`
  helpers, the "short name" problem disappears and the override list can shrink
  to only the ones the test code genuinely still needs. Verify and trim.

### 5. Contract test (tripwire)

New file: `tests/contract/test_test_infra_chart_integrity.py`. Reuses the
`rendered_manifests` fixture pattern from `tests/contract/test_helm_security_contexts.py`.

Asserts, against the output of `helm template charts/floe-platform -f values-test.yaml --set tests.enabled=true`:

1. **No raw test manifests survive**: `testing/k8s/jobs/` and `testing/k8s/rbac/`
   do not exist (or are empty). If a future contributor adds a raw manifest
   back, the test fails.
2. **Every test Job references only chart-rendered names**: for each Job under
   `templates/tests/`, every `serviceAccountName`, every `secretRef.name`,
   every `configMapRef.name`, every env value that looks like a hostname
   (regex match against `{fullname}-*`) must match a rendered resource in the
   same render.
3. **`tests.enabled=false` renders zero test resources**: second render with
   `tests.enabled=false` produces no resources with `test-type` label or
   `tests/` template path. Proves the feature flag is clean.
4. **Single warehouse source**: `.Values.tests.warehouse` and
   `.Values.polaris.catalogName` (or whichever the bootstrap job reads) resolve
   to the same string in the rendered output. Prevents the Apr 5 `floe-e2e`/
   `floe-demo` flip-flop from happening again.
5. **Shell scripts don't shadow chart identifiers**: grep
   `testing/ci/test-*.sh` (excluding `common.sh`) for literal `floe-platform-`
   — expected count: zero. Any match fails the test with the offending
   file:line.

The test runs in `gate-build` alongside `test_helm_security_contexts.py`.
It's offline (no cluster), fast (<5s), and doesn't depend on any service.

## Blast Radius

**Touched (modify or create)**:
- `charts/floe-platform/templates/tests/job-e2e.yaml` (NEW, from existing raw file)
- `charts/floe-platform/templates/tests/job-e2e-destructive.yaml` (NEW, from existing raw file)
- `charts/floe-platform/templates/tests/rbac-standard.yaml` (NEW, from existing raw file)
- `charts/floe-platform/templates/tests/rbac-destructive.yaml` (NEW, from existing raw file)
- `charts/floe-platform/templates/_helpers.tpl` (add test-runner SA helpers)
- `charts/floe-platform/values.yaml` (add `tests.enabled: false` default + schema)
- `charts/floe-platform/values-test.yaml` (add `tests.enabled: true`, `tests.warehouse`, migrate hardcoded test settings)
- `charts/floe-platform/templates/job-polaris-bootstrap.yaml` (unify `catalogName` with `tests.warehouse`)
- `testing/ci/common.sh` (NEW)
- `testing/ci/test-integration.sh` (source common.sh, remove TEST_SUITE=integration branch, use `floe_render_test_job`)
- `testing/ci/test-e2e-cluster.sh` (source common.sh, replace `KIND_CLUSTER` default, use `floe_render_test_job`)
- `testing/ci/test-e2e.sh` (source common.sh, replace hardcoded service names with `floe_service_name` calls)
- `tests/contract/test_test_infra_chart_integrity.py` (NEW)
- `Makefile` (any targets invoking the deleted scripts; touch only what breaks)

**Deleted**:
- `testing/k8s/jobs/test-runner.yaml`
- `testing/k8s/jobs/test-e2e.yaml` (replaced by chart template)
- `testing/k8s/jobs/test-e2e-destructive.yaml` (replaced by chart template)
- `testing/k8s/rbac/e2e-test-runner.yaml` (replaced by chart template)
- `testing/k8s/rbac/e2e-destructive-runner.yaml` (replaced by chart template)
- `testing/k8s/jobs/` directory (empty)
- `testing/k8s/rbac/` directory (empty)

**Failure-propagation scope**:
- **Local**: chart templating, test manifest rendering, test shell scripts.
  Breaks here are caught by `helm lint`, `helm template`, `helm-unittest`,
  and the new contract test. All run in gate-build.
- **Adjacent**: `make test-e2e`, `make test-e2e-destructive`, `make test-integration`,
  GitHub Actions workflows that invoke the scripts. Breaks here fail CI loudly,
  not silently.
- **Systemic**: NONE. Production deploy path (`values.yaml`, `helm install
  floe-platform`) is unchanged when `tests.enabled=false` — the test templates
  simply don't render. Contract AC validates this explicitly.

**Not touched**:
- Python test code under `tests/unit/`, `tests/integration/`, `tests/e2e/` —
  they consume env vars, not K8s identifiers.
- `CompiledArtifacts` schema and the cross-package contract.
- Source code of `floe-core`, plugins, or any Layer 1/2/3/4 component.
- `docker/dagster-demo/Dockerfile`, demo products, `demo/manifest.yaml`.
- Memory / auto-memory / specwright state.
- DevPod workspace configuration.

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Chart template complexity grows too far | Low | Medium | Test templates are gated by `tests.enabled` — invisible to prod readers of the chart. Same pattern Bitnami, Prometheus, Grafana charts use. |
| `helm template -s` behaviour changes across Helm versions | Low | Low | `-s` has been stable since Helm 3.5. CI pins helm version. |
| First run after merge fails because live Kind release is out of sync | Medium | Medium | `common.sh` does a version check: `helm list -n ${FLOE_NAMESPACE} -o json` → compare chart version to `charts/floe-platform/Chart.yaml`. Mismatch → actionable error telling user to `make install-platform`. |
| Contract test becomes a maintenance tax when adding new test jobs | Low | Low | The test walks templates generically — adding a new `templates/tests/job-foo.yaml` requires no test edit, it's picked up automatically. Only fails when a *raw* manifest is reintroduced. |
| `fullnameOverride` removed from values-test.yaml by a future edit | Low | High | Contract AC: assert the override is still set (or, stronger, assert rendered Services match `${FLOE_RELEASE_NAME}-*`). |
| Deleting `testing/k8s/` breaks a GitHub Action that apply-s it directly | Low | High | Grep workflows + scripts for `testing/k8s/` references before delete. Part of the implementation. |

## Why not the alternatives

**Alternative A: Keep raw manifests, add a contract test only.** Rejected.
Contract test catches drift after it happens, doesn't prevent it. We still
maintain the same identifier in four places; the contract test just turns
"silent rot" into "noisy rot". Does not address the user's direct question
("why are naming conventions hardcoded?"). Does not eliminate the
`fullnameOverride` land mine.

**Alternative B: Keep raw manifests, generate them from the chart at build
time via `make generate-test-manifests`.** Rejected. Adds a generated file
problem (two sources of truth — template + committed output — with a
generation step enforcing consistency). Classic anti-pattern: stale generated
files go unnoticed in PRs. Chart templates *are* the generator; the output is
ephemeral and passed directly to `kubectl apply -f -`, never committed.

**Alternative C: conftest `--combine` + Rego instead of pytest.** Worth
discussing as the contract test's implementation, but secondary to the
primary fix. Rejected as primary because `test_helm_security_contexts.py`
already establishes the pytest-based chart contract pattern in the repo;
introducing Rego is a second cognitive load for no capability the pytest
approach lacks at this scale. Revisit if contract count grows past ~5.

**Alternative D: `helm upgrade --set tests.enabled=true` (lifecycle-managed)
instead of `helm template | kubectl apply -f -` (ephemeral).** Rejected. Tests
should not mutate the release revision history. Every test run would bump
the Helm release version, pollute `helm history`, and risk partial rollback
on failure. `helm template` + `kubectl apply -f -` gives us the same
rendering guarantees with no release-state side effects. (This matches
how Bitnami test hooks work.)

## Decomposition hint for sw-plan

This is one coherent change. The four steps are tightly coupled — you cannot
delete `test-runner.yaml` before repointing `test-integration.sh`, cannot
repoint the shell scripts before the chart templates exist, cannot add the
contract test before the raw manifests are gone. Suggest a single work unit
with four sequential tasks:

1. Chart templates + helpers + values (tests.enabled flag, tests.warehouse unification)
2. `testing/ci/common.sh` + shell script migration
3. Delete dead code (`test-runner.yaml`, `testing/k8s/jobs/`, `testing/k8s/rbac/`, `TEST_SUITE=integration` branch)
4. Contract test `test_test_infra_chart_integrity.py` + gate wiring

Each task ends in a running `make test-e2e` on DevPod + Hetzner, so RED/GREEN
loops are meaningful. Task 4 is the tripwire that locks the new pattern in.

## Acceptance signal (for sw-plan to turn into ACs)

- `rg 'floe-platform-' testing/ci/*.sh` returns only `common.sh`.
- `rg 'floe-platform-' testing/k8s/` returns zero matches (directory gone).
- `helm template charts/floe-platform -f values-test.yaml` renders test jobs with names that match `helm template charts/floe-platform -f values-test.yaml --show-only templates/service-polaris.yaml` output — i.e. same fullname prefix.
- `helm template charts/floe-platform` (without `--set tests.enabled=true`) renders zero documents whose metadata.name starts with `*-test-*` and zero documents under `templates/tests/`.
- `make test-e2e` on DevPod + Hetzner reaches the test-run phase without any "service not found" / "secret not found" / "serviceaccount not found" errors from the Job manifests.
- New contract test `tests/contract/test_test_infra_chart_integrity.py` passes in gate-build.
- `testing/k8s/jobs/test-runner.yaml` no longer exists.
- Changing `.Values.polaris.catalogName` (or equivalent single-source key) from `floe-e2e` to any other string results in both the bootstrap job and the test job env agreeing on the new value in one diff — no second edit required.

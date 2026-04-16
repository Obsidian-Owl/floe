# Research Brief: Test Infrastructure Stability

**Topic ID**: test-infra-stability
**Date**: 2026-04-07
**Status**: Active
**Confidence**: HIGH across all three tracks

## Triggering Questions

1. "Polaris `floe-e2e` warehouse is never created anywhere — this was working before — what's changed?"
2. "Integration test runner is stale (blocked before running any tests) — how is it stale? It was only JUST created?"
3. Agreement with recommendation: create a work unit whose deliverable is a contract test for the test infrastructure itself.

---

## Track 1 — Polaris `floe-e2e` warehouse creation

**Finding**: The bootstrap job EXISTS and has existed since Feb. The problem is naming churn and test fragility, not a regression in creation logic.

**Evidence**:
- `charts/floe-platform/templates/job-polaris-bootstrap.yaml` lines 203-269 — Helm
  post-install/post-upgrade hook that calls `POST /api/management/v1/catalogs`,
  treats 409 as idempotent success, runs as init-container chain
  (`wait-for-minio` → `wait-for-polaris` → bootstrap).
- `charts/floe-platform/values-test.yaml:67` — `catalogName: "floe-e2e"` ✓
- PyIceberg terminology note: the client-side `warehouse=` parameter maps 1:1 to
  the Polaris `catalog-name`. There is no separate "warehouse" object to create.
  Ref: `plugins/floe-orchestrator-dagster/tests/integration/conftest.py:324`.
- Git archaeology (key commits on `job-polaris-bootstrap.yaml` / catalog name):
  - `6fcdfa5` — initial bootstrap job
  - `789ff99` — in-cluster test infra, catalog name pinned
  - `f1f1e25` (Apr 5) — rename to `floe-demo`
  - `6d36b46` (Apr 5) — revert back to `floe-e2e`
- The live Hetzner cluster was deployed mid-churn; the running Helm release is
  not necessarily at HEAD. Test code hardcodes `floe-e2e` via
  `POLARIS_WAREHOUSE` env fallback — tests pass only when release + env +
  values.yaml all agree.

**Root cause**: not a regression in *creation*, but drift between the Helm release
state, `values-test.yaml` at deployment time, and test env var defaults. There is
no contract binding these three.

**Correction to user's assumption**: "this was working before" — the bootstrap
path has never been broken; it has been fragile. Tests relying on side-effects
of a specific Helm release version will fail whenever that version and test
env expectations diverge.

**Confidence**: HIGH — sources: chart templates, values files, conftest, git log.

---

## Track 2 — `test-runner.yaml` staleness

**Finding**: The file is LIVE (used by default `TEST_SUITE=integration`), last
substantively edited **2026-02-06** (commit `4df87c3`), and was **deliberately
skipped** by the March migration commit that updated its siblings.

**Evidence**:
- File: `testing/k8s/jobs/test-runner.yaml` (3 Jobs: `floe-test-runner`,
  `floe-test-unit`, `floe-test-integration`).
- Invocation: `testing/ci/test-integration.sh:37` applies this file directly
  when `TEST_SUITE=integration` (the default path).
- Stale references inside the file:
  - Lines 28, 175 — `serviceAccountName: dagster` (no such SA in the deployed
    namespace; e2e siblings use `e2e-test-runner`).
  - Lines 53, 61, 66, 207, 215, 220 — `postgres-secret`, `minio-secret`
    (Helm-rendered names are `floe-platform-postgresql`, `floe-platform-minio`).
  - Lines 44-47, 70-72 — Services `postgres`, `minio`, `polaris`
    (Helm-rendered names are `floe-platform-*`).
- Sibling migration **commit `128381e`** (2026-03-29,
  "fix(ci): align Job secrets and service names with Helm chart") updated
  `test-e2e.yaml` and `test-e2e-destructive.yaml` — and **skipped**
  `test-runner.yaml`. No commit since has touched the missing fields.

**Correction to user's assumption**: "it was only JUST created" — the file is
from Feb 6, 2026 (~2 months old). The perception of newness comes from the fact
it only started *failing visibly* once the rest of the platform was Helm-aligned
in late March and the e2e path became the only one that worked. The integration
path quietly rotted in place.

**Why it keeps happening**: three independent sources of truth for the same
identifiers (SA names, Secret names, Service names):
1. `charts/floe-platform/templates/*.yaml` (Helm-rendered)
2. `testing/k8s/jobs/*.yaml` (raw manifests applied by shell scripts)
3. `testing/ci/*.sh` (env vars: `KIND_CLUSTER` vs `KIND_CLUSTER_NAME`, etc.)

Changes in (1) have no enforcement against (2) or (3). helm-unittest, ruff,
mypy, gate-build all stay green because they don't cross that boundary.

**Confidence**: HIGH — sources: file contents, git log, migration commit diff,
shell script contents.

---

## Track 3 — External patterns for a test-infra contract test

**Goal**: pick a tool/pattern that can assert "every `serviceAccountName` in
`testing/k8s/jobs/*.yaml` is rendered by the chart" (and equivalents for
Secrets, Services, ConfigMaps) offline, in CI, before any cluster exists.

**Candidates evaluated**:

| Tool | Cross-file/referential? | Offline? | Verdict |
|---|---|---|---|
| **conftest + Rego `--combine`** | ✅ yes | ✅ yes | **Recommended primary** |
| **pytest-helm-templates** | ✅ yes (Python loop) | ✅ yes | **Recommended fallback / complement** |
| helm-unittest | ❌ per-template | ✅ | Insufficient (already used) |
| kubeconform / kubeval | ❌ schema only | ✅ | Insufficient |
| datree / polaris / kube-score | ❌ per-resource | ✅ | Insufficient |
| Kyverno CLI (offline) | ❌ partial | ✅ | Can't resolve chart refs |
| kubectl `--dry-run=server` | Partial | ❌ needs cluster | Wrong layer |
| helm test hooks | ✅ runtime | ❌ needs deploy | Too late; floe already has one |

**Recommended shape (conftest)**:
```bash
helm template charts/floe-platform -f charts/floe-platform/values-test.yaml \
  > /tmp/chart-rendered.yaml
conftest test /tmp/chart-rendered.yaml testing/k8s/jobs/*.yaml \
  testing/k8s/rbac/*.yaml --combine --policy testing/k8s/policies/
```
Rego policy iterates the combined array, builds sets of chart-rendered
(ServiceAccount|Secret|Service|ConfigMap) names keyed by namespace, then denies
any `batch/v1 Job` whose `serviceAccountName` / `envFrom[].secretRef.name` /
volume Secret refs / Service hostnames (via env) are not in the rendered set.

**Recommended shape (pytest-helm-templates)** — Pythonic alternative that fits
floe's existing `tests/contract/` style (same directory as
`test_helm_security_contexts.py`):
```python
def test_job_manifests_only_reference_chart_rendered_names(rendered_chart):
    chart_sa_names = {...}  # walk rendered_chart
    job_docs = yaml.safe_load_all(open("testing/k8s/jobs/test-runner.yaml"))
    for doc in job_docs:
        assert doc["spec"]["template"]["spec"]["serviceAccountName"] in chart_sa_names
```

**Sibling prior art in-repo**: `tests/contract/test_helm_security_contexts.py`
already shells out to `helm template` and walks rendered docs. A new contract
test file can re-use the `rendered_manifests` fixture pattern directly — no new
tooling required for the Python path.

**Confidence**: HIGH — sources: conftest.dev docs, helm-unittest README,
pytest-helm-templates PyPI, kubeconform/kubeval/kube-score/datree/polaris docs,
Kyverno CLI offline limitations.

---

## Open Questions (for sw-design)

1. **conftest vs pytest**: conftest is the stronger fit for Rego-style set
   algebra and plays nicely with CI; pytest reuses existing fixtures and keeps
   the test next to `test_helm_security_contexts.py`. sw-design should pick one
   as primary (the other can be a later follow-up).
2. **Scope of the contract**: minimum viable is SA + Secret + Service
   cross-reference. Should it also cover env-var-embedded hostnames
   (`POLARIS_HOST`, `MINIO_HOST`, `DAGSTER_HOST`) which are themselves drift
   sources?
3. **Single source of truth for cluster env vars**: `KIND_CLUSTER` vs
   `KIND_CLUSTER_NAME` across `test-integration.sh` and `test-e2e-cluster.sh` is
   a separate drift axis. Worth including in the same work unit or a sibling?
4. **test-runner.yaml vs test-e2e.yaml convergence**: should the stale
   `test-runner.yaml` be deleted and integration-tier tests promoted to use the
   `e2e-test-runner` SA + Helm-aligned names, collapsing the two paths? This
   changes scope from "add a contract test" to "contract test + migrate +
   delete dead file".

---

## Consumer Guidance (sw-design)

- **Treat Track 1 and Track 2 as symptoms, not targets.** The target is the
  *class* of bug: manifest/chart/script drift with no enforcement. Fixing
  `test-runner.yaml`'s three stale names without adding the contract test
  guarantees we're back here in another 6 weeks.
- **The contract test is the only deliverable that changes the failure mode
  from "chase for weeks" to "chase for minutes".** All other fixes are cleanup.
- **Scope recommendation for the work unit**:
  1. Contract test (conftest OR pytest) that fails on any unknown reference.
  2. Fix `test-runner.yaml` stale refs (driven by the now-failing contract test).
  3. Unify `KIND_CLUSTER*` env var between the two shell scripts.
  4. Optional stretch: delete `test-runner.yaml` in favour of promoting
     integration tier onto the `e2e-test-runner` SA path.

---

## Meta

- **Research briefs at cap**: `.specwright/research/` holds 10 briefs before
  this one (writing this brings it to 11). Protocol asks me to warn and suggest
  cleanup — oldest candidates for removal: `alpha-remaining-bugs-20260328.md`,
  `dagster-materialization-failure-20260328.md`, `helm-v4-upgrade-20260328.md`,
  `tunnel-stability-20260329.md`, `e2e-ci-resilience-20260329.md`,
  `service-mesh-evaluation-20260330.md` — all >7 days old and referenced by
  already-shipped work.
- **Stage boundary**: sw-research stops here. Next step: user invokes
  `/sw-design` to turn this brief into a work unit.

# Context: test-infra-drift-elimination

**Baseline commit**: `3d89868582bd4286626e640d7b79072394a18a48` (origin/main)
**Research input**: `.specwright/research/test-infra-stability-20260407.md`

## The problem in one line

Four independent files maintain their own copy of the same Kubernetes identifiers. When one changes, the others rot silently until a test run lights it up, and we've been chasing that pattern for weeks.

## The four drift sources

| Source | What it hardcodes | Authority |
|---|---|---|
| `charts/floe-platform/templates/*.yaml` | Service/Secret/ConfigMap/SA names, all rendered through `floe-platform.fullname` helpers | **Canonical** (the chart is the deploy) |
| `charts/floe-platform/values-test.yaml` | `fullnameOverride: floe-platform` — the *only* reason hardcoded strings elsewhere happen to work | Test-specific pin |
| `testing/k8s/jobs/test-e2e.yaml`, `test-e2e-destructive.yaml` | ~20 literal `floe-platform-*` strings, SA name `e2e-test-runner`, namespace `floe-test`, Secret keys | Drifts independently |
| `testing/k8s/jobs/test-runner.yaml` | Stale refs (`dagster` SA, `postgres-secret`, `minio-secret`, bare `postgres`/`minio`/`polaris` Services) — **dead Feb 6 file, never cleaned up** | Should have been deleted |
| `testing/k8s/rbac/e2e-test-runner.yaml` | SA name, Role name, RoleBinding name, namespace | Drifts independently |
| `testing/ci/test-integration.sh`, `test-e2e-cluster.sh`, `test-e2e.sh` | Cluster name (`KIND_CLUSTER` vs `KIND_CLUSTER_NAME` — two different env var names for the same thing), image name, namespace, ~6 port-forward service names | Drifts independently |
| Test runner Python (`ServiceEndpoint` host list baked into Job env) | ~10 `POLARIS_HOST`, `MINIO_HOST`, `DAGSTER_HOST` env vars carrying the "Helm name != short name" workaround | Lives in Job yaml |

## Why the hardcoding "works" today

`values-test.yaml:37` pins `fullnameOverride: floe-platform`. This makes every rendered name begin with the literal string `floe-platform-`, which happens to match the hardcoded strings in the test jobs. The override is load-bearing and undocumented as such. Remove it or rename the release and every raw test manifest breaks simultaneously.

## Why this keeps biting us

`.specwright/research/test-infra-stability-20260407.md` Track 2 found:
- `test-runner.yaml` was last touched 2026-02-06 (`4df87c3`)
- Sibling migration commit `128381e` (2026-03-29, "align Job secrets and service names with Helm chart") updated `test-e2e.yaml` and `test-e2e-destructive.yaml` — and skipped `test-runner.yaml`
- Today's commit `bc3506d` (test-observability) created new `test-e2e.yaml` / `test-e2e-destructive.yaml` content but still left `test-runner.yaml` in place and still invoked by `test-integration.sh:37` for default `TEST_SUITE=integration`
- No gate detects the drift. helm-unittest, ruff, mypy, contract-tests-for-security all pass because none of them cross the chart↔raw-manifest boundary

Track 1 (`floe-e2e` warehouse) is the same pattern one layer up: chart values (`catalogName: floe-e2e`), test env default (`POLARIS_WAREHOUSE=floe-e2e`), and bootstrap job logic all encode the same name independently. Apr 5 had two commits flipping between `floe-e2e` and `floe-demo` — the live cluster caught the middle state.

## What the chart already provides (and we're not using)

`charts/floe-platform/templates/_helpers.tpl` defines:
- `floe-platform.fullname` — canonical prefix
- `floe-platform.polaris.fullname` → `{{fullname}}-polaris`
- `floe-platform.otel.fullname` → `{{fullname}}-otel`
- `floe-platform.marquez.fullname` → `{{fullname}}-marquez`
- `floe-platform.postgresql.secretName` → `{{fullname}}-postgresql`
- `floe-platform.serviceAccountName`
- `floe-platform.environmentNamespace`

These are the primitives we should be rendering test manifests through. Instead the test YAMLs bypass them.

## External research (Track 3 of the brief)

- **conftest `--combine` + Rego**: can assert cross-file referential integrity offline. Good for a tripwire.
- **pytest-helm-templates**: same capability, fits floe's existing `tests/contract/` style, reuses the `rendered_manifests` fixture pattern from `test_helm_security_contexts.py`.
- **helm-unittest / kubeconform / datree**: per-file only. Insufficient.

## Constraints inherited from the constitution and CLAUDE.md

- **S5 K8s-Native Testing**: all tests run in Kind cluster. The chart must remain the deploy unit.
- **S4 Contracts**: `CompiledArtifacts` is the sole *cross-package* contract. This design adds an internal *infrastructure* contract (chart ↔ test manifests) — scoped to `charts/floe-platform` and `testing/`, does not touch package boundaries.
- **Quality escalation**: any choice between valid approaches goes to user. Choices needing escalation at plan time are flagged in `assumptions.md`.
- **Tests FAIL never skip**: the contract test is an unconditional assertion, not a warning.
- **Pre-alpha, no backcompat**: the Feb 6 `test-runner.yaml` can be deleted outright. No migration path needed.

## Files that will be touched

See `design.md` § Blast Radius.

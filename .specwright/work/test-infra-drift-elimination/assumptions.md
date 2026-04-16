# Assumptions

## A1 — `values-test.yaml` `fullnameOverride: floe-platform` is intentional, not a vestige

**Type**: clarify + technical
**Status**: ACCEPTED (auto, Type 2 reversible)
**Why**: The line is present and every hardcoded test identifier depends on it. The design keeps it and surfaces it through `floe_service_name`. If it was unintentional, removing it still works — the rendered names would start with the release name instead, and `floe_service_name` would still resolve correctly because it uses `${FLOE_RELEASE_NAME}`.

## A2 — All test Jobs can be gated by a single `.Values.tests.enabled` flag without breaking `helm lint`

**Type**: technical
**Status**: ACCEPTED (auto, Type 2)
**Why**: Standard Helm pattern. Bitnami, Prometheus, Grafana, Jaeger charts all do this. `helm lint` passes on fully-gated templates.

## A3 — `helm template -s templates/tests/job-e2e.yaml` works in the pinned Helm version

**Type**: technical
**Status**: ACCEPTED (auto, Type 2)
**Why**: `-s` (show-only) is stable since Helm 3.5; repo uses Helm 3.14 (see P68 in MEMORY).

## A4 — The e2e test code does not depend on literal string `floe-platform-*` in its own logic

**Type**: clarify
**Status**: VERIFIED (grep) — tests read hostnames from env vars, not from literals. A one-off sanity grep in task 2 will confirm before deleting the override env var list.
**Why**: `test-e2e.yaml` sets `POLARIS_HOST`, `MINIO_HOST` etc. precisely because the test code wants env vars. The env vars will continue to be set — the change is that their *values* come from chart helpers instead of hardcoded strings.

## A5 — `testing/k8s/jobs/test-runner.yaml` has no production consumer

**Type**: clarify
**Status**: VERIFIED — only `test-integration.sh:37` references it, and only on the `TEST_SUITE=integration` default branch which is being removed in task 3.
**Why**: `rg 'test-runner\.yaml' --type-not md` returns only that one line.

## A6 — GitHub Actions workflows either don't reference `testing/k8s/` directly, or the references can be migrated without a breaking change to CI semantics

**Type**: reference + external
**Status**: TO VERIFY at task 3 start (grep `.github/workflows/` for `testing/k8s/`). If any workflow applies raw manifests directly, it migrates to `helm template ... | kubectl apply -f -` as part of task 3.
**Why**: The research brief focused on shell scripts, not workflows. Cheap to verify, blocking if missed.

## A7 — `fullnameOverride` can be preserved without breaking chart tests

**Type**: technical
**Status**: ACCEPTED (auto, Type 2)
**Why**: The override already exists and `helm unittest` already passes on `values-test.yaml`. No change proposed.

## A8 — Contract test (`pytest`) is the right tool vs conftest/Rego

**Type**: clarify
**Status**: ACCEPTED with WARN (recorded in design.md Alternatives). The repo already has a pytest-based chart contract test pattern in `tests/contract/test_helm_security_contexts.py`. Using the same pattern keeps reviewer cognitive load low and shares the `rendered_manifests` fixture approach. Revisit if contract count >5.
**Why**: Reversible — swapping pytest for conftest later is a mechanical rewrite.

## A9 — `tests.warehouse` unification with `polaris.catalogName` won't break the existing Polaris bootstrap job

**Type**: technical
**Status**: TO VERIFY at task 1 start. Read `charts/floe-platform/templates/job-polaris-bootstrap.yaml` to confirm which values key the bootstrap reads, then decide whether to alias or replace. If aliasing is required for any reason, task 1 keeps both keys with a chart-level assertion that they match. If not, task 1 makes `polaris.catalogName` the canonical key and `tests.warehouse` a read-only reference.
**Why**: This is the fix for the Apr 5 `floe-e2e`/`floe-demo` flip-flop. Must not regress it.

## A10 — No cross-package or cross-plugin code needs changes

**Type**: clarify
**Status**: ACCEPTED (auto, Type 2)
**Why**: The design only touches `charts/`, `testing/`, and `tests/contract/`. No Layer 1-4 code (floe-core, plugins, demos) is affected. `CompiledArtifacts` and all package contracts are untouched.

---

## Open (blocking if unresolved at plan gate)

None of the assumptions above are Type 1 structural overrides. All Type 2 items are auto-accepted. A6 and A9 are verification-at-task-start items, which is the standard pattern for "cheap to check when we get there" — they don't block the design gate.

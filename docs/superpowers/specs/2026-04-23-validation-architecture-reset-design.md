# Validation Architecture Reset Design

Status: Proposed
Date: 2026-04-23
Author: Codex

## Summary

floe's current validation harness conflates distinct execution contexts into one "standard E2E" lane. The in-cluster least-privilege runner is currently expected to validate deployed product behavior, perform Helm-admin deployment workflows, inspect repo-local metadata such as `.gitignore` and `.vuln-ignore`, and tolerate localhost assumptions that only make sense on a developer machine.

That is why the latest failures look unrelated while sharing one root cause. RBAC-denied Helm tests, missing `.git` metadata, `127.0.0.1` service assumptions, and stale Polaris/Iceberg state all appear as "standard E2E" failures even though they belong to different validation classes.

This design resets validation architecture around explicit execution lanes. Each lane gets one purpose, one execution context, and one allowed assumption set.

## Problem Statement

The latest validated failures cluster into five categories:

- Execution-context mismatch:
  - `tests/e2e/test_runtime_loader_e2e.py` assumes `http://127.0.0.1:3000` from inside the cluster.
- Repo-checkout assumptions inside the test-runner image:
  - `tests/e2e/test_governance.py::test_pip_audit_clean` expects `.vuln-ignore`.
  - `tests/e2e/test_profile_isolation.py` expects `.gitignore` and a real git checkout.
- Admin/Helm workflow assumptions inside a least-privilege runner:
  - `tests/e2e/test_helm_workflow.py` needs Helm release-secret access in its own namespace and currently fails under the standard in-cluster RBAC profile.
- Product-state/idempotency weakness:
  - `tests/e2e/test_dbt_lifecycle_e2e.py`
  - `tests/e2e/test_data_pipeline.py`
  - `tests/e2e/test_compile_deploy_materialize_e2e.py`
  still fail on reruns because Polaris/Iceberg state is not reset deterministically enough.
- Actual product gap:
  - `tests/e2e/test_observability.py::TestObservability::test_openlineage_four_emission_points`
    still indicates missing valid `parentRun` lineage semantics.

The first four are validation-architecture failures. The last one is a real product defect and should remain visible after the harness is fixed.

## Goals

- Separate validation by execution context so failures classify cleanly.
- Keep least-privilege in-cluster validation focused on deployed product behavior.
- Move repo-aware and admin/deployment workflows out of the standard product lane.
- Make Polaris/Iceberg reset behavior explicit and deterministic before dbt seed/run flows.
- Preserve visibility for real product defects instead of burying them under harness noise.

## Non-Goals

- Rewrite every E2E file into a new directory structure in one pass.
- Replace all existing shell orchestration at once.
- Hide true product bugs behind retries or broad skips.
- Revisit the broader contract-layer hard-reset design in this plan.

## Decision

Adopt four validation lanes:

1. `contract`
2. `bootstrap`
3. `platform_blackbox`
4. `developer_workflow`

`destructive` remains a gated follow-on lane rather than part of the standard pass.

The immediate implementation uses pytest markers plus runner split. It does not require a full filesystem re-home of all tests on day one.

## Lane Definitions

### 1. `contract`

Purpose:

- Validate schemas, wiring, marker discipline, chart/test-runner contracts, and structural invariants.

Execution context:

- Host pytest.

Allowed assumptions:

- Source checkout is present.
- Files can be read directly.

Disallowed assumptions:

- Live cluster state.
- Deployed services.

### 2. `bootstrap`

Purpose:

- Validate admin/deployment workflows and environment readiness.
- Answer "can an operator bring this platform up correctly?"

Execution context:

- Host-side pytest with real `kubectl` and `helm`.
- Full kubeconfig available.

Allowed assumptions:

- Helm CLI access.
- Namespace creation/deletion.
- Helm release inspection.
- Repo checkout is present.

Disallowed assumptions:

- Least-privilege in-cluster RBAC.
- `localhost` inside a K8s pod.

Representative tests:

- `tests/e2e/test_helm_workflow.py`
- `tests/e2e/test_platform_bootstrap.py`
- `tests/e2e/test_platform_deployment_e2e.py`

### 3. `platform_blackbox`

Purpose:

- Validate deployed platform behavior from an in-cluster consumer perspective.
- This is the actual standard product lane.

Execution context:

- In-cluster pytest Job using the standard least-privilege ServiceAccount.

Allowed assumptions:

- K8s DNS and service environment variables.
- Real platform services already deployed.
- No direct repo metadata required.

Disallowed assumptions:

- `.git`, `.gitignore`, `.vuln-ignore`
- Helm admin workflows
- `127.0.0.1`/port-forward access patterns

Representative tests:

- `tests/e2e/test_compile_deploy_materialize_e2e.py`
- `tests/e2e/test_data_pipeline.py`
- `tests/e2e/test_dbt_lifecycle_e2e.py`
- `tests/e2e/test_observability.py`
- `tests/e2e/test_runtime_loader_e2e.py` after service-contract correction

### 4. `developer_workflow`

Purpose:

- Validate repo-aware developer behavior.
- Answer "does this checkout behave correctly for local tooling and source-controlled workflow contracts?"

Execution context:

- Host-side pytest on a normal checkout.

Allowed assumptions:

- `.git`
- `.gitignore`
- `.vuln-ignore`
- local source tree inspection

Disallowed assumptions:

- In-cluster service DNS as the only execution mode.
- Least-privilege runtime SA context.

Representative tests:

- `tests/e2e/test_profile_isolation.py`
- `tests/e2e/test_governance.py::test_pip_audit_clean`
- `tests/e2e/test_runtime_loader_e2e.py::test_thin_definitions_are_deployed`

### 5. `destructive`

Purpose:

- Validate upgrades, pod kills, and other intentionally disruptive workflows.

Execution context:

- Separate in-cluster privileged Job after non-destructive product validation passes.

Allowed assumptions:

- Elevated RBAC compared with the standard runner.

Disallowed assumptions:

- Being mixed into the same status signal as the standard product lane.

## Classification Rules

The immediate classification strategy is marker-first:

- Explicit markers for outlier files and functions.
- Any `tests/e2e` item with no explicit lane marker defaults to `platform_blackbox`.
- Existing `destructive` marker keeps precedence over all other lane defaults.

This avoids a large file move while still making the execution boundary explicit.

## Reset And Idempotency Contract

The product failures around dbt seed/run are not solved by lane split alone. The platform lane also needs a stronger reset contract:

- Before `dbt seed`:
  - purge the raw namespace with a fresh Polaris catalog client
  - verify the namespace is actually empty or absent before continuing
- Before `dbt run`:
  - purge the model namespace with the same verification
- After shared module-scoped fixtures:
  - purge both namespaces again
- On reset failure:
  - fail early with a reset-specific error instead of letting dbt fail with stale metadata symptoms

Current silent best-effort cleanup is too weak. Reset must become an asserted precondition, not a courtesy.

## Runner Architecture

The full validation orchestration becomes:

1. Host `bootstrap`
2. In-cluster `platform_blackbox`
3. Host `developer_workflow`
4. In-cluster `destructive` only if `bootstrap` and `platform_blackbox` pass

This preserves one decisive product signal while still surfacing repo/admin failures separately.

## Why This Is Sufficient

More brainstorming is not required before acting because the current failure set already maps cleanly onto these boundaries:

- RBAC failures are from running admin workflows in a least-privilege product lane.
- repo-metadata failures are from running checkout-aware tests inside an image that is not a checkout.
- localhost failures are from mixed execution assumptions.
- dbt/Polaris rerun failures are from weak reset semantics.

Those are specific design faults, not canaries of an unknown larger collapse.

## Deferred Work

The following stays intentionally separate from the validation-architecture reset:

- OpenLineage `parentRun`/`runId` correctness
- broader contract-layer generation work
- full filesystem re-home of all tests into new directories

Those can follow once the validation lanes produce clean, trustworthy signals.

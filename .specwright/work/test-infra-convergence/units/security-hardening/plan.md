# Plan: Security Hardening + Containerized Tools

## Task Breakdown

### Task 1: YAML anchors and Dagster security context propagation

**AC covered**: AC-1

Add YAML anchors for `podSecurityContext` and `containerSecurityContext` at the top
of `values.yaml`. Wire to all Dagster components using verified key paths.

**File change map**:
- `charts/floe-platform/values.yaml` — add anchors, add dagster subchart mappings

### Task 2: OTel, Jaeger, and MinIO security context propagation

**AC covered**: AC-2, AC-3

Wire security contexts to remaining subcharts. Preserve Jaeger's existing UID 10001.
Map MinIO to Bitnami schema with `enabled: true`.

**File change map**:
- `charts/floe-platform/values.yaml` — add otel, jaeger, minio subchart mappings

### Task 3: Security context contract test

**AC covered**: AC-4

Create a contract test that renders `helm template` and validates security contexts
on all pod specs. Exclude Marquez explicitly.

**File change map**:
- `tests/contract/test_helm_security_contexts.py` — new file

### Task 4: Containerized validation tools

**AC covered**: AC-5, AC-6, AC-7

Add Makefile targets for kubeconform, kubesec, and helm-unittest using pinned Docker
images. No host installation required.

**File change map**:
- `Makefile` — add `helm-validate`, `helm-security`, `helm-test-unit` targets

### Task 5: RBAC least-privilege for test runners

**AC covered**: AC-8, AC-9

Restrict secrets access on both runner Roles. Standard runner drops `list`/`watch`
verbs (only `get` remains). Destructive runner adds `resourceNames` scoping on
`update`/`delete` verbs (K8s does not support `resourceNames` with `create`, so
document that gap inline). Add a contract test that parses the RBAC manifests and
asserts the constraints.

**File change map**:
- `testing/k8s/rbac/e2e-test-runner.yaml` — remove `list`/`watch` from secrets rule
- `testing/k8s/rbac/e2e-destructive-runner.yaml` — split secrets rules, add `resourceNames` for update/delete
- `tests/contract/test_rbac_least_privilege.py` — new contract test

### Task 6: Marquez gap documentation

**AC covered**: AC-10

Document the Marquez root-user gap in AUDIT.md with upstream reference.

**File change map**:
- `.specwright/AUDIT.md` — add finding (or create if missing)

## Architecture Decisions

- YAML anchors are used within a single `values.yaml` document (not across files).
  The `values-dev.yaml` overlay inherits from base — security contexts don't need
  to be redeclared in overlays unless overriding.
- Jaeger's UID 10001 is preserved (not overridden to 1000) because Jaeger's image
  is built for that UID. Only capability drops are added.
- Contract test uses `subprocess.run(["helm", "template", ...])` to render the chart,
  then parses the multi-document YAML output. This is a structural test, not a live
  cluster test — it belongs in `tests/contract/`.

## Dependencies

- Independent of Units 1 and 2. Can be built in parallel.
- The contract test requires Helm CLI on the host (or containerized Helm). Since the
  test runner image includes Helm, this is available in-cluster. For host execution,
  Helm is already a development dependency.

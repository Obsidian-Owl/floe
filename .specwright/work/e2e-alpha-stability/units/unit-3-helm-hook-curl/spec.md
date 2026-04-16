# Spec: Unit 3 — Helm Hook curl Replacement

## Acceptance Criteria

### AC-1: Hook uses `curlimages/curl` image

The pre-upgrade hook Job container uses `curlimages/curl:8.5.0` by default (configurable via `postgresql.preUpgradeCleanup.image.repository` and `.tag`).

**How to verify**: `helm template` with default values shows `curlimages/curl:8.5.0` as the Job container image. No reference to `bitnami/kubectl` in any template.

### AC-2: Script checks StatefulSet existence via K8s REST API

The hook script performs a GET request to the K8s API to check if the PostgreSQL StatefulSet exists before attempting deletion. Returns cleanly if StatefulSet is absent (HTTP 404).

**How to verify**: `helm template` output contains curl GET to `/apis/apps/v1/namespaces/.../statefulsets/...` with HTTP code check.

### AC-3: Script deletes StatefulSet with orphan propagation via REST API

On existence (HTTP 200), the script sends a DELETE request with `{"propagationPolicy":"Orphan"}` body. This preserves pods and PVCs while removing the StatefulSet controller.

**How to verify**: Template output contains `curl -X DELETE` with `propagationPolicy.*Orphan` in the request body.

### AC-4: Script uses ServiceAccount token for authentication

The script reads the token from `/var/run/secrets/kubernetes.io/serviceaccount/token` and the CA cert from `/var/run/secrets/kubernetes.io/serviceaccount/ca.crt`. Uses `Authorization: Bearer` header.

**How to verify**: Template output references both paths and the Bearer authorization header.

### AC-5: Script handles unexpected HTTP codes

If the GET request returns anything other than 200 or 404, the script exits with a non-zero code and an error message to stderr.

**How to verify**: Template output contains an else branch with `exit 1` and `>&2` error output.

### AC-6: Security context unchanged

The Job container retains all existing security hardening:
- `runAsNonRoot: true`
- `runAsUser: 1000`
- `readOnlyRootFilesystem: true`
- `allowPrivilegeEscalation: false`
- `capabilities.drop: [ALL]`
- Resource limits: `cpu: 100m`, `memory: 64Mi`

**How to verify**: Helm unit test asserts all security context fields match (existing test AC-6 continues to pass).

### AC-7: RBAC unchanged

The Role, RoleBinding, and ServiceAccount resources are identical to the previous implementation. Verbs remain `["get", "list", "watch", "delete"]` on `statefulsets` in the `apps` API group.

**How to verify**: Existing RBAC helm unit tests (AC-4) continue to pass without modification.

### AC-8: Helm unit tests updated for curl script

The AC-7 test (script content validation) uses `matchRegex` patterns that verify:
- The target StatefulSet name contains `floe-platform-postgresql`
- The script references `propagationPolicy` with `Orphan`

**How to verify**: `helm unittest charts/floe-platform` passes.

### AC-9: `bitnami/kubectl` removed from Kind pre-loads

`testing/k8s/setup-cluster.sh` no longer pre-loads `bitnami/kubectl:1.32.0`. `curlimages/curl:8.5.0` remains pre-loaded.

**How to verify**: `grep -c 'bitnami/kubectl' testing/k8s/setup-cluster.sh` returns 0.

### AC-10: values.yaml defaults updated

`postgresql.preUpgradeCleanup.image.repository` defaults to `curlimages/curl` and `.tag` defaults to `8.5.0`.

**How to verify**: Read `values.yaml` preUpgradeCleanup section.

### AC-11: POSIX shell compatibility

The script uses `/bin/sh` and POSIX-compatible constructs only (`[ ]` not `[[ ]]`). A comment documents this constraint.

**How to verify**: Script uses `[ ]` for conditionals. Comment present explaining POSIX constraint.

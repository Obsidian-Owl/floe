# Context: Unit 3 — Helm Hook curl Replacement

## Scope

Replace `bitnami/kubectl:1.32.0` with `curlimages/curl:8.5.0` in the pre-upgrade hook. Use K8s REST API instead of kubectl CLI for StatefulSet deletion.

## Files to modify

| File | Change |
|------|--------|
| `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml` | Rewrite shell script from kubectl to curl |
| `charts/floe-platform/values.yaml` | Change default image from `bitnami/kubectl:1.32.0` to `curlimages/curl:8.5.0` |
| `charts/floe-platform/tests/hook-pre-upgrade_test.yaml` | Update AC-7 regex patterns for curl script |
| `testing/k8s/setup-cluster.sh` | Remove `bitnami/kubectl:1.32.0` pre-load |

## Key references

- Current template: `pre-upgrade-statefulset-cleanup.yaml` (122 lines)
- Current values: `values.yaml:434-441` — `image.repository: bitnami/kubectl`, `image.tag: "1.32.0"`
- Kind pre-loads: `setup-cluster.sh:130-144` — curl already at line 135, kubectl at ~line 140
- RBAC: Role grants `["get", "list", "watch", "delete"]` on `statefulsets` — unchanged
- K8s API: `DELETE /apis/apps/v1/namespaces/{ns}/statefulsets/{name}` with body `{"propagationPolicy":"Orphan"}`
- ServiceAccount token: `/var/run/secrets/kubernetes.io/serviceaccount/token`
- CA cert: `/var/run/secrets/kubernetes.io/serviceaccount/ca.crt`

## Shell script constraints (architect WARN-1)

- Script runs under `/bin/sh` (busybox on Alpine), NOT bash
- Use `[ ]` not `[[ ]]` — add comment: `# POSIX sh — [[ ]] not available in busybox`
- Errors to stderr (`>&2`) per code-quality rules
- `set -e` for fail-fast

## Helm unit test patterns (P49)

- `matchRegex` for script content validation
- Test must verify: StatefulSet name (`floe-platform-postgresql`), propagation policy (`Orphan`)
- Document indexes: 0=ServiceAccount, 1=Role, 2=RoleBinding, 3=Job

## E2E tests fixed

- #5: `test_helm_upgrade_succeeds`
- #6: `test_helm_history_shows_revisions`
- #7: `test_helm_release_deployed`

# Plan: Unit 3 — Helm Hook curl Replacement

## Tasks

1. Update `values.yaml` — change default image to `curlimages/curl:8.5.0`
2. Rewrite `pre-upgrade-statefulset-cleanup.yaml` — replace kubectl script with curl + K8s REST API
3. Update `hook-pre-upgrade_test.yaml` — modify AC-7 regex patterns for curl script
4. Update `setup-cluster.sh` — remove `bitnami/kubectl:1.32.0` pre-load
5. Run `helm unittest charts/floe-platform` to verify all hook tests pass

## File change map

| File | Action | Lines |
|------|--------|-------|
| `charts/floe-platform/values.yaml` | EDIT — change image repo + tag | lines 440-441 |
| `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml` | EDIT — rewrite command script | lines 93-106 |
| `charts/floe-platform/tests/hook-pre-upgrade_test.yaml` | EDIT — update AC-7 matchRegex patterns | lines 176-184 |
| `testing/k8s/setup-cluster.sh` | EDIT — remove bitnami/kubectl pre-load line | ~line 140 |

## Script structure

```
set -e
# Read SA token + CA cert
# GET /apis/apps/v1/namespaces/{ns}/statefulsets/{name} -> HTTP code
# if 200 -> DELETE with propagationPolicy:Orphan
# elif 404 -> log "not found", exit 0
# else -> error, exit 1
```

## Unchanged resources

- ServiceAccount (documentIndex 0) — no changes
- Role (documentIndex 1) — no changes
- RoleBinding (documentIndex 2) — no changes
- Job metadata, annotations, security context, resources — no changes

## Verification

```bash
# Helm unit tests
helm unittest charts/floe-platform

# Template render check
helm template test charts/floe-platform \
  --set postgresql.enabled=true \
  --set postgresql.preUpgradeCleanup.enabled=true \
  -s templates/hooks/pre-upgrade-statefulset-cleanup.yaml

# Grep checks
grep -c 'bitnami/kubectl' testing/k8s/setup-cluster.sh  # expect: 0
grep 'curlimages/curl' charts/floe-platform/values.yaml  # expect: match
```

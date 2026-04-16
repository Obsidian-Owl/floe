# Gate: Wiring
**Status**: WARN
**Timestamp**: 2026-03-26T15:15:00Z

## Scope
Changed files: `docker/dagster-demo/Dockerfile`, `charts/floe-platform/values.yaml`, `charts/floe-platform/values-test.yaml`, `Makefile`

## Findings

### WARN-1: kubectl tag mismatch between values files and setup-cluster.sh
- **File**: `testing/k8s/setup-cluster.sh:139-141`
- **Severity**: WARN
- **Detail**: Values files now use `bitnami/kubectl:1.32.0` but `setup-cluster.sh` still pre-loads `bitnami/kubectl:1.32` (which doesn't exist on Docker Hub). The Kind pre-load fails with "manifest not found", meaning the Helm hook will attempt an internet pull at deploy time.
- **Fix**: Update `setup-cluster.sh` lines 139-141 to use `1.32.0` to match values files

### Investigated — FALSE POSITIVE: dagster-k8s version variable
- **Claim**: dagster-k8s should use `DAGSTER_VERSION` (1.x) not `DAGSTER_POSTGRES_VERSION` (0.x)
- **Reality**: Dagster companion packages (dagster-postgres, dagster-k8s, dagster-graphql) use `0.(Y+16).Z` versioning for core dagster `1.Y.Z`. So dagster-k8s `0.28.14` IS the correct version for dagster `1.12.14`. Build succeeded, pip check passed, import works.
- **Evidence**: The pyproject.toml constraint `dagster-k8s>=1.10.0` appears misleading but is a pre-existing concern not introduced by this PR.

## Cross-file wiring
- Dockerfile pip install: consistent with existing pattern
- Helm values tag change: properly propagated to both values.yaml and values-test.yaml
- Makefile target: correctly uses existing `testing/ci/test-e2e.sh`, follows DooD pattern (P57)
- Smoke test: includes `import dagster_k8s`

## Verdict
One real WARN: setup-cluster.sh tag mismatch needs fixing.

# Context: Flux v2 GitOps Implementation

**Baseline commit**: 412b1c4 (origin/main)

## Research Brief

Full research at `.specwright/research/flux-implementation-20260415.md` (4 tracks, 5 resolved questions).

## Key Files

### Test Infrastructure (Phase 1 targets)
- `testing/k8s/setup-cluster.sh` — Kind cluster creation + Helm deployment (365 lines)
- `testing/k8s/kind-config.yaml` — Kind v1.29.0 config with port mappings, 10.244.0.0/16 pod CIDR
- `testing/ci/common.sh` — Shared identifiers: `FLOE_RELEASE_NAME=floe-platform`, `FLOE_NAMESPACE=floe-test`
- `testing/ci/test-e2e-cluster.sh` — In-cluster test runner (271 lines)
- `testing/fixtures/helm.py` — `recover_stuck_helm_release()` utility (174 lines)
- `tests/e2e/conftest.py` — Session fixtures: `helm_release_health()` (lines 264-307), infra smoke check (227-260)

### CLI (Phase 2 target)
- `packages/floe-core/src/floe_core/cli/platform/compile.py` — `floe platform compile` (376 lines)
  - Output: `artifacts.to_json_file(output)` at line 173-175
  - `--output` flag at line 73, default `target/compiled_artifacts.json`
- `packages/floe-core/src/floe_core/cli/platform/deploy.py` — `floe platform deploy` (271 lines)
  - Wraps `helm upgrade --install` via subprocess

### Helm Chart
- `charts/floe-platform/Chart.yaml` — Version 0.1.0, K8s >=1.28.0-0
- `charts/floe-platform/values-test.yaml` — Test values (13,969 bytes)
- Dependencies: dagster@1.12.17, otel-collector@0.108.0, minio@14.8.5, jaeger@3.4.1

### Existing Flux Examples (need update)
- `charts/examples/flux/helmrelease.yaml` — Uses v2beta2 API (DEPRECATED)
- `charts/examples/flux/kustomization.yaml` — Multi-env pattern (v1 API, current)

### GitHub Actions
- `.github/workflows/helm-release.yaml` — Already publishes to GHCR OCI + GitHub Pages
- `.github/workflows/helm-ci.yaml` — Lint + validation on chart changes
- `.github/workflows/release.yml` — Full release on v*.*.* tags

### Compiled Artifacts
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` — 827 lines
  - `to_json_file()` (lines 695-713)
  - `to_yaml_file()` (lines 715-740)
  - Default output: `target/compiled_artifacts.json`

## Gotchas

### Flux-specific
- HelmRelease cannot point to local filesystem paths — must use GitRepository or OCI
- `strategy: uninstall` performs uninstall-between-each-retry (not "rollback N times then uninstall")
- `remediateLastFailure` defaults to `true` when `retries > 0`
- SemVer `>=1.0.0` does NOT match pre-releases — use `>=1.0.0-0`
- `flux suspend` via CLI is not persisted to Git — parent Kustomization may overwrite
- Flux auto-adopts existing Helm releases by matching release name + namespace

### Kind/DevPod
- Docker images must be `--platform linux/amd64` (Mac arm64 → Hetzner amd64)
- `kind load docker-image` works with Flux — Flux has no image-pulling logic of its own
- Charts setting `imagePullPolicy: IfNotPresent` will use locally-loaded images

### Current pain points (from AUDIT.md)
- DX-003: Silent failure in resource creation — resources report success when subsystems absent
- DX-004: PyIceberg S3 endpoint corruption through 6-layer config merge
- DBT-001: Credentials hardcoded in 31 files
- CON-001: `try_create_*` functions have 3 different failure semantics

### Helm release state
- Currently stuck at revision 54 with status `failed`
- Blocks all 306 E2E tests
- Test runner SA lacks `clusterroles` RBAC for `helm rollback`
- Flux remediation would have auto-healed this via `strategy: uninstall`

## Audit Findings Relevance

The AUDIT.md BLOCKER findings (DX-001 through DX-004, CON-001, DBT-001, SCP-001) are
orthogonal to this design. Flux addresses infrastructure-level Helm management, not
application-level architecture issues. However, Flux's auto-healing directly resolves
the cascading failure pattern that makes these audit findings harder to fix (you can't
debug application code when the infrastructure is stuck).

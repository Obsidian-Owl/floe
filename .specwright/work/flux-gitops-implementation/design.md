# Design: Flux v2 GitOps Implementation for Floe

**Work ID**: flux-gitops-implementation
**Status**: Draft
**Date**: 2026-04-15

## Problem Statement

Floe's test infrastructure suffers from cascading failures when Helm releases
enter stuck states (`failed`, `pending-upgrade`). A single stuck release blocks
all 306+ E2E tests. The current mitigation — a session-scoped pytest fixture
that detects and rolls back stuck releases — is reactive, fragile, and requires
RBAC permissions the test runner SA doesn't always have.

Simultaneously, Floe users deploying to production have no official GitOps path.
The `floe deploy` command wraps `helm upgrade --install` — imperative, not
auditable, and disconnected from version control.

## Solution Overview

Implement Flux v2 in two phases:

1. **Phase 1 — Test Infrastructure**: Install Flux controllers in the Kind cluster.
   Manage the `floe-platform` Helm release via a HelmRelease CRD with `strategy: uninstall`
   remediation. This auto-heals stuck releases without pytest fixtures or manual intervention.

2. **Phase 2 — User-Facing GitOps**: Provide a forkable `floe-gitops-template` repo,
   update `charts/examples/flux/` to GA API versions, add `floe compile --output-format=configmap`
   CLI option, publish charts to GHCR via OCI with Cosign signing, and document SOPS secrets.

## Approach

### Phase 1: Flux for Test Infrastructure (Kind Cluster)

**Install Flux controllers (minimal)**:
```bash
# Pin version for reproducibility (P53)
FLUX_VERSION="2.5.1"
flux install --version="${FLUX_VERSION}" --components="source-controller,helm-controller"
```
Resource footprint: ~150m CPU / 128Mi memory (requests). Under reconciliation load,
controllers may use more — monitor with `kubectl top pods -n flux-system`.

**Pre-Flux cleanup (one-time for existing clusters)**:
The current `floe-platform` release is stuck at revision 54, status `failed`. Flux cannot
cleanly adopt a release in `failed` state with no previous `deployed` revision (fluxcd/flux2#4614).
Before applying the HelmRelease CRD, existing clusters must run:
```bash
helm uninstall floe-platform -n floe-test --wait || true
```
This is a destructive one-time migration step. New clusters (created by `setup-cluster.sh`)
do not need this — Flux performs the initial install.

**HelmRelease for floe-platform**:
```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: floe-platform
  namespace: floe-test
spec:
  interval: 30m          # Long interval for dev — reconcile on-demand with flux reconcile
  chart:
    spec:
      chart: ./charts/floe-platform
      sourceRef:
        kind: GitRepository
        name: floe
  values:
    # Inline: test-environment values (merged from values-test.yaml)
  install:
    remediation:
      retries: 3
    timeout: 10m
  upgrade:
    remediation:
      retries: 3
      strategy: uninstall    # Full uninstall between retries
      remediateLastFailure: true
    cleanupOnFail: true
    timeout: 10m
```

**HelmRelease for floe-jobs-test** (WARN-1 resolution):
The `floe-jobs-test` release is also managed by Flux to prevent split-brain:
```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: floe-jobs-test
  namespace: floe-test
spec:
  interval: 30m
  dependsOn:
    - name: floe-platform    # Jobs depend on platform being ready
  chart:
    spec:
      chart: ./charts/floe-jobs
      sourceRef:
        kind: GitRepository
        name: floe
  valuesFrom:
    - kind: ConfigMap
      name: floe-jobs-test-values
  install:
    remediation:
      retries: 2
  upgrade:
    remediation:
      retries: 2
      strategy: uninstall
```

**GitRepository source** (Kind dev):
```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: floe
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/floe-platform/floe
  ref:
    branch: main
```
Note: source-controller must have network access to GitHub from inside the Kind cluster.
For offline/firewalled environments, use `flux suspend` + direct Helm instead. See
"Dev Iteration Workflow" section below.

**Integration with setup-cluster.sh** (BLOCK-2 resolution):

Add Flux installation step between Kind cluster creation and Helm deployment:
1. `kind create cluster` (existing)
2. Install `flux` CLI if not present (version-pinned)
3. `flux install --version=${FLUX_VERSION} --components="source-controller,helm-controller"`
4. Apply GitRepository + HelmRelease CRDs via `kubectl apply -f`
5. Wait for HelmRelease readiness:

```bash
# Synchronous readiness wait (replaces helm --wait)
# kubectl wait supports custom resource conditions
info "Waiting for Flux to reconcile floe-platform (up to 15m)..."
if ! kubectl wait helmrelease/floe-platform \
    -n floe-test \
    --for=condition=Ready \
    --timeout=900s 2>/dev/null; then
    # Detailed error on failure
    error "HelmRelease reconciliation failed:"
    flux get helmrelease floe-platform -n floe-test 2>/dev/null || true
    kubectl get events --sort-by='.lastTimestamp' -n floe-test | tail -10
    exit 1
fi
info "floe-platform reconciled successfully"

# Then wait for floe-jobs-test (depends on floe-platform)
kubectl wait helmrelease/floe-jobs-test \
    -n floe-test \
    --for=condition=Ready \
    --timeout=600s
```

Timeout rationale: first reconciliation = source clone (~30s) + chart dependency build
(~60s) + install (~3-5m) + pod readiness (~2-3m) = ~7m. 15m provides 2x margin. The
`interval: 30m` is for steady-state; initial reconciliation happens immediately.

**Flux CLI prerequisite** (WARN-4 resolution):
Add to `check_prerequisites()` in setup-cluster.sh:
```bash
if ! command -v flux &>/dev/null; then
    info "Installing flux CLI v${FLUX_VERSION}..."
    curl -s https://fluxcd.io/install.sh | FLUX_VERSION="${FLUX_VERSION}" bash
fi
```

**Flux suspend/resume for destructive tests** (BLOCK-3 resolution):

`test_helm_upgrade_e2e.py` directly calls `helm upgrade`, conflicting with Flux management.
Solution: a crash-safe pytest fixture that suspends Flux before destructive tests:

```python
@pytest.fixture(scope="module")
def flux_suspended(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Suspend Flux HelmRelease management for destructive tests.
    
    Crash-safe: registers a finalizer that always resumes Flux,
    even if the test crashes or is interrupted.
    """
    release = "floe-platform"
    namespace = os.environ.get("FLOE_NAMESPACE", "floe-test")
    
    # Check if Flux is managing this release
    result = subprocess.run(
        ["kubectl", "get", "helmrelease", release, "-n", namespace],
        capture_output=True, text=True
    )
    flux_active = result.returncode == 0
    
    if flux_active:
        subprocess.run(
            ["flux", "suspend", "helmrelease", release, "-n", namespace],
            check=True
        )
    
    def _resume() -> None:
        if flux_active:
            subprocess.run(
                ["flux", "resume", "helmrelease", release, "-n", namespace],
                check=False  # Best-effort on cleanup
            )
    
    # Register finalizer BEFORE yielding — runs even on crash
    request.addfinalizer(_resume)
    yield
```

Tests using this fixture:
- `test_helm_upgrade_e2e.py` — uses `flux_suspended` fixture
- Other destructive tests that directly manipulate the Helm release

Additionally, the `helm_release_health()` session fixture checks for suspended HelmReleases
at session start and resumes them (handles the case where a previous test session crashed):
```python
# At session start, before health check:
result = subprocess.run(
    ["kubectl", "get", "helmrelease", release, "-n", ns,
     "-o", "jsonpath={.spec.suspend}"],
    capture_output=True, text=True
)
if result.stdout.strip() == "true":
    logger.warning("HelmRelease was suspended (previous crash?), resuming...")
    subprocess.run(["flux", "resume", "helmrelease", release, "-n", ns])
```

**`testing/fixtures/helm.py` simplification**:
`recover_stuck_helm_release()` remains available for environments without Flux (e.g., CI
with ephemeral clusters that use direct Helm). The Kind dev path delegates recovery to Flux.

**Dev Iteration Workflow** (WARN-3 resolution):

For rapid local development (edit chart → test → fix → test):
```bash
# Option A: Flux-managed (changes must be committed)
# 1. Edit chart
# 2. git commit
# 3. flux reconcile source git floe       # Force source refresh
# 4. flux reconcile helmrelease floe-platform  # Force reconcile
# 5. Test

# Option B: Direct Helm (suspend Flux, work freely)
# 1. flux suspend helmrelease floe-platform
# 2. Edit chart, helm upgrade --install directly (current workflow)
# 3. Test
# 4. When done: git commit, flux resume helmrelease floe-platform
```

Option A is the GitOps-native path. Option B is the escape hatch for rapid iteration.
Both are documented in `testing/k8s/README.md`.

**PVC behavior during uninstall** (WARN-5 resolution):
`strategy: uninstall` deletes the Helm release but PVCs created by StatefulSet
`volumeClaimTemplates` are NOT Helm-owned — they survive uninstall. For the test
environment, `values-test.yaml` sets `postgresql.persistence.enabled=false` (emptyDir),
so no persistent data is at risk. If persistence is ever enabled for debugging, PVC
data will survive the uninstall+reinstall cycle because StatefulSet PVCs are not managed
by Helm. However, Helm-owned PVCs (created directly in chart templates) would be deleted.
This is acceptable for test infrastructure.

### Phase 2: User-Facing GitOps

**2a. Update `charts/examples/flux/`**:
- `helmrelease.yaml`: v2beta2 → v2 API, add `strategy: uninstall`, add OCI chart source
- `kustomization.yaml`: Add ConfigMap valuesFrom pattern, SOPS decryption example
- New: `ocirepository.yaml` with Cosign verification

**2b. `floe compile --output-format=configmap`**:
Add `--output-format` flag to `floe platform compile` command:
- `json` (default, existing): writes `compiled_artifacts.json`
- `yaml`: writes `compiled_artifacts.yaml` (existing)
- `configmap`: writes a Kubernetes ConfigMap YAML wrapping the compiled values

The ConfigMap output integrates with Flux's `valuesFrom: kind: ConfigMap` pattern:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: floe-compiled-values
data:
  values.yaml: |
    # Compiled platform values from floe compile
    dagster:
      enabled: true
    polaris:
      enabled: true
    # ... full compiled values
```

**2c. OCI chart publishing**:
The existing `helm-release.yaml` workflow already publishes to GHCR OCI. Add:
- Cosign keyless signing step (Sigstore OIDC)
- SemVer pre-release support (`>=1.0.0-0`)

**2d. Template repository**:
Create `floe-gitops-template` as a GitHub template repository:
```
clusters/
  dev/floe-platform/
    kustomization.yaml
    helmrelease.yaml
    values.yaml
  staging/floe-platform/
    kustomization.yaml
    values-override.yaml
  production/floe-platform/
    kustomization.yaml
    values-override.yaml
infrastructure/
  flux-system/
  sources/ocirepository.yaml
  secrets/sops-example.yaml
scripts/setup.sh
```

**2e. Secrets documentation**:
Document SOPS (Age) as the default secrets approach. ESO as enterprise option.
Add `secrets.provider` field to manifest schema for future integration.

## Integration Points

### CLI (`packages/floe-core/src/floe_core/cli/platform/`)
- `compile.py`: Add `--output-format=configmap` flag
- `deploy.py`: No changes in Phase 1. Future Phase 3: `--gitops` flag

### Helm Chart (`charts/floe-platform/`)
- No chart changes required. Flux is transparent to chart authors.
- HelmRelease CRD manages the same chart with same values.

### Test Infrastructure (`testing/`)
- `testing/k8s/setup-cluster.sh`: Add Flux install step
- `testing/ci/common.sh`: New helpers for Flux status checks
- `testing/fixtures/helm.py`: Simplify recovery (Flux handles it)
- `tests/e2e/conftest.py`: Simplify `helm_release_health()` to status check

### GitHub Actions (`.github/workflows/`)
- `helm-release.yaml`: Add Cosign signing step
- No new workflows for Flux itself (Flux runs in-cluster)

### Examples (`charts/examples/flux/`)
- Full rewrite: v2beta2 → v2, add OCI pattern, add SOPS example

## Risk Assessment

### R1: Flux controller resource pressure in Kind (LOW)
~150m CPU / 128Mi is modest. Kind on Hetzner has adequate resources.
Mitigation: Monitor via `kubectl top pods -n flux-system`.

### R2: Git commit requirement for dev iteration (MEDIUM)
Flux requires changes committed to Git before reconciliation. For rapid local dev,
this slows iteration vs. direct `helm upgrade`.
Mitigation: Document the `flux suspend` / direct Helm escape hatch for rapid iteration.
In-cluster tests already commit changes (they're submitted as Jobs).

### R3: Flux suspend/resume interaction with tests (LOW)
E2E tests may need to suspend Flux during destructive upgrade tests.
Mitigation: `flux suspend helmrelease` CLI command. Test teardown resumes.

### R4: Pre-release SemVer matching (LOW)
`>=1.0.0` does NOT match `1.0.0-rc.1`. Must use `>=1.0.0-0`.
Mitigation: Document in examples and template repo.

### R5: Complexity for new contributors (MEDIUM)
Adding Flux to the dev setup increases onboarding complexity.
Mitigation: `make kind-up` abstracts Flux installation. Data engineers never touch Flux.

## Blast Radius

### Modules/Files Touched

| Path | Change | Propagation |
|------|--------|-------------|
| `testing/k8s/setup-cluster.sh` | Add Flux install, replace Helm deploy with CRDs, add readiness wait | Adjacent — CI depends on this script |
| `testing/ci/common.sh` | Add Flux status helpers | Local — utility functions |
| `testing/fixtures/helm.py` | Add `flux_suspended` fixture, simplify recovery | Adjacent — E2E conftest uses this |
| `tests/e2e/conftest.py` | Add suspended-check at session start, simplify health fixture | Local — session fixture |
| `tests/e2e/test_helm_upgrade_e2e.py` | Add `flux_suspended` fixture dependency | Local — single test file |
| `charts/examples/flux/*` | Rewrite examples (v2beta2 → v2, add OCI, add SOPS) | Local — examples, not chart code |
| `charts/floe-platform/flux/` | NEW: HelmRelease + GitRepository manifests for Kind | Local — consumed by setup-cluster.sh |
| `packages/floe-core/src/floe_core/cli/platform/compile.py` | Add output format flag | Local — CLI only |
| `.github/workflows/helm-release.yaml` | Add Cosign step | Local — release workflow |

### What This Design Does NOT Change

- **Helm chart templates**: Zero changes to `charts/floe-platform/templates/`
- **Plugin system**: No plugin changes, no new plugin types
- **CompiledArtifacts schema**: No schema changes (configmap output is a wrapper)
- **Production `floe deploy`**: Imperative path remains the default
- **CI test execution**: In-cluster test runner (`test-e2e-cluster.sh`) unchanged
- **Package dependencies**: No new Python dependencies

### Operational Model Changes (honest assessment)

- **Developer mental model**: Debugging shifts from `helm status/history` to `flux get helmrelease` + `helm status`. Both are needed because Flux wraps Helm.
- **New CLI dependency**: `flux` CLI must be installed on dev machines and CI runners (version-pinned)
- **Flux controller monitoring**: If helm-controller crashes, auto-healing stops silently. Health check at session start mitigates but doesn't fully solve. Recommend adding `kubectl get pods -n flux-system` to infrastructure smoke check.

## Alternatives Considered

### ArgoCD instead of Flux
ArgoCD's `selfHeal` has a known bug (issue #18442) where healing is silently skipped
when a previous sync against the same commit SHA failed. This makes ArgoCD unsuitable
for the auto-recovery use case that drives Phase 1. Flux's remediation model is
purpose-built for this scenario.

### Custom operator for Helm recovery
Building a custom controller to watch Helm releases and recover stuck ones. Rejected:
Flux already does this with battle-tested code. Adding a custom operator adds maintenance
burden for no additional value.

### Keep reactive pytest fixture
The current `helm_release_health()` fixture could be enhanced with more RBAC permissions.
Rejected: This is reactive (detects after failure), not proactive (prevents failure).
It also runs once per test session, not continuously.

## WARNs from Architect Review

### WARN-1: `floe-jobs-test` release not accounted for → RESOLVED
Added HelmRelease for `floe-jobs-test` with `dependsOn: floe-platform`. Both releases
now managed by Flux.

### WARN-2: GitRepository requires network access to GitHub
Source-controller must reach github.com from inside Kind. For offline/firewalled
environments, use `flux suspend` + direct Helm. Documented in Dev Iteration Workflow.

### WARN-3: Dev iteration friction → RESOLVED
Two documented paths: Option A (commit + `flux reconcile`) and Option B (suspend +
direct Helm). Option B preserves current workflow exactly.

### WARN-4: `flux` CLI is undeclared prerequisite → RESOLVED
Added to `check_prerequisites()` with auto-install and version pinning.

### WARN-5: `strategy: uninstall` and PVC behavior → RESOLVED
Documented: StatefulSet PVCs survive uninstall (not Helm-owned). Test environment
uses `emptyDir` (persistence disabled). No data loss risk for test infra.

### WARN-6: Flux issue #2299 — orphaned resources after uninstall
Known issue. For the test infrastructure use case, orphaned resources would be caught
by the subsequent reinstall failing. The `cleanupOnFail: true` setting helps. If
orphaned resources persist, `setup-cluster.sh` can add a namespace cleanup step.

### WARN-7: Flux controller monitoring
Added `kubectl get pods -n flux-system` to infrastructure smoke check.
`helm_release_health()` session fixture also checks for Flux controller readiness.

### Simplicity Assessment Response
The architect raised a valid question: why not `--atomic` + enhanced fixture + RBAC?
Answer: Phase 1 (test infra) and Phase 2 (user GitOps) are coupled. We will ship Flux
examples and OCI publishing to users — testing Flux on our own infra first is essential
dogfooding. If Phase 2 were not planned, `--atomic` would be sufficient for Phase 1.
But since we're building GitOps support for users, we must validate it ourselves first.
Additionally, `--atomic` only handles upgrade failures; it does not auto-heal releases
that enter `failed` state from external causes (K8s node restart, OOM kill, etc.).

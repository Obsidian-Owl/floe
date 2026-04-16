# Plan: flux-kind-install

**Unit**: 1 of 3
**Parent**: flux-gitops-implementation

## Task Breakdown

### Task 1: Add FLUX_VERSION to common.sh and create CRD manifests

**Files:**
- MODIFY `testing/ci/common.sh` — Add `FLUX_VERSION` constant + export
- CREATE `charts/floe-platform/flux/helmrelease-platform.yaml` — HelmRelease CRD for floe-platform
- CREATE `charts/floe-platform/flux/helmrelease-jobs.yaml` — HelmRelease CRD for floe-jobs-test
- CREATE `charts/floe-platform/flux/gitrepository.yaml` — GitRepository source CRD

**Acceptance criteria covered:** AC-1, AC-2, AC-3, AC-4

**Approach:**
- Add `FLUX_VERSION` after existing `FLOE_*` constants block in common.sh
- HelmRelease manifests follow design.md spec exactly (v2 API, strategy: uninstall)
- GitRepository uses v1 GA API with `spec.ref.branch: main`
- Tests: YAML structure validation (unit tier)

### Task 2: Add Flux CLI prerequisite check to setup-cluster.sh

**Files:**
- MODIFY `testing/k8s/setup-cluster.sh` — Add flux CLI check in `check_prerequisites()`, add `--no-flux` flag parsing

**Acceptance criteria covered:** AC-5, AC-10

**Approach:**
- Add `flux` CLI check after existing prerequisite checks (kubectl, helm, kind)
- Auto-install via `curl -s https://fluxcd.io/install.sh | FLUX_VERSION="${FLUX_VERSION}" bash`
- Add `--no-flux` / `FLOE_NO_FLUX` flag at argument parsing section
- Tests: Script behavior validation (integration tier)

### Task 3: Add Flux install and HelmRelease application to setup-cluster.sh

**Files:**
- MODIFY `testing/k8s/setup-cluster.sh` — Add Flux install step, pre-Flux cleanup, CRD application, readiness wait

**Acceptance criteria covered:** AC-6, AC-7, AC-8, AC-9, AC-10, AC-11

**Approach:**
- After Kind cluster creation, before existing Helm deploy:
  1. Check `FLOE_NO_FLUX` — if set, skip to existing Helm path
  2. Run `flux install --components="source-controller,helm-controller"`
  3. Verify both controllers reach Running within 120s
  4. Detect existing failed release: `helm status ... --output json`, parse `.info.status`
  5. If status in `{failed, pending-upgrade, pending-install, pending-rollback}`: `helm uninstall ... --wait --timeout=300s`
  6. `kubectl apply -f charts/floe-platform/flux/`
  7. `kubectl wait helmrelease/floe-platform ... --timeout=900s`
  8. `kubectl wait helmrelease/floe-jobs-test ... --timeout=600s`
  9. On any failure: diagnostic output for both HelmReleases + events, exit non-zero
- The existing direct Helm path is preserved inside the `--no-flux` conditional
- `--no-flux` path regression: verify pods Running, services reachable
- Tests: Full cluster setup validation (e2e tier), non-Flux path regression (e2e tier)

## File Change Map

| File | Action | Lines Changed (est.) |
|------|--------|---------------------|
| `testing/ci/common.sh` | MODIFY | +5 |
| `testing/k8s/setup-cluster.sh` | MODIFY | +80, -10 |
| `charts/floe-platform/flux/helmrelease-platform.yaml` | CREATE | ~40 |
| `charts/floe-platform/flux/helmrelease-jobs.yaml` | CREATE | ~30 |
| `charts/floe-platform/flux/gitrepository.yaml` | CREATE | ~15 |

## Dependencies

- None (first unit)

## Risks

- Flux install requires network access from Kind to pull controller images
- `kubectl wait` for custom resource conditions requires CRD to be registered first
- Pre-Flux cleanup is destructive — must be gated on release status detection

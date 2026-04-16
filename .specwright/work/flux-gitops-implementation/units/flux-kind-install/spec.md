# Spec: flux-kind-install

**Unit**: 1 of 3
**Parent**: flux-gitops-implementation
**Purpose**: Install Flux v2 controllers in Kind cluster and manage Helm releases via HelmRelease CRDs

## Acceptance Criteria

### AC-1: Flux version constant in common.sh [tier: unit]

`testing/ci/common.sh` defines `FLUX_VERSION` as a pinned version string (e.g., `"2.5.1"`),
exported alongside existing `FLOE_*` constants. The value is not hardcoded elsewhere in
the codebase — verified by a grep-based check that no other file contains a literal Flux
version string in `flux install` or `flux --version` commands.

### AC-2: HelmRelease CRD for floe-platform [tier: unit]

`charts/floe-platform/flux/helmrelease-platform.yaml` contains a structurally valid
HelmRelease CRD (YAML structure matches expected fields; CRD admission is validated
implicitly by AC-8's e2e deployment) with:
- `apiVersion: helm.toolkit.fluxcd.io/v2` (GA, not v2beta2)
- `metadata.name: floe-platform` in namespace `floe-test`
- `spec.chart.spec.chart: ./charts/floe-platform` (relative to GitRepository root)
- `spec.chart.spec.sourceRef.kind: GitRepository` with `name: floe` and `namespace: flux-system`
- `spec.interval: 30m`
- `spec.install.remediation.retries: 3` with `timeout: 10m`
- `spec.upgrade.remediation.retries: 3`, `strategy: uninstall`, `remediateLastFailure: true`
- `spec.upgrade.cleanupOnFail: true` with `timeout: 10m`

Rationale for 3 install/upgrade retries: platform chart has multiple subcharts (dagster,
polaris, minio, postgresql) — transient failures during dependency resolution are common
in Kind.

### AC-3: HelmRelease CRD for floe-jobs-test [tier: unit]

`charts/floe-platform/flux/helmrelease-jobs.yaml` contains a structurally valid
HelmRelease CRD with:
- `apiVersion: helm.toolkit.fluxcd.io/v2`
- `metadata.name: floe-jobs-test` in namespace `floe-test`
- `spec.chart.spec.sourceRef.kind: GitRepository` with `name: floe` and `namespace: flux-system`
- `spec.dependsOn` containing `{name: floe-platform}`
- `spec.install.remediation.retries: 2`
- `spec.upgrade.remediation.retries: 2`, `strategy: uninstall`

Rationale for 2 retries (vs platform's 3): jobs chart is simpler (no subcharts), so
fewer transient failures expected.

### AC-4: GitRepository source CRD [tier: unit]

`charts/floe-platform/flux/gitrepository.yaml` contains a valid GitRepository CRD with:
- `apiVersion: source.toolkit.fluxcd.io/v1` (GA)
- `metadata.name: floe` in namespace `flux-system`
- `spec.interval: 1m`
- `spec.url: https://github.com/floe-platform/floe` (HTTPS, not SSH — Kind has no SSH keys)
- `spec.ref.branch: main`

### AC-5: Flux CLI prerequisite check [tier: integration]

`setup-cluster.sh` checks for the `flux` CLI in `check_prerequisites()`. If `flux` is
not on PATH, the script prints an error message to stderr with install instructions:
```
"ERROR: flux CLI not found. Install: curl -s https://fluxcd.io/install.sh | sudo bash"
```
and exits non-zero. This follows the existing check-and-fail pattern used for kubectl,
helm, kind, and docker — no auto-install.

If `flux` IS on PATH, the script verifies the version matches `${FLUX_VERSION}` from
`common.sh` by parsing `flux --version` output. Version mismatch produces a warning
(not a failure) to stderr.

When `FLOE_NO_FLUX=1` is set, the flux CLI check is skipped entirely.

### AC-6: Flux controller installation [tier: e2e]

After Kind cluster creation (and only when `FLOE_NO_FLUX` is not set), `setup-cluster.sh`
runs `flux install --components="source-controller,helm-controller"`. On completion,
both `source-controller` and `helm-controller` pods in `flux-system` namespace reach
`Running` phase. If only one controller starts (partial failure), the script treats this
as a failure — same diagnostic path as AC-9.

### AC-7: Pre-Flux cleanup for existing clusters [tier: integration]

`setup-cluster.sh` detects whether an existing Helm release named `${FLOE_RELEASE_NAME}`
exists in namespace `${FLOE_NAMESPACE}` via `helm status ... --output json`. If the
release exists AND its `.info.status` is one of: `failed`, `pending-upgrade`,
`pending-install`, `pending-rollback`, the script runs:
```
helm uninstall ${FLOE_RELEASE_NAME} -n ${FLOE_NAMESPACE} --wait --timeout=300s
```
If the release does not exist (helm status returns non-zero), or its status is `deployed`
or `superseded`, this step is skipped. The 300s timeout prevents indefinite hangs from
stuck PVC finalizers.

### AC-8: HelmRelease application and readiness wait [tier: e2e]

`setup-cluster.sh` applies the CRD manifests from `charts/floe-platform/flux/` via
`kubectl apply -f`, then waits for readiness:
```
kubectl wait helmrelease/floe-platform -n floe-test \
    --for=condition=Ready --timeout=900s
```
followed by:
```
kubectl wait helmrelease/floe-jobs-test -n floe-test \
    --for=condition=Ready --timeout=600s
```
If the platform wait succeeds but jobs-test fails, the diagnostic output includes BOTH
HelmReleases: `flux get helmrelease -n floe-test` (not just the failing one) and the
last 10 events via `kubectl get events --sort-by='.lastTimestamp' -n floe-test | tail -10`.
The script exits non-zero.

### AC-9: Flux install failure produces actionable diagnostics [tier: integration]

If `flux install` fails (non-zero exit) OR either controller pod does not reach `Running`
within 120s, `setup-cluster.sh` outputs to stderr:
1. The `flux install` error output (if install itself failed)
2. `kubectl get pods -n flux-system` showing per-pod status (catches partial failures)
3. The message: "Flux installation failed. Check cluster resources and network connectivity."
Then exits non-zero. The script does NOT proceed to apply HelmRelease CRDs.

### AC-10: Direct Helm deployment path preserved [tier: integration]

`setup-cluster.sh` supports a `--no-flux` flag (or `FLOE_NO_FLUX=1` env var) that skips
Flux installation entirely and uses the existing direct `helm upgrade --install` path.
When `--no-flux` is set:
- AC-5 flux CLI check is skipped
- AC-6 flux install is skipped
- AC-7 pre-Flux cleanup still runs (it cleans Helm state, not Flux state)
- AC-8 HelmRelease application is skipped; direct `helm upgrade --install` is used instead
- The `--no-flux` path produces the same cluster state (pods running, services available)
  as the Flux path, verified by the existing infrastructure smoke check in conftest.py

### AC-11: Non-Flux path regression test [tier: e2e]

A test (or CI job variant) validates that `setup-cluster.sh --no-flux` produces a
functional cluster where the E2E test suite can run. This ensures the direct Helm path
does not bitrot as the Flux path evolves. The test verifies: namespace exists, platform
pods are Running, services are reachable.

## WARNs from Spec Review (Accepted)

- WARN-6: "Not hardcoded elsewhere" verified by grep check (documented in AC-1)
- WARN-7: Unit tests validate YAML structure only; CRD admission validated by AC-8 e2e (documented in AC-2/AC-3)
- WARN-8: Partial controller failure covered by AC-9 revision
- WARN-9: Diagnostic output failure-path testing is inherently e2e; accepted as-is
- WARN-11: `helm uninstall --wait` timeout now specified (300s) in AC-7
- INFO-12: Chart path dependency on GitRepository made explicit in AC-2
- INFO-13: `dependsOn` ordering is Flux-internal; unit test validates field presence only (accepted)
- INFO-14: Retry count rationale added to AC-2 and AC-3
- INFO-16: `sourceRef` field with namespace now explicit in AC-2 and AC-3

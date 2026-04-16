# Integration Criteria: flux-gitops-implementation

These criteria verify that the three work units integrate correctly after all are built.

## Structural Integration Criteria

- [ ] IC-1: `testing/ci/common.sh` exports `FLUX_VERSION` and `testing/k8s/setup-cluster.sh` sources it via `. "$(dirname ...)"/common.sh` (existing sourcing mechanism).
- [ ] IC-2: `testing/k8s/setup-cluster.sh` applies CRD manifests from `charts/floe-platform/flux/` using a path relative to the repo root (e.g., `kubectl apply -f "${REPO_ROOT}/charts/floe-platform/flux/"`).
- [ ] IC-3: `testing/fixtures/flux.py` exports `flux_suspended` fixture and `is_flux_managed` helper function.
- [ ] IC-4: `tests/e2e/conftest.py` imports crash-recovery logic from `testing.fixtures.flux` (not inline reimplementation).
- [ ] IC-5: `testing/fixtures/helm.py` imports `is_flux_managed` from `testing.fixtures.flux` for the Flux delegation check.
- [ ] IC-6: `tests/e2e/test_helm_upgrade_e2e.py` declares `flux_suspended` as a fixture parameter (imported from `testing.fixtures.flux`).
- [ ] IC-7: `charts/examples/flux/helmrelease.yaml` references `ocirepository.yaml` via `spec.chart.spec.sourceRef.kind: OCIRepository`.
- [ ] IC-8: `packages/floe-core/src/floe_core/cli/platform/compile.py` calls `CompiledArtifacts.to_configmap_yaml()` from `compiled_artifacts.py` when `--output-format=configmap`.

## Behavioral Integration Criteria

- [ ] IC-B1: After `setup-cluster.sh` completes (Unit 1) and the Flux controllers are running, running `flux get helmrelease -n floe-test` shows `floe-platform` with condition `Ready=True` and a deployed revision.
- [ ] IC-B2: When a test module uses `flux_suspended` (Unit 2) and the test process is killed mid-execution (SIGKILL), the next test session startup (via conftest crash recovery from Unit 2) detects and resumes the suspended HelmRelease. Verified by: `kubectl get helmrelease floe-platform -o jsonpath='{.spec.suspend}'` returning empty or `false` after session startup.
- [ ] IC-B3: Running `floe platform compile --output-format=configmap` (Unit 3) produces a ConfigMap YAML that, when applied to the Kind cluster via `kubectl apply -f`, appears in `kubectl get configmap floe-compiled-values -n floe-test` and can be referenced by a HelmRelease `valuesFrom` field.
- [ ] IC-B4: The `recover_stuck_helm_release()` function (modified in Unit 2) detects the Flux-managed HelmRelease (created in Unit 1) and delegates recovery to `flux reconcile` instead of direct Helm rollback.

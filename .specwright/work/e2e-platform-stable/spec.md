# Spec: E2E Platform Stability Fixes

## Acceptance Criteria

### AC-1: dagster-k8s installed in Docker image
- The Dagster daemon pod can import `dagster_k8s` without error
- `kubectl exec <daemon-pod> -- python -c "import dagster_k8s; print(dagster_k8s.__version__)"` returns a version string
- The Dockerfile smoke test at build time verifies `import dagster_k8s` succeeds
- `pip check` in the build stage reports no dependency conflicts

### AC-2: K8sRunLauncher can launch materialization runs
- Triggering an asset materialization via Dagster GraphQL returns a run that reaches `SUCCESS` status (not `FAILURE`)
- The daemon log does NOT contain `ModuleNotFoundError: No module named 'dagster_k8s'`
- E2E test `test_trigger_asset_materialization` passes

### AC-3: Pre-upgrade hook image resolves
- `bitnami/kubectl` image tag in values.yaml and values-test.yaml is a valid, pullable tag
- `kubectl get events -n floe-test | grep -i ErrImagePull` returns no results for the kubectl image
- The pre-upgrade hook job (when enabled) completes without `ErrImagePull`

### AC-4: E2E tests runnable inside DevPod via Makefile
- `make test-e2e` works inside the DevPod workspace (establishes port-forwards, fixes kubeconfig, runs tests)
- All 84 previously-erroring tests (port-forward dependent) now either pass or fail on their own merits (not infrastructure errors)
- The Makefile target handles the DooD kubeconfig IP rewriting automatically

### AC-5: Full E2E suite green (minus known issues)
- Running the full E2E suite on DevPod produces zero infrastructure errors
- The materialization test passes end-to-end
- No regressions: the 128 previously-passing tests continue to pass

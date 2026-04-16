# Context: E2E Platform Stability Fixes

## Key Files

### Dockerfile
- `docker/dagster-demo/Dockerfile` — 3-stage build (export → build → runtime)
- Lines 119-125: Explicit pip install of dagster ecosystem packages
- Line 117: Incorrect comment claiming dagster-k8s is "not required in-container"
- Line 134: Smoke test imports (add dagster_k8s here)
- `DAGSTER_VERSION=1.12.14`, `DAGSTER_POSTGRES_VERSION=0.28.14`
- dagster-k8s uses 0.x versioning (same as dagster-postgres: 0.28.14)

### Helm Chart Values
- `charts/floe-platform/values.yaml:436-438` — preUpgradeCleanup image config
- `charts/floe-platform/values-test.yaml:194-198` — same, test-specific
- Tag `"1.32"` doesn't exist on Docker Hub; `"1.32.0"` does
- `preUpgradeCleanup.enabled: false` in values.yaml, `true` in values-test.yaml
- Template: `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml`

### E2E Test Runner
- `testing/ci/test-e2e.sh` — sets up 8 port-forwards before running pytest
- `Makefile:128-137` — `test-e2e` and `test-e2e-local` targets
- `.devcontainer/hetzner/postStartCommand.sh` — creates Kind cluster but no port-forwards

### Dagster K8s Integration
- `plugins/floe-orchestrator-dagster/pyproject.toml:44` — declares `dagster-k8s>=1.10.0,<2.0.0` under `[docker]` extras
- `uv.lock` has the constraint but NOT a resolved `[[package]]` entry for dagster-k8s
- All Helm values files configure `K8sRunLauncher` (values.yaml:188, values-demo.yaml:79, etc.)

## Gotchas
- dagster-k8s is NOT in uv.lock as a resolved package — `uv export --extra docker` may not emit it, so explicit pip install is required
- bitnami/kubectl uses semver patch tags (1.32.0) not minor-only (1.32)
- DevPod DooD kubeconfig needs IP rewriting before every kubectl command
- The E2E port-check hook (`.claude/hooks/check-e2e-ports.sh`) blocks any bash command containing `pytest.*tests/e2e` — tests MUST go through the proper runner

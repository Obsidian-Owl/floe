# Spec: Dependency Bump + Helm Hook Deadline

## Acceptance Criteria

### AC-1: requests upgraded to >=2.33.0
- `pyproject.toml` declares `"requests>=2.33.0"`
- `uv.lock` resolves requests to >=2.33.0
- `uv lock --upgrade-package requests` succeeds without conflicts

### AC-2: pip-audit passes
- `test_pip_audit_clean` E2E test passes
- `pip-audit` reports 0 vulnerabilities for requests

### AC-3: Hook deadline is configurable via values
- Template uses `{{ .Values.postgresql.preUpgradeCleanup.activeDeadlineSeconds | default 300 }}`
- `values.yaml` documents the parameter under `postgresql.preUpgradeCleanup`
- `values-test.yaml` sets `activeDeadlineSeconds: 600`

### AC-4: Helm unit tests updated
- `hook-pre-upgrade_test.yaml` tests:
  - Default deadline is 300 (no override)
  - Custom deadline via values override
- Tests pass: `helm unittest charts/floe-platform`

### AC-5: E2E helm upgrade test is more resilient
- `test_helm_upgrade_succeeds` has 600s budget for the hook in test environment
- Timing flakes from image pull delays are absorbed by the larger deadline

## Error Cases
- `uv lock` conflict → `uv tree --package requests` to identify conflicting transitive dep
- Helm template syntax error → `helm template` dry-run catches before deploy

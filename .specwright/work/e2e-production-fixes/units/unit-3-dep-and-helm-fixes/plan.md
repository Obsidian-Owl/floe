# Plan: Dependency Bump + Helm Hook Deadline

## Tasks

### Task 1: Bump requests constraint
- File: `pyproject.toml` line 26
- Change: `"requests>=2.31"` → `"requests>=2.33.0"`
- Run: `uv lock --upgrade-package requests`
- Verify: `uv tree --package requests` shows >=2.33.0

### Task 2: Parameterize hook deadline
- File: `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml` line 74
- Change: `activeDeadlineSeconds: 300` → `activeDeadlineSeconds: {{ .Values.postgresql.preUpgradeCleanup.activeDeadlineSeconds | default 300 }}`

### Task 3: Add values entries
- File: `charts/floe-platform/values.yaml` — add `activeDeadlineSeconds: 300` under `postgresql.preUpgradeCleanup`
- File: `charts/floe-platform/values-test.yaml` — add `activeDeadlineSeconds: 600` under `postgresql.preUpgradeCleanup`

### Task 4: Update helm unit tests
- File: `charts/floe-platform/tests/hook-pre-upgrade_test.yaml`
- Update AC-4b test to use `.Values` reference or add a custom-value test case
- Run: `helm unittest charts/floe-platform`

## File Change Map
| File | Change |
|------|--------|
| `pyproject.toml` | Bump requests constraint |
| `uv.lock` | Regenerated |
| `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml` | Parameterize deadline |
| `charts/floe-platform/values.yaml` | Add activeDeadlineSeconds default |
| `charts/floe-platform/values-test.yaml` | Set 600s for CI |
| `charts/floe-platform/tests/hook-pre-upgrade_test.yaml` | Update assertion |

## Dependencies
- None (independent unit)

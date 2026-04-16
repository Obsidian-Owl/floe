# Plan: dbt Jobs Template Fix

## Tasks

### Task 1: Update values.yaml — structured values
- File: `charts/floe-jobs/values.yaml`
- Remove `args: ["run", "--profiles-dir", "/etc/dbt", "--project-dir", "/dbt"]`
- Add `profilesDir: /etc/dbt`, `projectDir: /dbt` under `dbt:`
- Add comment explaining `dbt.args` override escape hatch

### Task 2: Update job.yaml template — args construction
- File: `charts/floe-jobs/templates/job.yaml` lines 53-56
- Replace verbatim `dbt.args` rendering with conditional logic:
  - If `dbt.args` set → render verbatim (escape hatch)
  - Else → construct from `profilesDir`, `projectDir`, `target`, `debug`

### Task 3: Update cronjob.yaml template — same change
- File: `charts/floe-jobs/templates/cronjob.yaml` lines 63-66
- Same args construction logic as job.yaml

### Task 4: Fix values-test.yaml key mismatch
- File: `charts/floe-jobs/values-test.yaml`
- Rename `jobDefaults:` to `defaults:`
- Verify `profilesDir: /dbt/profiles` and `projectDir: /dbt` are under `dbt:`

### Task 5: Add/update helm unit tests
- File: `charts/floe-jobs/tests/` (create or update test files)
- Test default args, custom profilesDir, args override, target flag

## File Change Map
| File | Change |
|------|--------|
| `charts/floe-jobs/values.yaml` | Replace `args` with `profilesDir`, `projectDir` |
| `charts/floe-jobs/values-test.yaml` | Fix `jobDefaults` → `defaults` |
| `charts/floe-jobs/templates/job.yaml` | Args construction with escape hatch |
| `charts/floe-jobs/templates/cronjob.yaml` | Same args construction |
| `charts/floe-jobs/tests/*.yaml` | Add/update unit tests |

## Dependencies
- None (independent unit)

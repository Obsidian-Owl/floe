# Spec: dbt Jobs Template Fix

## Acceptance Criteria

### AC-1: Template constructs args from individual values
- When `dbt.args` is NOT set, the template constructs args from:
  - `dbt.profilesDir` (default: `/etc/dbt`)
  - `dbt.projectDir` (default: `/dbt`)
  - `dbt.target` (optional, adds `--target <value>` when set)
  - `dbt.debug` (optional, adds `--debug` flag when true)
- Rendered args: `["run", "--profiles-dir", "<profilesDir>", "--project-dir", "<projectDir>"]`

### AC-2: dbt.args override takes precedence (backward compatibility)
- When `dbt.args` IS set in values, the template renders it verbatim (existing behavior)
- This is the escape hatch for custom args that don't fit the structured pattern

### AC-3: values.yaml uses structured values instead of hardcoded args
- `values.yaml` removes `args:` from `dbt:` section
- `values.yaml` adds `profilesDir: /etc/dbt` and `projectDir: /dbt` under `dbt:`
- Default behavior is identical to current (same rendered args)

### AC-4: values-test.yaml key mismatch fixed
- `jobDefaults:` renamed to `defaults:` in `values-test.yaml` to match `values.yaml` schema
- All intended overrides (`backoffLimit: 1`, `activeDeadlineSeconds: 300`, `ttlSecondsAfterFinished: 60`) are now applied

### AC-5: Both job.yaml and cronjob.yaml templates updated
- The args construction logic is identical in both templates
- `helm template` renders correct args for both Job and CronJob variants

### AC-6: Helm unit tests validate args construction
- Test case: default values produce `["run", "--profiles-dir", "/etc/dbt", "--project-dir", "/dbt"]`
- Test case: custom `profilesDir`/`projectDir` produce correct args
- Test case: `dbt.args` override renders verbatim
- Test case: `dbt.target` adds `--target` flag

## Error Cases
- `dbt.profilesDir` set but no `dbt.profiles` content → pod has `--profiles-dir` flag pointing to empty directory. This is an existing issue (the ConfigMap gate requires `dbt.profiles` to be set separately). Document in values.yaml comment.
- Both `dbt.args` and `dbt.profilesDir` set → `dbt.args` takes precedence (documented behavior)

# Spec: Dagster writable volumes for readOnlyRootFilesystem

**Work unit**: `debug-dagster-readonly-fs`
**Scope**: Fix Dagster CrashLoopBackOff by adding writable emptyDir volumes

## Acceptance Criteria

### AC-1: Dagster pods start successfully with readOnlyRootFilesystem: true

Both `dagsterWebserver` and `dagsterDaemon` pods must reach `Running` + `Ready` state
with `readOnlyRootFilesystem: true` preserved. The fix uses the subchart's `volumes` /
`volumeMounts` extension points to mount writable `emptyDir` volumes for all directories
Dagster creates at runtime:

- `$DAGSTER_HOME/.telemetry/`
- `$DAGSTER_HOME/logs/`
- `$DAGSTER_HOME/.logs_queue/`
- `$DAGSTER_HOME/history/`
- `$DAGSTER_HOME/schedules/`
- `$DAGSTER_HOME/storage/`
- `/tmp` (general scratch)

The `dagster.yaml` ConfigMap file mount at `$DAGSTER_HOME/dagster.yaml` (subPath) must
not be shadowed.

### AC-2: Telemetry remains enabled

`dagster.telemetry.enabled` remains `true` in the Dagster subchart values. The fix must
not disable telemetry. After the fix, Dagster must be able to write its instance UUID
to `.telemetry/id.yaml` without errors.

### AC-3: Helm chart unit tests pass

`helm unittest charts/floe-platform` must pass with no regressions. If existing tests
assert on Dagster deployment volume counts, update them to reflect the new volumes.

## Files

| File | Action | Change |
|------|--------|--------|
| `charts/floe-platform/values.yaml` | edit | Add `volumes` + `volumeMounts` to dagsterWebserver and dagsterDaemon |
| `charts/floe-platform/values-test.yaml` | edit (if needed) | Same volumes if test values override Dagster config |

# Diagnosis: Dagster CrashLoopBackOff — readOnlyRootFilesystem vs writable directories

## Problem

**Observed**: Dagster daemon and webserver pods enter CrashLoopBackOff immediately on startup.
**Expected**: Pods start and become Ready.
**Error**: `OSError: [Errno 30] Read-only file system: '/opt/dagster/dagster_home/.telemetry'`

## Root Cause (HIGH confidence)

The chart applies `readOnlyRootFilesystem: true` via the `*containerSecurityContextPSS` YAML anchor
to both `dagsterWebserver` and `dagsterDaemon` (`values.yaml:150-151`, `186-187`). Dagster requires
write access to multiple subdirectories under `$DAGSTER_HOME` (`/opt/dagster/dagster_home`) at startup:

| Directory | Purpose | When created |
|-----------|---------|-------------|
| `.telemetry/` | Instance UUID (`id.yaml`) | Startup (when `telemetry.enabled: true`) |
| `logs/` | Telemetry event log (rotating, 10MB) | Telemetry upload thread start |
| `.logs_queue/` | Staging for upload | Telemetry upload thread start |
| `history/` | SQLite run storage | Instance init |
| `history/runs/` | SQLite event log storage | Instance init |
| `schedules/` | SQLite schedule storage | Instance init |
| `storage/` | Compute logs (stdout/stderr) | Instance init |

Additionally, `~/.dagster/.telemetry/user_id.yaml` is hardcoded to `~/.dagster` regardless of
`$DAGSTER_HOME` — the pod's home directory must also be writable when telemetry is enabled.

**Why `DAGSTER_DISABLE_TELEMETRY` doesn't solve it**: This env var only suppresses the HTTP POST
to `telemetry.dagster.io` — it does NOT prevent directory creation. Even with `telemetry: enabled: false`
in `dagster.yaml`, the `history/`, `schedules/`, `storage/` directories are still created at instance init.

**Why Polaris works**: Polaris mounts writable `emptyDir` volumes for `/tmp`, `/work`, and `/home/jboss`
(`deployment-polaris.yaml:106-125`). Dagster has no equivalent writable volumes.

## Blast Radius

**Affected**:
- `dagsterWebserver` — CrashLoopBackOff, UI inaccessible
- `dagsterDaemon` — CrashLoopBackOff, no schedule/sensor execution
- ALL E2E tests that depend on Dagster (asset materialization, demo flow, observability)

**Not affected**:
- Polaris, MinIO, PostgreSQL, Jaeger, Marquez, OTel, Cube — all Running
- Unit tests, Helm chart unit tests — no Dagster pods needed

## Fix Approach

Add `emptyDir` writable volumes to both Dagster components via the subchart's `extraVolumes` /
`extraVolumeMounts` values. Mount individual subdirectories to avoid shadowing the `dagster.yaml`
ConfigMap file mount at `$DAGSTER_HOME/dagster.yaml`.

**Files**: `charts/floe-platform/values.yaml` (1 file, ~30 lines added)

The Dagster subchart's deployment templates support `extraVolumes` and `extraVolumeMounts` — this
is the intended extension point. No template modifications required.

## Alternatives Considered

| Alternative | Why rejected |
|------------|-------------|
| `DAGSTER_DISABLE_TELEMETRY=true` | Only blocks upload HTTP POST, not directory creation. Also, user requires telemetry as a proof point. |
| `telemetry: enabled: false` | Suppresses `.telemetry/` writes but NOT `history/`, `schedules/`, `storage/`. Pods still crash. |
| `readOnlyRootFilesystem: false` for Dagster | Weakens PSS restricted security posture. Every other component works with readOnly. |
| Mount emptyDir over entire `$DAGSTER_HOME` | Shadows the `dagster.yaml` ConfigMap subPath mount. Would require init container to copy config. |

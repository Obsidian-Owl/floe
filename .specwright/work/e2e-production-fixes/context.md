# Context: E2E Production Fixes

## Research Brief

Full research at `.specwright/research/e2e-failures-20260327.md`.

## Key File Paths

### Track 1: Dagster Code Location Loading
- `docker/dagster-demo/Dockerfile` -- 3-stage build, COPY demo/* at lines 147-161
- `demo/customer-360/definitions.py` -- `MANIFEST_PATH = DBT_PROJECT_DIR / "target" / "manifest.json"`
- `demo/customer-360/target/manifest.json` -- 587KB, exists locally but gitignored
- `.gitignore` line 89: `target/` (excludes all target directories)
- `Makefile` targets: `compile-demo`, `build-demo-image`
- Dagster workspace template: `charts/floe-platform/templates/configmap-dagster-workspace.yaml`

### Track 2: OpenLineage START Events
- `packages/floe-core/src/floe_core/compilation/stages.py` lines 562-586 -- per-model emission loop
- `packages/floe-core/src/floe_core/compilation/stages.py` line 341 -- pipeline START
- `packages/floe-core/src/floe_core/compilation/stages.py` line 633 -- pipeline COMPLETE
- `tests/e2e/test_observability.py` line 889 -- `test_openlineage_four_emission_points`
- `tests/e2e/conftest.py` line 932 -- `seed_observability` fixture (Phase 1: compile, Phase 2: Dagster run)

### Track 3: requests CVE
- `pyproject.toml` line 26: `"requests>=2.31"`

### Track 4: Helm Upgrade Flake
- `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml` line 74: `activeDeadlineSeconds: 300`
- `charts/floe-platform/tests/hook-pre-upgrade_test.yaml` line 81: hardcodes `value: 300`

### Track 5: dbt Jobs
- `charts/floe-jobs/values.yaml` line 92: `args: ["run", "--profiles-dir", "/etc/dbt"]`
- `charts/floe-jobs/values-test.yaml` lines 41-42: `profilesDir: /dbt/profiles` (unconsumed)
- `charts/floe-jobs/templates/job.yaml` lines 53-56: renders `dbt.args` verbatim
- `charts/floe-jobs/templates/configmap.yaml` lines 7-19: creates dbt-profiles ConfigMap when `dbt.profiles` is set

## Gotchas

1. `@dbt_assets(manifest=...)` reads at import time, not run time
2. Marquez maps OpenLineage START -> RUNNING/NEW (not literal "START")
3. Per-model emission is back-to-back synchronous -- Marquez may never surface intermediate state
4. `values-test.yaml` sets `jobDefaults:` but `values.yaml` uses `defaults:` -- key mismatch
5. The configmap.yaml infrastructure for dbt profiles exists but is gated on `dbt.profiles` which is never set

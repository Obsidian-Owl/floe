# Context: Unit 4 — dbt Jobs Template Fix

## Problem
Triple mismatch in floe-jobs chart:
1. `values.yaml` line 92 hardcodes `args: ["run", "--profiles-dir", "/etc/dbt", "--project-dir", "/dbt"]`
2. No volume mounted at `/etc/dbt` — pod fails immediately
3. `values-test.yaml` sets `profilesDir: /dbt/profiles` and `projectDir: /dbt` but no template consumes them
4. `values-test.yaml` uses `jobDefaults:` key but `values.yaml` uses `defaults:` — overrides silently ignored

## Key Files
- `charts/floe-jobs/values.yaml` line 92: hardcoded args
- `charts/floe-jobs/values-test.yaml` lines 41-42: unconsumed profilesDir/projectDir
- `charts/floe-jobs/values-test.yaml` line 62: `jobDefaults:` (should be `defaults:`)
- `charts/floe-jobs/templates/job.yaml` lines 53-56: renders `dbt.args` verbatim
- `charts/floe-jobs/templates/cronjob.yaml` lines 63-66: same pattern
- `charts/floe-jobs/templates/configmap.yaml` lines 7-19: creates dbt-profiles ConfigMap when `dbt.profiles` is set (infrastructure exists but never activated)

## Design Decision
D5: Values-driven args construction with `dbt.args` as escape hatch. Template constructs args from `profilesDir`, `projectDir`, `target` when `dbt.args` is not set. `dbt.args` override takes precedence for backward compatibility.

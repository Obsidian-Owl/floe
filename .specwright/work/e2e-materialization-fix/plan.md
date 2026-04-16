# Plan: E2E Materialization Fix

## Task Breakdown

### Task 1: Update code generator template (AC-1, AC-2, AC-3)

Update the template string in `generate_entry_point_code()` to use `DbtProject`
instead of `DbtCliResource` for the `@dbt_assets(project=...)` parameter.

**Two changes in the template string:**
1. Import line: add `DbtProject` to the import
2. Decorator parameter: change `project=DbtCliResource(...)` to `project=DbtProject(..., profiles_dir=...)`

### Task 2: Add review-by date to CVE ignore (AC-4)

Update the `.vuln-ignore` entry for `GHSA-m959-cc7f-wv43` to include a review-by
date comment, matching the pattern of existing entries (e.g., Pygments at line 26).

## File Change Map

| File | Change | Task |
|------|--------|------|
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` | Template line 1179: add `DbtProject` to import. Template line 1189: change `DbtCliResource` to `DbtProject` with `profiles_dir` | T1 |
| `.vuln-ignore` | Add `# Review by 2026-04-28` to GHSA-m959-cc7f-wv43 entry | T2 |

## As-Built Notes

### Discovered during validation: Dockerfile manifest path bug

The E2E validation revealed two additional issues not in the original design:

1. **Missing dbt manifests in Docker image** — `target/manifest.json` from the build context was generated on the developer workspace and embedded absolute host paths (e.g., `/workspace/demo/customer-360/` or `/Users/.../demo/customer-360/`). At runtime in the container, dbt constructs seed file patterns from `root_path` in the manifest, resolving to nonexistent paths.

2. **`partial_parse.msgpack` carries stale paths** — Even after generating fresh manifests, the msgpack cache re-introduces the old paths. Must be deleted before `dbt parse`.

**Fix**: Added a `RUN` step in `docker/dagster-demo/Dockerfile` to delete `partial_parse.msgpack` and regenerate manifests with `dbt parse --profiles-dir .` inside the container. Also extended `chown` to cover `/app/demo` for dagster user write access.

**Validation result**: 3 successful materialization runs on DevPod (customer-360: 3 seeds, 6 models, 31 data tests).

### File Change Map (as-built)

| File | Change | Task |
|------|--------|------|
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` | Template: add `DbtProject` import, change `project=` parameter | T1 |
| `.vuln-ignore` | Add review-by date to GHSA-m959-cc7f-wv43 | T2 |
| `docker/dagster-demo/Dockerfile` | Add manifest regeneration step, extend chown | Validation discovery |

## Architecture Decisions

- **Single work unit**: All changes are local scope, <=2 files, no architectural boundaries crossed
- **No new tests**: Generator output testing is out of scope (decision D2). The fix is verified by live debugging evidence and consistency with the manually fixed demo files
- **Template-only change**: No logic changes to `generate_entry_point_code()` — only the string template content changes

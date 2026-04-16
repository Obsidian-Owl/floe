# Spec: E2E Materialization Fix

## Summary

Fix three stacked issues preventing asset materialization in E2E tests:
1. Helm v4 `--atomic` deprecation causing upgrade failures
2. New CVE in cryptography 46.0.5 failing pip-audit
3. `@dbt_assets(project=DbtCliResource(...))` type mismatch — must be `DbtProject`

Fixes 1-2 are already committed (`56378e4`). Fix 3 demo files are committed (`af7c697`).
Remaining work: update the code generator template to match.

## Acceptance Criteria

### AC-1: Code generator template uses DbtProject

**Given** the code generator template in `plugin.py:generate_entry_point_code()`
**When** the template imports dagster-dbt types
**Then** it imports `DbtProject` alongside `DbtCliResource` and `dbt_assets`

**Verification**: The template string contains `from dagster_dbt import DbtCliResource, DbtProject, dbt_assets`

### AC-2: Code generator template passes DbtProject to @dbt_assets

**Given** the code generator template in `plugin.py:generate_entry_point_code()`
**When** the template defines the `@dbt_assets` decorator
**Then** `project=` uses `DbtProject(project_dir=DBT_PROJECT_DIR, profiles_dir=DBT_PROJECT_DIR)` (not `DbtCliResource`)

**Verification**: The template string contains `project=DbtProject(project_dir=DBT_PROJECT_DIR, profiles_dir=DBT_PROJECT_DIR)`

### AC-3: Generated definitions match manual fix

**Given** a call to `generate_entry_point_code()` with valid inputs
**When** the generated `definitions.py` is compared to `demo/customer-360/definitions.py`
**Then** the import line and `@dbt_assets(project=...)` parameter match the same pattern used in the manually fixed demo files

**Verification**: Generated output contains `DbtProject` import and `project=DbtProject(...)` — same pattern as committed fix `af7c697`

### AC-4: CVE ignore entry has review-by date

**Given** the `.vuln-ignore` entry for `GHSA-m959-cc7f-wv43`
**When** reviewed for consistency with other entries
**Then** the entry includes a `# Review by YYYY-MM-DD` comment (30-day window)

**Verification**: `.vuln-ignore` line for `GHSA-m959-cc7f-wv43` contains `Review by 2026-04-28`

## WARNs from Architect Review

- **W2**: No test for code generator output content — noted, out of scope (tracked as backlog)

# Context: Unit 1 — Config Fixes (CVE sync + profiles.yml)

## Scope

Two configuration-only fixes that require no code changes:
- **Fix A**: Add missing CVE to `.vuln-ignore`
- **Fix B**: Change DuckDB path in 3 demo `profiles.yml` files

## Files to modify

| File | Change |
|------|--------|
| `.vuln-ignore` | Add `GHSA-gc5v-m9x4-r6x2` with rationale comment |
| `demo/customer-360/profiles.yml` | `path: "target/demo.duckdb"` -> `path: ":memory:"` |
| `demo/iot-telemetry/profiles.yml` | Same |
| `demo/financial-risk/profiles.yml` | Same |

## Key references

- `pyproject.toml:233-238` — existing CVE rationale
- `test_pip_audit_clean` — reads `.vuln-ignore`
- `test_dbt_profile_correct_for_in_cluster_execution` — validates compiled profiles use `:memory:`
- `values.yaml:~667-670` — `readOnlyRootFilesystem: true`
- Pattern P39 — single-file ignore/allow lists
- `docker/dagster-demo/Dockerfile` — copies demo directories into image as-is

## E2E tests fixed

- #1: `test_trigger_asset_materialization` (profiles.yml path)
- #2: `test_iceberg_tables_exist_after_materialization` (cascade from #1)
- #4: `test_pip_audit_clean` (missing CVE ignore)

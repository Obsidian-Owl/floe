# Gate: Wiring

**Status**: WARN
**Timestamp**: 2026-04-13T19:30:00+10:00

## Checks (6 total: 5 PASS, 1 WARN)

| # | Check | Status |
|---|---|---|
| 1 | `dbt_utils.py` imports resolve | PASS |
| 2 | `test_iceberg_purge_e2e.py` imports + `_DBT_UTILS_PATH` | PASS |
| 3 | `test_polaris_jdbc_durability.py` imports | PASS |
| 4 | `test_iceberg_purge.py` importlib + path | PASS |
| 5 | `rbac-standard.yaml` Helm helpers | PASS |
| 6 | `_test-job.tpl` Helm helpers + env vars | WARN |

## Findings

### WARN: W1 — Env var name mismatch (non-blocking)
- `dbt_utils.py` reads `POLARIS_URL` but Helm sets `POLARIS_URI`
- `dbt_utils.py` reads `MINIO_URL` but Helm sets `MINIO_ENDPOINT`
- **Impact**: Fallback to `ServiceEndpoint()` resolves correctly in K8s, so these env var reads are effectively dead code. Non-blocking but misleading.
- **Recommendation**: Align env var names in `dbt_utils.py` to match Helm template (`POLARIS_URI`, `MINIO_ENDPOINT`). Track as tech debt.

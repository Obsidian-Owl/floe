# Security Gate Report: runtime-loader

**Date**: 2026-04-06
**Branch**: feat/e2e-production-bugfixes
**Gate**: gate-security
**Result**: PASS (with advisory notes)

---

## Scan Scope

### Production files scanned:
- `demo/customer-360/definitions.py`
- `demo/financial-risk/definitions.py`
- `demo/iot-telemetry/definitions.py`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/__init__.py`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`

### Test files spot-checked for leaked secrets:
- `plugins/floe-orchestrator-dagster/tests/unit/test_code_generator_iceberg.py`
- `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`
- `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py`
- `plugins/floe-orchestrator-dagster/tests/integration/test_loader_integration.py`
- `tests/e2e/test_runtime_loader_e2e.py`

---

## Checks Performed

| Category | Result | Details |
|----------|--------|---------|
| Leaked secrets (API keys, tokens, passwords, private keys) | PASS | No hardcoded credentials in production code |
| Dangerous constructs | PASS | No use of eval, exec, or __import__ |
| Command injection | PASS | No subprocess calls or shell=True |
| Unsafe deserialization | PASS | No unsafe deserialization found |
| SQL injection | PASS | iceberg.py uses identifier validation regex and quoting; nosec B608 justified |
| Error data leakage (CWE-209) | PASS | Exception handlers log type(exc).__name__ not str(exc) |
| Fail-open error handling (CWE-636) | PASS | See advisory notes below |

---

## Advisory Notes (non-blocking)

### Note 1: Bare except-Exception-pass blocks in loader.py

**File**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py`
**Lines**: 87-88, 100-101, 111-112

Three bare except-Exception-pass blocks for lineage emission (trace facet, emit_fail, emit_complete). These are intentionally non-blocking -- lineage emission failure must not prevent dbt run or swallow the dbt error. The dbt error is always re-raised (line 102), so no fail-open security path exists.

**Verdict**: Acceptable. Lineage is observability, not security-critical control flow.

### Note 2: Broad exception catch for namespace creation in iceberg.py

**File**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
**Lines**: 81-86

Catches all exceptions during catalog.create_namespace() and logs type(exc).__name__ at debug level. This is a create-if-not-exists pattern where 409 Conflict is expected. No security-critical decision depends on this.

**Verdict**: Acceptable. Could be narrowed to specific exception types but is not a security risk.

### Note 3: Dynamic SQL in iceberg.py with nosec B608

**File**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
**Line**: 107

Uses f-string interpolation for SQL but is guarded by _is_safe_identifier() validation (regex ^[a-zA-Z_][a-zA-Z0-9_]*$) on both schema_name and table_name before reaching this line (lines 96-101). Identifiers are also quoted. The nosec B608 suppression is justified.

**Verdict**: Acceptable. Input is validated and comes from DuckDB information_schema, not user input.

### Note 4: Predictable /tmp path in iceberg.py

**File**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
**Line**: 46

Uses /tmp/{safe_name}.duckdb with a predictable path. The safe_name is derived from product_name validated upstream via Pydantic. This runs inside K8s pods where /tmp is pod-local, not shared.

**Verdict**: Acceptable in K8s containerized context. Not a symlink attack vector.

### Note 5: Test credentials use environment variables with fallbacks

**File**: `plugins/floe-orchestrator-dagster/tests/integration/conftest.py`

Integration test fixtures use os.environ.get() with default test credentials (e.g., "demo-admin:demo-secret", "minioadmin123"). These are documented K8s test environment defaults, not production credentials, and follow the project convention of env-var-with-fallback for test infrastructure.

**Verdict**: Acceptable. Follows project convention per MEMORY.md.

---

## Findings Summary

| Severity | Count |
|----------|-------|
| BLOCK | 0 |
| WARN | 0 |
| Advisory | 5 |

**Overall Result**: **PASS**

No blocking or warning-level security issues found. All advisory notes document accepted patterns consistent with project conventions.

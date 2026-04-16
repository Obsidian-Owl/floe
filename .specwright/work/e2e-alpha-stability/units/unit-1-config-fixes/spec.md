# Spec: Unit 1 — Config Fixes (CVE sync + profiles.yml)

## Acceptance Criteria

### AC-1: `.vuln-ignore` contains requests CVE

`.vuln-ignore` includes `GHSA-gc5v-m9x4-r6x2` with a comment explaining:
- The CVE ID
- Why it is ignored (not exploitable — `extract_zipped_paths()` unused)
- What blocks the upstream fix (`datacontract-cli <2.33` pin)

**How to verify**: `grep GHSA-gc5v-m9x4-r6x2 .vuln-ignore` returns the entry.

### AC-2: All demo profiles.yml use `:memory:` path

All 3 demo product `profiles.yml` files specify `path: ":memory:"` instead of `path: "target/demo.duckdb"`:
- `demo/customer-360/profiles.yml`
- `demo/iot-telemetry/profiles.yml`
- `demo/financial-risk/profiles.yml`

**How to verify**: `grep -r 'path:.*demo.duckdb' demo/` returns no results. `grep -r 'path:.*:memory:' demo/` returns 3 results.

### AC-3: No other profiles.yml fields changed

Only the `path` field changes. Profile name, target, type, and threads remain unchanged for each product.

**How to verify**: `git diff` shows exactly 3 files changed, each with a single-line diff on the `path` field.

### AC-4: Existing vuln-ignore entries preserved

All existing entries in `.vuln-ignore` remain. The new entry is appended, not replacing anything.

**How to verify**: `.vuln-ignore` line count increases by exactly 3 (comment line, blank line, CVE ID) or 4 (with additional context comment).

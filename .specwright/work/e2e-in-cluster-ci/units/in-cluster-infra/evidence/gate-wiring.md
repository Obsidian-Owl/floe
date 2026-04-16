# Gate: Wiring

**Status**: PASS (after fixes — 1 BLOCK fixed, 2 WARN fixed)
**Timestamp**: 2026-03-29T04:55:00Z

## Findings (all resolved)

### BLOCK-1: KIND_CLUSTER_NAME mismatch → FIXED
- weekly.yml created clusters `floe-weekly`/`floe-e2e` but test-integration.sh defaulted to `floe`
- Fix: Added `KIND_CLUSTER_NAME` env var to all test steps in weekly.yml

### WARN-1: Both Jobs created simultaneously → FIXED
- `test-e2e.yaml` contained two YAML documents; `kubectl apply -f` created both
- Fix: Split into `test-e2e.yaml` and `test-e2e-destructive.yaml`
- Updated script to reference `test-e2e-destructive.yaml` for destructive suite

### WARN-2: Silent RBAC/PVC failures → FIXED (same as security WARN-5)

## Cross-reference verification (all PASS)

| Check | Status |
|-------|--------|
| Job SA names match RBAC SA names | PASS |
| PVC claimName matches PVC manifest | PASS |
| test-type labels consistent | PASS |
| JOB_NAME values match Job metadata.name | PASS |
| Manifest paths exist | PASS |
| TEST_SUITE values match case statement | PASS |
| SKIP_BUILD=true on destructive run | PASS |
| All RBAC/PVC in floe-test namespace | PASS |

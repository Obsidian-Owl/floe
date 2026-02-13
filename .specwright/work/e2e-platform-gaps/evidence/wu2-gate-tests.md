# Gate: Tests — WU-2 Evidence

**Work Unit**: wu-2-cube (Cube Multi-Arch + Pod Scheduling)
**Gate**: gate-tests
**Status**: WARN
**Timestamp**: 2026-02-13T16:05:00Z

## Scope

- `testing/tests/unit/test_ci_workflows.py` (13 tests)
- `tests/e2e/test_platform_deployment_e2e.py` (2 new xfail tests)

## Findings

- **BLOCK**: 0
- **WARN**: 5
- **INFO**: 5

### WARN Findings

1. **W-001**: xfail structural check is shallow — substring search on file rather than AST-level verification of decorator-to-function binding
2. **W-002**: No negative/boundary tests for nightly workflow structure (e.g., single-platform only)
3. **W-003**: Dockerfile FROM check doesn't verify base image is cubejs/cubestore
4. **W-004**: cubeStore key casing fallback masked mismatch — **FIXED** (commit 0c5e8c5)
5. **W-005**: xfail tests absorb all failure causes indiscriminately (image pull vs selector mismatch)

### INFO Findings

1. Tags assertion uses substring match (acceptable for controlled file)
2. Repeated YAML parsing in TestNightlyWorkflow (4x)
3. Repeated YAML parsing in TestValuesTestCubeStore (5x)
4. Cube Store readiness test only checks first pod
5. No test validates QEMU setup step presence

## Coverage Map

| AC | Tests | Coverage |
|----|-------|----------|
| WU2-AC1 | 7 tests | Good |
| WU2-AC2 | 2 tests | Good |
| WU2-AC3 | 2 tests | Strong (exact values) |
| WU2-AC4 | 1 test | Adequate |
| WU2-AC5 | 3 tests | Adequate |

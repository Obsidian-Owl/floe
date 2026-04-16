# Gate: Wiring Report

**Generated**: 2026-04-07T06:55:00Z
**Status**: WARN

## Scope

Per-unit wiring analysis (unit 1 of 3 — cross-unit check not applicable).

## Findings

### WARN-1: Pod cleanup races with K8s garbage collector (resolved in practice)
- **Location**: `testing/ci/test-e2e-full.sh:48`
- Pod delete with `-l test-type=e2e` may race against GC after Job deletion.
  In practice, the explicit delete is faster than GC. The 30s wait loop at
  lines 51-60 handles the timing. Not a functional issue.

### WARN-2: Artifact filename in error message (FIXED)
- **Location**: `testing/ci/test-e2e-cluster.sh:207`
- Error message referenced hardcoded `e2e-output.log` instead of
  `${TEST_SUITE}-output.log`. Fixed in commit `f27ac10`.

### INFO-1: No orphaned files
- `test-e2e-full.sh` referenced by `Makefile:137`
- `test-e2e-cluster.sh` referenced by `Makefile:132` and `test-e2e-full.sh:35,74`
- All files wired correctly.

### INFO-2: Env var consistency verified
- `SKIP_BUILD`, `IMAGE_LOAD_METHOD`, `TEST_SUITE`, `TEST_NAMESPACE`, `JOB_TIMEOUT`
  consistent between `test-e2e-cluster.sh` and `test-e2e-full.sh`.

### INFO-3: Namespace hardcoding assumption
- Job manifests have `namespace: floe-test` in metadata. `TEST_NAMESPACE` defaults
  to `floe-test`. If these diverge, Jobs would be created in wrong namespace.
  Currently consistent.

## Cross-Unit Integration

Not applicable — this is unit 1 of 3 (not the final unit).

## Verdict

WARN — one wiring bug found and fixed (artifact filename). No BLOCK findings.

# Gate: Wiring — WU-2 Evidence

**Work Unit**: wu-2-cube (Cube Multi-Arch + Pod Scheduling)
**Gate**: gate-wiring
**Status**: PASS (after fix)
**Timestamp**: 2026-02-13T16:10:00Z

## Initial Run: FAIL (2 BLOCK)

### BLOCK Findings (RESOLVED)

1. **cubeStore key casing mismatch** — values-test.yaml used `cubestore` (lowercase) but subchart expects `cubeStore` (camelCase). YAML is case-sensitive, so the image override was silently ignored.
   - **Fix**: Changed to `cubeStore` in values-test.yaml (commit 0c5e8c5)

2. **Tests masked the mismatch** — dual-key lookup `cube.get("cubestore", cube.get("cubeStore", {}))` accepted both casings.
   - **Fix**: Tests now enforce exact `cubeStore` key (commit 0c5e8c5)

### WARN Findings (Accepted)

1. Dockerfile multi-arch strategy may produce QEMU-emulated ARM64 image (acceptable for CI testing)
2. Version tag prefix inconsistency (v0.36.0 in Dockerfile ARG vs 0.36.0 in output tags)

### INFO Findings

1. No cubeStore sub-key in parent chart values.yaml (valid subchart delegation pattern)
2. xfail(strict=False) absorbs all failure modes (intentional per WU2-AC5)
3. Test file placement correct (unit/ and e2e/)
4. No orphaned files detected
5. No circular imports

## Re-run After Fix: PASS

- **BLOCK**: 0 (2 resolved)
- **WARN**: 2
- **INFO**: 5

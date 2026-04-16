# Plan: In-Cluster Runner as Default Path

## Task Breakdown

### Task 1: DevPod-aware image loading and dbt fix

**AC covered**: AC-1, AC-7

Extend the existing `testing/ci/test-e2e-cluster.sh` image loading section (lines 67-76)
with environment auto-detection. Also fix the Dockerfile dbt install path for non-root
user accessibility.

```bash
# Signature for auto-detection function
load_image() {
    local image_name: str
    local method: str  # kind | devpod | skip | auto
    # Returns: 0 on success, 1 on failure
}
```

**File change map**:
- `testing/ci/test-e2e-cluster.sh` — replace hardcoded `kind load` with `load_image()` function
- `testing/Dockerfile` — fix dbt install path (install to `/usr/local/bin/` directly or chmod)

### Task 2: Full E2E orchestrator script

**AC covered**: AC-2, AC-5

Create `testing/ci/test-e2e-full.sh` that sequences standard and destructive suites.

**File change map**:
- `testing/ci/test-e2e-full.sh` — new file

### Task 3: Makefile target reorganization

**AC covered**: AC-3

Update Makefile E2E targets. Rename old `test-e2e` to `test-e2e-host`, make new
`test-e2e` call `test-e2e-cluster.sh`, add `test-e2e-full`.

**File change map**:
- `Makefile` — update targets (lines 129-161)

### Task 4: Hook update and error handling

**AC covered**: AC-4, AC-6

Update `.claude/hooks/check-e2e-ports.sh` to allow in-cluster execution. Audit all
scripts for error handling compliance.

**File change map**:
- `.claude/hooks/check-e2e-ports.sh` — add in-cluster bypass
- `testing/ci/test-e2e-cluster.sh` — error handling audit
- `testing/ci/test-e2e-full.sh` — error handling (part of Task 2)

## Architecture Decisions

- Auto-detection order: Kind first (fast), then DevPod, then fail-fast. Kind is checked
  first because it's the more common local development path.
- `IMAGE_LOAD_METHOD` override exists for CI and edge cases.
- `FORCE_DESTRUCTIVE` flag allows running destructive tests even after standard failures
  (useful for debugging destructive tests in isolation).

## Dependencies

- This unit has no dependencies on other units.
- Units 2 (observability) and 3 (security) depend on this unit's Makefile structure.

## As-Built Notes

### Plan Deviations

- **Artifact filenames**: Plan did not specify artifact naming. Post-build review found
  that both suites would overwrite `e2e-output.log`. Fixed by prefixing with `${TEST_SUITE}`
  (e.g., `e2e-output.log` → `e2e-destructive-output.log`).
- **dbt install method**: Plan said "fix dbt install path (install to `/usr/local/bin/`
  directly or chmod)". Initial implementation used `chmod + symlink` but symlink traversal
  is blocked by `/root/` permissions (`0700`). Changed to `cp` (copy binary directly).
- **Pod cleanup failure mode**: Plan did not specify behavior when pod cleanup times out.
  Post-build review added `exit 1` on timeout to prevent PVC RWO conflicts.

### Implementation Decisions

- `load_image()` auto-detection order: Kind → DevPod → fail-fast. Kind checked first
  because it's the more common local path and the check is instant.
- `test-e2e-full.sh` passes `SKIP_BUILD=true` to Phase 2 since the image was already
  built in Phase 1.
- Hook bypass uses `INTEGRATION_TEST_HOST=k8s` (existing env var) rather than introducing
  a new variable.

### Actual File Paths

| Planned | Actual | Notes |
|---------|--------|-------|
| `testing/ci/test-e2e-cluster.sh` | Same | Extended, not replaced |
| `testing/ci/test-e2e-full.sh` | Same | New file |
| `Makefile` | Same | Updated targets |
| `.claude/hooks/check-e2e-ports.sh` | Same | Updated bypass |
| `testing/Dockerfile` | Same | dbt copy fix |

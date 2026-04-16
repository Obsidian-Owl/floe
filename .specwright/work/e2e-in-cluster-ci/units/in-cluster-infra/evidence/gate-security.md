# Gate: Security

**Status**: PASS (0 BLOCK, 5 WARN, 6 INFO)
**Timestamp**: 2026-03-29T04:50:00Z

## Findings

### WARN-1: POLARIS_CREDENTIAL hardcoded in Job manifests
- **File**: `testing/k8s/jobs/test-e2e.yaml:67`, `test-e2e-destructive.yaml:67`
- **Detail**: Plaintext `demo-admin:demo-secret` instead of secretKeyRef
- **Disposition**: Pre-existing codebase-wide pattern for demo credentials (pragma: allowlist secret). Test-only, Kind cluster scoped.

### WARN-2: kubectl downloaded without checksum verification
- **File**: `testing/Dockerfile:24-27`
- **Detail**: Pre-existing. HTTPS+TLS1.2 enforced but no SHA256 check.

### WARN-3: Pipe-to-shell for dbt CLI install
- **File**: `testing/Dockerfile:44`
- **Detail**: Pre-existing. weekly.yml does download-first pattern correctly.

### WARN-4: uv binary from unpinned `latest` tag
- **File**: `testing/Dockerfile:20`
- **Detail**: Pre-existing. Non-reproducible builds.

### WARN-5: Silent RBAC/PVC apply failures → FIXED
- **File**: `testing/ci/test-integration.sh:110-116`
- **Detail**: Was `2>/dev/null || true`. Fixed to fail-fast with error messages.

### INFO findings (no action needed)
- RBAC secrets read (justified for Helm state), RBAC secrets CRUD (justified for destructive tests), pods/exec (justified for psql test), no GHA interpolation issues, non-root user configured correctly, no image scanning (low risk for test image).

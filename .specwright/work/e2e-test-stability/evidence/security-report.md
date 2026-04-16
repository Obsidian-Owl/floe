# Security Gate Report

**Work Unit**: e2e-test-stability
**Timestamp**: 2026-03-31T11:25:00Z
**Verdict**: WARN

## Phase 1: Secret Detection — PASS

No leaked secrets, API keys, tokens, or private keys found in changed files.
- `demo-secret` in `demo/manifest.yaml:53` has `# pragma: allowlist secret` — local dev credential, not production.
- `.vuln-ignore` contains only CVE identifiers, no sensitive data.

## Phase 2: Injection Patterns — WARN

### WARN: Dockerfile $FLOE_PLUGINS loop lacks input validation
- **File**: `docker/dagster-demo/Dockerfile:106`
- **What**: `for pkg in $FLOE_PLUGINS` iterates over build-arg without validating plugin names against an allowlist.
- **Impact**: LOW — build-time only, trusted CI context, not user-facing.
- **Remediation**: Add plugin name allowlist validation in the loop.

### WARN: Remote kubeconfig written without exec plugin filtering
- **File**: `scripts/devpod-sync-kubeconfig.sh:91`
- **What**: Kubeconfig from remote DevPod written to disk without filtering `exec:` credential plugin entries.
- **Impact**: LOW — DevPod is a trusted development environment, not production.
- **Remediation**: Document trust assumption or add sanitization step.

## Phase 3: Logical Security — PASS

No fail-open error handling, error data leakage, or missing auth patterns found.
Shell scripts redirect errors to stderr correctly.

# Gate: Security Report

**Generated**: 2026-04-07T09:10:00Z
**Status**: WARN

## Findings

### Pre-existing (not introduced by this unit)

| # | Severity | Finding | Location |
|---|----------|---------|----------|
| S-1 | HIGH | Secrets RBAC over-permissioned (`list`+`watch` on all secrets) | `testing/k8s/rbac/e2e-test-runner.yaml:53-54` |
| S-2 | HIGH | Destructive runner has full secrets CRUD without `resourceNames` | `testing/k8s/rbac/e2e-destructive-runner.yaml:47-49` |
| S-3 | MEDIUM | Plain HTTP for in-cluster services (no mTLS) | Both Job manifests |
| S-4 | INFO | `imagePullPolicy: IfNotPresent` with `latest` tag | Both Job manifests |

### Introduced by this unit

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| S-5 | MEDIUM | `LOG_TAIL_LINES` not validated as numeric | Accepted — `kubectl --tail` rejects non-numeric |
| S-6 | INFO | No checksum verification on `kubectl cp` artifacts | Accepted — CI-internal |

## Verdict

WARN — no new critical/high issues introduced. S-1 and S-2 are pre-existing
RBAC issues tracked for unit 3 (security-hardening).

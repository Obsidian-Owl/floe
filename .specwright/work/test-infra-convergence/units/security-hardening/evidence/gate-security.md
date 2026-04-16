# Gate: Security

**Status**: PASS

## Bandit Scan

Command: `bandit -r` across the 6 new test files for this unit.

| Severity | Count |
|----------|-------|
| High | 0 |
| Medium | 0 |
| Low | 78 |

All Low findings are `assert_used` (B101) — expected and standard in pytest files.
No Medium or High severity findings.

## Secret / Credential Review

- No hardcoded credentials in any changed file.
- `tests/contract/test_rbac_least_privilege.py` references Helm release secret
  name prefixes (`sh.helm.release.v1.*`) — these are K8s resource names, not secrets.
- `.specwright/AUDIT.md` SEC-001 entry is descriptive (no secret material).

## Notes

This unit's primary purpose IS a security hardening — every change
narrows capabilities rather than widening them:
- Dropped secrets list/watch on standard runner (AC-8)
- Scoped update/delete via resourceNames on destructive runner (AC-9)
- Enforced PSS restricted profile on Dagster/OTel/Jaeger/MinIO workloads (AC-1, AC-2, AC-3)
- Marquez exemption explicitly documented with upstream tracker (AC-10)

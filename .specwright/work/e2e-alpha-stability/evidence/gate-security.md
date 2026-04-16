# Gate: Security

**Status**: WARN
**Timestamp**: 2026-03-28T04:45:00Z

## Results

0 Critical, 3 High, 4 Medium, 2 Low findings.

## Findings

| Severity | Count |
|----------|-------|
| BLOCK | 0 |
| WARN | 3 |
| INFO | 6 |

### WARN-1: Overly broad NOPASSWD sudoers — `/bin/sh` grants root shell

- **File**: `.devcontainer/Dockerfile:95`
- **CWE**: CWE-269 (Improper Privilege Management)
- **Action**: Replace bare `/bin/sh` with dedicated wrapper script

### WARN-2: `docker exec --privileged` on Kind control-plane

- **File**: `testing/k8s/setup-cluster.sh:104-108`
- **CWE**: CWE-250 (Execution with Unnecessary Privileges)
- **Action**: Drop `--privileged` flag — kubectl doesn't need kernel capabilities

### WARN-3: Credential values in assertion messages

- **File**: `tests/e2e/test_dbt_e2e_profile.py:442`
- **CWE**: CWE-532 (Information Exposure Through Log Files)
- **Action**: Remove credential interpolation from assertion failure messages

### Positive Changes (INFO)

- TOCTOU race eliminated (CWE-367 fix)
- TLS with cluster CA (not --insecure)
- Minimal RBAC + hardened security context
- Supply chain reduction (bitnami/kubectl removed)

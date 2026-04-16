# Security Gate Evidence

**Branch**: feat/e2e-production-fixes
**Date**: 2026-03-27
**Gate**: security
**Status**: PASS

## 1. Bandit Scan

**Changed Python files**: `tests/e2e/test_observability.py`

**Result**: Only B101 (assert_used) findings, all Low severity.
These are expected in test files -- pytest uses `assert` statements as the standard assertion mechanism.

**Verdict**: PASS -- no Medium or High severity findings.

## 2. Hardcoded Credentials Check

**Files scanned**: All changed files (Python, YAML, Makefile, .gitignore, JSON)

**Checks performed**:
- Grep for password/secret/api_key/token patterns in Python diff: **no matches**
- Grep for hardcoded password values in YAML diff: **no matches**
- Chart template references to Secret resources are standard K8s patterns (secretRef, imagePullSecrets), not hardcoded values

**Verdict**: PASS -- no hardcoded credentials found.

## 3. Shell Injection Check

**Changed shell scripts**: None (no .sh or .bash files changed)

**Additional checks**:
- Helm template changes: no `eval`, `exec`, or `shell` patterns in added lines
- Python file: no `subprocess`, `shell=True`, or `eval` usage
- Existing chart comment at `job-polaris-bootstrap.yaml:298` explicitly documents why eval is avoided (case dispatch pattern per P31)

**Verdict**: PASS (N/A -- no shell scripts changed)

## 4. pip-audit

**Findings** (3 known vulnerabilities, all pre-existing):

| Package | Version | CVE | Severity | Status |
|---------|---------|-----|----------|--------|
| pip | 25.3 | CVE-2026-1703 | Moderate | Pre-existing, path traversal limited to install prefixes |
| pygments | 2.19.2 | CVE-2026-4539 | Low | Local-only ReDoS, no upstream fix available |
| requests | 2.32.5 | CVE-2026-25645 | Moderate | Documented in pyproject.toml -- floe never calls `extract_zipped_paths()`, fix blocked by datacontract-cli pin |

**None of these vulnerabilities were introduced by this branch**. The `requests` CVE is explicitly documented with rationale in `pyproject.toml` (added in this branch as documentation of pre-existing state, with ignore entry and tracking comment).

**Verdict**: PASS -- no new vulnerabilities introduced, pre-existing issues documented.

## Summary

```
GATE: security
STATUS: PASS
FINDINGS:
- [INFO] Bandit: Only B101 (assert_used) in test file -- expected for pytest
- [INFO] No hardcoded credentials in any changed files
- [INFO] No shell scripts changed; no shell injection vectors in Helm changes
- [INFO] pip-audit: 3 pre-existing CVEs, none introduced by this branch
- [INFO] requests CVE-2026-25645 documented with rationale and ignore entry in pyproject.toml
```

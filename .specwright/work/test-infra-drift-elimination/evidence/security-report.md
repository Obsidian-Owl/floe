# Gate: Security

**Status**: PASS
**Timestamp**: 2026-04-08

## Scope
Changed files in work unit `test-infra-drift-elimination`:
- Python: `tests/contract/test_test_infra_chart_integrity.py`, `tests/unit/test_observability_manifests.py`, `tests/contract/test_rbac_least_privilege.py`
- Shell: `testing/ci/common.sh`, `testing/ci/test-*.sh`
- Helm: `charts/floe-platform/templates/tests/*.yaml`, `_helpers.tpl`

## Scanners
### Bandit (Python)
`bandit -ll -r tests/contract/test_test_infra_chart_integrity.py tests/unit/test_observability_manifests.py`
→ **0 issues at medium+ severity**

Low-severity findings are standard `assert` usage in pytest tests (B101), which
is the intended test style for this project. Not actionable.

### Chart-level security (AC-8 carry-forward)
The contract test `test_test_runner_rbac_rendered_from_chart` asserts the
standard runner Role's `secrets` verb list is `["get"]` only (no `list`/`watch`),
preserving the least-privilege invariant from the prior security-hardening work.

### Shell scripts
`common.sh` uses `set -uo pipefail` and strict quoting. No `eval`, no dynamic
`$(…)` over untrusted input, no credentials interpolated.

## Credential hygiene
No credentials introduced in this work unit. Chart continues to use
`secretKeyRef` for all sensitive values.

## Verdict
PASS.

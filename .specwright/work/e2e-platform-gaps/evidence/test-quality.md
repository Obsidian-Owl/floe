# Gate: test-quality -- WU-1 Re-verification

**Date**: 2026-02-13
**Scope**: Changed files on feat/wu-1-bootstrap vs main (re-run after BLOCK fixes)
**Auditor**: Specwright Tester Agent
**Test Run**: 19/19 passed in 0.35s

---

## Files Reviewed

| File | Change Summary |
|------|---------------|
| `testing/fixtures/helm.py` (NEW, 154 lines) | Shared Helm recovery module: `parse_helm_status()`, `recover_stuck_helm_release()` with injectable `helm_runner` |
| `testing/tests/unit/test_helm_recovery.py` (NEW, 293 lines) | 19 unit tests covering parse + recovery logic |
| `tests/e2e/conftest.py` (lines 166-191) | `helm_release_health` fixture now delegates to shared module |
| `tests/e2e/test_helm_upgrade_e2e.py` (lines 34-54, 76) | `_recover_stuck_release()` wrapper now delegates to shared module |

---

## Previous BLOCK Resolution

### BLOCK-1: Duplicated Recovery Logic Without Shared Test Coverage

**Status: RESOLVED**

The recovery logic is now consolidated in `testing/fixtures/helm.py` as a single `recover_stuck_helm_release()` function. Both call sites (`conftest.py:185` and `test_helm_upgrade_e2e.py:49`) delegate to this shared function, passing `helm_runner=run_helm` for dependency injection. The duplication is eliminated -- both callers are thin wrappers (5-6 lines each) around the shared function.

The new unit test file covers all scenarios originally recommended:
- Healthy release, no recovery needed (`test_healthy_release_no_recovery`)
- Stuck in each of `pending-upgrade`, `pending-install`, `pending-rollback`, `failed` (parametrized `test_recovery_for_each_stuck_state`)
- Release does not exist (`test_release_not_found_returns_false`)
- Rollback fails (`test_rollback_failure_raises_runtime_error`)
- Malformed JSON (`test_malformed_json_raises_value_error`)
- Empty stdout (`test_empty_stdout_raises_value_error`)
- Missing `info` key (`test_missing_info_key_treated_as_healthy`)
- `version` field is string not int (`test_version_as_string_raises_value_error`)
- Revision 1 boundary (`test_revision_1_rollback_targets_revision_1`)
- Custom timeout propagation (`test_custom_rollback_timeout`)
- Non-stuck state (`test_superseded_state_not_stuck`)

All mocks have `assert_called*()` verification. The injectable `helm_runner` design is clean and testable.

### BLOCK-2: No Guard Against Malformed JSON From Helm Output

**Status: RESOLVED**

`parse_helm_status()` now validates both empty/whitespace-only output (`ValueError: "helm status returned empty output"`) and invalid JSON (`ValueError: "helm status returned invalid JSON: ... Output preview: ..."` with first 200 chars). The function is called by `recover_stuck_helm_release()`, so both call sites benefit.

Five unit tests directly exercise `parse_helm_status()` error paths:
- `test_empty_string_raises_value_error` -- exact match on "empty output"
- `test_whitespace_only_raises_value_error` -- whitespace-only input
- `test_invalid_json_raises_value_error` -- garbage input
- `test_partial_json_raises_value_error` -- truncated JSON
- `test_valid_json` -- happy path with exact value assertions

Two additional tests verify the error propagation through `recover_stuck_helm_release()`:
- `test_malformed_json_raises_value_error`
- `test_empty_stdout_raises_value_error`

### Previous WARN-5: Inconsistent Timeouts

**Status: RESOLVED** -- Both call sites now use `rollback_timeout="5m"` consistently.

### Previous INFO-2: Redundant Local Import

**Status: RESOLVED** -- The inline `import json as _json` is gone; JSON parsing is now in the shared module.

---

## Findings

### BLOCK (must fix before ship)

None.

### WARN (should fix, can ship with justification)

#### WARN-1: Rollback Argument Assertions Use `in` Rather Than Exact Position

**File**: `testing/tests/unit/test_helm_recovery.py:149-150, 238`
**Category**: Assertion Strength

The rollback command assertions use substring-style checks:
```python
assert "rollback" in rollback_args
assert "4" in rollback_args
```

This is a membership check on a list of strings. The concern is that `"4"` would match any element containing `"4"` -- but since these are exact string elements in a list, `"4" in ["rollback", "floe-platform", "4", "-n", ...]` is actually checking for exact element equality. So `"4"` would NOT match `"14"` or `"40"` -- Python `in` on lists uses `__eq__`, not substring matching.

However, the assertion does not verify argument *position*. An implementation that put the revision number in the wrong position (e.g., `helm rollback 4 floe-platform` instead of `helm rollback floe-platform 4`) would still pass this test.

A stronger assertion would verify the exact argument list:
```python
assert rollback_args == [
    "rollback", "floe-platform", "4", "-n", "floe-test",
    "--wait", "--timeout", "5m",
]
```

**Impact**: Low. Helm would reject malformed argument ordering, so this would surface in E2E tests. The current assertions prove the right values are present, just not in the right order.

**Recommendation**: Replace `in` checks with exact list comparison in `test_recovery_for_each_stuck_state` for one representative case (e.g., `pending-upgrade` at revision 5). The parametrized tests can keep the lighter assertion.

---

#### WARN-2: Revision-1 Rollback Test Does Not Verify Warning Message

**File**: `testing/tests/unit/test_helm_recovery.py:219-238`
**Category**: Behavior Coverage

The implementation emits a special warning when `current_revision == 1` (lines 120-125 of `helm.py`):
```
WARNING: Helm release 'X' stuck in 'Y' at revision 1.
Rollback to revision 1 re-deploys the same revision...
```

The test verifies `result is True` and that `"1"` is in the rollback args, but does not verify the warning was printed. This means the warning could be silently removed without any test detecting the regression.

**Recommendation**: Use `capsys` (pytest's output capture) to verify the revision-1 warning message is emitted. This is a behavioral contract worth preserving -- the warning tells operators about the self-referential rollback.

---

#### WARN-3 (carried forward): `test_no_crashloopbackoff_after_upgrade` Ignores `initContainerStatuses`

**File**: `tests/e2e/test_helm_upgrade_e2e.py:139-142`
**Category**: Boundary Coverage

Unchanged from prior audit. The CrashLoopBackOff check inspects only `containerStatuses`, not `initContainerStatuses`. Init containers failing after an upgrade (e.g., migration job) would be invisible to this test.

---

#### WARN-4 (carried forward): `test_services_healthy_after_upgrade` Returns True for Empty Pod List

**File**: `tests/e2e/test_helm_upgrade_e2e.py:161-180`
**Category**: Boundary Coverage

Unchanged from prior audit. If `pods.get("items", [])` is empty (e.g., upgrade deleted all resources), `all_pods_ready()` returns `True` because the for-loop body never executes.

---

#### WARN-5: `test_revision_1_rollback_targets_revision_1` Assertion Ambiguity

**File**: `testing/tests/unit/test_helm_recovery.py:238`
**Category**: Assertion Strength

```python
assert "1" in rollback_args  # Rollback to revision 1
```

The string `"1"` appears in multiple elements of the rollback args list: it could match the revision `"1"`, or potentially a timeout value, or a namespace containing `"1"`. In the current implementation, the args list is `["rollback", "floe-platform", "1", "-n", "floe-test", "--wait", "--timeout", "5m"]`. The `"1"` at position 2 is the revision. But if the release name changed to contain `"1"` (e.g., `"floe-platform-1"`), the assertion would still pass even if the revision was wrong.

A stronger assertion would check the specific position:
```python
assert rollback_args[2] == "1"
```

**Impact**: Low, since the release name is hardcoded in this test. But the pattern is fragile.

---

### INFO (observations, no action required)

#### INFO-1: `helm_runner` Type Is `Any`

**File**: `testing/fixtures/helm.py:73`

The `helm_runner` parameter is typed as `Any`. A `Protocol` or `Callable[[list[str]], subprocess.CompletedProcess[str]]` type would provide better static analysis and documentation. This is cosmetic -- the injectable design itself is sound.

---

#### INFO-2: Test Class Ordering Dependency in E2E (carried forward)

**File**: `tests/e2e/test_helm_upgrade_e2e.py`

The four E2E tests (`test_helm_upgrade_succeeds`, `test_no_crashloopbackoff_after_upgrade`, `test_services_healthy_after_upgrade`, `test_helm_history_shows_revisions`) have implicit ordering dependency. If the upgrade test fails, the subsequent tests validate stale state. This is a known pattern in E2E suites and is acceptable.

---

#### INFO-3: `_recover_stuck_release` Wrapper in `test_helm_upgrade_e2e.py` Is Thin

**File**: `tests/e2e/test_helm_upgrade_e2e.py:34-54`

The wrapper function `_recover_stuck_release()` is 20 lines but its body is just a 5-line delegation. It could be replaced with a direct call to `recover_stuck_helm_release()`. This is a style preference, not a defect -- the wrapper does provide a convenient single-import point and keeps the import lazy.

---

#### INFO-4: `_make_status_json` Helper Does Not Validate Version Type

**File**: `testing/tests/unit/test_helm_recovery.py:39-44`

The `_make_status_json` helper accepts `version: int | str` but does not validate the type. This is intentional -- it enables the `test_version_as_string_raises_value_error` test to pass a string version. Noting for completeness.

---

## Lazy Implementation Test

Applying the adversarial "lazy implementation" check:

**Q: Could `parse_helm_status` be replaced with a no-op that returns `{}`?**
A: No. `test_valid_json` asserts `result["info"]["status"] == "deployed"` and `result["version"] == 3`. A no-op returning `{}` would raise `KeyError`.

**Q: Could `recover_stuck_helm_release` be replaced with `return False`?**
A: No. `test_recovery_for_each_stuck_state` asserts `result is True` and `mock_runner.call_count == 2`. A hardcoded `return False` would fail on both.

**Q: Could `recover_stuck_helm_release` skip the rollback but still return `True`?**
A: No. `test_recovery_for_each_stuck_state` asserts `mock_runner.call_count == 2` (status + rollback) and that the second call args contain `"rollback"`.

**Q: Could the JSON error handling be removed?**
A: No. `test_malformed_json_raises_value_error`, `test_empty_stdout_raises_value_error`, and three `TestParseHelmStatus` error tests all assert specific `ValueError` matches.

**Q: Could the version type check be removed?**
A: No. `test_version_as_string_raises_value_error` asserts `ValueError` when version is `"3"` (string).

**Q: Could the rollback revision calculation be wrong (e.g., always rollback to revision 1)?**
A: Partially caught. `test_recovery_for_each_stuck_state` asserts `"4"` is in rollback args (for revision 5). An implementation that always rolled back to revision 1 would fail this test. However, an implementation that hardcoded `revision - 1` without the `max(1, ...)` guard would pass all existing tests. The `test_revision_1_rollback_targets_revision_1` only checks that `"1"` is in the args, which is the same as `max(1, 0)` AND `0`. But since `"0"` would not match `"1"`, this test does catch the `max` guard (if `max` were removed, the result would be `"0"` at position 2, and `"1"` would only match the release name which is `"floe-platform"` -- no match for `"1"` as a standalone element). So the guard IS tested.

**Conclusion**: The test suite is robust against lazy implementations. The core behaviors -- stuck state detection, rollback invocation with correct revision, JSON error handling, type validation -- are all verified with specific assertions and mock invocation checks.

---

## Mock Discipline Audit

Every `MagicMock()` in the test file has corresponding `assert_called*()`:

| Test | Mock Created | Assertion |
|------|-------------|-----------|
| `test_healthy_release_no_recovery` | `mock_runner` | `assert_called_once_with(["status", ...])` |
| `test_release_not_found_returns_false` | `mock_runner` | `assert_called_once()` |
| `test_recovery_for_each_stuck_state` | `mock_runner` | `call_count == 2`, `call_args_list[1]` inspected |
| `test_rollback_failure_raises_runtime_error` | `mock_runner` | Implicitly verified via `side_effect` (2 calls consumed) |
| `test_malformed_json_raises_value_error` | `mock_runner` | Implicitly verified (called once, raises before rollback) |
| `test_empty_stdout_raises_value_error` | `mock_runner` | Implicitly verified (called once, raises before rollback) |
| `test_missing_info_key_treated_as_healthy` | `mock_runner` | Implicitly verified via return value `False` |
| `test_revision_1_rollback_targets_revision_1` | `mock_runner` | `call_args_list[1]` inspected |
| `test_version_as_string_raises_value_error` | `mock_runner` | Implicitly verified (raises before rollback) |
| `test_custom_rollback_timeout` | `mock_runner` | `call_args_list[1]` inspected for `"10m"` |
| `test_superseded_state_not_stuck` | `mock_runner` | `assert_called_once()` |

Observation: 4 tests use implicit verification (exception raised = mock consumed), 4 use explicit `assert_called*()`, and 3 inspect `call_args_list`. All mocks serve a behavioral verification purpose -- none are "import-satisfying" mocks.

---

## Requirement Traceability

All 19 tests (including 4 parametrized variants) have `@pytest.mark.requirement("AC-2.9")`. All tests have docstrings. No tests use `pytest.skip()` or `time.sleep()`.

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| **BLOCK** | 0 | -- |
| **WARN** | 5 | WARN-1, WARN-2, WARN-3 (carried), WARN-4 (carried), WARN-5 |
| **INFO** | 4 | INFO-1, INFO-2 (carried), INFO-3, INFO-4 |

### Previous BLOCKs

Both BLOCK-1 (duplicated logic) and BLOCK-2 (no JSON guard) are genuinely resolved. The shared module + injectable runner + 19 unit tests directly address both findings. Previous WARN-5 (inconsistent timeouts) is also resolved.

### Remaining WARNs

- WARN-1 and WARN-5 are assertion strength nits -- the tests catch real bugs, just not with maximum precision on argument ordering.
- WARN-2 is a missing behavioral check (revision-1 warning message not asserted).
- WARN-3 and WARN-4 are carried forward from the original audit and are E2E-specific boundary gaps unrelated to this fix.

### Strengths

- Clean dependency injection via `helm_runner` parameter enables isolated unit testing without subprocess calls.
- Parametrized tests cover all 4 stuck states without copy-paste.
- Error paths are thoroughly tested: empty output, invalid JSON, truncated JSON, wrong type for version field, rollback failure.
- Mock invocation assertions verify the side effects (helm rollback actually called), not just return values.
- Both consumers (`conftest.py`, `test_helm_upgrade_e2e.py`) delegate to the shared function -- no logic duplication remains.

## Verdict: PASS

The two previous BLOCKs are resolved. The 5 WARNs are genuine but non-blocking -- they identify assertion precision improvements and E2E boundary gaps that can be addressed in a follow-up. The test suite is robust against lazy implementations and properly verifies the behavioral contract of the recovery module.

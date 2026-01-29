# Draft: Test Infrastructure Improvement

## Verified Issues

### Issue 1: Contract Test Mock Mismatch (CRITICAL) ✅ VERIFIED
- **File**: `tests/contract/test_orchestrator_plugin_abc.py`
- **ABC signature** (line 329): `emit_lineage_event(self, event_type, job_name, ...)` - uses `job_name`
- **Test assertion** (line 165): `assert "job_name" in params` - CORRECT
- **Mock implementation** (line 362-369): Uses `job` instead of `job_name` - **THIS IS THE BUG**
- **Fix**: Update mock parameter from `job` → `job_name`

### Issue 2: Sigstore Browser Auth (HIGH) ✅ VERIFIED
- **File**: `packages/floe-core/src/floe_core/oci/signing.py`
- SigningClient uses sigstore-python for keyless signing
- `_get_identity_token()` attempts OIDC token acquisition
- When run outside CI/CD (no ambient OIDC), sigstore-python falls back to browser OAuth
- Integration tests in `test_signing_e2e.py` do REAL auth - can trigger browser popup locally
- **Fix**: Add environment guard to prevent interactive auth in tests

### Issue 3: Test Path Configuration (MEDIUM) ✅ VERIFIED
- **File**: `pyproject.toml` lines 84-106
- Already uses `--import-mode=importlib` (good)
- `pythonpath` has 14 explicit paths - brittle
- Tests must be run from repo root
- **Fix**: Consolidate path configuration, add environment guards

### Issue 4: Test Infrastructure Gaps (MEDIUM) ✅ VERIFIED
- **63 conftest.py files** found across the monorepo
- Marker definitions duplicated (root pyproject.toml + individual conftest files)
- No socket-level blocking for external requests
- Integration test conftest.py is minimal

## Requirements Confirmed

1. **Immediate**: Fix contract test mock (line 362: `job` → `job_name`)
2. **Immediate**: Prevent sigstore browser auth in tests/local dev
3. **Short-term**: Improve test path configuration
4. **Medium-term**: Standardize test infrastructure (markers, conftest, fixtures)
5. **Long-term**: Make testing easy for all developers

## Constraints Confirmed
- Maintain backward compatibility with existing tests
- CI/CD integration tests should still work
- Don't break any existing passing tests
- Follow existing codebase patterns

## Research Findings (User-Provided)
1. Use `--import-mode=importlib` (already configured)
2. Register all markers at root level only
3. Socket-level blocking for external requests
4. Add environment guards for interactive auth
5. ABC contract tests should use inheritance pattern

## User Decisions
- Include cleanup of __init__.py files: YES
- Auth guard strategy: Environment variable (FLOE_SIGNING_ALLOW_INTERACTIVE)

## Metis Corrections (CRITICAL)
1. **__init__.py count is ~8 files, NOT 357** - Exclude .venv and /testing/ directories
2. **Marker duplication is in 18 pyproject.toml files**, not conftest files
3. **Must validate contract test actually fails** before fixing
4. **DO NOT touch /testing/ directory** - has real infrastructure code

## Guardrails (from Metis)
- ONLY delete empty __init__.py files (not /testing/*, not .venv/*)
- ONLY change `job` → `job_name` at line 365
- Socket blocking: ONLY for unit tests, allow network for integration/e2e
- Sigstore guard: Default to BLOCKING (opt-in for interactive)

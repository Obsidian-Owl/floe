# Test Infrastructure Fix Plan

## TL;DR

> **Quick Summary**: Fix critical test failures, prevent browser OAuth in tests, and standardize test infrastructure across the floe monorepo.
> 
> **Deliverables**:
> - Fixed contract test (mock signature alignment)
> - Browser OAuth guard in signing module
> - Improved error messages for test path issues
> - Consolidated conftest patterns
> - Testing conventions documentation
> 
> **Estimated Effort**: Medium (2-3 days)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 → Task 3 → Task 6

---

## Context

### Original Request
Fix test infrastructure issues in floe monorepo including:
1. Contract test failure (ABC signature mismatch)
2. Sigstore browser OAuth triggering in tests
3. Test path configuration issues
4. Test infrastructure gaps (duplicate markers, missing fixtures)

### Interview Summary
**Key Discussions**:
- User prioritized issues: CRITICAL (contract test) → HIGH (browser auth) → MEDIUM (path/infra)
- Test infrastructure exists (pytest with custom markers)
- 63 conftest.py files identified across monorepo
- E2E tests requiring Kind cluster are out of scope

**Research Findings**:
- Contract test line 165 assertion is CORRECT (`job_name`), mock at lines 362-369 is WRONG
- Mock uses `job: str` but ABC expects `job_name: str`, plus missing 5 parameters
- Signing module has existing env var pattern (`FLOE_OIDC_TOKEN_MAX_RETRIES`)
- OAuth fallback at `_attempt_token_acquisition()` line 632

---

## Work Objectives

### Core Objective
Restore test suite reliability and prevent interactive auth from blocking test runs.

### Concrete Deliverables
- `tests/contract/test_orchestrator_plugin_abc.py` - Fixed mock implementation
- `packages/floe-core/src/floe_core/oci/signing.py` - Browser OAuth guard
- `tests/conftest.py` - Enhanced with PYTHONPATH check and clear error messages
- `docs/testing/CONVENTIONS.md` - Testing conventions documentation

### Definition of Done
- [ ] `pytest tests/contract/test_orchestrator_plugin_abc.py` passes
- [ ] `FLOE_DISABLE_BROWSER_OAUTH=true pytest tests/` prevents browser auth
- [ ] Running tests from wrong directory shows helpful error message
- [ ] All 673+ passing tests remain passing

### Must Have
- Contract test fix with correct ABC signature
- Environment variable guard for browser OAuth
- No regressions in existing passing tests

### Must NOT Have (Guardrails)
- Do NOT change the ABC signature itself (only fix test mock)
- Do NOT remove any existing tests
- Do NOT modify E2E test infrastructure (Kind cluster requirements)
- Do NOT consolidate all 63 conftest files (too invasive)
- Do NOT add new test coverage (fixing existing only)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest with custom markers)
- **User wants tests**: YES (TDD for new code)
- **Framework**: pytest with existing patterns

### Automated Verification

Each TODO includes executable verification commands:
- Contract test: `pytest tests/contract/test_orchestrator_plugin_abc.py -v`
- Signing guard: `FLOE_DISABLE_BROWSER_OAUTH=true pytest packages/floe-core/tests/unit/oci/test_signing.py -v -k browser`
- Full suite: `pytest tests/ packages/ --ignore=tests/e2e -x`

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: Fix contract test mock (CRITICAL)
└── Task 2: Add browser OAuth guard (HIGH)

Wave 2 (After Wave 1):
├── Task 3: Add unit tests for OAuth guard
├── Task 4: Improve PYTHONPATH error messages
└── Task 5: Document env vars in README

Wave 3 (After Wave 2):
└── Task 6: Create testing conventions doc
└── Task 7: Final verification and cleanup
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 7 | 2 |
| 2 | None | 3, 5 | 1 |
| 3 | 2 | 7 | 4, 5 |
| 4 | None | 6 | 3, 5 |
| 5 | 2 | 6 | 3, 4 |
| 6 | 4, 5 | 7 | None |
| 7 | 1, 3, 6 | None | None |

---

## TODOs

### Wave 1: Critical Fixes

- [ ] 1. Fix contract test mock implementation

  **What to do**:
  - Update `emit_lineage_event` mock at lines 362-369 to match ABC signature
  - Add missing imports: `UUID`, `RunState`, `LineageDataset`
  - Update method signature with all 9 parameters
  - Return a mock UUID instead of None

  **Must NOT do**:
  - Do NOT modify the ABC definition in `orchestrator.py`
  - Do NOT change other test methods in the file

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file edit with clear before/after, no architectural decisions
  - **Skills**: [`testing`]
    - `testing`: Understands test patterns and pytest conventions

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Task 7
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `packages/floe-core/src/floe_core/plugins/orchestrator.py:328-340` - ABC signature to match exactly
  - `tests/contract/test_orchestrator_plugin_abc.py:362-369` - Current mock to replace

  **Type References**:
  - `packages/floe-core/src/floe_core/lineage/__init__.py` - `LineageDataset`, `RunState` exports
  - `uuid.UUID` - Standard library UUID for return type

  **Test References**:
  - `tests/contract/test_orchestrator_plugin_abc.py:150-167` - Assertion that validates signature

  **Acceptance Criteria**:

  ```bash
  # Agent runs:
  pytest tests/contract/test_orchestrator_plugin_abc.py::TestOrchestratorPluginSignatureContract -v
  # Assert: All tests PASS
  # Assert: Exit code 0
  
  # Verify LSP clean:
  # Check file has no type errors for emit_lineage_event override
  ```

  **Evidence to Capture**:
  - [ ] pytest output showing all contract tests pass
  - [ ] LSP diagnostics showing no override errors

  **Commit**: YES
  - Message: `fix(tests): align contract test mock with OrchestratorPlugin ABC signature`
  - Files: `tests/contract/test_orchestrator_plugin_abc.py`
  - Pre-commit: `pytest tests/contract/test_orchestrator_plugin_abc.py -v`

---

- [ ] 2. Add browser OAuth guard in signing module

  **What to do**:
  - Add `DISABLE_BROWSER_OAUTH` constant near line 100 (following existing pattern)
  - Add guard check in `_attempt_token_acquisition()` at line 632
  - Raise `OIDCTokenError` with helpful message when guard is active
  - Log warning before raising to aid debugging

  **Must NOT do**:
  - Do NOT change the ambient credential detection logic
  - Do NOT modify retry logic or other token acquisition code
  - Do NOT make browser OAuth disabled by default (breaks local dev)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small focused change with clear insertion points
  - **Skills**: [`testing`]
    - `testing`: Understands how to make code testable

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Tasks 3, 5
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `packages/floe-core/src/floe_core/oci/signing.py:74-99` - Existing env var pattern with `_get_env_int()`
  - `packages/floe-core/src/floe_core/oci/signing.py:612-637` - `_attempt_token_acquisition()` method

  **API/Type References**:
  - `packages/floe-core/src/floe_core/oci/signing.py:OIDCTokenError` - Error class to raise

  **Documentation References**:
  - Constitution V requirement: Tests FAIL (not skip) when dependencies unavailable

  **Acceptance Criteria**:

  ```bash
  # Agent runs - verify guard works:
  FLOE_DISABLE_BROWSER_OAUTH=true python -c "
  import os
  os.environ['FLOE_DISABLE_BROWSER_OAUTH'] = 'true'
  from floe_core.oci.signing import DISABLE_BROWSER_OAUTH
  print(f'Guard active: {DISABLE_BROWSER_OAUTH}')
  assert DISABLE_BROWSER_OAUTH == True
  "
  # Assert: Output shows "Guard active: True"
  # Assert: Exit code 0
  
  # Verify no syntax errors:
  python -m py_compile packages/floe-core/src/floe_core/oci/signing.py
  # Assert: Exit code 0
  ```

  **Evidence to Capture**:
  - [ ] Python verification showing constant is correctly parsed
  - [ ] py_compile success

  **Commit**: YES
  - Message: `feat(oci): add FLOE_DISABLE_BROWSER_OAUTH guard to prevent interactive auth`
  - Files: `packages/floe-core/src/floe_core/oci/signing.py`
  - Pre-commit: `python -m py_compile packages/floe-core/src/floe_core/oci/signing.py`

---

### Wave 2: Tests and Error Messages

- [ ] 3. Add unit test for browser OAuth guard

  **What to do**:
  - Add test `test_browser_oauth_disabled_raises_error()` to existing test file
  - Mock `detect_credential()` to return None (no ambient creds)
  - Set env var `FLOE_DISABLE_BROWSER_OAUTH=true`
  - Verify `OIDCTokenError` is raised with appropriate message
  - Verify `Issuer` is never called (no browser attempt)

  **Must NOT do**:
  - Do NOT modify existing test methods
  - Do NOT test actual browser OAuth flow

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single test addition following existing patterns
  - **Skills**: [`testing`]
    - `testing`: Pytest patterns, mocking, env var handling

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5)
  - **Blocks**: Task 7
  - **Blocked By**: Task 2

  **References**:

  **Pattern References**:
  - `packages/floe-core/tests/unit/oci/test_signing.py:189-212` - Existing OAuth fallback test pattern
  - `packages/floe-core/tests/unit/oci/test_signing.py:172-187` - Ambient credential test pattern

  **Test References**:
  - `packages/floe-core/tests/unit/oci/conftest.py` - Fixtures for signing tests

  **Acceptance Criteria**:

  ```bash
  # Agent runs:
  pytest packages/floe-core/tests/unit/oci/test_signing.py -v -k "browser_oauth_disabled"
  # Assert: 1 test collected, 1 passed
  # Assert: Exit code 0
  
  # Verify test actually tests the guard:
  grep -n "FLOE_DISABLE_BROWSER_OAUTH" packages/floe-core/tests/unit/oci/test_signing.py
  # Assert: Shows env var being set in test
  ```

  **Evidence to Capture**:
  - [ ] pytest output showing new test passes
  - [ ] grep output confirming test sets env var

  **Commit**: YES
  - Message: `test(oci): add unit test for browser OAuth guard`
  - Files: `packages/floe-core/tests/unit/oci/test_signing.py`
  - Pre-commit: `pytest packages/floe-core/tests/unit/oci/test_signing.py -v`

---

- [ ] 4. Improve PYTHONPATH error messages in root conftest

  **What to do**:
  - Add early check in `tests/conftest.py` for testing module availability
  - Provide clear error message if `testing` module import fails
  - Include suggested fix: "Run from repo root with: pytest tests/"
  - Check for common mistakes (running from package directory)

  **Must NOT do**:
  - Do NOT change PYTHONPATH configuration
  - Do NOT modify package-level pyproject.toml files
  - Do NOT add hard dependencies that break existing test runs

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small enhancement to existing conftest
  - **Skills**: [`testing`]
    - `testing`: Pytest fixtures, conftest patterns

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 5)
  - **Blocks**: Task 6
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `tests/conftest.py` - Root conftest to modify
  - `pyproject.toml` - Pytest configuration with pythonpath

  **Documentation References**:
  - `testing/__init__.py` - Testing module entry point

  **Acceptance Criteria**:

  ```bash
  # Agent runs - verify helpful error from wrong directory:
  cd packages/floe-core && python -c "
  import sys
  sys.path.insert(0, 'src')
  try:
      from testing.base_classes import IntegrationTestBase
      print('ERROR: Should have failed!')
  except ImportError as e:
      print(f'Good: Import failed as expected: {e}')
  " 2>&1
  # Assert: Shows import error (expected behavior)
  
  # Verify tests still work from root:
  cd /Users/dmccarthy/Projects/floe && pytest tests/conftest.py --collect-only 2>&1 | head -5
  # Assert: No import errors
  ```

  **Evidence to Capture**:
  - [ ] Import fails gracefully from wrong directory
  - [ ] Tests collect successfully from repo root

  **Commit**: YES
  - Message: `dx(tests): add helpful error message for PYTHONPATH issues`
  - Files: `tests/conftest.py`
  - Pre-commit: `pytest tests/conftest.py --collect-only`

---

- [ ] 5. Document environment variables in README section

  **What to do**:
  - Add "Environment Variables" section to testing documentation
  - Document `FLOE_DISABLE_BROWSER_OAUTH` with use case (CI/CD)
  - Document `FLOE_OIDC_TOKEN_MAX_RETRIES` (already exists)
  - Include example CI/CD configuration snippet

  **Must NOT do**:
  - Do NOT create new markdown files (update existing)
  - Do NOT document internal implementation details

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation update, clear technical writing
  - **Skills**: []
    - No special skills needed for documentation

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 4)
  - **Blocks**: Task 6
  - **Blocked By**: Task 2

  **References**:

  **Documentation References**:
  - `packages/floe-core/README.md` - Package README to update
  - `docs/guides/` - Existing documentation structure

  **Acceptance Criteria**:

  ```bash
  # Agent runs:
  grep -n "FLOE_DISABLE_BROWSER_OAUTH" packages/floe-core/README.md
  # Assert: Shows env var documented
  
  # Verify markdown is valid:
  python -c "import re; content=open('packages/floe-core/README.md').read(); print('Headers:', len(re.findall(r'^#+', content, re.M)))"
  # Assert: No parsing errors
  ```

  **Evidence to Capture**:
  - [ ] grep showing env var is documented
  - [ ] README remains valid markdown

  **Commit**: YES
  - Message: `docs(oci): document FLOE_DISABLE_BROWSER_OAUTH environment variable`
  - Files: `packages/floe-core/README.md`
  - Pre-commit: `grep FLOE_DISABLE_BROWSER_OAUTH packages/floe-core/README.md`

---

### Wave 3: Conventions and Verification

- [ ] 6. Create testing conventions documentation

  **What to do**:
  - Create `docs/testing/CONVENTIONS.md` with:
    - Running tests (from repo root)
    - Marker usage (`@pytest.mark.integration`, `@pytest.mark.requirement`)
    - Conftest organization (when to use package vs root)
    - Environment variables for test configuration
    - E2E test requirements (Kind cluster)
  - Keep it concise (<200 lines)

  **Must NOT do**:
  - Do NOT document internal test utilities
  - Do NOT include implementation details
  - Do NOT create multiple files (single conventions doc)

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation creation, technical writing
  - **Skills**: [`testing`]
    - `testing`: Understanding of test patterns to document accurately

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential)
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 4, 5

  **References**:

  **Pattern References**:
  - `tests/conftest.py` - Root fixtures to document
  - `pyproject.toml:[tool.pytest.ini_options]` - Markers to document

  **Documentation References**:
  - `docs/` - Existing docs structure
  - `CONTRIBUTING.md` - Code standards section

  **Acceptance Criteria**:

  ```bash
  # Agent runs:
  test -f docs/testing/CONVENTIONS.md && echo "File exists"
  # Assert: "File exists"
  
  wc -l docs/testing/CONVENTIONS.md
  # Assert: Less than 200 lines
  
  grep -c "pytest" docs/testing/CONVENTIONS.md
  # Assert: At least 5 occurrences (comprehensive)
  ```

  **Evidence to Capture**:
  - [ ] File exists and is under 200 lines
  - [ ] Contains pytest usage information

  **Commit**: YES
  - Message: `docs(testing): add testing conventions documentation`
  - Files: `docs/testing/CONVENTIONS.md`
  - Pre-commit: `test -f docs/testing/CONVENTIONS.md`

---

- [ ] 7. Final verification and cleanup

  **What to do**:
  - Run full test suite (excluding E2E)
  - Verify no regressions in passing tests
  - Run with `FLOE_DISABLE_BROWSER_OAUTH=true` to verify guard works
  - Verify LSP diagnostics are clean for modified files
  - Delete draft file after confirmation

  **Must NOT do**:
  - Do NOT run E2E tests (require Kind cluster)
  - Do NOT modify any files (verification only)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Verification commands only, no code changes
  - **Skills**: [`testing`]
    - `testing`: Understanding test output interpretation

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (final)
  - **Blocks**: None (terminal task)
  - **Blocked By**: Tasks 1, 3, 6

  **References**:

  **Pattern References**:
  - All files modified in previous tasks

  **Acceptance Criteria**:

  ```bash
  # Agent runs full verification:
  FLOE_DISABLE_BROWSER_OAUTH=true pytest tests/ packages/ \
    --ignore=tests/e2e \
    --ignore=tests/integration \
    -x -q 2>&1 | tail -20
  # Assert: Shows "X passed" with 0 failures
  # Assert: Exit code 0
  
  # Verify contract tests specifically:
  pytest tests/contract/test_orchestrator_plugin_abc.py -v --tb=short
  # Assert: All tests pass
  
  # Verify no LSP errors in modified files:
  # Check signing.py and test_orchestrator_plugin_abc.py have no type errors
  ```

  **Evidence to Capture**:
  - [ ] Full test suite output showing all pass
  - [ ] Contract test output specifically
  - [ ] Clean LSP diagnostics for modified files

  **Commit**: NO (verification only)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `fix(tests): align contract test mock with OrchestratorPlugin ABC signature` | `tests/contract/test_orchestrator_plugin_abc.py` | pytest contract tests |
| 2 | `feat(oci): add FLOE_DISABLE_BROWSER_OAUTH guard to prevent interactive auth` | `packages/floe-core/src/floe_core/oci/signing.py` | py_compile |
| 3 | `test(oci): add unit test for browser OAuth guard` | `packages/floe-core/tests/unit/oci/test_signing.py` | pytest signing tests |
| 4 | `dx(tests): add helpful error message for PYTHONPATH issues` | `tests/conftest.py` | pytest collect |
| 5 | `docs(oci): document FLOE_DISABLE_BROWSER_OAUTH environment variable` | `packages/floe-core/README.md` | grep check |
| 6 | `docs(testing): add testing conventions documentation` | `docs/testing/CONVENTIONS.md` | file exists |

---

## Success Criteria

### Verification Commands
```bash
# Contract test passes:
pytest tests/contract/test_orchestrator_plugin_abc.py -v
# Expected: All tests PASS

# Browser OAuth guard works:
FLOE_DISABLE_BROWSER_OAUTH=true pytest packages/floe-core/tests/unit/oci/test_signing.py -v -k browser
# Expected: Guard test passes, no browser opened

# Full suite (excluding E2E) passes:
pytest tests/ packages/ --ignore=tests/e2e --ignore=tests/integration -x
# Expected: 670+ tests pass
```

### Final Checklist
- [ ] Contract test mock matches ABC signature exactly
- [ ] Browser OAuth guard prevents interactive auth when enabled
- [ ] PYTHONPATH issues show helpful error messages
- [ ] Environment variables documented
- [ ] Testing conventions documented
- [ ] All previously passing tests still pass
- [ ] No new LSP errors introduced

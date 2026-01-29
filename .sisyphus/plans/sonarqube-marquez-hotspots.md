# SonarQube Security Hotspots Remediation - Marquez Plugin

## TL;DR

> **Quick Summary**: Fix 2 SonarQube security hotspots in the Marquez lineage plugin by replacing hardcoded password placeholder with Kubernetes secret reference pattern and enforcing HTTPS URLs via Pydantic validation.
> 
> **Deliverables**:
> - Helm values use `existingSecret` pattern (no passwords in code)
> - URL validation enforces HTTPS (except localhost)
> - `FLOE_ALLOW_INSECURE_HTTP` env var for development override
> - Tests for new validation behavior
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1.2 → Task 2.1 → Task 3.2

---

## Context

### Original Request
Fix 2 SonarQube security hotspots in `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py`:
1. Password placeholder in `get_helm_values()` (line 240)
2. HTTP URL warning-only approach (lines 109-113)

### Interview Summary
**Key Discussions**:
- **Validation location**: User confirmed Pydantic-only approach (field_validator on MarquezConfig, remove __init__ warning)
- **Environment variable**: Use `FLOE_ALLOW_INSECURE_HTTP` consistent with existing `FLOE_ALLOW_INSECURE_SSL`

**Research Findings**:
- **Keycloak URL pattern** (`plugins/floe-identity-keycloak/src/floe_identity_keycloak/config.py:135-181`): Established pattern for URL security validation with `_is_localhost()` helper
- **SSL override pattern** (`packages/floe-core/src/floe_core/lineage/transport.py:53`): Uses `FLOE_ALLOW_INSECURE_SSL` with CRITICAL log on override
- **Bitnami PostgreSQL**: `existingSecret` + `secretKeys` is the standard pattern for K8s secret references

---

## Work Objectives

### Core Objective
Eliminate SonarQube security hotspots by implementing proper security patterns for password handling and URL validation.

### Concrete Deliverables
- `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py` with existingSecret pattern and field_validator
- `plugins/floe-lineage-marquez/README.md` with environment variable documentation
- `plugins/floe-lineage-marquez/tests/unit/test_plugin.py` with validation tests

### Definition of Done
- [ ] `grep -r "password.*SET_VIA" plugins/floe-lineage-marquez/` returns no matches
- [ ] `MarquezConfig(url="http://external:5000")` raises `ValueError`
- [ ] `MarquezConfig(url="http://localhost:5000")` succeeds
- [ ] `pytest plugins/floe-lineage-marquez/tests/` passes
- [ ] `pre-commit run --all-files` passes

### Must Have
- No hardcoded passwords in code (even placeholders)
- HTTPS enforcement for non-localhost URLs
- Localhost exception for development
- Environment variable override with CRITICAL log
- Tests covering all validation paths

### Must NOT Have (Guardrails)
- Substring matching for localhost detection (vulnerable to bypass)
- Password strings in any form in plugin code
- HTTP allowed by default for non-localhost
- Tests that rely on external network

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES
- **User wants tests**: YES (Tests after implementation)
- **Framework**: pytest

### Automated Verification

**For code changes (using Bash):**
```bash
# Verify no password in code
grep -r "password.*=" plugins/floe-lineage-marquez/src/ && echo "FAIL: password found" || echo "PASS: no password"

# Verify existingSecret present
grep -q "existingSecret" plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py && echo "PASS" || echo "FAIL"
```

**For validation logic (using pytest):**
```bash
cd plugins/floe-lineage-marquez
pytest tests/unit/test_plugin.py -v -k "url" --tb=short
```

**For full verification:**
```bash
pre-commit run --all-files
pytest plugins/floe-lineage-marquez/tests/ --cov=floe_lineage_marquez
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1.1: Fix password (existingSecret) [no dependencies]
├── Task 1.2: Fix HTTP URL (field_validator) [no dependencies]
└── Task 1.3: Update README [no dependencies]

Wave 2 (After Wave 1):
├── Task 2.1: Update tests [depends: 1.1, 1.2]
└── Task 2.2: Verify coverage [depends: 2.1]

Wave 3 (After Wave 2):
├── Task 3.1: Run pre-commit [depends: all Wave 2]
├── Task 3.2: Run full test suite [depends: 3.1]
└── Task 3.3: Commit and push [depends: 3.2]
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1.1 | None | 2.1 | 1.2, 1.3 |
| 1.2 | None | 2.1 | 1.1, 1.3 |
| 1.3 | None | None | 1.1, 1.2 |
| 2.1 | 1.1, 1.2 | 2.2 | None |
| 2.2 | 2.1 | 3.1 | None |
| 3.1 | 2.2 | 3.2 | None |
| 3.2 | 3.1 | 3.3 | None |
| 3.3 | 3.2 | None | None |

---

## TODOs

- [ ] 1. **Task 1.1: Replace Password with existingSecret Pattern**

  **What to do**:
  - Edit `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py`
  - In `get_helm_values()` method (lines 236-243), replace the `auth` section
  - Remove `"password": "<SET_VIA_HELM_VALUES>"` line
  - Add `"existingSecret": "marquez-postgresql-credentials"` 
  - Add `"secretKeys": {"adminPasswordKey": "postgres-password", "userPasswordKey": "password"}`
  - Remove the `# pragma: allowlist secret` comment (no longer needed)

  **Must NOT do**:
  - Keep any password string in the code
  - Change the username or database name

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple, localized change to a single dictionary in one file
  - **Skills**: None required
    - This is a straightforward text replacement
  - **Skills Evaluated but Omitted**:
    - `helm-k8s-deployment`: Not needed - we're changing Python code, not Helm templates

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1.2, 1.3)
  - **Blocks**: Task 2.1 (tests depend on this change)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py:236-243` - Current code to replace

  **Documentation References**:
  - Bitnami PostgreSQL chart: `auth.existingSecret` and `auth.secretKeys` pattern

  **Acceptance Criteria**:

  ```bash
  # Agent runs:
  grep -q "existingSecret" plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py
  # Assert: Exit code 0 (found)

  grep "password.*SET_VIA\|password.*<" plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py
  # Assert: Exit code 1 (NOT found)

  grep -q "secretKeys" plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py
  # Assert: Exit code 0 (found)
  ```

  **Commit**: YES (groups with 1.2, 1.3)
  - Message: `fix(marquez): use existingSecret for PostgreSQL credentials`
  - Files: `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py`

---

- [ ] 2. **Task 1.2: Add URL Security Validation to MarquezConfig**

  **What to do**:
  - Edit `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py`
  - Add imports at top: `import ipaddress`, `import logging`, `import os`, `from urllib.parse import urlparse`
  - Add `field_validator` import: change `from pydantic import BaseModel, Field` to `from pydantic import BaseModel, Field, field_validator`
  - Add `_LOCALHOST_HOSTNAMES` constant and `_is_localhost()` helper function before `MarquezConfig` class
  - Add `@field_validator("url")` method to `MarquezConfig` class that:
    - Strips trailing slashes
    - For HTTP URLs: checks if localhost (allow) or non-localhost (reject unless `FLOE_ALLOW_INSECURE_HTTP=true`)
    - Logs CRITICAL when env override is used
  - Remove lines 109-113 (the warning in `__init__`) - validation now happens in Pydantic

  **Must NOT do**:
  - Use substring matching for localhost (use proper URL parsing + IP address checking)
  - Allow HTTP without explicit env var override
  - Skip the CRITICAL log when override is used
  - Keep the old warning in `__init__`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Requires careful security implementation with proper URL parsing and IP address handling
  - **Skills**: [`pydantic-schemas`]
    - `pydantic-schemas`: Pydantic v2 field_validator syntax and patterns
  - **Skills Evaluated but Omitted**:
    - `testing`: Tests are in separate task

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1.1, 1.3)
  - **Blocks**: Task 2.1 (tests depend on this change)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `plugins/floe-identity-keycloak/src/floe_identity_keycloak/config.py:38-60` - `_is_localhost()` helper implementation
  - `plugins/floe-identity-keycloak/src/floe_identity_keycloak/config.py:135-181` - `@field_validator("server_url")` pattern
  - `packages/floe-core/src/floe_core/lineage/transport.py:53` - Environment variable override pattern with CRITICAL log

  **API/Type References**:
  - `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py:22-58` - Current MarquezConfig class to modify

  **Acceptance Criteria**:

  ```bash
  # Agent runs Python validation tests:
  cd plugins/floe-lineage-marquez
  
  # Test 1: HTTP non-localhost rejected
  python -c "
from floe_lineage_marquez import MarquezConfig
try:
    MarquezConfig(url='http://external.example.com:5000')
    print('FAIL: should have raised ValueError')
    exit(1)
except ValueError as e:
    if 'HTTP not allowed' in str(e):
        print('PASS: HTTP rejected for non-localhost')
    else:
        print(f'FAIL: wrong error: {e}')
        exit(1)
"
  # Assert: Exit code 0

  # Test 2: HTTP localhost allowed
  python -c "
from floe_lineage_marquez import MarquezConfig
config = MarquezConfig(url='http://localhost:5000')
assert config.url == 'http://localhost:5000', 'URL not preserved'
print('PASS: HTTP allowed for localhost')
"
  # Assert: Exit code 0

  # Test 3: HTTPS always allowed
  python -c "
from floe_lineage_marquez import MarquezConfig
config = MarquezConfig(url='https://marquez.example.com:5000')
print('PASS: HTTPS allowed')
"
  # Assert: Exit code 0
  ```

  **Commit**: YES (groups with 1.1, 1.3)
  - Message: `fix(marquez): enforce HTTPS for non-localhost URLs`
  - Files: `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py`

---

- [ ] 3. **Task 1.3: Update README with Environment Variable Documentation**

  **What to do**:
  - Edit `plugins/floe-lineage-marquez/README.md`
  - Add "## Environment Variables" section before "## Requirements"
  - Document `FLOE_ALLOW_INSECURE_HTTP` with table format
  - Add security notes about when this should/shouldn't be used

  **Must NOT do**:
  - Present the env var as a production option
  - Skip security warnings

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation update
  - **Skills**: None required
  - **Skills Evaluated but Omitted**:
    - All skills - simple markdown addition

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1.1, 1.2)
  - **Blocks**: None
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `packages/floe-core/README.md:90-94` - Existing env var documentation format for `FLOE_ALLOW_INSECURE_SSL`

  **Documentation References**:
  - `plugins/floe-lineage-marquez/README.md` - Current README to modify

  **Acceptance Criteria**:

  ```bash
  # Agent runs:
  grep -q "FLOE_ALLOW_INSECURE_HTTP" plugins/floe-lineage-marquez/README.md
  # Assert: Exit code 0

  grep -q "development only" plugins/floe-lineage-marquez/README.md
  # Assert: Exit code 0 (security warning present)
  ```

  **Commit**: YES (groups with 1.1, 1.2)
  - Message: `docs(marquez): document FLOE_ALLOW_INSECURE_HTTP env var`
  - Files: `plugins/floe-lineage-marquez/README.md`

---

- [ ] 4. **Task 2.1: Add Tests for New Validation Behavior**

  **What to do**:
  - Edit `plugins/floe-lineage-marquez/tests/unit/test_plugin.py`
  - Add new test functions for URL validation:
    - `test_config_rejects_http_non_localhost()` - ValueError for HTTP external URLs
    - `test_config_allows_http_localhost()` - HTTP allowed for localhost
    - `test_config_allows_http_127_0_0_1()` - HTTP allowed for 127.0.0.1
    - `test_config_allows_http_ipv6_loopback()` - HTTP allowed for ::1
    - `test_config_allows_https_always()` - HTTPS always works
    - `test_config_http_allowed_with_env_override()` - FLOE_ALLOW_INSECURE_HTTP=true works
    - `test_config_http_logs_critical_with_override()` - CRITICAL log emitted
  - Update `test_helm_values_password_placeholder()` to `test_helm_values_uses_existing_secret()`
  - All tests should use `@pytest.mark.requirement("REQ-527")` decorator

  **Must NOT do**:
  - Delete existing valid tests
  - Skip env var cleanup in monkeypatch tests
  - Use external network in tests

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Security-critical tests need comprehensive coverage
  - **Skills**: [`testing`]
    - `testing`: pytest patterns, monkeypatch usage, test organization
  - **Skills Evaluated but Omitted**:
    - `pydantic-schemas`: Tests exercise Pydantic but don't need schema knowledge

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential)
  - **Blocks**: Task 2.2
  - **Blocked By**: Tasks 1.1, 1.2

  **References**:

  **Pattern References**:
  - `plugins/floe-lineage-marquez/tests/unit/test_plugin.py:259-282` - Existing config validation tests
  - `packages/floe-core/tests/lineage/test_transport.py:221-288` - Tests for FLOE_ALLOW_INSECURE_SSL pattern

  **Test References**:
  - `plugins/floe-lineage-marquez/tests/unit/test_plugin.py` - Current test file structure

  **Acceptance Criteria**:

  ```bash
  # Agent runs:
  cd plugins/floe-lineage-marquez
  pytest tests/unit/test_plugin.py -v -k "url or secret" --tb=short
  # Assert: All URL validation tests pass
  # Assert: existingSecret test passes

  pytest tests/unit/test_plugin.py -v --tb=short
  # Assert: Exit code 0 (all tests pass)
  ```

  **Commit**: NO (will commit with 2.2)
  - Files: `plugins/floe-lineage-marquez/tests/unit/test_plugin.py`

---

- [ ] 5. **Task 2.2: Verify Test Coverage**

  **What to do**:
  - Run pytest with coverage for marquez plugin
  - Verify new code paths are covered (≥80%)
  - If coverage gaps exist, add missing tests

  **Must NOT do**:
  - Skip coverage verification
  - Proceed if coverage < 80% on new code

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple coverage check command
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential after 2.1)
  - **Blocks**: Task 3.1
  - **Blocked By**: Task 2.1

  **References**:

  **Documentation References**:
  - `plugins/floe-lineage-marquez/pyproject.toml` - Coverage configuration

  **Acceptance Criteria**:

  ```bash
  # Agent runs:
  cd plugins/floe-lineage-marquez
  pytest tests/ --cov=floe_lineage_marquez --cov-report=term-missing --cov-fail-under=80
  # Assert: Exit code 0 (coverage ≥ 80%)
  ```

  **Commit**: YES (groups with 2.1)
  - Message: `test(marquez): add URL validation and existingSecret tests`
  - Files: `plugins/floe-lineage-marquez/tests/unit/test_plugin.py`

---

- [ ] 6. **Task 3.1: Run Pre-commit Checks**

  **What to do**:
  - Run pre-commit on all modified files
  - Fix any issues (ruff, mypy, formatting)

  **Must NOT do**:
  - Skip pre-commit
  - Disable checks to make them pass

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard pre-commit run
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential)
  - **Blocks**: Task 3.2
  - **Blocked By**: Task 2.2

  **References**: None needed

  **Acceptance Criteria**:

  ```bash
  # Agent runs:
  pre-commit run --all-files
  # Assert: Exit code 0 (all hooks pass)
  ```

  **Commit**: NO (just verification)

---

- [ ] 7. **Task 3.2: Run Full Test Suite**

  **What to do**:
  - Run complete test suite for marquez plugin
  - Ensure no regressions

  **Must NOT do**:
  - Skip tests
  - Ignore failures

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard test run
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential)
  - **Blocks**: Task 3.3
  - **Blocked By**: Task 3.1

  **References**: None needed

  **Acceptance Criteria**:

  ```bash
  # Agent runs:
  pytest plugins/floe-lineage-marquez/tests/ -v
  # Assert: Exit code 0 (all tests pass)
  # Assert: No test failures or errors
  ```

  **Commit**: NO (just verification)

---

- [ ] 8. **Task 3.3: Commit and Push**

  **What to do**:
  - Stage all modified files
  - Create commit with descriptive message
  - Push to remote

  **Must NOT do**:
  - Commit without running tests
  - Use generic commit message

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard git operations
  - **Skills**: [`git-master`]
    - `git-master`: Atomic commit patterns, message formatting

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (final)
  - **Blocks**: None
  - **Blocked By**: Task 3.2

  **References**: None needed

  **Acceptance Criteria**:

  ```bash
  # Agent runs:
  git status
  # Assert: All changes staged or committed

  git log -1 --oneline
  # Assert: Commit message matches expected format

  git push
  # Assert: Exit code 0
  ```

  **Commit**: YES
  - Message: `fix(marquez): resolve SonarQube security hotspots

- Replace hardcoded password placeholder with existingSecret pattern
  for Bitnami PostgreSQL Helm chart compatibility
- Add Pydantic field_validator for URL security enforcement
  (HTTPS required except localhost)
- Add FLOE_ALLOW_INSECURE_HTTP env var for development override
- Add comprehensive tests for new validation behavior

Resolves: SonarQube hotspots in floe-lineage-marquez plugin`
  - Files: All modified files

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 2.2 | `test(marquez): add URL validation and existingSecret tests` | `tests/unit/test_plugin.py` | pytest passes |
| 3.3 | `fix(marquez): resolve SonarQube security hotspots` | `__init__.py`, `README.md` | pre-commit + pytest |

---

## Success Criteria

### Verification Commands
```bash
# No password in code
grep -r "password.*=" plugins/floe-lineage-marquez/src/ | grep -v existingSecret
# Expected: no output (exit code 1)

# existingSecret pattern present
grep "existingSecret" plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py
# Expected: "marquez-postgresql-credentials"

# URL validation works
cd plugins/floe-lineage-marquez && python -c "from floe_lineage_marquez import MarquezConfig; MarquezConfig(url='http://external:5000')" 2>&1
# Expected: ValueError with "HTTP not allowed"

# All tests pass
pytest plugins/floe-lineage-marquez/tests/ -v
# Expected: all pass

# Pre-commit clean
pre-commit run --all-files
# Expected: exit code 0
```

### Final Checklist
- [ ] No hardcoded password in code (Must Have)
- [ ] existingSecret pattern in Helm values (Must Have)
- [ ] URL validation rejects HTTP non-localhost (Must Have)
- [ ] URL validation allows HTTP localhost (Must Have)
- [ ] FLOE_ALLOW_INSECURE_HTTP override works (Must Have)
- [ ] CRITICAL log emitted on override (Must Have)
- [ ] All tests pass (Must Have)
- [ ] Coverage ≥ 80% (Must Have)
- [ ] No substring matching for localhost (Must NOT Have - guardrail)

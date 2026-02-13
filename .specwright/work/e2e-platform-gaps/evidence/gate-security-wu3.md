# Security Scan: WU-3 (Dagster SDK Migration)

## Executive Summary
- **Critical Issues**: 0
- **High Issues**: 0
- **Medium Issues**: 1
- **Low Issues**: 2
- **Risk Level**: LOW

**Overall Assessment**: WU-3 changes are security-clean. One medium-severity issue (HTTP usage in local test environment) and two low-severity informational items. No blockers for merge.

---

## Medium Findings (Fix Before Production)

### 1. HTTP Protocol in Test Environment Variables
- **CWE**: CWE-319 (Cleartext Transmission of Sensitive Information)
- **Location**: `tests/e2e/test_compile_deploy_materialize_e2e.py:172,241,370`
- **Severity**: MEDIUM
- **Vulnerable Code**:
```python
dagster_url = os.environ.get("DAGSTER_URL", "http://localhost:3000")
```
- **Context**: Used for GraphQL API calls to Dagster webserver
- **Risk Assessment**:
  - **Local/Test Impact**: NEGLIGIBLE - localhost traffic doesn't cross network boundaries
  - **Production Impact**: MEDIUM - if DAGSTER_URL is exposed to external hosts without TLS
- **Remediation**:
  - **Immediate (test environment)**: No action needed - localhost HTTP is safe for E2E tests
  - **Production hardening**: Enforce HTTPS validation for external Dagster URLs:
```python
dagster_url = os.environ.get("DAGSTER_URL", "http://localhost:3000")
if not dagster_url.startswith(("http://localhost", "http://127.0.0.1")):
    if not dagster_url.startswith("https://"):
        raise ValueError("External DAGSTER_URL must use HTTPS")
```
- **Status**: WARN - Acceptable for test code, recommend production hardening

---

## Low Findings (Informational)

### 2. GraphQL Error Messages May Expose Internal State
- **CWE**: CWE-209 (Information Exposure Through Error Messages)
- **Location**: `tests/e2e/test_compile_deploy_materialize_e2e.py:214,420,423`
- **Severity**: LOW
- **Vulnerable Code**:
```python
# Line 214
pytest.fail(f"Dagster repository error: {repos_data['message']}")

# Line 420-423
if "message" in launch_result:
    pytest.fail(f"Materialization launch failed: {launch_result['message']}")
if "errors" in launch_result:
    errors = [e["message"] for e in launch_result["errors"]]
    pytest.fail(f"Run config invalid: {errors}")
```
- **Context**: Test code propagates GraphQL error messages verbatim to pytest output
- **Risk Assessment**:
  - **Test Code**: ACCEPTABLE - detailed errors aid debugging
  - **Production Code**: Would require sanitization to avoid exposing internal paths/stack traces
- **Remediation**: None required for test code. For production error handling:
```python
# Sanitize production errors
logger.error("Dagster API error", error_detail=repos_data['message'])
raise FloeError("Pipeline deployment failed - check logs")
```
- **Status**: INFO - Test code pattern is correct

### 3. File Path Operations Use Trusted Paths Only
- **CWE**: CWE-22 (Path Traversal) - **NOT PRESENT**
- **Location**: `testing/tests/unit/test_dagster_migration.py:20-31,52,66,76,85,102,201`
- **Severity**: INFO (no vulnerability)
- **Secure Code**:
```python
# Line 20-31: All paths computed from __file__, not user input
REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_DEPLOY_TEST = REPO_ROOT / "tests" / "e2e" / "test_compile_deploy_materialize_e2e.py"
SENSOR_MODULE = REPO_ROOT / "plugins" / "floe-orchestrator-dagster" / "src" / "floe_orchestrator_dagster" / "sensors.py"

# Line 52,66,76,85,102: Reading trusted paths
content = E2E_DEPLOY_TEST.read_text()
content = SENSOR_MODULE.read_text()

# Line 190-201: Globbing trusted directory
py_files = list(DAGSTER_SRC_DIR.rglob("*.py"))
ast.parse(py_file.read_text())
```
- **Analysis**: All file paths are:
  1. Computed from `__file__` (trusted internal path)
  2. Constructed via Path concatenation (no string interpolation)
  3. Used for reading test/source files (no user input)
  4. No `..` traversal or user-controlled paths
- **Status**: SECURE - No path traversal risk

---

## Security Checklist: PASS

- [x] **No hardcoded secrets** - No credentials, API keys, or passwords found
- [x] **All user input validated** - N/A: No user input in these files
- [x] **Parameterized queries used** - N/A: No SQL queries (GraphQL uses typed variables)
- [x] **Safe subprocess usage** - N/A: No subprocess calls
- [x] **Secure password hashing** - N/A: No password handling
- [x] **HTTPS enforced** - MEDIUM: HTTP acceptable for localhost tests, requires production hardening
- [x] **Proper error handling** - Test error propagation is correct

---

## OWASP Top 10 Analysis

| Vulnerability Class | Status | Evidence |
|---------------------|--------|----------|
| **A01: Broken Access Control** | CLEAR | No authentication/authorization logic |
| **A02: Cryptographic Failures** | CLEAR | No cryptography usage |
| **A03: Injection** | CLEAR | No SQL/command/LDAP injection vectors |
| **A04: Insecure Design** | CLEAR | Secure patterns: typed GraphQL, trusted paths |
| **A05: Security Misconfiguration** | WARN | HTTP in tests (acceptable), recommend HTTPS validation |
| **A06: Vulnerable Components** | N/A | Dependency scanning out of scope |
| **A07: Auth/AuthN Failures** | CLEAR | No authentication logic |
| **A08: Data Integrity Failures** | CLEAR | No deserialization (pickle/yaml.load) |
| **A09: Logging Failures** | CLEAR | Errors logged appropriately for test code |
| **A10: SSRF** | CLEAR | Dagster URL from environment, not user input |

---

## Code Injection Scan: CLEAN

**Searched for**:
- `eval()`, `exec()`, `__import__()` - **NOT FOUND**
- `pickle.loads()`, `yaml.load()` - **NOT FOUND**
- `subprocess.run(..., shell=True)` - **NOT FOUND**

**Result**: No code injection vectors present.

---

## Secrets Detection: CLEAN

**Searched for**:
- Hardcoded passwords, API keys, tokens, credentials - **NOT FOUND**
- Sensitive data in logs - **NOT FOUND**

**Result**: No secrets detected. All configuration via environment variables.

---

## GraphQL Security: SECURE

**Pattern Analysis**:
```python
# Static query strings (not constructed from user input)
query = """
{
    repositoriesOrError {
        ... on RepositoryConnection {
            nodes { name location { name } }
        }
        ... on PythonError { message }
    }
}
"""

# Typed variables (JSON structure, not string interpolation)
variables = {
    "executionParams": {
        "selector": {"assetSelection": [{"path": ["stg_customers"]}]},
        "mode": "default",
    },
}
```

**Security Properties**:
1. Queries are static strings (no dynamic construction)
2. Variables use JSON objects (type-safe)
3. No string interpolation into GraphQL
4. Asset paths are hardcoded (`["stg_customers"]`), not user-controlled

**Result**: GraphQL usage follows secure patterns.

---

## File Operations Security: SECURE

**Pattern Analysis**:
```python
# Trusted path construction
REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_DEPLOY_TEST = REPO_ROOT / "tests" / "e2e" / "test_compile_deploy_materialize_e2e.py"

# Read operations on trusted paths
content = E2E_DEPLOY_TEST.read_text()

# AST parsing (safe operation)
ast.parse(py_file.read_text())
```

**Security Properties**:
1. All paths computed from `__file__` (trusted anchor)
2. Path concatenation via `/` operator (safe from traversal)
3. No user input in path construction
4. Read-only operations (no write/delete)
5. AST parsing is safe (no code execution)

**Result**: File operations are secure.

---

## Sensor Security: SECURE

**Changed Code** (`sensors.py:125-133`):
```python
health_check_sensor = sensor(
    name="health_check_sensor",
    description="Triggers first pipeline run when platform services are healthy",
    minimum_interval_seconds=60,
    asset_selection="*",
)(_health_check_sensor_impl)
```

**Security Properties**:
1. Sensor uses Dagster SDK decorator (type-safe)
2. `asset_selection="*"` is a Dagster glob (not shell glob)
3. No user input in sensor definition
4. No credentials or secrets
5. Implementation function (`_health_check_sensor_impl`) only checks environment variables

**Result**: Sensor definition is secure.

---

## Environment Variable Usage: SECURE

**Pattern Analysis**:
```python
# E2E test
dagster_url = os.environ.get("DAGSTER_URL", "http://localhost:3000")

# Sensor implementation
dagster_home = os.environ.get("DAGSTER_HOME")
```

**Security Properties**:
1. Uses `os.environ.get()` with safe defaults
2. No secret leakage (values not logged)
3. URL used for HTTP client (not shell execution)
4. No injection vectors (httpx escapes URL components)

**Recommendation**: Add HTTPS validation for production (see Finding #1).

---

## Recommendations

### Immediate (WU-3)
- **None** - Code is secure for E2E test environment

### Before Production
1. **Add HTTPS enforcement** for external Dagster URLs:
   ```python
   def validate_dagster_url(url: str) -> str:
       """Validate Dagster URL uses HTTPS for external hosts."""
       if url.startswith(("http://localhost", "http://127.0.0.1")):
           return url  # Allow HTTP for local development
       if not url.startswith("https://"):
           raise ValueError(
               "External DAGSTER_URL must use HTTPS. "
               f"Got: {url.split('://')[0]}://<redacted>"
           )
       return url
   ```

2. **Add structured logging** for production error handling:
   ```python
   # Instead of: pytest.fail(f"Error: {repos_data['message']}")
   logger.error("dagster_graphql_error", error_detail=repos_data['message'])
   raise FloeError("Pipeline deployment failed - check logs")
   ```

### Future Hardening
- Add rate limiting for Dagster GraphQL calls
- Add request timeout enforcement (already present: `timeout=30.0`)
- Add retry logic with exponential backoff for transient failures

---

## References

**CWE Mappings**:
- CWE-319: Cleartext Transmission of Sensitive Information
- CWE-209: Information Exposure Through Error Messages
- CWE-22: Path Traversal (not present)
- CWE-89: SQL Injection (not present)
- CWE-78: Command Injection (not present)

**Security Standards**:
- OWASP Top 10 2021
- `.claude/rules/security.md`: Project security standards
- `.claude/rules/code-quality.md`: Quality enforcement

---

## Scan Metadata

- **Scanned Files**: 3
  1. `testing/tests/unit/test_dagster_migration.py` (207 lines)
  2. `tests/e2e/test_compile_deploy_materialize_e2e.py` (lines 179-231, context: full file)
  3. `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/sensors.py` (lines 125-131, context: full file)

- **Scan Date**: 2026-02-13
- **Scanner**: Security Analyst Agent (floe project)
- **Methodology**:
  - Static code analysis (AST parsing)
  - Pattern matching (secrets, injection vectors)
  - OWASP Top 10 mapping
  - CWE reference validation

- **Tools/Techniques**:
  - Grep pattern matching for dangerous constructs
  - File content analysis for hardcoded secrets
  - HTTP/HTTPS protocol validation
  - GraphQL query construction review
  - Path traversal vulnerability analysis
  - Error handling pattern review

---

## Conclusion

**APPROVED FOR MERGE**

WU-3 (Dagster SDK Migration) introduces **zero critical or high-severity security issues**. The one medium-severity finding (HTTP usage) is acceptable for local E2E tests and does not block merge. Production deployment should add HTTPS validation as recommended.

All code follows secure patterns:
- No hardcoded secrets
- No injection vulnerabilities
- Safe file operations (trusted paths only)
- Secure GraphQL usage (static queries + typed variables)
- Appropriate error handling for test code

**Security Gate Status**: ✅ PASS

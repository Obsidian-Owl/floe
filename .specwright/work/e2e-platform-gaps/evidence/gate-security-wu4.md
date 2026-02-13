# Gate: Security — WU-4 Evidence

**Status**: PASS  
**Findings**: Critical: 0, High: 0, Medium: 0, Low: 1  
**Risk Level**: LOW

---

## Executive Summary

Security audit of WU-4 OTel Pipeline + Label Alignment changes found **no critical or high-severity vulnerabilities**. All code follows secure coding practices with one low-severity advisory for test credential documentation.

**Files Audited**:
- `testing/tests/unit/test_otel_pipeline.py` (NEW — 23 structural validation tests)
- `tests/e2e/test_observability.py` (label selector changes)
- `tests/e2e/test_observability_roundtrip_e2e.py` (service name alignment)
- `tests/e2e/conftest.py` (new TracerProvider fixture)

---

## OWASP Top 10 Assessment

### CWE-78: Command Injection (OS Command Injection)
**Status**: ✅ SECURE

**Subprocess Usage Analysis**:
All subprocess calls use **list format with no shell=True**:

```python
# tests/e2e/conftest.py:129-132
subprocess.run(
    cmd,  # List of strings
    capture_output=True,
    text=True,
    timeout=timeout,
    check=False,  # No shell=True
)

# tests/e2e/test_observability.py:387-393
subprocess.run(
    ["kubectl", "get", "svc", "-n", "floe-test", "-o", "name"],
    capture_output=True,
    text=True,
    timeout=30,
    check=False,
)
```

**Verdict**: No command injection risk. All subprocess calls use parameterized list format.

---

### CWE-798: Hardcoded Credentials
**Status**: ⚠️ LOW RISK (Test-only credentials with proper controls)

**Credential Usage**:
```python
# tests/e2e/conftest.py:417
default_cred = "demo-admin:demo-secret"  # pragma: allowlist secret

# tests/e2e/conftest.py:430-433
"s3.access-key-id": os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
"s3.secret-access-key": os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin123")

# tests/e2e/conftest.py:508-509
"client_id": "demo-admin",  # pragma: allowlist secret
"client_secret": "demo-secret",  # pragma: allowlist secret
```

**Mitigation Controls**:
1. ✅ `# pragma: allowlist secret` comments for security scanner exceptions
2. ✅ Inline documentation: "Demo credentials for local testing only"
3. ✅ Environment variable override: `os.environ.get("POLARIS_CREDENTIAL", default_cred)`
4. ✅ Usage context comment: "production uses K8s secrets"
5. ✅ Credentials only used in **test fixtures** (never in production code)

**Recommendation**: Add `.specwright/SECURITY.md` note documenting that demo credentials are non-functional outside local Kind cluster.

**Severity**: LOW (test-only credentials with documented scope)

---

### CWE-89: SQL Injection
**Status**: ✅ NOT APPLICABLE

No SQL queries found in audited files. All data access uses HTTP APIs (Jaeger, Marquez, OTel Collector).

---

### CWE-94: Code Injection
**Status**: ✅ SECURE

No usage of:
- `eval()`
- `exec()`
- `compile()`
- `__import__()`

---

### CWE-502: Insecure Deserialization
**Status**: ✅ SECURE

No usage of:
- `pickle.loads()`
- `yaml.unsafe_load()`
- `marshal.loads()`

YAML parsing uses `yaml.safe_load()` (test_otel_pipeline.py:117, 133, etc.)

---

### CWE-327: Use of a Broken or Risky Cryptographic Algorithm
**Status**: ✅ NOT APPLICABLE

No cryptographic operations in test code. TLS configuration uses `insecure=True` for **local cluster testing only** (OTel Collector within K8s cluster network).

```python
# tests/e2e/conftest.py:607
exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
```

**Context**: This is acceptable for E2E tests targeting localhost/in-cluster services. Not a production configuration.

---

### CWE-532: Insertion of Sensitive Information into Log File
**Status**: ✅ SECURE

**Token Handling**:
```python
# tests/e2e/conftest.py:517
token = token_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}", ...}
```

Token is:
1. Retrieved from OAuth endpoint (not logged)
2. Used immediately in Authorization header
3. Never printed or logged
4. Scoped to session fixture (automatically cleaned up)

**Error Messages**: No secrets exposed in pytest.fail() messages. Only generic descriptions like "Failed to get Polaris admin token" (line 515).

---

### CWE-22: Path Traversal
**Status**: ✅ NOT APPLICABLE

No file path manipulation from user input. All paths use `Path(__file__)` + hardcoded relative paths:

```python
# tests/e2e/test_observability.py:484
spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
manifest_path = project_root / "demo" / "manifest.yaml"
```

---

### CWE-918: Server-Side Request Forgery (SSRF)
**Status**: ✅ SECURE

HTTP client usage is **bounded to test fixtures**:
- Jaeger client: `base_url=jaeger_url` from env (default localhost:16686)
- Marquez client: `base_url=marquez_url` from env (default localhost:5000)
- OTel exporter: `endpoint=otel_endpoint` from env (default localhost:4317)

No user-controlled URLs. All URLs derived from environment variables with safe defaults (localhost).

---

### CWE-209: Information Exposure Through Error Messages
**Status**: ✅ SECURE

Error messages are **diagnostic, not exposing internals**:

```python
# tests/e2e/test_observability_roundtrip_e2e.py:103-108
pytest.fail(
    f"No compilation traces found in Jaeger after 30s.\n"
    f"Expected service: 'floe-platform'\n"
    f"Available services: {services}\n"  # Safe: list of service names
    f"OTel Collector may not be forwarding to Jaeger.\n"
    f"Check: kubectl logs -n floe-test -l app.kubernetes.io/name=otel --tail=20"
)
```

Messages provide:
- What failed (high-level description)
- Expected vs actual state
- Next troubleshooting step

No stack traces, credentials, or internal paths exposed.

---

## Additional Security Checks

### Input Validation
**Status**: ✅ SECURE

All external inputs validated:
- YAML parsing uses `yaml.safe_load()` (prevents code execution)
- HTTP responses checked with `status_code` validation
- JSON responses validated with `assert "data" in response_json` (prevents KeyError)

### Exception Handling
**Status**: ✅ SECURE

No bare `except:` clauses. All exceptions caught with specific types:

```python
# tests/e2e/test_observability_roundtrip_e2e.py:85
except (httpx.HTTPError, ValueError):
    return False
```

### Timeout Protection
**Status**: ✅ SECURE

All subprocess calls have timeouts:
- Default: 60s (conftest.py:115)
- Namespace deletion: 300s (conftest.py:284)
- OTel collector acceptance: 10s (test_observability_roundtrip_e2e.py:194)

Prevents resource exhaustion from hung processes.

---

## Findings Summary

### LOW-001: Test Credentials Documentation
**Severity**: Low  
**CWE**: CWE-798 (Hardcoded Credentials)  
**Location**:
- `tests/e2e/conftest.py:417` (demo-admin:demo-secret)
- `tests/e2e/conftest.py:430-433` (minioadmin credentials)
- `tests/e2e/conftest.py:508-509` (client_id/client_secret)

**Issue**: Demo credentials hardcoded in test fixtures.

**Mitigation**: 
- ✅ Credentials scoped to test-only fixtures
- ✅ `# pragma: allowlist secret` markers for scanners
- ✅ Environment variable overrides available
- ✅ Inline comments documenting test-only scope

**Recommendation**: Add documentation to `.specwright/SECURITY.md`:
```markdown
## Test Credentials
Demo credentials in E2E fixtures (demo-admin:demo-secret, minioadmin:minioadmin123)
are non-functional outside local Kind cluster and do not provide access to production systems.
```

**Risk**: Negligible. Credentials only authenticate against ephemeral test Polaris/MinIO instances in local Kind clusters.

---

## Secure Coding Patterns Observed

### ✅ Environment Variable Usage
All service endpoints configurable via env vars with safe defaults:
```python
jaeger_url = os.environ.get("JAEGER_URL", "http://localhost:16686")
marquez_url = os.environ.get("MARQUEZ_URL", "http://localhost:5000")
polaris_url = os.environ.get("POLARIS_URL", "http://localhost:8181")
```

### ✅ Safe HTTP Clients
HTTP clients configured with timeouts to prevent hangs:
```python
httpx.Client(base_url=marquez_url, timeout=30.0)
```

### ✅ Resource Cleanup
Session-scoped fixtures properly clean up resources:
```python
yield provider
provider.shutdown()  # tests/e2e/conftest.py:613
```

### ✅ Type Safety
All functions have type hints per project standards:
```python
def run_kubectl(
    args: list[str],
    namespace: str | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
```

---

## Verdict

**SECURITY GATE: PASS**

WU-4 changes introduce **no security vulnerabilities**. Code follows secure subprocess usage, proper credential handling for test environments, and robust error handling without information leakage.

**Only advisory**: Document test credential scope in security documentation (low priority, non-blocking).

**Evidence**:
- ✅ No shell injection vectors
- ✅ No SQL injection
- ✅ No code execution vulnerabilities
- ✅ No hardcoded production credentials
- ✅ Safe deserialization (yaml.safe_load)
- ✅ Timeout protection on all external calls
- ✅ Proper exception handling
- ✅ No TLS bypass in production paths

**Approved for merge.**

---

## References
- OWASP Top 10 2021: https://owasp.org/Top10/
- CWE-78 (Command Injection): https://cwe.mitre.org/data/definitions/78.html
- CWE-798 (Hardcoded Credentials): https://cwe.mitre.org/data/definitions/798.html
- Project Security Standards: `.claude/rules/security.md`

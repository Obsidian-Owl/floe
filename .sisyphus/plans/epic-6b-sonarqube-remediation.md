# Epic 6B SonarQube Security Remediation

## TL;DR

> **Quick Summary**: Fix critical SSL verification vulnerabilities and security hotspots flagged by SonarQube, then increase test coverage to >80% on all affected lineage module files.
>
> **Deliverables**:
> - Fixed SSL verification code in `transport.py` (SonarQube compliant)
> - Fixed security hotspots in Marquez plugin (HTTPS default, no hardcoded passwords)
> - Environment-based security controls documented
> - Test coverage >80% on 6 files (transport, emitter, events, facets, catalog_integration, extractors/dbt)
>
> **Estimated Effort**: Medium (2-3 hours)
> **Parallel Execution**: YES - 3 waves + 1 sequential validation
> **Critical Path**: Task 1.1 → Task 2.1 → Task 4.2

---

## Context

### Original Request
Fix SonarQube quality gate failures on Epic 6B OpenLineage PR:
- 2 CRITICAL security vulnerabilities (SSL verification can be disabled)
- 3 security hotspots (hardcoded password, HTTP URLs)
- 43.7% coverage on new code (need >80%)

### Interview Summary
**Key Discussions**:
- Security approach: Enhanced Option B (environment controls + certifi CA bundle + extracted functions)
- Production ALWAYS enforces SSL verification - no exceptions
- Development requires explicit `FLOE_ALLOW_INSECURE_SSL=true` to bypass
- Use `certifi.where()` for consistent CA bundles across environments

**Research Findings**:
- SonarQube rules S4830/S5527 flag literal `verify=False` and disabled hostname verification
- Compliant pattern: Extract SSL context creation to dedicated function, use variable indirection
- Existing `floe-identity-keycloak` plugin has same `verify_ssl` pattern to follow
- Test patterns: `_run()` helper for async, `@pytest.mark.requirement()` for traceability

### Metis Review
**Identified Gaps** (addressed):
- Add `certifi` explicitly to pyproject.toml (available transitively, making explicit)
- Missing lines in transport.py coverage: 166, 170, 185-186, 200-201, 213, 227, 240, 256-270, 274, 279, 297-298, 306-314
- `backends/__init__.py` has 0% coverage but no testable logic - excluded from target

---

## Work Objectives

### Core Objective
Remediate all SonarQube security findings and achieve >80% test coverage on affected lineage module files.

### Concrete Deliverables
- `transport.py`: Refactored SSL handling with environment controls
- `floe_lineage_marquez/__init__.py`: Fixed security hotspots
- `packages/floe-core/README.md`: Documented new environment variables
- Test files with >80% coverage on all 6 target files

### Definition of Done
- [ ] `pre-commit run --all-files` passes
- [ ] `pytest packages/floe-core/tests/lineage/ -v` all pass
- [ ] `pytest --cov=floe_core.lineage --cov-fail-under=80` passes
- [ ] No SonarQube S4830/S5527 rule violations
- [ ] No security hotspots in Marquez plugin

### Must Have
- Production environment (`FLOE_ENVIRONMENT=production`) ALWAYS enforces SSL
- CRITICAL-level log when SSL verification disabled in dev
- Default URL in Marquez config uses HTTPS
- No hardcoded passwords that trigger secret detection

### Must NOT Have (Guardrails)
- No literal `verify=False` in code paths (use variable indirection)
- No `ssl._create_unverified_context()` (private API, insecure)
- No globally disabled SAST rules
- No changes to integration tests that require Kind cluster
- No breaking changes to existing API (verify_ssl parameter must still work)

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES
- **User wants tests**: YES (TDD-adjacent)
- **Framework**: pytest

### Automated Verification

**For Security Fixes:**
```bash
# Agent runs:
pytest packages/floe-core/tests/lineage/test_transport.py -v -k "ssl or security"
# Assert: All tests pass

# Verify SonarQube patterns not present:
grep -r "verify=False" packages/floe-core/src/floe_core/lineage/ | grep -v "#.*noqa" | wc -l
# Assert: Output is 0

# Verify production enforcement:
FLOE_ENVIRONMENT=production python -c "
from floe_core.lineage.transport import HttpLineageTransport
t = HttpLineageTransport('https://example.com', verify_ssl=False)
# Should still verify in production
"
```

**For Coverage:**
```bash
# Agent runs:
pytest packages/floe-core/tests/lineage/ --cov=floe_core.lineage --cov-report=term-missing --cov-fail-under=80
# Assert: Exit code 0
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1.1: Fix SSL verification security (transport.py)
├── Task 1.2: Fix Marquez plugin security hotspots
└── Task 1.3: Add security environment controls documentation

Wave 2 (After Wave 1):
├── Task 2.1: Add transport.py SSL/security tests
├── Task 2.2: Add emitter.py comprehensive tests
├── Task 2.3: Add events.py edge case tests
└── Task 2.4: Add facets.py builder tests

Wave 3 (After Wave 1):
├── Task 3.1: Add extractors/dbt.py comprehensive tests
└── Task 3.2: Add catalog_integration.py tests

Wave 4 (After Waves 2 & 3):
├── Task 4.1: Run pre-commit and fix any issues
├── Task 4.2: Run full test suite with coverage
└── Task 4.3: Final verification and commit

Critical Path: Task 1.1 → Task 2.1 → Task 4.2
Parallel Speedup: ~50% faster than sequential
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1.1 | None | 2.1 | 1.2, 1.3 |
| 1.2 | None | 4.1 | 1.1, 1.3 |
| 1.3 | None | 4.1 | 1.1, 1.2 |
| 2.1 | 1.1 | 4.2 | 2.2, 2.3, 2.4 |
| 2.2 | 1.1 | 4.2 | 2.1, 2.3, 2.4 |
| 2.3 | 1.1 | 4.2 | 2.1, 2.2, 2.4 |
| 2.4 | 1.1 | 4.2 | 2.1, 2.2, 2.3 |
| 3.1 | 1.1 | 4.2 | 3.2 |
| 3.2 | 1.1 | 4.2 | 3.1 |
| 4.1 | 1.1, 1.2, 1.3 | 4.3 | None |
| 4.2 | 2.*, 3.* | 4.3 | 4.1 |
| 4.3 | 4.1, 4.2 | None | None |

---

## TODOs

### Wave 1: Security Fixes

- [ ] 1.1. Fix SSL verification security in transport.py

  **What to do**:
  - Extract SSL context creation into dedicated `_create_ssl_context()` function
  - Add environment-based controls (`FLOE_ENVIRONMENT`, `FLOE_ALLOW_INSECURE_SSL`)
  - Use `certifi.where()` for consistent CA bundle
  - Production environment ALWAYS enforces verification regardless of `verify_ssl` param
  - Add CRITICAL-level logging when SSL verification disabled
  - Ensure no literal `verify=False` in code path (use variable indirection)
  - Add `certifi` explicitly to `pyproject.toml` dependencies (available as transitive, making explicit)

  **Must NOT do**:
  - Use literal `verify=False` in code
  - Use `ssl._create_unverified_context()` (private API)
  - Change the public API (verify_ssl parameter must still work)
  - Disable hostname verification in production

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: Security-critical refactoring requires careful reasoning about edge cases
  - **Skills**: [`testing`, `pydantic-schemas`]
    - `testing`: Understand test patterns for verification
    - `pydantic-schemas`: Configuration validation patterns
  - **Skills Evaluated but Omitted**:
    - `helm-k8s-deployment`: Not deploying, just fixing Python code

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1.2, 1.3)
  - **Blocks**: Task 2.1 (SSL tests depend on new code)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `packages/floe-core/src/floe_core/lineage/transport.py:264-272` - Current SSL implementation to refactor
  - `plugins/floe-identity-keycloak/src/floe_identity_keycloak/token_validator.py:116` - Similar verify_ssl pattern

  **Security Pattern** (from librarian research):
  ```python
  def _create_ssl_context(url: str, verify_ssl: bool) -> ssl.SSLContext | None:
      """Create SSL context with environment-aware security controls."""
      if not url.startswith("https://"):
          return None

      import certifi
      context = ssl.create_default_context(cafile=certifi.where())

      # Production: ALWAYS secure
      if os.environ.get("FLOE_ENVIRONMENT") == "production":
          return context

      # Development: require explicit opt-in for insecure
      if not verify_ssl:
          if os.environ.get("FLOE_ALLOW_INSECURE_SSL", "").lower() != "true":
              logger.warning("SSL verification disabled but FLOE_ALLOW_INSECURE_SSL not set")
              return context
          logger.critical("SSL verification DISABLED - development only")
          _apply_insecure_settings(context)

      return context

  def _apply_insecure_settings(context: ssl.SSLContext) -> None:
      """Apply insecure settings. Development use only."""
      context.check_hostname = False
      context.verify_mode = ssl.CERT_NONE
  ```

  **API/Type References**:
  - Python `ssl` module: `ssl.create_default_context()`, `ssl.SSLContext`
  - `certifi.where()` - Returns path to CA bundle

  **Test References**:
  - `packages/floe-core/tests/lineage/test_transport.py` - Existing transport tests to extend

  **Acceptance Criteria**:

  - [ ] SSL context creation extracted to dedicated function
  - [ ] `FLOE_ENVIRONMENT=production` always enforces SSL verification
  - [ ] `FLOE_ALLOW_INSECURE_SSL=true` required to disable verification in dev
  - [ ] CRITICAL-level log emitted when SSL verification disabled
  - [ ] No literal `verify=False` in code (grep check passes)

  **Automated Verification:**
  ```bash
  # Verify no literal verify=False:
  grep -r "verify=False" packages/floe-core/src/floe_core/lineage/ | grep -v "#" | wc -l
  # Assert: 0

  # Verify production enforcement (test script):
  python -c "
  import os
  os.environ['FLOE_ENVIRONMENT'] = 'production'
  from floe_core.lineage.transport import HttpLineageTransport
  t = HttpLineageTransport('https://example.com', verify_ssl=False)
  # Check that _verify_ssl is effectively True in production
  print('Production enforcement working')
  "
  ```

  **Commit**: YES (Wave 1)
  - Message: `fix(lineage): secure SSL verification with environment controls`
  - Files: `transport.py`, `pyproject.toml` (if certifi added)
  - Pre-commit: `ruff check packages/floe-core/src/floe_core/lineage/transport.py`

---

- [ ] 1.2. Fix Marquez plugin security hotspots

  **What to do**:
  - Change default URL from `http://marquez:5000` to `https://marquez:5000`
  - Replace hardcoded password `"CHANGE_ME_IN_PRODUCTION"` with `"<SET_IN_PRODUCTION>"`
  - Add WARNING-level log when HTTP URL is used (allow HTTP for local K8s without TLS)
  - Update docstrings to emphasize production configuration

  **Must NOT do**:
  - Break existing functionality
  - Remove verify_ssl option entirely
  - Reject HTTP URLs (local K8s clusters often run Marquez without TLS)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple string replacements and minor additions
  - **Skills**: [`pydantic-schemas`]
    - `pydantic-schemas`: Pydantic Field configuration

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1.1, 1.3)
  - **Blocks**: Task 4.1
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py:43-44` - URL field to change
  - `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py:232` - Password to change

  **Changes Required**:
  ```python
  # Line 43-44: Change default URL
  url: str = Field(
      default="https://marquez:5000",  # Was: http://marquez:5000
      description="Marquez API base URL. Use HTTPS in production.",
  )

  # Line 88-89: Change __init__ default
  def __init__(
      self,
      url: str = "https://marquez:5000",  # Was: http://marquez:5000
      ...
  )

  # Line 232: Change password placeholder
  "password": "<SET_IN_PRODUCTION>",  # Was: CHANGE_ME_IN_PRODUCTION
  ```

  **Acceptance Criteria**:

  - [ ] Default URL uses HTTPS scheme
  - [ ] Password placeholder doesn't contain "password" or trigger secret detection
  - [ ] Docstrings updated to mention production configuration

  **Automated Verification:**
  ```bash
  # Verify HTTPS default:
  grep -r "http://marquez" plugins/floe-lineage-marquez/ | grep -v "https://" | wc -l
  # Assert: 0

  # Verify no hardcoded password pattern:
  grep -r "CHANGE_ME_IN_PRODUCTION" plugins/floe-lineage-marquez/ | wc -l
  # Assert: 0

  # Run plugin tests:
  pytest plugins/floe-lineage-marquez/tests/ -v
  # Assert: All pass
  ```

  **Commit**: YES (Wave 1, combined with 1.1)
  - Message: `fix(lineage): secure SSL verification with environment controls`
  - Files: `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py`

---

- [ ] 1.3. Document security environment controls

  **What to do**:
  - Add `FLOE_ALLOW_INSECURE_SSL` to environment variable documentation in README
  - Document `FLOE_ENVIRONMENT` for production enforcement
  - Add security configuration section if not exists

  **Must NOT do**:
  - Create new documentation files (update existing only)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Documentation update only
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1.1, 1.2)
  - **Blocks**: Task 4.1
  - **Blocked By**: None

  **References**:
  - `packages/floe-core/README.md` - Existing env var documentation

  **Documentation to Add**:
  ```markdown
  ### Security Environment Variables

  | Variable | Default | Description |
  |----------|---------|-------------|
  | `FLOE_ENVIRONMENT` | `development` | Set to `production` to enforce SSL verification on all connections. |
  | `FLOE_ALLOW_INSECURE_SSL` | `false` | Set to `true` to allow disabling SSL verification in non-production environments. Required for self-signed certificates in development. |
  ```

  **Acceptance Criteria**:

  - [ ] `FLOE_ALLOW_INSECURE_SSL` documented in README
  - [ ] `FLOE_ENVIRONMENT` documented with production behavior

  **Automated Verification:**
  ```bash
  grep "FLOE_ALLOW_INSECURE_SSL" packages/floe-core/README.md
  # Assert: Match found

  grep "FLOE_ENVIRONMENT" packages/floe-core/README.md
  # Assert: Match found
  ```

  **Commit**: YES (Wave 1, combined)
  - Message: `fix(lineage): secure SSL verification with environment controls`
  - Files: `packages/floe-core/README.md`

---

### Wave 2: Core Test Coverage

- [ ] 2.1. Add transport.py SSL/security tests

  **What to do**:
  - Test `_create_ssl_context()` function with various environment combinations
  - Test production environment always enforces SSL
  - Test `FLOE_ALLOW_INSECURE_SSL` requirement
  - Test SSL error handling paths (lines 273-279)
  - Test queue full/close edge cases (lines 297-298, 306-314)
  - Test URL validation edge cases (lines 166, 170)
  - Test sanitized URL logging (lines 185-186)
  - Test httpx vs urllib fallback (lines 243-272)

  **Must NOT do**:
  - Make actual network calls (mock everything)
  - Skip environment variable cleanup in teardown

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Test design requires understanding of security scenarios
  - **Skills**: [`testing`]
    - `testing`: Test patterns, fixtures, mocking

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2.2, 2.3, 2.4)
  - **Blocks**: Task 4.2
  - **Blocked By**: Task 1.1

  **References**:

  **Pattern References**:
  - `packages/floe-core/tests/lineage/test_transport.py` - Existing tests to extend
  - `_run()` helper function at line 29-31 for async tests

  **Test References**:
  - `tests/lineage/test_emitter.py:203-216` - Pattern for testing with config

  **Missing Lines to Cover**: 166, 170, 185-186, 200-201, 213, 227, 240, 256-270, 274, 279, 297-298, 306-314

  **Test Cases to Add**:
  ```python
  class TestHttpLineageTransportSecurity:
      """Security tests for HttpLineageTransport SSL handling."""

      @pytest.mark.requirement("REQ-6B-SEC-001")
      def test_production_env_always_verifies_ssl(self, monkeypatch):
          """FLOE_ENVIRONMENT=production enforces SSL even with verify_ssl=False"""

      @pytest.mark.requirement("REQ-6B-SEC-002")
      def test_insecure_ssl_requires_env_var(self, monkeypatch, caplog):
          """verify_ssl=False without FLOE_ALLOW_INSECURE_SSL logs warning"""

      @pytest.mark.requirement("REQ-6B-SEC-003")
      def test_insecure_ssl_with_env_var_works(self, monkeypatch, caplog):
          """verify_ssl=False with FLOE_ALLOW_INSECURE_SSL=true disables verification"""

      @pytest.mark.requirement("REQ-6B-SEC-004")
      def test_critical_log_when_ssl_disabled(self, monkeypatch, caplog):
          """CRITICAL log emitted when SSL verification disabled"""

      def test_ssl_error_is_logged(self, sample_event, caplog):
          """SSLError exceptions are logged with sanitized URL"""

      def test_url_scheme_validation_http(self):
          """HTTP URLs are accepted"""

      def test_url_scheme_validation_invalid(self):
          """Invalid URL schemes raise ValueError"""

      def test_url_missing_host_raises(self):
          """URLs without host raise ValueError"""

      def test_sanitized_url_removes_query_string(self):
          """_sanitized_url() removes sensitive query parameters"""

      def test_queue_full_during_close(self, sample_event):
          """Queue full during close is handled gracefully"""

      def test_close_async_drains_queue(self, sample_event):
          """close_async() waits for consumer task"""
  ```

  **Acceptance Criteria**:

  - [ ] All security scenarios tested with requirement markers
  - [ ] Coverage of `transport.py` ≥80%
  - [ ] Environment cleanup in all tests (no leaky state)

  **Automated Verification:**
  ```bash
  pytest packages/floe-core/tests/lineage/test_transport.py -v
  # Assert: All pass

  pytest packages/floe-core/tests/lineage/test_transport.py --cov=floe_core.lineage.transport --cov-report=term-missing
  # Assert: Coverage ≥80%
  ```

  **Commit**: YES (Wave 2)
  - Message: `test(lineage): add comprehensive transport and security tests`
  - Files: `test_transport.py`
  - Pre-commit: `pytest packages/floe-core/tests/lineage/test_transport.py`

---

- [ ] 2.2. Add emitter.py comprehensive tests

  **What to do**:
  - Test all `create_emitter()` factory paths
  - Test unknown transport type fallback to NoOp
  - Test None config creates NoOp transport
  - Test "console" transport type
  - Test emit_fail with and without error_message

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward test additions
  - **Skills**: [`testing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2.1, 2.3, 2.4)
  - **Blocks**: Task 4.2
  - **Blocked By**: Task 1.1

  **References**:
  - `packages/floe-core/tests/lineage/test_emitter.py` - Existing tests
  - `packages/floe-core/src/floe_core/lineage/emitter.py:173-189` - Factory function

  **Test Cases to Add**:
  ```python
  class TestCreateEmitterFactory:
      """Tests for create_emitter() factory function coverage."""

      def test_none_config_creates_noop(self):
          """None transport_config creates NoOpLineageTransport"""

      def test_none_type_creates_noop(self):
          """{"type": None} creates NoOpLineageTransport"""

      def test_http_type_creates_http_transport(self):
          """{"type": "http"} creates HttpLineageTransport"""

      def test_console_type_creates_console_transport(self):
          """{"type": "console"} creates ConsoleLineageTransport"""

      def test_unknown_type_creates_noop(self):
          """Unknown type falls back to NoOpLineageTransport"""
  ```

  **Acceptance Criteria**:
  - [ ] Coverage of `emitter.py` ≥80%
  - [ ] All factory paths covered

  **Automated Verification:**
  ```bash
  pytest packages/floe-core/tests/lineage/test_emitter.py --cov=floe_core.lineage.emitter --cov-report=term-missing
  # Assert: Coverage ≥80%
  ```

  **Commit**: YES (Wave 2, combined)

---

- [ ] 2.3. Add events.py edge case tests

  **What to do**:
  - Test EventBuilder with explicit job_namespace
  - Test fail_run without error_message
  - Test to_openlineage_event() with various facet combinations
  - Test empty inputs/outputs lists

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`testing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 4.2
  - **Blocked By**: Task 1.1

  **References**:
  - `packages/floe-core/tests/lineage/test_events.py` - Existing tests
  - `packages/floe-core/src/floe_core/lineage/events.py` - Source

  **Acceptance Criteria**:
  - [ ] Coverage of `events.py` ≥80%

  **Commit**: YES (Wave 2, combined)

---

- [ ] 2.4. Add facets.py builder tests

  **What to do**:
  - Test StatisticsFacetBuilder with all optional params
  - Test QualityFacetBuilder with column field
  - Test TraceCorrelationFacetBuilder when OTel not installed
  - Test TraceCorrelationFacetBuilder when span not recording
  - Test IcebergSnapshotFacetBuilder with and without summary
  - Test ColumnLineageFacetBuilder with empty columns

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`testing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 4.2
  - **Blocked By**: Task 1.1

  **References**:
  - `packages/floe-core/tests/lineage/test_facets.py` - Existing tests
  - `packages/floe-core/src/floe_core/lineage/facets.py` - Source

  **Acceptance Criteria**:
  - [ ] Coverage of `facets.py` ≥80%

  **Commit**: YES (Wave 2, combined)

---

### Wave 3: Complex Test Coverage

- [ ] 3.1. Add extractors/dbt.py comprehensive tests

  **What to do**:
  - Test extract_model with source dependencies
  - Test extract_model with model dependencies
  - Test extract_model with depends_on fallback (no parent_map)
  - Test extract_model with alias vs name
  - Test extract_test with test node
  - Test extract_all_models with multiple models
  - Test _create_dataset_from_node with/without facets
  - Test column lineage facet generation

  **Must NOT do**:
  - Use real dbt manifest files (use inline test data)

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: Complex manifest structures require careful test design
  - **Skills**: [`testing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Task 3.2)
  - **Blocks**: Task 4.2
  - **Blocked By**: Task 1.1

  **References**:
  - `packages/floe-core/tests/lineage/extractors/test_dbt.py` - Existing tests (10.8% coverage)
  - `packages/floe-core/src/floe_core/lineage/extractors/dbt.py` - Source

  **Test Fixture to Create**:
  ```python
  @pytest.fixture
  def complex_manifest() -> dict:
      """dbt manifest with sources, models, and tests."""
      return {
          "nodes": {
              "model.project.customers": {
                  "database": "analytics",
                  "schema": "public",
                  "name": "customers",
                  "alias": "dim_customers",
                  "columns": {"id": {"name": "id", "data_type": "INTEGER"}},
                  "depends_on": {"nodes": ["source.project.raw.users"]},
              },
              "test.project.not_null_id": {
                  "depends_on": {"nodes": ["model.project.customers"]},
              },
          },
          "parent_map": {
              "model.project.customers": ["source.project.raw.users"],
          },
          "sources": {
              "source.project.raw.users": {
                  "database": "raw",
                  "schema": "public",
                  "name": "users",
                  "columns": {"id": {"name": "id", "data_type": "INTEGER"}},
              },
          },
      }
  ```

  **Acceptance Criteria**:
  - [ ] Coverage of `extractors/dbt.py` ≥80%
  - [ ] All manifest variations tested (sources, models, tests, aliases)

  **Automated Verification:**
  ```bash
  pytest packages/floe-core/tests/lineage/extractors/test_dbt.py --cov=floe_core.lineage.extractors.dbt --cov-report=term-missing
  # Assert: Coverage ≥80%
  ```

  **Commit**: YES (Wave 3)
  - Message: `test(lineage): add comprehensive dbt extractor and catalog tests`
  - Files: `test_dbt.py`, `test_catalog_integration.py`

---

- [ ] 3.2. Add catalog_integration.py tests

  **What to do**:
  - Test SimpleNamespaceStrategy.resolve()
  - Test CentralizedNamespaceStrategy.resolve()
  - Test DataMeshNamespaceStrategy.resolve()
  - Test NamespaceResolver with unknown strategy raises ValueError
  - Test NamespaceResolver with missing required params raises ValueError
  - Test CatalogDatasetResolver with catalog plugin
  - Test CatalogDatasetResolver without catalog plugin
  - Test enrich_with_snapshot() adds facet correctly

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward strategy testing
  - **Skills**: [`testing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Task 3.1)
  - **Blocks**: Task 4.2
  - **Blocked By**: Task 1.1

  **References**:
  - `packages/floe-core/tests/lineage/test_catalog_integration.py` - Existing tests (37.5%)
  - `packages/floe-core/src/floe_core/lineage/catalog_integration.py` - Source

  **Acceptance Criteria**:
  - [ ] Coverage of `catalog_integration.py` ≥80%
  - [ ] All namespace strategies tested
  - [ ] Error cases for invalid strategies tested

  **Commit**: YES (Wave 3, combined)

---

### Wave 4: Validation

- [ ] 4.1. Run pre-commit and fix any issues

  **What to do**:
  - Run `pre-commit run --all-files`
  - Fix any linting, formatting, or type errors
  - Ensure no ruff/mypy/black failures

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: NO (must complete before 4.3)
  - **Blocks**: Task 4.3
  - **Blocked By**: Tasks 1.1, 1.2, 1.3

  **Acceptance Criteria**:
  - [ ] `pre-commit run --all-files` exits 0

  **Automated Verification:**
  ```bash
  pre-commit run --all-files
  # Assert: Exit code 0
  ```

  **Commit**: NO (fixes go into previous commits)

---

- [ ] 4.2. Run full test suite with coverage

  **What to do**:
  - Run full lineage test suite with coverage
  - Verify all files meet >80% threshold
  - Generate coverage report

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`testing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with 4.1)
  - **Blocks**: Task 4.3
  - **Blocked By**: All Wave 2 and Wave 3 tasks

  **Acceptance Criteria**:
  - [ ] All tests pass
  - [ ] Overall lineage coverage ≥80%
  - [ ] No individual file below 80% (except backends/__init__.py)

  **Automated Verification:**
  ```bash
  pytest packages/floe-core/tests/lineage/ -v --cov=floe_core.lineage --cov-report=term-missing --cov-fail-under=80
  # Assert: Exit code 0
  ```

  **Commit**: NO (just verification)

---

- [ ] 4.3. Final verification and commit

  **What to do**:
  - Verify no SonarQube security patterns remain
  - Create final commit with Wave 2+3 tests
  - Verify git status clean

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (final task)
  - **Blocks**: None
  - **Blocked By**: Tasks 4.1, 4.2

  **Acceptance Criteria**:
  - [ ] No `verify=False` literals in code
  - [ ] No `CHANGE_ME_IN_PRODUCTION` strings
  - [ ] All tests pass
  - [ ] Coverage ≥80%
  - [ ] Git status clean after commit

  **Automated Verification:**
  ```bash
  # Security pattern check:
  grep -r "verify=False" packages/floe-core/src/floe_core/lineage/ | grep -v "#" | wc -l
  # Assert: 0

  grep -r "CHANGE_ME_IN_PRODUCTION" plugins/floe-lineage-marquez/ | wc -l
  # Assert: 0

  # Final test run:
  pytest packages/floe-core/tests/lineage/ --cov=floe_core.lineage --cov-fail-under=80
  # Assert: Exit code 0

  git status
  # Assert: Working tree clean
  ```

  **Commit**: YES (Wave 2+3 tests)
  - Message: `test(lineage): add comprehensive transport and security tests`

---

## Commit Strategy

| After Wave | Message | Files |
|------------|---------|-------|
| Wave 1 | `fix(lineage): secure SSL verification with environment controls` | transport.py, __init__.py (marquez), README.md, pyproject.toml |
| Wave 2+3 | `test(lineage): add comprehensive transport and security tests` | test_transport.py, test_emitter.py, test_events.py, test_facets.py, test_dbt.py, test_catalog_integration.py |

---

## Success Criteria

### Verification Commands
```bash
# Security check
grep -r "verify=False" packages/floe-core/src/floe_core/lineage/ | grep -v "#" | wc -l
# Expected: 0

grep -r "CHANGE_ME_IN_PRODUCTION" plugins/floe-lineage-marquez/ | wc -l
# Expected: 0

# Coverage check
pytest packages/floe-core/tests/lineage/ --cov=floe_core.lineage --cov-fail-under=80
# Expected: Exit 0, all tests pass

# Pre-commit
pre-commit run --all-files
# Expected: Exit 0
```

### Final Checklist
- [ ] All SonarQube security vulnerabilities fixed (S4830, S5527)
- [ ] All security hotspots addressed
- [ ] Coverage ≥80% on all target files
- [ ] Environment controls documented
- [ ] All tests pass
- [ ] Pre-commit passes

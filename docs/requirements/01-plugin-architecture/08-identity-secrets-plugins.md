# REQ-071 to REQ-087: Identity and Secrets Plugin Standards

**Domain**: Plugin Architecture
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

IdentityPlugin and SecretsPlugin provide authentication/authorization and secrets management capabilities. Identity plugins (OIDC, JWT) secure service-to-service communication; Secrets plugins (Infisical, K8s, Vault) manage sensitive configuration.

**Key ADRs**: ADR-0022 (Security & RBAC), ADR-0023 (Secrets Management), ADR-0031 (Infisical), ADR-0024 (OIDC)

## Requirements

### REQ-071: IdentityPlugin ABC Definition **[New]**

**Requirement**: IdentityPlugin MUST define abstract methods: authenticate_service(), generate_jwt(), validate_token(), get_security_context().

**Rationale**: Enforces consistent interface for authentication mechanisms.

**Acceptance Criteria**:
- [ ] ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 4 abstract methods defined with type hints
- [ ] Docstrings explain purpose, parameters, return values
- [ ] mypy --strict passes on interface definition

**Enforcement**: ABC enforcement tests, mypy strict mode
**Test Coverage**: `tests/contract/test_identity_plugin.py::test_abc_compliance`
**Traceability**: plugin-architecture.md, ADR-0022

---

### REQ-072: IdentityPlugin Service Authentication **[New]**

**Requirement**: IdentityPlugin.authenticate_service() MUST authenticate service-to-service requests and return credentials.

**Rationale**: Enables service identity verification without hardcoded credentials.

**Acceptance Criteria**:
- [ ] Accepts service name and authentication method
- [ ] Returns temporary credentials (tokens, certificates)
- [ ] Credentials expire and refresh automatically
- [ ] Supports OAuth2, JWT, mTLS mechanisms
- [ ] No credentials logged or exposed

**Enforcement**: Authentication tests, token expiration tests
**Test Coverage**: `tests/integration/test_identity_service_auth.py`
**Traceability**: ADR-0022, ADR-0024

---

### REQ-073: IdentityPlugin JWT Generation **[New]**

**Requirement**: IdentityPlugin.generate_jwt() MUST generate signed JWT tokens for service-to-service communication.

**Rationale**: Enables row-level security and context propagation.

**Acceptance Criteria**:
- [ ] Generates JWT with standard claims (sub, iat, exp)
- [ ] Includes custom claims for floe context (namespace, roles)
- [ ] JWT signed with plugin-specific algorithm (HS256, RS256)
- [ ] Expiration configurable (default 1 hour)
- [ ] Tokens not logged or exposed

**Enforcement**: JWT validation tests, claim verification tests
**Example**: JWT includes `{"sub": "service-account:floe-job-runner", "namespace": "sales", "roles": ["data_reader"]}`
**Test Coverage**: `tests/integration/test_identity_jwt_generation.py`
**Traceability**: ADR-0022

---

### REQ-074: IdentityPlugin Token Validation **[New]**

**Requirement**: IdentityPlugin.validate_token() MUST verify JWT tokens and return security context.

**Rationale**: Enables API servers to verify caller identity.

**Acceptance Criteria**:
- [ ] Verifies JWT signature and expiration
- [ ] Extracts claims from token
- [ ] Returns security context (user/service, roles, namespaces)
- [ ] Rejects expired or invalid tokens
- [ ] Error messages not leaking security details

**Enforcement**: Token validation tests, security tests
**Test Coverage**: `tests/unit/test_identity_token_validation.py`
**Traceability**: ADR-0022

---

### REQ-075: IdentityPlugin Security Context **[New]**

**Requirement**: IdentityPlugin.get_security_context() MUST return security context for downstream authorization decisions.

**Rationale**: Enables row-level security and access control.

**Acceptance Criteria**:
- [ ] Returns dict with user/service identity, roles, namespaces
- [ ] Includes tenant isolation information
- [ ] Supports dynamic role resolution
- [ ] Context propagates through request chain
- [ ] No sensitive data in context (use opaque IDs)

**Enforcement**: Security context validation tests
**Test Coverage**: `tests/integration/test_identity_security_context.py`
**Traceability**: ADR-0022

---

### REQ-076: SecretsPlugin ABC Definition **[New]**

**Requirement**: SecretsPlugin MUST define abstract methods: get_secret(), create_secret(), inject_env_vars(), generate_secret_mounts().

**Rationale**: Enforces consistent interface for secrets management.

**Acceptance Criteria**:
- [ ] ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 4 abstract methods defined with type hints
- [ ] Docstrings explain purpose, parameters, return values
- [ ] mypy --strict passes on interface definition

**Enforcement**: ABC enforcement tests, mypy strict mode
**Test Coverage**: `tests/contract/test_secrets_plugin.py::test_abc_compliance`
**Traceability**: plugin-architecture.md, ADR-0023

---

### REQ-077: SecretsPlugin Secret Retrieval **[New]**

**Requirement**: SecretsPlugin.get_secret() MUST retrieve secrets by name from the backend.

**Rationale**: Enables runtime secret injection into jobs and services.

**Acceptance Criteria**:
- [ ] Accepts secret name and optional namespace
- [ ] Returns dict[str, str] with secret values
- [ ] Handles missing secrets gracefully
- [ ] Values never logged or exposed
- [ ] Supports dynamic refresh on change

**Enforcement**: Secret retrieval tests, error handling tests
**Test Coverage**: `tests/integration/test_secrets_retrieval.py`
**Traceability**: ADR-0023

---

### REQ-078: SecretsPlugin Secret Creation **[New]**

**Requirement**: SecretsPlugin.create_secret() MUST create or update secrets in the backend.

**Rationale**: Enables programmatic secret provisioning.

**Acceptance Criteria**:
- [ ] Accepts secret name, namespace, and key-value pairs
- [ ] Creates new secret or updates existing
- [ ] Returns success/failure status
- [ ] Idempotent: creating same secret twice succeeds
- [ ] Secret values never logged or exposed

**Enforcement**: Secret creation tests, idempotency tests
**Test Coverage**: `tests/integration/test_secrets_creation.py`
**Traceability**: ADR-0023

---

### REQ-079: SecretsPlugin Environment Variable Injection **[New]**

**Requirement**: SecretsPlugin.inject_env_vars() MUST generate environment variable configuration for job pods.

**Rationale**: Enables secrets injection into container environment.

**Acceptance Criteria**:
- [ ] Accepts mapping of secret refs (name to env var)
- [ ] Returns K8s pod spec fragment or env var config
- [ ] Supports envFrom secretRef syntax
- [ ] Config integrates with K8s Job spec

**Enforcement**: Pod spec generation tests, K8s validation tests
**Test Coverage**: `tests/unit/test_secrets_env_vars.py`
**Traceability**: ADR-0023

---

### REQ-080: SecretsPlugin Secret Mounting **[New]**

**Requirement**: SecretsPlugin.generate_secret_mounts() MUST generate Kubernetes pod spec for mounting secrets.

**Rationale**: Enables secrets injection via environment variables or volume mounts.

**Acceptance Criteria**:
- [ ] Accepts secret name and optional mount path
- [ ] Returns K8s pod spec fragment
- [ ] Supports envFrom (env vars) and volume mounts
- [ ] Config integrates with K8s Job spec

**Enforcement**: Pod spec generation tests
**Test Coverage**: `tests/unit/test_secrets_mounts.py`
**Traceability**: ADR-0023

---

### REQ-081: Identity and Secrets Plugin Implementations **[New]**

**Requirement**: System MUST provide reference implementations for Identity (OIDC) and Secrets (Infisical, K8s) plugins.

**Rationale**: Covers standard deployments without requiring custom plugin development.

**Acceptance Criteria**:
- [ ] OIDCIdentityPlugin: OIDC with JWT validation
- [ ] K8sSecretsPlugin: Native K8s Secrets
- [ ] InfisicalSecretsPlugin: Infisical (default OSS)
- [ ] All implementations pass compliance test suite
- [ ] Each implementation includes documentation

**Enforcement**: Plugin compliance tests for each implementation
**Test Coverage**: `tests/integration/test_identity_secrets_implementations.py`
**Traceability**: ADR-0022, ADR-0023

---

### REQ-082: Identity and Secrets Plugin Error Handling **[New]**

**Requirement**: Identity and Secrets plugins MUST handle failures gracefully with actionable error messages.

**Rationale**: Enables operators to diagnose and recover from failures.

**Acceptance Criteria**:
- [ ] Catches plugin-specific exceptions
- [ ] Translates to PluginExecutionError with context
- [ ] Error messages suggest resolution steps
- [ ] No stack traces or sensitive data exposed
- [ ] Includes debug context in logs

**Enforcement**: Error handling tests, security tests
**Test Coverage**: `tests/unit/test_identity_secrets_error_handling.py`
**Traceability**: ADR-0025 (Exception Handling)

---

### REQ-083: Identity and Secrets Plugin Type Safety **[New]**

**Requirement**: Identity and Secrets plugin implementations MUST pass mypy --strict with full type annotations.

**Acceptance Criteria**:
- [ ] All methods have type hints
- [ ] Return types match ABC signatures
- [ ] mypy --strict passes on plugin implementations
- [ ] No use of Any except for truly dynamic values

**Enforcement**: mypy in CI/CD, type checking tests
**Test Coverage**: CI/CD mypy validation
**Traceability**: python-standards.md

---

### REQ-084: Identity and Secrets Plugin Compliance Test Suite **[New]**

**Requirement**: System MUST provide BaseIdentityPluginTests and BaseSecretsPluginTests classes for compliance validation.

**Rationale**: Ensures all plugins meet minimum security and functionality requirements.

**Acceptance Criteria**:
- [ ] BaseIdentityPluginTests in testing/base_classes/
- [ ] BaseSecretsPluginTests in testing/base_classes/
- [ ] Tests all ABC methods for each plugin type
- [ ] Tests authentication and secret operations
- [ ] Tests error handling and security
- [ ] Tests K8s integration

**Enforcement**: Plugin compliance tests must pass for all implementations
**Test Coverage**: `testing/base_classes/base_identity_plugin_tests.py`, `testing/base_classes/base_secrets_plugin_tests.py`
**Traceability**: TESTING.md

---

### REQ-085: Identity and Secrets Plugin Security Standards **[New]**

**Requirement**: Identity and Secrets plugins MUST adhere to security standards: no credential logging, secure credential rotation, audit trail support.

**Rationale**: Prevents credential compromise and ensures compliance.

**Acceptance Criteria**:
- [ ] No credentials logged or printed
- [ ] Credentials never in error messages
- [ ] Secret rotation supported with zero-downtime
- [ ] Audit trail for secret access (where applicable)
- [ ] Uses K8s Secrets or encrypted backends
- [ ] OWASP Top 10 compliance verified

**Enforcement**: Security scanning, credential tests, audit tests
**Test Coverage**: `tests/unit/test_identity_secrets_security.py`
**Traceability**: security.md, ADR-0022, ADR-0023

---

### REQ-086: IdentityPlugin Test Fixtures **[New]**

**Requirement**: System MUST provide test fixtures for IdentityPlugin implementations that extend the Epic 9C testing framework.

**Rationale**: Integration tests for identity implementations (Keycloak, Dex) require OIDC/JWT fixtures to validate authentication, token generation, and security context extraction.

**Acceptance Criteria**:
- [ ] Fixture module: `testing/fixtures/identity.py` (extends 9C patterns)
- [ ] `IdentityTestConfig(BaseModel)` with `frozen=True`
- [ ] Context manager: `identity_provider_context()` for lifecycle
- [ ] Implementation fixtures: `keycloak_fixture()`, `dex_fixture()` for testing
- [ ] Mock fixtures for unit tests (no real IdP required)
- [ ] K8s manifest: `testing/k8s/services/keycloak.yaml` for integration tests
- [ ] Extends: `IntegrationTestBase` from Epic 9C
- [ ] Type hints: mypy --strict passes
- [ ] Test coverage: >80% of fixture code

**Constraints**:
- MUST extend Epic 9C testing framework (`testing.base_classes`)
- MUST follow fixture pattern from `testing/fixtures/__init__.py`
- MUST use Pydantic v2 `ConfigDict(frozen=True)` for config
- MUST support credential injection via environment variables
- MUST NOT expose test credentials in logs or error messages

**Test Coverage**: `testing/tests/unit/test_identity_fixtures.py`

**Traceability**:
- Epic 9C (Testing Framework dependency)
- Epic 7A (IdentityPlugin)
- ADR-0065 (K8s-native testing)

---

### REQ-087: SecretsPlugin Test Fixtures **[New]**

**Requirement**: System MUST provide test fixtures for SecretsPlugin implementations that extend the Epic 9C testing framework.

**Rationale**: Integration tests for secrets implementations (Vault, Infisical) require secrets backend fixtures to validate secret retrieval, creation, and K8s secret mounting.

**Acceptance Criteria**:
- [ ] Fixture module: `testing/fixtures/secrets.py` (extends 9C patterns)
- [ ] `SecretsTestConfig(BaseModel)` with `frozen=True`
- [ ] Context manager: `secrets_backend_context()` for lifecycle
- [ ] Implementation fixtures: `vault_fixture()`, `infisical_fixture()` for testing
- [ ] Mock fixtures for unit tests (no real backend required)
- [ ] K8s manifest: `testing/k8s/services/vault.yaml` for integration tests
- [ ] Extends: `IntegrationTestBase` from Epic 9C
- [ ] Type hints: mypy --strict passes
- [ ] Test coverage: >80% of fixture code

**Constraints**:
- MUST extend Epic 9C testing framework (`testing.base_classes`)
- MUST follow fixture pattern from `testing/fixtures/__init__.py`
- MUST use Pydantic v2 `ConfigDict(frozen=True)` for config
- MUST support credential injection via environment variables
- MUST NOT expose secret values in logs or error messages

**Test Coverage**: `testing/tests/unit/test_secrets_fixtures.py`

**Traceability**:
- Epic 9C (Testing Framework dependency)
- Epic 7A (SecretsPlugin)
- ADR-0065 (K8s-native testing)

---

## Domain Acceptance Criteria

Identity and Secrets Standards (REQ-071 to REQ-087) complete when:

- [ ] All 15 requirements documented with complete fields
- [ ] IdentityPlugin and SecretsPlugin ABCs defined
- [ ] At least 1 reference implementation per plugin type
- [ ] Contract tests pass for all implementations
- [ ] Integration tests validate authentication and secret flows
- [ ] Security audit completed (Aikido scan)
- [ ] Documentation backreferences all requirements

## Epic Mapping

**Epic 3: Plugin Interface Extraction** - Extract identity and secrets management to plugins

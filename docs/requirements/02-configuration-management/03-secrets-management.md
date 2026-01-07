# REQ-131 to REQ-140: Secrets Management and Credential Injection

**Domain**: Configuration Management
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines the secrets management system that securely handles credentials for database connections, API access, and other sensitive configuration without exposing secrets in code or logs.

**Key Principle**: Secrets managed externally (Infisical, K8s Secrets, Vault), never hardcoded (ADR-0031)

## Requirements

### REQ-131: SecretsPlugin Interface **[New]**

**Requirement**: System MUST define SecretsPlugin ABC in `floe_core/plugin_interfaces/secrets.py` with required methods: get_secret, create_secret, inject_env_vars, generate_secret_mounts.

**Rationale**: Enables pluggable secrets backends without hardcoding credential handling.

**Acceptance Criteria**:
- [ ] SecretsPlugin ABC defined with required methods
- [ ] get_secret(name: str, namespace: str) → dict[str, str]
- [ ] create_secret(name: str, namespace: str, data: dict) → None
- [ ] inject_env_vars(secret_refs: dict) → dict[str, Any]
- [ ] generate_secret_mounts(secret_name: str) → dict (K8s pod spec)
- [ ] PluginMetadata required (name, version, floe_api_version)
- [ ] Registered via entry_points: floe.secrets

**Enforcement**:
- Plugin interface compliance tests
- Abstract method validation tests
- Entry point registration tests

**Constraints**:
- MUST inherit from ABC with abstractmethod decorators
- MUST NOT expose secrets in return values (use SecretStr)
- FORBIDDEN to log secrets

**Test Coverage**: `tests/contract/test_secrets_plugin.py`

**Traceability**:
- adr/0031-infisical-secrets.md lines 78-115
- Domain 01 (Plugin Architecture)

---

### REQ-132: Infisical Plugin Implementation **[New]**

**Requirement**: System MUST provide `floe-secrets-infisical` plugin implementing SecretsPlugin using Infisical SDK and InfisicalSecret CRD for Kubernetes-native secret management.

**Rationale**: Provides production-ready, actively maintained secrets backend with native K8s integration.

**Acceptance Criteria**:
- [ ] InfisicalSecretsPlugin implements SecretsPlugin interface
- [ ] Uses infisicalsdk for API access
- [ ] Supports Universal Auth (client_id, client_secret)
- [ ] Configurable site_url (cloud or self-hosted)
- [ ] Configurable project_id and environment
- [ ] Supports secret scoping: /compute/snowflake/, /catalog/polaris/
- [ ] Caches credentials to avoid repeated API calls
- [ ] Clear error messages for auth failures

**Enforcement**:
- SDK integration tests
- Authentication tests
- Credential caching tests
- Error handling tests

**Constraints**:
- MUST use official infisicalsdk package
- MUST NOT hardcode credentials
- FORBIDDEN to log auth tokens

**Test Coverage**: `plugins/floe-secrets-infisical/tests/unit/test_infisical_plugin.py`

**Traceability**:
- adr/0031-infisical-secrets.md lines 118-175
- REQ-131 (SecretsPlugin Interface)

---

### REQ-133: InfisicalSecret CRD Support for K8s Pod Injection **[New]**

**Requirement**: System MUST support InfisicalSecret Kubernetes CRD (Custom Resource Definition) with auto-reload annotation for pod-level secret injection.

**Rationale**: Enables automatic secret rotation without manual pod restart.

**Acceptance Criteria**:
- [ ] Generate InfisicalSecret YAML from floe configuration
- [ ] CRD spec includes: projectSlug, envSlug, secretsPath
- [ ] Support auto-reload annotation: `secrets.infisical.com/auto-reload: "true"`
- [ ] Support resyncInterval (default 60s)
- [ ] Sync secrets to K8s Secret named by reference
- [ ] Pod restart when secret changes
- [ ] Clear error if Infisical Operator not installed

**Enforcement**:
- CRD generation tests
- K8s Secret sync tests
- Pod restart tests
- Error handling tests

**Constraints**:
- MUST follow Infisical CRD schema
- MUST validate required fields
- FORBIDDEN to expose secrets in pod logs

**Test Coverage**: `tests/integration/test_infisical_crd.py`

**Traceability**:
- adr/0031-infisical-secrets.md lines 177-214
- REQ-132 (Infisical Plugin Implementation)

---

### REQ-134: K8s Secrets Plugin as Fallback **[New]**

**Requirement**: System MUST provide `floe-secrets-k8s` plugin implementing SecretsPlugin using native Kubernetes Secrets for simple deployments without external dependencies.

**Rationale**: Provides minimal-dependency option for development and simple deployments.

**Acceptance Criteria**:
- [ ] K8sSecretsPlugin implements SecretsPlugin interface
- [ ] Uses Kubernetes Python client to manage Secrets
- [ ] Supports custom namespace (default: floe-jobs)
- [ ] No external service dependencies
- [ ] Manual secret creation via kubectl (not managed by plugin)
- [ ] Clear documentation for manual K8s secret setup
- [ ] Fallback when Infisical unavailable

**Enforcement**:
- K8s client integration tests
- Namespace handling tests
- Error handling tests

**Constraints**:
- MUST use official Kubernetes Python client
- MUST handle missing secrets gracefully
- FORBIDDEN to create secrets automatically

**Test Coverage**: `plugins/floe-secrets-k8s/tests/unit/test_k8s_plugin.py`

**Traceability**:
- adr/0031-infisical-secrets.md lines 218-227
- REQ-131 (SecretsPlugin Interface)

---

### REQ-135: Secrets Configuration in Platform Manifest **[New]**

**Requirement**: System MUST support secrets plugin configuration in Manifest via plugins.secrets field with plugin type, auth config, and secret references for compute/catalog/ingestion.

**Rationale**: Enables platform team to select secrets backend without code changes.

**Acceptance Criteria**:
- [ ] plugins.secrets field in Manifest: type (infisical/k8s/vault)
- [ ] Infisical config: site_url, project_id, auth (client_id, client_secret)
- [ ] K8s config: namespace (default: floe-jobs)
- [ ] Vault config: address, auth_method, role
- [ ] Secret references: connection_secret_ref per compute target
- [ ] Example: connection_secret_ref: snowflake-credentials
- [ ] Clear error if secrets not configured

**Enforcement**:
- Configuration validation tests
- Plugin selection tests
- Credential validation tests

**Constraints**:
- MUST support multiple backends
- MUST validate auth credentials
- FORBIDDEN to hardcode credentials in config

**Test Coverage**: `tests/unit/test_secrets_configuration.py`

**Traceability**:
- adr/0031-infisical-secrets.md lines 216-241

---

### REQ-136: Secret Reference Injection in dbt profiles.yml **[New]**

**Requirement**: System MUST support secret references in dbt profiles.yml via `{{ env_var('SECRET_NAME') }}` syntax, resolved at runtime from secrets backend.

**Rationale**: Enables dbt to access secrets without hardcoding credentials.

**Acceptance Criteria**:
- [ ] Secret references: {{ env_var('SNOWFLAKE_PASSWORD') }}
- [ ] Resolved at runtime from secrets backend
- [ ] SecretsPlugin injects as K8s environment variables
- [ ] Pod receives environment variables before dbt execution
- [ ] Error if secret not found: "Secret 'SNOWFLAKE_PASSWORD' not found in namespace"
- [ ] Supports multiple secrets in single profile

**Enforcement**:
- Secret reference tests
- Runtime injection tests
- Error handling tests
- Integration tests with dbt

**Constraints**:
- MUST resolve secrets at pod startup
- MUST handle missing secrets gracefully
- FORBIDDEN to log secret values

**Test Coverage**: `tests/integration/test_secret_injection.py`

**Traceability**:
- adr/0031-infisical-secrets.md lines 244-311
- REQ-132 (Infisical Plugin Implementation)

---

### REQ-137: Secret Mounting as Files in K8s Pods **[New]**

**Requirement**: System MUST support mounting secrets as files in K8s pods via volumeMounts for applications that require file-based credentials (e.g., private keys, certificates).

**Rationale**: Enables certificate-based authentication (SSL, TLS, OAuth private keys).

**Acceptance Criteria**:
- [ ] generate_secret_mounts() returns K8s volumeMounts spec
- [ ] Mount path: /run/secrets/{secret_name}/
- [ ] Supports multiple files per secret
- [ ] Example: private key in /run/secrets/google-sa/key.json
- [ ] Pod can read credentials from mounted files
- [ ] Error if volume mounts not supported by backend

**Enforcement**:
- Volume mount spec tests
- File access tests
- Permission tests

**Constraints**:
- MUST use K8s volume mount syntax
- MUST set proper file permissions (600)
- FORBIDDEN to expose sensitive files in logs

**Test Coverage**: `tests/integration/test_secret_file_mounting.py`

**Traceability**:
- adr/0031-infisical-secrets.md

---

### REQ-138: Secret Rotation and Auto-Reload **[New]**

**Requirement**: System MUST support automatic secret rotation and pod auto-reload when secrets change in backend (Infisical), without manual intervention.

**Rationale**: Enables automatic credential rotation without downtime.

**Acceptance Criteria**:
- [ ] Infisical auto-reload annotation: secrets.infisical.com/auto-reload: "true"
- [ ] Configurable sync interval (default 60s)
- [ ] Operator watches for secret changes
- [ ] Pod restarts automatically with new credentials
- [ ] Job completes before secret expires
- [ ] Clear logging of secret rotation events
- [ ] No manual pod restart required

**Enforcement**:
- Auto-reload tests
- Pod restart tests
- Secret update tests
- Logging tests

**Constraints**:
- MUST support automatic pod restart
- MUST handle secret update during job execution
- FORBIDDEN to require manual intervention

**Test Coverage**: `tests/integration/test_secret_auto_reload.py`

**Traceability**:
- adr/0031-infisical-secrets.md lines 369-387
- REQ-133 (InfisicalSecret CRD Support)

---

### REQ-139: Secrets Namespace Isolation **[New]**

**Requirement**: System MUST isolate secrets by Kubernetes namespace to prevent products from accessing secrets outside their domain/namespace.

**Rationale**: Prevents unauthorized access to other domains' credentials.

**Acceptance Criteria**:
- [ ] K8s namespace per domain: floe-sales, floe-marketing, floe-finance
- [ ] Products can only access secrets in their namespace
- [ ] RBAC restricts cross-namespace secret access
- [ ] Error if product tries to access secret outside namespace
- [ ] Namespace derived from domain: floe-{domain}
- [ ] Clear error messages for access violations

**Enforcement**:
- RBAC tests
- Access control tests
- Namespace isolation tests
- Error handling tests

**Constraints**:
- MUST enforce K8s RBAC
- MUST prevent cross-namespace access
- FORBIDDEN to allow privilege escalation

**Test Coverage**: `tests/integration/test_secrets_namespace_isolation.py`

**Traceability**:
- security.md
- REQ-125 (Access Control Enforcement via Catalog RBAC)

---

### REQ-140: Secrets Audit Logging **[New]**

**Requirement**: System MUST log all secret access attempts (successful and failed) with timestamp, user/service, action, and secret name (NOT value) for audit compliance.

**Rationale**: Enables compliance audits and security investigations.

**Acceptance Criteria**:
- [ ] Log all secret get/create operations
- [ ] Log includes: timestamp, requester, action, secret_name
- [ ] Log does NOT include secret values
- [ ] Logs structured (JSON format for production)
- [ ] Failed access attempts logged
- [ ] Integration with audit backend (e.g., CloudTrail, Splunk)
- [ ] Audit logs retention: configurable (default 90 days)

**Enforcement**:
- Audit logging tests
- No-secrets-in-logs tests
- Structured logging tests
- Retention policy tests

**Constraints**:
- MUST NOT log secret values
- MUST NOT log auth tokens
- MUST log all access attempts (successes and failures)
- FORBIDDEN to skip audit logging

**Test Coverage**: `tests/unit/test_secrets_audit_logging.py`

**Traceability**:
- security.md
- adr/0031-infisical-secrets.md lines 389-393

---

## Domain Acceptance Criteria

Secrets Management and Credential Injection (REQ-131 to REQ-140) is complete when:

- [ ] All 10 requirements have complete template fields
- [ ] SecretsPlugin interface defined
- [ ] Infisical plugin implemented with InfisicalSecret CRD
- [ ] K8s Secrets plugin as fallback
- [ ] Secret references resolved at runtime
- [ ] Secret file mounting supported
- [ ] Auto-reload functionality working
- [ ] Namespace isolation enforced
- [ ] Audit logging implemented
- [ ] Unit tests pass with >80% coverage
- [ ] Integration tests pass with real Infisical/K8s
- [ ] Documentation updated:
  - [ ] adr/0031-infisical-secrets.md backreferences requirements
  - [ ] security.md backreferences requirements

## Epic Mapping

These requirements are satisfied in **Epic 5: Secrets Management & Security**:
- Phase 1: SecretsPlugin interface and Infisical implementation
- Phase 2: K8s Secrets fallback and configuration
- Phase 3: Secret injection and auto-reload
- Phase 4: Audit logging and namespace isolation

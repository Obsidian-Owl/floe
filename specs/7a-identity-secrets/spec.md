# Feature Specification: Identity & Secrets Plugin System

**Epic**: 7A (Identity & Secrets)
**Feature Branch**: `7a-identity-secrets`
**Created**: 2026-01-18
**Status**: Draft
**Input**: User description: "Implement Identity and Secrets Plugin ABCs with K8s Secrets, Infisical, and Keycloak reference implementations for secure credential management across the floe platform"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - SecretReference Runtime Resolution (Priority: P0)

As a data engineer, I want secrets resolved at runtime so that credentials never appear in configuration files or git history.

**Why this priority**: Security is non-negotiable. Secrets in code/config are the #1 security vulnerability in data platforms. This is the foundation all other stories depend on.

**Independent Test**: Can be fully tested by configuring a SecretReference in manifest.yaml, running `floe compile`, and verifying the output profiles.yml contains only `env_var()` references with no actual secrets.

**Acceptance Scenarios**:

1. **Given** a manifest.yaml with `connection_secret_ref: snowflake-credentials`, **When** `floe compile` runs, **Then** profiles.yml contains `{{ env_var('SNOWFLAKE_PASSWORD') }}` not the actual password.

2. **Given** a K8s Secret `snowflake-credentials` exists in namespace `floe-jobs`, **When** a dbt job pod starts, **Then** environment variables are injected via `envFrom: secretRef`.

3. **Given** a SecretReference with `source: kubernetes`, **When** the secret doesn't exist, **Then** the job fails with a clear error message indicating the missing secret.

---

### User Story 2 - Kubernetes Secrets Backend (Priority: P0)

As a platform operator, I want K8s Secrets as the default secrets backend so that I can use native Kubernetes security without external dependencies.

**Why this priority**: K8s Secrets is the simplest deployment path (zero external dependencies). Required for development environments and basic production deployments.

**Independent Test**: Can be fully tested by creating a K8s Secret, configuring `floe-secrets-k8s` plugin, and verifying secret retrieval/injection works end-to-end.

**Acceptance Scenarios**:

1. **Given** `plugins.secrets.type: k8s` in manifest.yaml, **When** deploying to Kubernetes, **Then** no external secrets management is required.

2. **Given** a K8sSecretsPlugin instance, **When** calling `get_secret("db-creds", "floe-jobs")`, **Then** returns the secret data as a dictionary.

3. **Given** a K8sSecretsPlugin instance, **When** calling `list_secrets("db-")`, **Then** returns all secrets with names starting with "db-".

4. **Given** secrets are updated in K8s, **When** pod restarts (via Reloader annotation), **Then** the new secret values are available.

---

### User Story 3 - Infisical Secrets Backend (Priority: P1)

As a platform operator, I want Infisical integration so that I can use an actively-maintained OSS secrets management solution with auto-reload capabilities.

**Why this priority**: Infisical replaces ESO (paused development) as the recommended OSS solution per ADR-0031. Provides auto-reload, centralized secrets UI, and audit logging.

**Independent Test**: Can be fully tested by configuring InfisicalSecret CRs, verifying K8s Secret sync, and testing pod auto-reload on secret changes.

**Acceptance Scenarios**:

1. **Given** `plugins.secrets.type: infisical` in manifest.yaml, **When** an InfisicalSecret CR is created, **Then** the Infisical Operator syncs secrets to a K8s Secret.

2. **Given** an InfisicalSecretsPlugin instance with valid credentials, **When** calling `get_all_secrets("production", "/compute/snowflake")`, **Then** returns all secrets from that path.

3. **Given** `secrets.infisical.com/auto-reload: "true"` annotation on a Deployment, **When** a secret changes in Infisical, **Then** pods are automatically restarted.

4. **Given** sync interval of 60 seconds, **When** a secret is updated in Infisical, **Then** the K8s Secret is updated within 60 seconds.

---

### User Story 4 - OAuth2/OIDC Authentication (Priority: P1)

As a platform operator, I want external identity provider integration so that users can authenticate using corporate SSO (Keycloak, Okta, Azure AD).

**Why this priority**: Enterprise deployments require SSO. Human access to Dagster UI, Grafana, and other platform services needs centralized authentication.

**Independent Test**: Can be fully tested by configuring Keycloak, creating OIDC clients, and verifying token-based authentication flow.

**Acceptance Scenarios**:

1. **Given** a KeycloakPlugin instance, **When** calling `get_oidc_config("floe")`, **Then** returns valid OIDCConfig with all required endpoints.

2. **Given** valid client credentials, **When** calling `authenticate(credentials)`, **Then** returns a valid JWT access token.

3. **Given** a valid JWT token, **When** calling `validate_token(token)`, **Then** returns TokenValidationResult with user info and expiration.

4. **Given** an expired token, **When** calling `validate_token(token)`, **Then** returns `valid=False` with appropriate error message.

---

### User Story 5 - Secret Audit Logging (Priority: P2)

As a security officer, I want all secret access audited so that I can track credential usage for compliance requirements.

**Why this priority**: Required for SOC 2, ISO 27001, and enterprise compliance. Provides security incident investigation capability.

**Independent Test**: Can be fully tested by accessing secrets and verifying audit log entries contain requester identity, timestamp, and secret path.

**Acceptance Scenarios**:

1. **Given** audit logging enabled, **When** a secret is accessed via SecretsPlugin, **Then** an audit event is logged with requester identity.

2. **Given** a secret access audit log, **When** queried by time range, **Then** returns all access events within that period.

3. **Given** an audit event, **Then** it contains: timestamp, requester_id, secret_path, operation (read/write), and source_ip.

---

### Edge Cases

- What happens when a secret backend is temporarily unavailable?
  - Cached credentials should be used if available (within cache TTL)
  - Clear error message indicating backend unavailability
  - Retry with exponential backoff before failing

- How does the system handle secret key name collisions across backends?
  - Namespace-scoped secrets prevent collisions
  - Clear naming convention enforced: `{service}-{environment}-credentials`

- What happens when token refresh fails during a long-running job?
  - Token should be refreshed before expiration (configurable threshold)
  - Job should fail gracefully with clear authentication error
  - Automatic retry with fresh token before final failure

- How are secrets handled during pod termination?
  - Secrets remain in environment variables until pod terminates
  - No cleanup required (K8s handles pod lifecycle)
  - Graceful shutdown allows in-flight operations to complete

## Requirements *(mandatory)*

### Functional Requirements

#### Core Plugin Interfaces

- **FR-001**: System MUST provide `IdentityPlugin` ABC with `authenticate()`, `get_user_info()`, and `validate_token()` methods.

- **FR-002**: System MUST provide `SecretsPlugin` ABC with `get_secret()`, `set_secret()`, and `list_secrets()` methods.

- **FR-003**: System MUST provide `SecretReference` Pydantic model for manifest-level secret declarations (source, name, key).

- **FR-004**: All plugin implementations MUST inherit from `PluginMetadata` and declare `name`, `version`, and `floe_api_version`.

#### K8s Secrets Plugin (Default)

- **FR-010**: System MUST provide `K8sSecretsPlugin` as the default secrets backend requiring no external dependencies.

- **FR-011**: `K8sSecretsPlugin` MUST support namespace-scoped secret access using the K8s API.

- **FR-012**: `K8sSecretsPlugin` MUST generate pod spec fragments with `envFrom: secretRef` for environment variable injection.

- **FR-013**: `K8sSecretsPlugin` MUST support both in-cluster and kubeconfig-based authentication.

#### Infisical Secrets Plugin

- **FR-020**: System MUST provide `InfisicalSecretsPlugin` for integration with Infisical (MIT-licensed OSS).

- **FR-021**: `InfisicalSecretsPlugin` MUST support Universal Auth (client ID/secret) authentication.

- **FR-022**: `InfisicalSecretsPlugin` MUST integrate with the Infisical K8s Operator via `InfisicalSecret` CRD.

- **FR-023**: `InfisicalSecretsPlugin` MUST support auto-reload pods when secrets change (via operator annotation).

- **FR-024**: `InfisicalSecretsPlugin` MUST support path-based secret organization (e.g., `/compute/snowflake/`).

#### Keycloak Identity Plugin (Default)

- **FR-030**: System MUST provide `KeycloakPlugin` as the default OIDC identity provider.

- **FR-031**: `KeycloakPlugin` MUST return valid `OIDCConfig` with discovery, JWKS, authorization, token, and userinfo endpoints.

- **FR-032**: `KeycloakPlugin` MUST support realm-based multi-tenancy for Data Mesh domain isolation.

- **FR-033**: `KeycloakPlugin` MUST support client creation with configurable scopes and redirect URIs.

- **FR-034**: `KeycloakPlugin` MUST validate JWT tokens using JWKS endpoint verification.

#### Token and Credential Management

- **FR-040**: System MUST support automatic token refresh before expiration (configurable threshold, default: 30 seconds).

- **FR-041**: System MUST provide `TokenValidationResult` dataclass with `valid`, `user_info`, `error`, and `expires_at` fields.

- **FR-042**: System MUST provide `UserInfo` dataclass with `subject`, `email`, `name`, `roles`, `groups`, and `claims` fields.

- **FR-043**: System MUST NOT expose secret values in logs, error messages, or stack traces (use `SecretStr` for runtime values).

#### Environment Variable Injection

- **FR-050**: System MUST convert `SecretReference` to dbt-compatible `env_var()` syntax via `to_env_var_syntax()` method.

- **FR-051**: System MUST generate environment variable names following pattern: `FLOE_SECRET_{NAME}_{KEY}` (uppercase, underscores).

- **FR-052**: System MUST support multi-key secrets (e.g., `db-creds` with `username`, `password`, `host` keys).

#### Security Requirements

- **FR-060**: All secrets plugins MUST raise `PermissionError` when lacking permission to access a secret.

- **FR-061**: All secrets plugins MUST raise `ConnectionError` when unable to connect to the backend.

- **FR-062**: Secret values MUST use `pydantic.SecretStr` at runtime to prevent accidental logging.

- **FR-063**: System MUST support Kubernetes RBAC for service account-based secret access.

### Key Entities

- **IdentityPlugin**: Abstract base class for authentication providers. Handles OAuth2/OIDC flows, token validation, and user info retrieval.

- **SecretsPlugin**: Abstract base class for credential management backends. Provides secure secret storage, retrieval, and injection.

- **SecretReference**: Immutable Pydantic model representing a pointer to a secret. Never contains actual secret values.

- **UserInfo**: Dataclass containing authenticated user information (subject, email, roles, groups).

- **TokenValidationResult**: Dataclass containing token validation status and user context.

- **OIDCConfig**: Dataclass containing OIDC provider endpoint URLs for service integration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All secrets plugins pass compliance test suite (`BaseSecretsPluginTests`) with 100% method coverage.

- **SC-002**: All identity plugins pass compliance test suite (`BaseIdentityPluginTests`) with 100% method coverage.

- **SC-003**: Secret resolution latency under 100ms for cached lookups, under 500ms for uncached.

- **SC-004**: Zero secrets appear in `floe compile` output, logs, or error messages.

- **SC-005**: Token validation latency under 50ms using cached JWKS.

- **SC-006**: Secrets sync from Infisical to K8s Secret completes within configured interval (default: 60s).

- **SC-007**: Auto-reload triggers pod restart within 30 seconds of secret sync completion.

- **SC-008**: All secret access operations produce audit log entries within 1 second.

## Assumptions

- Kubernetes 1.28+ is available (required for K8s Secrets API)
- Keycloak 24.0+ is available for identity provider (per ADR-0024)
- Infisical Operator is pre-installed for `floe-secrets-infisical` plugin
- Network connectivity exists between job pods and secrets backends
- RBAC is configured to allow service accounts to access required secrets

### External Operator Dependencies

**Note on SC-006 and SC-007**: These success criteria are satisfied by external Kubernetes operators, not by floe plugin code:

| Success Criteria | External Operator | Plugin Responsibility |
|------------------|-------------------|----------------------|
| **SC-006**: Secrets sync within 60s | Infisical Operator (`infisical-operator`) | Configure `InfisicalSecret` CRD via plugin config; operator handles sync |
| **SC-007**: Auto-reload within 30s | Reloader (`stakater/Reloader`) | Add `secrets.infisical.com/auto-reload: "true"` annotation; Reloader handles restart |

The `floe-secrets-infisical` plugin provides:
- Configuration models for Infisical connection (client ID, secret, project ID)
- `InfisicalSecret` CRD generation for operator consumption
- Secret path organization and retrieval via Infisical SDK

The actual K8s Secret synchronization and pod restart are handled entirely by the pre-installed operators.

## Out of Scope

- HashiCorp Vault integration (future Epic or commercial plugin)
- AWS Secrets Manager direct integration (use Infisical bidirectional sync)
- GCP Secret Manager direct integration (use Infisical bidirectional sync)
- Azure Key Vault direct integration (use Infisical bidirectional sync)
- Secret backup and disaster recovery
- Dex identity provider plugin (lightweight alternative, future Epic)
- Multi-factor authentication (MFA) configuration

## References

- ADR-0023: Secrets Management Architecture
- ADR-0024: Identity and Access Management
- ADR-0031: Infisical as Default Secrets Management
- `packages/floe-core/src/floe_core/plugins/identity.py` - IdentityPlugin ABC (existing)
- `packages/floe-core/src/floe_core/plugins/secrets.py` - SecretsPlugin ABC (existing)
- `packages/floe-core/src/floe_core/schemas/secrets.py` - SecretReference model (existing)
- `docs/plans/epics/07-security/epic-07a-identity-secrets.md` - Epic specification

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Epic 12A: Tech Debt Q1 2026

**Architecture Improvements:**

- Break circular dependency between `floe_core` and `floe_rbac_k8s` via registry lookup pattern
- Extract `_BatchFetcher` class for parallel OCI manifest fetching (fixes N+1 performance issue)
- Split `IcebergTableManager` god class into focused internal classes:
  - `_IcebergTableLifecycle` - create, drop, exists operations
  - `_IcebergSchemaManager` - schema evolution operations
  - `_IcebergSnapshotManager` - snapshot operations
  - `_IcebergCompactionManager` - compaction operations

**Performance Optimizations:**

- OCI client `list()` now uses parallel fetching with ThreadPoolExecutor (5x faster)
- OCI client `pull()` uses dictionary lookup instead of linear search
- Added `limit` parameter to `plugin_registry.list()` for pagination
- Added `max_violations` parameter to `PolicyEnforcer.enforce()` for early exit

**Testing Infrastructure:**

- New base test classes in `testing/base_classes/`:
  - `BasePluginMetadataTests` - Validates PluginMetadata ABC compliance
  - `BasePluginLifecycleTests` - Validates lifecycle hook implementations
  - `BasePluginDiscoveryTests` - Validates entry point discovery (11 reusable tests)
- Migrated DuckDB, Polaris, and Dagster plugin tests to use base classes
- Eliminated 100% of duplicated discovery test code across plugins
- Golden test utilities for behavior-preserving refactoring

**Dependency Cleanup:**

- Removed `croniter` dependency (replaced with regex-based cron validation)
- Removed `pytz` dependency (replaced with Python stdlib `zoneinfo`)

**Code Quality:**

- All 3991 unit tests pass with 87.77% coverage
- mypy --strict passes on key modified files
- No circular import errors

#### Epic 7A: Identity & Secrets Plugin System

**New Packages:**

- `floe-secrets-k8s` - Kubernetes Secrets backend plugin for native K8s secret management
- `floe-secrets-infisical` - Infisical secrets backend plugin for centralized OSS secrets management
- `floe-identity-keycloak` - Keycloak identity provider plugin for OAuth2/OIDC authentication

**Plugin ABCs (floe-core):**

- `SecretsPlugin` - Abstract base class for secrets backends
  - `get_secret(name)` - Retrieve a single secret value
  - `set_secret(name, value)` - Create or update a secret
  - `list_secrets(prefix)` - List secrets with optional prefix filter
  - `get_multi_key_secret(name)` - Retrieve multi-key secrets (e.g., username + password)
  - `generate_pod_env_spec(secret_names)` - Generate K8s pod env spec for secret injection

- `IdentityPlugin` - Abstract base class for identity providers
  - `authenticate(credentials)` - Authenticate user and return access token
  - `validate_token(token)` - Validate JWT token and return user info
  - `refresh_token(refresh_token)` - Refresh expired access token
  - `get_user_info(token)` - Get user profile information
  - `get_oidc_config()` - Get OIDC discovery configuration

**Schema Definitions (floe-core):**

- `SecretReference` - Pydantic model for referencing secrets in configuration
- `SecretsPluginConfig` - Base configuration for secrets plugins
- `IdentityPluginConfig` - Base configuration for identity plugins
- `TokenValidationResult` - Result of token validation with user info
- `UserInfo` - User profile information from identity provider
- `OIDCConfig` - OIDC discovery configuration

**Audit Logging:**

- Structured audit logging for all secret access operations
- JSON-formatted logs via `structlog` with OpenTelemetry trace context
- Audit events include: requester_id, secret_path, operation, result, timestamp

**Plugin Features:**

- K8s Secrets Plugin:
  - Namespace-scoped secret access
  - In-cluster and kubeconfig authentication
  - Pod spec generation for envFrom injection

- Infisical Secrets Plugin:
  - Universal Auth authentication
  - Path-based secret organization
  - InfisicalSecret CRD integration for K8s sync
  - OpenTelemetry tracing support

- Keycloak Identity Plugin:
  - OIDC/OAuth2 authentication flows
  - JWT validation with JWKS
  - Realm-based multi-tenancy
  - Token refresh support

**Entry Points:**

- `floe.secrets`:
  - `k8s` -> `floe_secrets_k8s:K8sSecretsPlugin`
  - `infisical` -> `floe_secrets_infisical:InfisicalSecretsPlugin`

- `floe.identity`:
  - `keycloak` -> `floe_identity_keycloak:KeycloakIdentityPlugin`

**Documentation:**

- Quickstart guide at `specs/7a-identity-secrets/quickstart.md`
- Audit logging documentation with query examples
- InfisicalSecret CRD integration guide

### Changed

- Updated `floe-core` with new plugin ABCs for identity and secrets management

### Security

- All secrets use `pydantic.SecretStr` to prevent accidental logging
- Audit logging captures all secret access for compliance
- JWT validation uses JWKS for secure key management

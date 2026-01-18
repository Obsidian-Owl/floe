# Implementation Plan: Epic 7A - Identity & Secrets Plugins

**Branch**: `7a-identity-secrets` | **Date**: 2026-01-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/7a-identity-secrets/spec.md`

## Summary

Implement Identity and Secrets plugin interfaces with three reference implementations:
- **K8sSecretsPlugin**: Default secrets backend using Kubernetes Secrets (zero dependencies)
- **InfisicalSecretsPlugin**: Recommended OSS secrets manager per ADR-0031
- **KeycloakIdentityPlugin**: Default OIDC identity provider per ADR-0024

The existing ABCs (`IdentityPlugin`, `SecretsPlugin`) and `SecretReference` model in floe-core define the contracts. This epic creates concrete implementations following established plugin patterns from `floe-compute-duckdb` and `floe-catalog-polaris`.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**:
- floe-core>=0.1.0 (plugin interfaces, schemas)
- kubernetes>=26.0.0 (K8s Secrets backend)
- python-keycloak>=3.0.0 (Keycloak admin API)
- authlib>=1.2.0 (OIDC/JWT validation)
- infisicalsdk>=2.0.0 (Infisical integration)
- pydantic>=2.0 (configuration validation)
- structlog>=24.0 (logging)
- opentelemetry-api>=1.0 (tracing)
- tenacity>=8.0 (retry logic)
- httpx>=0.25.0 (HTTP client)

**Storage**: N/A (plugins access external secrets/identity backends)
**Testing**: pytest with K8s-native integration tests (Kind cluster)
**Target Platform**: Kubernetes 1.28+
**Project Type**: Plugin packages (3 new packages under `plugins/`)
**Performance Goals**:
- Token validation: <50ms (cached JWKS)
- Secret retrieval: <100ms
- Health check: <5s timeout
**Constraints**:
- Zero secrets in logs or error messages
- SecretStr for all credential fields
- All plugins implement PluginMetadata lifecycle
**Scale/Scope**: 3 plugin packages, ~1500 LOC each

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (plugins/floe-secrets-*, plugins/floe-identity-*)
- [x] No SQL parsing/validation in Python (N/A - no SQL in this epic)
- [x] No orchestration logic outside floe-dagster (N/A)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (ABC)
- [x] Plugin registered via entry point (not direct import)
- [x] PluginMetadata declares name, version, floe_api_version

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s)
- [x] Pluggable choices documented in manifest.yaml

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (not direct coupling)
- [x] Pydantic v2 models for all schemas
- [x] Contract changes follow versioning rules

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic
- [x] Credentials use SecretStr
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only
- [x] Layer ownership respected (Data Team vs Platform Team)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted
- [x] OpenLineage events for data transformations (N/A - no data transforms)

## Project Structure

### Documentation (this feature)

```text
specs/7a-identity-secrets/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Technical decisions
├── data-model.md        # Entity definitions
├── quickstart.md        # Getting started guide
├── contracts/           # Interface contracts
│   ├── identity-plugin-interface.md
│   └── secrets-plugin-interface.md
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
plugins/
├── floe-secrets-k8s/
│   ├── src/floe_secrets_k8s/
│   │   ├── __init__.py          # Export K8sSecretsPlugin
│   │   ├── plugin.py            # K8sSecretsPlugin implementation
│   │   ├── config.py            # K8sSecretsConfig (Pydantic)
│   │   └── errors.py            # Custom exceptions
│   ├── tests/
│   │   ├── conftest.py          # Test fixtures
│   │   ├── unit/
│   │   │   ├── test_config.py
│   │   │   └── test_plugin.py
│   │   └── integration/
│   │       ├── test_discovery.py
│   │       └── test_k8s_secrets.py
│   └── pyproject.toml           # Entry point: floe.secrets -> k8s
│
├── floe-secrets-infisical/
│   ├── src/floe_secrets_infisical/
│   │   ├── __init__.py
│   │   ├── plugin.py            # InfisicalSecretsPlugin
│   │   ├── config.py            # InfisicalSecretsConfig
│   │   └── errors.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── unit/
│   │   │   ├── test_config.py
│   │   │   └── test_plugin.py
│   │   └── integration/
│   │       ├── test_discovery.py
│   │       └── test_infisical.py
│   └── pyproject.toml           # Entry point: floe.secrets -> infisical
│
└── floe-identity-keycloak/
    ├── src/floe_identity_keycloak/
    │   ├── __init__.py
    │   ├── plugin.py            # KeycloakIdentityPlugin
    │   ├── config.py            # KeycloakIdentityConfig
    │   ├── jwks_cache.py        # JWKS caching for token validation
    │   └── errors.py
    ├── tests/
    │   ├── conftest.py
    │   ├── unit/
    │   │   ├── test_config.py
    │   │   ├── test_token_validation.py
    │   │   └── test_user_info.py
    │   └── integration/
    │       ├── test_discovery.py
    │       └── test_keycloak.py
    └── pyproject.toml           # Entry point: floe.identity -> keycloak

testing/
└── k8s/
    └── services/
        └── keycloak.yaml        # Keycloak test deployment

tests/
└── contract/
    └── test_identity_secrets_contracts.py  # Plugin ABC compliance
```

**Structure Decision**: Three separate plugin packages following the established pattern from `floe-compute-duckdb`. Each package is independently installable and registered via entry points.

## Complexity Tracking

> No Constitution Check violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

## Implementation Phases

### Phase 1: Core Plugin Infrastructure
1. Create plugin package scaffolding (3 packages)
2. Implement configuration models (Pydantic v2)
3. Register entry points in pyproject.toml

### Phase 2: K8s Secrets Plugin
1. Implement K8sSecretsPlugin with kubernetes client
2. Add auto-detection for in-cluster vs kubeconfig
3. Implement health_check() and lifecycle methods
4. Unit tests with mocked kubernetes client
5. Integration tests with Kind cluster

### Phase 3: Infisical Secrets Plugin
1. Implement InfisicalSecretsPlugin with infisicalsdk
2. Support Universal Auth authentication
3. Handle self-hosted and cloud Infisical
4. Unit tests with mocked SDK
5. Integration tests (optional - requires Infisical deployment)

### Phase 4: Keycloak Identity Plugin
1. Implement KeycloakIdentityPlugin with python-keycloak
2. Add JWKS caching for token validation
3. Support realm-based multi-tenancy
4. Unit tests with mocked Keycloak
5. Integration tests with Keycloak in Kind

### Phase 5: Contract and E2E Testing
1. BaseSecretsPluginTests compliance tests
2. BaseIdentityPluginTests compliance tests
3. Cross-plugin integration scenarios
4. Documentation and examples

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| K8s Secrets as default | kubernetes client | Zero dependencies, works everywhere |
| Infisical over ESO | infisicalsdk | ADR-0031: ESO paused, Infisical MIT license |
| Keycloak as default IdP | python-keycloak | ADR-0024: Production-ready, realm-based |
| JWKS caching | 1hr TTL in-memory | <50ms validation target |
| Error handling | PermissionError, ConnectionError | Consistent with ABC contracts |

## References

- [ADR-0023: Secrets Management](../../docs/architecture/adr/0023-secrets-management.md)
- [ADR-0024: Identity & Access Management](../../docs/architecture/adr/0024-identity-access-management.md)
- [ADR-0031: Infisical Replaces ESO](../../docs/architecture/adr/0031-infisical-replaces-eso.md)
- [Plugin System Architecture](../../docs/architecture/plugin-system/index.md)

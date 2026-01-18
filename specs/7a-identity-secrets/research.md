# Research: Epic 7A - Identity & Secrets Plugins

**Date**: 2026-01-18
**Status**: Complete
**Branch**: `7a-identity-secrets`

## Prior Decisions (from Agent-Memory)

Agent-memory search found relevant prior context:
- **Secrets Plugin**: Implements Secrets Management, handles storage and retrieval of credentials
- **Identity Management**: Uses plugins to facilitate secure storage and access to secrets

## Executive Summary

This research consolidates technical decisions for implementing Identity and Secrets plugins in the floe platform. The codebase already has:
- `IdentityPlugin` ABC with authenticate/get_user_info/validate_token methods
- `SecretsPlugin` ABC with get_secret/set_secret/list_secrets methods
- `SecretReference` Pydantic model for manifest-level declarations
- Plugin registry with entry point discovery

Implementation follows established patterns from `floe-compute-duckdb` and `floe-catalog-polaris` plugins.

---

## Research Topics

### R1: Plugin Infrastructure Patterns

**Decision**: Follow existing plugin structure from `floe-compute-duckdb` and `floe-catalog-polaris`.

**Rationale**: Consistency with existing plugins ensures maintainability and leverages proven patterns.

**Key Findings**:

1. **Directory Structure**:
   ```
   plugins/floe-{category}-{tech}/
   ├── src/floe_{category}_{tech}/
   │   ├── __init__.py          # Export public API
   │   ├── plugin.py            # Main XyzPlugin class
   │   ├── config.py            # Pydantic configuration
   │   └── errors.py            # Custom exceptions
   ├── tests/
   │   ├── unit/
   │   └── integration/
   └── pyproject.toml           # Entry point registration
   ```

2. **Entry Point Registration**:
   ```toml
   [project.entry-points."floe.identity"]
   keycloak = "floe_identity_keycloak.plugin:KeycloakIdentityPlugin"

   [project.entry-points."floe.secrets"]
   k8s = "floe_secrets_k8s.plugin:K8sSecretsPlugin"
   infisical = "floe_secrets_infisical.plugin:InfisicalSecretsPlugin"
   ```

3. **PluginMetadata Base Class**:
   - Required properties: `name`, `version`, `floe_api_version`
   - Lifecycle methods: `startup()`, `shutdown()`, `health_check()`
   - Configuration: `get_config_schema()` returns Pydantic model

**Alternatives Considered**:
- Direct import pattern: Rejected (doesn't support dynamic discovery)
- YAML-based plugin manifest: Rejected (adds configuration complexity)

---

### R2: K8s Secrets Backend Implementation

**Decision**: Use `kubernetes` Python client for K8s Secrets access.

**Rationale**: Official client, well-maintained, supports both in-cluster and kubeconfig auth.

**Implementation Pattern**:
```python
from kubernetes import client, config

class K8sSecretsPlugin(SecretsPlugin):
    def __init__(self, namespace: str = "default"):
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self.v1 = client.CoreV1Api()
        self.namespace = namespace

    def get_secret(self, key: str) -> str | None:
        try:
            secret = self.v1.read_namespaced_secret(key, self.namespace)
            return base64.b64decode(secret.data[key]).decode()
        except ApiException as e:
            if e.status == 404:
                return None
            raise
```

**Key Design Decisions**:
- Auto-detect cluster vs local config
- Namespace-scoped by default (security)
- Return None for missing secrets (not exception)
- Raise exceptions for permission/connection errors

**Alternatives Considered**:
- `kopf` (Kubernetes Operator Framework): Overkill for simple secret access
- Direct REST calls via `httpx`: Loses auth handling benefits of official client

---

### R3: Infisical Secrets Backend Implementation

**Decision**: Use `infisicalsdk` (official Python SDK) with Universal Auth.

**Rationale**: Per ADR-0031, Infisical replaces ESO as recommended OSS solution. SDK provides native integration.

**Implementation Pattern**:
```python
from infisicalsdk import InfisicalClient

class InfisicalSecretsPlugin(SecretsPlugin):
    def __init__(
        self,
        client_id: str,
        client_secret: SecretStr,
        site_url: str = "https://app.infisical.com",
        project_id: str = None,
    ):
        self.client = InfisicalClient(
            client_id=client_id,
            client_secret=client_secret.get_secret_value(),
            site_url=site_url,
        )
        self.project_id = project_id
```

**Key Design Decisions**:
- Universal Auth (client ID/secret) for service-to-service
- Support both cloud and self-hosted Infisical
- Path-based secret organization (`/compute/snowflake/`)
- Rely on Infisical Operator for K8s Secret sync

**Integration with K8s Operator**:
```yaml
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: snowflake-credentials
  annotations:
    secrets.infisical.com/auto-reload: "true"
spec:
  resyncInterval: 60
  secretsScope:
    projectSlug: floe-platform
    envSlug: production
    secretsPath: /compute/snowflake
```

**Alternatives Considered**:
- External Secrets Operator (ESO): PAUSED development (ADR-0031)
- Direct Infisical REST API: SDK provides better error handling and auth

---

### R4: Keycloak Identity Provider Implementation

**Decision**: Use `python-keycloak` library for Keycloak admin API, `authlib` for OIDC flows.

**Rationale**: Per ADR-0024, Keycloak is default OIDC provider. `python-keycloak` is official client.

**Implementation Pattern**:
```python
from keycloak import KeycloakAdmin, KeycloakOpenID
from authlib.integrations.requests_client import OAuth2Session

class KeycloakIdentityPlugin(IdentityPlugin):
    def __init__(self, config: KeycloakConfig):
        self.server_url = config.server_url
        self.realm = config.realm
        self.admin = KeycloakAdmin(
            server_url=config.server_url,
            realm_name=config.realm,
            client_id=config.admin_client_id,
            client_secret_key=config.admin_client_secret.get_secret_value(),
        )
        self.oidc = KeycloakOpenID(
            server_url=config.server_url,
            realm_name=config.realm,
            client_id=config.client_id,
            client_secret_key=config.client_secret.get_secret_value(),
        )
```

**Key Design Decisions**:
- Separate admin client (for client management) from OIDC client (for auth flows)
- Realm-based multi-tenancy (Data Mesh domain isolation)
- JWKS caching for token validation performance
- Support for client creation via admin API

**Alternatives Considered**:
- Dex: Lightweight but lacks admin API for client management
- Direct OIDC via `authlib` only: Loses Keycloak-specific features (realm management)

---

### R5: Token Validation and JWKS Caching

**Decision**: Use `authlib` with in-memory JWKS caching and automatic refresh.

**Rationale**: JWKS endpoint should be cached for performance (SC-005: <50ms validation).

**Implementation Pattern**:
```python
from authlib.jose import jwt, JsonWebKey
import httpx
import time

class JWKSCache:
    def __init__(self, jwks_uri: str, ttl_seconds: int = 3600):
        self.jwks_uri = jwks_uri
        self.ttl = ttl_seconds
        self._cache = None
        self._expires_at = 0

    def get_key(self, header: dict) -> JsonWebKey:
        if time.time() > self._expires_at:
            response = httpx.get(self.jwks_uri)
            self._cache = JsonWebKey.import_key_set(response.json())
            self._expires_at = time.time() + self.ttl
        return self._cache.find_by_kid(header["kid"])
```

**Key Design Decisions**:
- 1-hour default cache TTL (configurable)
- Automatic refresh on expiration
- Thread-safe access
- Fallback to re-fetch on key not found (rotation handling)

**Alternatives Considered**:
- No caching: Would exceed 50ms latency target
- Redis-based caching: Overkill for single-pod deployments

---

### R6: Audit Logging Integration

**Decision**: Use structlog with OpenTelemetry trace context for audit events.

**Rationale**: Consistent with floe observability patterns. OTel provides distributed tracing.

**Implementation Pattern**:
```python
import structlog
from opentelemetry import trace

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)

def get_secret(self, key: str) -> str | None:
    with tracer.start_as_current_span("get_secret") as span:
        span.set_attribute("secret.key", key)

        result = self._backend.get(key)

        # Audit log (never logs actual secret value)
        logger.info(
            "secret_accessed",
            key=key,
            found=result is not None,
            requester=self._get_requester_identity(),
            trace_id=span.get_span_context().trace_id,
        )

        return result
```

**Key Design Decisions**:
- Never log secret values
- Include requester identity from service account context
- Include trace ID for correlation
- Structured JSON format for SIEM ingestion

**Alternatives Considered**:
- Separate audit service: Adds latency, overkill for MVP
- File-based audit: Doesn't support distributed tracing

---

### R7: Error Handling Strategy

**Decision**: Raise standard exceptions per ABC contracts.

**Rationale**: Consistent error types enable proper handling by consumers.

**Exception Hierarchy**:
```python
# Built-in exceptions used per ABC contracts
PermissionError  # Lacking permission to access secret
ConnectionError  # Unable to connect to backend

# Plugin-specific exceptions
class SecretsPluginError(Exception):
    """Base exception for secrets plugins."""
    pass

class SecretNotFoundError(SecretsPluginError):
    """Secret key does not exist."""
    pass

class SecretValidationError(SecretsPluginError):
    """Secret format validation failed."""
    pass
```

**Error Mapping**:
| Backend Error | Plugin Exception |
|---------------|------------------|
| K8s 403 Forbidden | `PermissionError` |
| K8s 404 Not Found | Return `None` |
| K8s Connection refused | `ConnectionError` |
| Infisical 401 Unauthorized | `PermissionError` |
| Keycloak 401 Invalid token | `TokenValidationResult(valid=False)` |

---

### R8: Configuration Schema Design

**Decision**: Pydantic v2 models with SecretStr for credentials.

**K8s Secrets Config**:
```python
class K8sSecretsConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str = Field(
        default="default",
        description="K8s namespace for secrets"
    )
    kubeconfig_path: str | None = Field(
        default=None,
        description="Path to kubeconfig (None = in-cluster)"
    )
```

**Infisical Secrets Config**:
```python
class InfisicalSecretsConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    site_url: str = Field(
        default="https://app.infisical.com",
        description="Infisical server URL"
    )
    client_id: str = Field(..., description="Universal Auth client ID")
    client_secret: SecretStr = Field(..., description="Universal Auth client secret")
    project_id: str = Field(..., description="Infisical project ID")
    environment: str = Field(
        default="production",
        description="Environment slug"
    )
```

**Keycloak Identity Config**:
```python
class KeycloakIdentityConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    server_url: str = Field(..., description="Keycloak server URL")
    realm: str = Field(default="floe", description="Realm name")
    client_id: str = Field(..., description="OIDC client ID")
    client_secret: SecretStr = Field(..., description="OIDC client secret")
    admin_client_id: str | None = Field(
        default=None,
        description="Admin API client ID (for client management)"
    )
    admin_client_secret: SecretStr | None = Field(
        default=None,
        description="Admin API client secret"
    )
```

---

### R9: Testing Strategy

**Decision**: Layered testing with K8s-native integration tests.

**Test Organization**:
```
plugins/floe-secrets-k8s/tests/
├── unit/
│   ├── test_config.py        # Config validation
│   ├── test_plugin.py        # Mock K8s client
│   └── test_env_injection.py # Pod spec generation
└── integration/
    ├── test_discovery.py     # Entry point registration
    └── test_k8s_secrets.py   # Real K8s cluster (Kind)

plugins/floe-identity-keycloak/tests/
├── unit/
│   ├── test_config.py
│   ├── test_token_validation.py  # Mock JWKS
│   └── test_user_info.py
└── integration/
    ├── test_discovery.py
    └── test_keycloak.py      # Real Keycloak (K8s)
```

**Test Infrastructure**:
- Inherit from `PluginTestBase` for integration tests
- K8s test fixtures in `testing/k8s/services/`:
  - `keycloak.yaml` - Keycloak deployment for testing
  - `infisical.yaml` - Infisical deployment (optional)
- Use `@pytest.mark.requirement()` for traceability

---

### R10: Dependencies Summary

**Core Dependencies (all plugins)**:
```toml
dependencies = [
    "floe-core>=0.1.0",
    "pydantic>=2.0",
    "structlog>=24.0",
    "opentelemetry-api>=1.0",
    "tenacity>=8.0",
]
```

**K8s Secrets Plugin**:
```toml
dependencies = [
    # Core deps above
    "kubernetes>=26.0.0",
]
```

**Infisical Secrets Plugin**:
```toml
dependencies = [
    # Core deps above
    "infisicalsdk>=2.0.0",
    "httpx>=0.25.0",
]
```

**Keycloak Identity Plugin**:
```toml
dependencies = [
    # Core deps above
    "python-keycloak>=3.0.0",
    "authlib>=1.2.0",
    "httpx>=0.25.0",
]
```

---

## Summary of Decisions

| Topic | Decision | ADR Reference |
|-------|----------|---------------|
| K8s Secrets Backend | `kubernetes` client with auto-detect auth | ADR-0023 |
| Infisical Backend | `infisicalsdk` with Universal Auth | ADR-0031 |
| Identity Provider | `python-keycloak` + `authlib` | ADR-0024 |
| Token Caching | In-memory JWKS cache (1hr TTL) | ADR-0024 |
| Audit Logging | structlog + OTel trace context | ADR-0024 |
| Configuration | Pydantic v2 with SecretStr | Constitution IV |
| Testing | K8s-native integration tests | Constitution V |

---

## Open Questions (Resolved)

1. **Q**: Should we support HashiCorp Vault in this Epic?
   **A**: No - explicitly out of scope per spec. Future Epic or commercial plugin.

2. **Q**: How to handle secret rotation?
   **A**: Rely on Infisical Operator auto-reload annotation + Reloader for K8s Secrets.

3. **Q**: Multi-tenant identity isolation?
   **A**: Keycloak realms map to Data Mesh domains per ADR-0024.

# Data Model: Epic 7A - Identity & Secrets

**Date**: 2026-01-18
**Status**: Complete
**Branch**: `7a-identity-secrets`

## Overview

This document defines the data entities for the Identity & Secrets plugin system. All models use Pydantic v2 with frozen configuration for immutability.

---

## Core Entities

### SecretReference (Existing - floe-core)

**Purpose**: Manifest-level placeholder for secrets. Never contains actual values.

**Location**: `packages/floe-core/src/floe_core/schemas/secrets.py`

```python
class SecretSource(str, Enum):
    """Secret backend source for credential resolution."""
    ENV = "env"                    # Environment variable
    KUBERNETES = "kubernetes"      # K8s Secret (default)
    VAULT = "vault"                # HashiCorp Vault
    EXTERNAL_SECRETS = "external-secrets"  # Deprecated per ADR-0031
    INFISICAL = "infisical"        # NEW: Infisical backend

class SecretReference(BaseModel):
    """Pointer to a secret - never contains actual values."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: SecretSource = SecretSource.KUBERNETES
    name: str  # K8s Secret name or Infisical path
    key: str | None = None  # Key within multi-value secret

    def to_env_var_syntax(self) -> str:
        """Convert to dbt-compatible env_var() syntax."""
        env_name = self.name.upper().replace("-", "_")
        if self.key:
            env_name = f"{env_name}_{self.key.upper().replace('-', '_')}"
        return f"{{{{ env_var('FLOE_SECRET_{env_name}') }}}}"
```

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| source | SecretSource | No | KUBERNETES | Backend type |
| name | str | Yes | - | Secret identifier |
| key | str | No | None | Key within multi-value secret |

**Validation Rules**:
- `name`: 1-253 chars, lowercase alphanumeric with hyphens
- `key`: If provided, must be valid env var format

---

### UserInfo (Existing - floe-core)

**Purpose**: Authenticated user information from identity provider.

**Location**: `packages/floe-core/src/floe_core/plugins/identity.py`

```python
@dataclass
class UserInfo:
    """User information from identity provider."""
    subject: str          # Unique user ID (OIDC sub claim)
    email: str = ""       # User's email address
    name: str = ""        # Display name
    roles: list[str] = field(default_factory=list)   # Role assignments
    groups: list[str] = field(default_factory=list)  # Group memberships
    claims: dict[str, Any] = field(default_factory=dict)  # Additional claims
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| subject | str | Yes | Unique user identifier (OIDC sub) |
| email | str | No | User's email address |
| name | str | No | User's display name |
| roles | list[str] | No | Role assignments |
| groups | list[str] | No | Group memberships |
| claims | dict[str, Any] | No | Additional OIDC claims |

---

### TokenValidationResult (Existing - floe-core)

**Purpose**: Result of JWT token validation.

**Location**: `packages/floe-core/src/floe_core/plugins/identity.py`

```python
@dataclass
class TokenValidationResult:
    """Result of token validation."""
    valid: bool                     # Token is valid
    user_info: UserInfo | None = None  # User info if valid
    error: str = ""                 # Error message if invalid
    expires_at: str = ""            # Token expiration (ISO 8601)
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| valid | bool | Yes | Token validation status |
| user_info | UserInfo | No | User info (only if valid=True) |
| error | str | No | Error message (only if valid=False) |
| expires_at | str | No | Token expiration timestamp |

---

### OIDCConfig (New)

**Purpose**: OIDC provider endpoint configuration for service integration.

**Location**: `packages/floe-core/src/floe_core/plugins/identity.py` (to add)

```python
@dataclass
class OIDCConfig:
    """OIDC configuration for service integration."""
    issuer_url: str           # https://keycloak.example.com/realms/floe
    discovery_url: str        # /.well-known/openid-configuration
    jwks_uri: str             # /protocol/openid-connect/certs
    authorization_endpoint: str  # /protocol/openid-connect/auth
    token_endpoint: str       # /protocol/openid-connect/token
    userinfo_endpoint: str    # /protocol/openid-connect/userinfo
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| issuer_url | str | Yes | OIDC issuer URL |
| discovery_url | str | Yes | Well-known configuration endpoint |
| jwks_uri | str | Yes | JSON Web Key Set endpoint |
| authorization_endpoint | str | Yes | Authorization endpoint |
| token_endpoint | str | Yes | Token exchange endpoint |
| userinfo_endpoint | str | Yes | User info endpoint |

---

## Configuration Entities

### K8sSecretsConfig

**Purpose**: Configuration for Kubernetes Secrets plugin.

**Location**: `plugins/floe-secrets-k8s/src/floe_secrets_k8s/config.py`

```python
class K8sSecretsConfig(BaseModel):
    """Configuration for K8s Secrets plugin."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str = Field(
        default="default",
        description="K8s namespace for secrets",
        pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
    )
    kubeconfig_path: str | None = Field(
        default=None,
        description="Path to kubeconfig file (None = in-cluster)",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="API call timeout",
    )
```

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| namespace | str | No | "default" | K8s namespace |
| kubeconfig_path | str | No | None | Kubeconfig path |
| timeout_seconds | int | No | 30 | API timeout |

---

### InfisicalSecretsConfig

**Purpose**: Configuration for Infisical Secrets plugin.

**Location**: `plugins/floe-secrets-infisical/src/floe_secrets_infisical/config.py`

```python
class InfisicalSecretsConfig(BaseModel):
    """Configuration for Infisical Secrets plugin."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    site_url: str = Field(
        default="https://app.infisical.com",
        description="Infisical server URL",
    )
    client_id: str = Field(
        ...,
        description="Universal Auth client ID",
    )
    client_secret: SecretStr = Field(
        ...,
        description="Universal Auth client secret",
    )
    project_id: str = Field(
        ...,
        description="Infisical project ID",
    )
    environment: str = Field(
        default="production",
        description="Environment slug (development, staging, production)",
    )
    secrets_path: str = Field(
        default="/",
        description="Base path for secrets in project",
    )
```

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| site_url | str | No | app.infisical.com | Server URL |
| client_id | str | Yes | - | Universal Auth ID |
| client_secret | SecretStr | Yes | - | Universal Auth secret |
| project_id | str | Yes | - | Project ID |
| environment | str | No | "production" | Environment slug |
| secrets_path | str | No | "/" | Base path |

---

### KeycloakIdentityConfig

**Purpose**: Configuration for Keycloak Identity plugin.

**Location**: `plugins/floe-identity-keycloak/src/floe_identity_keycloak/config.py`

```python
class KeycloakIdentityConfig(BaseModel):
    """Configuration for Keycloak Identity plugin."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    server_url: str = Field(
        ...,
        description="Keycloak server URL (e.g., https://keycloak.example.com)",
    )
    realm: str = Field(
        default="floe",
        description="Realm name",
    )
    client_id: str = Field(
        ...,
        description="OIDC client ID",
    )
    client_secret: SecretStr = Field(
        ...,
        description="OIDC client secret",
    )
    admin_client_id: str | None = Field(
        default=None,
        description="Admin API client ID (for management operations)",
    )
    admin_client_secret: SecretStr | None = Field(
        default=None,
        description="Admin API client secret",
    )
    jwks_cache_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="JWKS cache TTL in seconds",
    )
```

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| server_url | str | Yes | - | Keycloak URL |
| realm | str | No | "floe" | Realm name |
| client_id | str | Yes | - | OIDC client ID |
| client_secret | SecretStr | Yes | - | OIDC client secret |
| admin_client_id | str | No | None | Admin client ID |
| admin_client_secret | SecretStr | No | None | Admin client secret |
| jwks_cache_ttl_seconds | int | No | 3600 | JWKS cache TTL |

---

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                      IDENTITY DOMAIN                            │
│                                                                 │
│  KeycloakIdentityConfig ──► KeycloakIdentityPlugin              │
│           │                        │                            │
│           │                        ▼                            │
│           │              ┌─────────────────────┐                │
│           │              │  IdentityPlugin     │ (ABC)          │
│           │              │  • authenticate()   │                │
│           │              │  • get_user_info()  │                │
│           │              │  • validate_token() │                │
│           │              └─────────┬───────────┘                │
│           │                        │                            │
│           │                        ▼                            │
│           │              ┌─────────────────────┐                │
│           └──────────────│    OIDCConfig       │                │
│                          └─────────────────────┘                │
│                                    │                            │
│                                    ▼                            │
│                          ┌─────────────────────┐                │
│                          │ TokenValidationResult│                │
│                          │     └──► UserInfo   │                │
│                          └─────────────────────┘                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      SECRETS DOMAIN                             │
│                                                                 │
│  K8sSecretsConfig ──────► K8sSecretsPlugin                      │
│  InfisicalSecretsConfig ──► InfisicalSecretsPlugin              │
│           │                        │                            │
│           │                        ▼                            │
│           │              ┌─────────────────────┐                │
│           │              │  SecretsPlugin      │ (ABC)          │
│           │              │  • get_secret()     │                │
│           │              │  • set_secret()     │                │
│           │              │  • list_secrets()   │                │
│           │              └─────────────────────┘                │
│           │                        ▲                            │
│           │                        │                            │
│           └────────────────────────┘                            │
│                                                                 │
│  SecretReference ──────► to_env_var_syntax()                    │
│  (manifest.yaml)         (profiles.yml generation)              │
└─────────────────────────────────────────────────────────────────┘
```

---

## State Transitions

### Token Lifecycle

```
┌───────────────┐
│   No Token    │
└───────┬───────┘
        │ authenticate()
        ▼
┌───────────────┐
│  Token Valid  │◄────────────┐
└───────┬───────┘             │
        │                     │ refresh_token()
        │ validate_token()    │
        ▼                     │
┌───────────────┐      ┌──────┴──────┐
│ Token Expired │──────► Token Refresh │
└───────┬───────┘      └─────────────┘
        │
        │ (refresh fails)
        ▼
┌───────────────┐
│Re-authenticate│
└───────────────┘
```

### Secret Resolution Flow

```
┌───────────────────┐
│  SecretReference  │
│  (manifest.yaml)  │
└─────────┬─────────┘
          │ floe compile
          ▼
┌───────────────────┐
│  env_var() syntax │
│  (profiles.yml)   │
└─────────┬─────────┘
          │ job pod starts
          ▼
┌───────────────────┐
│ SecretsPlugin     │
│ resolves at       │
│ runtime           │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Environment       │
│ Variables in Pod  │
└───────────────────┘
```

---

## Validation Rules Summary

| Entity | Field | Rule |
|--------|-------|------|
| SecretReference | name | 1-253 chars, lowercase alphanumeric + hyphens |
| SecretReference | key | Valid env var format if provided |
| K8sSecretsConfig | namespace | K8s namespace format |
| K8sSecretsConfig | timeout_seconds | 5-300 seconds |
| InfisicalSecretsConfig | environment | Non-empty string |
| KeycloakIdentityConfig | realm | Non-empty string |
| KeycloakIdentityConfig | jwks_cache_ttl_seconds | 60-86400 seconds |

---

## Security Considerations

1. **Secret Values**: Never stored in any model. Only references.
2. **SecretStr**: All credential fields use Pydantic SecretStr (masked in repr).
3. **Frozen Models**: All configs are frozen (immutable after creation).
4. **Extra Forbid**: Unknown fields rejected (prevent injection).

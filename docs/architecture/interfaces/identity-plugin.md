# IdentityPlugin

**Purpose**: User authentication via OIDC
**Location**: `floe_core/interfaces/identity.py`
**Entry Point**: `floe.identities`
**ADR**: [ADR-0024: Identity and Access Management](../adr/0024-identity-access-management.md)

IdentityPlugin abstracts identity providers (Keycloak, Dex, Okta, Auth0), enabling consistent OIDC-based authentication across all floe services.

## Interface Definition

```python
# floe_core/interfaces/identity.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class OIDCConfig:
    """OIDC configuration for service integration."""
    issuer_url: str              # https://keycloak.example.com/realms/floe
    discovery_url: str           # /.well-known/openid-configuration
    jwks_uri: str                # /protocol/openid-connect/certs
    authorization_endpoint: str  # /protocol/openid-connect/auth
    token_endpoint: str          # /protocol/openid-connect/token
    userinfo_endpoint: str       # /protocol/openid-connect/userinfo

@dataclass
class ClientCredentials:
    """OAuth2 client credentials for a service."""
    client_id: str
    client_secret_ref: str  # K8s Secret reference

@dataclass
class UserInfo:
    """Authenticated user information."""
    subject: str           # Unique user ID
    email: str | None
    name: str | None
    groups: list[str]      # Group memberships
    roles: list[str]       # Role assignments

class IdentityPlugin(ABC):
    """Interface for identity providers (Keycloak, Dex, Okta, etc.)."""

    name: str
    version: str
    is_self_hosted: bool  # True for Keycloak/Dex, False for Okta/Auth0

    @abstractmethod
    def get_oidc_config(self, realm: str | None = None) -> OIDCConfig:
        """Get OIDC configuration for service integration.

        Args:
            realm: Optional realm/tenant for multi-tenant deployments

        Returns:
            OIDCConfig with all OIDC endpoints
        """
        pass

    @abstractmethod
    def create_client(
        self,
        client_id: str,
        client_type: str,  # "confidential" | "public"
        redirect_uris: list[str],
        scopes: list[str],
    ) -> ClientCredentials:
        """Create an OIDC client for a service.

        Args:
            client_id: Unique client identifier
            client_type: confidential (server-side) or public (SPA)
            redirect_uris: Allowed redirect URIs after auth
            scopes: Requested OAuth2 scopes

        Returns:
            ClientCredentials with client_id and secret reference
        """
        pass

    @abstractmethod
    def get_client_credentials(self, client_id: str) -> ClientCredentials:
        """Get existing client credentials."""
        pass

    @abstractmethod
    def validate_token(self, token: str) -> UserInfo | None:
        """Validate a JWT access token.

        Args:
            token: JWT access token

        Returns:
            UserInfo if valid, None if invalid/expired
        """
        pass

    @abstractmethod
    def get_groups(self) -> list[str]:
        """List all groups in the identity provider."""
        pass

    @abstractmethod
    def get_group_members(self, group: str) -> list[UserInfo]:
        """Get members of a group."""
        pass

    @abstractmethod
    def generate_helm_values(self) -> dict:
        """Generate Helm values for deploying this IdP.

        Returns:
            Dict suitable for Helm chart values.yaml
        """
        pass
```

## Reference Implementations

| Plugin | Description | Self-Hosted |
|--------|-------------|-------------|
| `KeycloakIdentityPlugin` | Full-featured IdP with admin UI | Yes |
| `DexIdentityPlugin` | Lightweight OIDC connector | Yes |
| `OktaIdentityPlugin` | Enterprise SaaS IdP | No |
| `Auth0IdentityPlugin` | Developer-friendly SaaS IdP | No |

## Related Documents

- [ADR-0024: Identity and Access Management](../adr/0024-identity-access-management.md)
- [Plugin Architecture](../plugin-system/index.md)
- [SecretsPlugin](secrets-plugin.md) - For client secret storage

# ADR-0024: Identity and Access Management

## Status

Accepted

## Context

ADR-0022 (Security & RBAC Model) established security patterns for service-to-service authentication within floe. However, it identified a gap: **human user authentication** for accessing platform UIs and APIs.

Users need to authenticate to:

1. **Dagster UI** - View pipelines, trigger runs, monitor jobs
2. **Cube API** - Query semantic layer from BI tools
3. **Grafana** - View observability dashboards
4. **Polaris API** - Manage catalog (admin users)
5. **MinIO Console** - Manage object storage (admin users)

Without a standardized identity solution:

- Each service requires separate user management
- No Single Sign-On (SSO) across platform services
- Enterprise identity federation (LDAP, AD, SAML) unsupported
- Compliance requirements (SOC2, ISO 27001) harder to meet
- Human access and machine access use inconsistent patterns

**Key Requirements:**

- **SSO**: Single authentication for all floe UIs
- **Federation**: Connect to enterprise IdPs (LDAP, AD, SAML, OIDC)
- **Standards-based**: OpenID Connect (OIDC) as the protocol
- **Self-hosted default**: No mandatory cloud dependencies
- **Pluggable**: Support commercial IdPs (Okta, Auth0, Azure AD)
- **Multi-tenant**: Support Data Mesh domain isolation

## Decision

Implement identity management as a **pluggable component** with **Keycloak as the default**.

### Plugin Model

Create an `IdentityPlugin` interface that abstracts identity provider operations:

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

### Default: Keycloak

Keycloak is the default identity provider because:

| Criterion | Keycloak |
|-----------|----------|
| **License** | Apache 2.0 |
| **Maturity** | 12+ years, battle-tested |
| **Enterprise Support** | Red Hat (optional) |
| **Protocol Support** | OIDC, SAML, LDAP, Kerberos |
| **Federation** | Extensive (AD, LDAP, social, SAML) |
| **Helm Charts** | Bitnami (official), Codecentric |
| **Multi-tenancy** | Realms provide isolation |
| **Admin UI** | Full-featured web console |
| **Community** | 23k+ GitHub stars, active development |

### Alternatives

| Provider | Type | Use Case | Helm Chart |
|----------|------|----------|------------|
| **Keycloak** | OSS (default) | Full-featured, enterprise-ready | Bitnami |
| **Dex** | OSS | Lightweight, federation-only | dex/dex |
| **Authentik** | OSS | Modern UI, Python-based | goauthentik/authentik |
| **Zitadel** | OSS | Cloud-native, Go-based | zitadel/zitadel |
| **Okta** | Commercial | Enterprise, managed | N/A (external) |
| **Auth0** | Commercial | Developer-friendly, managed | N/A (external) |
| **Azure AD** | Commercial | Microsoft ecosystem | N/A (external) |
| **AWS Cognito** | Commercial | AWS ecosystem | N/A (external) |
| **Google Identity** | Commercial | GCP ecosystem | N/A (external) |

## Consequences

### Positive

- **SSO out of box**: Single login for all floe services
- **Enterprise ready**: Federation with AD/LDAP/SAML
- **Standards-based**: OIDC works with any compliant IdP
- **Self-hosted default**: No mandatory cloud dependencies
- **Pluggable**: Easy switch to commercial IdPs
- **Multi-tenant**: Keycloak realms map to Data Mesh domains

### Negative

- **Additional component**: Keycloak requires deployment and maintenance
- **Resource overhead**: Keycloak needs PostgreSQL and ~1GB RAM
- **Complexity**: OIDC configuration requires understanding
- **Learning curve**: Keycloak admin UI has many options

### Neutral

- Commercial IdPs (Okta, Auth0) remain viable alternatives
- Dex provides a lightweight option for simple federation
- Managed Keycloak available from Red Hat if self-hosting burdensome

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  IDENTITY ARCHITECTURE                                                       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  IDENTITY PROVIDER (IdentityPlugin)                                      ││
│  │  Default: Keycloak | Alt: Dex, Authentik, Zitadel, Okta, Auth0...       ││
│  │                                                                          ││
│  │  ┌────────────────────────────────────────────────────────────────────┐ ││
│  │  │  Endpoints                                                          │ ││
│  │  │                                                                     │ ││
│  │  │  /.well-known/openid-configuration  → OIDC Discovery               │ ││
│  │  │  /protocol/openid-connect/auth      → Authorization                │ ││
│  │  │  /protocol/openid-connect/token     → Token Exchange               │ ││
│  │  │  /protocol/openid-connect/certs     → JWKS (public keys)           │ ││
│  │  │  /protocol/openid-connect/userinfo  → User Info                    │ ││
│  │  └────────────────────────────────────────────────────────────────────┘ ││
│  │                                                                          ││
│  │  ┌────────────────────────────────────────────────────────────────────┐ ││
│  │  │  Federation (optional)                                              │ ││
│  │  │                                                                     │ ││
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │ ││
│  │  │  │ LDAP/AD  │  │  GitHub  │  │  Google  │  │  SAML    │           │ ││
│  │  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │ ││
│  │  └────────────────────────────────────────────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                      │                                       │
│                                      │ OIDC/JWT                              │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  SERVICE INTEGRATION                                                     ││
│  │                                                                          ││
│  │  ┌──────────────────────────────┐  ┌──────────────────────────────────┐ ││
│  │  │  DIRECT OIDC                  │  │  PROXY-BASED (oauth2-proxy)      │ ││
│  │  │  (Services with native OIDC)  │  │  (Services without OIDC)         │ ││
│  │  │                               │  │                                  │ ││
│  │  │  • Polaris (v1.1.0+)         │  │  • Dagster UI                    │ ││
│  │  │  • Cube (JWT/JWKS)           │  │  • Custom apps                   │ ││
│  │  │  • Grafana                    │  │                                  │ ││
│  │  │  • MinIO                      │  │  Ingress annotations:            │ ││
│  │  │                               │  │  auth-url, auth-signin           │ ││
│  │  └──────────────────────────────┘  └──────────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  USER AUTHENTICATION FLOW                                                    │
│                                                                              │
│  1. User accesses protected service                                         │
│     │                                                                        │
│     ▼                                                                        │
│  2. Service/Proxy checks for valid session                                  │
│     │                                                                        │
│     ├─► Session valid? → Allow access                                       │
│     │                                                                        │
│     └─► No session? → Redirect to IdP                                       │
│           │                                                                  │
│           ▼                                                                  │
│  3. User authenticates at IdP (Keycloak)                                    │
│     │                                                                        │
│     ├─► Local credentials                                                   │
│     ├─► Federated login (LDAP, AD, GitHub, etc.)                           │
│     └─► MFA (if configured)                                                 │
│           │                                                                  │
│           ▼                                                                  │
│  4. IdP issues tokens                                                       │
│     │                                                                        │
│     ├─► ID Token (user identity, for client)                               │
│     ├─► Access Token (authorization, for APIs)                             │
│     └─► Refresh Token (session renewal)                                    │
│           │                                                                  │
│           ▼                                                                  │
│  5. Redirect back to service with tokens                                    │
│     │                                                                        │
│     ▼                                                                        │
│  6. Service validates token (via JWKS)                                      │
│     │                                                                        │
│     ▼                                                                        │
│  7. Extract user info and roles → Apply authorization                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Service Integration

### Polaris (Native OIDC)

Polaris 1.1.0+ supports external OIDC authentication natively:

```yaml
# Polaris configuration (via Helm values)
polaris:
  auth:
    type: external  # or "mixed" for internal + external
  quarkus:
    oidc:
      tenant-enabled: true
      auth-server-url: https://keycloak.floe-platform.svc.cluster.local/realms/floe
      client-id: polaris
      application-type: service
```

**Role Mapping:**
```yaml
# Map Keycloak roles to Polaris principal roles
polaris:
  security:
    principal-role-mapping:
      filter: "realm_access.roles"
      mappings:
        catalog-admin: "PRINCIPAL_ROLE:catalog_admin"
        data-engineer: "PRINCIPAL_ROLE:data_engineer"
```

### Cube (JWT/JWKS)

Cube validates JWTs using the IdP's JWKS endpoint:

```javascript
// cube.js configuration
module.exports = {
  jwt: {
    // Keycloak JWKS endpoint
    jwkUrl: "https://keycloak.floe-platform.svc.cluster.local/realms/floe/protocol/openid-connect/certs",

    // Verify issuer and audience
    issuer: ["https://keycloak.floe-platform.svc.cluster.local/realms/floe"],
    audience: "cube",

    // Extract claims for security context
    claimsNamespace: "https://floe.dev/",
  },
};
```

**Security Context Extraction:**
```javascript
// Extract namespace and roles from JWT
module.exports = {
  contextToAppId: ({ securityContext }) => {
    return securityContext.namespace || 'default';
  },

  extendContext: (req) => {
    return {
      namespace: req.securityContext?.['https://floe.dev/namespace'],
      roles: req.securityContext?.realm_access?.roles || [],
    };
  },
};
```

### Grafana (Native OIDC)

```yaml
# Grafana Helm values
grafana:
  grafana.ini:
    auth.generic_oauth:
      enabled: true
      name: Keycloak
      allow_sign_up: true
      client_id: grafana
      client_secret: ${GRAFANA_OAUTH_CLIENT_SECRET}
      scopes: openid profile email groups
      auth_url: https://keycloak.floe-platform.svc.cluster.local/realms/floe/protocol/openid-connect/auth
      token_url: https://keycloak.floe-platform.svc.cluster.local/realms/floe/protocol/openid-connect/token
      api_url: https://keycloak.floe-platform.svc.cluster.local/realms/floe/protocol/openid-connect/userinfo
      role_attribute_path: contains(realm_access.roles[*], 'admin') && 'Admin' || 'Viewer'
```

### Dagster (oauth2-proxy)

Dagster OSS doesn't have native OIDC. Use oauth2-proxy at ingress level:

```yaml
# oauth2-proxy Helm values
oauth2-proxy:
  config:
    clientID: dagster
    clientSecret: ${DAGSTER_OAUTH_CLIENT_SECRET}
    cookieSecret: ${OAUTH2_PROXY_COOKIE_SECRET}

  extraArgs:
    provider: oidc
    oidc-issuer-url: https://keycloak.floe-platform.svc.cluster.local/realms/floe
    email-domain: "*"
    pass-access-token: true
    set-xauthrequest: true

  ingress:
    enabled: true
    hosts:
      - oauth.floe-platform.svc.cluster.local
```

```yaml
# Dagster Ingress with oauth2-proxy
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: dagster-webserver
  annotations:
    nginx.ingress.kubernetes.io/auth-url: "http://oauth2-proxy.floe-platform.svc.cluster.local/oauth2/auth"
    nginx.ingress.kubernetes.io/auth-signin: "https://dagster.example.com/oauth2/start?rd=$escaped_request_uri"
    nginx.ingress.kubernetes.io/auth-response-headers: "X-Auth-Request-User,X-Auth-Request-Email,X-Auth-Request-Groups"
spec:
  rules:
    - host: dagster.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: dagster-webserver
                port:
                  number: 3000
```

### MinIO (Native OIDC)

```yaml
# MinIO Helm values
minio:
  oidc:
    enabled: true
    configUrl: https://keycloak.floe-platform.svc.cluster.local/realms/floe/.well-known/openid-configuration
    clientId: minio
    clientSecret: ${MINIO_OAUTH_CLIENT_SECRET}
    claimName: policy
    scopes: openid,profile,email
```

---

## Multi-Tenancy (Data Mesh)

For Data Mesh deployments, Keycloak realms map to domains:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  KEYCLOAK MULTI-REALM ARCHITECTURE                                          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  Master Realm (Platform Admin)                                           ││
│  │  • Platform administrators                                               ││
│  │  • Cross-realm management                                                ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  sales realm    │  │  marketing realm│  │  finance realm  │             │
│  │                 │  │                 │  │                 │             │
│  │  Users:         │  │  Users:         │  │  Users:         │             │
│  │  • sales-admin  │  │  • mkt-admin    │  │  • fin-admin    │             │
│  │  • sales-eng-1  │  │  • mkt-analyst  │  │  • fin-analyst  │             │
│  │                 │  │                 │  │                 │             │
│  │  Clients:       │  │  Clients:       │  │  Clients:       │             │
│  │  • polaris      │  │  • polaris      │  │  • polaris      │             │
│  │  • cube         │  │  • cube         │  │  • cube         │             │
│  │  • dagster      │  │  • dagster      │  │  • dagster      │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│           │                   │                   │                         │
│           ▼                   ▼                   ▼                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ floe-sales-     │  │ floe-marketing- │  │ floe-finance-   │             │
│  │ domain ns       │  │ domain ns       │  │ domain ns       │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Realm-to-Namespace Mapping:**
```yaml
# platform-manifest.yaml (Data Mesh mode)
identity:
  type: keycloak
  config:
    multi_realm: true
    realm_mapping:
      sales: floe-sales-domain
      marketing: floe-marketing-domain
      finance: floe-finance-domain
```

---

## Plugin Implementations

### Keycloak Plugin (Default)

```python
# plugins/floe-identity-keycloak/plugin.py
from keycloak import KeycloakAdmin, KeycloakOpenID

class KeycloakPlugin(IdentityPlugin):
    """Keycloak identity provider plugin."""

    name = "keycloak"
    version = "1.0.0"
    is_self_hosted = True

    def __init__(self, config: dict):
        self.server_url = config["server_url"]
        self.realm = config.get("realm", "floe")
        self.admin = KeycloakAdmin(
            server_url=self.server_url,
            realm_name=self.realm,
            client_id=config["admin_client_id"],
            client_secret_key=config["admin_client_secret"],
        )

    def get_oidc_config(self, realm: str | None = None) -> OIDCConfig:
        r = realm or self.realm
        base = f"{self.server_url}/realms/{r}"
        return OIDCConfig(
            issuer_url=base,
            discovery_url=f"{base}/.well-known/openid-configuration",
            jwks_uri=f"{base}/protocol/openid-connect/certs",
            authorization_endpoint=f"{base}/protocol/openid-connect/auth",
            token_endpoint=f"{base}/protocol/openid-connect/token",
            userinfo_endpoint=f"{base}/protocol/openid-connect/userinfo",
        )

    def create_client(
        self,
        client_id: str,
        client_type: str,
        redirect_uris: list[str],
        scopes: list[str],
    ) -> ClientCredentials:
        self.admin.create_client({
            "clientId": client_id,
            "publicClient": client_type == "public",
            "redirectUris": redirect_uris,
            "defaultClientScopes": scopes,
        })
        secret = self.admin.get_client_secrets(client_id)
        # Store in K8s Secret
        secret_name = f"{client_id}-credentials"
        self._create_k8s_secret(secret_name, {"client_secret": secret})
        return ClientCredentials(
            client_id=client_id,
            client_secret_ref=secret_name,
        )

    def generate_helm_values(self) -> dict:
        return {
            "image": {
                "repository": "quay.io/keycloak/keycloak",
                "tag": "24.0",
            },
            "postgresql": {
                "enabled": True,
            },
            "replicas": 2,
            "resources": {
                "requests": {"cpu": "500m", "memory": "1Gi"},
                "limits": {"cpu": "2", "memory": "2Gi"},
            },
        }
```

### Dex Plugin (Lightweight Federation)

```python
# plugins/floe-identity-dex/plugin.py
class DexPlugin(IdentityPlugin):
    """Dex identity provider plugin (CNCF project)."""

    name = "dex"
    version = "1.0.0"
    is_self_hosted = True

    def get_oidc_config(self, realm: str | None = None) -> OIDCConfig:
        # Dex doesn't have realms, uses single issuer
        base = self.issuer_url
        return OIDCConfig(
            issuer_url=base,
            discovery_url=f"{base}/.well-known/openid-configuration",
            jwks_uri=f"{base}/keys",
            authorization_endpoint=f"{base}/auth",
            token_endpoint=f"{base}/token",
            userinfo_endpoint=f"{base}/userinfo",
        )

    def generate_helm_values(self) -> dict:
        return {
            "image": {
                "repository": "ghcr.io/dexidp/dex",
                "tag": "v2.39.0",
            },
            "config": {
                "issuer": self.issuer_url,
                "storage": {"type": "kubernetes", "config": {"inCluster": True}},
                "connectors": self._generate_connectors(),
            },
        }

    def _generate_connectors(self) -> list:
        """Generate Dex connectors for upstream IdPs."""
        connectors = []
        if self.config.get("ldap"):
            connectors.append({
                "type": "ldap",
                "id": "ldap",
                "name": "LDAP",
                "config": self.config["ldap"],
            })
        if self.config.get("github"):
            connectors.append({
                "type": "github",
                "id": "github",
                "name": "GitHub",
                "config": self.config["github"],
            })
        return connectors
```

### External IdP Plugin (Okta, Auth0, Azure AD)

```python
# plugins/floe-identity-external/plugin.py
class ExternalIdPPlugin(IdentityPlugin):
    """Plugin for external/commercial identity providers."""

    name = "external"
    version = "1.0.0"
    is_self_hosted = False

    def __init__(self, config: dict):
        self.provider = config["provider"]  # okta, auth0, azure-ad, cognito
        self.issuer_url = config["issuer_url"]
        self.discovery_url = config.get(
            "discovery_url",
            f"{self.issuer_url}/.well-known/openid-configuration"
        )
        # Fetch OIDC config from discovery endpoint
        self._oidc_config = self._fetch_discovery()

    def _fetch_discovery(self) -> dict:
        """Fetch OIDC configuration from discovery endpoint."""
        import requests
        response = requests.get(self.discovery_url)
        return response.json()

    def get_oidc_config(self, realm: str | None = None) -> OIDCConfig:
        c = self._oidc_config
        return OIDCConfig(
            issuer_url=c["issuer"],
            discovery_url=self.discovery_url,
            jwks_uri=c["jwks_uri"],
            authorization_endpoint=c["authorization_endpoint"],
            token_endpoint=c["token_endpoint"],
            userinfo_endpoint=c["userinfo_endpoint"],
        )

    def generate_helm_values(self) -> dict:
        # External IdPs don't need Helm deployment
        return {}

    def create_client(self, *args, **kwargs) -> ClientCredentials:
        raise NotImplementedError(
            f"Create clients directly in {self.provider} admin console"
        )
```

---

## Configuration Schema

```yaml
# platform-manifest.yaml
plugins:
  identity:
    type: keycloak | dex | authentik | zitadel | external

    # Keycloak (default)
    config:
      # Helm chart source
      chart:
        repository: oci://registry-1.docker.io/bitnamicharts
        name: keycloak
        version: "21.0.0"

      # Keycloak configuration
      realm: floe
      admin_user_ref: keycloak-admin    # K8s Secret
      admin_password_ref: keycloak-admin

      # High availability
      replicas: 2

      # Database (bundled or external)
      database:
        type: bundled | external
        external_secret_ref: keycloak-db  # If external

      # Federation (optional)
      federation:
        ldap:
          enabled: false
          server_url: ldap://ldap.example.com
          bind_dn_ref: ldap-credentials
        github:
          enabled: false
          client_id_ref: github-oauth
        saml:
          enabled: false
          metadata_url: https://idp.example.com/metadata

    # Dex (lightweight)
    config:
      issuer_url: https://dex.floe-platform.svc.cluster.local
      connectors:
        - type: ldap
          config_ref: dex-ldap-config
        - type: github
          config_ref: dex-github-config

    # External (Okta, Auth0, Azure AD)
    config:
      provider: okta | auth0 | azure-ad | cognito | google
      issuer_url: https://your-tenant.okta.com
      # Clients created manually in provider console
      clients:
        polaris:
          client_id: polaris-client-id
          client_secret_ref: okta-polaris-secret
        cube:
          client_id: cube-client-id
          client_secret_ref: okta-cube-secret

# Service integration
services:
  orchestrator:
    auth:
      enabled: true
      type: oauth2-proxy  # Dagster requires proxy
      allowed_groups: ["platform-admins", "data-engineers"]

  catalog:
    auth:
      enabled: true
      type: native  # Polaris has native OIDC
      allowed_groups: ["catalog-admins", "data-engineers"]

  semantic:
    auth:
      enabled: true
      type: jwt  # Cube uses JWT validation
      allowed_groups: ["bi-users", "data-analysts"]

  observability:
    auth:
      enabled: true
      type: native  # Grafana has native OIDC
      allowed_groups: ["platform-admins", "observers"]
```

---

## Deployment

### Deploy with Keycloak (Default)

```bash
# Deploy platform with identity
floe platform deploy

# Output:
Deploying platform services to namespace: floe-platform
  ✓ PostgreSQL (keycloak-db): StatefulSet 1/1 ready
  ✓ Keycloak: StatefulSet 2/2 ready
  ✓ Creating realm: floe
  ✓ Creating clients: polaris, cube, grafana, dagster
  ✓ oauth2-proxy: Deployment 2/2 ready
  ...

Identity provider deployed:
  Admin Console: https://keycloak.example.com/admin
  Realm: floe
  Clients: polaris, cube, grafana, dagster, minio
```

### Configure Federation

```bash
# Add LDAP federation
floe identity add-connector ldap \
  --server-url ldap://ldap.example.com \
  --bind-dn "cn=admin,dc=example,dc=com" \
  --bind-password-ref ldap-admin-password \
  --user-search-base "ou=users,dc=example,dc=com"

# Add GitHub federation
floe identity add-connector github \
  --client-id-ref github-oauth \
  --client-secret-ref github-oauth \
  --orgs "my-org"
```

### Create Service Clients

```bash
# Create client for custom application
floe identity create-client my-app \
  --redirect-uris "https://my-app.example.com/callback" \
  --scopes "openid,profile,email"

# Output:
Client created: my-app
  Client ID: my-app
  Client Secret: stored in K8s Secret 'my-app-credentials'
  OIDC Config: https://keycloak.example.com/realms/floe/.well-known/openid-configuration
```

---

## Security Considerations

### Token Lifetimes

```yaml
# Recommended token lifetimes
identity:
  config:
    token_lifetimes:
      access_token: 5m       # Short-lived for security
      refresh_token: 30m     # Session renewal
      id_token: 5m           # Same as access token
      offline_token: 30d     # Long-lived for CI/CD
```

### Network Security

```yaml
# Network policy for Keycloak
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: keycloak-network-policy
  namespace: floe-platform
spec:
  podSelector:
    matchLabels:
      app: keycloak
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - port: 8080
    # Allow from platform services
    - from:
        - podSelector: {}
      ports:
        - port: 8080
  egress:
    # Allow to PostgreSQL
    - to:
        - podSelector:
            matchLabels:
              app: postgresql
      ports:
        - port: 5432
    # Allow to external IdPs for federation
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - port: 443
```

### Audit Logging

```yaml
# Keycloak event logging
keycloak:
  extraEnv:
    - name: KC_LOG_LEVEL
      value: "INFO"
    - name: KC_SPI_EVENTS_LISTENER_JBOSS_LOGGING_SUCCESS_LEVEL
      value: "INFO"
    - name: KC_SPI_EVENTS_LISTENER_JBOSS_LOGGING_ERROR_LEVEL
      value: "WARN"

  # Event types to log
  eventsEnabled: true
  eventsExpiration: 604800  # 7 days
  adminEventsEnabled: true
  adminEventsDetailsEnabled: true
```

---

## References

### Documentation

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Dex Documentation](https://dexidp.io/docs/)
- [Authentik Documentation](https://goauthentik.io/docs/)
- [Zitadel Documentation](https://zitadel.com/docs)
- [oauth2-proxy Documentation](https://oauth2-proxy.github.io/oauth2-proxy/)

### Helm Charts

- [Bitnami Keycloak](https://github.com/bitnami/charts/tree/main/bitnami/keycloak)
- [Codecentric Keycloak](https://github.com/codecentric/helm-charts/tree/master/charts/keycloak)
- [Dex Helm Chart](https://github.com/dexidp/helm-charts)
- [oauth2-proxy Helm Chart](https://github.com/oauth2-proxy/manifests)

### Polaris OIDC

- [Polaris External IdP](https://polaris.apache.org/releases/1.2.0/managing-security/external-idp/)
- [Polaris Keycloak Guide](https://polaris.apache.org/in-dev/unreleased/getting-started/using-polaris/keycloak-idp/)

### Related ADRs

- [ADR-0022: Security & RBAC Model](0022-security-rbac-model.md) - Service-to-service auth
- [ADR-0023: Secrets Management](0023-secrets-management.md) - Credential storage
- [ADR-0018: Opinionation Boundaries](0018-opinionation-boundaries.md) - Plugin model

# ADR-0031: Infisical as Default Secrets Management

## Status

Accepted (Supersedes ADR-0023)

## Context

ADR-0023 established External Secrets Operator (ESO) as the recommended secrets management solution for cloud integration. However, as of August 2025, ESO development has been paused due to maintainer burnout, creating significant risk:

- No new features or patches
- No security updates
- Pre-v1.0 instability (breaking changes in minor versions)
- Uncertain future maintenance

floe requires a secrets management solution that:

1. **Is actively maintained** - Regular releases and security patches
2. **Is truly open source** - MIT or Apache 2.0 license, not just "source available"
3. **Has native Kubernetes integration** - Operator pattern with CRDs
4. **Supports auto-reload** - Pods restart when secrets change
5. **Provides Python SDK** - For programmatic access in plugins
6. **Has commercial upgrade path** - Enterprise features available when needed

### Alternatives Evaluated

| Solution | License | K8s Native | Active Dev | OSS Features |
|----------|---------|------------|------------|--------------|
| **Infisical** | MIT | Yes (Operator) | Yes (Dec 2025: v0.154.6) | Full secrets management |
| External Secrets Operator | Apache 2.0 | Yes | **PAUSED** | Bridge to external stores |
| HashiCorp Vault | BSL 1.1 | Yes (Operator) | Yes | **Enterprise features paywalled** |
| Doppler | Proprietary | Yes | Yes | Limited OSS |
| Native K8s Secrets | Apache 2.0 | Yes | Yes | No external sync |

## Decision

Adopt **Infisical** as the default open-source secrets management solution for floe:

1. **Default Plugin**: `floe-secrets-infisical` replaces `floe-secrets-eso`
2. **K8s Secrets Fallback**: Native K8s Secrets remain supported for simple deployments
3. **Commercial Extensions**: Vault and Infisical Enterprise plugins added later

### Why Infisical

- **Active Development**: 447 releases, 24k+ GitHub stars, SOC 2 Type II certified
- **True Open Source**: MIT license for core functionality
- **Native K8s Operator**: InfisicalSecret CRD with auto-reload
- **Python SDK**: Official `infisicalsdk` package
- **Production Ready**: Used by Fortune 500 companies and governments
- **Cloud Sync**: Supports AWS SM, GCP SM, Azure KV via bidirectional sync

## Consequences

### Positive

- **Active maintenance**: Regular releases and security updates
- **Unified solution**: Single tool for secrets management (not just a bridge)
- **Auto-reload**: Native pod restart on secret changes
- **Python SDK**: Clean integration in floe plugins
- **Open source**: MIT license allows customization
- **ESO compatible**: Infisical works as ESO provider for migration

### Negative

- **Younger project**: 3 years vs Vault's 11+ years
- **Self-hosting complexity**: Requires PostgreSQL and Redis
- **Enterprise features paywalled**: SSO, advanced RBAC, audit logging require paid tier
- **Fewer integrations**: Smaller ecosystem than Vault

### Neutral

- K8s Secrets still supported as fallback
- Vault plugin available for enterprises requiring dynamic secrets
- Infisical can be used with ESO as migration path

---

## Implementation

### SecretsPlugin Interface (Unchanged)

```python
# floe_core/interfaces/secrets.py
from abc import ABC, abstractmethod

class SecretsPlugin(ABC):
    """Interface for secrets management."""

    name: str
    version: str

    @abstractmethod
    def get_secret(self, name: str, namespace: str) -> dict[str, str]:
        """Retrieve a secret by name."""
        pass

    @abstractmethod
    def create_secret(
        self,
        name: str,
        namespace: str,
        data: dict[str, str]
    ) -> None:
        """Create a secret."""
        pass

    @abstractmethod
    def inject_env_vars(self, secret_refs: dict[str, str]) -> dict[str, str]:
        """Generate environment variable mappings for K8s pods."""
        pass

    @abstractmethod
    def generate_secret_mounts(self, secret_name: str) -> dict:
        """Generate K8s pod spec for mounting secrets as env vars."""
        pass
```

### Infisical Plugin Implementation

```python
# plugins/floe-secrets-infisical/plugin.py
from infisicalsdk import InfisicalClient

class InfisicalSecretsPlugin(SecretsPlugin):
    """Secrets plugin using Infisical."""

    name = "infisical"
    version = "1.0.0"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        site_url: str = "https://app.infisical.com",
        project_id: str = None,
    ):
        self.client = InfisicalClient(
            client_id=client_id,
            client_secret=client_secret,
            site_url=site_url,
        )
        self.project_id = project_id

    def get_secret(self, name: str, namespace: str) -> dict[str, str]:
        """Retrieve secrets from Infisical."""
        secrets = self.client.list_secrets(
            project_id=self.project_id,
            environment=namespace,
            path="/",
        )
        return {s.secret_name: s.secret_value for s in secrets if s.secret_name == name}

    def get_all_secrets(self, environment: str, path: str = "/") -> dict[str, str]:
        """Retrieve all secrets for an environment."""
        secrets = self.client.list_secrets(
            project_id=self.project_id,
            environment=environment,
            path=path,
        )
        return {s.secret_name: s.secret_value for s in secrets}

    def inject_env_vars(self, secret_refs: dict[str, str]) -> dict[str, str]:
        """Generate env var config referencing K8s Secret (synced by Operator)."""
        return {
            "envFrom": [{"secretRef": {"name": ref}} for ref in secret_refs.values()]
        }

    def generate_secret_mounts(self, secret_name: str) -> dict:
        """Generate K8s pod spec fragment."""
        return {
            "envFrom": [
                {"secretRef": {"name": secret_name}}
            ]
        }
```

### Kubernetes Operator Deployment

```bash
# Install Infisical Secrets Operator
helm repo add infisical-helm-charts 'https://dl.cloudsmith.io/public/infisical/helm-charts/helm/charts/'
helm repo update
helm install infisical-secrets-operator infisical-helm-charts/secrets-operator \
  --namespace infisical --create-namespace
```

### InfisicalSecret CRD

```yaml
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: snowflake-credentials
  namespace: floe-jobs
  annotations:
    secrets.infisical.com/auto-reload: "true"  # Pod restart on change
spec:
  hostAPI: https://app.infisical.com/api
  resyncInterval: 60  # seconds
  authentication:
    universalAuth:
      credentialsRef:
        secretName: infisical-machine-identity
        secretNamespace: infisical
  managedSecretReference:
    secretName: snowflake-credentials
    secretNamespace: floe-jobs
    secretType: Opaque
    creationPolicy: Owner
  secretsScope:
    projectSlug: floe-platform
    envSlug: production
    secretsPath: /compute/snowflake
```

### Platform Manifest Configuration

```yaml
# platform-manifest.yaml
plugins:
  secrets:
    type: infisical  # Default OSS
    config:
      site_url: https://infisical.company.com  # Self-hosted or cloud
      project_slug: floe-platform

  # Alternative: K8s Secrets (no external dependencies)
  # secrets:
  #   type: k8s

  # Future: Vault (commercial plugin)
  # secrets:
  #   type: vault
  #   config:
  #     address: https://vault.company.com
  #     auth_method: kubernetes

  compute:
    type: snowflake
    connection_secret_ref: snowflake-credentials
```

---

## Secrets Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  INFISICAL SECRETS FLOW                                                      │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. SECRET SOURCE (Infisical)                                        │    │
│  │                                                                      │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │ Infisical Project: floe-platform                              │   │    │
│  │  │                                                               │   │    │
│  │  │ Environments:                                                 │   │    │
│  │  │   - development                                               │   │    │
│  │  │   - staging                                                   │   │    │
│  │  │   - production                                                │   │    │
│  │  │                                                               │   │    │
│  │  │ Secrets:                                                      │   │    │
│  │  │   /compute/snowflake/                                         │   │    │
│  │  │     - SNOWFLAKE_ACCOUNT                                       │   │    │
│  │  │     - SNOWFLAKE_USER                                          │   │    │
│  │  │     - SNOWFLAKE_PASSWORD                                      │   │    │
│  │  │   /catalog/polaris/                                           │   │    │
│  │  │     - POLARIS_CLIENT_ID                                       │   │    │
│  │  │     - POLARIS_CLIENT_SECRET                                   │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  │                          │                                          │    │
│  └──────────────────────────┼──────────────────────────────────────────┘    │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  2. INFISICAL OPERATOR                                              │    │
│  │                                                                      │    │
│  │  InfisicalSecret CR                     K8s Secret                  │    │
│  │  ┌───────────────────────┐             ┌───────────────────────┐   │    │
│  │  │ kind: InfisicalSecret │ ──syncs──►  │ kind: Secret          │   │    │
│  │  │ spec:                 │             │ data:                 │   │    │
│  │  │   secretsScope:       │             │   SNOWFLAKE_ACCOUNT   │   │    │
│  │  │     projectSlug: floe │             │   SNOWFLAKE_USER      │   │    │
│  │  │     envSlug: prod     │             │   SNOWFLAKE_PASSWORD  │   │    │
│  │  └───────────────────────┘             └───────────────────────┘   │    │
│  │                                                                      │    │
│  │  Features:                                                          │    │
│  │    ✓ Auto-reload pods on secret change                              │    │
│  │    ✓ Configurable sync interval                                     │    │
│  │    ✓ Secret ownership (deletion cleanup)                            │    │
│  │                                                                      │    │
│  └──────────────────────────┬──────────────────────────────────────────┘    │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  3. JOB POD                                                          │    │
│  │                                                                      │    │
│  │  spec:                                                              │    │
│  │    containers:                                                       │    │
│  │      - name: dbt                                                    │    │
│  │        envFrom:                                                      │    │
│  │          - secretRef:                                               │    │
│  │              name: snowflake-credentials                            │    │
│  │                                                                      │    │
│  │  Environment:                                                       │    │
│  │    SNOWFLAKE_ACCOUNT=xxx.us-east-1                                 │    │
│  │    SNOWFLAKE_USER=dbt_user                                         │    │
│  │    SNOWFLAKE_PASSWORD=***                                          │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Plugin Architecture

```
floe/plugins/
├── floe-secrets-k8s/           # Default (no external dependencies)
│   └── plugin.py               # K8s Secrets only
├── floe-secrets-infisical/     # Default OSS (MIT)
│   └── plugin.py               # Infisical Operator integration
├── floe-secrets-vault/         # Commercial plugin (future)
│   └── plugin.py               # HashiCorp Vault integration
└── floe-secrets-infisical-ee/  # Commercial plugin (future)
    └── plugin.py               # Infisical Enterprise features
```

### Plugin Selection

| Deployment | Plugin | Use Case |
|------------|--------|----------|
| Development | `k8s` | Simple, no external deps |
| Production (OSS) | `infisical` | Full secrets management |
| Enterprise | `vault` | Dynamic secrets, PKI |
| Enterprise | `infisical-ee` | SSO, advanced RBAC |

---

## Migration from ESO

For deployments currently using External Secrets Operator:

1. **Keep ESO running** - Infisical supports ESO as a provider
2. **Configure Infisical as ESO provider**:
   ```yaml
   apiVersion: external-secrets.io/v1beta1
   kind: SecretStore
   metadata:
     name: infisical-store
   spec:
     provider:
       infisical:
         auth:
           universalAuth:
             credentials:
               clientId: <client-id>
               clientSecret: <client-secret>
         projectSlug: floe-platform
   ```
3. **Migrate incrementally** - Switch secrets one at a time
4. **Remove ESO** - Once all secrets migrated to native Infisical Operator

---

## Security Considerations

### Authentication

- **Machine Identity**: Use Universal Auth (client ID/secret)
- **Token Rotation**: Tokens auto-rotated by SDK
- **Least Privilege**: Scope access by project and environment

### Secret Rotation

```yaml
# Auto-reload annotation
metadata:
  annotations:
    secrets.infisical.com/auto-reload: "true"
```

When secrets change in Infisical:
1. Operator syncs to K8s Secret
2. Operator triggers pod restart
3. New pods receive updated environment variables

### Audit Logging

- **Infisical Cloud**: Built-in audit logs
- **Self-hosted**: Configure PostgreSQL audit tables
- **Enterprise**: Advanced audit with SIEM integration

---

## CLI Commands

```bash
# List secrets (names only)
floe secrets list --namespace=floe-jobs
# Output:
# NAME                      TYPE              SYNC STATUS
# snowflake-credentials     InfisicalSecret   Synced
# catalog-credentials       InfisicalSecret   Synced

# Check sync status
floe secrets status
# Output:
# NAME                      PROJECT           ENV         LAST SYNC
# snowflake-credentials     floe-platform     production  2m ago
# catalog-credentials       floe-platform     production  2m ago

# Validate secret references
floe secrets validate
# Output:
# Validating secret references in platform-manifest.yaml...
# ✓ snowflake-credentials: exists, 3 keys
# ✓ catalog-credentials: exists, 2 keys
```

---

## References

- [Infisical Documentation](https://infisical.com/docs)
- [Infisical Kubernetes Operator](https://infisical.com/docs/integrations/platforms/kubernetes/overview)
- [infisicalsdk PyPI](https://pypi.org/project/infisicalsdk/)
- [ESO Development Paused Announcement](https://infisical.com/blog/external-secrets-operator-paused)
- [Infisical GitHub](https://github.com/Infisical/infisical)
- [ADR-0023: Secrets Management](0023-secrets-management.md) - Superseded by this ADR
- [ADR-0022: Security & RBAC Model](0022-security-rbac-model.md) - Security context

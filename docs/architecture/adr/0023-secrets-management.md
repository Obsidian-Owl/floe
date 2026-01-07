# ADR-0023: Secrets Management Architecture

## Status

Accepted

**RFC 2119 Compliance:** This ADR uses MUST/SHOULD/MAY keywords per [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119.txt). See [glossary](../../contracts/glossary.md#documentation-keywords-rfc-2119).

## Context

floe requires credentials for:

1. **Compute targets**: Snowflake passwords, BigQuery service accounts, Databricks tokens
2. **Object storage**: MinIO access keys, AWS IAM credentials, GCS service accounts
3. **Catalog access**: Polaris OAuth2 client credentials
4. **Ingestion sources**: API keys, database passwords, OAuth tokens
5. **Internal services**: JWT signing keys, PostgreSQL passwords

Without a consistent secrets management strategy:

- Credentials MUST NOT be hardcoded or committed to git (security violation)
- Different plugins handle secrets inconsistently
- Rotation is manual and error-prone
- Cloud-native credential sources are underutilized

Key requirements:

- **No secrets in code**: All credentials via environment or external stores
- **Consistent interface**: Same pattern regardless of secret backend
- **Rotation support**: Credentials can be rotated without redeploy
- **Cloud integration**: Native support for AWS/GCP/Azure secret managers
- **dbt compatibility**: Works with dbt's `env_var()` pattern

## Decision

Implement a `SecretsPlugin` abstraction with three supported backends:

1. **Kubernetes Secrets** (default) - Simple, no external dependencies
2. **External Secrets Operator** - Syncs from cloud secret managers
3. **HashiCorp Vault** - Dynamic secrets, enterprise features

All backends produce the same output: environment variables injected into job pods.

## Consequences

### Positive

- **Unified interface**: Plugins don't know secret backend
- **Batteries included**: K8s Secrets works out of box
- **Cloud-native**: ESO enables AWS/GCP/Azure integration
- **Dynamic secrets**: Vault provides short-lived credentials
- **dbt compatible**: Always uses `env_var()` pattern

### Negative

- **ESO dependency**: External Secrets Operator must be installed separately
- **Vault complexity**: Requires Vault infrastructure and expertise
- **Rotation coordination**: Must restart pods after rotation (unless using Vault)

### Neutral

- K8s Secrets suitable for many deployments
- ESO installation well-documented
- Vault enterprise features optional

---

## Secrets Flow Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SECRETS FLOW                                                                │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. SECRET SOURCE                                                    │    │
│  │                                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │ AWS Secrets  │  │ GCP Secret   │  │ Azure Key    │              │    │
│  │  │ Manager      │  │ Manager      │  │ Vault        │              │    │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │    │
│  │         │                 │                 │                       │    │
│  │         └────────────────►│◄────────────────┘                       │    │
│  │                           │                                          │    │
│  │                           ▼                                          │    │
│  │              ┌─────────────────────────┐                            │    │
│  │              │ External Secrets        │                            │    │
│  │              │ Operator (optional)     │                            │    │
│  │              └───────────┬─────────────┘                            │    │
│  │                          │                                          │    │
│  └──────────────────────────┼──────────────────────────────────────────┘    │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  2. KUBERNETES SECRET                                                │    │
│  │                                                                      │    │
│  │  apiVersion: v1                                                     │    │
│  │  kind: Secret                                                       │    │
│  │  metadata:                                                          │    │
│  │    name: snowflake-credentials                                      │    │
│  │  stringData:                                                        │    │
│  │    SNOWFLAKE_ACCOUNT: "xxx.us-east-1"                              │    │
│  │    SNOWFLAKE_USER: "dbt_user"                                      │    │
│  │    SNOWFLAKE_PASSWORD: "***"                                       │    │
│  │                                                                      │    │
│  └──────────────────────────┬──────────────────────────────────────────┘    │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  3. JOB POD                                                          │    │
│  │                                                                      │    │
│  │  spec:                                                              │    │
│  │    containers:                                                      │    │
│  │      - name: dbt                                                    │    │
│  │        envFrom:                                                     │    │
│  │          - secretRef:                                               │    │
│  │              name: snowflake-credentials                            │    │
│  │                                                                      │    │
│  │  Environment:                                                       │    │
│  │    SNOWFLAKE_ACCOUNT=xxx.us-east-1                                 │    │
│  │    SNOWFLAKE_USER=dbt_user                                         │    │
│  │    SNOWFLAKE_PASSWORD=***                                          │    │
│  │                                                                      │    │
│  └──────────────────────────┬──────────────────────────────────────────┘    │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  4. DBT PROFILE                                                      │    │
│  │                                                                      │    │
│  │  # profiles.yml (generated)                                         │    │
│  │  floe:                                                              │    │
│  │    target: prod                                                     │    │
│  │    outputs:                                                         │    │
│  │      prod:                                                          │    │
│  │        type: snowflake                                              │    │
│  │        account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"               │    │
│  │        user: "{{ env_var('SNOWFLAKE_USER') }}"                     │    │
│  │        password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"             │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Secret Categories

| Category | Examples | Lifecycle | Backend Recommendation |
|----------|----------|-----------|------------------------|
| **Compute credentials** | Snowflake password, BQ SA key | Long-lived, rotated quarterly | ESO + cloud secret manager |
| **Storage credentials** | MinIO keys, S3 access keys | Long-lived or vended | Polaris credential vending |
| **Ingestion sources** | API keys, OAuth tokens | Varies by source | ESO for cloud, K8s for API keys |
| **Internal services** | PostgreSQL, Redis passwords | Long-lived | K8s Secrets |
| **Signing keys** | JWT secrets, cosign keys | Long-lived, rarely rotated | K8s Secrets |

---

## Plugin Implementations

### SecretsPlugin Interface

```python
# floe_core/interfaces/secrets.py
from abc import ABC, abstractmethod

class SecretsPlugin(ABC):
    """Interface for secrets management (K8s Secrets, ESO, Vault)."""

    name: str
    version: str

    @abstractmethod
    def get_secret(self, name: str, namespace: str) -> dict[str, str]:
        """Retrieve a secret by name.

        Args:
            name: Secret name
            namespace: K8s namespace

        Returns:
            Dict of key-value pairs
        """
        pass

    @abstractmethod
    def create_secret(
        self,
        name: str,
        namespace: str,
        data: dict[str, str]
    ) -> None:
        """Create a secret.

        Args:
            name: Secret name
            namespace: K8s namespace
            data: Key-value pairs to store
        """
        pass

    @abstractmethod
    def inject_env_vars(self, secret_refs: dict[str, str]) -> dict[str, str]:
        """Generate environment variable mappings for K8s pods.

        Args:
            secret_refs: Mapping of env var name to secret key

        Returns:
            K8s env var configuration for pod spec
        """
        pass

    @abstractmethod
    def generate_secret_mounts(self, secret_name: str) -> dict:
        """Generate K8s pod spec for mounting secrets as env vars.

        Args:
            secret_name: Name of K8s Secret

        Returns:
            Pod spec fragment with envFrom configuration
        """
        pass
```

### Kubernetes Secrets (Default)

```python
# plugins/floe-secrets-k8s/plugin.py
from kubernetes import client, config

class K8sSecretsPlugin(SecretsPlugin):
    """Default secrets plugin using Kubernetes Secrets."""

    name = "k8s"
    version = "1.0.0"

    def __init__(self):
        config.load_incluster_config()
        self.v1 = client.CoreV1Api()

    def get_secret(self, name: str, namespace: str) -> dict[str, str]:
        secret = self.v1.read_namespaced_secret(name, namespace)
        return {
            k: base64.b64decode(v).decode()
            for k, v in secret.data.items()
        }

    def create_secret(
        self,
        name: str,
        namespace: str,
        data: dict[str, str]
    ) -> None:
        secret = client.V1Secret(
            metadata=client.V1ObjectMeta(name=name),
            string_data=data,
        )
        self.v1.create_namespaced_secret(namespace, secret)

    def inject_env_vars(self, secret_refs: dict[str, str]) -> dict[str, str]:
        # Returns pod spec fragment
        return {
            "envFrom": [{"secretRef": {"name": ref}} for ref in secret_refs.values()]
        }

    def generate_secret_mounts(self, secret_name: str) -> dict:
        return {
            "envFrom": [
                {"secretRef": {"name": secret_name}}
            ]
        }
```

### External Secrets Operator

```python
# plugins/floe-secrets-eso/plugin.py
class ESOSecretsPlugin(SecretsPlugin):
    """Secrets plugin using External Secrets Operator."""

    name = "external-secrets"
    version = "1.0.0"

    def create_external_secret(
        self,
        name: str,
        namespace: str,
        secret_store: str,
        remote_ref: str,
    ) -> None:
        """Create ExternalSecret CR that syncs from cloud secret manager."""
        external_secret = {
            "apiVersion": "external-secrets.io/v1beta1",
            "kind": "ExternalSecret",
            "metadata": {
                "name": name,
                "namespace": namespace,
            },
            "spec": {
                "refreshInterval": "1h",
                "secretStoreRef": {
                    "name": secret_store,
                    "kind": "ClusterSecretStore",
                },
                "target": {
                    "name": name,
                    "creationPolicy": "Owner",
                },
                "data": [
                    {
                        "secretKey": key,
                        "remoteRef": {"key": remote_ref, "property": key},
                    }
                    for key in self.expected_keys
                ],
            },
        }
        # Apply via kubernetes client
        self.custom_api.create_namespaced_custom_object(
            group="external-secrets.io",
            version="v1beta1",
            namespace=namespace,
            plural="externalsecrets",
            body=external_secret,
        )
```

**ESO SecretStore Configuration:**

```yaml
# AWS Secrets Manager
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
---
# GCP Secret Manager
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: gcp-secret-manager
spec:
  provider:
    gcpsm:
      projectID: my-gcp-project
      auth:
        workloadIdentity:
          clusterLocation: us-central1
          clusterName: my-cluster
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
---
# Azure Key Vault
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: azure-keyvault
spec:
  provider:
    azurekv:
      vaultUrl: "https://my-vault.vault.azure.net"
      authType: ManagedIdentity
```

### HashiCorp Vault

```python
# plugins/floe-secrets-vault/plugin.py
import hvac

class VaultSecretsPlugin(SecretsPlugin):
    """Secrets plugin using HashiCorp Vault."""

    name = "vault"
    version = "1.0.0"

    def __init__(self, vault_addr: str, auth_method: str = "kubernetes"):
        self.client = hvac.Client(url=vault_addr)
        if auth_method == "kubernetes":
            self._auth_kubernetes()

    def _auth_kubernetes(self):
        """Authenticate using Kubernetes service account."""
        with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
            jwt = f.read()
        self.client.auth.kubernetes.login(role="floe", jwt=jwt)

    def get_secret(self, name: str, namespace: str) -> dict[str, str]:
        """Read secret from Vault KV v2."""
        path = f"floe/{namespace}/{name}"
        response = self.client.secrets.kv.v2.read_secret_version(path=path)
        return response["data"]["data"]

    def get_dynamic_credentials(
        self,
        backend: str,
        role: str,
    ) -> dict[str, str]:
        """Get dynamic database credentials from Vault."""
        # Vault generates short-lived credentials
        response = self.client.secrets.database.generate_credentials(
            name=role,
            mount_point=backend,
        )
        return {
            "username": response["data"]["username"],
            "password": response["data"]["password"],
            "lease_id": response["lease_id"],
            "lease_duration": response["lease_duration"],
        }
```

**Vault Configuration:**

```hcl
# Vault policy for floe
path "floe/*" {
  capabilities = ["read", "list"]
}

path "database/creds/snowflake-dbt" {
  capabilities = ["read"]
}

# Kubernetes auth method
resource "vault_kubernetes_auth_backend_role" "floe_runtime" {
  backend                          = vault_auth_backend.kubernetes.path
  role_name                        = "floe"
  bound_service_account_names      = ["floe-job-runner"]
  bound_service_account_namespaces = ["floe-jobs"]
  token_policies                   = ["floe"]
  token_ttl                        = 3600
}
```

---

## Credential Flow

### Compile-Time: Manifest → Profile

```
manifest.yaml                floe compile              profiles.yml
       │                                   │                          │
       ▼                                   ▼                          ▼
┌──────────────────────┐           ┌─────────────────┐      ┌─────────────────────┐
│ plugins:             │           │                 │      │ floe:               │
│   compute:           │───────────│  ComputePlugin  │──────│   target: prod      │
│     type: snowflake  │           │  .generate_dbt_ │      │   outputs:          │
│     connection_      │           │   profile()     │      │     prod:           │
│       secret_ref:    │           │                 │      │       type: snowflake│
│       snowflake-     │           └─────────────────┘      │       account: "{{  │
│       credentials    │                                    │         env_var(    │
│                      │                                    │         'SNOWFLAKE_ │
└──────────────────────┘                                    │         ACCOUNT')}}"|
                                                            └─────────────────────┘
```

**Key Principle:** `floe compile` generates profiles that reference environment variables, never actual secrets.

### Runtime: Secret Injection

```
┌─────────────────┐
│ Dagster         │
│ schedules job   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  K8s Job Pod Spec                                                            │
│                                                                              │
│  spec:                                                                       │
│    serviceAccountName: floe-job-runner                                      │
│    containers:                                                               │
│      - name: dbt                                                            │
│        image: ghcr.io/floe/dbt:1.7                                  │
│        command: ["dbt", "run"]                                              │
│        envFrom:                                                              │
│          - secretRef:                                                        │
│              name: snowflake-credentials  ◄── Injected by SecretsPlugin     │
│          - secretRef:                                                        │
│              name: catalog-credentials                                       │
│        env:                                                                  │
│          - name: DBT_PROFILES_DIR                                           │
│            value: /app/profiles                                             │
│        volumeMounts:                                                         │
│          - name: dbt-profiles                                               │
│            mountPath: /app/profiles                                         │
│    volumes:                                                                  │
│      - name: dbt-profiles                                                   │
│        configMap:                                                            │
│          name: dbt-profiles  ◄── Contains profiles.yml with env_var()       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Secret Rotation

### Static Rotation (K8s Secrets, ESO)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STATIC ROTATION WORKFLOW                                                    │
│                                                                              │
│  1. Update secret in source (AWS SM, Azure KV, K8s Secret)                  │
│                                                                              │
│  2. ESO syncs to K8s Secret (if using ESO)                                  │
│     └── refreshInterval: 1h                                                 │
│                                                                              │
│  3. Trigger pod restart                                                     │
│     └── kubectl rollout restart deployment/dagster-daemon                   │
│     └── Or: Use Reloader (stakater/Reloader) for automatic restart          │
│                                                                              │
│  4. New pods pick up updated environment variables                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Reloader Annotation (Automatic Restart):**

```yaml
# Auto-restart when secret changes
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dagster-daemon
  annotations:
    reloader.stakater.com/auto: "true"
spec:
  template:
    spec:
      containers:
        - name: daemon
          envFrom:
            - secretRef:
                name: snowflake-credentials
```

### Dynamic Rotation (Vault)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  DYNAMIC CREDENTIALS (VAULT)                                                 │
│                                                                              │
│  ┌──────────────┐                      ┌──────────────┐                     │
│  │  Job Pod     │  1. Request creds    │    Vault     │                     │
│  │  (dbt run)   │ ────────────────────►│  Database    │                     │
│  │              │                      │  Secrets     │                     │
│  │              │ ◄────────────────────│  Engine      │                     │
│  │              │  2. Short-lived      │              │                     │
│  │              │     credentials      └──────┬───────┘                     │
│  │              │     (TTL: 1h)               │                             │
│  │              │                             │                             │
│  │              │  3. Execute dbt             │                             │
│  │              │ ─────────────────►  ┌───────┴───────┐                     │
│  │              │                     │   Snowflake   │                     │
│  │              │                     │   (target)    │                     │
│  └──────────────┘                     └───────────────┘                     │
│                                                                              │
│  Benefits:                                                                   │
│  • No static credentials in K8s Secrets                                     │
│  • Automatic rotation (credentials expire)                                  │
│  • Audit trail in Vault                                                     │
│  • Revocation on job failure                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Credential Vending (Polaris)

For object storage access, Polaris can vend short-lived credentials:

```python
# CatalogPlugin.vend_credentials()
def vend_credentials(
    self,
    table_path: str,
    operations: list[str]  # ["READ", "WRITE"]
) -> dict:
    """Request short-lived credentials from Polaris."""
    response = self.client.post(
        f"{self.catalog_uri}/v1/credentials/vend",
        json={
            "table": table_path,
            "operations": operations,
        }
    )
    return {
        "access_key_id": response["accessKeyId"],
        "secret_access_key": response["secretAccessKey"],
        "session_token": response["sessionToken"],
        "expiration": response["expiration"],  # ~1 hour
    }
```

---

## Cloud Provider Integration

### AWS Secrets Manager + ESO

```yaml
# manifest.yaml
plugins:
  secrets:
    type: external-secrets
    config:
      store: aws-secrets-manager
      region: us-east-1

# ExternalSecret for compute credentials
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: snowflake-credentials
  namespace: floe-jobs
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: snowflake-credentials
    creationPolicy: Owner
  data:
    - secretKey: SNOWFLAKE_ACCOUNT
      remoteRef:
        key: floe/prod/snowflake
        property: account
    - secretKey: SNOWFLAKE_USER
      remoteRef:
        key: floe/prod/snowflake
        property: user
    - secretKey: SNOWFLAKE_PASSWORD
      remoteRef:
        key: floe/prod/snowflake
        property: password
```

### GCP Secret Manager + ESO

```yaml
# manifest.yaml
plugins:
  secrets:
    type: external-secrets
    config:
      store: gcp-secret-manager
      project: my-gcp-project

# ExternalSecret for BigQuery SA
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: bigquery-credentials
  namespace: floe-jobs
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: gcp-secret-manager
    kind: ClusterSecretStore
  target:
    name: bigquery-credentials
  data:
    - secretKey: GOOGLE_APPLICATION_CREDENTIALS_JSON
      remoteRef:
        key: floe-bigquery-sa
```

### Azure Key Vault + ESO

```yaml
# manifest.yaml
plugins:
  secrets:
    type: external-secrets
    config:
      store: azure-keyvault
      vault_url: https://my-vault.vault.azure.net

# ExternalSecret for Synapse
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: synapse-credentials
  namespace: floe-jobs
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: azure-keyvault
    kind: ClusterSecretStore
  target:
    name: synapse-credentials
  data:
    - secretKey: SYNAPSE_CONNECTION_STRING
      remoteRef:
        key: floe-synapse-connection
```

---

## Configuration Schema

```yaml
# manifest.yaml - full secrets configuration
plugins:
  secrets:
    type: k8s | external-secrets | vault

    # K8s Secrets (default)
    # No additional config needed

    # External Secrets Operator
    config:
      store: string              # ClusterSecretStore name
      refresh_interval: 1h       # How often to sync

    # HashiCorp Vault
    config:
      address: https://vault.example.com
      auth_method: kubernetes | approle
      role: floe
      mount_path: kubernetes    # For K8s auth
      secret_path_prefix: floe/

  # Compute plugin with secret reference
  compute:
    type: snowflake
    connection_secret_ref: snowflake-credentials  # K8s Secret name

  # Catalog plugin with secret reference
  catalog:
    type: polaris
    config:
      client_secret_ref: polaris-credentials

# Secret references in ingestion configs
ingestion:
  pipelines:
    - name: salesforce-sync
      source:
        type: salesforce
        secret_refs:
          client_id: salesforce-credentials
          client_secret: salesforce-credentials
```

---

## CLI Commands

```bash
# List secrets (names only, not values)
floe secrets list --namespace=floe-jobs
# Output:
# NAME                      TYPE              AGE
# snowflake-credentials     Opaque            7d
# catalog-credentials       Opaque            7d
# salesforce-credentials    Opaque            3d

# Check secret sync status (ESO)
floe secrets status
# Output:
# NAME                      STORE                   SYNC STATUS    LAST SYNC
# snowflake-credentials     aws-secrets-manager     Synced         2m ago
# catalog-credentials       aws-secrets-manager     Synced         2m ago

# Rotate a secret (updates in source, triggers sync)
floe secrets rotate snowflake-credentials --restart-deployments
# Output:
# Rotating secret: snowflake-credentials
# ✓ Secret updated in AWS Secrets Manager
# ✓ ExternalSecret sync triggered
# ✓ Restarting deployments: dagster-daemon
# Rotation complete.

# Validate secret references
floe secrets validate
# Output:
# Validating secret references in manifest.yaml...
# ✓ snowflake-credentials: exists, 3 keys
# ✓ catalog-credentials: exists, 2 keys
# ✗ salesforce-credentials: NOT FOUND
#
# 1 error found. Run 'floe secrets create salesforce-credentials' to fix.
```

---

## Security Best Practices

### Do

- SHOULD use ESO or Vault for production deployments
- SHOULD enable automatic secret rotation where supported
- MUST use separate secrets per environment (dev/staging/prod)
- SHOULD scope secrets to specific namespaces
- SHOULD use Reloader for automatic pod restarts on secret change
- MUST audit secret access via K8s audit logs

### Don't

- MUST NOT commit secrets to git (use `.gitignore`)
- MUST NOT log secret values
- MUST NOT share secrets across environments
- SHOULD NOT use long-lived credentials when short-lived available
- SHOULD NOT grant broad secret access (use resourceNames)

### Secret Naming Convention

```
{service}-{environment}-credentials
{service}-{purpose}-secret

Examples:
  snowflake-prod-credentials
  polaris-oauth-credentials
  salesforce-api-secret
  cube-jwt-signing-key
```

---

## References

- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [External Secrets Operator](https://external-secrets.io/)
- [HashiCorp Vault](https://www.vaultproject.io/)
- [Vault Kubernetes Auth](https://developer.hashicorp.com/vault/docs/auth/kubernetes)
- [Reloader](https://github.com/stakater/Reloader) - Automatic pod restart on secret change
- [dbt env_var](https://docs.getdbt.com/reference/dbt-jinja-functions/env_var)
- [ADR-0022: Security & RBAC Model](0022-security-rbac-model.md) - Security context
- [Interfaces: SecretsPlugin](../interfaces/secrets-plugin.md) - Plugin interface
- [Storage Integration](../storage-integration.md) - Credential vending

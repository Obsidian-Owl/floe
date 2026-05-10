# SecretsPlugin

**Purpose**: Credential management and secret injection
**Location**: `packages/floe-core/src/floe_core/plugins/secrets.py`
**Entry Point**: `floe.secrets`
**ADR**: [ADR-0023: Secrets Management](../adr/0023-secrets-management.md), [ADR-0031: Infisical Secrets](../adr/0031-infisical-secrets.md)

SecretsPlugin abstracts credential storage and retrieval, supporting Kubernetes Secrets, External Secrets Operator (ESO), HashiCorp Vault, and other secret management solutions.

## Composition Capabilities

Secrets plugins declare their credential projection surface with
`get_secret_capabilities(self) -> PluginCapabilities`. The composition resolver
uses this secret-free declaration to validate storage and catalog requirements
before deployment bindings are rendered.

Supported `secret_projection_modes` are:

- `kubernetes-secret` - Credentials are available through a Kubernetes Secret
  reference.
- `external-secret-sync` - Credentials are synchronized by an external secrets
  controller and referenced without embedding secret values.
- `csi-secret-volume` - Credentials are projected through a CSI secret volume.
- `environment` - Credentials are projected as environment variables from a
  managed secret source.

Capabilities must not contain raw secret values. Provider-specific fields, such
as Infisical project IDs, Vault paths, or cloud secret manager identifiers,
remain in provider-owned plugin config or provider-owned deployment bindings.
`floe-core` validates named modes and provider labels; the secrets plugin owns
translation into its runtime or controller-specific resources.

## Interface Definition

The live ABC is `SecretsPlugin` in
`packages/floe-core/src/floe_core/plugins/secrets.py`. The snippet below is a
conceptual excerpt for the public contract.

```python
# Conceptual excerpt; see packages/floe-core/src/floe_core/plugins/secrets.py
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
            K8s env var configuration
        """
        pass
```

## Reference Implementations

| Plugin | Description |
|--------|-------------|
| `K8sSecretsPlugin` | Native Kubernetes Secrets |
| `ESOSecretsPlugin` | External Secrets Operator (AWS SM, GCP SM, Azure KV) |
| `VaultSecretsPlugin` | HashiCorp Vault integration |

## Related Documents

- [ADR-0023: Secrets Management](../adr/0023-secrets-management.md)
- [ADR-0031: Infisical Secrets](../adr/0031-infisical-secrets.md)
- [Plugin Architecture](../plugin-system/index.md)
- [ComputePlugin](compute-plugin.md) - For credential injection into dbt profiles

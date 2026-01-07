# SecretsPlugin

**Purpose**: Credential management and secret injection
**Location**: `floe_core/interfaces/secrets.py`
**Entry Point**: `floe.secrets`
**ADR**: [ADR-0023: Secrets Management](../adr/0023-secrets-management.md), [ADR-0031: Secret References](../adr/0031-secret-references.md)

SecretsPlugin abstracts credential storage and retrieval, supporting Kubernetes Secrets, External Secrets Operator (ESO), HashiCorp Vault, and other secret management solutions.

## Interface Definition

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
- [ADR-0031: Secret References](../adr/0031-secret-references.md)
- [Plugin Architecture](../plugin-system/index.md)
- [ComputePlugin](compute-plugin.md) - For credential injection into dbt profiles

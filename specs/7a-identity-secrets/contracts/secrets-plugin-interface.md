# Contract: SecretsPlugin Interface

**Version**: 1.0.0
**Status**: Draft
**Date**: 2026-01-18

## Overview

This contract defines the interface for Secrets plugins in the floe platform. All secrets backend implementations MUST conform to this interface.

## Interface Definition

```python
from __future__ import annotations
from abc import abstractmethod
from typing import Any
from floe_core.plugin_metadata import PluginMetadata

class SecretsPlugin(PluginMetadata):
    """Abstract base class for credential management plugins.

    All secrets plugins MUST implement these methods:
    - get_secret(): Retrieve a secret by key
    - set_secret(): Store a secret
    - list_secrets(): List available secrets

    Implementations include:
    - K8sSecretsPlugin (default)
    - InfisicalSecretsPlugin (recommended OSS)
    - VaultSecretsPlugin (enterprise)
    """

    @abstractmethod
    def get_secret(self, key: str) -> str | None:
        """Retrieve a secret by key.

        Args:
            key: Secret key/path (e.g., "database/password").

        Returns:
            Secret value as string, or None if not found.

        Raises:
            PermissionError: Lacking permission to read the secret.
            ConnectionError: Unable to connect to secrets backend.
        """
        ...

    @abstractmethod
    def set_secret(
        self,
        key: str,
        value: str,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """Store a secret.

        Creates the secret if it doesn't exist, or updates it.

        Args:
            key: Secret key/path.
            value: Secret value to store.
            metadata: Optional metadata to associate with the secret.

        Raises:
            PermissionError: Lacking permission to write the secret.
            ConnectionError: Unable to connect to secrets backend.
        """
        ...

    @abstractmethod
    def list_secrets(self, prefix: str = "") -> list[str]:
        """List available secrets.

        Args:
            prefix: Optional prefix to filter secrets.

        Returns:
            List of secret keys matching the prefix.

        Raises:
            PermissionError: Lacking permission to list secrets.
            ConnectionError: Unable to connect to secrets backend.
        """
        ...

    def generate_pod_env_spec(self, secret_name: str) -> dict[str, Any]:
        """Generate K8s pod spec fragment for secret injection.

        Optional method for K8s-native plugins.

        Args:
            secret_name: K8s Secret name to mount.

        Returns:
            Pod spec fragment with envFrom configuration.

        Example:
            >>> spec = plugin.generate_pod_env_spec("db-creds")
            >>> spec
            {'envFrom': [{'secretRef': {'name': 'db-creds'}}]}
        """
        return {
            "envFrom": [{"secretRef": {"name": secret_name}}]
        }

    def get_multi_key_secret(self, name: str) -> dict[str, str]:
        """Retrieve all key-value pairs from a multi-key secret.

        OPTIONAL: This method is NOT part of the core SecretsPlugin contract.
        Implementations MAY override this method if the backend natively supports
        multi-key secrets (e.g., K8s Secrets with multiple data keys).

        The default implementation raises NotImplementedError, which is the
        expected behavior for backends that don't support multi-key retrieval.
        Callers MUST handle NotImplementedError gracefully.

        Note:
            - K8sSecretsPlugin: SHOULD implement (K8s Secrets are inherently multi-key)
            - InfisicalSecretsPlugin: MAY implement (path-based secrets can be grouped)
            - VaultSecretsPlugin: MAY implement (KV v2 supports multi-key)

        Args:
            name: Secret name.

        Returns:
            Dictionary of key-value pairs from the secret.

        Raises:
            NotImplementedError: Default - backend doesn't support multi-key.
            PermissionError: Lacking permission to read the secret.
            ConnectionError: Unable to connect to secrets backend.
        """
        raise NotImplementedError("Multi-key secrets not supported")
```

## Entry Point Registration

Plugins MUST register via `pyproject.toml`:

```toml
[project.entry-points."floe.secrets"]
k8s = "floe_secrets_k8s.plugin:K8sSecretsPlugin"
infisical = "floe_secrets_infisical.plugin:InfisicalSecretsPlugin"
vault = "floe_secrets_vault.plugin:VaultSecretsPlugin"
```

## Compliance Requirements

### CR-001: PluginMetadata Properties

All implementations MUST provide:
- `name`: Unique identifier (e.g., "k8s", "infisical", "vault")
- `version`: Semantic version (e.g., "1.0.0")
- `floe_api_version`: Minimum API version (e.g., "1.0")

### CR-002: Health Check

All implementations MUST implement `health_check()`:
- Return within 5 seconds
- Return `HealthStatus` with state and optional message
- Check connectivity to secrets backend

### CR-003: Configuration Schema

All implementations MUST provide `get_config_schema()`:
- Return Pydantic BaseModel subclass
- Use `SecretStr` for all credentials
- Use `ConfigDict(frozen=True, extra="forbid")`

### CR-004: Error Handling

All implementations MUST:
- Return `None` for non-existent secrets (not raise exception)
- Raise `PermissionError` for authorization failures
- Raise `ConnectionError` for connectivity issues
- Never expose internal exceptions to callers

### CR-005: Security

All implementations MUST:
- Never log secret values
- Never include secret values in error messages
- Mask credentials in any diagnostic output
- Use environment variables or SecretStr for configuration

### CR-006: Audit Logging

All implementations SHOULD:
- Log secret access operations (key only, not value)
- Include requester identity in logs
- Include trace context for distributed tracing

## Testing Requirements

All implementations MUST pass `BaseSecretsPluginTests`:

```python
class BaseSecretsPluginTests(PluginTestBase):
    """Compliance tests for SecretsPlugin implementations."""

    @pytest.mark.requirement("7A-FR-002")
    def test_plugin_has_required_metadata(self) -> None:
        """Plugin has name, version, floe_api_version."""

    @pytest.mark.requirement("7A-FR-002")
    def test_get_secret_returns_value_or_none(self) -> None:
        """get_secret() returns str or None, raises for errors."""

    @pytest.mark.requirement("7A-FR-002")
    def test_set_secret_creates_or_updates(self) -> None:
        """set_secret() creates new or updates existing secret."""

    @pytest.mark.requirement("7A-FR-002")
    def test_list_secrets_returns_list(self) -> None:
        """list_secrets() returns list of keys."""

    @pytest.mark.requirement("7A-FR-002")
    def test_list_secrets_filters_by_prefix(self) -> None:
        """list_secrets(prefix) filters results."""

    @pytest.mark.requirement("7A-FR-060")
    def test_permission_error_on_unauthorized(self) -> None:
        """Raises PermissionError when unauthorized."""

    @pytest.mark.requirement("7A-FR-061")
    def test_connection_error_on_unavailable(self) -> None:
        """Raises ConnectionError when backend unavailable."""
```

## K8s Integration

### Pod Spec Generation

Plugins SHOULD support generating K8s pod spec fragments:

```python
# For envFrom injection (all keys in secret)
{
    "envFrom": [
        {"secretRef": {"name": "snowflake-credentials"}}
    ]
}

# For specific key injection
{
    "env": [
        {
            "name": "DATABASE_PASSWORD",
            "valueFrom": {
                "secretKeyRef": {
                    "name": "db-creds",
                    "key": "password"
                }
            }
        }
    ]
}
```

### SecretReference Resolution

The `SecretReference` model converts to dbt-compatible syntax:

```python
ref = SecretReference(name="db-creds", key="password")
ref.to_env_var_syntax()
# Returns: "{{ env_var('FLOE_SECRET_DB_CREDS_PASSWORD') }}"
```

## Versioning

- **1.0.0**: Initial interface (get_secret, set_secret, list_secrets)
- Future: Add delete_secret(), rotate_secret(), get_metadata() methods

"""SecretsPlugin ABC for credential management plugins.

This module defines the abstract base class for secrets plugins that
provide credential management functionality. Secrets plugins are
responsible for:
- Retrieving secrets by key
- Storing secrets securely
- Listing available secrets

Example:
    >>> from floe_core.plugins.secrets import SecretsPlugin
    >>> class VaultPlugin(SecretsPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "vault"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from floe_core.plugin_metadata import PluginMetadata


class SecretsPlugin(PluginMetadata):
    """Abstract base class for credential management plugins.

    SecretsPlugin extends PluginMetadata with secrets-specific methods
    for managing credentials. Implementations include HashiCorp Vault,
    AWS Secrets Manager, and environment variables.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - get_secret() method
        - set_secret() method
        - list_secrets() method

    Example:
        >>> class VaultPlugin(SecretsPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "vault"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def get_secret(self, key: str) -> str | None:
        ...         return self._client.read_secret(key)

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
    """

    @abstractmethod
    def get_secret(self, key: str) -> str | None:
        """Retrieve a secret by key.

        Fetches the secret value for the given key from the secrets
        backend. Returns None if the secret doesn't exist.

        Args:
            key: Secret key/path (e.g., "database/password", "api/key").

        Returns:
            Secret value as string, or None if not found.

        Raises:
            PermissionError: If lacking permission to read the secret.
            ConnectionError: If unable to connect to secrets backend.

        Example:
            >>> password = plugin.get_secret("database/postgres/password")
            >>> password
            'supersecret123'

            >>> missing = plugin.get_secret("nonexistent/key")
            >>> missing is None
            True
        """
        ...

    @abstractmethod
    def set_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
        """Store a secret.

        Stores the secret value at the given key. Creates the secret
        if it doesn't exist, or updates it if it does.

        Args:
            key: Secret key/path (e.g., "database/password").
            value: Secret value to store.
            metadata: Optional metadata to associate with the secret.

        Raises:
            PermissionError: If lacking permission to write the secret.
            ConnectionError: If unable to connect to secrets backend.

        Example:
            >>> plugin.set_secret(
            ...     key="database/postgres/password",
            ...     value="newsecret456",
            ...     metadata={"created_by": "floe", "environment": "prod"}
            ... )
        """
        ...

    @abstractmethod
    def list_secrets(self, prefix: str = "") -> list[str]:
        """List available secrets.

        Returns a list of secret keys, optionally filtered by prefix.

        Args:
            prefix: Optional prefix to filter secrets (e.g., "database/").

        Returns:
            List of secret keys matching the prefix.

        Raises:
            PermissionError: If lacking permission to list secrets.
            ConnectionError: If unable to connect to secrets backend.

        Example:
            >>> plugin.list_secrets()
            ['database/postgres/password', 'api/stripe/key', 'api/sendgrid/key']

            >>> plugin.list_secrets(prefix="api/")
            ['api/stripe/key', 'api/sendgrid/key']
        """
        ...

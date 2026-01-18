"""InfisicalSecretsPlugin implementation.

This module provides the InfisicalSecretsPlugin class for accessing Infisical
as the recommended OSS secrets backend for the floe platform (per ADR-0031).

Implements:
    - FR-020: InfisicalSecretsPlugin integration
    - FR-021: Universal Auth authentication
    - FR-022: InfisicalSecret CRD integration
    - FR-023: Auto-reload pods on secret change
    - FR-024: Path-based secret organization

Example:
    >>> from pydantic import SecretStr
    >>> from floe_secrets_infisical import InfisicalSecretsPlugin, InfisicalSecretsConfig
    >>> config = InfisicalSecretsConfig(
    ...     client_id="my-client-id",
    ...     client_secret=SecretStr("my-client-secret"),
    ...     project_id="proj_12345",
    ... )
    >>> plugin = InfisicalSecretsPlugin(config=config)
    >>> plugin.startup()
    >>> secret = plugin.get_secret("database-password")
    >>> plugin.shutdown()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from floe_core.audit import AuditLogger, AuditOperation
from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.secrets import SecretsPlugin

from floe_secrets_infisical.config import InfisicalSecretsConfig
from floe_secrets_infisical.errors import (
    InfisicalAccessDeniedError,
    InfisicalAuthError,
    InfisicalBackendUnavailableError,
    InfisicalSecretNotFoundError,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)

# OpenTelemetry tracing (lazy import for optional dependency)
_tracer: Any = None
_tracer_initialized = False


def _get_tracer() -> Any:
    """Get OpenTelemetry tracer, or None if not available."""
    global _tracer, _tracer_initialized
    if not _tracer_initialized:
        _tracer_initialized = True
        try:
            from opentelemetry import trace

            _tracer = trace.get_tracer("floe_secrets_infisical")
        except ImportError:
            _tracer = None  # Mark as unavailable
    return _tracer


class InfisicalSecretsPlugin(SecretsPlugin):
    """Infisical secrets backend plugin.

    This plugin provides access to Infisical as the recommended OSS secrets
    backend for the floe platform. It uses Universal Auth for authentication
    and supports both Infisical Cloud and self-hosted instances.

    Attributes:
        name: Plugin identifier ("infisical").
        version: Plugin version.
        floe_api_version: Required floe API version.
        description: Human-readable description.
        config: Plugin configuration.

    Example:
        >>> from pydantic import SecretStr
        >>> config = InfisicalSecretsConfig(
        ...     client_id="my-client-id",
        ...     client_secret=SecretStr("my-client-secret"),
        ...     project_id="proj_12345",
        ...     environment="production",
        ... )
        >>> plugin = InfisicalSecretsPlugin(config=config)
        >>> plugin.startup()
        >>> password = plugin.get_secret("db-password")
        >>> plugin.shutdown()
    """

    # Class-level metadata for entry point discovery
    name = "infisical"
    version = "0.1.0"
    floe_api_version = "1.0"
    description = "Infisical secrets backend for floe platform"

    def __init__(self, config: InfisicalSecretsConfig) -> None:
        """Initialize the plugin.

        Args:
            config: Plugin configuration with Universal Auth credentials.
        """
        self._config = config
        self._client: Any = None
        self._authenticated = False
        self._audit_logger = AuditLogger()

    @property
    def config(self) -> InfisicalSecretsConfig:
        """Return the plugin configuration."""
        return self._config

    # =========================================================================
    # PluginMetadata Methods
    # =========================================================================

    @classmethod
    def get_config_schema(cls) -> type[BaseModel]:
        """Return the configuration schema.

        Returns:
            InfisicalSecretsConfig Pydantic model class.
        """
        return InfisicalSecretsConfig

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def startup(self) -> None:
        """Initialize and authenticate with Infisical.

        Authenticates using Universal Auth credentials from the configuration.
        Supports both Infisical Cloud and self-hosted instances.

        Raises:
            InfisicalAuthError: If authentication fails.
            InfisicalBackendUnavailableError: If unable to connect to Infisical.
        """
        tracer = _get_tracer()
        span = None
        if tracer:
            span = tracer.start_span("infisical.startup")

        try:
            self._authenticate()
            logger.info(
                "InfisicalSecretsPlugin started",
                extra={
                    "site_url": self._config.site_url,
                    "project_id": self._config.project_id,
                    "environment": self._config.environment,
                    "secret_path": self._config.secret_path,
                },
            )
        except Exception as e:
            if span:
                span.set_status(
                    status=_get_span_status_error(),
                    description=str(e),
                )
            raise
        finally:
            if span:
                span.end()

    def _authenticate(self) -> None:
        """Authenticate with Infisical using Universal Auth.

        Raises:
            InfisicalAuthError: If authentication fails.
            InfisicalBackendUnavailableError: If unable to connect.
        """
        try:
            from infisical_client import (
                AuthenticationOptions,
                ClientSettings,
                InfisicalClient,
                UniversalAuthMethod,
            )

            # Configure Universal Auth
            auth = AuthenticationOptions(
                universal_auth=UniversalAuthMethod(
                    client_id=self._config.client_id,
                    client_secret=self._config.client_secret.get_secret_value(),
                )
            )

            # Create client with site URL for self-hosted support
            settings = ClientSettings(
                site_url=self._config.site_url,
                auth=auth,
            )

            self._client = InfisicalClient(settings=settings)
            self._authenticated = True

        except ImportError as e:
            logger.exception("infisical-python-sdk not installed")
            raise InfisicalBackendUnavailableError(
                site_url=self._config.site_url,
                reason="infisical-python-sdk not installed. Install with: pip install",
            ) from e
        except Exception as e:
            error_str = str(e).lower()
            if "unauthorized" in error_str or "401" in error_str or "auth" in error_str:
                logger.exception("Infisical authentication failed")
                raise InfisicalAuthError(reason=str(e)) from e
            if "connection" in error_str or "timeout" in error_str:
                logger.exception("Failed to connect to Infisical")
                raise InfisicalBackendUnavailableError(
                    site_url=self._config.site_url,
                    reason=str(e),
                ) from e
            logger.exception("Infisical authentication error")
            raise InfisicalAuthError(reason=str(e)) from e

    def shutdown(self) -> None:
        """Clean up resources."""
        self._client = None
        self._authenticated = False
        logger.info("InfisicalSecretsPlugin shutdown complete")

    def health_check(self) -> HealthStatus:
        """Check connectivity to Infisical API.

        Returns:
            HealthStatus indicating current health state.
        """
        if not self._authenticated or self._client is None:
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message="Plugin not initialized - call startup() first",
            )

        try:
            # Try to list secrets to verify connectivity
            self._list_secrets_internal()
            return HealthStatus(
                state=HealthState.HEALTHY,
                message=f"Connected to Infisical at {self._config.site_url}",
            )
        except Exception as e:
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message=f"Infisical health check failed: {e}",
            )

    # =========================================================================
    # SecretsPlugin Methods
    # =========================================================================

    def get_secret(self, key: str) -> str | None:
        """Retrieve a secret value by key.

        Fetches the secret from the configured path and environment in Infisical.

        Args:
            key: Secret key name (e.g., "database-password", "api-key").

        Returns:
            Secret value as string, or None if not found.

        Raises:
            InfisicalAccessDeniedError: If lacking permission to read the secret.
            InfisicalBackendUnavailableError: If unable to connect to Infisical.

        Example:
            >>> plugin.get_secret("db-password")
            'supersecret123'
            >>> plugin.get_secret("nonexistent")
            None
        """
        self._ensure_initialized()

        tracer = _get_tracer()
        span = None
        if tracer:
            span = tracer.start_span(
                "infisical.get_secret",
                attributes={"secret.key": key, "secret.path": self._config.secret_path},
            )

        try:
            from infisical_client import GetSecretOptions
            options = GetSecretOptions(
                secret_name=key,
                project_id=self._config.project_id or "",
                environment=self._config.environment,
                path=self._config.secret_path,
            )

            secret = self._client.getSecret(options)

            if span:
                span.set_attribute("secret.found", True)

            self._audit_logger.log_success(
                requester_id="system",
                secret_path=key,
                operation=AuditOperation.GET,
                plugin_type=self.name,
                namespace=self._config.environment,
                metadata={"found": True, "path": self._config.secret_path},
            )
            # Cast to str since infisical_client returns Any
            return str(secret.secret_value) if secret.secret_value else None

        except Exception as e:
            error_str = str(e).lower()

            # Check for not found
            if "not found" in error_str or "404" in error_str:
                if span:
                    span.set_attribute("secret.found", False)
                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.GET,
                    plugin_type=self.name,
                    namespace=self._config.environment,
                    metadata={"found": False, "path": self._config.secret_path},
                )
                return None

            # Check for access denied
            if "forbidden" in error_str or "403" in error_str or "permission" in error_str:
                if span:
                    span.set_status(_get_span_status_error(), "Access denied")
                self._audit_logger.log_denied(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.GET,
                    reason=str(e),
                    plugin_type=self.name,
                    namespace=self._config.environment,
                )
                raise InfisicalAccessDeniedError(
                    secret_key=key,
                    project_id=self._config.project_id or "",
                    reason=str(e),
                ) from e

            # Connection issues
            if "connection" in error_str or "timeout" in error_str:
                if span:
                    span.set_status(_get_span_status_error(), "Connection error")
                self._audit_logger.log_error(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.GET,
                    error=str(e),
                    plugin_type=self.name,
                    namespace=self._config.environment,
                )
                raise InfisicalBackendUnavailableError(
                    site_url=self._config.site_url,
                    reason=str(e),
                ) from e

            # Treat other errors as not found (per CR-004)
            logger.debug(
                "Secret not found or error retrieving",
                extra={"key": key, "error": str(e)},
            )
            if span:
                span.set_attribute("secret.found", False)
            self._audit_logger.log_success(
                requester_id="system",
                secret_path=key,
                operation=AuditOperation.GET,
                plugin_type=self.name,
                namespace=self._config.environment,
                metadata={"found": False, "path": self._config.secret_path},
            )
            return None

        finally:
            if span:
                span.end()

    def set_secret(
        self, key: str, value: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Store a secret value.

        Creates the secret if it doesn't exist, or updates it if it does.

        Args:
            key: Secret key name.
            value: Secret value to store.
            metadata: Optional metadata (used for secret comment/tags).

        Raises:
            InfisicalAccessDeniedError: If lacking permission to write the secret.
            InfisicalBackendUnavailableError: If unable to connect to Infisical.

        Example:
            >>> plugin.set_secret("db-password", "new-secret-value")
            >>> plugin.set_secret(
            ...     "api-key",
            ...     "new-key-value",
            ...     metadata={"created_by": "floe", "environment": "prod"}
            ... )
        """
        self._ensure_initialized()

        tracer = _get_tracer()
        span = None
        if tracer:
            span = tracer.start_span(
                "infisical.set_secret",
                attributes={"secret.key": key, "secret.path": self._config.secret_path},
            )

        try:
            # Check if secret exists
            existing = self.get_secret(key)

            if existing is not None:
                # Update existing secret
                self._update_secret(key, value, metadata)
                if span:
                    span.set_attribute("secret.operation", "update")
            else:
                # Create new secret
                self._create_secret(key, value, metadata)
                if span:
                    span.set_attribute("secret.operation", "create")

            operation_type = "update" if existing else "create"
            logger.info(
                "Secret stored",
                extra={
                    "key": key,
                    "path": self._config.secret_path,
                    "operation": operation_type,
                },
            )
            self._audit_logger.log_success(
                requester_id="system",
                secret_path=key,
                operation=AuditOperation.SET,
                plugin_type=self.name,
                namespace=self._config.environment,
                metadata={"action": operation_type, "path": self._config.secret_path},
            )

        except (InfisicalAccessDeniedError, InfisicalBackendUnavailableError):
            if span:
                span.set_status(_get_span_status_error(), "Failed to set secret")
            self._audit_logger.log_error(
                requester_id="system",
                secret_path=key,
                operation=AuditOperation.SET,
                error="Access denied or backend unavailable",
                plugin_type=self.name,
                namespace=self._config.environment,
            )
            raise
        except Exception as e:
            if span:
                span.set_status(_get_span_status_error(), str(e))
            error_str = str(e).lower()
            if "forbidden" in error_str or "403" in error_str:
                self._audit_logger.log_denied(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.SET,
                    reason=str(e),
                    plugin_type=self.name,
                    namespace=self._config.environment,
                )
                raise InfisicalAccessDeniedError(
                    secret_key=key,
                    project_id=self._config.project_id or "",
                    reason=str(e),
                ) from e
            self._audit_logger.log_error(
                requester_id="system",
                secret_path=key,
                operation=AuditOperation.SET,
                error=str(e),
                plugin_type=self.name,
                namespace=self._config.environment,
            )
            raise InfisicalBackendUnavailableError(
                site_url=self._config.site_url,
                reason=str(e),
            ) from e
        finally:
            if span:
                span.end()

    def _create_secret(
        self, key: str, value: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Create a new secret in Infisical.

        Args:
            key: Secret key name.
            value: Secret value.
            metadata: Optional metadata.
        """
        from infisical_client import CreateSecretOptions
        comment = ""
        if metadata:
            comment = ", ".join(f"{k}={v}" for k, v in metadata.items())

        options = CreateSecretOptions(
            secret_name=key,
            secret_value=value,
            project_id=self._config.project_id or "",
            environment=self._config.environment,
            path=self._config.secret_path,
            secret_comment=comment if comment else None,
        )

        self._client.createSecret(options)

    def _update_secret(
        self, key: str, value: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Update an existing secret in Infisical.

        Args:
            key: Secret key name.
            value: New secret value.
            metadata: Optional metadata.
        """
        from infisical_client import UpdateSecretOptions
        comment = ""
        if metadata:
            comment = ", ".join(f"{k}={v}" for k, v in metadata.items())

        options = UpdateSecretOptions(
            secret_name=key,
            secret_value=value,
            project_id=self._config.project_id or "",
            environment=self._config.environment,
            path=self._config.secret_path,
            new_secret_comment=comment if comment else None,
        )

        self._client.updateSecret(options)

    def delete_secret(self, key: str) -> None:
        """Delete a secret from Infisical.

        Args:
            key: Secret key name to delete.

        Raises:
            InfisicalSecretNotFoundError: If secret doesn't exist.
            InfisicalAccessDeniedError: If lacking permission.
            InfisicalBackendUnavailableError: If unable to connect.
        """
        self._ensure_initialized()

        tracer = _get_tracer()
        span = None
        if tracer:
            span = tracer.start_span(
                "infisical.delete_secret",
                attributes={"secret.key": key, "secret.path": self._config.secret_path},
            )

        try:
            from infisical_client import DeleteSecretOptions
            options = DeleteSecretOptions(
                secret_name=key,
                project_id=self._config.project_id or "",
                environment=self._config.environment,
                path=self._config.secret_path,
            )

            self._client.deleteSecret(options)
            logger.info("Secret deleted", extra={"key": key})
            self._audit_logger.log_success(
                requester_id="system",
                secret_path=key,
                operation=AuditOperation.DELETE,
                plugin_type=self.name,
                namespace=self._config.environment,
                metadata={"path": self._config.secret_path},
            )

        except Exception as e:
            if span:
                span.set_status(_get_span_status_error(), str(e))
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                self._audit_logger.log_error(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.DELETE,
                    error="Secret not found",
                    plugin_type=self.name,
                    namespace=self._config.environment,
                )
                raise InfisicalSecretNotFoundError(
                    key,
                    path=self._config.secret_path,
                    environment=self._config.environment,
                ) from e
            if "forbidden" in error_str or "403" in error_str:
                self._audit_logger.log_denied(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.DELETE,
                    reason=str(e),
                    plugin_type=self.name,
                    namespace=self._config.environment,
                )
                raise InfisicalAccessDeniedError(
                    secret_key=key,
                    project_id=self._config.project_id or "",
                    reason=str(e),
                ) from e
            self._audit_logger.log_error(
                requester_id="system",
                secret_path=key,
                operation=AuditOperation.DELETE,
                error=str(e),
                plugin_type=self.name,
                namespace=self._config.environment,
            )
            raise InfisicalBackendUnavailableError(
                site_url=self._config.site_url,
                reason=str(e),
            ) from e
        finally:
            if span:
                span.end()

    def list_secrets(self, prefix: str = "") -> list[str]:
        """List available secrets at the configured path.

        Returns a list of secret key names, optionally filtered by prefix.

        Args:
            prefix: Optional prefix to filter secrets.

        Returns:
            List of secret keys matching the prefix.

        Raises:
            InfisicalAccessDeniedError: If lacking permission to list secrets.
            InfisicalBackendUnavailableError: If unable to connect to Infisical.

        Example:
            >>> plugin.list_secrets()
            ['db-password', 'api-key', 'redis-url']
            >>> plugin.list_secrets(prefix="db-")
            ['db-password', 'db-username']
        """
        self._ensure_initialized()

        tracer = _get_tracer()
        span = None
        if tracer:
            span = tracer.start_span(
                "infisical.list_secrets",
                attributes={
                    "secret.path": self._config.secret_path,
                    "secret.prefix": prefix,
                },
            )

        try:
            secrets = self._list_secrets_internal()

            # Filter by prefix if provided
            if prefix:
                secrets = [s for s in secrets if s.startswith(prefix)]

            if span:
                span.set_attribute("secret.count", len(secrets))

            self._audit_logger.log_success(
                requester_id="system",
                secret_path=prefix or "*",
                operation=AuditOperation.LIST,
                plugin_type=self.name,
                namespace=self._config.environment,
                metadata={"count": len(secrets), "path": self._config.secret_path},
            )

            return sorted(secrets)

        except (InfisicalAccessDeniedError, InfisicalBackendUnavailableError):
            if span:
                span.set_status(_get_span_status_error(), "Failed to list secrets")
            self._audit_logger.log_error(
                requester_id="system",
                secret_path=prefix or "*",
                operation=AuditOperation.LIST,
                error="Access denied or backend unavailable",
                plugin_type=self.name,
                namespace=self._config.environment,
            )
            raise
        except Exception as e:
            if span:
                span.set_status(_get_span_status_error(), str(e))
            error_str = str(e).lower()
            if "forbidden" in error_str or "403" in error_str:
                self._audit_logger.log_denied(
                    requester_id="system",
                    secret_path=prefix or "*",
                    operation=AuditOperation.LIST,
                    reason=str(e),
                    plugin_type=self.name,
                    namespace=self._config.environment,
                )
                raise InfisicalAccessDeniedError(
                    project_id=self._config.project_id or "",
                    reason=str(e),
                ) from e
            self._audit_logger.log_error(
                requester_id="system",
                secret_path=prefix or "*",
                operation=AuditOperation.LIST,
                error=str(e),
                plugin_type=self.name,
                namespace=self._config.environment,
            )
            raise InfisicalBackendUnavailableError(
                site_url=self._config.site_url,
                reason=str(e),
            ) from e
        finally:
            if span:
                span.end()

    def _list_secrets_internal(self) -> list[str]:
        """Internal method to list secrets from Infisical.

        Returns:
            List of secret key names.
        """
        from infisical_client import ListSecretsOptions
        options = ListSecretsOptions(
            project_id=self._config.project_id or "",
            environment=self._config.environment,
            path=self._config.secret_path,
        )

        secrets = self._client.listSecrets(options)
        return [s.secret_key for s in secrets]

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _ensure_initialized(self) -> None:
        """Ensure the plugin is initialized.

        Raises:
            InfisicalBackendUnavailableError: If plugin not initialized.
        """
        if not self._authenticated or self._client is None:
            raise InfisicalBackendUnavailableError(
                reason="Plugin not initialized - call startup() first"
            )


def _get_span_status_error() -> Any:
    """Get OpenTelemetry error status code.

    Returns:
        Status code for error, or None if OTel not available.
    """
    try:
        from opentelemetry.trace import StatusCode

        return StatusCode.ERROR
    except ImportError:
        return None


__all__ = ["InfisicalSecretsPlugin"]

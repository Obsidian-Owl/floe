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
import time
from typing import TYPE_CHECKING, Any

from floe_core.audit import AuditLogger, AuditOperation
from floe_core.composition.models import CapabilitySet, PluginCapabilities
from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.secrets import SecretsPlugin
from floe_core.telemetry.sanitization import sanitize_error_message

from floe_secrets_infisical.config import InfisicalSecretsConfig
from floe_secrets_infisical.errors import (
    InfisicalAccessDeniedError,
    InfisicalAuthError,
    InfisicalBackendUnavailableError,
    InfisicalSecretNotFoundError,
)
from floe_secrets_infisical.tracing import (
    ATTR_PATH,
    TRACER_NAME,
    get_tracer,
    record_result,
    secrets_span,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)

_SECRET_REFERENCE_MARKERS = ("secret", "password", "token", "credential", "private_key")
_REDACTED_SECRET_REFERENCE = "<redacted>"


class _ErrorType:
    """Error classification for Infisical API responses."""

    NOT_FOUND = "not_found"
    ACCESS_DENIED = "access_denied"
    UNAVAILABLE = "unavailable"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


def _classify_error(error: Exception) -> str:
    """Classify an exception by its error message pattern.

    Args:
        error: Exception to classify.

    Returns:
        Error type string from _ErrorType constants.
    """
    error_str = str(error).lower()

    if "not found" in error_str or "404" in error_str:
        return _ErrorType.NOT_FOUND

    if (
        "unauthorized" in error_str
        or "forbidden" in error_str
        or "401" in error_str
        or "403" in error_str
        or "permission" in error_str
    ):
        return _ErrorType.ACCESS_DENIED

    if (
        "connection" in error_str
        or "timeout" in error_str
        or "unavailable" in error_str
        or "503" in error_str
    ):
        return _ErrorType.UNAVAILABLE

    if isinstance(error, ValueError) or "validation" in error_str or "400" in error_str:
        return _ErrorType.VALIDATION

    return _ErrorType.UNKNOWN


def _safe_secret_reference_identity(reference: str | None) -> str | None:
    """Return a secret reference only when it is safe operational metadata."""
    if not reference:
        return None
    lowered = reference.lower()
    if any(marker in lowered for marker in _SECRET_REFERENCE_MARKERS):
        return None
    if any(part in lowered for part in ("://", "=", "?", "#", "@")):
        return None
    return reference


def _safe_audit_secret_path(reference: str | None) -> str:
    """Return safe secret identity for audit records."""
    return _safe_secret_reference_identity(reference) or _REDACTED_SECRET_REFERENCE


def _record_secret_span(
    span: Any,
    *,
    operation_type: str,
    outcome: str,
    started_at: float,
    found: bool | None = None,
    count: int | None = None,
    error_type: str | None = None,
) -> None:
    """Attach secret operation metadata without recording secret material."""
    record_result(span, found=found, count=count, operation_type=operation_type)
    span.set_attribute("secrets.outcome", outcome)
    span.set_attribute("secrets.duration_ms", (time.perf_counter() - started_at) * 1000)
    if error_type is not None:
        span.set_attribute("secrets.error_type", error_type)


def _classify_known_secret_error(error: Exception) -> str:
    """Classify plugin-specific known set_secret errors."""
    if isinstance(error, InfisicalAccessDeniedError):
        return _ErrorType.ACCESS_DENIED
    if isinstance(error, InfisicalBackendUnavailableError):
        return _ErrorType.UNAVAILABLE
    return _classify_error(error)


def _safe_error_reason(error: Exception, fallback: str) -> str:
    """Return a non-sensitive reason string for surfaced plugin exceptions."""
    error_str = sanitize_error_message(str(error)).lower()
    for status_code in ("400", "401", "403", "404", "408", "429", "500", "502", "503", "504"):
        if status_code in error_str:
            return f"{fallback} ({status_code})"
    return fallback


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
        super().__init__()
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

    def get_secret_capabilities(self) -> PluginCapabilities:
        """Return Infisical external secret sync capabilities."""
        return PluginCapabilities(
            plugin_type="secrets",
            plugin_name=self.name,
            capabilities=CapabilitySet(
                credential_modes=["external-secret-sync", "kubernetes-secret"],
                secret_projection_modes=["external-secret-sync", "kubernetes-secret"],
                providers=["infisical", "kubernetes"],
            ),
        )

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    @property
    def tracer_name(self) -> str | None:
        """OpenTelemetry tracer name for this plugin.

        Returns:
            The tracer name constant for instrumentation audit.
        """
        return TRACER_NAME

    def startup(self) -> None:
        """Initialize and authenticate with Infisical.

        Authenticates using Universal Auth credentials from the configuration.
        Supports both Infisical Cloud and self-hosted instances.

        Raises:
            InfisicalAuthError: If authentication fails.
            InfisicalBackendUnavailableError: If unable to connect to Infisical.
        """
        tracer = get_tracer()
        with secrets_span(tracer, "startup", provider="infisical"):
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
            logger.error(
                "infisical-python-sdk not installed",
                extra={"error_type": type(e).__name__},
            )
            raise InfisicalBackendUnavailableError(
                reason="infisical-python-sdk not installed. Install with: pip install",
            ) from e
        except Exception as e:
            error_str = str(e).lower()
            if "unauthorized" in error_str or "401" in error_str or "auth" in error_str:
                logger.error(
                    "Infisical authentication failed",
                    extra={"error_type": type(e).__name__},
                )
                raise InfisicalAuthError(
                    reason=_safe_error_reason(e, "authentication failed")
                ) from e
            if "connection" in error_str or "timeout" in error_str:
                logger.error(
                    "Failed to connect to Infisical",
                    extra={"error_type": type(e).__name__},
                )
                raise InfisicalBackendUnavailableError(
                    reason=_safe_error_reason(e, "connection failed"),
                ) from e
            logger.error(
                "Infisical authentication error",
                extra={"error_type": type(e).__name__},
            )
            raise InfisicalAuthError(reason=_safe_error_reason(e, "authentication failed")) from e

    def shutdown(self) -> None:
        """Clean up resources."""
        self._client = None
        self._authenticated = False
        logger.info("InfisicalSecretsPlugin shutdown complete")

    def health_check(self, timeout: float | None = None) -> HealthStatus:
        """Check connectivity to Infisical API.

        Args:
            timeout: Maximum time in seconds to wait for response.
                Not used by this plugin; accepted for base ABC compatibility.

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

        tracer = get_tracer()
        with secrets_span(
            tracer,
            "get_secret",
            provider="infisical",
            key_name=_safe_secret_reference_identity(key),
            extra_attributes={ATTR_PATH: self._config.secret_path},
        ) as span:
            started_at = time.perf_counter()
            try:
                if not key:
                    raise ValueError("Secret reference must not be empty")
                from infisical_client import GetSecretOptions

                options = GetSecretOptions(
                    secret_name=key,
                    project_id=self._config.project_id or "",
                    environment=self._config.environment,
                    path=self._config.secret_path,
                )

                secret = self._client.getSecret(options)

                _record_secret_span(
                    span,
                    operation_type="get",
                    outcome="success",
                    started_at=started_at,
                    found=bool(secret.secret_value),
                )

                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=_safe_audit_secret_path(key),
                    operation=AuditOperation.GET,
                    plugin_type=self.name,
                    namespace=self._config.environment,
                    metadata={"found": True, "path": self._config.secret_path},
                )
                # Cast to str since infisical_client returns Any
                return str(secret.secret_value) if secret.secret_value else None

            except Exception as e:
                error_type = _classify_error(e)
                return self._handle_get_secret_error(e, error_type, key, span, started_at)

    def set_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
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

        tracer = get_tracer()
        with secrets_span(
            tracer,
            "set_secret",
            provider="infisical",
            key_name=_safe_secret_reference_identity(key),
            extra_attributes={ATTR_PATH: self._config.secret_path},
        ) as span:
            started_at = time.perf_counter()
            try:
                if not key:
                    raise ValueError("Secret reference must not be empty")
                operation_type = self._create_or_update_secret(key, value, metadata, span)
                _record_secret_span(
                    span,
                    operation_type=operation_type,
                    outcome="success",
                    started_at=started_at,
                )
                self._log_set_secret_success(key, operation_type)

            except InfisicalAccessDeniedError as e:
                self._log_set_secret_known_error(key, span, started_at, e)
                raise InfisicalAccessDeniedError(
                    secret_key=_safe_audit_secret_path(key),
                    project_id=self._config.project_id or "",
                    reason=_safe_error_reason(e, "access denied"),
                ) from e
            except InfisicalBackendUnavailableError as e:
                self._log_set_secret_known_error(key, span, started_at, e)
                raise InfisicalBackendUnavailableError(
                    reason=_safe_error_reason(e, "backend unavailable"),
                ) from e
            except Exception as e:
                self._handle_set_secret_error(e, key, span, started_at)

    def _create_or_update_secret(
        self,
        key: str,
        value: str,
        metadata: dict[str, Any] | None,
        span: Any,
    ) -> str:
        """Create or update a secret based on existence.

        Args:
            key: Secret key name.
            value: Secret value.
            metadata: Optional metadata.
            span: OpenTelemetry span (may be None).

        Returns:
            Operation type ("create" or "update").
        """
        existing = self.get_secret(key)

        if existing is not None:
            self._update_secret(key, value, metadata)
            if span:
                span.set_attribute("secret.operation", "update")
            return "update"

        self._create_secret(key, value, metadata)
        if span:
            span.set_attribute("secret.operation", "create")
        return "create"

    def _log_set_secret_success(self, key: str, operation_type: str) -> None:
        """Log successful set_secret operation.

        Args:
            key: Secret key.
            operation_type: Operation performed ("create" or "update").
        """
        logger.info(
            "Secret stored",
            extra={
                "key": _safe_audit_secret_path(key),
                "path": self._config.secret_path,
                "operation": operation_type,
            },
        )
        self._audit_logger.log_success(
            requester_id="system",
            secret_path=_safe_audit_secret_path(key),
            operation=AuditOperation.SET,
            plugin_type=self.name,
            namespace=self._config.environment,
            metadata={"action": operation_type, "path": self._config.secret_path},
        )

    def _log_set_secret_known_error(
        self,
        key: str,
        span: Any,
        started_at: float,
        error: InfisicalAccessDeniedError | InfisicalBackendUnavailableError,
    ) -> None:
        """Log known error from set_secret (access denied or unavailable).

        Args:
            key: Secret key.
            span: OpenTelemetry span (may be None).
        """
        # Error status is set by secrets_span context manager on re-raise
        error_type = _classify_known_secret_error(error)
        _record_secret_span(
            span,
            operation_type="set",
            outcome="failure",
            started_at=started_at,
            error_type=error_type,
        )
        if error_type == _ErrorType.ACCESS_DENIED:
            self._audit_logger.log_denied(
                requester_id="system",
                secret_path=_safe_audit_secret_path(key),
                operation=AuditOperation.SET,
                reason="access denied",
                plugin_type=self.name,
                namespace=self._config.environment,
            )
        else:
            self._audit_logger.log_error(
                requester_id="system",
                secret_path=_safe_audit_secret_path(key),
                operation=AuditOperation.SET,
                error="backend unavailable",
                plugin_type=self.name,
                namespace=self._config.environment,
            )

    def _handle_set_secret_error(
        self, e: Exception, key: str, span: Any, started_at: float
    ) -> None:
        """Handle unknown errors from set_secret.

        Args:
            e: The exception that occurred.
            key: Secret key.
            span: OpenTelemetry span (may be None).

        Raises:
            InfisicalAccessDeniedError: If error indicates access denied.
            InfisicalBackendUnavailableError: For all other errors.
        """
        # Error status is set by secrets_span context manager on re-raise
        error_type = _classify_error(e)
        _record_secret_span(
            span,
            operation_type="set",
            outcome="failure",
            started_at=started_at,
            error_type=error_type,
        )
        if error_type == _ErrorType.VALIDATION:
            raise ValueError(_safe_error_reason(e, "validation failed")) from e
        if error_type == _ErrorType.ACCESS_DENIED:
            self._audit_logger.log_denied(
                requester_id="system",
                secret_path=_safe_audit_secret_path(key),
                operation=AuditOperation.SET,
                reason=_safe_error_reason(e, "access denied"),
                plugin_type=self.name,
                namespace=self._config.environment,
            )
            raise InfisicalAccessDeniedError(
                secret_key=_safe_audit_secret_path(key),
                project_id=self._config.project_id or "",
                reason=_safe_error_reason(e, "access denied"),
            ) from e

        self._audit_logger.log_error(
            requester_id="system",
            secret_path=_safe_audit_secret_path(key),
            operation=AuditOperation.SET,
            error=_safe_error_reason(e, "backend unavailable"),
            plugin_type=self.name,
            namespace=self._config.environment,
        )
        raise InfisicalBackendUnavailableError(
            reason=_safe_error_reason(e, "backend unavailable"),
        ) from e

    def _create_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
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

    def _update_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
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

        tracer = get_tracer()
        with secrets_span(
            tracer,
            "delete_secret",
            provider="infisical",
            key_name=_safe_secret_reference_identity(key),
            extra_attributes={ATTR_PATH: self._config.secret_path},
        ) as span:
            started_at = time.perf_counter()
            try:
                if not key:
                    raise ValueError("Secret reference must not be empty")
                from infisical_client import DeleteSecretOptions

                options = DeleteSecretOptions(
                    secret_name=key,
                    project_id=self._config.project_id or "",
                    environment=self._config.environment,
                    path=self._config.secret_path,
                )

                self._client.deleteSecret(options)
                logger.info("Secret deleted", extra={"key": _safe_audit_secret_path(key)})
                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=_safe_audit_secret_path(key),
                    operation=AuditOperation.DELETE,
                    plugin_type=self.name,
                    namespace=self._config.environment,
                    metadata={"path": self._config.secret_path},
                )
                _record_secret_span(
                    span,
                    operation_type="delete",
                    outcome="success",
                    started_at=started_at,
                )

            except Exception as e:
                error_type = _classify_error(e)
                _record_secret_span(
                    span,
                    operation_type="delete",
                    outcome="failure",
                    started_at=started_at,
                    error_type=error_type,
                )
                if error_type == _ErrorType.VALIDATION:
                    raise ValueError(_safe_error_reason(e, "validation failed")) from e
                if error_type == _ErrorType.NOT_FOUND:
                    self._audit_logger.log_error(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(key),
                        operation=AuditOperation.DELETE,
                        error="Secret not found",
                        plugin_type=self.name,
                        namespace=self._config.environment,
                    )
                    raise InfisicalSecretNotFoundError(
                        _safe_audit_secret_path(key),
                        path=self._config.secret_path,
                        environment=self._config.environment,
                    ) from e
                if error_type == _ErrorType.ACCESS_DENIED:
                    self._audit_logger.log_denied(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(key),
                        operation=AuditOperation.DELETE,
                        reason=_safe_error_reason(e, "access denied"),
                        plugin_type=self.name,
                        namespace=self._config.environment,
                    )
                    raise InfisicalAccessDeniedError(
                        secret_key=_safe_audit_secret_path(key),
                        project_id=self._config.project_id or "",
                        reason=_safe_error_reason(e, "access denied"),
                    ) from e
                self._audit_logger.log_error(
                    requester_id="system",
                    secret_path=_safe_audit_secret_path(key),
                    operation=AuditOperation.DELETE,
                    error=_safe_error_reason(e, "backend unavailable"),
                    plugin_type=self.name,
                    namespace=self._config.environment,
                )
                raise InfisicalBackendUnavailableError(
                    reason=_safe_error_reason(e, "backend unavailable"),
                ) from e

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

        tracer = get_tracer()
        with secrets_span(
            tracer,
            "list_secrets",
            provider="infisical",
            extra_attributes={
                ATTR_PATH: self._config.secret_path,
                "secrets.prefix": _safe_secret_reference_identity(prefix) or "",
            },
        ) as span:
            started_at = time.perf_counter()
            try:
                secrets = self._list_secrets_with_filter(prefix)
                self._log_list_secrets_success(prefix, len(secrets), span, started_at)
                return secrets

            except (InfisicalAccessDeniedError, InfisicalBackendUnavailableError):
                self._log_list_secrets_known_error(prefix, span, started_at)
                raise
            except Exception as e:
                self._handle_list_secrets_error(e, prefix, span, started_at)

    def _list_secrets_with_filter(self, prefix: str) -> list[str]:
        """List secrets and filter by prefix.

        Args:
            prefix: Optional prefix to filter secrets.

        Returns:
            Sorted list of secret keys matching the prefix.
        """
        secrets = self._list_secrets_internal()
        if prefix:
            secrets = [s for s in secrets if s.startswith(prefix)]
        return sorted(secrets)

    def _log_list_secrets_success(
        self, prefix: str, count: int, span: Any, started_at: float
    ) -> None:
        """Log successful list_secrets operation.

        Args:
            prefix: Filter prefix used.
            count: Number of secrets found.
            span: OpenTelemetry span (may be None).
        """
        _record_secret_span(
            span,
            operation_type="list",
            outcome="success",
            started_at=started_at,
            count=count,
        )

        self._audit_logger.log_success(
            requester_id="system",
            secret_path=_safe_audit_secret_path(prefix) if prefix else "*",
            operation=AuditOperation.LIST,
            plugin_type=self.name,
            namespace=self._config.environment,
            metadata={"count": count, "path": self._config.secret_path},
        )

    def _log_list_secrets_known_error(self, prefix: str, span: Any, started_at: float) -> None:
        """Log known error from list_secrets (access denied or unavailable).

        Args:
            prefix: Filter prefix used.
            span: OpenTelemetry span (may be None).
        """
        # Error status is set by secrets_span context manager on re-raise
        _record_secret_span(
            span,
            operation_type="list",
            outcome="failure",
            started_at=started_at,
            error_type=_ErrorType.UNAVAILABLE,
        )
        self._audit_logger.log_error(
            requester_id="system",
            secret_path=_safe_audit_secret_path(prefix) if prefix else "*",
            operation=AuditOperation.LIST,
            error="Access denied or backend unavailable",
            plugin_type=self.name,
            namespace=self._config.environment,
        )

    def _handle_list_secrets_error(
        self, e: Exception, prefix: str, span: Any, started_at: float
    ) -> None:
        """Handle unknown errors from list_secrets.

        Args:
            e: The exception that occurred.
            prefix: Filter prefix used.
            span: OpenTelemetry span (may be None).

        Raises:
            InfisicalAccessDeniedError: If error indicates access denied.
            InfisicalBackendUnavailableError: For all other errors.
        """
        # Error status is set by secrets_span context manager on re-raise
        error_type = _classify_error(e)
        _record_secret_span(
            span,
            operation_type="list",
            outcome="failure",
            started_at=started_at,
            error_type=error_type,
        )
        if error_type == _ErrorType.VALIDATION:
            raise ValueError(_safe_error_reason(e, "validation failed")) from e
        if error_type == _ErrorType.ACCESS_DENIED:
            self._audit_logger.log_denied(
                requester_id="system",
                secret_path=_safe_audit_secret_path(prefix) if prefix else "*",
                operation=AuditOperation.LIST,
                reason=_safe_error_reason(e, "access denied"),
                plugin_type=self.name,
                namespace=self._config.environment,
            )
            raise InfisicalAccessDeniedError(
                project_id=self._config.project_id or "",
                reason=_safe_error_reason(e, "access denied"),
            ) from e

        self._audit_logger.log_error(
            requester_id="system",
            secret_path=_safe_audit_secret_path(prefix) if prefix else "*",
            operation=AuditOperation.LIST,
            error=_safe_error_reason(e, "backend unavailable"),
            plugin_type=self.name,
            namespace=self._config.environment,
        )
        raise InfisicalBackendUnavailableError(
            reason=_safe_error_reason(e, "backend unavailable"),
        ) from e

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

    def _handle_get_secret_error(
        self,
        e: Exception,
        error_type: str,
        key: str,
        span: Any,
        started_at: float,
    ) -> str | None:
        """Handle errors from get_secret operation.

        Args:
            e: The exception that occurred.
            error_type: Classified error type from _classify_error.
            key: Secret key that was being retrieved.
            span: OpenTelemetry span (may be None).

        Returns:
            None for not-found cases (secret not found is not an error).

        Raises:
            InfisicalAccessDeniedError: If access was denied.
            InfisicalBackendUnavailableError: If connection failed.
        """
        if error_type == _ErrorType.NOT_FOUND:
            _record_secret_span(
                span,
                operation_type="get",
                outcome="failure",
                started_at=started_at,
                found=False,
                error_type=error_type,
            )
            self._audit_logger.log_success(
                requester_id="system",
                secret_path=_safe_audit_secret_path(key),
                operation=AuditOperation.GET,
                plugin_type=self.name,
                namespace=self._config.environment,
                metadata={"found": False, "path": self._config.secret_path},
            )
            return None

        if error_type == _ErrorType.ACCESS_DENIED:
            # Error status is set by secrets_span context manager on re-raise
            _record_secret_span(
                span,
                operation_type="get",
                outcome="failure",
                started_at=started_at,
                error_type=error_type,
            )
            self._audit_logger.log_denied(
                requester_id="system",
                secret_path=_safe_audit_secret_path(key),
                operation=AuditOperation.GET,
                reason=_safe_error_reason(e, "access denied"),
                plugin_type=self.name,
                namespace=self._config.environment,
            )
            raise InfisicalAccessDeniedError(
                secret_key=_safe_audit_secret_path(key),
                project_id=self._config.project_id or "",
                reason=_safe_error_reason(e, "access denied"),
            ) from e

        if error_type == _ErrorType.UNAVAILABLE:
            # Error status is set by secrets_span context manager on re-raise
            _record_secret_span(
                span,
                operation_type="get",
                outcome="failure",
                started_at=started_at,
                error_type=error_type,
            )
            self._audit_logger.log_error(
                requester_id="system",
                secret_path=_safe_audit_secret_path(key),
                operation=AuditOperation.GET,
                error=_safe_error_reason(e, "backend unavailable"),
                plugin_type=self.name,
                namespace=self._config.environment,
            )
            raise InfisicalBackendUnavailableError(
                reason=_safe_error_reason(e, "backend unavailable"),
            ) from e

        if error_type == _ErrorType.VALIDATION:
            _record_secret_span(
                span,
                operation_type="get",
                outcome="failure",
                started_at=started_at,
                error_type=error_type,
            )
            raise ValueError(_safe_error_reason(e, "validation failed")) from e

        # UNKNOWN error - treat as not found (per CR-004)
        logger.debug(
            "Secret not found or error retrieving",
            extra={
                "key": _safe_audit_secret_path(key),
                "error_type": _classify_error(e),
            },
        )
        _record_secret_span(
            span,
            operation_type="get",
            outcome="failure",
            started_at=started_at,
            found=False,
            error_type=error_type,
        )
        self._audit_logger.log_success(
            requester_id="system",
            secret_path=_safe_audit_secret_path(key),
            operation=AuditOperation.GET,
            plugin_type=self.name,
            namespace=self._config.environment,
            metadata={"found": False, "path": self._config.secret_path},
        )
        return None


__all__ = ["InfisicalSecretsPlugin"]

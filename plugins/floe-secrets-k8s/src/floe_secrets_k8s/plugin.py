"""K8sSecretsPlugin implementation.

This module provides the K8sSecretsPlugin class for accessing Kubernetes Secrets
as the default secrets backend for the floe platform.

Implements:
    - FR-010: K8sSecretsPlugin as default secrets backend
    - FR-011: Namespace-scoped secret access
    - FR-012: Pod spec generation for envFrom injection
    - FR-013: In-cluster and kubeconfig authentication

Example:
    >>> from floe_secrets_k8s import K8sSecretsPlugin, K8sSecretsConfig
    >>> config = K8sSecretsConfig(namespace="floe-jobs")
    >>> plugin = K8sSecretsPlugin(config)
    >>> secret = plugin.get_secret("database-password")
"""

from __future__ import annotations

import base64
import logging
import time
from typing import TYPE_CHECKING, Any

from floe_core.audit import AuditLogger, AuditOperation
from floe_core.composition.models import CapabilitySet, PluginCapabilities
from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.secrets import SecretsPlugin
from floe_core.telemetry.sanitization import sanitize_error_message

from floe_secrets_k8s.config import K8sSecretsConfig
from floe_secrets_k8s.errors import (
    SecretAccessDeniedError,
    SecretBackendUnavailableError,
)
from floe_secrets_k8s.tracing import get_tracer, secrets_span

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)

_SECRET_REFERENCE_MARKERS = ("secret", "password", "token", "credential", "private_key")
_REDACTED_SECRET_REFERENCE = "<redacted>"


class _ErrorType:
    ACCESS_DENIED = "access_denied"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


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


def _classify_k8s_error(error: Exception) -> str:
    """Classify Kubernetes secret backend errors for low-cardinality telemetry."""
    status = getattr(error, "status", None)
    error_str = str(error).lower()
    if status in {401, 403} or any(
        marker in error_str for marker in ("401", "403", "unauthorized", "forbidden", "permission")
    ):
        return _ErrorType.ACCESS_DENIED
    if status == 404 or "404" in error_str or "not found" in error_str:
        return _ErrorType.NOT_FOUND
    if status in {408, 429, 500, 502, 503, 504} or any(
        marker in error_str
        for marker in (
            "408",
            "429",
            "500",
            "502",
            "503",
            "504",
            "connection",
            "timeout",
            "unavailable",
        )
    ):
        return _ErrorType.UNAVAILABLE
    if isinstance(error, ValueError) or "400" in error_str or "validation" in error_str:
        return _ErrorType.VALIDATION
    return _ErrorType.UNKNOWN


def _safe_audit_secret_path(reference: str | None) -> str:
    """Return safe secret identity for audit records."""
    return _safe_secret_reference_identity(reference) or _REDACTED_SECRET_REFERENCE


def _safe_error_reason(error: Exception, fallback: str) -> str:
    """Return a sanitized, low-cardinality error reason for public/audit paths."""
    status = getattr(error, "status", None)
    if status in {400, 401, 403, 404, 408, 429, 500, 502, 503, 504}:
        return f"{fallback} ({status})"
    sanitized = sanitize_error_message(str(error)).lower()
    for status_code in ("400", "401", "403", "404", "408", "429", "500", "502", "503", "504"):
        if status_code in sanitized:
            return f"{fallback} ({status_code})"
    return fallback


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
    span.set_attribute("secrets.operation_type", operation_type)
    span.set_attribute("secrets.outcome", outcome)
    span.set_attribute("secrets.duration_ms", (time.perf_counter() - started_at) * 1000)
    if found is not None:
        span.set_attribute("secrets.found", found)
    if count is not None:
        span.set_attribute("secrets.count", count)
    if error_type is not None:
        span.set_attribute("secrets.error_type", error_type)


class K8sSecretsPlugin(SecretsPlugin):
    """Kubernetes Secrets backend plugin.

    This plugin provides access to Kubernetes Secrets as the default secrets
    backend for the floe platform. It supports both in-cluster authentication
    (when running inside K8s) and kubeconfig-based authentication (for local
    development).

    Attributes:
        config: Plugin configuration.

    Example:
        >>> config = K8sSecretsConfig(namespace="production")
        >>> plugin = K8sSecretsPlugin(config)
        >>> plugin.startup()
        >>> password = plugin.get_secret("db-password")
        >>> plugin.shutdown()
    """

    def __init__(self, config: K8sSecretsConfig | None = None) -> None:
        """Initialize the plugin.

        Args:
            config: Plugin configuration. Uses defaults if None.
        """
        super().__init__()
        self._config = config or K8sSecretsConfig()
        self.config = self._config
        self._client: Any = None
        self._api: Any = None
        self._audit_logger = AuditLogger()

    def configure(self, config: BaseModel | None) -> None:
        """Override to keep self.config in sync with self._config.

        The ABC's configure() only updates self._config. This plugin
        exposes self.config as the public attribute (~60 call sites),
        so both must stay synchronized.

        Args:
            config: Validated plugin configuration, or None to reset.
        """
        super().configure(config)
        self.config = self._config

    @property
    def namespace(self) -> str:
        """Return the configured namespace for audit logging."""
        return self.config.namespace

    # =========================================================================
    # PluginMetadata Properties
    # =========================================================================

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "k8s"

    @property
    def version(self) -> str:
        """Return the plugin version."""
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Return the required floe API version."""
        return "1.0"

    @property
    def description(self) -> str:
        """Return the plugin description."""
        return "Kubernetes Secrets backend for floe platform"

    @property
    def tracer_name(self) -> str | None:
        """OpenTelemetry tracer name for this plugin.

        Override to report instrumentation status to the audit system.

        Returns:
            Tracer name string for the K8s secrets plugin.
        """
        return "floe.secrets.k8s"

    def get_config_schema(self) -> type[BaseModel]:
        """Return the configuration schema."""
        return K8sSecretsConfig

    def get_secret_capabilities(self) -> PluginCapabilities:
        """Return Kubernetes Secret projection capabilities."""
        return PluginCapabilities(
            plugin_type="secrets",
            plugin_name=self.name,
            capabilities=CapabilitySet(
                credential_modes=["kubernetes-secret"],
                secret_projection_modes=["kubernetes-secret"],
                providers=["kubernetes"],
            ),
        )

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def startup(self) -> None:
        """Initialize the Kubernetes client.

        Attempts to load configuration in this order:
        1. Explicit kubeconfig path from config
        2. In-cluster configuration
        3. Default kubeconfig (~/.kube/config)

        Raises:
            SecretBackendUnavailableError: If unable to connect to K8s API.
        """
        try:
            from kubernetes import client
            from kubernetes import config as k8s_config

            if self.config.kubeconfig_path:
                # Use explicit kubeconfig
                k8s_config.load_kube_config(
                    config_file=self.config.kubeconfig_path,
                    context=self.config.context,
                )
                logger.info(
                    "Loaded kubeconfig",
                    extra={
                        "kubeconfig_path": self.config.kubeconfig_path,
                        "context": self.config.context,
                    },
                )
            else:
                # Try in-cluster first, fall back to default kubeconfig
                try:
                    k8s_config.load_incluster_config()
                    logger.info("Loaded in-cluster configuration")
                except k8s_config.ConfigException:
                    k8s_config.load_kube_config(context=self.config.context)
                    logger.info(
                        "Loaded default kubeconfig",
                        extra={"context": self.config.context},
                    )

            self._client = client
            self._api = client.CoreV1Api()

        except Exception as e:
            error_type = _classify_k8s_error(e)
            if error_type == _ErrorType.UNKNOWN:
                error_type = _ErrorType.UNAVAILABLE
            logger.error(
                "Failed to initialize Kubernetes client",
                extra={
                    "error_type": error_type,
                    "error_message": _safe_error_reason(e, "backend unavailable"),
                },
            )
            raise SecretBackendUnavailableError(
                reason=_safe_error_reason(e, "backend unavailable")
            ) from e

    def shutdown(self) -> None:
        """Clean up resources."""
        self._client = None
        self._api = None
        logger.info("K8sSecretsPlugin shutdown complete")

    def health_check(self, timeout: float | None = None) -> HealthStatus:
        """Check connectivity to Kubernetes API.

        Args:
            timeout: Optional timeout in seconds (unused, reserved for base ABC).

        Returns:
            HealthStatus indicating current health state.
        """
        tracer = get_tracer()
        with secrets_span(tracer, "health_check", provider="k8s"):
            if self._api is None:
                return HealthStatus(
                    state=HealthState.UNHEALTHY,
                    message="Plugin not initialized - call startup() first",
                )

            try:
                # Try to list secrets to verify connectivity and permissions
                self._api.list_namespaced_secret(
                    namespace=self.config.namespace,
                    limit=1,
                )
                return HealthStatus(
                    state=HealthState.HEALTHY,
                    message=f"Connected to K8s API, namespace: {self.config.namespace}",
                )
            except Exception as e:
                error_type = _classify_k8s_error(e)
                return HealthStatus(
                    state=HealthState.UNHEALTHY,
                    message=f"K8s API check failed: {error_type}",
                )

    # =========================================================================
    # SecretsPlugin Methods
    # =========================================================================

    def get_secret(self, key: str) -> str | None:
        """Retrieve a secret value by key.

        The key format is either:
        - "secret-name" - retrieves the "value" key from the secret
        - "secret-name/key" - retrieves a specific key from the secret

        Args:
            key: Secret key in format "secret-name" or "secret-name/key".

        Returns:
            Secret value as string, or None if not found.

        Raises:
            SecretAccessDeniedError: If lacking permission to read the secret.
            SecretBackendUnavailableError: If unable to connect to K8s API.
        """
        tracer = get_tracer()
        with secrets_span(
            tracer,
            "get_secret",
            provider="k8s",
            key_name=_safe_secret_reference_identity(key),
            namespace=self.config.namespace,
        ) as span:
            started_at = time.perf_counter()
            try:
                self._ensure_initialized()
                secret_name, secret_key = self._parse_key(key)
                secret = self._api.read_namespaced_secret(
                    name=secret_name,
                    namespace=self.config.namespace,
                )

                if secret.data is None:
                    self._audit_logger.log_success(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(key),
                        operation=AuditOperation.GET,
                        plugin_type=self.name,
                        namespace=self.config.namespace,
                        metadata={"found": False},
                    )
                    _record_secret_span(
                        span,
                        operation_type="get",
                        outcome="success",
                        started_at=started_at,
                        found=False,
                    )
                    return None

                if secret_key not in secret.data:
                    self._audit_logger.log_success(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(key),
                        operation=AuditOperation.GET,
                        plugin_type=self.name,
                        namespace=self.config.namespace,
                        metadata={"found": False},
                    )
                    _record_secret_span(
                        span,
                        operation_type="get",
                        outcome="success",
                        started_at=started_at,
                        found=False,
                    )
                    return None

                # K8s secrets are base64 encoded
                encoded_value = secret.data[secret_key]
                result = base64.b64decode(encoded_value).decode("utf-8")

                # Log successful access
                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=_safe_audit_secret_path(key),
                    operation=AuditOperation.GET,
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                    metadata={"found": True},
                )
                _record_secret_span(
                    span,
                    operation_type="get",
                    outcome="success",
                    started_at=started_at,
                    found=True,
                )

                return result

            except SecretBackendUnavailableError:
                _record_secret_span(
                    span,
                    operation_type="get",
                    outcome="failure",
                    started_at=started_at,
                    error_type=_ErrorType.UNAVAILABLE,
                )
                raise
            except self._client.rest.ApiException as e:
                error_type = _classify_k8s_error(e)
                if e.status == 404:
                    self._audit_logger.log_success(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(key),
                        operation=AuditOperation.GET,
                        plugin_type=self.name,
                        namespace=self.config.namespace,
                        metadata={"found": False},
                    )
                    _record_secret_span(
                        span,
                        operation_type="get",
                        outcome="failure",
                        started_at=started_at,
                        found=False,
                        error_type=error_type,
                    )
                    return None
                if error_type == _ErrorType.ACCESS_DENIED:
                    self._audit_logger.log_denied(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(key),
                        operation=AuditOperation.GET,
                        reason=_safe_error_reason(e, "access denied"),
                        plugin_type=self.name,
                        namespace=self.config.namespace,
                    )
                    _record_secret_span(
                        span,
                        operation_type="get",
                        outcome="failure",
                        started_at=started_at,
                        error_type=error_type,
                    )
                    raise SecretAccessDeniedError(
                        _safe_audit_secret_path(secret_name),
                        namespace=self.config.namespace,
                        reason=_safe_error_reason(e, "access denied"),
                    ) from e
                self._audit_logger.log_error(
                    requester_id="system",
                    secret_path=_safe_audit_secret_path(key),
                    operation=AuditOperation.GET,
                    error=_safe_error_reason(e, "backend unavailable"),
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                )
                _record_secret_span(
                    span,
                    operation_type="get",
                    outcome="failure",
                    started_at=started_at,
                    error_type=error_type,
                )
                raise SecretBackendUnavailableError(
                    reason=_safe_error_reason(e, "backend unavailable")
                ) from e
            except ValueError as e:
                _record_secret_span(
                    span,
                    operation_type="get",
                    outcome="failure",
                    started_at=started_at,
                    error_type=_classify_k8s_error(e),
                )
                raise

    def set_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
        """Store a secret value.

        Creates the secret if it doesn't exist, or updates it if it does.
        The key format is either:
        - "secret-name" - stores value under the "value" key
        - "secret-name/key" - stores value under the specified key

        Args:
            key: Secret key in format "secret-name" or "secret-name/key".
            value: Secret value to store.
            metadata: Optional metadata (stored as annotations).

        Raises:
            SecretAccessDeniedError: If lacking permission to write the secret.
            SecretBackendUnavailableError: If unable to connect to K8s API.
        """
        tracer = get_tracer()
        with secrets_span(
            tracer,
            "set_secret",
            provider="k8s",
            key_name=_safe_secret_reference_identity(key),
            namespace=self.config.namespace,
        ) as span:
            started_at = time.perf_counter()
            try:
                self._ensure_initialized()
                secret_name, secret_key = self._parse_key(key)

                encoded_value = base64.b64encode(value.encode("utf-8")).decode("utf-8")

                labels = dict(self.config.labels)
                annotations: dict[str, str] = {}
                if metadata:
                    for k, v in metadata.items():
                        annotations[f"floe.dev/{k}"] = str(v)

                # Try to read existing secret
                try:
                    existing = self._api.read_namespaced_secret(
                        name=secret_name,
                        namespace=self.config.namespace,
                    )
                    # Update existing secret
                    if existing.data is None:
                        existing.data = {}
                    existing.data[secret_key] = encoded_value

                    # Merge labels and annotations
                    self._merge_labels_and_annotations(existing.metadata, labels, annotations)

                    self._api.replace_namespaced_secret(
                        name=secret_name,
                        namespace=self.config.namespace,
                        body=existing,
                    )
                    logger.info(
                        "Updated secret",
                        extra={
                            "secret_name": _safe_audit_secret_path(secret_name),
                            "key": _safe_audit_secret_path(secret_key),
                        },
                    )
                    self._audit_logger.log_success(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(key),
                        operation=AuditOperation.SET,
                        plugin_type=self.name,
                        namespace=self.config.namespace,
                        metadata={"action": "updated"},
                    )
                    _record_secret_span(
                        span,
                        operation_type="update",
                        outcome="success",
                        started_at=started_at,
                    )

                except self._client.rest.ApiException as e:
                    if e.status != 404:
                        raise

                    # Create new secret
                    secret_body = self._client.V1Secret(
                        metadata=self._client.V1ObjectMeta(
                            name=secret_name,
                            namespace=self.config.namespace,
                            labels=labels,
                            annotations=annotations if annotations else None,
                        ),
                        data={secret_key: encoded_value},
                        type="Opaque",
                    )
                    self._api.create_namespaced_secret(
                        namespace=self.config.namespace,
                        body=secret_body,
                    )
                    logger.info(
                        "Created secret",
                        extra={
                            "secret_name": _safe_audit_secret_path(secret_name),
                            "key": _safe_audit_secret_path(secret_key),
                        },
                    )
                    self._audit_logger.log_success(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(key),
                        operation=AuditOperation.SET,
                        plugin_type=self.name,
                        namespace=self.config.namespace,
                        metadata={"action": "created"},
                    )
                    _record_secret_span(
                        span,
                        operation_type="create",
                        outcome="success",
                        started_at=started_at,
                    )

            except SecretBackendUnavailableError:
                _record_secret_span(
                    span,
                    operation_type="set",
                    outcome="failure",
                    started_at=started_at,
                    error_type=_ErrorType.UNAVAILABLE,
                )
                raise
            except self._client.rest.ApiException as e:
                error_type = _classify_k8s_error(e)
                if error_type == _ErrorType.ACCESS_DENIED:
                    self._audit_logger.log_denied(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(key),
                        operation=AuditOperation.SET,
                        reason=_safe_error_reason(e, "access denied"),
                        plugin_type=self.name,
                        namespace=self.config.namespace,
                    )
                    _record_secret_span(
                        span,
                        operation_type="set",
                        outcome="failure",
                        started_at=started_at,
                        error_type=error_type,
                    )
                    raise SecretAccessDeniedError(
                        _safe_audit_secret_path(secret_name),
                        namespace=self.config.namespace,
                        reason=_safe_error_reason(e, "access denied"),
                    ) from e
                self._audit_logger.log_error(
                    requester_id="system",
                    secret_path=_safe_audit_secret_path(key),
                    operation=AuditOperation.SET,
                    error=_safe_error_reason(e, "backend unavailable"),
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                )
                _record_secret_span(
                    span,
                    operation_type="set",
                    outcome="failure",
                    started_at=started_at,
                    error_type=error_type,
                )
                raise SecretBackendUnavailableError(
                    reason=_safe_error_reason(e, "backend unavailable")
                ) from e
            except ValueError as e:
                _record_secret_span(
                    span,
                    operation_type="set",
                    outcome="failure",
                    started_at=started_at,
                    error_type=_classify_k8s_error(e),
                )
                raise

    def list_secrets(self, prefix: str = "") -> list[str]:
        """List available secrets.

        Returns a list of secret keys in "secret-name/key" format.

        Args:
            prefix: Optional prefix to filter secrets.

        Returns:
            List of secret keys matching the prefix.

        Raises:
            SecretAccessDeniedError: If lacking permission to list secrets.
            SecretBackendUnavailableError: If unable to connect to K8s API.
        """
        tracer = get_tracer()
        with secrets_span(
            tracer,
            "list_secrets",
            provider="k8s",
            namespace=self.config.namespace,
        ) as span:
            started_at = time.perf_counter()
            try:
                self._ensure_initialized()
                # List secrets with our managed-by label
                label_selector = ",".join(f"{k}={v}" for k, v in self.config.labels.items())

                secrets = self._api.list_namespaced_secret(
                    namespace=self.config.namespace,
                    label_selector=label_selector if self.config.labels else None,
                )

                result: list[str] = []
                for secret in secrets.items:
                    if secret.data is None:
                        continue

                    secret_name = secret.metadata.name
                    for key in secret.data:
                        full_key = f"{secret_name}/{key}"
                        if prefix and not full_key.startswith(prefix):
                            continue
                        result.append(full_key)

                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=_safe_audit_secret_path(prefix) if prefix else "*",
                    operation=AuditOperation.LIST,
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                    metadata={"count": len(result)},
                )
                _record_secret_span(
                    span,
                    operation_type="list",
                    outcome="success",
                    started_at=started_at,
                    count=len(result),
                )

                return sorted(result)

            except SecretBackendUnavailableError:
                _record_secret_span(
                    span,
                    operation_type="list",
                    outcome="failure",
                    started_at=started_at,
                    error_type=_ErrorType.UNAVAILABLE,
                )
                raise
            except self._client.rest.ApiException as e:
                error_type = _classify_k8s_error(e)
                if error_type == _ErrorType.ACCESS_DENIED:
                    self._audit_logger.log_denied(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(prefix) if prefix else "*",
                        operation=AuditOperation.LIST,
                        reason=_safe_error_reason(e, "access denied"),
                        plugin_type=self.name,
                        namespace=self.config.namespace,
                    )
                    _record_secret_span(
                        span,
                        operation_type="list",
                        outcome="failure",
                        started_at=started_at,
                        error_type=error_type,
                    )
                    raise SecretAccessDeniedError(
                        "",
                        namespace=self.config.namespace,
                        reason=_safe_error_reason(e, "access denied"),
                    ) from e
                self._audit_logger.log_error(
                    requester_id="system",
                    secret_path=_safe_audit_secret_path(prefix) if prefix else "*",
                    operation=AuditOperation.LIST,
                    error=_safe_error_reason(e, "backend unavailable"),
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                )
                _record_secret_span(
                    span,
                    operation_type="list",
                    outcome="failure",
                    started_at=started_at,
                    error_type=error_type,
                )
                raise SecretBackendUnavailableError(
                    reason=_safe_error_reason(e, "backend unavailable")
                ) from e

    def generate_pod_env_spec(self, secret_name: str) -> dict[str, Any]:
        """Generate K8s pod spec fragment for secret injection.

        Returns a partial pod spec that injects all keys from the specified
        secret as environment variables using envFrom.

        Args:
            secret_name: K8s Secret name to mount.

        Returns:
            Pod spec fragment with envFrom configuration.

        Example:
            >>> spec = plugin.generate_pod_env_spec("db-creds")
            >>> spec
            {'envFrom': [{'secretRef': {'name': 'db-creds'}}]}
        """
        return {"envFrom": [{"secretRef": {"name": secret_name}}]}

    def get_multi_key_secret(self, name: str) -> dict[str, str]:
        """Retrieve all key-value pairs from a K8s Secret.

        K8s Secrets natively support multiple keys, so this method is
        fully implemented for this plugin.

        Args:
            name: Secret name.

        Returns:
            Dictionary of key-value pairs from the secret.

        Raises:
            SecretAccessDeniedError: If lacking permission to read the secret.
            SecretBackendUnavailableError: If unable to connect to K8s API.
        """
        tracer = get_tracer()
        with secrets_span(
            tracer,
            "get_multi_key_secret",
            provider="k8s",
            key_name=_safe_secret_reference_identity(name),
            namespace=self.config.namespace,
        ) as span:
            started_at = time.perf_counter()
            try:
                self._ensure_initialized()
                secret = self._api.read_namespaced_secret(
                    name=name,
                    namespace=self.config.namespace,
                )

                if secret.data is None:
                    self._audit_logger.log_success(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(name),
                        operation=AuditOperation.GET,
                        plugin_type=self.name,
                        namespace=self.config.namespace,
                        metadata={"found": False, "multi_key": True},
                    )
                    _record_secret_span(
                        span,
                        operation_type="get_multi",
                        outcome="success",
                        started_at=started_at,
                        found=False,
                        count=0,
                    )
                    return {}

                result: dict[str, str] = {}
                for key, encoded_value in secret.data.items():
                    result[key] = base64.b64decode(encoded_value).decode("utf-8")

                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=_safe_audit_secret_path(name),
                    operation=AuditOperation.GET,
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                    metadata={"found": True, "multi_key": True, "key_count": len(result)},
                )
                _record_secret_span(
                    span,
                    operation_type="get_multi",
                    outcome="success",
                    started_at=started_at,
                    found=True,
                    count=len(result),
                )
                return result

            except SecretBackendUnavailableError:
                _record_secret_span(
                    span,
                    operation_type="get_multi",
                    outcome="failure",
                    started_at=started_at,
                    error_type=_ErrorType.UNAVAILABLE,
                )
                raise
            except self._client.rest.ApiException as e:
                error_type = _classify_k8s_error(e)
                if e.status == 404:
                    self._audit_logger.log_success(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(name),
                        operation=AuditOperation.GET,
                        plugin_type=self.name,
                        namespace=self.config.namespace,
                        metadata={"found": False, "multi_key": True},
                    )
                    _record_secret_span(
                        span,
                        operation_type="get_multi",
                        outcome="failure",
                        started_at=started_at,
                        found=False,
                        count=0,
                        error_type=error_type,
                    )
                    return {}
                if error_type == _ErrorType.ACCESS_DENIED:
                    self._audit_logger.log_denied(
                        requester_id="system",
                        secret_path=_safe_audit_secret_path(name),
                        operation=AuditOperation.GET,
                        reason=_safe_error_reason(e, "access denied"),
                        plugin_type=self.name,
                        namespace=self.config.namespace,
                    )
                    _record_secret_span(
                        span,
                        operation_type="get_multi",
                        outcome="failure",
                        started_at=started_at,
                        error_type=error_type,
                    )
                    raise SecretAccessDeniedError(
                        _safe_audit_secret_path(name),
                        namespace=self.config.namespace,
                        reason=_safe_error_reason(e, "access denied"),
                    ) from e
                self._audit_logger.log_error(
                    requester_id="system",
                    secret_path=_safe_audit_secret_path(name),
                    operation=AuditOperation.GET,
                    error=_safe_error_reason(e, "backend unavailable"),
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                )
                _record_secret_span(
                    span,
                    operation_type="get_multi",
                    outcome="failure",
                    started_at=started_at,
                    error_type=error_type,
                )
                raise SecretBackendUnavailableError(
                    reason=_safe_error_reason(e, "backend unavailable")
                ) from e
            except ValueError as e:
                _record_secret_span(
                    span,
                    operation_type="get_multi",
                    outcome="failure",
                    started_at=started_at,
                    error_type=_classify_k8s_error(e),
                )
                raise

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _ensure_initialized(self) -> None:
        """Ensure the plugin is initialized.

        Raises:
            SecretBackendUnavailableError: If plugin not initialized.
        """
        if self._api is None:
            raise SecretBackendUnavailableError(
                reason="Plugin not initialized - call startup() first"
            )

    def _parse_key(self, key: str) -> tuple[str, str]:
        """Parse a key into secret name and key.

        Args:
            key: Key in format "secret-name" or "secret-name/key".

        Returns:
            Tuple of (secret_name, secret_key).
        """
        if not key:
            raise ValueError("Secret reference must not be empty")
        if "/" in key:
            parts = key.split("/", 1)
            if not parts[0] or not parts[1]:
                raise ValueError("Secret reference must include name and key")
            return parts[0], parts[1]
        return key, "value"

    def _merge_labels_and_annotations(
        self,
        existing_metadata: Any,
        labels: dict[str, str],
        annotations: dict[str, str],
    ) -> None:
        """Merge labels and annotations into existing secret metadata.

        Args:
            existing_metadata: V1ObjectMeta from existing secret.
            labels: Labels to merge.
            annotations: Annotations to merge.
        """
        if existing_metadata.labels:
            existing_metadata.labels.update(labels)
        else:
            existing_metadata.labels = labels

        if annotations:
            if existing_metadata.annotations:
                existing_metadata.annotations.update(annotations)
            else:
                existing_metadata.annotations = annotations


__all__ = ["K8sSecretsPlugin"]

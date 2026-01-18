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
from typing import TYPE_CHECKING, Any

from floe_core.audit import AuditLogger, AuditOperation
from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.secrets import SecretsPlugin

from floe_secrets_k8s.config import K8sSecretsConfig
from floe_secrets_k8s.errors import (
    SecretAccessDeniedError,
    SecretBackendUnavailableError,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)


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
        self.config = config or K8sSecretsConfig()
        self._client: Any = None
        self._api: Any = None
        self._audit_logger = AuditLogger()

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

    def get_config_schema(self) -> type[BaseModel]:
        """Return the configuration schema."""
        return K8sSecretsConfig

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
            logger.exception("Failed to initialize Kubernetes client")
            raise SecretBackendUnavailableError(reason=str(e)) from e

    def shutdown(self) -> None:
        """Clean up resources."""
        self._client = None
        self._api = None
        logger.info("K8sSecretsPlugin shutdown complete")

    def health_check(self) -> HealthStatus:
        """Check connectivity to Kubernetes API.

        Returns:
            HealthStatus indicating current health state.
        """
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
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message=f"K8s API check failed: {e}",
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
        self._ensure_initialized()

        # Parse key format
        secret_name, secret_key = self._parse_key(key)

        try:
            secret = self._api.read_namespaced_secret(
                name=secret_name,
                namespace=self.config.namespace,
            )

            if secret.data is None:
                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.GET,
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                    metadata={"found": False},
                )
                return None

            if secret_key not in secret.data:
                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.GET,
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                    metadata={"found": False},
                )
                return None

            # K8s secrets are base64 encoded
            encoded_value = secret.data[secret_key]
            result = base64.b64decode(encoded_value).decode("utf-8")

            # Log successful access
            self._audit_logger.log_success(
                requester_id="system",
                secret_path=key,
                operation=AuditOperation.GET,
                plugin_type=self.name,
                namespace=self.config.namespace,
                metadata={"found": True},
            )

            return result

        except self._client.rest.ApiException as e:
            if e.status == 404:
                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.GET,
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                    metadata={"found": False},
                )
                return None
            if e.status == 403:
                self._audit_logger.log_denied(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.GET,
                    reason=str(e),
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                )
                raise SecretAccessDeniedError(
                    secret_name,
                    namespace=self.config.namespace,
                    reason=str(e),
                ) from e
            self._audit_logger.log_error(
                requester_id="system",
                secret_path=key,
                operation=AuditOperation.GET,
                error=str(e),
                plugin_type=self.name,
                namespace=self.config.namespace,
            )
            raise SecretBackendUnavailableError(reason=str(e)) from e

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
        self._ensure_initialized()

        secret_name, secret_key = self._parse_key(key)

        # Prepare secret data
        encoded_value = base64.b64encode(value.encode("utf-8")).decode("utf-8")

        # Prepare labels and annotations
        labels = dict(self.config.labels)
        annotations: dict[str, str] = {}
        if metadata:
            # Store metadata as annotations
            for k, v in metadata.items():
                annotations[f"floe.dev/{k}"] = str(v)

        try:
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
                self._merge_labels_and_annotations(
                    existing.metadata, labels, annotations
                )

                self._api.replace_namespaced_secret(
                    name=secret_name,
                    namespace=self.config.namespace,
                    body=existing,
                )
                logger.info(
                    "Updated secret",
                    extra={"secret_name": secret_name, "key": secret_key},
                )
                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.SET,
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                    metadata={"action": "updated"},
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
                    extra={"secret_name": secret_name, "key": secret_key},
                )
                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.SET,
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                    metadata={"action": "created"},
                )

        except self._client.rest.ApiException as e:
            if e.status == 403:
                self._audit_logger.log_denied(
                    requester_id="system",
                    secret_path=key,
                    operation=AuditOperation.SET,
                    reason=str(e),
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                )
                raise SecretAccessDeniedError(
                    secret_name,
                    namespace=self.config.namespace,
                    reason=str(e),
                ) from e
            self._audit_logger.log_error(
                requester_id="system",
                secret_path=key,
                operation=AuditOperation.SET,
                error=str(e),
                plugin_type=self.name,
                namespace=self.config.namespace,
            )
            raise SecretBackendUnavailableError(reason=str(e)) from e

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
        self._ensure_initialized()

        try:
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
                secret_path=prefix or "*",
                operation=AuditOperation.LIST,
                plugin_type=self.name,
                namespace=self.config.namespace,
                metadata={"count": len(result)},
            )

            return sorted(result)

        except self._client.rest.ApiException as e:
            if e.status == 403:
                self._audit_logger.log_denied(
                    requester_id="system",
                    secret_path=prefix or "*",
                    operation=AuditOperation.LIST,
                    reason=str(e),
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                )
                raise SecretAccessDeniedError(
                    "",
                    namespace=self.config.namespace,
                    reason=str(e),
                ) from e
            self._audit_logger.log_error(
                requester_id="system",
                secret_path=prefix or "*",
                operation=AuditOperation.LIST,
                error=str(e),
                plugin_type=self.name,
                namespace=self.config.namespace,
            )
            raise SecretBackendUnavailableError(reason=str(e)) from e

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
        self._ensure_initialized()

        try:
            secret = self._api.read_namespaced_secret(
                name=name,
                namespace=self.config.namespace,
            )

            if secret.data is None:
                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=name,
                    operation=AuditOperation.GET,
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                    metadata={"found": False, "multi_key": True},
                )
                return {}

            result: dict[str, str] = {}
            for key, encoded_value in secret.data.items():
                result[key] = base64.b64decode(encoded_value).decode("utf-8")

            self._audit_logger.log_success(
                requester_id="system",
                secret_path=name,
                operation=AuditOperation.GET,
                plugin_type=self.name,
                namespace=self.config.namespace,
                metadata={"found": True, "multi_key": True, "key_count": len(result)},
            )
            return result

        except self._client.rest.ApiException as e:
            if e.status == 404:
                self._audit_logger.log_success(
                    requester_id="system",
                    secret_path=name,
                    operation=AuditOperation.GET,
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                    metadata={"found": False, "multi_key": True},
                )
                return {}
            if e.status == 403:
                self._audit_logger.log_denied(
                    requester_id="system",
                    secret_path=name,
                    operation=AuditOperation.GET,
                    reason=str(e),
                    plugin_type=self.name,
                    namespace=self.config.namespace,
                )
                raise SecretAccessDeniedError(
                    name,
                    namespace=self.config.namespace,
                    reason=str(e),
                ) from e
            self._audit_logger.log_error(
                requester_id="system",
                secret_path=name,
                operation=AuditOperation.GET,
                error=str(e),
                plugin_type=self.name,
                namespace=self.config.namespace,
            )
            raise SecretBackendUnavailableError(reason=str(e)) from e

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
        if "/" in key:
            parts = key.split("/", 1)
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

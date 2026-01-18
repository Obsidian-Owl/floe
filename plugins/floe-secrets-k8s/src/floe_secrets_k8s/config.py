"""Configuration models for K8sSecretsPlugin.

This module provides Pydantic configuration models for the K8s Secrets plugin.

Implements:
    - FR-010: K8sSecretsPlugin configuration
    - CR-003: Configuration schema via Pydantic

Example:
    >>> from floe_secrets_k8s import K8sSecretsConfig
    >>> config = K8sSecretsConfig(namespace="my-namespace")
    >>> config.namespace
    'my-namespace'
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class K8sSecretsConfig(BaseModel):
    """Configuration for K8sSecretsPlugin.

    This configuration controls how the plugin connects to the Kubernetes API
    and manages secrets within a specific namespace.

    Attributes:
        namespace: K8s namespace for secrets (default: "floe-jobs").
        kubeconfig_path: Path to kubeconfig file. None uses in-cluster config.
        context: Kubeconfig context to use. None uses current context.
        labels: Labels to apply to created secrets.
        secret_prefix: Prefix for secret names managed by this plugin.

    Example:
        >>> config = K8sSecretsConfig(
        ...     namespace="production",
        ...     labels={"managed-by": "floe"},
        ... )
        >>> config.namespace
        'production'

        >>> # In-cluster configuration (default)
        >>> config = K8sSecretsConfig()
        >>> config.kubeconfig_path is None
        True

        >>> # External kubeconfig
        >>> config = K8sSecretsConfig(
        ...     kubeconfig_path="~/.kube/config",
        ...     context="my-cluster",
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"namespace": "floe-jobs"},
                {
                    "namespace": "production",
                    "kubeconfig_path": "~/.kube/config",
                    "context": "prod-cluster",
                    "labels": {"managed-by": "floe", "environment": "prod"},
                },
            ]
        },
    )

    namespace: str = Field(
        default="floe-jobs",
        min_length=1,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$",
        description="Kubernetes namespace for secrets",
        examples=["floe-jobs", "production", "staging"],
    )

    kubeconfig_path: str | None = Field(
        default=None,
        description="Path to kubeconfig file. None uses in-cluster config.",
        examples=["~/.kube/config", "/etc/kubernetes/admin.conf"],
    )

    context: str | None = Field(
        default=None,
        description="Kubeconfig context to use. None uses current context.",
        examples=["minikube", "prod-cluster", "kind-floe"],
    )

    labels: dict[str, str] = Field(
        default_factory=lambda: {"managed-by": "floe"},
        description="Labels to apply to created secrets",
        examples=[{"managed-by": "floe", "environment": "dev"}],
    )

    secret_prefix: str = Field(
        default="floe-",
        min_length=0,
        max_length=50,
        description="Prefix for secret names managed by this plugin",
        examples=["floe-", "app-secrets-"],
    )

    @field_validator("kubeconfig_path")
    @classmethod
    def expand_kubeconfig_path(cls, v: str | None) -> str | None:
        """Expand ~ in kubeconfig path.

        Args:
            v: The kubeconfig path value.

        Returns:
            Expanded path or None.
        """
        if v is None:
            return None
        return str(Path(v).expanduser())

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate K8s label format.

        K8s labels must follow naming conventions:
        - Keys: prefix/name or name, max 63 chars each segment
        - Values: max 63 chars, alphanumeric with dashes

        Args:
            v: The labels dictionary.

        Returns:
            Validated labels dictionary.

        Raises:
            ValueError: If label format is invalid.
        """
        for key, value in v.items():
            if len(key) > 253:
                msg = f"Label key too long: {key}"
                raise ValueError(msg)
            if len(value) > 63:
                msg = f"Label value too long for key {key}: {value}"
                raise ValueError(msg)
        return v


__all__ = ["K8sSecretsConfig"]

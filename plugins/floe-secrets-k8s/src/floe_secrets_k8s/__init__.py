"""floe-secrets-k8s: Kubernetes Secrets backend for floe platform.

This plugin provides K8s Secrets integration as the default secrets backend
with zero external dependencies beyond Kubernetes itself.

Example:
    >>> from floe_secrets_k8s import K8sSecretsPlugin, K8sSecretsConfig
    >>> config = K8sSecretsConfig(namespace="floe-jobs")
    >>> plugin = K8sSecretsPlugin(config)
    >>> secret = plugin.get_secret("database-password")
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = [
    "K8sSecretsPlugin",
    "K8sSecretsConfig",
]

# Lazy imports to avoid circular dependencies and improve startup time
def __getattr__(name: str):
    """Lazy import of plugin components."""
    if name == "K8sSecretsPlugin":
        from floe_secrets_k8s.plugin import K8sSecretsPlugin
        return K8sSecretsPlugin
    if name == "K8sSecretsConfig":
        from floe_secrets_k8s.config import K8sSecretsConfig
        return K8sSecretsConfig
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

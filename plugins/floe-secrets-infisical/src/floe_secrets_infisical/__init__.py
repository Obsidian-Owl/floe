"""floe-secrets-infisical: Infisical secrets backend for floe platform.

This plugin provides Infisical integration as the recommended OSS secrets
backend per ADR-0031, with Universal Auth and auto-reload capabilities.

Example:
    >>> from floe_secrets_infisical import InfisicalSecretsPlugin, InfisicalSecretsConfig
    >>> config = InfisicalSecretsConfig(
    ...     client_id="...",
    ...     client_secret="...",
    ...     project_id="..."
    ... )
    >>> plugin = InfisicalSecretsPlugin(config)
    >>> secret = plugin.get_secret("database/password")
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0"
__all__ = [
    "InfisicalSecretsPlugin",
    "InfisicalSecretsConfig",
    "InfisicalPluginError",
    "InfisicalAuthError",
    "InfisicalSecretNotFoundError",
    "InfisicalAccessDeniedError",
    "InfisicalBackendUnavailableError",
    "InfisicalValidationError",
]


# Lazy imports to avoid circular dependencies and improve startup time
def __getattr__(name: str) -> Any:
    """Lazy import of plugin components."""
    if name == "InfisicalSecretsPlugin":
        from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

        return InfisicalSecretsPlugin
    if name == "InfisicalSecretsConfig":
        from floe_secrets_infisical.config import InfisicalSecretsConfig

        return InfisicalSecretsConfig
    if name in (
        "InfisicalPluginError",
        "InfisicalAuthError",
        "InfisicalSecretNotFoundError",
        "InfisicalAccessDeniedError",
        "InfisicalBackendUnavailableError",
        "InfisicalValidationError",
    ):
        from floe_secrets_infisical import errors

        return getattr(errors, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

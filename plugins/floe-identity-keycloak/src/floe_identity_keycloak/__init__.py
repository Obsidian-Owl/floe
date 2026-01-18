"""floe-identity-keycloak: Keycloak identity provider for floe platform.

This plugin provides Keycloak/OIDC integration as the default identity provider
for the floe platform per ADR-0024.

Example:
    >>> from floe_identity_keycloak import KeycloakIdentityPlugin, KeycloakIdentityConfig
    >>> config = KeycloakIdentityConfig(
    ...     server_url="https://keycloak.example.com",
    ...     client_id="floe",
    ...     client_secret="..."
    ... )
    >>> plugin = KeycloakIdentityPlugin(config)
    >>> result = plugin.validate_token(token)
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0"
__all__ = [
    # Plugin and config
    "KeycloakIdentityPlugin",
    "KeycloakIdentityConfig",
    # Exceptions
    "KeycloakPluginError",
    "KeycloakConfigError",
    "KeycloakAuthError",
    "KeycloakTokenError",
    "KeycloakUnavailableError",
]

# Lazy imports to avoid circular dependencies and improve startup time
def __getattr__(name: str) -> Any:
    """Lazy import of plugin components."""
    if name == "KeycloakIdentityPlugin":
        from floe_identity_keycloak.plugin import KeycloakIdentityPlugin
        return KeycloakIdentityPlugin
    if name == "KeycloakIdentityConfig":
        from floe_identity_keycloak.config import KeycloakIdentityConfig
        return KeycloakIdentityConfig
    if name in (
        "KeycloakPluginError",
        "KeycloakConfigError",
        "KeycloakAuthError",
        "KeycloakTokenError",
        "KeycloakUnavailableError",
    ):
        from floe_identity_keycloak import errors
        return getattr(errors, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

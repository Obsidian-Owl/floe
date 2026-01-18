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

__version__ = "0.1.0"
__all__ = [
    "KeycloakIdentityPlugin",
    "KeycloakIdentityConfig",
]

# Lazy imports to avoid circular dependencies and improve startup time
def __getattr__(name: str):
    """Lazy import of plugin components."""
    if name == "KeycloakIdentityPlugin":
        from floe_identity_keycloak.plugin import KeycloakIdentityPlugin
        return KeycloakIdentityPlugin
    if name == "KeycloakIdentityConfig":
        from floe_identity_keycloak.config import KeycloakIdentityConfig
        return KeycloakIdentityConfig
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

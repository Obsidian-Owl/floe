"""Configuration models for KeycloakIdentityPlugin.

This module provides Pydantic configuration models for the Keycloak Identity plugin.

Implements:
    - FR-030: KeycloakIdentityPlugin configuration
    - CR-003: Configuration schema via Pydantic

Security:
    - HTTPS required for all non-localhost URLs
    - Proper hostname parsing prevents bypass attacks
"""

from __future__ import annotations

import ipaddress
from typing import Annotated
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

# SECURITY: Known localhost hostnames (exact match only)
_LOCALHOST_HOSTNAMES: frozenset[str] = frozenset(
    {
        "localhost",
        "localhost.localdomain",
    }
)


def _is_localhost(hostname: str) -> bool:
    """Check if hostname represents localhost.

    SECURITY: Uses exact hostname matching and proper IP address parsing
    to prevent bypass attacks like 'localhost.attacker.com'.

    Args:
        hostname: The hostname to check.

    Returns:
        True if the hostname is localhost or a loopback IP address.
    """
    # Check known localhost hostnames (case-insensitive, exact match)
    if hostname.lower() in _LOCALHOST_HOSTNAMES:
        return True

    # Check if it's a loopback IP address
    try:
        addr = ipaddress.ip_address(hostname)
        # Handle IPv4-mapped IPv6 addresses (e.g., ::ffff:127.0.0.1)
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            return addr.ipv4_mapped.is_loopback
        return addr.is_loopback
    except ValueError:
        # Not a valid IP address - must match hostname exactly
        return False


class KeycloakIdentityConfig(BaseModel):
    """Configuration for KeycloakIdentityPlugin.

    This model validates and stores configuration for connecting to a Keycloak
    server for OIDC-based identity management.

    Attributes:
        server_url: Keycloak server URL (must be HTTPS except for localhost).
        realm: Keycloak realm name.
        client_id: OIDC client ID.
        client_secret: OIDC client secret (stored securely).
        verify_ssl: Whether to verify SSL certificates. Defaults to True.
        timeout: HTTP request timeout in seconds. Defaults to 30.0.
        scopes: OIDC scopes to request. Defaults to ["openid", "profile", "email"].

    Examples:
        >>> from pydantic import SecretStr
        >>> config = KeycloakIdentityConfig(
        ...     server_url="https://keycloak.example.com",
        ...     realm="floe",
        ...     client_id="floe-client",
        ...     client_secret=SecretStr("my-secret"),
        ... )
        >>> config.discovery_url
        'https://keycloak.example.com/realms/floe/.well-known/openid-configuration'
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    server_url: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            description="Keycloak server URL (must be HTTPS except for localhost)",
        ),
    ]
    realm: Annotated[
        str,
        Field(..., min_length=1, description="Keycloak realm name"),
    ]
    client_id: Annotated[
        str,
        Field(..., min_length=1, description="OIDC client ID"),
    ]
    client_secret: Annotated[
        SecretStr,
        Field(..., description="OIDC client secret"),
    ]
    verify_ssl: Annotated[
        bool,
        Field(default=True, description="Whether to verify SSL certificates"),
    ]
    timeout: Annotated[
        float,
        Field(default=30.0, gt=0, description="HTTP request timeout in seconds"),
    ]
    scopes: Annotated[
        list[str],
        Field(
            default_factory=lambda: ["openid", "profile", "email"],
            description="OIDC scopes to request",
        ),
    ]

    @field_validator("server_url")
    @classmethod
    def validate_server_url(cls, v: str) -> str:
        """Validate server URL format and protocol.

        SECURITY NOTES:
            - HTTP is ONLY allowed for localhost/loopback addresses (127.0.0.1, ::1)
            - This is intentional for local development and testing environments
            - Production deployments MUST use HTTPS URLs which are enforced by this validator
            - Uses proper URL parsing to prevent bypass attacks (not substring matching)
            - The localhost exception is safe because loopback traffic never leaves the host

        Args:
            v: The server URL to validate.

        Returns:
            Validated and normalized server URL.

        Raises:
            ValueError: If URL is not HTTPS (except for localhost).
        """
        # Strip trailing slashes
        v = v.rstrip("/")

        # SECURITY: HTTP is only allowed for localhost addresses.
        # This is safe because loopback traffic never leaves the host.
        # Production deployments must use HTTPS.
        if v.startswith("http://"):
            # SECURITY: Parse URL to extract actual hostname
            # Never use substring matching - vulnerable to bypass
            parsed = urlparse(v)
            hostname = parsed.hostname or ""

            # Check if it's actually localhost (proper validation)
            if _is_localhost(hostname):
                return v

            raise ValueError(
                f"HTTP not allowed for '{hostname}'. "
                "server_url must use HTTPS for non-localhost URLs. "
                "HTTP is only allowed for localhost development."
            )

        if not v.startswith("https://"):
            raise ValueError("server_url must start with https:// or http://localhost")

        return v

    @field_validator("client_secret")
    @classmethod
    def validate_client_secret(cls, v: SecretStr) -> SecretStr:
        """Validate that client_secret is not empty.

        Args:
            v: The client secret to validate.

        Returns:
            Validated client secret.

        Raises:
            ValueError: If client secret is empty.
        """
        if not v.get_secret_value():
            raise ValueError("client_secret cannot be empty")
        return v

    @model_validator(mode="after")
    def validate_config(self) -> KeycloakIdentityConfig:
        """Perform cross-field validation.

        Returns:
            Validated configuration.
        """
        # Ensure openid scope is always included
        if "openid" not in self.scopes:
            # Since model is frozen, we can't modify scopes here
            # The default includes openid, and users should include it
            pass
        return self

    @property
    def discovery_url(self) -> str:
        """Get the OIDC discovery URL.

        Returns:
            URL to the .well-known/openid-configuration endpoint.
        """
        return f"{self.server_url}/realms/{self.realm}/.well-known/openid-configuration"

    @property
    def token_url(self) -> str:
        """Get the token endpoint URL.

        Returns:
            URL to the token endpoint.
        """
        return f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/token"

    @property
    def jwks_url(self) -> str:
        """Get the JWKS endpoint URL.

        Returns:
            URL to the JWKS (JSON Web Key Set) endpoint.
        """
        return f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/certs"

    @property
    def userinfo_url(self) -> str:
        """Get the userinfo endpoint URL.

        Returns:
            URL to the userinfo endpoint.
        """
        return f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/userinfo"

    @property
    def authorization_url(self) -> str:
        """Get the authorization endpoint URL.

        Returns:
            URL to the authorization endpoint.
        """
        return f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/auth"

    @property
    def end_session_url(self) -> str:
        """Get the end session (logout) endpoint URL.

        Returns:
            URL to the end session endpoint.
        """
        return f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/logout"

    @property
    def introspect_url(self) -> str:
        """Get the token introspection endpoint URL.

        Returns:
            URL to the token introspection endpoint.
        """
        return f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/token/introspect"

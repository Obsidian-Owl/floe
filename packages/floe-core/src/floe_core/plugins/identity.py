"""IdentityPlugin ABC for authentication provider plugins.

This module defines the abstract base class for identity plugins that
provide authentication functionality. Identity plugins are responsible for:
- Authenticating users/services
- Retrieving user information
- Validating tokens

Example:
    >>> from floe_core.plugins.identity import IdentityPlugin
    >>> class OIDCPlugin(IdentityPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "oidc"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any

from floe_core.plugin_metadata import PluginMetadata


@dataclass
class UserInfo:
    """User information from identity provider.

    Attributes:
        subject: Unique user identifier (sub claim).
        email: User's email address.
        name: User's display name.
        roles: List of user roles.
        groups: List of user groups.
        claims: Additional identity claims.

    Example:
        >>> user = UserInfo(
        ...     subject="auth0|123456",
        ...     email="user@example.com",
        ...     name="John Doe",
        ...     roles=["analyst", "viewer"]
        ... )
    """

    subject: str
    email: str = ""
    name: str = ""
    roles: list[str] = field(default_factory=lambda: [])
    groups: list[str] = field(default_factory=lambda: [])
    claims: dict[str, Any] = field(default_factory=lambda: {})


@dataclass
class TokenValidationResult:
    """Result of token validation.

    Attributes:
        valid: Whether the token is valid.
        user_info: User information if valid.
        error: Error message if invalid.
        expires_at: Token expiration timestamp.

    Example:
        >>> result = TokenValidationResult(
        ...     valid=True,
        ...     user_info=UserInfo(subject="user123", email="user@example.com"),
        ...     expires_at="2024-01-15T12:00:00Z"
        ... )
    """

    valid: bool
    user_info: UserInfo | None = None
    error: str = ""
    expires_at: str = ""


@dataclass
class OIDCConfig:
    """OIDC provider endpoint configuration.

    Contains all endpoints required for OIDC integration with identity providers
    like Keycloak, Auth0, Okta, or Azure AD.

    Attributes:
        issuer_url: The issuer URL (iss claim in tokens).
        discovery_url: The .well-known/openid-configuration endpoint.
        jwks_uri: JSON Web Key Set endpoint for token validation.
        authorization_endpoint: OAuth2 authorization endpoint.
        token_endpoint: OAuth2 token endpoint.
        userinfo_endpoint: OIDC userinfo endpoint.

    Example:
        >>> config = OIDCConfig(
        ...     issuer_url="https://keycloak.example.com/realms/floe",
        ...     discovery_url="https://keycloak.example.com/realms/floe/.well-known/openid-configuration",
        ...     jwks_uri="https://keycloak.example.com/realms/floe/protocol/openid-connect/certs",
        ...     authorization_endpoint="https://keycloak.example.com/realms/floe/protocol/openid-connect/auth",
        ...     token_endpoint="https://keycloak.example.com/realms/floe/protocol/openid-connect/token",
        ...     userinfo_endpoint="https://keycloak.example.com/realms/floe/protocol/openid-connect/userinfo",
        ... )
    """

    issuer_url: str
    discovery_url: str
    jwks_uri: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str


class IdentityPlugin(PluginMetadata):
    """Abstract base class for authentication provider plugins.

    IdentityPlugin extends PluginMetadata with identity-specific methods
    for authentication. Implementations include OAuth2/OIDC providers
    (Auth0, Keycloak, Okta) and service account authentication.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - authenticate() method
        - get_user_info() method
        - validate_token() method

    Example:
        >>> class OIDCPlugin(IdentityPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "oidc"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def authenticate(self, credentials: dict) -> str | None:
        ...         # Exchange credentials for token
        ...         return self._client.get_token(credentials)

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
    """

    @abstractmethod
    def authenticate(self, credentials: dict[str, Any]) -> str | None:
        """Authenticate and return an access token.

        Exchanges credentials for an access token from the identity
        provider.

        Args:
            credentials: Authentication credentials (varies by provider):
                - OAuth2 password grant: {"username": "...", "password": "..."}
                - OAuth2 client credentials: {"client_id": "...", "client_secret": "..."}
                - API key: {"api_key": "..."}

        Returns:
            Access token string if successful, None if authentication fails.

        Raises:
            ConnectionError: If unable to connect to identity provider.

        Example:
            >>> token = plugin.authenticate({
            ...     "client_id": "my-service",
            ...     "client_secret": "secret123"
            ... })
            >>> token
            'eyJhbGciOiJSUzI1NiIs...'
        """
        ...

    @abstractmethod
    def get_user_info(self, token: str) -> UserInfo | None:
        """Retrieve user information from token.

        Fetches user profile information using the access token.

        Args:
            token: Valid access token.

        Returns:
            UserInfo object if token is valid, None otherwise.

        Raises:
            ConnectionError: If unable to connect to identity provider.

        Example:
            >>> user = plugin.get_user_info(token)
            >>> user.email
            'user@example.com'
            >>> user.roles
            ['analyst', 'viewer']
        """
        ...

    @abstractmethod
    def validate_token(self, token: str) -> TokenValidationResult:
        """Validate an access token.

        Verifies the token signature, expiration, and claims.

        Args:
            token: Access token to validate.

        Returns:
            TokenValidationResult with validation status and user info.

        Example:
            >>> result = plugin.validate_token(token)
            >>> if result.valid:
            ...     print(f"User: {result.user_info.email}")
            ... else:
            ...     print(f"Invalid: {result.error}")
        """
        ...

    def get_oidc_config(self, realm: str | None = None) -> OIDCConfig:
        """Get OIDC configuration for service integration.

        Returns the OIDC discovery endpoints for the identity provider.
        This is an optional method - plugins that don't support OIDC
        should raise NotImplementedError.

        Args:
            realm: Optional realm/tenant identifier for multi-tenant providers.

        Returns:
            OIDCConfig with all OIDC endpoints.

        Raises:
            NotImplementedError: If plugin doesn't support OIDC discovery.
            ConnectionError: If unable to fetch OIDC configuration.

        Example:
            >>> config = plugin.get_oidc_config(realm="floe")
            >>> config.jwks_uri
            'https://keycloak.example.com/realms/floe/protocol/openid-connect/certs'
        """
        raise NotImplementedError("OIDC not supported by this plugin")

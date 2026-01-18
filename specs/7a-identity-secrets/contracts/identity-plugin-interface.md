# Contract: IdentityPlugin Interface

**Version**: 1.0.0
**Status**: Draft
**Date**: 2026-01-18

## Overview

This contract defines the interface for Identity plugins in the floe platform. All identity provider implementations MUST conform to this interface.

## Interface Definition

```python
from __future__ import annotations
from abc import abstractmethod
from typing import Any
from floe_core.plugin_metadata import PluginMetadata

class IdentityPlugin(PluginMetadata):
    """Abstract base class for authentication provider plugins.

    All identity plugins MUST implement these methods:
    - authenticate(): Exchange credentials for access token
    - get_user_info(): Retrieve user profile from token
    - validate_token(): Verify token validity

    Implementations include:
    - KeycloakIdentityPlugin (default)
    - DexIdentityPlugin (lightweight)
    - ExternalIdentityPlugin (Okta, Auth0, Azure AD)
    """

    @abstractmethod
    def authenticate(self, credentials: dict[str, Any]) -> str | None:
        """Exchange credentials for an access token.

        Args:
            credentials: Authentication credentials (varies by provider):
                - OAuth2 password: {"username": "...", "password": "..."}
                - Client credentials: {"client_id": "...", "client_secret": "..."}
                - API key: {"api_key": "..."}

        Returns:
            Access token string if successful, None if authentication fails.

        Raises:
            ConnectionError: Unable to connect to identity provider.
            PermissionError: Invalid credentials provided.
        """
        ...

    @abstractmethod
    def get_user_info(self, token: str) -> UserInfo | None:
        """Retrieve user information from token.

        Args:
            token: Valid access token.

        Returns:
            UserInfo if token is valid, None if invalid/expired.

        Raises:
            ConnectionError: Unable to connect to identity provider.
        """
        ...

    @abstractmethod
    def validate_token(self, token: str) -> TokenValidationResult:
        """Validate an access token.

        Verifies token signature, expiration, and claims using JWKS.

        Args:
            token: Access token to validate.

        Returns:
            TokenValidationResult with validation status and user info.

        Raises:
            ConnectionError: Unable to fetch JWKS for validation.
        """
        ...

    def get_oidc_config(self, realm: str | None = None) -> OIDCConfig:
        """Get OIDC configuration for service integration.

        Optional method for plugins that support OIDC discovery.

        Args:
            realm: Optional realm/tenant identifier.

        Returns:
            OIDCConfig with all OIDC endpoints.

        Raises:
            NotImplementedError: If plugin doesn't support OIDC.
        """
        raise NotImplementedError("OIDC not supported by this plugin")
```

## Data Types

### UserInfo

```python
@dataclass
class UserInfo:
    """Authenticated user information."""
    subject: str           # Unique user ID (required)
    email: str = ""        # Email address
    name: str = ""         # Display name
    roles: list[str] = field(default_factory=list)   # Role assignments
    groups: list[str] = field(default_factory=list)  # Group memberships
    claims: dict[str, Any] = field(default_factory=dict)  # Additional claims
```

### TokenValidationResult

```python
@dataclass
class TokenValidationResult:
    """Result of token validation."""
    valid: bool                     # True if token is valid
    user_info: UserInfo | None = None  # User info (if valid)
    error: str = ""                 # Error message (if invalid)
    expires_at: str = ""            # ISO 8601 expiration timestamp
```

### OIDCConfig

```python
@dataclass
class OIDCConfig:
    """OIDC provider endpoint configuration."""
    issuer_url: str           # Issuer URL
    discovery_url: str        # .well-known/openid-configuration
    jwks_uri: str             # JWKS endpoint
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
```

## Entry Point Registration

Plugins MUST register via `pyproject.toml`:

```toml
[project.entry-points."floe.identity"]
keycloak = "floe_identity_keycloak.plugin:KeycloakIdentityPlugin"
dex = "floe_identity_dex.plugin:DexIdentityPlugin"
external = "floe_identity_external.plugin:ExternalIdentityPlugin"
```

## Compliance Requirements

### CR-001: PluginMetadata Properties

All implementations MUST provide:
- `name`: Unique identifier (e.g., "keycloak")
- `version`: Semantic version (e.g., "1.0.0")
- `floe_api_version`: Minimum API version (e.g., "1.0")

### CR-002: Health Check

All implementations MUST implement `health_check()`:
- Return within 5 seconds
- Return `HealthStatus` with state and optional message

### CR-003: Configuration Schema

All implementations MUST provide `get_config_schema()`:
- Return Pydantic BaseModel subclass
- Use `SecretStr` for credentials
- Use `ConfigDict(frozen=True, extra="forbid")`

### CR-004: Error Handling

All implementations MUST:
- Raise `ConnectionError` for connectivity issues
- Raise `PermissionError` for authentication failures
- Never expose internal exceptions to callers

### CR-005: Security

All implementations MUST:
- Never log token or credential values
- Use `SecretStr` for all secret fields
- Validate all inputs

## Testing Requirements

All implementations MUST pass `BaseIdentityPluginTests`:

```python
class BaseIdentityPluginTests(PluginTestBase):
    """Compliance tests for IdentityPlugin implementations."""

    @pytest.mark.requirement("7A-FR-001")
    def test_plugin_has_required_metadata(self) -> None:
        """Plugin has name, version, floe_api_version."""

    @pytest.mark.requirement("7A-FR-001")
    def test_authenticate_returns_token_or_none(self) -> None:
        """authenticate() returns str or None, never raises for bad creds."""

    @pytest.mark.requirement("7A-FR-001")
    def test_validate_token_returns_result(self) -> None:
        """validate_token() always returns TokenValidationResult."""

    @pytest.mark.requirement("7A-FR-001")
    def test_get_user_info_returns_userinfo_or_none(self) -> None:
        """get_user_info() returns UserInfo or None."""
```

## Versioning

- **1.0.0**: Initial interface (authenticate, get_user_info, validate_token)
- Future: Add refresh_token(), revoke_token() methods

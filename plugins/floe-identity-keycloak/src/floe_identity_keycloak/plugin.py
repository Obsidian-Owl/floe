"""KeycloakIdentityPlugin implementation.

This module provides the KeycloakIdentityPlugin class for OIDC authentication
via Keycloak as the default identity provider per ADR-0024.

Implements:
    - FR-030: KeycloakPlugin as default OIDC provider
    - FR-031: OIDCConfig with discovery/JWKS endpoints
    - FR-032: Realm-based multi-tenancy
    - FR-033: Client creation with configurable scopes
    - FR-034: JWT validation using JWKS
    - OB-005: OpenTelemetry tracing for authentication operations
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.identity import (
    IdentityPlugin,
    OIDCConfig,
    TokenValidationResult,
    UserInfo,
)

from .config import KeycloakIdentityConfig
from .token_validator import TokenValidator

# OpenTelemetry imports - optional dependency
try:
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind, Status, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    SpanKind = None  # type: ignore[assignment, misc]
    Status = None  # type: ignore[assignment, misc]
    StatusCode = None  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer

# Tracer name for Keycloak plugin
_TRACER_NAME = "floe.identity.keycloak"

# Error messages (avoid S1192 duplicate string literals)
_NOT_STARTED_ERROR = "Plugin not started. Call startup() first."

# OpenTelemetry span attribute names
_SPAN_REALM = "keycloak.realm"
_SPAN_CLIENT_ID = "keycloak.client_id"
_SPAN_AUTH_SUCCESS = "keycloak.auth.success"
_SPAN_TOKEN_VALID = "keycloak.token.valid"


def _get_tracer() -> Tracer | None:
    """Get OpenTelemetry tracer if available.

    Returns:
        Tracer instance or None if OTel not available.
    """
    if not _OTEL_AVAILABLE or trace is None:
        return None
    return trace.get_tracer(_TRACER_NAME)


class KeycloakIdentityPlugin(IdentityPlugin):
    """Keycloak OIDC identity plugin.

    This plugin provides OIDC-based authentication via Keycloak server.
    It supports password grant, client credentials grant, and token validation.

    Attributes:
        name: Plugin name ("keycloak").
        version: Plugin version.
        floe_api_version: Compatible floe API version.
        description: Plugin description.

    Examples:
        >>> from pydantic import SecretStr
        >>> config = KeycloakIdentityConfig(
        ...     server_url="https://keycloak.example.com",
        ...     realm="floe",
        ...     client_id="floe-client",
        ...     client_secret=SecretStr("secret"),
        ... )
        >>> plugin = KeycloakIdentityPlugin(config=config)
        >>> plugin.startup()
        >>> token = plugin.authenticate({"username": "user", "password": "pass"})
    """

    @property
    def name(self) -> str:
        """Plugin name."""
        return "keycloak"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Compatible floe API version."""
        return "1.0"

    @property
    def description(self) -> str:
        """Plugin description."""
        return "Keycloak OIDC identity provider for floe platform"

    def __init__(self, config: KeycloakIdentityConfig) -> None:
        """Initialize KeycloakIdentityPlugin.

        Args:
            config: Keycloak configuration.
        """
        self._config = config
        self._client: httpx.Client | None = None
        self._token_validator: TokenValidator | None = None
        self._realm_validators: dict[str, TokenValidator] = {}
        self._started = False

    @property
    def realm(self) -> str:
        """Get the configured realm name."""
        return self._config.realm

    @property
    def server_url(self) -> str:
        """Get the Keycloak server URL."""
        return self._config.server_url

    def startup(self) -> None:
        """Start the plugin and initialize resources.

        Creates HTTP client and token validator.
        """
        if self._started:
            return

        self._client = httpx.Client(
            verify=self._config.verify_ssl,
            timeout=self._config.timeout,
        )

        self._token_validator = TokenValidator(
            issuer=f"{self._config.server_url}/realms/{self._config.realm}",
            audience=self._config.client_id,
            jwks_url=self._config.jwks_url,
            verify_ssl=self._config.verify_ssl,
            timeout=self._config.timeout,
        )

        self._started = True

    def shutdown(self) -> None:
        """Shutdown the plugin and release resources."""
        if self._client:
            self._client.close()
            self._client = None

        self._token_validator = None
        self._realm_validators.clear()
        self._started = False

    def health_check(self) -> HealthStatus:
        """Check if plugin is healthy.

        Returns:
            HealthStatus indicating current health state.
        """
        if not self._started or not self._client:
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message="Plugin not started or client not initialized",
            )

        try:
            response = self._client.get(self._config.discovery_url)
            if response.status_code == 200:
                return HealthStatus(state=HealthState.HEALTHY)
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message=f"Keycloak returned status {response.status_code}",
            )
        except httpx.HTTPError as e:
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message=f"Failed to connect to Keycloak: {e}",
            )

    def authenticate(self, credentials: dict[str, Any]) -> str | None:
        """Authenticate and return an access token.

        Supports password grant (username/password) and client credentials grant.
        Emits OpenTelemetry spans for observability.

        Args:
            credentials: Authentication credentials:
                - Password grant: {"username": "...", "password": "..."}
                - Client credentials: {} (uses configured client credentials)

        Returns:
            Access token string if successful, None if authentication fails.

        Raises:
            RuntimeError: If plugin not started.
        """
        if not self._started or not self._client:
            raise RuntimeError(_NOT_STARTED_ERROR)

        # Determine grant type
        if "username" in credentials and "password" in credentials:
            grant_type = "password"
            # Password grant
            data = {
                "grant_type": "password",
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret.get_secret_value(),
                "username": credentials["username"],
                "password": credentials["password"],
                "scope": " ".join(self._config.scopes),
            }
        else:
            grant_type = "client_credentials"
            # Client credentials grant
            data = {
                "grant_type": "client_credentials",
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret.get_secret_value(),
                "scope": " ".join(self._config.scopes),
            }

        tracer = _get_tracer()
        if tracer is None:
            # No tracing available, execute directly
            return self._do_authenticate(data)

        # Execute with tracing
        with tracer.start_as_current_span(
            "keycloak.authenticate",
            kind=SpanKind.CLIENT,
        ) as span:
            span.set_attribute(_SPAN_REALM, self._config.realm)
            span.set_attribute(_SPAN_CLIENT_ID, self._config.client_id)
            span.set_attribute("keycloak.grant_type", grant_type)

            try:
                result = self._do_authenticate(data)
                if result is not None:
                    span.set_attribute(_SPAN_AUTH_SUCCESS, True)
                    span.set_status(Status(StatusCode.OK))
                else:
                    span.set_attribute(_SPAN_AUTH_SUCCESS, False)
                    span.set_status(Status(StatusCode.ERROR, "Authentication failed"))
                return result
            except Exception as e:
                span.set_attribute(_SPAN_AUTH_SUCCESS, False)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def _do_authenticate(self, data: dict[str, Any]) -> str | None:
        """Execute authentication request.

        Args:
            data: Token request data.

        Returns:
            Access token or None.
        """
        try:
            response = self._client.post(  # type: ignore[union-attr]
                self._config.token_url,
                data=data,
            )

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                return str(access_token) if access_token else None

            return None

        except httpx.HTTPError:
            return None

    def get_user_info(self, token: str) -> UserInfo | None:
        """Retrieve user information from token.

        Fetches user info from Keycloak's userinfo endpoint.

        Args:
            token: Valid access token.

        Returns:
            UserInfo object if token is valid, None otherwise.

        Raises:
            RuntimeError: If plugin not started.
        """
        if not self._started or not self._client:
            raise RuntimeError(_NOT_STARTED_ERROR)

        try:
            response = self._client.get(
                self._config.userinfo_url,
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code != 200:
                return None

            data = response.json()

            # Map Keycloak userinfo to UserInfo dataclass
            return UserInfo(
                subject=data.get("sub", ""),
                email=data.get("email", ""),
                name=data.get("name", ""),
                roles=self._extract_roles(data),
                groups=data.get("groups", []),
                claims=data,
            )

        except httpx.HTTPError:
            return None

    def validate_token(self, token: str) -> TokenValidationResult:
        """Validate an access token.

        Verifies the token signature, expiration, and claims using JWKS.
        Emits OpenTelemetry spans for observability.

        Args:
            token: Access token to validate.

        Returns:
            TokenValidationResult with validation status and user info.

        Raises:
            RuntimeError: If plugin not started.
        """
        if not self._started or not self._token_validator:
            raise RuntimeError(_NOT_STARTED_ERROR)

        tracer = _get_tracer()
        if tracer is None:
            # No tracing available, execute directly
            return self._validate_and_convert(token, self._token_validator)

        # Execute with tracing
        with tracer.start_as_current_span(
            "keycloak.validate_token",
            kind=SpanKind.CLIENT,
        ) as span:
            span.set_attribute(_SPAN_REALM, self._config.realm)
            span.set_attribute(_SPAN_CLIENT_ID, self._config.client_id)

            try:
                result = self._validate_and_convert(token, self._token_validator)
                span.set_attribute(_SPAN_TOKEN_VALID, result.valid)
                if result.valid:
                    span.set_status(Status(StatusCode.OK))
                    if result.user_info:
                        span.set_attribute("keycloak.user.subject", result.user_info.subject)
                else:
                    span.set_status(Status(StatusCode.ERROR, result.error or "Invalid token"))
                return result
            except Exception as e:
                span.set_attribute(_SPAN_TOKEN_VALID, False)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def _validate_and_convert(self, token: str, validator: TokenValidator) -> TokenValidationResult:
        """Validate token and convert to floe_core result.

        Args:
            token: Access token to validate.
            validator: TokenValidator instance.

        Returns:
            TokenValidationResult with validation status.
        """
        result = validator.validate(token)

        # Convert internal result to floe_core result
        if result.valid and result.user_info:
            user_info = UserInfo(
                subject=result.user_info.user_id,
                email=result.user_info.email or "",
                name=result.user_info.name or "",
                roles=result.user_info.roles or [],
                groups=[],
                claims={},
            )
            return TokenValidationResult(
                valid=True,
                user_info=user_info,
            )
        else:
            return TokenValidationResult(
                valid=False,
                error=result.error or "Token validation failed",
            )

    def get_oidc_config(self, realm: str | None = None) -> OIDCConfig:
        """Get OIDC configuration for service integration.

        Returns the OIDC discovery endpoints for Keycloak.

        Args:
            realm: Optional realm override. If None, uses configured realm.

        Returns:
            OIDCConfig with all OIDC endpoints.
        """
        effective_realm = realm or self._config.realm

        base_url = f"{self._config.server_url}/realms/{effective_realm}"
        protocol_url = f"{base_url}/protocol/openid-connect"

        return OIDCConfig(
            issuer_url=base_url,
            discovery_url=f"{base_url}/.well-known/openid-configuration",
            jwks_uri=f"{protocol_url}/certs",
            authorization_endpoint=f"{protocol_url}/auth",
            token_endpoint=f"{protocol_url}/token",
            userinfo_endpoint=f"{protocol_url}/userinfo",
        )

    def validate_token_for_realm(
        self,
        token: str,
        realm: str,
    ) -> TokenValidationResult:
        """Validate an access token against a specific realm.

        This method supports multi-tenancy by validating tokens from any
        realm on the same Keycloak server. TokenValidators are cached per
        realm for performance. Emits OpenTelemetry spans for observability.

        Args:
            token: Access token to validate.
            realm: Realm the token was issued from.

        Returns:
            TokenValidationResult with validation status and user info.

        Raises:
            RuntimeError: If plugin not started.

        Examples:
            >>> # Validate token from a different realm
            >>> result = plugin.validate_token_for_realm(token, "domain-sales")
            >>> if result.valid:
            ...     print(f"User: {result.user_info.subject}")
        """
        if not self._started:
            raise RuntimeError(_NOT_STARTED_ERROR)

        # Use cached validator or create new one
        validator = self._get_or_create_realm_validator(realm)

        tracer = _get_tracer()
        if tracer is None:
            return self._validate_and_convert(token, validator)

        # Execute with tracing
        with tracer.start_as_current_span(
            "keycloak.validate_token_for_realm",
            kind=SpanKind.CLIENT,
        ) as span:
            span.set_attribute(_SPAN_REALM, realm)
            span.set_attribute(_SPAN_CLIENT_ID, self._config.client_id)
            span.set_attribute("keycloak.multi_tenant", True)

            try:
                result = self._validate_and_convert(token, validator)
                span.set_attribute(_SPAN_TOKEN_VALID, result.valid)
                if result.valid:
                    span.set_status(Status(StatusCode.OK))
                    if result.user_info:
                        span.set_attribute("keycloak.user.subject", result.user_info.subject)
                else:
                    span.set_status(Status(StatusCode.ERROR, result.error or "Invalid token"))
                return result
            except Exception as e:
                span.set_attribute(_SPAN_TOKEN_VALID, False)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def authenticate_for_realm(
        self,
        credentials: dict[str, Any],
        realm: str,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> str | None:
        """Authenticate against a specific realm.

        This method supports multi-tenancy by allowing authentication
        against any realm on the same Keycloak server.

        Args:
            credentials: Authentication credentials:
                - Password grant: {"username": "...", "password": "..."}
                - Client credentials: {} (uses provided client credentials)
            realm: Target realm for authentication.
            client_id: Client ID for the realm. If None, uses configured client_id.
            client_secret: Client secret for the realm. If None, uses configured secret.

        Returns:
            Access token string if successful, None if authentication fails.

        Raises:
            RuntimeError: If plugin not started.

        Examples:
            >>> # Authenticate user in a different realm
            >>> token = plugin.authenticate_for_realm(
            ...     {"username": "user", "password": "pass"},
            ...     realm="domain-sales",
            ...     client_id="sales-client",
            ...     client_secret="sales-secret",
            ... )
        """
        if not self._started or not self._client:
            raise RuntimeError(_NOT_STARTED_ERROR)

        effective_client_id = client_id or self._config.client_id
        effective_client_secret = (
            client_secret
            if client_secret is not None
            else self._config.client_secret.get_secret_value()
        )

        token_url = f"{self._config.server_url}/realms/{realm}/protocol/openid-connect/token"

        # Determine grant type
        if "username" in credentials and "password" in credentials:
            data = {
                "grant_type": "password",
                "client_id": effective_client_id,
                "client_secret": effective_client_secret,
                "username": credentials["username"],
                "password": credentials["password"],
                "scope": " ".join(self._config.scopes),
            }
        else:
            data = {
                "grant_type": "client_credentials",
                "client_id": effective_client_id,
                "client_secret": effective_client_secret,
                "scope": " ".join(self._config.scopes),
            }

        try:
            response = self._client.post(token_url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                return str(access_token) if access_token else None
            return None
        except httpx.HTTPError:
            return None

    def get_available_realms(self) -> list[str]:
        """Get list of realms the plugin has validators for.

        Returns the configured realm plus any realms that have been
        used for multi-tenant validation.

        Returns:
            List of realm names.
        """
        realms = [self._config.realm]
        for realm in self._realm_validators:
            if realm not in realms:
                realms.append(realm)
        return realms

    def _get_or_create_realm_validator(self, realm: str) -> TokenValidator:
        """Get or create a TokenValidator for a specific realm.

        Args:
            realm: Realm name.

        Returns:
            TokenValidator configured for the realm.
        """
        # Return default validator if realm matches config
        if realm == self._config.realm and self._token_validator:
            return self._token_validator

        # Return cached validator if exists
        if realm in self._realm_validators:
            return self._realm_validators[realm]

        # Create new validator for realm
        base_url = f"{self._config.server_url}/realms/{realm}"
        validator = TokenValidator(
            issuer=base_url,
            audience=self._config.client_id,
            jwks_url=f"{base_url}/protocol/openid-connect/certs",
            verify_ssl=self._config.verify_ssl,
            timeout=self._config.timeout,
        )
        self._realm_validators[realm] = validator
        return validator

    def _extract_roles_from_access_dict(self, access_dict: Any, roles: list[str]) -> None:
        """Extract roles from an access dictionary (realm_access or resource dict).

        Args:
            access_dict: Dictionary containing a 'roles' key.
            roles: List to append extracted roles to (mutated in place).
        """
        if not isinstance(access_dict, dict):
            return
        roles_list = access_dict.get("roles")
        if not isinstance(roles_list, list):
            return
        for role in roles_list:
            if isinstance(role, str):
                roles.append(role)

    def _extract_roles(self, data: dict[str, Any]) -> list[str]:
        """Extract roles from userinfo or token claims.

        Args:
            data: Claims data from userinfo or token.

        Returns:
            List of roles.
        """
        roles: list[str] = []

        # Realm roles
        self._extract_roles_from_access_dict(data.get("realm_access"), roles)

        # Client roles from resource_access
        resource_access = data.get("resource_access")
        if isinstance(resource_access, dict):
            for resource in resource_access.values():
                self._extract_roles_from_access_dict(resource, roles)

        return roles

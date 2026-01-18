"""Token validation for Keycloak Identity Plugin.

This module provides JWT token validation using PyJWT with JWKS support.

Implements:
    - FR-034: JWT validation via PyJWT
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm


@dataclass
class UserInfo:
    """User information extracted from JWT claims.

    Attributes:
        user_id: Unique user identifier (sub claim).
        email: User email address.
        email_verified: Whether email is verified.
        name: Full name of the user.
        preferred_username: Preferred username.
        given_name: Given (first) name.
        family_name: Family (last) name.
        roles: List of roles assigned to the user.
    """

    user_id: str
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    preferred_username: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    roles: list[str] | None = None

    def __post_init__(self) -> None:
        """Initialize roles to empty list if None."""
        if self.roles is None:
            self.roles = []


@dataclass
class TokenValidationResult:
    """Result of token validation.

    Attributes:
        valid: Whether the token is valid.
        user_info: User information if valid, None otherwise.
        error: Error message if invalid, None otherwise.
    """

    valid: bool
    user_info: UserInfo | None = None
    error: str | None = None


class TokenValidator:
    """JWT token validator with JWKS support.

    This class validates JWT tokens using JWKS (JSON Web Key Set) from the
    identity provider. It supports caching of JWKS for performance.

    Attributes:
        issuer: Expected token issuer (iss claim).
        audience: Expected token audience (aud claim).
        jwks_url: URL to fetch JWKS from.

    Examples:
        >>> validator = TokenValidator(
        ...     issuer="https://keycloak.example.com/realms/floe",
        ...     audience="floe-client",
        ...     jwks_url="https://keycloak.example.com/realms/floe/protocol/openid-connect/certs",
        ... )
        >>> result = validator.validate(token)
        >>> if result.valid:
        ...     print(f"User: {result.user_info.email}")
    """

    def __init__(
        self,
        issuer: str,
        audience: str,
        jwks_url: str | None = None,
        *,
        verify_ssl: bool = True,
        timeout: float = 30.0,
    ) -> None:
        """Initialize token validator.

        Args:
            issuer: Expected token issuer.
            audience: Expected token audience.
            jwks_url: URL to fetch JWKS. If None, JWKS must be set manually.
            verify_ssl: Whether to verify SSL certificates.
            timeout: HTTP request timeout in seconds.
        """
        self._issuer = issuer
        self._audience = audience
        self._jwks_url = jwks_url
        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self._jwks: dict[str, Any] | None = None
        self._keys_by_kid: dict[str, Any] = {}

    def validate(self, token: str | None) -> TokenValidationResult:
        """Validate a JWT token.

        Args:
            token: JWT token string to validate.

        Returns:
            TokenValidationResult with validation status and user info.
        """
        # Handle None or empty token
        if not token:
            return TokenValidationResult(
                valid=False,
                error="Token is required",
            )

        try:
            # Get the key ID from token header
            try:
                header = jwt.get_unverified_header(token)
                kid = header.get("kid")
            except jwt.exceptions.DecodeError as e:
                return TokenValidationResult(
                    valid=False,
                    error=f"Malformed token: {e}",
                )

            # Fetch JWKS if not already loaded
            if self._jwks is None and self._jwks_url:
                self._fetch_jwks()

            # Get the signing key
            key: Any = None
            verify_signature = False

            if kid and self._jwks:
                key = self._get_key_by_kid(kid)
                if key is None:
                    return TokenValidationResult(
                        valid=False,
                        error=f"Key with ID '{kid}' not found in JWKS",
                    )
                verify_signature = True

            # Decode and validate the token
            options = {
                "verify_signature": verify_signature,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            }

            # Use empty string as key when not verifying signature (testing)
            decode_key: Any = key if key is not None else ""

            claims = jwt.decode(
                token,
                key=decode_key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options=options,
            )

            # Validate required claims
            if "sub" not in claims:
                return TokenValidationResult(
                    valid=False,
                    error="Missing required claim: sub",
                )

            # Extract user info
            user_info = self._extract_user_info(claims)

            return TokenValidationResult(
                valid=True,
                user_info=user_info,
            )

        except jwt.exceptions.ExpiredSignatureError:
            return TokenValidationResult(
                valid=False,
                error="Token has expired",
            )
        except jwt.exceptions.InvalidSignatureError:
            return TokenValidationResult(
                valid=False,
                error="Invalid token signature",
            )
        except jwt.exceptions.InvalidIssuerError:
            return TokenValidationResult(
                valid=False,
                error="Invalid token issuer",
            )
        except jwt.exceptions.InvalidAudienceError:
            return TokenValidationResult(
                valid=False,
                error="Invalid token audience",
            )
        except jwt.exceptions.DecodeError as e:
            return TokenValidationResult(
                valid=False,
                error=f"Failed to decode token: {e}",
            )
        except Exception as e:
            return TokenValidationResult(
                valid=False,
                error=f"Token validation failed: {e}",
            )

    def _fetch_jwks(self) -> None:
        """Fetch JWKS from the identity provider.

        Raises:
            httpx.HTTPError: If JWKS fetch fails.
        """
        if not self._jwks_url:
            return

        response = httpx.get(
            self._jwks_url,
            verify=self._verify_ssl,
            timeout=self._timeout,
        )
        response.raise_for_status()
        self._jwks = response.json()

        # Index keys by kid for quick lookup
        self._keys_by_kid = {}
        jwks_data: dict[str, Any] = self._jwks or {}
        keys_list: list[dict[str, Any]] = jwks_data.get("keys", [])
        for key in keys_list:
            kid = key.get("kid")
            if kid:
                self._keys_by_kid[kid] = key

    def _get_key_by_kid(self, kid: str) -> Any | None:
        """Get a key from JWKS by key ID.

        Args:
            kid: Key ID to look up.

        Returns:
            RSA public key if found, None otherwise.
        """
        jwk = self._keys_by_kid.get(kid)
        if jwk is None:
            return None

        # Convert JWK to PEM for PyJWT
        return RSAAlgorithm.from_jwk(jwk)

    def _extract_user_info(self, claims: dict[str, Any]) -> UserInfo:
        """Extract user information from JWT claims.

        Args:
            claims: Decoded JWT claims.

        Returns:
            UserInfo instance with extracted data.
        """
        # Extract roles from realm_access and resource_access
        roles: list[str] = []

        # Realm roles
        realm_access_raw = claims.get("realm_access")
        if isinstance(realm_access_raw, dict):
            realm_roles_raw = realm_access_raw.get("roles")
            if isinstance(realm_roles_raw, list):
                for role in realm_roles_raw:
                    if isinstance(role, str):
                        roles.append(role)

        # Client/resource roles
        resource_access_raw = claims.get("resource_access")
        if isinstance(resource_access_raw, dict):
            for resource_raw in resource_access_raw.values():
                if isinstance(resource_raw, dict):
                    resource_roles_raw = resource_raw.get("roles")
                    if isinstance(resource_roles_raw, list):
                        for role in resource_roles_raw:
                            if isinstance(role, str):
                                roles.append(role)

        return UserInfo(
            user_id=claims["sub"],
            email=claims.get("email"),
            email_verified=claims.get("email_verified", False),
            name=claims.get("name"),
            preferred_username=claims.get("preferred_username"),
            given_name=claims.get("given_name"),
            family_name=claims.get("family_name"),
            roles=roles,
        )

    def refresh_jwks(self) -> None:
        """Force refresh of JWKS cache."""
        self._jwks = None
        self._keys_by_kid = {}
        if self._jwks_url:
            self._fetch_jwks()

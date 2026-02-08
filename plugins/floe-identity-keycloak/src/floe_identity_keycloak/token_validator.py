"""Token validation for Keycloak Identity Plugin.

This module provides JWT token validation using PyJWT with JWKS support.

Implements:
    - FR-034: JWT validation via PyJWT

Security:
    - Signature verification is ALWAYS required (fail-closed)
    - Algorithm validation prevents algorithm confusion attacks
    - kid header required to prevent key ambiguity attacks
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

# SECURITY: Allowed signing algorithms (whitelist approach)
# Only RS256 is allowed to prevent algorithm confusion attacks
_ALLOWED_ALGORITHMS: frozenset[str] = frozenset({"RS256"})


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

        SECURITY: This method implements fail-closed validation:
        - Signature verification is ALWAYS required
        - kid header is REQUIRED to prevent key ambiguity
        - Algorithm is validated against a whitelist
        - JWKS must be available for signature verification

        Args:
            token: JWT token string to validate.

        Returns:
            TokenValidationResult with validation status and user info.
        """
        # Handle None or empty token
        if not token:
            return TokenValidationResult(valid=False, error="Token is required")

        try:
            return self._validate_token_internal(token)
        except jwt.exceptions.PyJWTError as e:
            return self._handle_jwt_error(e)
        except Exception as e:
            return TokenValidationResult(valid=False, error=f"Token validation failed: {e}")

    def _validate_token_internal(self, token: str) -> TokenValidationResult:
        """Internal token validation logic.

        Args:
            token: Non-empty JWT token string.

        Returns:
            TokenValidationResult with validation status and user info.
        """
        # Extract and validate header
        header_result = self._validate_token_header(token)
        if header_result is not None:
            return header_result

        # Header validation passed, so kid is guaranteed to exist
        header = jwt.get_unverified_header(token)
        kid: str = header["kid"]  # Validated in _validate_token_header

        # Ensure JWKS is available
        jwks_result = self._ensure_jwks_available()
        if jwks_result is not None:
            return jwks_result

        # Get the signing key
        key = self._get_key_by_kid(kid)
        if key is None:
            return TokenValidationResult(
                valid=False,
                error=f"Key with ID '{kid}' not found in JWKS",
            )

        # Decode and validate the token
        claims = self._decode_token(token, key)

        # Extract user info
        user_info = self._extract_user_info(claims)
        return TokenValidationResult(valid=True, user_info=user_info)

    def _validate_token_header(self, token: str) -> TokenValidationResult | None:
        """Validate token header for kid and algorithm.

        SECURITY: get_unverified_header() is safe here.
        We ONLY extract `kid` and `alg` to:
          1. Select the correct key from JWKS for signature verification
          2. Validate algorithm against whitelist before decoding

        Args:
            token: JWT token string.

        Returns:
            TokenValidationResult if validation fails, None if OK.
        """
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            alg = header.get("alg")
        except jwt.exceptions.DecodeError as e:
            return TokenValidationResult(valid=False, error=f"Malformed token: {e}")

        # SECURITY: Require kid header to prevent key ambiguity attacks
        if not kid:
            return TokenValidationResult(
                valid=False,
                error="Token missing required 'kid' header",
            )

        # SECURITY: Validate algorithm before decoding to prevent
        # algorithm confusion attacks (e.g., "none" or "HS256")
        if alg not in _ALLOWED_ALGORITHMS:
            return TokenValidationResult(
                valid=False,
                error=f"Algorithm '{alg}' not allowed. Allowed: {sorted(_ALLOWED_ALGORITHMS)}",
            )

        return None

    def _ensure_jwks_available(self) -> TokenValidationResult | None:
        """Ensure JWKS is available for signature verification.

        Returns:
            TokenValidationResult if JWKS unavailable, None if OK.
        """
        # Fetch JWKS if not already loaded
        if self._jwks is None and self._jwks_url:
            try:
                self._fetch_jwks()
            except Exception as e:
                return TokenValidationResult(
                    valid=False,
                    error=f"Failed to fetch JWKS: {e}",
                )

        # SECURITY: Require JWKS to be available - never skip signature verification
        if not self._jwks:
            return TokenValidationResult(
                valid=False,
                error="JWKS not available for signature verification",
            )

        return None

    def _decode_token(self, token: str, key: Any) -> dict[str, Any]:
        """Decode and validate JWT token.

        SECURITY: verify_signature is ALWAYS True - never disable.

        Args:
            token: JWT token string.
            key: RSA public key for verification.

        Returns:
            Decoded claims dictionary.
        """
        options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "verify_aud": True,
            "verify_iss": True,
            "require": ["exp", "iat", "iss", "aud", "sub"],
        }

        claims: dict[str, Any] = jwt.decode(
            token,
            key=key,
            algorithms=list(_ALLOWED_ALGORITHMS),
            audience=self._audience,
            issuer=self._issuer,
            options=options,
        )
        return claims

    def _handle_jwt_error(self, error: jwt.exceptions.PyJWTError) -> TokenValidationResult:
        """Handle JWT-specific errors with appropriate messages.

        Args:
            error: PyJWT exception.

        Returns:
            TokenValidationResult with appropriate error message.
        """
        error_messages: dict[type, str] = {
            jwt.exceptions.ExpiredSignatureError: "Token has expired",
            jwt.exceptions.InvalidSignatureError: "Invalid token signature",
            jwt.exceptions.InvalidIssuerError: "Invalid token issuer",
            jwt.exceptions.InvalidAudienceError: "Invalid token audience",
        }

        error_type = type(error)
        if error_type in error_messages:
            return TokenValidationResult(valid=False, error=error_messages[error_type])

        if isinstance(error, jwt.exceptions.MissingRequiredClaimError):
            return TokenValidationResult(valid=False, error=f"Missing required claim: {error}")

        if isinstance(error, jwt.exceptions.DecodeError):
            return TokenValidationResult(valid=False, error=f"Failed to decode token: {error}")

        return TokenValidationResult(valid=False, error=f"Token validation failed: {error}")

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

    def _collect_roles_from_access_dict(self, access_dict: Any, roles: list[str]) -> None:
        """Extract roles from an access dictionary and append to list.

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
        self._collect_roles_from_access_dict(claims.get("realm_access"), roles)

        # Client/resource roles
        resource_access_raw = claims.get("resource_access")
        if isinstance(resource_access_raw, dict):
            for resource_raw in resource_access_raw.values():
                self._collect_roles_from_access_dict(resource_raw, roles)

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

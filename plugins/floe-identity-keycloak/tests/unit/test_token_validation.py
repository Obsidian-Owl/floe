"""Unit tests for Keycloak token validation.

Task: T058
Requirements: 7A-FR-034 (JWT validation via PyJWT)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# Test RSA key pair for JWT signing (test purposes only)
# This is a 2048-bit RSA key pair generated for testing
TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MQ/23aaAvPKaXsqu
IG0Bg3P+YIeG6aXMiP1qGDdSVJB4qTzE9L5Lc6lYH0NJW0lf04KF1KxKhdP9cHPj
IrGhHaXNgNbHCpd/G/xGHMxwTMdA6tJdz0Q5Dh6RM0jgYJNaV7j4RVsJdMABuU3T
Uq0GGQe4HBOfyLdEy4D1AJiAoXrBdRlf9HEtk2A7m8fFkb3JJYqx7qf0S0s6IVVz
1Ns2CkLDY4qVvzL2ZJumNOPzPvfYCjCuN6qKkPsLLwA7sJThIkzFLz7k5tKxMqk8
O7c1/6J4YWnJKjA7WEkF0vqKSZh6MHZ7JQv9dwIDAQABAoIBAFG0G1R7bHvKPL1E
gDVsT0EBR+0nCOdUwlWANFrpEB2HpFyRCfz2pQOvF7dCsYvmFJ3I2K66sVgisOlg
B9ARVfgRvMXI4X/avm4pgf3xA9oHjH2LI9OGBGGTHn4FAzPhK/xPvVi9+h1Fv+hN
m7bDGEQeEj3xj0t5qT8wJ0S3y/sBbB2k8bVs2SJPX3N/1T7tQjHf0cHZ9YTEuPx+
jCfT+3zPFnKrpmrQrBcQPVx+VNLzjD4DVNM1dGfPzAjMfb2kBJ5EfQvV4EpGX2wx
+Vj+f1E1EZVHHfdyWU/sPYmT/r5LQvp7Z0V6EJVLuToNi5PXQB3RJxPMJSiZ8D7g
bJDcGwECgYEA7nGBt3Zc3SbePk0P2WDYyADsPj5xXiNOJfrE/BkA1dWdFqI8QTNY
xLhW9YuH3F9xDC/aKU1L/AO1Z9KiN27lkCHLf78l/H7CnHpVuDLu5sCkXfvYqjOx
8aHvPTDyNj9b+sXh5XYEulhXzsvGNkCl5NBuGOJEhN1ks8j0XqJ7xTcCgYEA4P3p
F3xt4fJzT5Qchbf8Rwe/sYe4Kp7d3rHBG8Q5JNUkGnrL/E7jrVsRoWNBm/oT3RYx
6+j9yCAJ0H3wLcWMq5j/rPQK8SbQAZJE31APmJJbL0bXq7/xpXg0fD8VLvLoNLOU
iq8cRlB9iQDL2IsMPyF6Y7xy5VkH2fPK9oJvFwECgYBxNMi8i5rfy5b/CkK0lPNr
pMXCcCnAHCcx/fdQ5K/U7Y6H7AxhV5Lkqh1S1qCjUCkMClLpvQJ85FpLef+C1p8T
TBGeqn/yPZG2X/VqKEXJF0l4u1p8q3w4R2EQFEF3wPT7E/p6V8P5VBN+D5UXNLEF
L0F3C7N1f3K5jKPPkOVNtwKBgD3K3K2u8qUd0L4g7z3T2CIw1P1HMk6n7C0R4Klu
L1w/c3pBUkJPL4L4lPxRbGS9Q+I5b4sN5QVKA/e2FrXwM/FXVK0YlCkJAHT2q8Mw
gu7Kxm7BnE2VAYVuBnpVTTBNPP0vXjKGEo9fH9Ln5w3nGE5fNmh3L9P+H0TNBQPB
5QABAoGBAK7r3J2bvtpdxR2P8FMQ4pWm8C9v7B9KDe1Cfjyv0A1Rj1LIhD2/D3R0
nMT5Lkk/iG1F3w/8tFc5QWLP1g5sXB8XKEX3SXkCdAVF4J2C6mE8j2Z/c5T7LSQQ
wXLw8Pw0XKP8B0aaOIbr8r0dHw0F1JKQk1d8R1j5lM8qQ0dSNL7T
-----END RSA PRIVATE KEY-----"""

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Z3VS5JJcds3xfn/ygWy
F8PbnGy0AHB7MQ/23aaAvPKaXsquIG0Bg3P+YIeG6aXMiP1qGDdSVJB4qTzE9L5L
c6lYH0NJW0lf04KF1KxKhdP9cHPjIrGhHaXNgNbHCpd/G/xGHMxwTMdA6tJdz0Q5
Dh6RM0jgYJNaV7j4RVsJdMABuU3TUq0GGQe4HBOfyLdEy4D1AJiAoXrBdRlf9HEt
k2A7m8fFkb3JJYqx7qf0S0s6IVVz1Ns2CkLDY4qVvzL2ZJumNOPzPvfYCjCuN6qK
kPsLLwA7sJThIkzFLz7k5tKxMqk8O7c1/6J4YWnJKjA7WEkF0vqKSZh6MHZ7JQv9
dwIDAQAB
-----END PUBLIC KEY-----"""

# Test key ID for JWKS
TEST_KEY_ID = "test-key-id"


@pytest.fixture
def mock_jwks_response() -> dict[str, Any]:
    """Create a mock JWKS response.

    Returns:
        Dict representing JWKS with our test public key.
    """
    # In real implementation, we'd convert PEM to JWK format
    # For tests, we return a mock structure
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "kid": TEST_KEY_ID,
                "alg": "RS256",
                "n": "0Z3VS5JJcds3xfn_ygWyF8PbnGy0AHB7MQ_23aaAvPKaXsquIG0Bg3P-YIeG6aXMiP1qGDdSVJB4qTzE9L5Lc6lYH0NJW0lf04KF1KxKhdP9cHPjIrGhHaXNgNbHCpd_G_xGHMxwTMdA6tJdz0Q5Dh6RM0jgYJNaV7j4RVsJdMABuU3TUq0GGQe4HBOfyLdEy4D1AJiAoXrBdRlf9HEtk2A7m8fFkb3JJYqx7qf0S0s6IVVz1Ns2CkLDY4qVvzL2ZJumNOPzPvfYCjCuN6qKkPsLLwA7sJThIkzFLz7k5tKxMqk8O7c1_6J4YWnJKjA7WEkF0vqKSZh6MHZ7JQv9dw",
                "e": "AQAB",
            }
        ]
    }


@pytest.fixture
def valid_token_claims() -> dict[str, Any]:
    """Create valid JWT claims.

    Returns:
        Dict with standard OIDC claims.
    """
    now = int(time.time())
    return {
        "iss": "https://keycloak.example.com/realms/floe",
        "sub": "user-123-456-789",
        "aud": "floe-client",
        "exp": now + 3600,  # 1 hour from now
        "iat": now,
        "nbf": now,
        "jti": "token-id-abc123",
        "typ": "Bearer",
        "azp": "floe-client",
        "email": "test@example.com",
        "email_verified": True,
        "name": "Test User",
        "preferred_username": "testuser",
        "given_name": "Test",
        "family_name": "User",
        "realm_access": {"roles": ["user", "admin"]},
        "resource_access": {"floe-client": {"roles": ["data-engineer"]}},
    }


@pytest.fixture
def expired_token_claims() -> dict[str, Any]:
    """Create expired JWT claims.

    Returns:
        Dict with expired claims.
    """
    now = int(time.time())
    return {
        "iss": "https://keycloak.example.com/realms/floe",
        "sub": "user-123-456-789",
        "aud": "floe-client",
        "exp": now - 3600,  # 1 hour ago (expired)
        "iat": now - 7200,  # 2 hours ago
        "email": "test@example.com",
        "name": "Test User",
    }


class TestTokenValidationValid:
    """Tests for valid token scenarios."""

    @pytest.mark.requirement("7A-FR-034")
    def test_valid_token_returns_valid_true(
        self,
        valid_token_claims: dict[str, Any],
        mock_jwks_response: dict[str, Any],
    ) -> None:
        """Test that a valid token returns valid=True with user info."""
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            # Mock the decode to return our claims
            mock_jwt.decode.return_value = valid_token_claims
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )
            # Inject mock JWKS and populate keys_by_kid
            validator._jwks = mock_jwks_response
            validator._keys_by_kid = {TEST_KEY_ID: mock_jwks_response["keys"][0]}

            result = validator.validate("mock.jwt.token")

            assert result.valid is True
            assert result.user_info is not None
            assert result.user_info.user_id == "user-123-456-789"
            assert result.user_info.email == "test@example.com"
            assert result.error is None

    @pytest.mark.requirement("7A-FR-034")
    def test_valid_token_extracts_roles(
        self,
        valid_token_claims: dict[str, Any],
        mock_jwks_response: dict[str, Any],
    ) -> None:
        """Test that roles are correctly extracted from token."""
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            mock_jwt.decode.return_value = valid_token_claims
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )
            # Inject mock JWKS and populate keys_by_kid
            validator._jwks = mock_jwks_response
            validator._keys_by_kid = {TEST_KEY_ID: mock_jwks_response["keys"][0]}

            result = validator.validate("mock.jwt.token")

            assert result.valid is True
            assert result.user_info is not None
            assert "user" in result.user_info.roles
            assert "admin" in result.user_info.roles

    @pytest.mark.requirement("7A-FR-034")
    def test_valid_token_extracts_client_roles(
        self,
        valid_token_claims: dict[str, Any],
        mock_jwks_response: dict[str, Any],
    ) -> None:
        """Test that client-specific roles are extracted."""
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            mock_jwt.decode.return_value = valid_token_claims
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )
            # Inject mock JWKS and populate keys_by_kid
            validator._jwks = mock_jwks_response
            validator._keys_by_kid = {TEST_KEY_ID: mock_jwks_response["keys"][0]}

            result = validator.validate("mock.jwt.token")

            assert result.valid is True
            # Client roles should also be included
            assert "data-engineer" in result.user_info.roles


class TestTokenValidationExpired:
    """Tests for expired token scenarios."""

    @pytest.mark.requirement("7A-FR-034")
    def test_expired_token_returns_valid_false(
        self,
        expired_token_claims: dict[str, Any],
        mock_jwks_response: dict[str, Any],
    ) -> None:
        """Test that an expired token returns valid=False with error."""
        from floe_identity_keycloak.token_validator import TokenValidator

        import jwt as real_jwt

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            # Use real exception classes for proper exception handling
            mock_jwt.exceptions = real_jwt.exceptions

            mock_jwt.decode.side_effect = real_jwt.exceptions.ExpiredSignatureError(
                "Token has expired"
            )
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )
            # Inject mock JWKS and populate keys_by_kid
            validator._jwks = mock_jwks_response
            validator._keys_by_kid = {TEST_KEY_ID: mock_jwks_response["keys"][0]}

            result = validator.validate("expired.jwt.token")

            assert result.valid is False
            assert result.user_info is None
            assert result.error is not None
            assert "expired" in result.error.lower()


class TestTokenValidationInvalid:
    """Tests for invalid token scenarios."""

    @pytest.mark.requirement("7A-FR-034")
    def test_invalid_signature_returns_valid_false(
        self,
        mock_jwks_response: dict[str, Any],
    ) -> None:
        """Test that invalid signature returns valid=False."""
        from floe_identity_keycloak.token_validator import TokenValidator

        import jwt as real_jwt

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            # Use real exception classes for proper exception handling
            mock_jwt.exceptions = real_jwt.exceptions

            mock_jwt.decode.side_effect = real_jwt.exceptions.InvalidSignatureError(
                "Signature verification failed"
            )
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )
            # Inject mock JWKS and populate keys_by_kid
            validator._jwks = mock_jwks_response
            validator._keys_by_kid = {TEST_KEY_ID: mock_jwks_response["keys"][0]}

            result = validator.validate("invalid.jwt.token")

            assert result.valid is False
            assert result.error is not None
            assert "signature" in result.error.lower() or "invalid" in result.error.lower()

    @pytest.mark.requirement("7A-FR-034")
    def test_missing_required_claims_returns_valid_false(
        self,
        mock_jwks_response: dict[str, Any],
    ) -> None:
        """Test that missing required claims returns valid=False."""
        from floe_identity_keycloak.token_validator import TokenValidator

        # Token missing 'sub' claim
        incomplete_claims = {
            "iss": "https://keycloak.example.com/realms/floe",
            "aud": "floe-client",
            "exp": int(time.time()) + 3600,
            # Missing 'sub' - required
        }

        import jwt as real_jwt

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            # Use real exception classes for proper exception handling
            mock_jwt.exceptions = real_jwt.exceptions

            # Simulate MissingRequiredClaimError when 'sub' is required
            mock_jwt.decode.side_effect = real_jwt.exceptions.MissingRequiredClaimError(
                "sub"
            )
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )
            # Inject mock JWKS and populate keys_by_kid
            validator._jwks = mock_jwks_response
            validator._keys_by_kid = {TEST_KEY_ID: mock_jwks_response["keys"][0]}

            result = validator.validate("incomplete.jwt.token")

            assert result.valid is False
            assert result.error is not None

    @pytest.mark.requirement("7A-FR-034")
    def test_wrong_issuer_returns_valid_false(
        self,
        valid_token_claims: dict[str, Any],
        mock_jwks_response: dict[str, Any],
    ) -> None:
        """Test that wrong issuer returns valid=False."""
        from floe_identity_keycloak.token_validator import TokenValidator

        import jwt as real_jwt

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            # Use real exception classes for proper exception handling
            mock_jwt.exceptions = real_jwt.exceptions

            mock_jwt.decode.side_effect = real_jwt.exceptions.InvalidIssuerError(
                "Invalid issuer"
            )
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            validator = TokenValidator(
                issuer="https://different-issuer.com",
                audience="floe-client",
            )
            # Inject mock JWKS and populate keys_by_kid
            validator._jwks = mock_jwks_response
            validator._keys_by_kid = {TEST_KEY_ID: mock_jwks_response["keys"][0]}

            result = validator.validate("wrong.issuer.token")

            assert result.valid is False
            assert result.error is not None

    @pytest.mark.requirement("7A-FR-034")
    def test_wrong_audience_returns_valid_false(
        self,
        valid_token_claims: dict[str, Any],
        mock_jwks_response: dict[str, Any],
    ) -> None:
        """Test that wrong audience returns valid=False."""
        from floe_identity_keycloak.token_validator import TokenValidator

        import jwt as real_jwt

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            # Use real exception classes for proper exception handling
            mock_jwt.exceptions = real_jwt.exceptions

            mock_jwt.decode.side_effect = real_jwt.exceptions.InvalidAudienceError(
                "Invalid audience"
            )
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="different-client",
            )
            # Inject mock JWKS and populate keys_by_kid
            validator._jwks = mock_jwks_response
            validator._keys_by_kid = {TEST_KEY_ID: mock_jwks_response["keys"][0]}

            result = validator.validate("wrong.audience.token")

            assert result.valid is False
            assert result.error is not None


class TestTokenValidationMalformed:
    """Tests for malformed token scenarios."""

    @pytest.mark.requirement("7A-FR-034")
    def test_malformed_token_returns_valid_false(self) -> None:
        """Test that malformed token returns valid=False."""
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            from jwt.exceptions import DecodeError

            mock_jwt.decode.side_effect = DecodeError("Not enough segments")
            mock_jwt.get_unverified_header.side_effect = DecodeError("Not enough segments")
            mock_jwt.exceptions = MagicMock()
            mock_jwt.exceptions.DecodeError = DecodeError

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )

            result = validator.validate("not-a-valid-jwt")

            assert result.valid is False
            assert result.error is not None

    @pytest.mark.requirement("7A-FR-034")
    def test_empty_token_returns_valid_false(self) -> None:
        """Test that empty token returns valid=False."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        result = validator.validate("")

        assert result.valid is False
        assert result.error is not None

    @pytest.mark.requirement("7A-FR-034")
    def test_none_token_returns_valid_false(self) -> None:
        """Test that None token returns valid=False."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        result = validator.validate(None)  # type: ignore[arg-type]

        assert result.valid is False
        assert result.error is not None


class TestTokenValidatorJWKS:
    """Tests for JWKS fetching and caching."""

    @pytest.mark.requirement("7A-FR-034")
    def test_jwks_fetched_on_first_validation(
        self,
        mock_jwks_response: dict[str, Any],
        valid_token_claims: dict[str, Any],
    ) -> None:
        """Test that JWKS is fetched on first validation."""
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            mock_jwt.decode.return_value = valid_token_claims
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            with patch("httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.json.return_value = mock_jwks_response
                mock_response.raise_for_status = MagicMock()
                mock_get.return_value = mock_response

                validator = TokenValidator(
                    issuer="https://keycloak.example.com/realms/floe",
                    audience="floe-client",
                    jwks_url="https://keycloak.example.com/realms/floe/protocol/openid-connect/certs",
                )

                # Trigger validation (which should fetch JWKS)
                validator.validate("test.token")

                mock_get.assert_called_once()

    @pytest.mark.requirement("7A-FR-034")
    def test_jwks_cached_after_fetch(
        self,
        mock_jwks_response: dict[str, Any],
        valid_token_claims: dict[str, Any],
    ) -> None:
        """Test that JWKS is cached after initial fetch."""
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            mock_jwt.decode.return_value = valid_token_claims
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            with patch("httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.json.return_value = mock_jwks_response
                mock_response.raise_for_status = MagicMock()
                mock_get.return_value = mock_response

                validator = TokenValidator(
                    issuer="https://keycloak.example.com/realms/floe",
                    audience="floe-client",
                    jwks_url="https://keycloak.example.com/realms/floe/protocol/openid-connect/certs",
                )

                # First validation
                validator.validate("test.token1")
                # Second validation
                validator.validate("test.token2")

                # JWKS should only be fetched once (cached)
                assert mock_get.call_count == 1


class TestTokenValidatorKeyLookup:
    """Tests for key lookup in JWKS."""

    @pytest.mark.requirement("7A-FR-034")
    def test_key_not_found_returns_valid_false(
        self,
        mock_jwks_response: dict[str, Any],
    ) -> None:
        """Test that unknown key ID returns valid=False."""
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            # Return a different key ID than what's in JWKS (with valid algorithm)
            mock_jwt.get_unverified_header.return_value = {
                "kid": "unknown-key-id",
                "alg": "RS256",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )
            validator._jwks = mock_jwks_response

            result = validator.validate("token.with.unknown.key")

            assert result.valid is False
            assert result.error is not None
            assert "key" in result.error.lower()


class TestTokenValidationSecurity:
    """Tests for security-critical validation scenarios.

    These tests verify the fail-closed security model:
    - Missing kid header must be rejected
    - Disallowed algorithms must be rejected
    - JWKS must be available for validation
    """

    @pytest.mark.requirement("7A-FR-034")
    def test_missing_kid_header_rejected(self) -> None:
        """SECURITY: Token without kid header must be rejected.

        This prevents key ambiguity attacks where an attacker submits
        a token without specifying which key signed it.
        """
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            # Token with missing kid header
            mock_jwt.get_unverified_header.return_value = {"alg": "RS256"}

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )

            result = validator.validate("token.without.kid")

            assert result.valid is False
            assert result.error is not None
            assert "kid" in result.error.lower()

    @pytest.mark.requirement("7A-FR-034")
    def test_none_algorithm_rejected(self) -> None:
        """SECURITY: 'none' algorithm must be rejected.

        The 'none' algorithm is a well-known JWT attack vector that
        allows unsigned tokens to be accepted as valid.
        """
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            # Token with 'none' algorithm attack
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "none",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )

            result = validator.validate("forged.token.none.alg")

            assert result.valid is False
            assert result.error is not None
            assert "algorithm" in result.error.lower()
            assert "none" in result.error.lower()

    @pytest.mark.requirement("7A-FR-034")
    def test_hs256_algorithm_rejected(self) -> None:
        """SECURITY: HS256 algorithm must be rejected.

        Algorithm confusion attacks can occur when a server accepts
        HS256 (symmetric) when it expects RS256 (asymmetric). The
        attacker can sign with the public key as HMAC secret.
        """
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            # Token with HS256 algorithm confusion attack
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "HS256",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )

            result = validator.validate("forged.token.hs256.alg")

            assert result.valid is False
            assert result.error is not None
            assert "algorithm" in result.error.lower()
            assert "HS256" in result.error

    @pytest.mark.requirement("7A-FR-034")
    def test_jwks_not_available_rejected(self) -> None:
        """SECURITY: Token must be rejected when JWKS is not available.

        Fail-closed behavior: if we cannot verify the signature, we
        must reject the token rather than accepting it unverified.
        """
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
                # No JWKS URL provided
            )
            # JWKS is not set
            validator._jwks = None

            result = validator.validate("token.without.jwks")

            assert result.valid is False
            assert result.error is not None
            assert "jwks" in result.error.lower()

    @pytest.mark.requirement("7A-FR-034")
    def test_jwks_fetch_failure_rejected(
        self,
        mock_jwks_response: dict[str, Any],
    ) -> None:
        """SECURITY: Token must be rejected when JWKS fetch fails.

        If we cannot retrieve the signing keys, we cannot verify
        signatures and must reject the token.
        """
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS256",
            }

            with patch("httpx.get") as mock_get:
                # Simulate JWKS fetch failure
                mock_get.side_effect = Exception("Connection refused")

                validator = TokenValidator(
                    issuer="https://keycloak.example.com/realms/floe",
                    audience="floe-client",
                    jwks_url="https://keycloak.example.com/realms/floe/protocol/openid-connect/certs",
                )

                result = validator.validate("token.with.fetch.failure")

                assert result.valid is False
                assert result.error is not None
                assert "jwks" in result.error.lower() or "fetch" in result.error.lower()

    @pytest.mark.requirement("7A-FR-034")
    def test_rs512_algorithm_rejected(self) -> None:
        """SECURITY: Only explicitly allowed algorithms are accepted.

        Even valid RSA algorithms like RS512 should be rejected if
        not in the explicit whitelist. This follows the principle
        of least privilege for cryptographic operations.
        """
        from floe_identity_keycloak.token_validator import TokenValidator

        with patch("floe_identity_keycloak.token_validator.jwt") as mock_jwt:
            # Token with RS512 (valid RSA but not whitelisted)
            mock_jwt.get_unverified_header.return_value = {
                "kid": TEST_KEY_ID,
                "alg": "RS512",
            }

            validator = TokenValidator(
                issuer="https://keycloak.example.com/realms/floe",
                audience="floe-client",
            )

            result = validator.validate("token.rs512.alg")

            assert result.valid is False
            assert result.error is not None
            assert "algorithm" in result.error.lower()

"""Unit tests for UserInfo extraction from JWT claims.

Task: T059
Requirements: 7A-FR-033 (User information extraction from OIDC claims)
"""

from __future__ import annotations

from typing import Any

import pytest


class TestUserInfoExtraction:
    """Tests for extracting user info from standard claims."""

    @pytest.mark.requirement("7A-FR-033")
    def test_extract_subject_from_claims(self) -> None:
        """Test extraction of subject (user_id) from claims."""
        from floe_identity_keycloak.token_validator import TokenValidator, UserInfo

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-abc-123-456",
            "email": "test@example.com",
        }

        user_info = validator._extract_user_info(claims)

        assert user_info.user_id == "user-abc-123-456"

    @pytest.mark.requirement("7A-FR-033")
    def test_extract_email_from_claims(self) -> None:
        """Test extraction of email from claims."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "email": "user@example.com",
            "email_verified": True,
        }

        user_info = validator._extract_user_info(claims)

        assert user_info.email == "user@example.com"
        assert user_info.email_verified is True

    @pytest.mark.requirement("7A-FR-033")
    def test_extract_name_fields_from_claims(self) -> None:
        """Test extraction of name fields from claims."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "name": "John Doe",
            "given_name": "John",
            "family_name": "Doe",
            "preferred_username": "johnd",
        }

        user_info = validator._extract_user_info(claims)

        assert user_info.name == "John Doe"
        assert user_info.given_name == "John"
        assert user_info.family_name == "Doe"
        assert user_info.preferred_username == "johnd"


class TestUserInfoRoleExtraction:
    """Tests for extracting roles from Keycloak claims."""

    @pytest.mark.requirement("7A-FR-033")
    def test_extract_roles_from_realm_access(self) -> None:
        """Test extraction of roles from realm_access claim."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "realm_access": {
                "roles": ["user", "admin", "developer"],
            },
        }

        user_info = validator._extract_user_info(claims)

        assert "user" in user_info.roles
        assert "admin" in user_info.roles
        assert "developer" in user_info.roles

    @pytest.mark.requirement("7A-FR-033")
    def test_extract_roles_from_resource_access(self) -> None:
        """Test extraction of roles from resource_access claim."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "resource_access": {
                "floe-client": {
                    "roles": ["data-engineer", "viewer"],
                },
                "other-client": {
                    "roles": ["operator"],
                },
            },
        }

        user_info = validator._extract_user_info(claims)

        assert "data-engineer" in user_info.roles
        assert "viewer" in user_info.roles
        assert "operator" in user_info.roles

    @pytest.mark.requirement("7A-FR-033")
    def test_extract_combined_realm_and_resource_roles(self) -> None:
        """Test extraction of roles from both realm_access and resource_access."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "realm_access": {
                "roles": ["user"],
            },
            "resource_access": {
                "floe-client": {
                    "roles": ["data-engineer"],
                },
            },
        }

        user_info = validator._extract_user_info(claims)

        # Both realm and resource roles should be present
        assert "user" in user_info.roles
        assert "data-engineer" in user_info.roles


class TestUserInfoMissingClaims:
    """Tests for handling missing optional claims."""

    @pytest.mark.requirement("7A-FR-033")
    def test_handle_missing_email(self) -> None:
        """Test handling of missing email claim."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            # No email claim
        }

        user_info = validator._extract_user_info(claims)

        assert user_info.user_id == "user-123"
        assert user_info.email is None

    @pytest.mark.requirement("7A-FR-033")
    def test_handle_missing_name_fields(self) -> None:
        """Test handling of missing name fields."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "email": "test@example.com",
            # No name fields
        }

        user_info = validator._extract_user_info(claims)

        assert user_info.name is None
        assert user_info.given_name is None
        assert user_info.family_name is None
        assert user_info.preferred_username is None

    @pytest.mark.requirement("7A-FR-033")
    def test_handle_missing_realm_access(self) -> None:
        """Test handling of missing realm_access claim."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            # No realm_access
        }

        user_info = validator._extract_user_info(claims)

        assert user_info.roles == []

    @pytest.mark.requirement("7A-FR-033")
    def test_handle_missing_resource_access(self) -> None:
        """Test handling of missing resource_access claim."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "realm_access": {
                "roles": ["user"],
            },
            # No resource_access
        }

        user_info = validator._extract_user_info(claims)

        assert user_info.roles == ["user"]

    @pytest.mark.requirement("7A-FR-033")
    def test_handle_email_verified_default(self) -> None:
        """Test that email_verified defaults to False when missing."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "email": "test@example.com",
            # No email_verified
        }

        user_info = validator._extract_user_info(claims)

        assert user_info.email_verified is False


class TestUserInfoMalformedClaims:
    """Tests for handling malformed claims."""

    @pytest.mark.requirement("7A-FR-033")
    def test_handle_non_dict_realm_access(self) -> None:
        """Test handling of non-dict realm_access claim."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "realm_access": "invalid",  # Should be dict
        }

        user_info = validator._extract_user_info(claims)

        # Should not crash, roles should be empty
        assert user_info.roles == []

    @pytest.mark.requirement("7A-FR-033")
    def test_handle_non_list_roles(self) -> None:
        """Test handling of non-list roles claim."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "realm_access": {
                "roles": "single-role",  # Should be list
            },
        }

        user_info = validator._extract_user_info(claims)

        # Should not crash, roles should be empty (non-list ignored)
        assert user_info.roles == []

    @pytest.mark.requirement("7A-FR-033")
    def test_handle_non_string_roles(self) -> None:
        """Test handling of non-string role values."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "realm_access": {
                "roles": ["valid-role", 123, None, {"nested": "role"}],
            },
        }

        user_info = validator._extract_user_info(claims)

        # Only string roles should be extracted
        assert "valid-role" in user_info.roles
        assert len(user_info.roles) == 1

    @pytest.mark.requirement("7A-FR-033")
    def test_handle_non_dict_resource_access(self) -> None:
        """Test handling of non-dict resource_access claim."""
        from floe_identity_keycloak.token_validator import TokenValidator

        validator = TokenValidator(
            issuer="https://keycloak.example.com/realms/floe",
            audience="floe-client",
        )

        claims = {
            "sub": "user-123",
            "resource_access": ["invalid"],  # Should be dict
        }

        user_info = validator._extract_user_info(claims)

        # Should not crash, roles should be empty
        assert user_info.roles == []


class TestUserInfoDataclass:
    """Tests for UserInfo dataclass."""

    @pytest.mark.requirement("7A-FR-033")
    def test_userinfo_defaults(self) -> None:
        """Test UserInfo default values."""
        from floe_identity_keycloak.token_validator import UserInfo

        user_info = UserInfo(user_id="user-123")

        assert user_info.user_id == "user-123"
        assert user_info.email is None
        assert user_info.email_verified is False
        assert user_info.name is None
        assert user_info.preferred_username is None
        assert user_info.given_name is None
        assert user_info.family_name is None
        assert user_info.roles == []

    @pytest.mark.requirement("7A-FR-033")
    def test_userinfo_with_all_fields(self) -> None:
        """Test UserInfo with all fields populated."""
        from floe_identity_keycloak.token_validator import UserInfo

        user_info = UserInfo(
            user_id="user-123",
            email="test@example.com",
            email_verified=True,
            name="Test User",
            preferred_username="testuser",
            given_name="Test",
            family_name="User",
            roles=["admin", "user"],
        )

        assert user_info.user_id == "user-123"
        assert user_info.email == "test@example.com"
        assert user_info.email_verified is True
        assert user_info.name == "Test User"
        assert user_info.preferred_username == "testuser"
        assert user_info.given_name == "Test"
        assert user_info.family_name == "User"
        assert user_info.roles == ["admin", "user"]

    @pytest.mark.requirement("7A-FR-033")
    def test_userinfo_roles_initialized_to_empty_list(self) -> None:
        """Test that roles is initialized to empty list if None."""
        from floe_identity_keycloak.token_validator import UserInfo

        user_info = UserInfo(user_id="user-123", roles=None)

        # __post_init__ should convert None to empty list
        assert user_info.roles == []


class TestTokenValidationResultDataclass:
    """Tests for TokenValidationResult dataclass."""

    @pytest.mark.requirement("7A-FR-034")
    def test_valid_result(self) -> None:
        """Test valid TokenValidationResult."""
        from floe_identity_keycloak.token_validator import (
            TokenValidationResult,
            UserInfo,
        )

        user_info = UserInfo(user_id="user-123")
        result = TokenValidationResult(valid=True, user_info=user_info)

        assert result.valid is True
        assert result.user_info is not None
        assert result.error is None

    @pytest.mark.requirement("7A-FR-034")
    def test_invalid_result(self) -> None:
        """Test invalid TokenValidationResult."""
        from floe_identity_keycloak.token_validator import TokenValidationResult

        result = TokenValidationResult(valid=False, error="Token expired")

        assert result.valid is False
        assert result.user_info is None
        assert result.error == "Token expired"

    @pytest.mark.requirement("7A-FR-034")
    def test_result_defaults(self) -> None:
        """Test TokenValidationResult default values."""
        from floe_identity_keycloak.token_validator import TokenValidationResult

        result = TokenValidationResult(valid=False)

        assert result.valid is False
        assert result.user_info is None
        assert result.error is None

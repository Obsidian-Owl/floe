"""Unit tests for credential vending helper module.

This module tests the credential extraction and parsing functions in
floe_catalog_polaris.credentials.

Requirements Covered:
    - T061/FLO-292: Parse vended credentials from PyIceberg table.io properties
    - FR-020: System MUST return short-lived, scoped credentials for table access
    - FR-021: Vended credentials MUST include expiration timestamp
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from floe_catalog_polaris.credentials import (
    MAX_CREDENTIAL_TTL_SECONDS,
    S3_ACCESS_KEY_ID,
    S3_SECRET_ACCESS_KEY,
    S3_SESSION_TOKEN,
    S3_SESSION_TOKEN_EXPIRES_AT,
    credentials_are_valid,
    extract_credentials_from_io_properties,
    get_expiration_datetime,
    get_ttl_seconds,
    is_expired,
    is_ttl_valid,
    parse_expiration,
    validate_credential_structure,
    validate_ttl,
)

# ============================================================================
# TestExtractCredentialsFromIOProperties - T061/FLO-292
# ============================================================================


class TestExtractCredentialsFromIOProperties:
    """Tests for extract_credentials_from_io_properties function."""

    @pytest.mark.requirement("FR-020")
    def test_extract_all_s3_credential_fields(self) -> None:
        """Test extraction of all S3 credential fields from table.io.properties.

        Validates that s3.access-key-id, s3.secret-access-key,
        s3.session-token, and s3.session-token-expires-at are extracted.
        """
        # Arrange
        io_properties = {
            S3_ACCESS_KEY_ID: "ASIATESTACCESSKEY",
            S3_SECRET_ACCESS_KEY: "testsecretkey123",
            S3_SESSION_TOKEN: "testsessiontoken456",
            S3_SESSION_TOKEN_EXPIRES_AT: "2026-01-09T12:00:00Z",
        }

        # Act
        result = extract_credentials_from_io_properties(io_properties)

        # Assert
        assert result["access_key"] == "ASIATESTACCESSKEY"
        assert result["secret_key"] == "testsecretkey123"
        assert result["token"] == "testsessiontoken456"
        assert result["expiration"] == "2026-01-09T12:00:00Z"

    @pytest.mark.requirement("FR-020")
    def test_extract_credentials_with_missing_optional_fields(self) -> None:
        """Test extraction when optional fields are missing.

        Session token may be absent for some storage backends.
        """
        # Arrange
        io_properties = {
            S3_ACCESS_KEY_ID: "ASIATESTACCESSKEY",
            S3_SECRET_ACCESS_KEY: "testsecretkey123",
            # No session token or expiration
        }

        # Act
        result = extract_credentials_from_io_properties(io_properties)

        # Assert - required fields present
        assert result["access_key"] == "ASIATESTACCESSKEY"
        assert result["secret_key"] == "testsecretkey123"
        # Optional fields default to empty string
        assert result["token"] == ""
        assert result["expiration"] == ""

    @pytest.mark.requirement("FR-020")
    def test_extract_credentials_from_empty_properties(self) -> None:
        """Test extraction from empty properties returns empty values."""
        # Arrange
        io_properties: dict[str, str] = {}

        # Act
        result = extract_credentials_from_io_properties(io_properties)

        # Assert - all fields empty
        assert result["access_key"] == ""
        assert result["secret_key"] == ""
        assert result["token"] == ""
        assert result["expiration"] == ""

    @pytest.mark.requirement("FR-020")
    def test_extract_credentials_ignores_non_s3_properties(self) -> None:
        """Test extraction ignores non-S3 properties."""
        # Arrange
        io_properties = {
            S3_ACCESS_KEY_ID: "ASIATESTACCESSKEY",
            S3_SECRET_ACCESS_KEY: "testsecretkey123",
            "s3.endpoint": "https://s3.example.com",
            "s3.region": "us-east-1",
            "unrelated.property": "value",
        }

        # Act
        result = extract_credentials_from_io_properties(io_properties)

        # Assert - only credential fields extracted
        assert set(result.keys()) == {"access_key", "secret_key", "token", "expiration"}


# ============================================================================
# TestParseExpiration - Expiration timestamp parsing
# ============================================================================


class TestParseExpiration:
    """Tests for parse_expiration function."""

    @pytest.mark.requirement("FR-021")
    def test_parse_iso_8601_with_z_suffix(self) -> None:
        """Test parsing ISO 8601 timestamp with Z suffix (UTC)."""
        # Act
        result = parse_expiration("2026-01-09T12:00:00Z")

        # Assert
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 9
        assert result.hour == 12
        assert result.tzinfo == timezone.utc

    @pytest.mark.requirement("FR-021")
    def test_parse_iso_8601_with_utc_offset(self) -> None:
        """Test parsing ISO 8601 timestamp with +00:00 offset."""
        # Act
        result = parse_expiration("2026-01-09T12:00:00+00:00")

        # Assert
        assert result is not None
        assert result.tzinfo is not None

    @pytest.mark.requirement("FR-021")
    def test_parse_iso_8601_naive_assumes_utc(self) -> None:
        """Test parsing naive ISO 8601 timestamp assumes UTC."""
        # Act
        result = parse_expiration("2026-01-09T12:00:00")

        # Assert
        assert result is not None
        assert result.tzinfo == timezone.utc

    @pytest.mark.requirement("FR-021")
    def test_parse_epoch_milliseconds(self) -> None:
        """Test parsing epoch milliseconds timestamp."""
        # Arrange - 2026-01-09T12:00:00Z in epoch ms
        epoch_ms = "1767952800000"

        # Act
        result = parse_expiration(epoch_ms)

        # Assert
        assert result is not None
        assert result.year == 2026
        assert result.tzinfo == timezone.utc

    @pytest.mark.requirement("FR-021")
    def test_parse_epoch_seconds(self) -> None:
        """Test parsing epoch seconds timestamp."""
        # Arrange - 2026-01-09T12:00:00Z in epoch seconds
        epoch_s = "1767952800"

        # Act
        result = parse_expiration(epoch_s)

        # Assert
        assert result is not None
        assert result.year == 2026
        assert result.tzinfo == timezone.utc

    @pytest.mark.requirement("FR-021")
    def test_parse_empty_string_returns_none(self) -> None:
        """Test parsing empty string returns None."""
        # Act
        result = parse_expiration("")

        # Assert
        assert result is None

    @pytest.mark.requirement("FR-021")
    def test_parse_invalid_format_returns_none(self) -> None:
        """Test parsing invalid format returns None."""
        # Act
        result = parse_expiration("not-a-date")

        # Assert
        assert result is None


# ============================================================================
# TestValidateCredentialStructure - Validation
# ============================================================================


class TestValidateCredentialStructure:
    """Tests for validate_credential_structure function."""

    @pytest.mark.requirement("FR-020")
    def test_validate_complete_credentials_returns_empty(self) -> None:
        """Test complete credentials returns empty list (no missing keys)."""
        # Arrange
        credentials = {
            "access_key": "ASIATESTACCESSKEY",
            "secret_key": "testsecretkey",
            "expiration": "2026-01-09T12:00:00Z",
        }

        # Act
        result = validate_credential_structure(credentials)

        # Assert
        assert result == []

    @pytest.mark.requirement("FR-020")
    def test_validate_missing_access_key(self) -> None:
        """Test missing access_key is reported."""
        # Arrange
        credentials = {
            "secret_key": "testsecretkey",
            "expiration": "2026-01-09T12:00:00Z",
        }

        # Act
        result = validate_credential_structure(credentials)

        # Assert
        assert "access_key" in result

    @pytest.mark.requirement("FR-020")
    def test_validate_empty_values_reported_as_missing(self) -> None:
        """Test empty string values are reported as missing."""
        # Arrange
        credentials = {
            "access_key": "",
            "secret_key": "testsecretkey",
            "expiration": "2026-01-09T12:00:00Z",
        }

        # Act
        result = validate_credential_structure(credentials)

        # Assert
        assert "access_key" in result


# ============================================================================
# TestCredentialsAreValid - Validity check
# ============================================================================


class TestCredentialsAreValid:
    """Tests for credentials_are_valid function."""

    @pytest.mark.requirement("FR-020")
    def test_valid_credentials_returns_true(self) -> None:
        """Test credentials with access_key and secret_key are valid."""
        # Arrange
        credentials = {
            "access_key": "ASIATESTACCESSKEY",
            "secret_key": "testsecretkey",
        }

        # Act
        result = credentials_are_valid(credentials)

        # Assert
        assert result is True

    @pytest.mark.requirement("FR-020")
    def test_empty_access_key_returns_false(self) -> None:
        """Test empty access_key makes credentials invalid."""
        # Arrange
        credentials = {
            "access_key": "",
            "secret_key": "testsecretkey",
        }

        # Act
        result = credentials_are_valid(credentials)

        # Assert
        assert result is False

    @pytest.mark.requirement("FR-020")
    def test_empty_secret_key_returns_false(self) -> None:
        """Test empty secret_key makes credentials invalid."""
        # Arrange
        credentials = {
            "access_key": "ASIATESTACCESSKEY",
            "secret_key": "",
        }

        # Act
        result = credentials_are_valid(credentials)

        # Assert
        assert result is False

    @pytest.mark.requirement("FR-020")
    def test_missing_keys_returns_false(self) -> None:
        """Test missing keys makes credentials invalid."""
        # Arrange
        credentials: dict[str, str] = {}

        # Act
        result = credentials_are_valid(credentials)

        # Assert
        assert result is False


# ============================================================================
# TestIsExpired - Expiration check
# ============================================================================


class TestIsExpired:
    """Tests for is_expired function."""

    @pytest.mark.requirement("FR-021")
    def test_future_expiration_not_expired(self) -> None:
        """Test credentials with future expiration are not expired."""
        # Arrange
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        credentials = {"expiration": future.isoformat()}

        # Act
        result = is_expired(credentials)

        # Assert
        assert result is False

    @pytest.mark.requirement("FR-021")
    def test_past_expiration_is_expired(self) -> None:
        """Test credentials with past expiration are expired."""
        # Arrange
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        credentials = {"expiration": past.isoformat()}

        # Act
        result = is_expired(credentials)

        # Assert
        assert result is True

    @pytest.mark.requirement("FR-021")
    def test_no_expiration_not_expired(self) -> None:
        """Test credentials without expiration are assumed valid."""
        # Arrange
        credentials = {"expiration": ""}

        # Act
        result = is_expired(credentials)

        # Assert
        assert result is False


# ============================================================================
# TestGetExpirationDatetime - Datetime extraction
# ============================================================================


class TestGetExpirationDatetime:
    """Tests for get_expiration_datetime function."""

    @pytest.mark.requirement("FR-021")
    def test_get_valid_expiration(self) -> None:
        """Test getting expiration datetime from credentials."""
        # Arrange
        credentials = {"expiration": "2026-01-09T12:00:00Z"}

        # Act
        result = get_expiration_datetime(credentials)

        # Assert
        assert result is not None
        assert result.year == 2026

    @pytest.mark.requirement("FR-021")
    def test_get_empty_expiration_returns_none(self) -> None:
        """Test empty expiration returns None."""
        # Arrange
        credentials = {"expiration": ""}

        # Act
        result = get_expiration_datetime(credentials)

        # Assert
        assert result is None


# ============================================================================
# TestGetTTLSeconds - TTL calculation
# ============================================================================


class TestGetTTLSeconds:
    """Tests for get_ttl_seconds function."""

    @pytest.mark.requirement("FR-021")
    def test_get_ttl_future_expiration(self) -> None:
        """Test TTL calculation for credentials with future expiration."""
        # Arrange - expiration 1 hour in future
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        credentials = {"expiration": future.isoformat()}

        # Act
        result = get_ttl_seconds(credentials)

        # Assert - should be approximately 3600 seconds (1 hour)
        assert 3590 <= result <= 3610

    @pytest.mark.requirement("FR-021")
    def test_get_ttl_past_expiration_returns_zero(self) -> None:
        """Test TTL returns 0 for expired credentials."""
        # Arrange - expiration 1 hour in past
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        credentials = {"expiration": past.isoformat()}

        # Act
        result = get_ttl_seconds(credentials)

        # Assert
        assert result == 0

    @pytest.mark.requirement("FR-021")
    def test_get_ttl_no_expiration_returns_zero(self) -> None:
        """Test TTL returns 0 when no expiration set."""
        # Arrange
        credentials = {"expiration": ""}

        # Act
        result = get_ttl_seconds(credentials)

        # Assert
        assert result == 0

    @pytest.mark.requirement("FR-021")
    def test_get_ttl_missing_expiration_key_returns_zero(self) -> None:
        """Test TTL returns 0 when expiration key is missing."""
        # Arrange
        credentials: dict[str, str] = {}

        # Act
        result = get_ttl_seconds(credentials)

        # Assert
        assert result == 0


# ============================================================================
# TestValidateTTL - TTL validation
# ============================================================================


class TestValidateTTL:
    """Tests for validate_ttl function."""

    @pytest.mark.requirement("FR-021")
    def test_validate_ttl_valid_future_expiration(self) -> None:
        """Test valid TTL returns True with no error."""
        # Arrange - expiration 1 hour in future (within 24 hour limit)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        credentials = {"expiration": future.isoformat()}

        # Act
        is_valid, error = validate_ttl(credentials)

        # Assert
        assert is_valid is True
        assert error is None

    @pytest.mark.requirement("FR-021")
    def test_validate_ttl_expired_returns_error(self) -> None:
        """Test expired credentials return validation error."""
        # Arrange - expiration 1 hour in past
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        credentials = {"expiration": past.isoformat()}

        # Act
        is_valid, error = validate_ttl(credentials)

        # Assert
        assert is_valid is False
        assert error == "Credentials have expired"

    @pytest.mark.requirement("FR-021")
    def test_validate_ttl_exceeds_maximum(self) -> None:
        """Test TTL exceeding 24 hours returns error."""
        # Arrange - expiration 48 hours in future (exceeds 24 hour limit)
        far_future = datetime.now(timezone.utc) + timedelta(hours=48)
        credentials = {"expiration": far_future.isoformat()}

        # Act
        is_valid, error = validate_ttl(credentials)

        # Assert
        assert is_valid is False
        assert error is not None
        assert "TTL exceeds maximum" in error
        assert "24 hours" in error

    @pytest.mark.requirement("FR-021")
    def test_validate_ttl_custom_max_ttl(self) -> None:
        """Test TTL validation with custom max TTL."""
        # Arrange - expiration 2 hours in future, max TTL 1 hour
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        credentials = {"expiration": future.isoformat()}
        max_ttl = 3600  # 1 hour

        # Act
        is_valid, error = validate_ttl(credentials, max_ttl_seconds=max_ttl)

        # Assert
        assert is_valid is False
        assert error is not None
        assert "TTL exceeds maximum" in error

    @pytest.mark.requirement("FR-021")
    def test_validate_ttl_no_expiration_is_valid(self) -> None:
        """Test credentials without expiration are considered valid."""
        # Arrange - no expiration set
        credentials = {"expiration": ""}

        # Act
        is_valid, error = validate_ttl(credentials)

        # Assert
        assert is_valid is True
        assert error is None

    @pytest.mark.requirement("FR-021")
    def test_validate_ttl_at_maximum_boundary(self) -> None:
        """Test TTL exactly at maximum is valid."""
        # Arrange - expiration exactly at 24 hour limit
        future = datetime.now(timezone.utc) + timedelta(seconds=MAX_CREDENTIAL_TTL_SECONDS - 10)
        credentials = {"expiration": future.isoformat()}

        # Act
        is_valid, error = validate_ttl(credentials)

        # Assert
        assert is_valid is True
        assert error is None


# ============================================================================
# TestIsTTLValid - Convenience wrapper
# ============================================================================


class TestIsTTLValid:
    """Tests for is_ttl_valid convenience function."""

    @pytest.mark.requirement("FR-021")
    def test_is_ttl_valid_true_for_valid_credentials(self) -> None:
        """Test returns True for valid credentials."""
        # Arrange - expiration 1 hour in future
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        credentials = {"expiration": future.isoformat()}

        # Act
        result = is_ttl_valid(credentials)

        # Assert
        assert result is True

    @pytest.mark.requirement("FR-021")
    def test_is_ttl_valid_false_for_expired(self) -> None:
        """Test returns False for expired credentials."""
        # Arrange - expiration in past
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        credentials = {"expiration": past.isoformat()}

        # Act
        result = is_ttl_valid(credentials)

        # Assert
        assert result is False

    @pytest.mark.requirement("FR-021")
    def test_is_ttl_valid_false_for_exceeds_max(self) -> None:
        """Test returns False when TTL exceeds maximum."""
        # Arrange - expiration 48 hours in future
        far_future = datetime.now(timezone.utc) + timedelta(hours=48)
        credentials = {"expiration": far_future.isoformat()}

        # Act
        result = is_ttl_valid(credentials)

        # Assert
        assert result is False

    @pytest.mark.requirement("FR-021")
    def test_is_ttl_valid_with_custom_max(self) -> None:
        """Test with custom max TTL parameter."""
        # Arrange - expiration 2 hours in future, max 1 hour
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        credentials = {"expiration": future.isoformat()}

        # Act
        result = is_ttl_valid(credentials, max_ttl_seconds=3600)

        # Assert
        assert result is False

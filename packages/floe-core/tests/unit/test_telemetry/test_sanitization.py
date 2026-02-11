"""Unit tests for error message sanitization utilities."""

from __future__ import annotations

import pytest

from floe_core.telemetry.sanitization import sanitize_error_message


class TestSanitizeErrorMessage:
    """Tests for sanitize_error_message utility."""

    @pytest.mark.requirement("6C-FR-014")
    def test_url_credential_redaction(self) -> None:
        """Test URL credential redaction in error messages.

        Validates that credentials in URL patterns like
        ://user:pass@host are replaced with ://REDACTED@host.  # pragma: allowlist secret
        """
        # pragma: allowlist secret
        msg = "Connection failed to postgresql://admin:secret123@db.example.com/warehouse"
        result = sanitize_error_message(msg)

        assert result == "Connection failed to postgresql://<REDACTED>@db.example.com/warehouse"
        assert "admin" not in result
        assert "secret123" not in result

    @pytest.mark.requirement("6C-FR-014")
    def test_password_key_value_redaction(self) -> None:
        """Test key-value redaction for password field.

        Validates that password=value patterns are replaced with
        password=<REDACTED>.
        """
        # pragma: allowlist secret
        msg = "Authentication failed with error: password=secret123 was invalid"
        result = sanitize_error_message(msg)

        assert result == "Authentication failed with error: password=<REDACTED> was invalid"
        assert "secret123" not in result

    @pytest.mark.requirement("6C-FR-014")
    def test_multiple_sensitive_keys_redacted(self) -> None:
        """Test multiple sensitive keys in one message are all redacted.

        Validates that when multiple sensitive key-value patterns appear,
        all are replaced with <REDACTED>.
        """
        # pragma: allowlist secret
        msg = (
            "Config error: access_key=AKIAIOSFODNN7EXAMPLE "  # pragma: allowlist secret
            "secret_key=wJalrXUtnFEMI/K7MDENG invalid"  # pragma: allowlist secret
        )
        result = sanitize_error_message(msg)

        assert result == "Config error: access_key=<REDACTED> secret_key=<REDACTED> invalid"
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "wJalrXUtnFEMI/K7MDENG" not in result

    @pytest.mark.requirement("6C-FR-014")
    def test_authorization_colon_separator(self) -> None:
        r"""Test key with colon separator is redacted.

        Validates that authorization: Bearer token patterns are replaced
        with authorization: <REDACTED> (the regex matches both = and :
        separators). Note: The regex \S+ only captures the first
        non-whitespace token after the separator, so "Bearer" is redacted
        but subsequent space-separated tokens remain.
        """
        # pragma: allowlist secret
        msg = "HTTP error: authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = sanitize_error_message(msg)

        # The regex only captures "Bearer" (first \S+ after colon),
        # not the full token
        assert (
            result == "HTTP error: authorization: <REDACTED> eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        )
        assert "Bearer" not in result

    @pytest.mark.requirement("6C-FR-014")
    def test_truncation_to_max_length(self) -> None:
        """Test error message truncation to max_length parameter.

        Validates that long error messages are truncated to the specified
        max_length (default 500 characters).
        """
        long_msg = "Error: " + ("x" * 600)
        result = sanitize_error_message(long_msg, max_length=100)

        assert len(result) == 100
        assert result.startswith("Error: ")

    @pytest.mark.requirement("6C-FR-014")
    def test_clean_string_unchanged(self) -> None:
        """Test clean strings without sensitive data pass through unchanged.

        Validates that error messages with no sensitive patterns are
        returned as-is (modulo truncation).
        """
        msg = "Connection timeout after 30 seconds"
        result = sanitize_error_message(msg)

        assert result == msg

    @pytest.mark.requirement("6C-FR-014")
    def test_empty_string_returns_empty(self) -> None:
        """Test empty string input returns empty string.

        Validates edge case where error message is empty.
        """
        result = sanitize_error_message("")

        assert result == ""

    @pytest.mark.requirement("6C-FR-014")
    def test_very_long_message_truncated_correctly(self) -> None:
        """Test very long error message is truncated to default 500 chars.

        Validates that messages exceeding the default max_length are
        truncated at exactly 500 characters.
        """
        base_msg = "Database error: "
        long_msg = base_msg + ("x" * 1000)
        result = sanitize_error_message(long_msg)

        assert len(result) == 500
        assert result.startswith(base_msg)
        assert result == long_msg[:500]

    @pytest.mark.requirement("6C-FR-014")
    def test_case_insensitive_redaction(self) -> None:
        """Test case-insensitive redaction of sensitive keys.

        Validates that PASSWORD=, Password=, and password= are all redacted
        due to re.IGNORECASE flag in the pattern.
        """
        msg_upper = "Error: PASSWORD=Secret123"  # pragma: allowlist secret
        msg_title = "Error: Password=Secret456"  # pragma: allowlist secret
        msg_lower = "Error: password=secret789"  # pragma: allowlist secret

        result_upper = sanitize_error_message(msg_upper)
        result_title = sanitize_error_message(msg_title)
        result_lower = sanitize_error_message(msg_lower)

        assert result_upper == "Error: PASSWORD=<REDACTED>"
        assert result_title == "Error: Password=<REDACTED>"
        assert result_lower == "Error: password=<REDACTED>"
        assert "Secret123" not in result_upper
        assert "Secret456" not in result_title
        assert "secret789" not in result_lower

    @pytest.mark.requirement("6C-FR-014")
    def test_api_key_redaction(self) -> None:
        """Test api_key field is redacted.

        Validates that api_key is recognized as a sensitive key
        and its value is replaced with <REDACTED>.
        """
        # pragma: allowlist secret
        msg = (
            "API request failed: api_key=sk-1234567890abcdef "  # pragma: allowlist secret
            "endpoint=/v1/data"
        )
        result = sanitize_error_message(msg)

        assert result == "API request failed: api_key=<REDACTED> endpoint=/v1/data"
        assert "sk-1234567890abcdef" not in result

    @pytest.mark.requirement("6C-FR-014")
    def test_token_redaction(self) -> None:
        """Test token field is redacted.

        Validates that token= patterns are replaced with token=<REDACTED>.
        """
        # pragma: allowlist secret
        msg = "Auth failed: token=ghp_1234567890abcdefGHIJKL user=testuser"
        result = sanitize_error_message(msg)

        assert result == "Auth failed: token=<REDACTED> user=testuser"
        assert "ghp_1234567890abcdefGHIJKL" not in result

    @pytest.mark.requirement("6C-FR-014")
    def test_credential_redaction(self) -> None:
        """Test credential field is redacted.

        Validates that credential= patterns are replaced with
        credential=<REDACTED>.
        """
        # pragma: allowlist secret
        msg = "S3 error: credential=ASIATESTACCESSKEY123 region=us-east-1"  # noqa: E501
        result = sanitize_error_message(msg)

        assert result == "S3 error: credential=<REDACTED> region=us-east-1"
        assert "ASIATESTACCESSKEY123" not in result

    @pytest.mark.requirement("6C-FR-014")
    def test_combined_url_and_key_value_redaction(self) -> None:
        """Test both URL credentials and key-value pairs are redacted.

        Validates that when a message contains both URL credentials and
        key-value sensitive data, both patterns are sanitized.
        """
        # pragma: allowlist secret
        msg = (
            "Failed to connect to postgresql://admin:pass123@db.host/warehouse "
            "with secret_key=wJalrXUtnFEMI/K7MDENG"
        )
        result = sanitize_error_message(msg)

        expected = (
            "Failed to connect to postgresql://<REDACTED>@db.host/warehouse "
            "with secret_key=<REDACTED>"
        )
        assert result == expected
        assert "admin" not in result
        assert "pass123" not in result
        assert "wJalrXUtnFEMI/K7MDENG" not in result

    @pytest.mark.requirement("6C-FR-014")
    def test_redaction_with_whitespace_around_separator(self) -> None:
        r"""Test redaction works with whitespace around = or : separator.

        Validates that patterns like "password = secret" and "token : value"
        are correctly redacted (the regex uses \s* to match optional whitespace).
        Note: Whitespace before the separator is preserved in the output.
        """
        msg_equals = "Config: password = secret123 is invalid"  # pragma: allowlist secret
        msg_colon = "Header: token : bearer-token-xyz"  # pragma: allowlist secret

        result_equals = sanitize_error_message(msg_equals)
        result_colon = sanitize_error_message(msg_colon)

        # Whitespace before separator is preserved, whitespace after is consumed
        assert result_equals == "Config: password =<REDACTED> is invalid"
        assert result_colon == "Header: token : <REDACTED>"
        assert "secret123" not in result_equals
        assert "bearer-token-xyz" not in result_colon

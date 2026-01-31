"""Unit tests for tag security validation.

Task ID: Security Fix
Requirement: SEC-001 (Command Injection Prevention)

Tests for validate_tag_security() function which prevents command injection
via malicious tag names containing shell metacharacters.
"""

from __future__ import annotations

import pytest

from floe_core.oci.promotion import (
    MAX_TAG_LENGTH,
    SAFE_TAG_PATTERN,
    validate_tag_security,
)


class TestSafeTagPattern:
    """Tests for SAFE_TAG_PATTERN regex constant."""

    @pytest.mark.requirement("SEC-001")
    def test_pattern_allows_semver_tags(self) -> None:
        """SAFE_TAG_PATTERN should allow standard semver tags."""
        valid_tags = [
            "v1.0.0",
            "1.2.3",
            "v1.0.0-alpha",
            "v1.0.0-rc.1",
            "v2.0.0-beta.2",
            "1.0.0-alpha.1",
        ]
        for tag in valid_tags:
            assert SAFE_TAG_PATTERN.match(tag), f"Tag '{tag}' should be valid"

    @pytest.mark.requirement("SEC-001")
    def test_pattern_allows_environment_tags(self) -> None:
        """SAFE_TAG_PATTERN should allow environment-suffixed tags."""
        valid_tags = [
            "v1.0.0-dev",
            "v1.0.0-staging",
            "v1.0.0-prod",
            "latest",
            "latest-dev",
            "latest-staging",
            "latest-prod",
        ]
        for tag in valid_tags:
            assert SAFE_TAG_PATTERN.match(tag), f"Tag '{tag}' should be valid"

    @pytest.mark.requirement("SEC-001")
    def test_pattern_blocks_shell_metacharacters(self) -> None:
        """SAFE_TAG_PATTERN should reject shell metacharacters."""
        malicious_tags = [
            "v1.0.0; rm -rf /",  # Command separator
            "v1.0.0 && echo pwned",  # Command chaining
            "v1.0.0 | cat /etc/passwd",  # Pipe
            "v1.0.0 > /tmp/pwned",  # Redirect
            "v1.0.0 < /etc/passwd",  # Input redirect
            "v1.0.0$(whoami)",  # Command substitution
            "v1.0.0`id`",  # Backtick substitution
            "v1.0.0 & bg",  # Background execution
            "v1.0.0\necho pwned",  # Newline injection
            "v1.0.0\techo pwned",  # Tab injection (if present)
        ]
        for tag in malicious_tags:
            assert not SAFE_TAG_PATTERN.match(tag), f"Tag '{tag}' should be rejected"

    @pytest.mark.requirement("SEC-001")
    def test_pattern_requires_alphanumeric_start(self) -> None:
        """Tags must start with alphanumeric character."""
        invalid_tags = [
            "-v1.0.0",  # Starts with hyphen
            ".v1.0.0",  # Starts with dot
            "_v1.0.0",  # Starts with underscore
            " v1.0.0",  # Starts with space
        ]
        for tag in invalid_tags:
            assert not SAFE_TAG_PATTERN.match(tag), f"Tag '{tag}' should be rejected"


class TestValidateTagSecurity:
    """Tests for validate_tag_security() function."""

    @pytest.mark.requirement("SEC-001")
    def test_valid_semver_tag_passes(self) -> None:
        """Valid semver tags should pass validation."""
        # Should not raise
        validate_tag_security("v1.0.0")
        validate_tag_security("1.2.3")
        validate_tag_security("v1.0.0-alpha")

    @pytest.mark.requirement("SEC-001")
    def test_valid_environment_tag_passes(self) -> None:
        """Valid environment-suffixed tags should pass validation."""
        validate_tag_security("v1.0.0-dev")
        validate_tag_security("v1.0.0-staging")
        validate_tag_security("v1.0.0-prod")
        validate_tag_security("latest")
        validate_tag_security("latest-prod")

    @pytest.mark.requirement("SEC-001")
    def test_empty_tag_raises_value_error(self) -> None:
        """Empty tag should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_tag_security("")

    @pytest.mark.requirement("SEC-001")
    def test_tag_exceeding_max_length_raises(self) -> None:
        """Tag exceeding MAX_TAG_LENGTH should raise ValueError."""
        long_tag = "v" + "1" * MAX_TAG_LENGTH  # Exceeds limit
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_tag_security(long_tag)

    @pytest.mark.requirement("SEC-001")
    def test_tag_at_max_length_passes(self) -> None:
        """Tag at exactly MAX_TAG_LENGTH should pass."""
        max_tag = "v" + "1" * (MAX_TAG_LENGTH - 1)  # Exactly at limit
        validate_tag_security(max_tag)

    @pytest.mark.requirement("SEC-001")
    def test_command_injection_semicolon_raises(self) -> None:
        """Tag with semicolon command injection should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag_security("v1.0.0; rm -rf /")

    @pytest.mark.requirement("SEC-001")
    def test_command_injection_pipe_raises(self) -> None:
        """Tag with pipe injection should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag_security("v1.0.0 | cat /etc/passwd")

    @pytest.mark.requirement("SEC-001")
    def test_command_injection_ampersand_raises(self) -> None:
        """Tag with ampersand injection should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag_security("v1.0.0 && echo pwned")

    @pytest.mark.requirement("SEC-001")
    def test_command_substitution_dollar_raises(self) -> None:
        """Tag with $() command substitution should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag_security("v1.0.0$(whoami)")

    @pytest.mark.requirement("SEC-001")
    def test_command_substitution_backtick_raises(self) -> None:
        """Tag with backtick substitution should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag_security("v1.0.0`id`")

    @pytest.mark.requirement("SEC-001")
    def test_redirect_injection_raises(self) -> None:
        """Tag with redirect characters should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag_security("v1.0.0 > /tmp/pwned")
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag_security("v1.0.0 < /etc/passwd")

    @pytest.mark.requirement("SEC-001")
    def test_space_in_tag_raises(self) -> None:
        """Tag with spaces should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag_security("v1.0.0 with spaces")

    @pytest.mark.requirement("SEC-001")
    def test_newline_in_tag_raises(self) -> None:
        """Tag with newlines should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag_security("v1.0.0\necho pwned")

    @pytest.mark.requirement("SEC-001")
    def test_error_message_includes_tag(self) -> None:
        """Error message should include the invalid tag for debugging."""
        try:
            validate_tag_security("v1.0.0;bad")
        except ValueError as e:
            assert "v1.0.0;bad" in str(e)


class TestShellEscapingDefenseInDepth:
    """Tests to verify shlex.quote is used as defense in depth.

    Even if tag validation is bypassed, shlex.quote should escape
    shell metacharacters in artifact references.
    """

    @pytest.mark.requirement("SEC-001")
    def test_shlex_quote_imported_in_promotion(self) -> None:
        """Verify shlex is imported in promotion module."""
        import floe_core.oci.promotion as promotion_module

        # Check shlex is in the module's imports
        assert hasattr(promotion_module, "shlex"), "shlex should be imported"

    @pytest.mark.requirement("SEC-001")
    def test_validate_tag_security_exported(self) -> None:
        """Verify validate_tag_security is accessible."""
        from floe_core.oci.promotion import validate_tag_security

        assert callable(validate_tag_security)

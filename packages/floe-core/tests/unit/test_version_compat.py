"""Unit tests for version compatibility module.

Tests for T030: Create unit tests for version compatibility.

Requirements Covered: FR-003, FR-004, FR-005, SC-004
"""

from __future__ import annotations

import pytest

from floe_core.version_compat import (
    FLOE_PLUGIN_API_MIN_VERSION,
    FLOE_PLUGIN_API_VERSION,
    _parse_version,
    is_compatible,
)


class TestParseVersion:
    """Tests for _parse_version() function."""

    @pytest.mark.requirement("FR-003")
    def test_parse_version_simple(self) -> None:
        """Test parsing simple X.Y version strings."""
        assert _parse_version("1.0") == (1, 0)
        assert _parse_version("2.1") == (2, 1)
        assert _parse_version("0.0") == (0, 0)

    @pytest.mark.requirement("FR-003")
    def test_parse_version_double_digits(self) -> None:
        """Test parsing versions with double-digit components."""
        assert _parse_version("1.10") == (1, 10)
        assert _parse_version("10.5") == (10, 5)
        assert _parse_version("99.99") == (99, 99)

    @pytest.mark.requirement("FR-003")
    def test_parse_version_leading_zeros(self) -> None:
        """Test parsing versions with leading zeros (valid but unusual)."""
        # int() strips leading zeros, which is acceptable
        assert _parse_version("01.02") == (1, 2)

    @pytest.mark.requirement("FR-003")
    def test_parse_version_invalid_format_single_number(self) -> None:
        """Test that single number without dot raises ValueError."""
        with pytest.raises(ValueError, match="Invalid version format"):
            _parse_version("1")

    @pytest.mark.requirement("FR-003")
    def test_parse_version_invalid_format_three_parts(self) -> None:
        """Test that X.Y.Z format raises ValueError (we use X.Y only)."""
        with pytest.raises(ValueError, match="Invalid version format"):
            _parse_version("1.0.0")

    @pytest.mark.requirement("FR-003")
    def test_parse_version_invalid_format_non_numeric(self) -> None:
        """Test that non-numeric version raises ValueError."""
        with pytest.raises(ValueError, match="Invalid version format"):
            _parse_version("one.two")

    @pytest.mark.requirement("FR-003")
    def test_parse_version_invalid_format_empty_string(self) -> None:
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid version format"):
            _parse_version("")

    @pytest.mark.requirement("FR-003")
    def test_parse_version_whitespace_tolerated(self) -> None:
        """Test that leading whitespace is tolerated (int() strips it)."""
        # Python's int() strips whitespace, so " 1.0" parses successfully
        assert _parse_version(" 1.0") == (1, 0)
        assert _parse_version("1. 0") == (1, 0)  # space after dot


class TestIsCompatible:
    """Tests for is_compatible() function."""

    @pytest.mark.requirement("FR-004")
    def test_is_compatible_exact_match(self) -> None:
        """Test that exact version match is compatible."""
        assert is_compatible("1.0", "1.0") is True
        assert is_compatible("2.5", "2.5") is True

    @pytest.mark.requirement("FR-004")
    def test_is_compatible_platform_has_newer_minor(self) -> None:
        """Test that plugin works when platform has newer minor version.

        Platform can provide newer features that plugin doesn't use.
        """
        assert is_compatible("1.0", "1.1") is True
        assert is_compatible("1.0", "1.5") is True
        assert is_compatible("1.2", "1.10") is True

    @pytest.mark.requirement("FR-005")
    def test_is_compatible_plugin_needs_newer_minor(self) -> None:
        """Test that plugin fails when it needs newer minor version.

        Plugin requires features not available in older platform.
        """
        assert is_compatible("1.2", "1.0") is False
        assert is_compatible("1.5", "1.4") is False
        assert is_compatible("1.10", "1.9") is False

    @pytest.mark.requirement("FR-005")
    def test_is_compatible_major_version_mismatch(self) -> None:
        """Test that major version mismatch is always incompatible.

        Major version changes indicate breaking API changes.
        """
        assert is_compatible("2.0", "1.0") is False
        assert is_compatible("1.0", "2.0") is False
        assert is_compatible("3.5", "2.9") is False

    @pytest.mark.requirement("FR-004")
    def test_is_compatible_with_zero_versions(self) -> None:
        """Test compatibility checks with zero versions (pre-release)."""
        assert is_compatible("0.0", "0.0") is True
        assert is_compatible("0.1", "0.5") is True
        assert is_compatible("0.5", "0.1") is False

    @pytest.mark.requirement("FR-004")
    def test_is_compatible_raises_on_invalid_plugin_version(self) -> None:
        """Test that invalid plugin version raises ValueError."""
        with pytest.raises(ValueError, match="Invalid version format"):
            is_compatible("invalid", "1.0")

    @pytest.mark.requirement("FR-004")
    def test_is_compatible_raises_on_invalid_platform_version(self) -> None:
        """Test that invalid platform version raises ValueError."""
        with pytest.raises(ValueError, match="Invalid version format"):
            is_compatible("1.0", "invalid")


class TestVersionConstants:
    """Tests for version constants."""

    @pytest.mark.requirement("SC-004")
    def test_floe_plugin_api_version_format(self) -> None:
        """Test that FLOE_PLUGIN_API_VERSION is valid X.Y format."""
        major, minor = _parse_version(FLOE_PLUGIN_API_VERSION)
        assert isinstance(major, int)
        assert isinstance(minor, int)
        assert major >= 0
        assert minor >= 0

    @pytest.mark.requirement("SC-004")
    def test_floe_plugin_api_min_version_format(self) -> None:
        """Test that FLOE_PLUGIN_API_MIN_VERSION is valid X.Y format."""
        major, minor = _parse_version(FLOE_PLUGIN_API_MIN_VERSION)
        assert isinstance(major, int)
        assert isinstance(minor, int)
        assert major >= 0
        assert minor >= 0

    @pytest.mark.requirement("SC-004")
    def test_min_version_compatible_with_current(self) -> None:
        """Test that minimum version is compatible with current version."""
        # MIN should be <= current (platform can run older plugins)
        assert is_compatible(FLOE_PLUGIN_API_MIN_VERSION, FLOE_PLUGIN_API_VERSION) is True

    @pytest.mark.requirement("SC-004")
    def test_current_version_values(self) -> None:
        """Test current version values are as expected."""
        # Current version is 0.1 (pre-1.0 unstable API)
        assert FLOE_PLUGIN_API_VERSION == "0.1"
        assert FLOE_PLUGIN_API_MIN_VERSION == "0.1"

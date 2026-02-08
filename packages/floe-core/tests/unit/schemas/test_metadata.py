"""Unit tests for ManifestMetadata model.

Tests validation of manifest metadata including name patterns,
version format, and owner requirements.

Task: T009
Requirements: FR-001, FR-002
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.schemas.metadata import NAME_PATTERN, SEMVER_PATTERN, ManifestMetadata


class TestManifestMetadataValidation:
    """Tests for ManifestMetadata validation rules."""

    @pytest.mark.requirement("001-FR-001")
    def test_valid_metadata_minimal(self) -> None:
        """Test that minimal valid metadata is accepted."""
        metadata = ManifestMetadata(
            name="test",
            version="1.0.0",
            owner="team@example.com",
        )
        assert metadata.name == "test"
        assert metadata.version == "1.0.0"
        assert metadata.owner == "team@example.com"
        assert metadata.description is None

    @pytest.mark.requirement("001-FR-001")
    def test_valid_metadata_full(self) -> None:
        """Test that full valid metadata is accepted."""
        metadata = ManifestMetadata(
            name="acme-platform",
            version="2.1.3",
            owner="platform-team@acme.com",
            description="ACME data platform configuration",
        )
        assert metadata.name == "acme-platform"
        assert metadata.version == "2.1.3"
        assert metadata.owner == "platform-team@acme.com"
        assert metadata.description == "ACME data platform configuration"

    @pytest.mark.requirement("001-FR-002")
    def test_name_pattern_valid_single_char(self) -> None:
        """Test that single character name is valid."""
        metadata = ManifestMetadata(name="a", version="1.0.0", owner="test")
        assert metadata.name == "a"

    @pytest.mark.requirement("001-FR-002")
    def test_name_pattern_valid_with_hyphens(self) -> None:
        """Test that name with hyphens is valid."""
        metadata = ManifestMetadata(
            name="my-platform-v2", version="1.0.0", owner="test"
        )
        assert metadata.name == "my-platform-v2"

    @pytest.mark.requirement("001-FR-002")
    def test_name_pattern_valid_numbers(self) -> None:
        """Test that name with numbers is valid."""
        metadata = ManifestMetadata(name="platform123", version="1.0.0", owner="test")
        assert metadata.name == "platform123"

    @pytest.mark.requirement("001-FR-002")
    def test_name_pattern_invalid_uppercase(self) -> None:
        """Test that uppercase name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ManifestMetadata(name="MyPlatform", version="1.0.0", owner="test")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    def test_name_pattern_invalid_starts_with_hyphen(self) -> None:
        """Test that name starting with hyphen is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ManifestMetadata(name="-platform", version="1.0.0", owner="test")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    def test_name_pattern_invalid_ends_with_hyphen(self) -> None:
        """Test that name ending with hyphen is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ManifestMetadata(name="platform-", version="1.0.0", owner="test")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    def test_name_pattern_invalid_special_chars(self) -> None:
        """Test that name with special characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ManifestMetadata(name="my_platform", version="1.0.0", owner="test")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    def test_name_too_long(self) -> None:
        """Test that name exceeding 63 characters is rejected."""
        long_name = "a" * 64
        with pytest.raises(ValidationError) as exc_info:
            ManifestMetadata(name=long_name, version="1.0.0", owner="test")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    def test_name_reserved_keyword(self) -> None:
        """Test that reserved names are rejected."""
        reserved_names = ["default", "system", "floe", "admin", "root"]
        for name in reserved_names:
            with pytest.raises(ValidationError) as exc_info:
                ManifestMetadata(name=name, version="1.0.0", owner="test")
            assert "reserved" in str(exc_info.value).lower()

    @pytest.mark.requirement("001-FR-002")
    def test_version_valid_semver(self) -> None:
        """Test that valid semver versions are accepted."""
        valid_versions = ["0.0.1", "1.0.0", "10.20.30", "999.999.999"]
        for version in valid_versions:
            metadata = ManifestMetadata(name="test", version=version, owner="test")
            assert metadata.version == version

    @pytest.mark.requirement("001-FR-002")
    def test_version_invalid_format(self) -> None:
        """Test that invalid version formats are rejected."""
        invalid_versions = ["1.0", "v1.0.0", "1.0.0-beta", "1.0.0.0", "latest"]
        for version in invalid_versions:
            with pytest.raises(ValidationError) as exc_info:
                ManifestMetadata(name="test", version=version, owner="test")
            assert "version" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    def test_owner_required(self) -> None:
        """Test that owner is required."""
        with pytest.raises(ValidationError) as exc_info:
            ManifestMetadata(name="test", version="1.0.0", owner="")
        assert "owner" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    def test_description_max_length(self) -> None:
        """Test that description exceeding 500 characters is rejected."""
        long_desc = "a" * 501
        with pytest.raises(ValidationError) as exc_info:
            ManifestMetadata(
                name="test", version="1.0.0", owner="test", description=long_desc
            )
        assert "description" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-001")
    def test_metadata_immutable(self) -> None:
        """Test that ManifestMetadata is immutable (frozen)."""
        metadata = ManifestMetadata(name="test", version="1.0.0", owner="test")
        with pytest.raises(ValidationError):
            metadata.name = "changed"  # type: ignore[misc]

    @pytest.mark.requirement("001-FR-001")
    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ManifestMetadata(
                name="test",
                version="1.0.0",
                owner="test",
                extra_field="not allowed",  # type: ignore[call-arg]
            )
        assert "extra" in str(exc_info.value).lower()


class TestManifestMetadataPatterns:
    """Tests for exported pattern constants."""

    @pytest.mark.requirement("001-FR-002")
    def test_name_pattern_exported(self) -> None:
        """Test that NAME_PATTERN constant is exported."""
        assert NAME_PATTERN is not None
        assert isinstance(NAME_PATTERN, str)

    @pytest.mark.requirement("001-FR-002")
    def test_semver_pattern_exported(self) -> None:
        """Test that SEMVER_PATTERN constant is exported."""
        assert SEMVER_PATTERN is not None
        assert isinstance(SEMVER_PATTERN, str)

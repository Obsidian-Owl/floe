"""Unit tests for schema version constants.

Tests for the centralized version constants module that provides
single-source-of-truth for schema versions across the codebase.

Task: Version centralization
Requirements: Contract stability
"""

from __future__ import annotations

import re

import pytest

from floe_core.schemas.versions import (
    COMPILED_ARTIFACTS_VERSION,
    COMPILED_ARTIFACTS_VERSION_HISTORY,
    get_compiled_artifacts_version,
)


class TestCompiledArtifactsVersion:
    """Tests for COMPILED_ARTIFACTS_VERSION constant."""

    @pytest.mark.requirement("SC-001")
    def test_version_is_semver_format(self) -> None:
        """Version MUST be in MAJOR.MINOR.PATCH format."""
        semver_pattern = r"^\d+\.\d+\.\d+$"
        assert re.match(semver_pattern, COMPILED_ARTIFACTS_VERSION), (
            f"Version '{COMPILED_ARTIFACTS_VERSION}' is not valid semver"
        )

    @pytest.mark.requirement("SC-001")
    def test_version_is_string(self) -> None:
        """Version MUST be a string type."""
        assert isinstance(COMPILED_ARTIFACTS_VERSION, str)

    @pytest.mark.requirement("SC-001")
    def test_version_not_empty(self) -> None:
        """Version MUST not be empty."""
        assert len(COMPILED_ARTIFACTS_VERSION) > 0


class TestVersionHistory:
    """Tests for COMPILED_ARTIFACTS_VERSION_HISTORY dictionary."""

    @pytest.mark.requirement("SC-001")
    def test_history_is_dict(self) -> None:
        """Version history MUST be a dictionary."""
        assert isinstance(COMPILED_ARTIFACTS_VERSION_HISTORY, dict)

    @pytest.mark.requirement("SC-001")
    def test_history_contains_current_version(self) -> None:
        """Current version MUST be documented in history."""
        assert COMPILED_ARTIFACTS_VERSION in COMPILED_ARTIFACTS_VERSION_HISTORY

    @pytest.mark.requirement("SC-001")
    def test_history_versions_are_semver(self) -> None:
        """All history versions MUST be valid semver."""
        semver_pattern = r"^\d+\.\d+\.\d+$"
        for version in COMPILED_ARTIFACTS_VERSION_HISTORY:
            assert re.match(semver_pattern, version), (
                f"History version '{version}' is not valid semver"
            )

    @pytest.mark.requirement("SC-001")
    def test_history_descriptions_are_strings(self) -> None:
        """All history descriptions MUST be strings."""
        for version, description in COMPILED_ARTIFACTS_VERSION_HISTORY.items():
            assert isinstance(description, str), f"Description for {version} is not a string"

    @pytest.mark.requirement("SC-001")
    def test_history_descriptions_not_empty(self) -> None:
        """All history descriptions MUST not be empty."""
        for version, description in COMPILED_ARTIFACTS_VERSION_HISTORY.items():
            assert len(description) > 0, f"Description for {version} is empty"


class TestGetCompiledArtifactsVersion:
    """Tests for get_compiled_artifacts_version() function."""

    @pytest.mark.requirement("SC-001")
    def test_returns_current_version(self) -> None:
        """Function MUST return the current version constant."""
        assert get_compiled_artifacts_version() == COMPILED_ARTIFACTS_VERSION

    @pytest.mark.requirement("SC-001")
    def test_returns_string(self) -> None:
        """Function MUST return a string."""
        assert isinstance(get_compiled_artifacts_version(), str)

    @pytest.mark.requirement("SC-001")
    def test_returns_semver(self) -> None:
        """Function MUST return valid semver."""
        semver_pattern = r"^\d+\.\d+\.\d+$"
        result = get_compiled_artifacts_version()
        assert re.match(semver_pattern, result)


class TestModuleExports:
    """Tests for module __all__ exports."""

    @pytest.mark.requirement("SC-001")
    def test_all_exports_defined(self) -> None:
        """Module MUST define __all__ exports."""
        from floe_core.schemas import versions

        assert hasattr(versions, "__all__")
        assert isinstance(versions.__all__, list)

    @pytest.mark.requirement("SC-001")
    def test_all_exports_are_importable(self) -> None:
        """All exports in __all__ MUST be importable."""
        from floe_core.schemas import versions

        for name in versions.__all__:
            assert hasattr(versions, name), f"Export '{name}' not found in module"

    @pytest.mark.requirement("SC-001")
    def test_expected_exports_present(self) -> None:
        """Expected exports MUST be in __all__."""
        from floe_core.schemas import versions

        expected = [
            "COMPILED_ARTIFACTS_VERSION",
            "COMPILED_ARTIFACTS_VERSION_HISTORY",
            "get_compiled_artifacts_version",
        ]
        for name in expected:
            assert name in versions.__all__, f"Expected export '{name}' not in __all__"

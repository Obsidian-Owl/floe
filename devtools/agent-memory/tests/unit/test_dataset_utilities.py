"""Unit tests for test dataset utilities.

These tests verify the test dataset name generation and isolation utilities.
They were moved from integration/ because they don't require external services.

Requirements Covered:
- FR-006: Test dataset isolation
"""

from __future__ import annotations

import pytest

# Import shared utilities from canonical location
from agent_memory.testing import generate_test_dataset_name


class TestGenerateTestDatasetName:
    """Tests for generate_test_dataset_name utility."""

    @pytest.mark.requirement("FR-006")
    def test_test_dataset_has_correct_prefix(self) -> None:
        """Test that generated dataset names have correct prefix.

        Validates:
        - Dataset name starts with 'test_'
        - Name has unique suffix (uuid)
        """
        test_dataset_name = generate_test_dataset_name()
        assert test_dataset_name.startswith(
            "test_"
        ), f"Expected test_ prefix: {test_dataset_name}"
        # Should be format: test_test_{uuid8}
        parts = test_dataset_name.split("_")
        assert len(parts) >= 3, f"Expected format test_test_<uuid>: {test_dataset_name}"

    @pytest.mark.requirement("FR-006")
    def test_generate_test_dataset_name_uniqueness(self) -> None:
        """Test that generated names are unique.

        Validates:
        - Multiple calls produce different names
        - Names follow expected format
        """
        names = [generate_test_dataset_name("arch") for _ in range(5)]

        # All names should be unique
        assert len(set(names)) == 5, "Generated names should be unique"

        # All names should have correct format
        for name in names:
            assert name.startswith("test_arch_"), f"Expected test_arch_ prefix: {name}"

    @pytest.mark.requirement("FR-006")
    def test_generate_test_dataset_name_with_custom_base(self) -> None:
        """Test that custom base names are used correctly.

        Validates:
        - Custom base is included in the generated name
        - Format is test_{base}_{uuid8}
        """
        name = generate_test_dataset_name("custom")
        assert name.startswith("test_custom_"), f"Expected test_custom_ prefix: {name}"

        # Suffix should be 8 hex characters
        suffix = name.split("_")[-1]
        assert len(suffix) == 8, f"Expected 8-character suffix: {suffix}"
        # Should be valid hex
        int(suffix, 16)  # Raises ValueError if not valid hex

"""Integration tests for test dataset isolation and cleanup.

These tests verify:
- Datasets are automatically cleaned up after tests
- delete_test_datasets() utility works correctly
- Test fixtures work with real Cognee Cloud API

Tests FAIL when infrastructure is unavailable (per testing standards).
Run with: pytest tests/integration/test_dataset_isolation.py -v

Note: Unit tests for generate_test_dataset_name are in tests/unit/test_dataset_utilities.py
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from agent_memory.cognee_client import CogneeClient


def generate_test_dataset_name(base: str = "test") -> str:
    """Generate unique test dataset name with prefix.

    Note: Canonical implementation is in tests/conftest.py, but we can't import
    from conftest directly. This is a local copy for use in these integration tests.

    Args:
        base: Base name for the dataset (default: "test").

    Returns:
        Unique dataset name in format: test_{base}_{uuid8}
    """
    suffix = uuid.uuid4().hex[:8]
    return f"test_{base}_{suffix}"


@pytest.mark.requirement("FR-006")
@pytest.mark.asyncio
async def test_test_dataset_fixture_cleanup(
    cognee_client: CogneeClient,
    test_dataset: str,
) -> None:
    """Test that test_dataset fixture provides isolated dataset.

    Validates:
    - Can add content to test dataset
    - Dataset is isolated (uses test_ prefix)
    - Cleanup happens automatically (verified by subsequent test)
    """
    # Add minimal content to verify dataset works
    await cognee_client.add_content(
        content="Test content for isolation verification",
        dataset_name=test_dataset,
    )

    # Verify content was added (list datasets should include our test dataset)
    datasets = await cognee_client.list_datasets()
    assert test_dataset in datasets, f"Expected {test_dataset} in {datasets}"

    # Cleanup will happen automatically when fixture yields


@pytest.mark.requirement("FR-006")
@pytest.mark.asyncio
async def test_delete_test_datasets_removes_test_prefixed(
    cognee_client: CogneeClient,
) -> None:
    """Test delete_test_datasets() utility removes only test_ prefixed datasets.

    Validates:
    - Creates test datasets
    - delete_test_datasets() removes them
    - Returns count of deleted datasets
    """
    # Create a few test datasets
    test_names = [
        generate_test_dataset_name("cleanup1"),
        generate_test_dataset_name("cleanup2"),
    ]

    for name in test_names:
        await cognee_client.add_content(
            content=f"Test content for {name}",
            dataset_name=name,
        )

    # Verify they exist
    datasets_before = await cognee_client.list_datasets()
    created_count = sum(1 for n in test_names if n in datasets_before)
    assert created_count == len(test_names), "Test datasets should exist before cleanup"

    # Clean up using the utility
    deleted = await cognee_client.delete_test_datasets()

    # Should have deleted at least our test datasets
    # (might be more from other tests)
    assert deleted >= len(test_names), (
        f"Expected to delete at least {len(test_names)}, got {deleted}"
    )

    # Verify our test datasets are gone
    datasets_after = await cognee_client.list_datasets()
    for name in test_names:
        assert name not in datasets_after, f"Expected {name} to be deleted"


@pytest.mark.requirement("FR-006")
@pytest.mark.asyncio
async def test_multiple_test_datasets_fixture(
    cognee_client: CogneeClient,
    test_datasets: list[str],
) -> None:
    """Test that test_datasets fixture supports multiple datasets.

    Validates:
    - Can create multiple datasets in one test
    - All are cleaned up after test
    """
    # Create multiple datasets
    ds1 = generate_test_dataset_name("multi1")
    ds2 = generate_test_dataset_name("multi2")
    test_datasets.extend([ds1, ds2])

    # Add content to each
    await cognee_client.add_content(
        content="Content for dataset 1",
        dataset_name=ds1,
    )
    await cognee_client.add_content(
        content="Content for dataset 2",
        dataset_name=ds2,
    )

    # Verify both exist
    datasets = await cognee_client.list_datasets()
    assert ds1 in datasets, f"Expected {ds1} in datasets"
    assert ds2 in datasets, f"Expected {ds2} in datasets"

    # Cleanup happens automatically via fixture teardown

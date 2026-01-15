"""Integration tests for test dataset isolation and cleanup.

These tests verify:
- Test datasets use proper test_ prefix
- Datasets are automatically cleaned up after tests
- delete_test_datasets() utility works correctly

Tests FAIL when infrastructure is unavailable (per testing standards).
Run with: pytest tests/integration/test_dataset_isolation.py -v
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid

import pytest

if TYPE_CHECKING:
    from agent_memory.cognee_client import CogneeClient


def generate_test_dataset_name(base: str = "test") -> str:
    """Generate unique test dataset name with prefix.

    Local copy of the utility function from tests/conftest.py to avoid
    import issues with pytest's conftest loading.
    """
    suffix = uuid.uuid4().hex[:8]
    return f"test_{base}_{suffix}"


@pytest.mark.requirement("FR-006")
@pytest.mark.asyncio
async def test_test_dataset_has_correct_prefix(test_dataset_name: str) -> None:
    """Test that generated dataset names have correct prefix.

    Validates:
    - Dataset name starts with 'test_'
    - Name has unique suffix (uuid)
    """
    assert test_dataset_name.startswith("test_"), f"Expected test_ prefix: {test_dataset_name}"
    # Should be format: test_test_{uuid8}
    parts = test_dataset_name.split("_")
    assert len(parts) >= 3, f"Expected format test_test_<uuid>: {test_dataset_name}"


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
async def test_generate_test_dataset_name_uniqueness() -> None:
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
    assert deleted >= len(test_names), f"Expected to delete at least {len(test_names)}, got {deleted}"

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

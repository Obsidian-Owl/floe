"""Pytest configuration for integration tests.

Integration tests require real Cognee Cloud credentials and connectivity.
Tests FAIL (not skip) when infrastructure is unavailable - this is intentional
per testing standards.

Test Isolation:
- All datasets use test_ prefix with unique suffixes
- Fixtures automatically clean up datasets after tests
- This prevents pollution of production datasets during development
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from agent_memory.cognee_client import CogneeClient
    from agent_memory.config import AgentMemoryConfig


@pytest.fixture
def cognee_config() -> AgentMemoryConfig:
    """Load Cognee configuration from environment.

    FAILS if required environment variables are not set.
    This is intentional - integration tests require real credentials.
    """
    from agent_memory.config import get_config

    try:
        return get_config()
    except Exception as e:
        pytest.fail(
            f"Configuration failed: {e}\n\n"
            "Integration tests require real credentials. Set:\n"
            "  COGNEE_API_KEY=<your-cognee-api-key>\n"
            "  OPENAI_API_KEY=<your-openai-api-key>\n\n"
            "Or run unit tests only: pytest tests/unit/"
        )


@pytest.fixture
def cognee_client(cognee_config: AgentMemoryConfig) -> CogneeClient:
    """Create CogneeClient with valid configuration.

    FAILS if configuration is invalid.
    """
    from agent_memory.cognee_client import CogneeClient

    return CogneeClient(cognee_config)


@pytest.fixture
def invalid_cognee_config(monkeypatch: pytest.MonkeyPatch) -> AgentMemoryConfig:
    """Create configuration with invalid API key for negative testing.

    Uses a clearly invalid key to test authentication failure handling.
    Uses monkeypatch for proper cleanup after test completes.
    """
    from pydantic import SecretStr

    from agent_memory.config import AgentMemoryConfig

    # Get original OpenAI key to preserve it (needed for some API calls)
    original_openai_key = os.environ.get("OPENAI_API_KEY", "sk-test-invalid")

    # Set invalid credentials - monkeypatch automatically restores after test
    monkeypatch.setenv("COGNEE_API_KEY", "invalid-test-key-12345")
    monkeypatch.setenv("OPENAI_API_KEY", original_openai_key)

    return AgentMemoryConfig(
        cognee_api_key=SecretStr("invalid-test-key-12345"),
        openai_api_key=SecretStr(original_openai_key),
    )


# =============================================================================
# Test Dataset Isolation Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def test_dataset(
    cognee_client: CogneeClient,
    test_dataset_name: str,
) -> AsyncGenerator[str, None]:
    """Provide isolated test dataset with automatic cleanup.

    This fixture ensures integration tests don't pollute production datasets.
    After the test completes, the dataset is automatically deleted.

    Args:
        cognee_client: Authenticated Cognee client fixture.
        test_dataset_name: Unique test dataset name with test_ prefix.

    Yields:
        Dataset name to use in the test.

    Example:
        >>> @pytest.mark.asyncio
        ... async def test_add_content(cognee_client, test_dataset):
        ...     await cognee_client.add_content("data", test_dataset)
        ...     # Dataset is auto-deleted after test
    """
    yield test_dataset_name

    # Cleanup: delete the test dataset after test completes
    try:
        await cognee_client.delete_dataset(test_dataset_name)
    except Exception:
        pass  # Best-effort cleanup - don't fail test on cleanup errors


@pytest_asyncio.fixture
async def test_datasets(
    cognee_client: CogneeClient,
) -> AsyncGenerator[list[str], None]:
    """Provide multiple isolated test datasets with automatic cleanup.

    Tests can create multiple datasets by appending to this list.
    All datasets in the list are cleaned up after the test completes.

    Args:
        cognee_client: Authenticated Cognee client fixture.

    Yields:
        List to append dataset names to.

    Example:
        >>> @pytest.mark.asyncio
        ... async def test_multi_dataset(cognee_client, test_datasets):
        ...     ds1 = generate_test_dataset_name("first")
        ...     ds2 = generate_test_dataset_name("second")
        ...     test_datasets.extend([ds1, ds2])
        ...     await cognee_client.add_content("data1", ds1)
        ...     await cognee_client.add_content("data2", ds2)
        ...     # Both datasets auto-deleted after test
    """
    dataset_names: list[str] = []
    yield dataset_names

    # Cleanup: delete all test datasets after test completes
    for name in dataset_names:
        try:
            await cognee_client.delete_dataset(name)
        except Exception:
            pass  # Best-effort cleanup

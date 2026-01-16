"""Shared pytest configuration and fixtures for agent-memory tests.

Provides shared fixtures across all test tiers:
- Mock Cognee client fixture for unit tests
- Real client fixture for integration tests (with credential check)
- Test data fixtures for common scenarios
- Session context fixtures
- Test dataset isolation (test_ prefix with auto-cleanup)

Implementation: T051 (FLO-636)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

# Import shared utilities from canonical location
from agent_memory.testing import generate_test_dataset_name

if TYPE_CHECKING:
    from agent_memory.session import DecisionRecord, SessionContext


# =============================================================================
# Test Isolation Utilities
# =============================================================================


class TestDatasetFixture:
    """Helper class for managing unique test datasets with cleanup tracking.

    Provides unique dataset names and tracks created datasets for cleanup.
    Used by integration tests to ensure test isolation and prevent pollution
    of production datasets.

    Implementation: T005 (FLO-693)

    Attributes:
        datasets: Set of dataset names created during the test.

    Example:
        >>> fixture = TestDatasetFixture()
        >>> name = fixture.create("architecture")
        >>> print(name)  # "test_architecture_a1b2c3d4"
        >>> fixture.datasets  # {"test_architecture_a1b2c3d4"}
        >>> # After test, cleanup:
        >>> for dataset in fixture.datasets:
        ...     await client.delete_dataset(dataset)
    """

    def __init__(self) -> None:
        """Initialize with empty dataset tracking."""
        self.datasets: set[str] = set()

    def create(self, base: str = "test") -> str:
        """Create a unique dataset name and track it for cleanup.

        Args:
            base: Base name for the dataset (default: "test").

        Returns:
            Unique dataset name in format: test_{base}_{uuid8}

        Example:
            >>> fixture = TestDatasetFixture()
            >>> name = fixture.create("contract")
            >>> name.startswith("test_contract_")
            True
        """
        name = generate_test_dataset_name(base)
        self.datasets.add(name)
        return name

    def clear(self) -> None:
        """Clear the tracked datasets.

        Call this after cleanup has been performed.
        """
        self.datasets.clear()


@pytest.fixture
def test_dataset_fixture() -> TestDatasetFixture:
    """Provide a TestDatasetFixture for managing test datasets.

    Returns:
        Fresh TestDatasetFixture instance.

    Example:
        >>> async def test_isolation(test_dataset_fixture, cognee_client):
        ...     dataset = test_dataset_fixture.create("isolation")
        ...     await cognee_client.add_content("data", dataset)
        ...     # Test logic...
        ...     # Cleanup tracked datasets
        ...     for ds in test_dataset_fixture.datasets:
        ...         await cognee_client.delete_dataset(ds)
    """
    return TestDatasetFixture()


@pytest.fixture
def test_dataset_name() -> str:
    """Provide a unique test dataset name.

    Returns:
        Unique dataset name with test_ prefix.

    Example:
        >>> def test_something(test_dataset_name):
        ...     # test_dataset_name is "test_test_a1b2c3d4"
        ...     await client.add_content("data", test_dataset_name)
    """
    return generate_test_dataset_name()


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock AgentMemoryConfig for unit tests.

    Returns:
        MagicMock configured to behave like AgentMemoryConfig.

    Example:
        >>> def test_something(mock_config):
        ...     # mock_config can be used anywhere config is needed
        ...     client = SomeClass(mock_config)
    """
    config = MagicMock()
    config.cognee_api_url = "https://api.cognee.ai"
    config.cognee_api_key.get_secret_value.return_value = "test-api-key"
    config.openai_api_key.get_secret_value.return_value = "sk-test-key"
    config.llm_provider = "openai"
    config.get_llm_api_key.return_value = "sk-test-key"
    return config


# =============================================================================
# Mock Client Fixtures
# =============================================================================


@pytest.fixture
def mock_cognee_client(mock_config: MagicMock) -> MagicMock:
    """Create a mock CogneeClient for unit tests.

    The mock client has all async methods configured as AsyncMock
    with sensible default return values.

    Args:
        mock_config: Mock configuration fixture.

    Returns:
        MagicMock configured to behave like CogneeClient.

    Example:
        >>> def test_add_content(mock_cognee_client):
        ...     mock_cognee_client.add_content.return_value = None
        ...     # Use mock_cognee_client in test
    """
    client = MagicMock()

    # Configure async methods
    client.validate_connection = AsyncMock(return_value=100.0)
    client.add_content = AsyncMock(return_value=None)
    client.cognify = AsyncMock(return_value=None)
    client.search = AsyncMock(return_value=_create_empty_search_result())
    client.health_check = AsyncMock(return_value=_create_healthy_status())
    client.reset_dataset = AsyncMock(return_value=None)
    client.delete_dataset = AsyncMock(return_value=None)

    # Store config reference
    client._config = mock_config

    return client


def _create_empty_search_result() -> MagicMock:
    """Create an empty search result mock."""
    result = MagicMock()
    result.results = []
    result.query = ""
    result.search_type = "GRAPH_COMPLETION"
    return result


def _create_healthy_status() -> MagicMock:
    """Create a healthy status mock."""
    status = MagicMock()
    status.overall_status = "healthy"
    status.cognee = MagicMock(status="healthy", message="Connected")
    status.llm = MagicMock(status="healthy", message="Configured")
    status.local = MagicMock(status="healthy", message="OK")
    return status


# =============================================================================
# Session Context Fixtures
# =============================================================================


@pytest.fixture
def sample_decision_record() -> DecisionRecord:
    """Create a sample DecisionRecord for testing.

    Returns:
        DecisionRecord with test data.

    Example:
        >>> def test_decision_handling(sample_decision_record):
        ...     assert sample_decision_record.decision == "Use Pydantic v2"
    """
    from agent_memory.session import DecisionRecord

    return DecisionRecord(
        decision="Use Pydantic v2 for all models",
        rationale="Better validation and performance",
        alternatives_considered=["dataclasses", "attrs"],
        timestamp=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_session_context(sample_decision_record: DecisionRecord) -> SessionContext:
    """Create a sample SessionContext for testing.

    Args:
        sample_decision_record: Decision record fixture.

    Returns:
        SessionContext with test data.

    Example:
        >>> def test_session_handling(sample_session_context):
        ...     assert len(sample_session_context.active_work_areas) == 2
    """
    from agent_memory.session import SessionContext

    return SessionContext(
        session_id=UUID("12345678-1234-5678-1234-567812345678"),
        captured_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        active_work_areas=["src/agent_memory/session.py", "tests/unit/test_session.py"],
        recent_decisions=[sample_decision_record],
        related_closed_tasks=["FLO-123", "FLO-456"],
        conversation_summary="Implemented session management feature",
    )


@pytest.fixture
def empty_session_context() -> SessionContext:
    """Create an empty SessionContext for testing edge cases.

    Returns:
        SessionContext with no data (all defaults).

    Example:
        >>> def test_empty_context(empty_session_context):
        ...     assert empty_session_context.active_work_areas == []
    """
    from agent_memory.session import SessionContext

    return SessionContext()


# =============================================================================
# Search Result Fixtures
# =============================================================================


@pytest.fixture
def mock_search_result_with_session() -> MagicMock:
    """Create a mock search result containing session context.

    Returns:
        MagicMock with session context in results.

    Example:
        >>> def test_retrieve_session(mock_cognee_client, mock_search_result_with_session):
        ...     mock_cognee_client.search.return_value = mock_search_result_with_session
    """
    result_item = MagicMock()
    result_item.content = """SESSION CONTEXT: 12345678-1234-5678-1234-567812345678
Captured: 2026-01-15T10:00:00+00:00

Work Areas:
  - src/agent_memory/session.py
  - tests/unit/test_session.py

Related Tasks:
  - FLO-123
  - FLO-456

Decisions:
  - Use Pydantic v2 for all models

Summary:
  Implemented session management feature"""

    result = MagicMock()
    result.results = [result_item]
    result.query = "session context for test-area"
    result.search_type = "GRAPH_COMPLETION"
    return result


@pytest.fixture
def mock_search_result_empty() -> MagicMock:
    """Create an empty mock search result.

    Returns:
        MagicMock with no results.

    Example:
        >>> def test_no_results(mock_cognee_client, mock_search_result_empty):
        ...     mock_cognee_client.search.return_value = mock_search_result_empty
    """
    result = MagicMock()
    result.results = []
    result.query = "session context for unknown-area"
    result.search_type = "GRAPH_COMPLETION"
    return result


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_markdown_content() -> str:
    """Provide sample markdown content for testing parsers.

    Returns:
        Sample markdown string with various elements.
    """
    return """# Sample Document

## Overview

This is a sample document for testing markdown parsing.

## Code Example

```python
def hello():
    print("Hello, World!")
```

## Lists

- Item 1
- Item 2
- Item 3

## Links

See [documentation](https://example.com) for more info.
"""


@pytest.fixture
def sample_python_source() -> str:
    """Provide sample Python source code for testing extractors.

    Returns:
        Sample Python code with docstrings and functions.
    """
    return '''"""Sample module docstring.

This module provides sample functionality for testing.
"""

from __future__ import annotations


def sample_function(arg1: str, arg2: int = 0) -> str:
    """Sample function with docstring.

    Args:
        arg1: First argument.
        arg2: Second argument with default.

    Returns:
        Formatted string result.
    """
    return f"{arg1}: {arg2}"


class SampleClass:
    """Sample class for testing.

    Attributes:
        value: The stored value.
    """

    def __init__(self, value: str) -> None:
        """Initialize with value."""
        self.value = value

    def get_value(self) -> str:
        """Return the stored value."""
        return self.value
'''


# =============================================================================
# CLI Test Fixtures
# =============================================================================


@pytest.fixture
def cli_runner() -> Any:
    """Create a Typer CLI runner for testing commands.

    Returns:
        CliRunner instance for invoking CLI commands.

    Example:
        >>> def test_cli_command(cli_runner):
        ...     from agent_memory.cli import app
        ...     result = cli_runner.invoke(app, ["--help"])
        ...     assert result.exit_code == 0
    """
    from typer.testing import CliRunner

    return CliRunner()


# =============================================================================
# Requirement Marker Registration
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers.

    Registers the requirement marker for test traceability.
    """
    config.addinivalue_line(
        "markers",
        "requirement(id): Link test to a requirement ID (e.g., FR-001)",
    )

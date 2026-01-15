"""Unit tests for shared conftest fixtures.

Validates that shared fixtures work correctly across test modules.

Implementation: T051 (FLO-636)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestMockConfigFixture:
    """Tests for mock_config fixture."""

    @pytest.mark.requirement("FR-016")
    def test_mock_config_has_cognee_url(self, mock_config: MagicMock) -> None:
        """Test mock_config provides cognee_api_url."""
        assert mock_config.cognee_api_url == "https://api.cognee.ai"

    @pytest.mark.requirement("FR-016")
    def test_mock_config_has_api_key(self, mock_config: MagicMock) -> None:
        """Test mock_config provides cognee_api_key."""
        assert mock_config.cognee_api_key.get_secret_value() == "test-api-key"

    @pytest.mark.requirement("FR-016")
    def test_mock_config_has_llm_provider(self, mock_config: MagicMock) -> None:
        """Test mock_config provides llm_provider."""
        assert mock_config.llm_provider == "openai"


class TestMockCogneeClientFixture:
    """Tests for mock_cognee_client fixture."""

    @pytest.mark.requirement("FR-016")
    def test_mock_client_has_async_methods(self, mock_cognee_client: MagicMock) -> None:
        """Test mock_cognee_client has all async methods configured."""
        # Verify async methods exist
        assert hasattr(mock_cognee_client, "validate_connection")
        assert hasattr(mock_cognee_client, "add_content")
        assert hasattr(mock_cognee_client, "cognify")
        assert hasattr(mock_cognee_client, "search")
        assert hasattr(mock_cognee_client, "health_check")

    @pytest.mark.requirement("FR-016")
    @pytest.mark.asyncio
    async def test_mock_client_validate_connection(self, mock_cognee_client: MagicMock) -> None:
        """Test mock_cognee_client.validate_connection returns latency."""
        result = await mock_cognee_client.validate_connection()
        assert result == 100.0

    @pytest.mark.requirement("FR-016")
    @pytest.mark.asyncio
    async def test_mock_client_search_returns_empty(self, mock_cognee_client: MagicMock) -> None:
        """Test mock_cognee_client.search returns empty results by default."""
        result = await mock_cognee_client.search("test query")
        assert result.results == []


class TestSampleDecisionRecordFixture:
    """Tests for sample_decision_record fixture."""

    @pytest.mark.requirement("FR-016")
    def test_sample_decision_has_content(self, sample_decision_record) -> None:
        """Test sample_decision_record has expected content."""
        assert "Pydantic v2" in sample_decision_record.decision
        assert sample_decision_record.rationale != ""
        assert len(sample_decision_record.alternatives_considered) > 0


class TestSampleSessionContextFixture:
    """Tests for sample_session_context fixture."""

    @pytest.mark.requirement("FR-016")
    def test_sample_context_has_work_areas(self, sample_session_context) -> None:
        """Test sample_session_context has work areas."""
        assert len(sample_session_context.active_work_areas) == 2
        assert any("session.py" in area for area in sample_session_context.active_work_areas)

    @pytest.mark.requirement("FR-016")
    def test_sample_context_has_tasks(self, sample_session_context) -> None:
        """Test sample_session_context has related tasks."""
        assert "FLO-123" in sample_session_context.related_closed_tasks
        assert "FLO-456" in sample_session_context.related_closed_tasks

    @pytest.mark.requirement("FR-016")
    def test_sample_context_has_decisions(self, sample_session_context) -> None:
        """Test sample_session_context has decisions."""
        assert len(sample_session_context.recent_decisions) == 1


class TestEmptySessionContextFixture:
    """Tests for empty_session_context fixture."""

    @pytest.mark.requirement("FR-016")
    def test_empty_context_has_no_work_areas(self, empty_session_context) -> None:
        """Test empty_session_context has no work areas."""
        assert empty_session_context.active_work_areas == []

    @pytest.mark.requirement("FR-016")
    def test_empty_context_has_no_tasks(self, empty_session_context) -> None:
        """Test empty_session_context has no tasks."""
        assert empty_session_context.related_closed_tasks == []

    @pytest.mark.requirement("FR-016")
    def test_empty_context_has_session_id(self, empty_session_context) -> None:
        """Test empty_session_context still has auto-generated session_id."""
        assert empty_session_context.session_id is not None


class TestMockSearchResultFixtures:
    """Tests for mock search result fixtures."""

    @pytest.mark.requirement("FR-016")
    def test_search_result_with_session_has_content(
        self, mock_search_result_with_session: MagicMock
    ) -> None:
        """Test mock_search_result_with_session contains session data."""
        assert len(mock_search_result_with_session.results) == 1
        content = mock_search_result_with_session.results[0].content
        assert "SESSION CONTEXT:" in content
        assert "FLO-123" in content

    @pytest.mark.requirement("FR-016")
    def test_search_result_empty_has_no_results(self, mock_search_result_empty: MagicMock) -> None:
        """Test mock_search_result_empty has no results."""
        assert mock_search_result_empty.results == []


class TestTestDataFixtures:
    """Tests for test data fixtures."""

    @pytest.mark.requirement("FR-016")
    def test_sample_markdown_content(self, sample_markdown_content: str) -> None:
        """Test sample_markdown_content has expected sections."""
        assert "# Sample Document" in sample_markdown_content
        assert "```python" in sample_markdown_content
        assert "- Item 1" in sample_markdown_content

    @pytest.mark.requirement("FR-016")
    def test_sample_python_source(self, sample_python_source: str) -> None:
        """Test sample_python_source has expected elements."""
        assert "def sample_function" in sample_python_source
        assert "class SampleClass" in sample_python_source
        assert '"""Sample module docstring.' in sample_python_source


class TestCliRunnerFixture:
    """Tests for cli_runner fixture."""

    @pytest.mark.requirement("FR-016")
    def test_cli_runner_can_invoke(self, cli_runner) -> None:
        """Test cli_runner can invoke CLI commands."""
        from agent_memory.cli import app

        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

"""Unit tests for session.py - session context management module.

Tests for session context functionality:
- DecisionRecord model
- SessionContext model
- capture_session_context function
- save_session_context function
- retrieve_session_context function
- Format and parse helpers

Implementation: T047 (FLO-632)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest


class TestDecisionRecordModel:
    """Tests for DecisionRecord model."""

    @pytest.mark.requirement("FR-016")
    def test_decision_record_has_required_fields(self) -> None:
        """Test DecisionRecord model has all required fields."""
        from agent_memory.session import DecisionRecord

        record = DecisionRecord(
            decision="Use Pydantic v2 for all models",
            rationale="Better validation and performance",
            alternatives_considered=["dataclasses", "attrs"],
        )

        assert record.decision == "Use Pydantic v2 for all models"
        assert record.rationale == "Better validation and performance"
        assert record.alternatives_considered == ["dataclasses", "attrs"]
        assert record.timestamp is not None

    @pytest.mark.requirement("FR-016")
    def test_decision_record_defaults(self) -> None:
        """Test DecisionRecord model default values."""
        from agent_memory.session import DecisionRecord

        record = DecisionRecord(decision="Simple decision")

        assert record.decision == "Simple decision"
        assert record.rationale == ""
        assert record.alternatives_considered == []
        assert record.timestamp is not None

    @pytest.mark.requirement("FR-016")
    def test_decision_record_requires_decision(self) -> None:
        """Test DecisionRecord model requires non-empty decision."""
        from pydantic import ValidationError

        from agent_memory.session import DecisionRecord

        with pytest.raises(ValidationError):
            DecisionRecord(decision="")

    @pytest.mark.requirement("FR-016")
    def test_decision_record_frozen(self) -> None:
        """Test DecisionRecord is immutable."""
        from pydantic import ValidationError

        from agent_memory.session import DecisionRecord

        record = DecisionRecord(decision="Test")

        with pytest.raises(ValidationError):
            record.decision = "Changed"  # type: ignore[misc]


class TestSessionContextModel:
    """Tests for SessionContext model."""

    @pytest.mark.requirement("FR-016")
    def test_session_context_has_required_fields(self) -> None:
        """Test SessionContext model has all required fields."""
        from agent_memory.session import DecisionRecord, SessionContext

        decisions = [
            DecisionRecord(decision="Decision 1"),
            DecisionRecord(decision="Decision 2"),
        ]

        context = SessionContext(
            active_work_areas=["src/module.py", "tests/test_module.py"],
            recent_decisions=decisions,
            related_closed_tasks=["FLO-123", "FLO-456"],
            conversation_summary="Worked on module implementation",
        )

        assert len(context.active_work_areas) == 2
        assert len(context.recent_decisions) == 2
        assert len(context.related_closed_tasks) == 2
        assert context.conversation_summary == "Worked on module implementation"
        assert context.session_id is not None
        assert context.captured_at is not None

    @pytest.mark.requirement("FR-016")
    def test_session_context_defaults(self) -> None:
        """Test SessionContext model default values."""
        from agent_memory.session import SessionContext

        context = SessionContext()

        assert context.active_work_areas == []
        assert context.recent_decisions == []
        assert context.related_closed_tasks == []
        assert context.conversation_summary is None
        assert isinstance(context.session_id, UUID)
        assert isinstance(context.captured_at, datetime)

    @pytest.mark.requirement("FR-016")
    def test_session_context_frozen(self) -> None:
        """Test SessionContext is immutable."""
        from pydantic import ValidationError

        from agent_memory.session import SessionContext

        context = SessionContext()

        with pytest.raises(ValidationError):
            context.conversation_summary = "Changed"  # type: ignore[misc]


class TestCaptureSessionContext:
    """Tests for capture_session_context function."""

    @pytest.mark.requirement("FR-016")
    def test_capture_with_issues_and_decisions(self) -> None:
        """Test capturing context with issues and decisions."""
        from agent_memory.session import capture_session_context

        context = capture_session_context(
            active_issues=["FLO-123", "FLO-456"],
            decisions=["Use REST API", "Add caching"],
        )

        assert context.related_closed_tasks == ["FLO-123", "FLO-456"]
        assert len(context.recent_decisions) == 2
        assert context.recent_decisions[0].decision == "Use REST API"
        assert context.recent_decisions[1].decision == "Add caching"

    @pytest.mark.requirement("FR-016")
    def test_capture_with_work_areas(self) -> None:
        """Test capturing context with work areas."""
        from agent_memory.session import capture_session_context

        context = capture_session_context(
            active_issues=[],
            decisions=[],
            work_areas=["src/session.py", "tests/test_session.py"],
        )

        assert context.active_work_areas == ["src/session.py", "tests/test_session.py"]

    @pytest.mark.requirement("FR-016")
    def test_capture_with_summary(self) -> None:
        """Test capturing context with summary."""
        from agent_memory.session import capture_session_context

        context = capture_session_context(
            active_issues=["FLO-123"],
            decisions=[],
            summary="Implemented session recovery feature",
        )

        assert context.conversation_summary == "Implemented session recovery feature"

    @pytest.mark.requirement("FR-016")
    def test_capture_empty_context(self) -> None:
        """Test capturing empty context."""
        from agent_memory.session import capture_session_context

        context = capture_session_context(active_issues=[], decisions=[])

        assert context.related_closed_tasks == []
        assert context.recent_decisions == []
        assert context.active_work_areas == []
        assert context.conversation_summary is None

    @pytest.mark.requirement("FR-016")
    def test_capture_generates_unique_session_id(self) -> None:
        """Test that each capture generates unique session ID."""
        from agent_memory.session import capture_session_context

        context1 = capture_session_context(active_issues=[], decisions=[])
        context2 = capture_session_context(active_issues=[], decisions=[])

        assert context1.session_id != context2.session_id


class TestSaveSessionContext:
    """Tests for save_session_context function."""

    @pytest.mark.requirement("FR-016")
    @pytest.mark.asyncio
    async def test_save_calls_add_content(self) -> None:
        """Test save_session_context calls client.add_content."""
        from agent_memory.session import SessionContext, save_session_context

        mock_client = MagicMock()
        mock_client.add_content = AsyncMock()

        context = SessionContext(
            active_work_areas=["src/module.py"],
            related_closed_tasks=["FLO-123"],
        )

        await save_session_context(mock_client, context)

        mock_client.add_content.assert_called_once()
        call_kwargs = mock_client.add_content.call_args.kwargs
        assert call_kwargs["dataset_name"] == "sessions"
        assert "SESSION CONTEXT:" in call_kwargs["content"]

    @pytest.mark.requirement("FR-016")
    @pytest.mark.asyncio
    async def test_save_uses_custom_dataset(self) -> None:
        """Test save_session_context uses custom dataset name."""
        from agent_memory.session import SessionContext, save_session_context

        mock_client = MagicMock()
        mock_client.add_content = AsyncMock()

        context = SessionContext()

        await save_session_context(mock_client, context, dataset="custom_sessions")

        call_kwargs = mock_client.add_content.call_args.kwargs
        assert call_kwargs["dataset_name"] == "custom_sessions"

    @pytest.mark.requirement("FR-016")
    @pytest.mark.asyncio
    async def test_save_formats_context_content(self) -> None:
        """Test save_session_context formats context for storage."""
        from agent_memory.session import (
            DecisionRecord,
            SessionContext,
            save_session_context,
        )

        mock_client = MagicMock()
        mock_client.add_content = AsyncMock()

        context = SessionContext(
            active_work_areas=["src/module.py"],
            recent_decisions=[DecisionRecord(decision="Test decision")],
            related_closed_tasks=["FLO-123"],
            conversation_summary="Test summary",
        )

        await save_session_context(mock_client, context)

        content = mock_client.add_content.call_args.kwargs["content"]
        assert "Work Areas:" in content
        assert "src/module.py" in content
        assert "Related Tasks:" in content
        assert "FLO-123" in content
        assert "Decisions:" in content
        assert "Test decision" in content
        assert "Summary:" in content
        assert "Test summary" in content


class TestRetrieveSessionContext:
    """Tests for retrieve_session_context function."""

    @pytest.mark.requirement("FR-016")
    @pytest.mark.asyncio
    async def test_retrieve_calls_search(self) -> None:
        """Test retrieve_session_context calls client.search."""
        from agent_memory.session import retrieve_session_context

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.results = []
        mock_client.search = AsyncMock(return_value=mock_result)

        await retrieve_session_context(mock_client, "plugin-system")

        mock_client.search.assert_called_once()
        call_args = mock_client.search.call_args
        assert "plugin-system" in call_args[0][0]

    @pytest.mark.requirement("FR-016")
    @pytest.mark.asyncio
    async def test_retrieve_returns_none_when_no_results(self) -> None:
        """Test retrieve returns None when no results found."""
        from agent_memory.session import retrieve_session_context

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.results = []
        mock_client.search = AsyncMock(return_value=mock_result)

        context = await retrieve_session_context(mock_client, "unknown-area")

        assert context is None

    @pytest.mark.requirement("FR-016")
    @pytest.mark.asyncio
    async def test_retrieve_parses_session_context(self) -> None:
        """Test retrieve parses session context from results."""
        from agent_memory.session import retrieve_session_context

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_item = MagicMock()
        mock_item.content = """SESSION CONTEXT: 12345678-1234-5678-1234-567812345678
Captured: 2026-01-15T00:00:00+00:00

Work Areas:
  - src/module.py

Related Tasks:
  - FLO-123
  - FLO-456

Decisions:
  - Use REST API

Summary:
  Test summary"""
        mock_result.results = [mock_item]
        mock_client.search = AsyncMock(return_value=mock_result)

        context = await retrieve_session_context(mock_client, "test-area")

        assert context is not None
        assert context.active_work_areas == ["src/module.py"]
        assert context.related_closed_tasks == ["FLO-123", "FLO-456"]
        assert len(context.recent_decisions) == 1
        assert context.recent_decisions[0].decision == "Use REST API"

    @pytest.mark.requirement("FR-016")
    @pytest.mark.asyncio
    async def test_retrieve_returns_none_for_invalid_content(self) -> None:
        """Test retrieve returns None for non-session content."""
        from agent_memory.session import retrieve_session_context

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_item = MagicMock()
        mock_item.content = "Some random content without session markers"
        mock_result.results = [mock_item]
        mock_client.search = AsyncMock(return_value=mock_result)

        context = await retrieve_session_context(mock_client, "test-area")

        assert context is None


class TestFormatContextForStorage:
    """Tests for _format_context_for_storage helper."""

    @pytest.mark.requirement("FR-016")
    def test_format_includes_session_id(self) -> None:
        """Test format includes session ID."""
        from agent_memory.session import SessionContext, _format_context_for_storage

        context = SessionContext()
        content = _format_context_for_storage(context)

        assert "SESSION CONTEXT:" in content
        assert str(context.session_id) in content

    @pytest.mark.requirement("FR-016")
    def test_format_includes_work_areas(self) -> None:
        """Test format includes work areas."""
        from agent_memory.session import SessionContext, _format_context_for_storage

        context = SessionContext(active_work_areas=["src/a.py", "src/b.py"])
        content = _format_context_for_storage(context)

        assert "Work Areas:" in content
        assert "src/a.py" in content
        assert "src/b.py" in content

    @pytest.mark.requirement("FR-016")
    def test_format_includes_tasks(self) -> None:
        """Test format includes related tasks."""
        from agent_memory.session import SessionContext, _format_context_for_storage

        context = SessionContext(related_closed_tasks=["FLO-1", "FLO-2"])
        content = _format_context_for_storage(context)

        assert "Related Tasks:" in content
        assert "FLO-1" in content
        assert "FLO-2" in content

    @pytest.mark.requirement("FR-016")
    def test_format_includes_decisions_with_rationale(self) -> None:
        """Test format includes decisions with rationale."""
        from agent_memory.session import (
            DecisionRecord,
            SessionContext,
            _format_context_for_storage,
        )

        decisions = [DecisionRecord(decision="Test", rationale="Because reasons")]
        context = SessionContext(recent_decisions=decisions)
        content = _format_context_for_storage(context)

        assert "Decisions:" in content
        assert "Test" in content
        assert "Rationale: Because reasons" in content


class TestParseContextFromResult:
    """Tests for _parse_context_from_result helper."""

    @pytest.mark.requirement("FR-016")
    def test_parse_returns_none_without_marker(self) -> None:
        """Test parse returns None without session marker."""
        from agent_memory.session import _parse_context_from_result

        result = _parse_context_from_result("Random content")
        assert result is None

    @pytest.mark.requirement("FR-016")
    def test_parse_extracts_work_areas(self) -> None:
        """Test parse extracts work areas."""
        from agent_memory.session import _parse_context_from_result

        content = """SESSION CONTEXT: test-id
Work Areas:
  - src/module.py
  - tests/test_module.py"""

        result = _parse_context_from_result(content)

        assert result is not None
        assert result.active_work_areas == ["src/module.py", "tests/test_module.py"]

    @pytest.mark.requirement("FR-016")
    def test_parse_extracts_tasks(self) -> None:
        """Test parse extracts related tasks."""
        from agent_memory.session import _parse_context_from_result

        content = """SESSION CONTEXT: test-id
Related Tasks:
  - FLO-123
  - FLO-456"""

        result = _parse_context_from_result(content)

        assert result is not None
        assert result.related_closed_tasks == ["FLO-123", "FLO-456"]

    @pytest.mark.requirement("FR-016")
    def test_parse_handles_empty_sections(self) -> None:
        """Test parse handles content with no sections."""
        from agent_memory.session import _parse_context_from_result

        content = "SESSION CONTEXT: test-id\nCaptured: 2026-01-15"

        result = _parse_context_from_result(content)

        assert result is not None
        assert result.active_work_areas == []
        assert result.related_closed_tasks == []

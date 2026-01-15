"""Unit tests for CLI session-recover command.

Tests for the session-recover command functionality:
- Work area argument parsing
- Session context retrieval from knowledge graph
- Display of prior work, tasks, and decisions
- Error handling for missing context

Implementation: T049 (FLO-634)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

runner = CliRunner()


class TestSessionRecoverCommand:
    """Tests for session-recover CLI command."""

    @pytest.mark.requirement("FR-016")
    def test_session_recover_requires_work_area(self) -> None:
        """Test that session-recover requires --work-area argument."""
        from agent_memory.cli import app

        result = runner.invoke(app, ["session-recover"])

        # Should fail without work-area argument
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-016")
    def test_session_recover_retrieves_context(self) -> None:
        """Test that session-recover retrieves context for work area."""
        from agent_memory.cli import app
        from agent_memory.session import DecisionRecord, SessionContext

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.retrieve_session_context") as mock_retrieve,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_context = SessionContext(
                active_work_areas=["src/module.py"],
                related_closed_tasks=["FLO-123"],
                recent_decisions=[DecisionRecord(decision="Use REST API")],
                conversation_summary="Implemented API endpoints",
            )
            mock_retrieve.return_value = mock_context

            result = runner.invoke(app, ["session-recover", "--work-area", "plugin-system"])

            assert result.exit_code == 0
            mock_retrieve.assert_called_once()
            call_args = mock_retrieve.call_args
            assert call_args[0][1] == "plugin-system"

    @pytest.mark.requirement("FR-016")
    def test_session_recover_displays_work_areas(self) -> None:
        """Test that session-recover displays work areas from context."""
        from agent_memory.cli import app
        from agent_memory.session import SessionContext

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.retrieve_session_context") as mock_retrieve,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_context = SessionContext(
                active_work_areas=["src/api.py", "tests/test_api.py"],
                related_closed_tasks=[],
                recent_decisions=[],
            )
            mock_retrieve.return_value = mock_context

            result = runner.invoke(app, ["session-recover", "--work-area", "api"])

            assert result.exit_code == 0
            assert "src/api.py" in result.output
            assert "tests/test_api.py" in result.output

    @pytest.mark.requirement("FR-016")
    def test_session_recover_displays_closed_tasks(self) -> None:
        """Test that session-recover displays related closed tasks."""
        from agent_memory.cli import app
        from agent_memory.session import SessionContext

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.retrieve_session_context") as mock_retrieve,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_context = SessionContext(
                active_work_areas=[],
                related_closed_tasks=["FLO-123", "FLO-456", "FLO-789"],
                recent_decisions=[],
            )
            mock_retrieve.return_value = mock_context

            result = runner.invoke(app, ["session-recover", "--work-area", "plugin"])

            assert result.exit_code == 0
            assert "FLO-123" in result.output
            assert "FLO-456" in result.output
            assert "FLO-789" in result.output

    @pytest.mark.requirement("FR-016")
    def test_session_recover_displays_decisions(self) -> None:
        """Test that session-recover displays decision history."""
        from agent_memory.cli import app
        from agent_memory.session import DecisionRecord, SessionContext

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.retrieve_session_context") as mock_retrieve,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_context = SessionContext(
                active_work_areas=[],
                related_closed_tasks=[],
                recent_decisions=[
                    DecisionRecord(decision="Use Pydantic v2"),
                    DecisionRecord(decision="Add caching layer"),
                ],
            )
            mock_retrieve.return_value = mock_context

            result = runner.invoke(app, ["session-recover", "--work-area", "models"])

            assert result.exit_code == 0
            assert "Use Pydantic v2" in result.output
            assert "Add caching layer" in result.output

    @pytest.mark.requirement("FR-016")
    def test_session_recover_displays_summary(self) -> None:
        """Test that session-recover displays conversation summary."""
        from agent_memory.cli import app
        from agent_memory.session import SessionContext

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.retrieve_session_context") as mock_retrieve,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_context = SessionContext(
                active_work_areas=[],
                related_closed_tasks=[],
                recent_decisions=[],
                conversation_summary="Implemented session recovery feature",
            )
            mock_retrieve.return_value = mock_context

            result = runner.invoke(app, ["session-recover", "--work-area", "session"])

            assert result.exit_code == 0
            assert "Implemented session recovery feature" in result.output

    @pytest.mark.requirement("FR-016")
    def test_session_recover_handles_no_context_found(self) -> None:
        """Test that session-recover handles case when no context found."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.retrieve_session_context") as mock_retrieve,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_retrieve.return_value = None

            result = runner.invoke(app, ["session-recover", "--work-area", "unknown-area"])

            assert result.exit_code == 0
            assert "No prior session" in result.output or "not found" in result.output.lower()

    @pytest.mark.requirement("FR-016")
    def test_session_recover_fails_without_config(self) -> None:
        """Test that session-recover fails if config cannot be loaded."""
        from agent_memory.cli import app

        with patch("agent_memory.cli._load_config") as mock_config:
            mock_config.return_value = None

            result = runner.invoke(app, ["session-recover", "--work-area", "test"])

            assert result.exit_code == 1

    @pytest.mark.requirement("FR-016")
    def test_session_recover_handles_client_error(self) -> None:
        """Test that session-recover handles client errors gracefully."""
        from agent_memory.cli import app
        from agent_memory.cognee_client import CogneeClientError

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.retrieve_session_context") as mock_retrieve,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_retrieve.side_effect = CogneeClientError("API error")

            result = runner.invoke(app, ["session-recover", "--work-area", "test"])

            assert result.exit_code == 1
            assert "API error" in result.output

    @pytest.mark.requirement("FR-016")
    def test_session_recover_displays_session_id(self) -> None:
        """Test that session-recover displays the session ID."""
        from uuid import UUID

        from agent_memory.cli import app
        from agent_memory.session import SessionContext

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.retrieve_session_context") as mock_retrieve,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            test_uuid = UUID("12345678-1234-5678-1234-567812345678")
            mock_context = SessionContext(
                session_id=test_uuid,
                active_work_areas=["src/module.py"],
            )
            mock_retrieve.return_value = mock_context

            result = runner.invoke(app, ["session-recover", "--work-area", "module"])

            assert result.exit_code == 0
            assert "12345678-1234-5678-1234-567812345678" in result.output

    @pytest.mark.requirement("FR-016")
    def test_session_recover_displays_timestamp(self) -> None:
        """Test that session-recover displays the capture timestamp."""
        from agent_memory.cli import app
        from agent_memory.session import SessionContext

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.retrieve_session_context") as mock_retrieve,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            capture_time = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
            mock_context = SessionContext(
                captured_at=capture_time,
                active_work_areas=["src/module.py"],
            )
            mock_retrieve.return_value = mock_context

            result = runner.invoke(app, ["session-recover", "--work-area", "module"])

            assert result.exit_code == 0
            assert "2026-01-15" in result.output

    @pytest.mark.requirement("FR-016")
    def test_session_recover_with_all_context_fields(self) -> None:
        """Test session-recover displays all context fields together."""
        from agent_memory.cli import app
        from agent_memory.session import DecisionRecord, SessionContext

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.retrieve_session_context") as mock_retrieve,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_context = SessionContext(
                active_work_areas=["src/api.py", "tests/test_api.py"],
                related_closed_tasks=["FLO-100", "FLO-101"],
                recent_decisions=[
                    DecisionRecord(decision="Use REST", rationale="Simpler to implement"),
                ],
                conversation_summary="Built API endpoints",
            )
            mock_retrieve.return_value = mock_context

            result = runner.invoke(app, ["session-recover", "--work-area", "api"])

            assert result.exit_code == 0
            # All sections should appear
            assert "src/api.py" in result.output
            assert "FLO-100" in result.output
            assert "Use REST" in result.output
            assert "Built API endpoints" in result.output

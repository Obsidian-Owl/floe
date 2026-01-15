"""Unit tests for CLI session-save command.

Tests for the session-save command functionality:
- Argument parsing (--issues, --decisions)
- Session context capture
- Session context save via client
- Error handling

Implementation: T048 (FLO-633)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

runner = CliRunner()


class TestSessionSaveCommand:
    """Tests for session-save CLI command."""

    @pytest.mark.requirement("FR-016")
    def test_session_save_captures_issues(self) -> None:
        """Test that session-save captures issue IDs from --issues."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.save_session_context") as mock_save,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_save.return_value = None

            result = runner.invoke(
                app, ["session-save", "--issues", "FLO-123,FLO-456"]
            )

            assert result.exit_code == 0
            mock_save.assert_called_once()
            call_args = mock_save.call_args
            context = call_args[0][1]  # Second positional arg is context
            assert "FLO-123" in context.related_closed_tasks
            assert "FLO-456" in context.related_closed_tasks

    @pytest.mark.requirement("FR-016")
    def test_session_save_captures_decisions(self) -> None:
        """Test that session-save captures decisions from --decisions."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.save_session_context") as mock_save,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_save.return_value = None

            result = runner.invoke(
                app,
                ["session-save", "--decisions", "Use Pydantic v2,Add caching"],
            )

            assert result.exit_code == 0
            mock_save.assert_called_once()
            call_args = mock_save.call_args
            context = call_args[0][1]
            decision_texts = [d.decision for d in context.recent_decisions]
            assert "Use Pydantic v2" in decision_texts
            assert "Add caching" in decision_texts

    @pytest.mark.requirement("FR-016")
    def test_session_save_captures_work_areas(self) -> None:
        """Test that session-save captures work areas from --work-areas."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.save_session_context") as mock_save,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_save.return_value = None

            result = runner.invoke(
                app,
                ["session-save", "--work-areas", "src/module.py,tests/test_module.py"],
            )

            assert result.exit_code == 0
            mock_save.assert_called_once()
            call_args = mock_save.call_args
            context = call_args[0][1]
            assert "src/module.py" in context.active_work_areas
            assert "tests/test_module.py" in context.active_work_areas

    @pytest.mark.requirement("FR-016")
    def test_session_save_captures_summary(self) -> None:
        """Test that session-save captures summary from --summary."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.save_session_context") as mock_save,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_save.return_value = None

            result = runner.invoke(
                app,
                ["session-save", "--summary", "Implemented session management"],
            )

            assert result.exit_code == 0
            mock_save.assert_called_once()
            call_args = mock_save.call_args
            context = call_args[0][1]
            assert context.conversation_summary == "Implemented session management"

    @pytest.mark.requirement("FR-016")
    def test_session_save_with_all_options(self) -> None:
        """Test session-save with all options combined."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.save_session_context") as mock_save,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_save.return_value = None

            result = runner.invoke(
                app,
                [
                    "session-save",
                    "--issues", "FLO-123",
                    "--decisions", "Use REST API",
                    "--work-areas", "src/api.py",
                    "--summary", "Added API endpoints",
                ],
            )

            assert result.exit_code == 0
            mock_save.assert_called_once()
            call_args = mock_save.call_args
            context = call_args[0][1]
            assert "FLO-123" in context.related_closed_tasks
            assert len(context.recent_decisions) == 1
            assert context.recent_decisions[0].decision == "Use REST API"
            assert "src/api.py" in context.active_work_areas
            assert context.conversation_summary == "Added API endpoints"

    @pytest.mark.requirement("FR-016")
    def test_session_save_shows_success_message(self) -> None:
        """Test that session-save displays success confirmation."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.save_session_context") as mock_save,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_save.return_value = None

            result = runner.invoke(
                app, ["session-save", "--issues", "FLO-123"]
            )

            assert result.exit_code == 0
            assert "Session context saved" in result.output

    @pytest.mark.requirement("FR-016")
    def test_session_save_shows_session_id(self) -> None:
        """Test that session-save displays the session ID."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.save_session_context") as mock_save,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_save.return_value = None

            result = runner.invoke(
                app, ["session-save", "--issues", "FLO-123"]
            )

            assert result.exit_code == 0
            # Session ID should appear in output (UUID format)
            assert "Session ID:" in result.output

    @pytest.mark.requirement("FR-016")
    def test_session_save_empty_context_works(self) -> None:
        """Test session-save works with no arguments (empty context)."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.save_session_context") as mock_save,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_save.return_value = None

            result = runner.invoke(app, ["session-save"])

            assert result.exit_code == 0
            mock_save.assert_called_once()
            call_args = mock_save.call_args
            context = call_args[0][1]
            assert context.related_closed_tasks == []
            assert context.recent_decisions == []

    @pytest.mark.requirement("FR-016")
    def test_session_save_fails_without_config(self) -> None:
        """Test that session-save fails if config cannot be loaded."""
        from agent_memory.cli import app

        with patch("agent_memory.cli._load_config") as mock_config:
            mock_config.return_value = None

            result = runner.invoke(app, ["session-save"])

            assert result.exit_code == 1

    @pytest.mark.requirement("FR-016")
    def test_session_save_handles_client_error(self) -> None:
        """Test that session-save handles client errors gracefully."""
        from agent_memory.cli import app
        from agent_memory.cognee_client import CogneeClientError

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.save_session_context") as mock_save,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_save.side_effect = CogneeClientError("API error")

            result = runner.invoke(app, ["session-save", "--issues", "FLO-123"])

            assert result.exit_code == 1
            assert "API error" in result.output

    @pytest.mark.requirement("FR-016")
    def test_session_save_uses_custom_dataset(self) -> None:
        """Test that session-save can use custom dataset name."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.save_session_context") as mock_save,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_save.return_value = None

            result = runner.invoke(
                app,
                ["session-save", "--issues", "FLO-123", "--dataset", "my_sessions"],
            )

            assert result.exit_code == 0
            mock_save.assert_called_once()
            call_kwargs = mock_save.call_args.kwargs
            assert call_kwargs["dataset"] == "my_sessions"

    @pytest.mark.requirement("FR-016")
    def test_session_save_displays_timestamp(self) -> None:
        """Test that session-save displays the capture timestamp."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.session.save_session_context") as mock_save,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_save.return_value = None

            result = runner.invoke(app, ["session-save"])

            assert result.exit_code == 0
            assert "Captured at:" in result.output

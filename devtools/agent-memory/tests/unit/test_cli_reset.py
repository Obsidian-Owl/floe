"""Unit tests for CLI reset command.

Tests for the reset command functionality:
- Safety check (requires --confirm flag)
- Prune system call
- Local state file deletion
- Error handling

Implementation: T044 (FLO-629)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

runner = CliRunner()


class TestResetCommand:
    """Tests for reset CLI command."""

    @pytest.mark.requirement("FR-022")
    def test_reset_requires_confirm_flag(self, tmp_path: Path) -> None:
        """Test reset command requires --confirm flag for safety."""
        from agent_memory.cli import app

        # Create minimal config
        cognee_dir = tmp_path / ".cognee"
        cognee_dir.mkdir()

        with patch("agent_memory.cli._load_config") as mock_config:
            mock_config.return_value = MagicMock()

            result = runner.invoke(app, ["reset"])

            assert result.exit_code == 1
            assert "requires --confirm flag" in result.output

    @pytest.mark.requirement("FR-022")
    def test_reset_shows_warning_without_confirm(self, tmp_path: Path) -> None:
        """Test reset shows warning about what will be deleted."""
        from agent_memory.cli import app

        with patch("agent_memory.cli._load_config") as mock_config:
            mock_config.return_value = MagicMock()

            result = runner.invoke(app, ["reset"])

            assert result.exit_code == 1
            assert "Knowledge graph data" in result.output
            assert "Vector embeddings" in result.output
            assert "Metadata and cache" in result.output
            assert "agent-memory reset --confirm" in result.output

    @pytest.mark.requirement("FR-022")
    def test_reset_with_confirm_calls_prune_system(self, tmp_path: Path) -> None:
        """Test reset with --confirm calls prune_system."""
        from agent_memory.cli import app

        # Setup .cognee directory with state files
        cognee_dir = tmp_path / ".cognee"
        cognee_dir.mkdir()
        (cognee_dir / "state.json").write_text('{"test": "data"}')
        (cognee_dir / "checksums.json").write_text('{"file.py": "hash123"}')

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.cli.Path") as mock_path_class,
        ):
            mock_config.return_value = MagicMock()

            # Setup mock client
            mock_client = MagicMock()
            mock_client.prune_system = AsyncMock()
            mock_client_class.return_value = mock_client

            # Setup mock path to use tmp_path
            def mock_path(path_str: str) -> Path:
                if ".cognee" in path_str:
                    return cognee_dir / path_str.split("/")[-1]
                return Path(path_str)

            mock_path_class.side_effect = mock_path

            result = runner.invoke(app, ["reset", "--confirm"])

            # Should call prune_system
            mock_client.prune_system.assert_called_once_with(
                graph=True,
                vector=True,
                metadata=True,
            )

    @pytest.mark.requirement("FR-022")
    def test_reset_deletes_state_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test reset deletes local state files."""
        from agent_memory.cli import app

        # Change to tmp_path
        monkeypatch.chdir(tmp_path)

        # Setup .cognee directory with state files
        cognee_dir = tmp_path / ".cognee"
        cognee_dir.mkdir()
        state_file = cognee_dir / "state.json"
        checksums_file = cognee_dir / "checksums.json"
        checkpoint_file = cognee_dir / "checkpoint.json"

        state_file.write_text('{"test": "data"}')
        checksums_file.write_text('{"file.py": "hash123"}')
        checkpoint_file.write_text('{"completed": []}')

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client.prune_system = AsyncMock()
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["reset", "--confirm"])

            assert result.exit_code == 0
            assert not state_file.exists()
            assert not checksums_file.exists()
            assert not checkpoint_file.exists()

    @pytest.mark.requirement("FR-022")
    def test_reset_handles_missing_state_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test reset handles case where state files don't exist."""
        from agent_memory.cli import app

        monkeypatch.chdir(tmp_path)

        # Create .cognee directory but no state files
        cognee_dir = tmp_path / ".cognee"
        cognee_dir.mkdir()

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client.prune_system = AsyncMock()
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["reset", "--confirm"])

            # Should succeed even without state files
            assert result.exit_code == 0
            assert "Reset completed successfully" in result.output

    @pytest.mark.requirement("FR-022")
    def test_reset_shows_success_message(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test reset shows success message on completion."""
        from agent_memory.cli import app

        monkeypatch.chdir(tmp_path)

        cognee_dir = tmp_path / ".cognee"
        cognee_dir.mkdir()

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client.prune_system = AsyncMock()
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["reset", "--confirm"])

            assert result.exit_code == 0
            assert "Pruning Cognee Cloud system" in result.output
            assert "Cognee Cloud pruned" in result.output
            assert "Reset completed successfully" in result.output

    @pytest.mark.requirement("FR-022")
    def test_reset_handles_prune_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test reset handles prune system errors gracefully."""
        from agent_memory.cli import app
        from agent_memory.cognee_client import CogneeClientError

        monkeypatch.chdir(tmp_path)

        cognee_dir = tmp_path / ".cognee"
        cognee_dir.mkdir()

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
        ):
            mock_config.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client.prune_system = AsyncMock(
                side_effect=CogneeClientError("Connection failed")
            )
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["reset", "--confirm"])

            assert result.exit_code == 1
            assert "Connection failed" in result.output

    @pytest.mark.requirement("FR-022")
    def test_reset_fails_without_config(self) -> None:
        """Test reset fails if config cannot be loaded."""
        from agent_memory.cli import app

        with patch("agent_memory.cli._load_config") as mock_config:
            mock_config.return_value = None

            result = runner.invoke(app, ["reset", "--confirm"])

            assert result.exit_code == 1


class TestPruneSystemClient:
    """Tests for CogneeClient.prune_system method."""

    @pytest.mark.requirement("FR-022")
    @pytest.mark.asyncio
    async def test_prune_system_calls_api(self) -> None:
        """Test prune_system calls the prune API endpoint."""
        from agent_memory.cognee_client import CogneeClient

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.cloud"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-key"

        client = CogneeClient(mock_config)

        with patch.object(client, "_make_request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            await client.prune_system(graph=True, vector=True, metadata=True)

            mock_request.assert_called_once_with(
                "DELETE",
                "/api/prune",
                json_data={
                    "graph": True,
                    "vector": True,
                    "metadata": True,
                },
            )

    @pytest.mark.requirement("FR-022")
    @pytest.mark.asyncio
    async def test_prune_system_fallback_on_404(self) -> None:
        """Test prune_system falls back to dataset deletion on 404."""
        from agent_memory.cognee_client import CogneeClient

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.cloud"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-key"

        client = CogneeClient(mock_config)

        with (
            patch.object(client, "_make_request") as mock_request,
            patch.object(client, "list_datasets") as mock_list,
            patch.object(client, "delete_dataset") as mock_delete,
        ):
            # First call returns 404, triggering fallback
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_request.return_value = mock_response

            mock_list.return_value = ["dataset1", "dataset2"]
            mock_delete.return_value = None

            await client.prune_system()

            # Should list and delete all datasets
            mock_list.assert_called_once()
            assert mock_delete.call_count == 2
            mock_delete.assert_any_call("dataset1")
            mock_delete.assert_any_call("dataset2")

    @pytest.mark.requirement("FR-022")
    @pytest.mark.asyncio
    async def test_prune_system_raises_on_error(self) -> None:
        """Test prune_system raises on non-404 errors."""
        from agent_memory.cognee_client import CogneeClient, CogneeClientError

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.cloud"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-key"

        client = CogneeClient(mock_config)

        with patch.object(client, "_make_request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_request.return_value = mock_response

            with pytest.raises(CogneeClientError, match="Prune system failed"):
                await client.prune_system()

    @pytest.mark.requirement("FR-022")
    @pytest.mark.asyncio
    async def test_prune_system_selective_options(self) -> None:
        """Test prune_system passes selective options to API."""
        from agent_memory.cognee_client import CogneeClient

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.cloud"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-key"

        client = CogneeClient(mock_config)

        with patch.object(client, "_make_request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            # Only prune graph, not vector or metadata
            await client.prune_system(graph=True, vector=False, metadata=False)

            mock_request.assert_called_once_with(
                "DELETE",
                "/api/prune",
                json_data={
                    "graph": True,
                    "vector": False,
                    "metadata": False,
                },
            )

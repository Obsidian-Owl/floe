"""Unit tests for CLI memify command.

Tests for the memify command functionality:
- Default dataset handling
- Custom dataset option
- Error handling

Implementation: Cognee SDK integration
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

runner = CliRunner()


class TestMemifyCommand:
    """Tests for memify CLI command."""

    @pytest.mark.requirement("FR-023")
    def test_memify_uses_default_dataset(self) -> None:
        """Test memify uses default dataset when not specified."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
        ):
            config = MagicMock()
            config.default_dataset = "floe"
            mock_config.return_value = config

            mock_client = MagicMock()
            mock_client.memify = AsyncMock()
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["memify"])

            assert result.exit_code == 0
            mock_client.memify.assert_called_once_with(dataset_name="floe")
            assert "Running memify on dataset: floe" in result.output
            assert "Memify completed successfully" in result.output

    @pytest.mark.requirement("FR-023")
    def test_memify_with_custom_dataset(self) -> None:
        """Test memify with custom dataset specified."""
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
        ):
            config = MagicMock()
            config.default_dataset = "floe"
            mock_config.return_value = config

            mock_client = MagicMock()
            mock_client.memify = AsyncMock()
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["memify", "--dataset", "custom"])

            assert result.exit_code == 0
            mock_client.memify.assert_called_once_with(dataset_name="custom")
            assert "Running memify on dataset: custom" in result.output

    @pytest.mark.requirement("FR-023")
    def test_memify_handles_error(self) -> None:
        """Test memify handles errors gracefully."""
        from agent_memory.cli import app
        from agent_memory.cognee_client import CogneeClientError

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
        ):
            config = MagicMock()
            config.default_dataset = "floe"
            mock_config.return_value = config

            mock_client = MagicMock()
            mock_client.memify = AsyncMock(
                side_effect=CogneeClientError("Memify failed: Connection timeout")
            )
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["memify"])

            assert result.exit_code == 1
            assert "Memify failed" in result.output

    @pytest.mark.requirement("FR-023")
    def test_memify_fails_without_config(self) -> None:
        """Test memify fails if config cannot be loaded."""
        from agent_memory.cli import app

        with patch("agent_memory.cli._load_config") as mock_config:
            mock_config.return_value = None

            result = runner.invoke(app, ["memify"])

            assert result.exit_code == 1


class TestMemifyClient:
    """Tests for CogneeClient.memify method."""

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_memify_calls_sdk(self) -> None:
        """Test memify calls the Cognee SDK."""
        from agent_memory.cognee_client import CogneeClient

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.cloud"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-key"
        mock_config.default_dataset = "floe"

        client = CogneeClient(mock_config)

        # Patch at the cogwit_sdk module level since it's imported inside the function
        with patch("cogwit_sdk.cogwit") as mock_cogwit_func:
            mock_sdk = MagicMock()
            mock_sdk.memify = AsyncMock(return_value=MagicMock(error=None))
            mock_cogwit_func.return_value = mock_sdk

            await client.memify(dataset_name="test_dataset")

            mock_sdk.memify.assert_called_once_with(dataset_name="test_dataset")

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_memify_uses_default_dataset(self) -> None:
        """Test memify uses default dataset when none specified."""
        from agent_memory.cognee_client import CogneeClient

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.cloud"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-key"
        mock_config.default_dataset = "default_ds"

        client = CogneeClient(mock_config)

        with patch("cogwit_sdk.cogwit") as mock_cogwit_func:
            mock_sdk = MagicMock()
            mock_sdk.memify = AsyncMock(return_value=MagicMock(error=None))
            mock_cogwit_func.return_value = mock_sdk

            await client.memify()  # No dataset specified

            mock_sdk.memify.assert_called_once_with(dataset_name="default_ds")

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_memify_raises_on_sdk_error(self) -> None:
        """Test memify raises CogneeClientError on SDK error."""
        from agent_memory.cognee_client import CogneeClient, CogneeClientError

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.cloud"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-key"
        mock_config.default_dataset = "floe"

        client = CogneeClient(mock_config)

        with patch("cogwit_sdk.cogwit") as mock_cogwit_func:
            mock_sdk = MagicMock()
            mock_sdk.memify = AsyncMock(return_value=MagicMock(error="Graph not found"))
            mock_cogwit_func.return_value = mock_sdk

            with pytest.raises(CogneeClientError, match="Memify failed"):
                await client.memify(dataset_name="test_dataset")

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_memify_raises_on_exception(self) -> None:
        """Test memify wraps exceptions in CogneeClientError."""
        from agent_memory.cognee_client import CogneeClient, CogneeClientError

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.cloud"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-key"
        mock_config.default_dataset = "floe"

        client = CogneeClient(mock_config)

        with patch("cogwit_sdk.cogwit") as mock_cogwit_func:
            mock_cogwit_func.side_effect = Exception("Network error")

            with pytest.raises(CogneeClientError, match="Memify failed"):
                await client.memify(dataset_name="test_dataset")

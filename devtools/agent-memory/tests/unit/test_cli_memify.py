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
            mock_client.memify = AsyncMock(return_value=True)
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
            mock_client.memify = AsyncMock(return_value=True)
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["memify", "--dataset", "custom"])

            assert result.exit_code == 0
            mock_client.memify.assert_called_once_with(dataset_name="custom")
            assert "Running memify on dataset: custom" in result.output

    @pytest.mark.requirement("FR-023")
    def test_memify_shows_warning_when_not_available(self) -> None:
        """Test memify shows helpful warning when endpoint not available.

        Cognee Cloud does not expose the memify endpoint. When this happens,
        the CLI should show a helpful message explaining the limitation
        instead of failing with an error.
        """
        from agent_memory.cli import app

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
        ):
            config = MagicMock()
            config.default_dataset = "floe"
            mock_config.return_value = config

            mock_client = MagicMock()
            mock_client.memify = AsyncMock(return_value=False)  # Not available
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["memify"])

            assert result.exit_code == 0  # Should not fail
            assert "Memify not available" in result.output
            assert "Cognee Cloud" in result.output
            assert "knowledge graph is still functional" in result.output

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
    """Tests for CogneeClient.memify method.

    These tests mock the cogwit_sdk module to test memify functionality
    without requiring the SDK to be installed.

    Uses patch.dict(sys.modules) for clean, isolated mocking of the optional SDK.
    """

    @pytest.fixture
    def mock_sdk_module(self) -> MagicMock:
        """Create a fresh mock cogwit_sdk module for each test.

        Returns:
            MagicMock configured to behave like cogwit_sdk module.
        """
        mock_module = MagicMock()
        mock_module.CogwitConfig = MagicMock()
        mock_module.cogwit = MagicMock()
        return mock_module

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock config for tests.

        Returns:
            MagicMock configured to behave like AgentMemoryConfig.
        """
        config = MagicMock()
        config.cognee_api_url = "https://api.cognee.cloud"
        config.cognee_api_key.get_secret_value.return_value = "test-key"
        config.default_dataset = "floe"
        return config

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_memify_calls_sdk(
        self, mock_sdk_module: MagicMock, mock_config: MagicMock
    ) -> None:
        """Test memify calls the Cognee SDK and returns True on success."""
        import sys

        # Setup the mock SDK behavior
        mock_sdk = MagicMock()
        mock_sdk.memify = AsyncMock(return_value=MagicMock(error=None, detail=None))
        mock_sdk_module.cogwit.return_value = mock_sdk

        with patch.dict(sys.modules, {"cogwit_sdk": mock_sdk_module}):
            from agent_memory.cognee_client import CogneeClient

            client = CogneeClient(mock_config)
            result = await client.memify(dataset_name="test_dataset")

        assert result is True
        mock_sdk.memify.assert_called_once_with(dataset_name="test_dataset")

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_memify_uses_default_dataset(
        self, mock_sdk_module: MagicMock, mock_config: MagicMock
    ) -> None:
        """Test memify uses default dataset when none specified."""
        import sys

        mock_config.default_dataset = "default_ds"

        # Setup the mock SDK behavior
        mock_sdk = MagicMock()
        mock_sdk.memify = AsyncMock(return_value=MagicMock(error=None, detail=None))
        mock_sdk_module.cogwit.return_value = mock_sdk

        with patch.dict(sys.modules, {"cogwit_sdk": mock_sdk_module}):
            from agent_memory.cognee_client import CogneeClient

            client = CogneeClient(mock_config)
            result = await client.memify()  # No dataset specified

        assert result is True
        mock_sdk.memify.assert_called_once_with(dataset_name="default_ds")

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_memify_returns_false_when_not_found(
        self, mock_sdk_module: MagicMock, mock_config: MagicMock
    ) -> None:
        """Test memify returns False when endpoint not available.

        Cognee Cloud (api.cognee.ai) does not expose the memify endpoint.
        The SDK returns MemifyError(status=404, error={'detail': 'Not Found'}).
        """
        import sys

        # Create a mock MemifyError class to mimic the real SDK response
        # The class name MUST be "MemifyError" for the type check to work
        class MemifyError:  # noqa: N801  # Class name matches SDK
            def __init__(self) -> None:
                self.status = 404
                self.error = {"detail": "Not Found"}

        # Setup the mock SDK to return a MemifyError with status 404
        mock_sdk = MagicMock()
        mock_sdk.memify = AsyncMock(return_value=MemifyError())
        mock_sdk_module.cogwit.return_value = mock_sdk

        with patch.dict(sys.modules, {"cogwit_sdk": mock_sdk_module}):
            from agent_memory.cognee_client import CogneeClient

            client = CogneeClient(mock_config)
            result = await client.memify(dataset_name="test_dataset")

        assert result is False

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_memify_returns_false_on_not_found_exception(
        self, mock_sdk_module: MagicMock, mock_config: MagicMock
    ) -> None:
        """Test memify returns False when SDK raises Not Found exception."""
        import sys

        # Setup the mock SDK to raise an exception containing "Not Found"
        mock_sdk = MagicMock()
        mock_sdk.memify = AsyncMock(
            side_effect=Exception("{'detail': 'Not Found'}")
        )
        mock_sdk_module.cogwit.return_value = mock_sdk

        with patch.dict(sys.modules, {"cogwit_sdk": mock_sdk_module}):
            from agent_memory.cognee_client import CogneeClient

            client = CogneeClient(mock_config)
            result = await client.memify(dataset_name="test_dataset")

        assert result is False

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_memify_raises_on_sdk_error(
        self, mock_sdk_module: MagicMock, mock_config: MagicMock
    ) -> None:
        """Test memify raises CogneeClientError on SDK error."""
        import sys

        # Setup the mock SDK to return an error
        mock_sdk = MagicMock()
        mock_sdk.memify = AsyncMock(return_value=MagicMock(error="Graph not found"))
        mock_sdk_module.cogwit.return_value = mock_sdk

        with patch.dict(sys.modules, {"cogwit_sdk": mock_sdk_module}):
            from agent_memory.cognee_client import CogneeClient, CogneeClientError

            client = CogneeClient(mock_config)

            with pytest.raises(CogneeClientError, match="Memify failed"):
                await client.memify(dataset_name="test_dataset")

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_memify_raises_on_exception(
        self, mock_sdk_module: MagicMock, mock_config: MagicMock
    ) -> None:
        """Test memify wraps exceptions in CogneeClientError."""
        import sys

        # Setup the mock SDK to raise an exception
        mock_sdk_module.cogwit.side_effect = Exception("Network error")

        with patch.dict(sys.modules, {"cogwit_sdk": mock_sdk_module}):
            from agent_memory.cognee_client import CogneeClient, CogneeClientError

            client = CogneeClient(mock_config)

            with pytest.raises(CogneeClientError, match="Memify failed"):
                await client.memify(dataset_name="test_dataset")

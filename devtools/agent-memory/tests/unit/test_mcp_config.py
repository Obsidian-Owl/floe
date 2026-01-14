"""Unit tests for MCP configuration module.

Tests for MCP server configuration generation functions.
"""

from __future__ import annotations

import pytest

from agent_memory.mcp_config import (
    DEFAULT_MCP_HOST,
    DEFAULT_MCP_PATH,
    DEFAULT_MCP_PORT,
    DEFAULT_SERVER_NAME,
    generate_mcp_config,
    get_docker_run_command,
    get_mcp_server_url,
)


class TestGenerateMcpConfig:
    """Tests for generate_mcp_config function."""

    @pytest.mark.requirement("FR-013")
    def test_default_config(self) -> None:
        """Test default MCP configuration generation."""
        config = generate_mcp_config()

        assert "mcpServers" in config
        assert "cognee" in config["mcpServers"]
        assert config["mcpServers"]["cognee"]["transport"] == "http"
        assert config["mcpServers"]["cognee"]["url"] == "http://localhost:8000/mcp"

    @pytest.mark.requirement("FR-013")
    def test_custom_port(self) -> None:
        """Test MCP configuration with custom port."""
        config = generate_mcp_config(port=9000)

        assert config["mcpServers"]["cognee"]["url"] == "http://localhost:9000/mcp"

    @pytest.mark.requirement("FR-013")
    def test_custom_host(self) -> None:
        """Test MCP configuration with custom host."""
        config = generate_mcp_config(host="cognee.local")

        assert config["mcpServers"]["cognee"]["url"] == "http://cognee.local:8000/mcp"

    @pytest.mark.requirement("FR-013")
    def test_custom_path(self) -> None:
        """Test MCP configuration with custom path."""
        config = generate_mcp_config(path="/api/mcp")

        assert config["mcpServers"]["cognee"]["url"] == "http://localhost:8000/api/mcp"

    @pytest.mark.requirement("FR-013")
    def test_custom_server_name(self) -> None:
        """Test MCP configuration with custom server name."""
        config = generate_mcp_config(server_name="memory")

        assert "memory" in config["mcpServers"]
        assert "cognee" not in config["mcpServers"]

    @pytest.mark.requirement("FR-013")
    def test_all_custom_values(self) -> None:
        """Test MCP configuration with all custom values."""
        config = generate_mcp_config(
            host="memory.example.com",
            port=8080,
            path="/v1/mcp",
            server_name="project-memory",
        )

        assert "project-memory" in config["mcpServers"]
        assert config["mcpServers"]["project-memory"]["transport"] == "http"
        assert (
            config["mcpServers"]["project-memory"]["url"]
            == "http://memory.example.com:8080/v1/mcp"
        )

    @pytest.mark.requirement("FR-013")
    def test_config_structure(self) -> None:
        """Test that config structure matches Claude Code expectations."""
        config = generate_mcp_config()

        # Top-level key must be mcpServers
        assert list(config.keys()) == ["mcpServers"]

        # Server entry must have transport and url
        server_config = config["mcpServers"]["cognee"]
        assert set(server_config.keys()) == {"transport", "url"}


class TestGetMcpServerUrl:
    """Tests for get_mcp_server_url function."""

    @pytest.mark.requirement("FR-013")
    def test_default_url(self) -> None:
        """Test default MCP server URL."""
        url = get_mcp_server_url()

        assert url == "http://localhost:8000/mcp"

    @pytest.mark.requirement("FR-013")
    def test_custom_url(self) -> None:
        """Test MCP server URL with custom values."""
        url = get_mcp_server_url(host="cognee.local", port=9000, path="/api/v1/mcp")

        assert url == "http://cognee.local:9000/api/v1/mcp"


class TestGetDockerRunCommand:
    """Tests for get_docker_run_command function."""

    @pytest.mark.requirement("FR-013")
    def test_default_command(self) -> None:
        """Test default Docker run command."""
        cmd = get_docker_run_command()

        assert "docker run" in cmd
        assert "--rm -it" in cmd
        assert "TRANSPORT_MODE=http" in cmd
        assert "$OPENAI_API_KEY" in cmd
        assert "$COGNEE_API_KEY" in cmd
        assert "-p 8000:8000" in cmd
        assert "cognee/cognee-mcp:main" in cmd

    @pytest.mark.requirement("FR-013")
    def test_detached_mode(self) -> None:
        """Test Docker run command in detached mode."""
        cmd = get_docker_run_command(detach=True)

        assert "-d --rm" in cmd
        assert "-it" not in cmd

    @pytest.mark.requirement("FR-013")
    def test_custom_port(self) -> None:
        """Test Docker run command with custom port."""
        cmd = get_docker_run_command(port=9000)

        assert "-p 9000:8000" in cmd

    @pytest.mark.requirement("FR-013")
    def test_explicit_api_keys(self) -> None:
        """Test Docker run command with explicit API keys."""
        cmd = get_docker_run_command(
            openai_api_key="sk-test-openai",
            cognee_api_key="cog-test-key",
        )

        assert "LLM_API_KEY=sk-test-openai" in cmd
        assert "API_TOKEN=cog-test-key" in cmd
        assert "$OPENAI_API_KEY" not in cmd
        assert "$COGNEE_API_KEY" not in cmd

    @pytest.mark.requirement("FR-013")
    def test_api_url(self) -> None:
        """Test Docker run command includes API URL."""
        cmd = get_docker_run_command()

        assert "API_URL=https://api.cognee.ai" in cmd


class TestModuleConstants:
    """Tests for module constants."""

    @pytest.mark.requirement("FR-013")
    def test_default_constants(self) -> None:
        """Test default constants have expected values."""
        assert DEFAULT_MCP_HOST == "localhost"
        assert DEFAULT_MCP_PORT == 8000
        assert DEFAULT_MCP_PATH == "/mcp"
        assert DEFAULT_SERVER_NAME == "cognee"

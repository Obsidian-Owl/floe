"""MCP server configuration for Claude Code integration.

Generates MCP (Model Context Protocol) server configuration for connecting
Claude Code to the Cognee knowledge graph.

Example:
    >>> from agent_memory.mcp_config import generate_mcp_config
    >>> config = generate_mcp_config()
    >>> config["mcpServers"]["cognee"]["transport"]
    'http'
"""

from __future__ import annotations

from typing import Any

# Default MCP server configuration
DEFAULT_MCP_HOST = "localhost"
DEFAULT_MCP_PORT = 8000
DEFAULT_MCP_PATH = "/mcp"
DEFAULT_SERVER_NAME = "cognee"


def generate_mcp_config(
    host: str = DEFAULT_MCP_HOST,
    port: int = DEFAULT_MCP_PORT,
    path: str = DEFAULT_MCP_PATH,
    server_name: str = DEFAULT_SERVER_NAME,
) -> dict[str, Any]:
    """Generate MCP server configuration for Claude Code.

    Creates a configuration dictionary compatible with Claude Code's
    `.claude/mcp.json` format. The configuration uses HTTP transport
    to connect to a locally running Cognee MCP server.

    Args:
        host: MCP server hostname. Defaults to "localhost".
        port: MCP server port. Defaults to 8000.
        path: MCP endpoint path. Defaults to "/mcp".
        server_name: Name for the MCP server entry. Defaults to "cognee".

    Returns:
        Dictionary containing MCP configuration compatible with Claude Code.
        Format:
        {
            "mcpServers": {
                "<server_name>": {
                    "transport": "http",
                    "url": "http://<host>:<port><path>"
                }
            }
        }

    Examples:
        >>> config = generate_mcp_config()
        >>> config["mcpServers"]["cognee"]["url"]
        'http://localhost:8000/mcp'

        >>> config = generate_mcp_config(port=9000)
        >>> config["mcpServers"]["cognee"]["url"]
        'http://localhost:9000/mcp'

        >>> config = generate_mcp_config(host="cognee.local", server_name="memory")
        >>> "memory" in config["mcpServers"]
        True
    """
    url = f"http://{host}:{port}{path}"

    return {
        "mcpServers": {
            server_name: {
                "transport": "http",
                "url": url,
            }
        }
    }


def get_mcp_server_url(
    host: str = DEFAULT_MCP_HOST,
    port: int = DEFAULT_MCP_PORT,
    path: str = DEFAULT_MCP_PATH,
) -> str:
    """Get the MCP server URL.

    Convenience function to generate just the URL without the full config.

    Args:
        host: MCP server hostname. Defaults to "localhost".
        port: MCP server port. Defaults to 8000.
        path: MCP endpoint path. Defaults to "/mcp".

    Returns:
        MCP server URL string.

    Examples:
        >>> get_mcp_server_url()
        'http://localhost:8000/mcp'

        >>> get_mcp_server_url(port=9000)
        'http://localhost:9000/mcp'
    """
    return f"http://{host}:{port}{path}"


def get_docker_run_command(
    openai_api_key: str | None = None,
    cognee_api_key: str | None = None,
    port: int = DEFAULT_MCP_PORT,
    detach: bool = False,
) -> str:
    """Generate Docker run command for Cognee MCP server.

    Creates a docker run command to start the Cognee MCP server container
    with the appropriate environment variables.

    Args:
        openai_api_key: OpenAI API key. If None, uses $OPENAI_API_KEY.
        cognee_api_key: Cognee API key. If None, uses $COGNEE_API_KEY.
        port: Port to expose. Defaults to 8000.
        detach: Run in detached mode. Defaults to False.

    Returns:
        Docker run command string.

    Examples:
        >>> cmd = get_docker_run_command()
        >>> "cognee/cognee-mcp:main" in cmd
        True

        >>> cmd = get_docker_run_command(detach=True)
        >>> "-d" in cmd
        True
    """
    llm_key = openai_api_key or "$OPENAI_API_KEY"
    api_key = cognee_api_key or "$COGNEE_API_KEY"

    run_flags = "-d --rm" if detach else "--rm -it"

    return (
        f"docker run {run_flags} "
        f"-e TRANSPORT_MODE=http "
        f"-e LLM_API_KEY={llm_key} "
        f"-e API_URL=https://api.cognee.ai "
        f"-e API_TOKEN={api_key} "
        f"-p {port}:8000 "
        f"cognee/cognee-mcp:main"
    )

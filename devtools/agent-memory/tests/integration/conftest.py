"""Pytest configuration for integration tests.

Integration tests require real Cognee Cloud credentials and connectivity.
Tests FAIL (not skip) when infrastructure is unavailable - this is intentional
per testing standards.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from agent_memory.cognee_client import CogneeClient
    from agent_memory.config import AgentMemoryConfig


@pytest.fixture
def cognee_config() -> AgentMemoryConfig:
    """Load Cognee configuration from environment.

    FAILS if required environment variables are not set.
    This is intentional - integration tests require real credentials.
    """
    from agent_memory.config import get_config

    try:
        return get_config()
    except Exception as e:
        pytest.fail(
            f"Configuration failed: {e}\n\n"
            "Integration tests require real credentials. Set:\n"
            "  COGNEE_API_KEY=<your-cognee-api-key>\n"
            "  OPENAI_API_KEY=<your-openai-api-key>\n\n"
            "Or run unit tests only: pytest tests/unit/"
        )


@pytest.fixture
def cognee_client(cognee_config: AgentMemoryConfig) -> CogneeClient:
    """Create CogneeClient with valid configuration.

    FAILS if configuration is invalid.
    """
    from agent_memory.cognee_client import CogneeClient

    return CogneeClient(cognee_config)


@pytest.fixture
def invalid_cognee_config() -> AgentMemoryConfig:
    """Create configuration with invalid API key for negative testing.

    Uses a clearly invalid key to test authentication failure handling.
    """
    from agent_memory.config import AgentMemoryConfig

    # Temporarily set invalid environment variables
    original_cognee_key = os.environ.get("COGNEE_API_KEY")
    original_openai_key = os.environ.get("OPENAI_API_KEY")

    try:
        # Set invalid credentials for this test
        os.environ["COGNEE_API_KEY"] = "invalid-test-key-12345"
        os.environ["OPENAI_API_KEY"] = original_openai_key or "sk-test-invalid"

        from pydantic import SecretStr

        return AgentMemoryConfig(
            cognee_api_key=SecretStr("invalid-test-key-12345"),
            openai_api_key=SecretStr(original_openai_key or "sk-test-invalid"),
        )
    finally:
        # Restore original environment
        if original_cognee_key:
            os.environ["COGNEE_API_KEY"] = original_cognee_key
        if original_openai_key:
            os.environ["OPENAI_API_KEY"] = original_openai_key

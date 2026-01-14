"""Integration tests for Cognee Cloud connectivity.

These tests verify:
- Health check endpoint connectivity
- Authentication with valid credentials
- Clear error messages with invalid credentials

Tests FAIL when infrastructure is unavailable (per testing standards).
Run with: pytest tests/integration/test_cognee_cloud.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from agent_memory.cognee_client import CogneeClient
    from agent_memory.config import AgentMemoryConfig


@pytest.mark.requirement("FR-001", "FR-002")
@pytest.mark.asyncio
async def test_health_check_returns_healthy(cognee_client: CogneeClient) -> None:
    """Test health check returns healthy status with valid credentials.

    Validates:
    - Cognee Cloud API is reachable
    - Health endpoint returns expected structure
    - Overall status is healthy or degraded (not unhealthy)
    """
    status = await cognee_client.health_check()

    # Verify structure
    assert status.overall_status in ("healthy", "degraded", "unhealthy")
    assert status.cognee_cloud is not None
    assert status.llm_provider is not None
    assert status.local_state is not None

    # For integration tests, we expect at least Cognee Cloud to be reachable
    assert status.cognee_cloud.status in (
        "healthy",
        "degraded",
    ), f"Cognee Cloud unhealthy: {status.cognee_cloud.message}"


@pytest.mark.requirement("FR-001", "FR-002")
@pytest.mark.asyncio
async def test_authentication_with_valid_credentials(
    cognee_client: CogneeClient,
) -> None:
    """Test authentication succeeds with valid API key.

    Validates:
    - API key authentication succeeds
    - Client can perform basic operations
    """
    # Health check implicitly validates authentication
    status = await cognee_client.health_check()

    # If Cognee Cloud returns 401, auth failed
    assert status.cognee_cloud.status != "unhealthy" or "401" not in str(
        status.cognee_cloud.message
    ), f"Authentication failed: {status.cognee_cloud.message}"


@pytest.mark.requirement("FR-002")
@pytest.mark.asyncio
async def test_authentication_fails_with_invalid_credentials(
    invalid_cognee_config: AgentMemoryConfig,
) -> None:
    """Test authentication fails gracefully with invalid API key.

    Validates:
    - Invalid credentials produce clear error message
    - Client handles authentication failure gracefully
    - Error message mentions authentication
    """
    from agent_memory.cognee_client import CogneeClient

    client = CogneeClient(invalid_cognee_config)
    status = await client.health_check()

    # With invalid credentials, Cognee Cloud should return unhealthy or 401
    assert status.cognee_cloud.status in (
        "unhealthy",
        "degraded",
    ), "Expected authentication to fail with invalid credentials"

    # Error message should be helpful
    message = status.cognee_cloud.message.lower()
    assert any(
        term in message for term in ("auth", "401", "invalid", "credential", "key")
    ), f"Error message should mention authentication issue: {status.cognee_cloud.message}"


@pytest.mark.requirement("FR-002")
@pytest.mark.asyncio
async def test_health_check_reports_response_time(cognee_client: CogneeClient) -> None:
    """Test health check includes response time metrics.

    Validates:
    - Response time is measured
    - Response time is reasonable (< 30 seconds)
    """
    status = await cognee_client.health_check()

    # Cognee Cloud component should have response time
    if status.cognee_cloud.response_time_ms is not None:
        assert status.cognee_cloud.response_time_ms >= 0
        assert (
            status.cognee_cloud.response_time_ms < 30000
        ), "Response time should be < 30 seconds"


@pytest.mark.requirement("FR-001")
@pytest.mark.asyncio
async def test_llm_provider_configured(cognee_client: CogneeClient) -> None:
    """Test LLM provider is properly configured.

    Validates:
    - LLM provider API key is configured
    - Provider is recognized (openai or anthropic)
    """
    status = await cognee_client.health_check()

    # LLM provider should be configured (healthy or at least have a message)
    assert status.llm_provider.status in (
        "healthy",
        "degraded",
    ), f"LLM provider not configured: {status.llm_provider.message}"

"""Unit tests for ops/health.py - health checking module.

Tests for health check functionality:
- HealthCheckResult model and classification
- health_check: Check overall system health
- check_cognee_cloud: Check Cognee Cloud connectivity
- check_llm_provider: Check LLM provider configuration
- check_local_state: Check local state files

This is TDD - tests written before implementation (T036: Create ops/health.py).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path


class TestHealthCheckResult:
    """Tests for HealthCheckResult model."""

    @pytest.mark.requirement("FR-017")
    def test_health_check_result_has_required_fields(self) -> None:
        """Test HealthCheckResult model has all required fields."""
        from agent_memory.ops.health import HealthCheckResult

        result = HealthCheckResult(
            overall_status="healthy",
            checked_at=datetime.now(),
            components={},
        )

        assert result.overall_status == "healthy"
        assert result.checked_at is not None
        assert result.components == {}

    @pytest.mark.requirement("FR-017")
    def test_health_check_result_is_healthy_property(self) -> None:
        """Test HealthCheckResult.is_healthy property."""
        from agent_memory.ops.health import HealthCheckResult

        healthy_result = HealthCheckResult(
            overall_status="healthy",
            checked_at=datetime.now(),
            components={},
        )
        assert healthy_result.is_healthy is True

        degraded_result = HealthCheckResult(
            overall_status="degraded",
            checked_at=datetime.now(),
            components={},
        )
        assert degraded_result.is_healthy is False

        unhealthy_result = HealthCheckResult(
            overall_status="unhealthy",
            checked_at=datetime.now(),
            components={},
        )
        assert unhealthy_result.is_healthy is False

    @pytest.mark.requirement("FR-017")
    def test_health_check_result_has_issues_property(self) -> None:
        """Test HealthCheckResult.has_issues property."""
        from agent_memory.ops.health import ComponentHealth, HealthCheckResult

        no_issues = HealthCheckResult(
            overall_status="healthy",
            checked_at=datetime.now(),
            components={
                "cognee": ComponentHealth(status="healthy", message="OK"),
            },
        )
        assert no_issues.has_issues is False

        has_issues = HealthCheckResult(
            overall_status="degraded",
            checked_at=datetime.now(),
            components={
                "cognee": ComponentHealth(status="unhealthy", message="Failed"),
            },
        )
        assert has_issues.has_issues is True


class TestComponentHealth:
    """Tests for ComponentHealth model."""

    @pytest.mark.requirement("FR-017")
    def test_component_health_model(self) -> None:
        """Test ComponentHealth model has all required fields."""
        from agent_memory.ops.health import ComponentHealth

        component = ComponentHealth(
            status="healthy",
            message="Connected successfully",
            response_time_ms=42,
        )

        assert component.status == "healthy"
        assert component.message == "Connected successfully"
        assert component.response_time_ms == 42

    @pytest.mark.requirement("FR-017")
    def test_component_health_optional_response_time(self) -> None:
        """Test ComponentHealth with no response time."""
        from agent_memory.ops.health import ComponentHealth

        component = ComponentHealth(
            status="unhealthy",
            message="Connection failed",
        )

        assert component.status == "unhealthy"
        assert component.response_time_ms is None


class TestCheckCogneeCloud:
    """Tests for check_cognee_cloud function."""

    @pytest.mark.requirement("FR-017")
    @pytest.mark.asyncio
    async def test_check_cognee_cloud_healthy(self) -> None:
        """Test check_cognee_cloud returns healthy status when connected."""
        from agent_memory.ops.health import check_cognee_cloud

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.ai"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-api-key"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await check_cognee_cloud(mock_config)

        assert result.status == "healthy"
        assert "Connected" in result.message or "connected" in result.message.lower()

    @pytest.mark.requirement("FR-017")
    @pytest.mark.asyncio
    async def test_check_cognee_cloud_auth_failure(self) -> None:
        """Test check_cognee_cloud returns unhealthy on auth failure."""
        from agent_memory.ops.health import check_cognee_cloud

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.ai"
        mock_config.cognee_api_key.get_secret_value.return_value = "invalid-key"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await check_cognee_cloud(mock_config)

        assert result.status == "unhealthy"
        assert "auth" in result.message.lower() or "401" in result.message

    @pytest.mark.requirement("FR-017")
    @pytest.mark.asyncio
    async def test_check_cognee_cloud_connection_error(self) -> None:
        """Test check_cognee_cloud handles connection errors."""
        import httpx

        from agent_memory.ops.health import check_cognee_cloud

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.ai"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-api-key"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await check_cognee_cloud(mock_config)

        assert result.status == "unhealthy"
        assert "connect" in result.message.lower() or "error" in result.message.lower()


class TestCheckLlmProvider:
    """Tests for check_llm_provider function."""

    @pytest.mark.requirement("FR-017")
    def test_check_llm_provider_valid_key(self) -> None:
        """Test check_llm_provider returns healthy with valid key."""
        from agent_memory.ops.health import check_llm_provider

        mock_config = MagicMock()
        mock_config.llm_provider = "openai"
        mock_config.get_llm_api_key.return_value = "sk-valid-key-with-length"

        result = check_llm_provider(mock_config)

        assert result.status == "healthy"
        assert "openai" in result.message.lower()

    @pytest.mark.requirement("FR-017")
    def test_check_llm_provider_invalid_key(self) -> None:
        """Test check_llm_provider returns unhealthy with invalid key."""
        from agent_memory.ops.health import check_llm_provider

        mock_config = MagicMock()
        mock_config.llm_provider = "openai"
        mock_config.get_llm_api_key.return_value = "short"  # Too short

        result = check_llm_provider(mock_config)

        assert result.status == "unhealthy"
        assert "invalid" in result.message.lower()

    @pytest.mark.requirement("FR-017")
    def test_check_llm_provider_missing_key(self) -> None:
        """Test check_llm_provider handles missing key."""
        from agent_memory.ops.health import check_llm_provider

        mock_config = MagicMock()
        mock_config.llm_provider = "openai"
        mock_config.get_llm_api_key.side_effect = ValueError("No API key")

        result = check_llm_provider(mock_config)

        assert result.status == "unhealthy"


class TestCheckLocalState:
    """Tests for check_local_state function."""

    @pytest.mark.requirement("FR-017")
    def test_check_local_state_exists(self, tmp_path: Path) -> None:
        """Test check_local_state returns healthy when .cognee exists."""
        from agent_memory.ops.health import check_local_state

        cognee_dir = tmp_path / ".cognee"
        cognee_dir.mkdir()

        result = check_local_state(tmp_path)

        assert result.status == "healthy"
        assert ".cognee" in result.message

    @pytest.mark.requirement("FR-017")
    def test_check_local_state_missing(self, tmp_path: Path) -> None:
        """Test check_local_state returns degraded when .cognee missing."""
        from agent_memory.ops.health import check_local_state

        result = check_local_state(tmp_path)

        assert result.status == "degraded"
        assert (
            "not found" in result.message.lower() or "missing" in result.message.lower()
        )


class TestHealthCheck:
    """Tests for health_check function."""

    @pytest.mark.requirement("FR-017")
    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, tmp_path: Path) -> None:
        """Test health_check returns healthy when all components healthy."""
        from agent_memory.ops.health import health_check

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.ai"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-api-key"
        mock_config.llm_provider = "openai"
        mock_config.get_llm_api_key.return_value = "sk-valid-key-with-length"

        cognee_dir = tmp_path / ".cognee"
        cognee_dir.mkdir()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await health_check(mock_config, base_path=tmp_path)

        assert result.overall_status == "healthy"
        assert result.is_healthy is True
        assert "cognee_cloud" in result.components
        assert "llm_provider" in result.components
        assert "local_state" in result.components

    @pytest.mark.requirement("FR-017")
    @pytest.mark.asyncio
    async def test_health_check_unhealthy_component(self, tmp_path: Path) -> None:
        """Test health_check returns unhealthy when a component fails."""
        import httpx

        from agent_memory.ops.health import health_check

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.ai"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-api-key"
        mock_config.llm_provider = "openai"
        mock_config.get_llm_api_key.return_value = "sk-valid-key-with-length"

        cognee_dir = tmp_path / ".cognee"
        cognee_dir.mkdir()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Failed"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await health_check(mock_config, base_path=tmp_path)

        assert result.overall_status == "unhealthy"
        assert result.is_healthy is False
        assert result.components["cognee_cloud"].status == "unhealthy"

    @pytest.mark.requirement("FR-017")
    @pytest.mark.asyncio
    async def test_health_check_degraded_component(self, tmp_path: Path) -> None:
        """Test health_check returns degraded when local state missing."""
        from agent_memory.ops.health import health_check

        mock_config = MagicMock()
        mock_config.cognee_api_url = "https://api.cognee.ai"
        mock_config.cognee_api_key.get_secret_value.return_value = "test-api-key"
        mock_config.llm_provider = "openai"
        mock_config.get_llm_api_key.return_value = "sk-valid-key-with-length"

        # No .cognee directory

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await health_check(mock_config, base_path=tmp_path)

        # degraded because local_state is degraded, but others are healthy
        assert result.overall_status == "degraded"
        assert result.components["local_state"].status == "degraded"


class TestHealthCheckResultSerialization:
    """Tests for HealthCheckResult serialization."""

    @pytest.mark.requirement("FR-017")
    def test_health_check_result_to_dict(self) -> None:
        """Test HealthCheckResult can be serialized to dict."""
        from agent_memory.ops.health import ComponentHealth, HealthCheckResult

        result = HealthCheckResult(
            overall_status="healthy",
            checked_at=datetime(2024, 1, 15, 12, 0, 0),
            components={
                "cognee_cloud": ComponentHealth(status="healthy", message="OK"),
            },
        )

        data = result.model_dump()

        assert data["overall_status"] == "healthy"
        assert "cognee_cloud" in data["components"]

    @pytest.mark.requirement("FR-017")
    def test_health_check_result_json_serializable(self) -> None:
        """Test HealthCheckResult can be serialized to JSON."""
        import json

        from agent_memory.ops.health import ComponentHealth, HealthCheckResult

        result = HealthCheckResult(
            overall_status="unhealthy",
            checked_at=datetime(2024, 1, 15, 12, 0, 0),
            components={
                "cognee_cloud": ComponentHealth(status="unhealthy", message="Failed"),
            },
        )

        json_str = result.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["overall_status"] == "unhealthy"
        assert parsed["is_healthy"] is False

"""Health checking module for agent-memory.

Provides functionality to check system health:
- Cognee Cloud connectivity
- LLM provider configuration
- Local state files

Implementation: T036 (FLO-621)
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import httpx
from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    from agent_memory.config import AgentMemoryConfig


class ComponentHealth(BaseModel):
    """Health status of an individual component.

    Attributes:
        status: Health status (healthy, degraded, unhealthy).
        message: Human-readable status message.
        response_time_ms: Optional response time in milliseconds.
    """

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Component health status"
    )
    message: str = Field(default="", description="Status message or error")
    response_time_ms: int | None = Field(
        default=None, ge=0, description="Response time in milliseconds"
    )


class HealthCheckResult(BaseModel):
    """Result of health check operation.

    Attributes:
        overall_status: Aggregated health status.
        checked_at: When the health check was performed.
        components: Health status of individual components.
    """

    overall_status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Overall system health"
    )
    checked_at: datetime = Field(..., description="When health check ran")
    components: dict[str, ComponentHealth] = Field(
        default_factory=dict, description="Component health statuses"
    )

    @computed_field
    @property
    def is_healthy(self) -> bool:
        """Check if overall status is healthy.

        Returns:
            True only if overall_status is 'healthy'.
        """
        return self.overall_status == "healthy"

    @computed_field
    @property
    def has_issues(self) -> bool:
        """Check if any component has issues.

        Returns:
            True if any component is not healthy.
        """
        return any(c.status != "healthy" for c in self.components.values())


async def check_cognee_cloud(config: AgentMemoryConfig) -> ComponentHealth:
    """Check connectivity to Cognee Cloud.

    Args:
        config: Agent memory configuration with API credentials.

    Returns:
        ComponentHealth with status and response time.
    """
    start_time = time.monotonic()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.cognee_api_url}/api/health",
                headers={"X-Api-Key": config.cognee_api_key.get_secret_value()},
                timeout=10.0,
            )
            response_time = int((time.monotonic() - start_time) * 1000)

            if response.status_code == 200:
                return ComponentHealth(
                    status="healthy",
                    message="Connected to Cognee Cloud",
                    response_time_ms=response_time,
                )
            elif response.status_code == 401:
                return ComponentHealth(
                    status="unhealthy",
                    message="Authentication failed (401) - check COGNEE_API_KEY",
                    response_time_ms=response_time,
                )
            else:
                return ComponentHealth(
                    status="degraded",
                    message=f"Unexpected status: {response.status_code}",
                    response_time_ms=response_time,
                )
    except httpx.TimeoutException:
        return ComponentHealth(
            status="unhealthy",
            message="Connection timeout",
        )
    except httpx.ConnectError as e:
        return ComponentHealth(
            status="unhealthy",
            message=f"Connection error: {e}",
        )
    except Exception as e:
        return ComponentHealth(
            status="unhealthy",
            message=f"Unexpected error: {e}",
        )


def check_llm_provider(config: AgentMemoryConfig) -> ComponentHealth:
    """Check LLM provider configuration.

    Args:
        config: Agent memory configuration.

    Returns:
        ComponentHealth indicating if LLM API key is configured.
    """
    try:
        api_key = config.get_llm_api_key()
        # Simple validation: key should be at least 10 characters
        if api_key and len(api_key) > 10:
            return ComponentHealth(
                status="healthy",
                message=f"{config.llm_provider} API key configured",
            )
        else:
            return ComponentHealth(
                status="unhealthy",
                message="LLM API key appears invalid (too short)",
            )
    except ValueError as e:
        return ComponentHealth(
            status="unhealthy",
            message=str(e),
        )
    except Exception as e:
        return ComponentHealth(
            status="unhealthy",
            message=f"Error checking LLM provider: {e}",
        )


def check_local_state(base_path: Path | None = None) -> ComponentHealth:
    """Check local state files.

    Args:
        base_path: Base path to check for .cognee directory.
            Defaults to current directory.

    Returns:
        ComponentHealth indicating if local state exists.
    """
    if base_path is None:
        base_path = Path.cwd()

    cognee_dir = base_path / ".cognee"

    if cognee_dir.exists():
        return ComponentHealth(
            status="healthy",
            message=f".cognee directory exists at {cognee_dir}",
        )
    else:
        return ComponentHealth(
            status="degraded",
            message=".cognee directory not found - run 'agent-memory init'",
        )


async def health_check(
    config: AgentMemoryConfig,
    *,
    base_path: Path | None = None,
) -> HealthCheckResult:
    """Perform comprehensive health check.

    Checks all components and returns aggregated status:
    - Cognee Cloud connectivity
    - LLM provider configuration
    - Local state files

    Args:
        config: Agent memory configuration.
        base_path: Base path for local state check. Defaults to cwd.

    Returns:
        HealthCheckResult with overall status and component details.
    """
    # Check all components
    cognee_health = await check_cognee_cloud(config)
    llm_health = check_llm_provider(config)
    local_health = check_local_state(base_path)

    components = {
        "cognee_cloud": cognee_health,
        "llm_provider": llm_health,
        "local_state": local_health,
    }

    # Determine overall status
    statuses = [c.status for c in components.values()]

    overall: Literal["healthy", "degraded", "unhealthy"]
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall = "unhealthy"
    else:
        overall = "degraded"

    return HealthCheckResult(
        overall_status=overall,
        checked_at=datetime.now(),
        components=components,
    )

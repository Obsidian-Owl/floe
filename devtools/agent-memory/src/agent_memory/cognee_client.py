"""Cognee Cloud client wrapper with async operations and retry logic.

Provides a thin wrapper around the Cognee SDK with:
- Structured logging via structlog
- Retry logic for transient failures
- Health check via httpx
- Type-safe configuration

Example:
    >>> from agent_memory.config import get_config
    >>> from agent_memory.cognee_client import CogneeClient
    >>>
    >>> config = get_config()
    >>> client = CogneeClient(config)
    >>> await client.health_check()
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Literal

import httpx
import structlog

if TYPE_CHECKING:
    from agent_memory.config import AgentMemoryConfig
    from agent_memory.models import HealthStatus, SearchResult

logger = structlog.get_logger(__name__)

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 1.0
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class CogneeClientError(Exception):
    """Base exception for Cognee client errors."""


class CogneeAuthenticationError(CogneeClientError):
    """Authentication with Cognee Cloud failed."""


class CogneeConnectionError(CogneeClientError):
    """Failed to connect to Cognee Cloud."""


class CogneeClient:
    """Async client wrapper for Cognee Cloud SDK.

    Provides a simplified interface to the Cognee SDK with:
    - Automatic configuration from AgentMemoryConfig
    - Structured logging for all operations
    - Retry logic for transient failures
    - Health check endpoint

    Args:
        config: Agent memory configuration with API credentials.

    Example:
        >>> config = get_config()
        >>> client = CogneeClient(config)
        >>> status = await client.health_check()
        >>> print(status.overall_status)
        'healthy'
    """

    def __init__(self, config: AgentMemoryConfig) -> None:
        """Initialize the Cognee client.

        Args:
            config: Configuration with Cognee API credentials.
        """
        self._config = config
        self._log = logger.bind(
            cognee_url=config.cognee_api_url,
        )
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure Cognee SDK is initialized with credentials."""
        if self._initialized:
            return

        import cognee  # type: ignore[import-untyped]  # type: ignore[import-untyped]

        # Configure Cognee with our settings (v0.5.x API)
        cognee.config.set_llm_config(
            {
                "llm_provider": self._config.llm_provider,
                "llm_model": f"{self._config.llm_provider}/{self._config.llm_model}",
                "llm_api_key": self._config.get_llm_api_key(),
            }
        )

        self._initialized = True
        self._log.info("cognee_client_initialized")

    async def health_check(self) -> HealthStatus:
        """Check connectivity to Cognee Cloud and LLM provider.

        Returns:
            HealthStatus with component-level status.

        Raises:
            CogneeConnectionError: If Cognee Cloud is unreachable.
        """
        from datetime import datetime

        from agent_memory.models import ComponentStatus, HealthStatus

        start_time = time.monotonic()
        cognee_status: ComponentStatus
        llm_status: ComponentStatus
        local_status: ComponentStatus

        # Check Cognee Cloud API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._config.cognee_api_url}/health",
                    headers={
                        "Authorization": f"Bearer {self._config.cognee_api_key.get_secret_value()}"
                    },
                    timeout=10.0,
                )
                response_time = int((time.monotonic() - start_time) * 1000)

                if response.status_code == 200:
                    cognee_status = ComponentStatus(
                        status="healthy",
                        message="Connected to Cognee Cloud",
                        response_time_ms=response_time,
                    )
                elif response.status_code == 401:
                    cognee_status = ComponentStatus(
                        status="unhealthy",
                        message="Authentication failed - check COGNEE_API_KEY",
                        response_time_ms=response_time,
                    )
                else:
                    cognee_status = ComponentStatus(
                        status="degraded",
                        message=f"Unexpected status: {response.status_code}",
                        response_time_ms=response_time,
                    )
        except httpx.TimeoutException:
            cognee_status = ComponentStatus(
                status="unhealthy",
                message="Connection timeout",
            )
        except httpx.ConnectError as e:
            cognee_status = ComponentStatus(
                status="unhealthy",
                message=f"Connection failed: {e}",
            )

        # Check LLM provider (simple key validation)
        try:
            llm_key = self._config.get_llm_api_key()
            if llm_key and len(llm_key) > 10:
                llm_status = ComponentStatus(
                    status="healthy",
                    message=f"{self._config.llm_provider} API key configured",
                )
            else:
                llm_status = ComponentStatus(
                    status="unhealthy",
                    message="LLM API key appears invalid",
                )
        except ValueError as e:
            llm_status = ComponentStatus(
                status="unhealthy",
                message=str(e),
            )

        # Check local state
        from pathlib import Path

        cognee_dir = Path(".cognee")
        if cognee_dir.exists():
            local_status = ComponentStatus(
                status="healthy",
                message=".cognee directory exists",
            )
        else:
            local_status = ComponentStatus(
                status="degraded",
                message=".cognee directory not found - run 'agent-memory init'",
            )

        # Determine overall status
        statuses = [cognee_status.status, llm_status.status, local_status.status]
        overall: Literal["healthy", "degraded", "unhealthy"]
        if all(s == "healthy" for s in statuses):
            overall = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall = "unhealthy"
        else:
            overall = "degraded"

        health = HealthStatus(
            overall_status=overall,
            checked_at=datetime.now(),
            cognee_cloud=cognee_status,
            llm_provider=llm_status,
            local_state=local_status,
        )

        self._log.info(
            "health_check_completed",
            overall_status=overall,
            cognee_status=cognee_status.status,
            llm_status=llm_status.status,
        )

        return health

    async def add_content(
        self,
        content: str | list[str],
        dataset_name: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add content to a Cognee dataset.

        Args:
            content: Text content or list of content to add.
            dataset_name: Target dataset name.
            metadata: Optional metadata to attach.

        Raises:
            CogneeClientError: If adding content fails.
        """
        await self._ensure_initialized()
        import cognee

        self._log.info(
            "add_content_started",
            dataset=dataset_name,
            content_count=len(content) if isinstance(content, list) else 1,
        )

        try:
            # Cognee expects content as text or list
            await cognee.add(content, dataset_name=dataset_name)
            self._log.info("add_content_completed", dataset=dataset_name)
        except Exception as e:
            self._log.error("add_content_failed", dataset=dataset_name, error=str(e))
            raise CogneeClientError(f"Failed to add content: {e}") from e

    async def cognify(self, dataset_name: str | None = None) -> None:
        """Process content into knowledge graph using LLM.

        Args:
            dataset_name: Optional dataset to cognify. If None, cognifies all.

        Raises:
            CogneeClientError: If cognify operation fails.
        """
        await self._ensure_initialized()
        import cognee

        self._log.info("cognify_started", dataset=dataset_name or "all")

        try:
            if dataset_name:
                await cognee.cognify(dataset_name=dataset_name)
            else:
                await cognee.cognify()
            self._log.info("cognify_completed", dataset=dataset_name or "all")
        except Exception as e:
            self._log.error("cognify_failed", dataset=dataset_name, error=str(e))
            raise CogneeClientError(f"Cognify failed: {e}") from e

    async def codify(self, repo_path: str, dataset_name: str | None = None) -> None:
        """Analyze code repository and build knowledge graph.

        Args:
            repo_path: Path to the repository to analyze.
            dataset_name: Optional dataset name for code analysis.

        Raises:
            CogneeClientError: If codify operation fails.
        """
        await self._ensure_initialized()
        import cognee

        self._log.info("codify_started", repo_path=repo_path, dataset=dataset_name)

        try:
            await cognee.codify(repo_path)
            self._log.info("codify_completed", repo_path=repo_path)
        except Exception as e:
            self._log.error("codify_failed", repo_path=repo_path, error=str(e))
            raise CogneeClientError(f"Codify failed: {e}") from e

    async def search(
        self,
        query: str,
        *,
        search_type: str = "GRAPH_COMPLETION",
        top_k: int | None = None,
    ) -> SearchResult:
        """Search the knowledge graph.

        Args:
            query: Search query string.
            search_type: Type of search (GRAPH_COMPLETION, SUMMARIES, INSIGHTS, CHUNKS).
            top_k: Maximum number of results. Uses config default if not specified.

        Returns:
            SearchResult with matching items.

        Raises:
            CogneeClientError: If search fails.
        """
        await self._ensure_initialized()
        import cognee

        from agent_memory.models import SearchResult, SearchResultItem

        effective_top_k = top_k or self._config.search_top_k
        start_time = time.monotonic()

        self._log.info(
            "search_started",
            query=query,
            search_type=search_type,
            top_k=effective_top_k,
        )

        try:
            # Call Cognee search
            results = await cognee.search(query, search_type=search_type)
            execution_time = int((time.monotonic() - start_time) * 1000)

            # Convert results to our model
            items: list[SearchResultItem] = []
            if results:
                for item in results[:effective_top_k]:
                    if isinstance(item, dict):
                        items.append(
                            SearchResultItem(
                                content=str(item.get("content", "")),
                                source_path=item.get("source"),
                                relevance_score=float(item.get("score", 0.0)),
                                metadata=item.get("metadata", {}),
                            )
                        )
                    else:
                        items.append(
                            SearchResultItem(
                                content=str(item),
                                relevance_score=0.0,
                            )
                        )

            search_result = SearchResult(
                query=query,
                search_type=search_type,
                results=items,
                total_count=len(items),
                execution_time_ms=execution_time,
            )

            self._log.info(
                "search_completed",
                query=query,
                result_count=len(items),
                execution_time_ms=execution_time,
            )

            return search_result

        except Exception as e:
            self._log.error("search_failed", query=query, error=str(e))
            raise CogneeClientError(f"Search failed: {e}") from e

    async def delete_dataset(self, dataset_name: str) -> None:
        """Delete a dataset from Cognee.

        Args:
            dataset_name: Name of dataset to delete.

        Raises:
            CogneeClientError: If deletion fails.
        """
        await self._ensure_initialized()
        import cognee

        self._log.info("delete_dataset_started", dataset=dataset_name)

        try:
            await cognee.delete(dataset_name=dataset_name)
            self._log.info("delete_dataset_completed", dataset=dataset_name)
        except Exception as e:
            self._log.error("delete_dataset_failed", dataset=dataset_name, error=str(e))
            raise CogneeClientError(f"Delete failed: {e}") from e

    async def list_datasets(self) -> list[str]:
        """List all datasets in Cognee.

        Returns:
            List of dataset names.

        Raises:
            CogneeClientError: If listing fails.
        """
        await self._ensure_initialized()
        import cognee

        self._log.info("list_datasets_started")

        try:
            # Get datasets from Cognee
            datasets = await cognee.get_datasets()
            dataset_names = [d.name if hasattr(d, "name") else str(d) for d in datasets]
            self._log.info("list_datasets_completed", count=len(dataset_names))
            return dataset_names
        except Exception as e:
            self._log.error("list_datasets_failed", error=str(e))
            raise CogneeClientError(f"List datasets failed: {e}") from e

    async def get_status(self, dataset_name: str | None = None) -> dict[str, Any]:
        """Get pipeline status for a dataset.

        Args:
            dataset_name: Optional dataset name. If None, gets overall status.

        Returns:
            Dictionary with status information.

        Raises:
            CogneeClientError: If status check fails.
        """
        await self._ensure_initialized()
        import cognee

        self._log.info("get_status_started", dataset=dataset_name)

        try:
            status = await cognee.get_status(dataset_name=dataset_name)
            self._log.info("get_status_completed", dataset=dataset_name)
            return status if isinstance(status, dict) else {"status": str(status)}
        except Exception as e:
            self._log.error("get_status_failed", dataset=dataset_name, error=str(e))
            raise CogneeClientError(f"Get status failed: {e}") from e

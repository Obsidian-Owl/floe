"""Cognee Cloud client wrapper with async operations and retry logic.

Provides a thin wrapper around the Cognee Cloud REST API with:
- Structured logging via structlog
- Retry logic for transient failures
- Health check via httpx
- Type-safe configuration

Uses Cognee Cloud REST API for add/cognify/search operations to ensure
LLM processing happens server-side (avoids SDK bugs with local LLM calls).

Example:
    >>> from agent_memory.config import get_config
    >>> from agent_memory.cognee_client import CogneeClient
    >>>
    >>> config = get_config()
    >>> client = CogneeClient(config)
    >>> await client.health_check()
"""

from __future__ import annotations

import asyncio
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
DEFAULT_TIMEOUT_SECONDS = 300.0  # 5 minutes for cognify operations
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


class CogneeClientError(Exception):
    """Base exception for Cognee client errors."""


class CogneeAuthenticationError(CogneeClientError):
    """Authentication with Cognee Cloud failed."""


class CogneeConnectionError(CogneeClientError):
    """Failed to connect to Cognee Cloud."""


class CogneeClient:
    """Async client wrapper for Cognee Cloud REST API.

    Provides a simplified interface to the Cognee Cloud API with:
    - Automatic configuration from AgentMemoryConfig
    - Structured logging for all operations
    - Retry logic for transient failures
    - Health check endpoint

    Uses REST API instead of local SDK to ensure LLM processing
    happens server-side in Cognee Cloud.

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

        Note:
            Call validate_connection() after initialization to verify
            connectivity to Cognee Cloud.
        """
        self._config = config
        self._log = logger.bind(
            cognee_url=config.cognee_api_url,
        )

    async def validate_connection(self) -> float:
        """Validate connection to Cognee Cloud.

        Performs a health check to verify connectivity and authentication.
        Should be called after initialization to ensure the client can
        communicate with Cognee Cloud.

        Returns:
            Connection latency in milliseconds.

        Raises:
            CogneeConnectionError: If Cognee Cloud is unreachable.
            CogneeAuthenticationError: If API key is invalid.

        Example:
            >>> client = CogneeClient(config)
            >>> latency_ms = await client.validate_connection()
            >>> print(f"Connected in {latency_ms}ms")
        """
        start_time = time.monotonic()

        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(
                    f"{self._config.cognee_api_url}/api/health",
                    headers={
                        "X-Api-Key": self._config.cognee_api_key.get_secret_value()
                    },
                    timeout=10.0,
                )
                latency_ms = int((time.monotonic() - start_time) * 1000)

                if response.status_code == 401:
                    self._log.error(
                        "connection_validation_auth_failed",
                        status_code=response.status_code,
                    )
                    raise CogneeAuthenticationError(
                        "Authentication failed - check COGNEE_API_KEY"
                    )

                if response.status_code != 200:
                    self._log.error(
                        "connection_validation_failed",
                        status_code=response.status_code,
                    )
                    raise CogneeConnectionError(
                        f"Cognee Cloud returned status {response.status_code}"
                    )

                self._log.info(
                    "connection_validated",
                    latency_ms=latency_ms,
                )
                return float(latency_ms)

        except httpx.TimeoutException as e:
            self._log.error("connection_validation_timeout", error=str(e))
            raise CogneeConnectionError(
                f"Connection to {self._config.cognee_api_url} timed out"
            ) from e
        except httpx.ConnectError as e:
            self._log.error("connection_validation_unreachable", error=str(e))
            raise CogneeConnectionError(
                f"Cannot reach {self._config.cognee_api_url}: {e}"
            ) from e

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers with authentication.

        Cognee Cloud uses X-Api-Key header for authentication.
        """
        return {
            "X-Api-Key": self._config.cognee_api_key.get_secret_value(),
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        *,
        json_data: dict[str, Any] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> httpx.Response:
        """Make an authenticated HTTP request to Cognee Cloud.

        Args:
            method: HTTP method (GET, POST, DELETE).
            endpoint: API endpoint path (e.g., "/api/add").
            json_data: Optional JSON body data.
            timeout: Request timeout in seconds.

        Returns:
            HTTP response.

        Raises:
            CogneeClientError: If request fails after retries.
        """
        url = f"{self._config.cognee_api_url}{endpoint}"
        last_error: Exception | None = None

        for attempt in range(DEFAULT_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=self._get_headers(),
                        json=json_data,
                        timeout=timeout,
                    )

                    if response.status_code in RETRYABLE_STATUS_CODES:
                        self._log.warning(
                            "request_retryable_error",
                            status_code=response.status_code,
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(DEFAULT_RETRY_DELAY_SECONDS * (attempt + 1))
                        continue

                    return response

            except (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.ReadError,
                httpx.RemoteProtocolError,
            ) as e:
                last_error = e
                self._log.warning(
                    "request_connection_error",
                    error=str(e),
                    attempt=attempt + 1,
                )
                await asyncio.sleep(DEFAULT_RETRY_DELAY_SECONDS * (attempt + 1))

        msg = f"Request failed after {DEFAULT_MAX_RETRIES} attempts"
        raise CogneeClientError(msg) from last_error

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
                    f"{self._config.cognee_api_url}/api/health",
                    headers={
                        "X-Api-Key": self._config.cognee_api_key.get_secret_value()
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
        """Add content to a Cognee dataset via REST API.

        Args:
            content: Text content or list of content to add.
            dataset_name: Target dataset name.
            metadata: Optional metadata to attach (currently unused by API).

        Raises:
            CogneeClientError: If adding content fails.
        """
        content_list = [content] if isinstance(content, str) else content

        self._log.info(
            "add_content_started",
            dataset=dataset_name,
            content_count=len(content_list),
        )

        try:
            # Use REST API to add content
            # Cognee Cloud API expects data as list of text strings
            response = await self._make_request(
                "POST",
                "/api/add",
                json_data={
                    "data": content_list,
                    "datasetName": dataset_name,
                },
            )

            if response.status_code not in (200, 201, 202):
                error_detail = response.text
                raise CogneeClientError(
                    f"Add content failed with status {response.status_code}: {error_detail}"
                )

            self._log.info("add_content_completed", dataset=dataset_name)
        except CogneeClientError:
            raise
        except Exception as e:
            self._log.error("add_content_failed", dataset=dataset_name, error=str(e))
            raise CogneeClientError(f"Failed to add content: {e}") from e

    async def cognify(self, dataset_name: str | None = None) -> None:
        """Process content into knowledge graph using LLM via REST API.

        Args:
            dataset_name: Optional dataset to cognify. If None, cognifies all.

        Raises:
            CogneeClientError: If cognify operation fails.
        """
        self._log.info("cognify_started", dataset=dataset_name or "all")

        try:
            # Use REST API - LLM processing happens server-side
            json_data: dict[str, Any] = {}
            if dataset_name:
                json_data["datasets"] = [dataset_name]

            response = await self._make_request(
                "POST",
                "/api/cognify",
                json_data=json_data,
                timeout=DEFAULT_TIMEOUT_SECONDS,  # Cognify can take a while
            )

            if response.status_code not in (200, 201, 202):
                error_detail = response.text
                raise CogneeClientError(
                    f"Cognify failed with status {response.status_code}: {error_detail}"
                )

            self._log.info("cognify_completed", dataset=dataset_name or "all")
        except CogneeClientError:
            raise
        except Exception as e:
            self._log.error("cognify_failed", dataset=dataset_name, error=str(e))
            raise CogneeClientError(f"Cognify failed: {e}") from e

    async def codify(self, repo_path: str, dataset_name: str | None = None) -> None:
        """Analyze code repository and build knowledge graph.

        Note: Codify is not yet supported via REST API.
        This method is a placeholder for future implementation.

        Args:
            repo_path: Path to the repository to analyze.
            dataset_name: Optional dataset name for code analysis.

        Raises:
            CogneeClientError: If codify operation fails.
        """
        self._log.info("codify_started", repo_path=repo_path, dataset=dataset_name)

        # Codify requires uploading code to the server
        # For now, raise NotImplementedError
        raise NotImplementedError(
            "Codify via REST API is not yet implemented. "
            "Use the local SDK or upload files via the add endpoint."
        )

    async def search(
        self,
        query: str,
        *,
        search_type: str = "GRAPH_COMPLETION",
        top_k: int | None = None,
    ) -> SearchResult:
        """Search the knowledge graph via REST API.

        Args:
            query: Search query string.
            search_type: Type of search (GRAPH_COMPLETION, SUMMARIES, INSIGHTS, CHUNKS).
            top_k: Maximum number of results. Uses config default if not specified.

        Returns:
            SearchResult with matching items.

        Raises:
            CogneeClientError: If search fails.
        """
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
            # Use REST API for search
            response = await self._make_request(
                "POST",
                "/api/search",
                json_data={
                    "query": query,
                    "search_type": search_type,
                    "top_k": effective_top_k,
                },
            )

            execution_time = int((time.monotonic() - start_time) * 1000)

            if response.status_code not in (200, 201):
                error_detail = response.text
                raise CogneeClientError(
                    f"Search failed with status {response.status_code}: {error_detail}"
                )

            # Parse response
            results_data = response.json()
            items: list[SearchResultItem] = []

            # Handle different response formats from Cognee Cloud
            raw_results: list[Any]
            if isinstance(results_data, list):
                raw_results = results_data
            elif isinstance(results_data, dict):
                raw_results = results_data.get("results") or results_data.get("data") or []
            else:
                raw_results = []

            for item in raw_results[:effective_top_k]:
                if isinstance(item, dict):
                    items.append(
                        SearchResultItem(
                            content=str(item.get("content", item.get("text", ""))),
                            source_path=item.get("source", item.get("source_path")),
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

        except CogneeClientError:
            raise
        except Exception as e:
            self._log.error("search_failed", query=query, error=str(e))
            raise CogneeClientError(f"Search failed: {e}") from e

    async def delete_dataset(self, dataset_name: str) -> None:
        """Delete a dataset from Cognee via REST API.

        Args:
            dataset_name: Name of dataset to delete.

        Raises:
            CogneeClientError: If deletion fails or dataset not found.
        """
        self._log.info("delete_dataset_started", dataset=dataset_name)

        try:
            # First, list datasets to get the UUID for the given name
            list_response = await self._make_request("GET", "/api/datasets")

            if list_response.status_code != 200:
                error_detail = list_response.text
                raise CogneeClientError(
                    f"Failed to list datasets: {list_response.status_code}: {error_detail}"
                )

            # Find the dataset UUID by name
            datasets_data = list_response.json()
            dataset_id: str | None = None

            # Handle different response formats
            datasets_list: list[dict[str, Any]]
            if isinstance(datasets_data, list):
                datasets_list = datasets_data
            elif isinstance(datasets_data, dict):
                datasets_list = (
                    datasets_data.get("datasets") or datasets_data.get("data") or []
                )
            else:
                datasets_list = []

            for ds in datasets_list:
                if isinstance(ds, dict):
                    ds_name = ds.get("name", "")
                    if ds_name == dataset_name:
                        dataset_id = ds.get("id", ds.get("dataset_id"))
                        break

            if not dataset_id:
                self._log.warning(
                    "delete_dataset_not_found",
                    dataset=dataset_name,
                )
                # Dataset doesn't exist, consider this a success
                return

            # Now delete by UUID
            response = await self._make_request(
                "DELETE",
                f"/api/datasets/{dataset_id}",
            )

            if response.status_code not in (200, 204):
                error_detail = response.text
                raise CogneeClientError(
                    f"Delete failed with status {response.status_code}: {error_detail}"
                )

            self._log.info("delete_dataset_completed", dataset=dataset_name)
        except CogneeClientError:
            raise
        except Exception as e:
            self._log.error("delete_dataset_failed", dataset=dataset_name, error=str(e))
            raise CogneeClientError(f"Delete failed: {e}") from e

    async def list_datasets(self) -> list[str]:
        """List all datasets in Cognee via REST API.

        Returns:
            List of dataset names.

        Raises:
            CogneeClientError: If listing fails.
        """
        self._log.info("list_datasets_started")

        try:
            response = await self._make_request(
                "GET",
                "/api/datasets",
            )

            if response.status_code != 200:
                error_detail = response.text
                raise CogneeClientError(
                    f"List datasets failed with status {response.status_code}: {error_detail}"
                )

            # Parse response
            data = response.json()
            datasets_list: list[Any]
            if isinstance(data, list):
                datasets_list = data
            elif isinstance(data, dict):
                datasets_list = data.get("datasets") or data.get("data") or []
            else:
                datasets_list = []

            dataset_names = [
                d.get("name", str(d)) if isinstance(d, dict) else str(d)
                for d in datasets_list
            ]

            self._log.info("list_datasets_completed", count=len(dataset_names))
            return dataset_names
        except CogneeClientError:
            raise
        except Exception as e:
            self._log.error("list_datasets_failed", error=str(e))
            raise CogneeClientError(f"List datasets failed: {e}") from e

    async def get_status(self, dataset_name: str | None = None) -> dict[str, Any]:
        """Get pipeline status for a dataset via REST API.

        Args:
            dataset_name: Optional dataset name. If None, gets overall status.

        Returns:
            Dictionary with status information.

        Raises:
            CogneeClientError: If status check fails.
        """
        self._log.info("get_status_started", dataset=dataset_name)

        try:
            endpoint = "/api/status"
            if dataset_name:
                endpoint = f"/api/datasets/{dataset_name}/status"

            response = await self._make_request("GET", endpoint)

            if response.status_code != 200:
                error_detail = response.text
                raise CogneeClientError(
                    f"Get status failed with status {response.status_code}: {error_detail}"
                )

            status = response.json()
            self._log.info("get_status_completed", dataset=dataset_name)
            return status if isinstance(status, dict) else {"status": str(status)}
        except CogneeClientError:
            raise
        except Exception as e:
            self._log.error("get_status_failed", dataset=dataset_name, error=str(e))
            raise CogneeClientError(f"Get status failed: {e}") from e

"""Batch fetcher for parallel OCI manifest retrieval.

This module provides the _BatchFetcher class for parallel HTTP requests to OCI
registries, fixing the N+1 query pattern in OCIClient.list().

Requirements: FR-005
User Story: US2 - Fix N+1 Performance Issues
Task: T012

The batch fetcher uses concurrent.futures.ThreadPoolExecutor to fetch multiple
manifests in parallel, reducing list() latency from O(n) to O(n/workers).

Example:
    >>> from floe_core.oci.batch_fetcher import BatchFetcher
    >>> from oras.client import OrasClient
    >>>
    >>> fetcher = BatchFetcher(max_workers=10)
    >>> results = fetcher.fetch_manifests(
    ...     oras_client=oras_client,
    ...     tag_refs=[("v1.0.0", "registry/repo:v1.0.0"), ...],
    ... )
    >>> for tag, manifest in results.items():
    ...     print(f"{tag}: {manifest['digest']}")
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from oras.client import OrasClient

logger = structlog.get_logger(__name__)


# Default configuration for parallel fetching
DEFAULT_MAX_WORKERS = 10
"""Default number of worker threads for parallel manifest fetching."""

MAX_WORKERS_LIMIT = 20
"""Maximum allowed workers to prevent overwhelming registries."""


class BatchFetchError(Exception):
    """Error during batch manifest fetching.

    Attributes:
        tag: The tag that failed to fetch.
        cause: The underlying exception.
    """

    def __init__(self, tag: str, cause: Exception) -> None:
        """Initialize BatchFetchError.

        Args:
            tag: The tag that failed to fetch.
            cause: The underlying exception.
        """
        self.tag = tag
        self.cause = cause
        super().__init__(f"Failed to fetch manifest for tag '{tag}': {cause}")


class BatchFetchResult:
    """Result of a batch manifest fetch operation.

    Attributes:
        manifests: Dictionary mapping tag names to manifest data.
        errors: Dictionary mapping tag names to errors that occurred.
        total_tags: Total number of tags attempted.
        successful_tags: Number of successfully fetched tags.
        failed_tags: Number of tags that failed to fetch.
    """

    def __init__(self) -> None:
        """Initialize empty BatchFetchResult."""
        self.manifests: dict[str, dict[str, Any]] = {}
        self.errors: dict[str, Exception] = {}

    @property
    def total_tags(self) -> int:
        """Return total number of tags attempted."""
        return len(self.manifests) + len(self.errors)

    @property
    def successful_tags(self) -> int:
        """Return number of successfully fetched tags."""
        return len(self.manifests)

    @property
    def failed_tags(self) -> int:
        """Return number of tags that failed to fetch."""
        return len(self.errors)

    def add_manifest(self, tag: str, manifest: dict[str, Any]) -> None:
        """Add a successfully fetched manifest.

        Args:
            tag: Tag name.
            manifest: Manifest data dictionary.
        """
        self.manifests[tag] = manifest

    def add_error(self, tag: str, error: Exception) -> None:
        """Add a failed fetch.

        Args:
            tag: Tag name.
            error: The exception that occurred.
        """
        self.errors[tag] = error


class BatchFetcher:
    """Parallel manifest fetcher using ThreadPoolExecutor.

    Fetches multiple OCI manifests concurrently to avoid N+1 query patterns.
    Uses ThreadPoolExecutor for I/O-bound parallel HTTP requests.

    Thread Safety:
        This class is thread-safe. Multiple threads can call fetch_manifests()
        concurrently. Each call creates its own executor.

    Example:
        >>> fetcher = BatchFetcher(max_workers=10)
        >>> result = fetcher.fetch_manifests(
        ...     oras_client=oras_client,
        ...     tag_refs=[("v1.0.0", "registry/repo:v1.0.0")],
        ... )
        >>> for tag, manifest in result.manifests.items():
        ...     print(f"{tag}: fetched successfully")
    """

    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS) -> None:
        """Initialize BatchFetcher.

        Args:
            max_workers: Maximum number of parallel workers.
                Capped at MAX_WORKERS_LIMIT to prevent overwhelming registries.
                Defaults to DEFAULT_MAX_WORKERS (10).
        """
        # Cap workers to prevent overwhelming registries
        self._max_workers = min(max_workers, MAX_WORKERS_LIMIT)
        logger.debug(
            "batch_fetcher_initialized",
            max_workers=self._max_workers,
        )

    @property
    def max_workers(self) -> int:
        """Return the maximum number of worker threads."""
        return self._max_workers

    def fetch_manifests(
        self,
        oras_client: OrasClient,
        tag_refs: list[tuple[str, str]],
    ) -> BatchFetchResult:
        """Fetch manifests for multiple tags in parallel.

        Uses ThreadPoolExecutor to fetch manifests concurrently, significantly
        reducing latency compared to sequential fetching.

        Args:
            oras_client: Authenticated ORAS client for registry operations.
            tag_refs: List of (tag_name, target_ref) tuples.
                - tag_name: Human-readable tag (e.g., "v1.0.0")
                - target_ref: Full OCI reference (e.g., "registry/repo:v1.0.0")

        Returns:
            BatchFetchResult containing successfully fetched manifests and errors.

        Example:
            >>> result = fetcher.fetch_manifests(
            ...     oras_client=client,
            ...     tag_refs=[
            ...         ("v1.0.0", "harbor.example.com/floe/test:v1.0.0"),
            ...         ("v1.0.1", "harbor.example.com/floe/test:v1.0.1"),
            ...     ],
            ... )
            >>> print(f"Fetched {result.successful_tags}/{result.total_tags}")
        """
        result = BatchFetchResult()

        if not tag_refs:
            return result

        log = logger.bind(
            total_tags=len(tag_refs),
            max_workers=self._max_workers,
        )
        log.debug("batch_fetch_started")

        def _fetch_single(tag_name: str, target_ref: str) -> tuple[str, dict[str, Any]]:
            """Fetch a single manifest (executed in thread pool).

            Args:
                tag_name: Tag name for result mapping.
                target_ref: Full OCI reference to fetch.

            Returns:
                Tuple of (tag_name, manifest_data).

            Raises:
                BatchFetchError: If fetch fails.
            """
            try:
                manifest_data = oras_client.get_manifest(container=target_ref)
                return tag_name, manifest_data
            except Exception as e:
                raise BatchFetchError(tag_name, e) from e

        # Use ThreadPoolExecutor for parallel I/O
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            # Submit all fetch tasks
            future_to_tag = {
                executor.submit(_fetch_single, tag_name, target_ref): tag_name
                for tag_name, target_ref in tag_refs
            }

            # Collect results as they complete
            for future in as_completed(future_to_tag):
                tag_name = future_to_tag[future]
                try:
                    _, manifest_data = future.result()
                    result.add_manifest(tag_name, manifest_data)
                except BatchFetchError as e:
                    result.add_error(tag_name, e.cause)
                    log.warning(
                        "batch_fetch_tag_failed",
                        tag=tag_name,
                        error=str(e.cause),
                    )
                except Exception as e:
                    result.add_error(tag_name, e)
                    log.warning(
                        "batch_fetch_tag_failed",
                        tag=tag_name,
                        error=str(e),
                    )

        log.debug(
            "batch_fetch_completed",
            successful=result.successful_tags,
            failed=result.failed_tags,
        )

        return result


__all__ = [
    "BatchFetcher",
    "BatchFetchError",
    "BatchFetchResult",
    "DEFAULT_MAX_WORKERS",
    "MAX_WORKERS_LIMIT",
]

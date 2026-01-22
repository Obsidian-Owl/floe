"""Performance benchmark tests for OCI client.

This module provides performance benchmarks to validate N+1 query fixes
in the OCI client's list() and pull() operations.

Requirements: SC-007
User Story: US2 - Fix N+1 Performance Issues
Task: T011
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from floe_core.oci.client import OCIClient
from floe_core.schemas.oci import AuthType, CacheConfig, RegistryAuth, RegistryConfig

# Performance targets (from spec)
LIST_TARGET_SECONDS = 6.0  # list() with 100 tags should complete in <6s
SPEEDUP_TARGET = 5.0  # 5x improvement over sequential baseline


class MockOrasClient:
    """Mock ORAS client that simulates registry latency."""

    def __init__(
        self,
        tags: list[str],
        latency_per_request: float = 0.05,
    ) -> None:
        """Initialize mock ORAS client.

        Args:
            tags: List of tag names to return.
            latency_per_request: Simulated network latency per request.
        """
        self.tags = tags
        self.latency = latency_per_request
        self.request_count = 0

    def get_tags(self, container: str) -> list[str]:  # noqa: ARG002
        """Return list of tags with simulated latency."""
        time.sleep(self.latency)
        self.request_count += 1
        return self.tags

    def get_manifest(self, container: str) -> dict[str, Any]:  # noqa: ARG002
        """Return mock manifest with simulated latency."""
        time.sleep(self.latency)
        self.request_count += 1
        return {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {
                "mediaType": "application/vnd.oci.empty.v1+json",
                "digest": "sha256:abc123",
                "size": 0,
            },
            "layers": [
                {
                    "mediaType": "application/octet-stream",
                    "digest": "sha256:layer1",
                    "size": 1024,
                }
            ],
            "annotations": {
                "org.opencontainers.image.created": "2026-01-22T00:00:00Z",
            },
        }


def _create_mock_client(
    tags: list[str],
    latency: float = 0.05,
) -> tuple[OCIClient, MockOrasClient]:
    """Create OCIClient with mocked ORAS backend.

    Args:
        tags: List of tag names.
        latency: Simulated latency per request.

    Returns:
        Tuple of (OCIClient, MockOrasClient).
    """
    mock_oras = MockOrasClient(tags, latency)

    config = RegistryConfig(
        uri="oci://registry.example.com/floe/test",
        auth=RegistryAuth(type=AuthType.ANONYMOUS),
        cache=CacheConfig(enabled=False),
    )

    client = OCIClient(registry_config=config, secrets_plugin=None)

    # Patch the _create_oras_client method
    client._create_oras_client = MagicMock(return_value=mock_oras)  # type: ignore[method-assign]

    return client, mock_oras


@pytest.mark.requirement("SC-007")
@pytest.mark.benchmark
def test_list_performance_with_100_tags() -> None:
    """Benchmark list() performance with 100 tags.

    Given an OCI registry with 100 tags,
    When I call client.list(),
    Then it completes within 6 seconds (vs 30s baseline).
    """
    # Create 100 mock tags
    tags = [f"v1.0.{i}" for i in range(100)]
    client, mock_oras = _create_mock_client(tags, latency=0.05)

    # Time the list operation
    start_time = time.monotonic()
    result = client.list()
    duration = time.monotonic() - start_time

    # Verify results
    assert len(result) == 100, f"Expected 100 tags, got {len(result)}"

    # Performance assertion
    # Note: This test will initially FAIL with sequential implementation
    # After T013 (ThreadPoolExecutor), it should pass
    assert duration < LIST_TARGET_SECONDS, (
        f"list() took {duration:.2f}s with 100 tags, "
        f"target is <{LIST_TARGET_SECONDS}s. "
        f"Total requests: {mock_oras.request_count}"
    )


@pytest.mark.requirement("SC-007")
@pytest.mark.benchmark
def test_list_parallel_speedup() -> None:
    """Verify parallel implementation achieves 5x speedup.

    Compares sequential vs parallel implementation timing.
    After T013, the parallel implementation should be 5x faster.
    """
    tags = [f"v1.0.{i}" for i in range(50)]
    latency = 0.05  # 50ms per request

    # Calculate expected sequential time: 1 get_tags + 50 get_manifest = 51 requests
    # Sequential: 51 * 0.05 = 2.55s
    expected_sequential = (1 + len(tags)) * latency

    # Create client
    client, mock_oras = _create_mock_client(tags, latency)

    # Time the list operation
    start_time = time.monotonic()
    result = client.list()
    actual_duration = time.monotonic() - start_time

    # Verify results
    assert len(result) == 50

    # Calculate actual speedup
    # If parallel with 10 workers: 1 + ceil(50/10) batches = ~6 requests worth of time
    # Expected parallel: ~0.3s
    speedup = expected_sequential / actual_duration if actual_duration > 0 else 1

    # Performance target: 5x speedup vs sequential baseline
    # Tests FAIL (not skip) when target not met per Constitution V
    assert speedup >= SPEEDUP_TARGET, (
        f"Parallel speedup {speedup:.1f}x is below target {SPEEDUP_TARGET}x. "
        f"Duration: {actual_duration:.2f}s vs expected sequential {expected_sequential:.2f}s. "
        f"Implement ThreadPoolExecutor-based parallel fetching (T013)."
    )


@pytest.mark.requirement("SC-007")
@pytest.mark.benchmark
def test_list_uses_thread_pool() -> None:
    """Verify list() uses ThreadPoolExecutor for parallel fetching.

    After T013, the implementation should use concurrent.futures.ThreadPoolExecutor
    either directly or via BatchFetcher.
    """
    import ast
    from pathlib import Path

    client_path = (
        Path(__file__).parents[3]
        / "src"
        / "floe_core"
        / "oci"
        / "client.py"
    )
    assert client_path.exists()

    content = client_path.read_text()
    tree = ast.parse(content)

    # Check for ThreadPoolExecutor usage directly OR via BatchFetcher
    has_thread_pool = False
    has_batch_fetcher = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id == "ThreadPoolExecutor":
                has_thread_pool = True
            elif node.id == "BatchFetcher":
                has_batch_fetcher = True
        if isinstance(node, ast.Attribute):
            if node.attr == "ThreadPoolExecutor":
                has_thread_pool = True
            elif node.attr == "BatchFetcher":
                has_batch_fetcher = True

    # BatchFetcher uses ThreadPoolExecutor internally
    uses_parallel_fetching = has_thread_pool or has_batch_fetcher

    # This test documents the requirement
    # After T013, this should pass
    assert uses_parallel_fetching, (
        "client.py should use ThreadPoolExecutor (directly or via BatchFetcher) "
        "for parallel manifest fetching. "
        "Implement _BatchFetcher class (T012) and update list() method (T013)."
    )


@pytest.mark.requirement("SC-007")
@pytest.mark.benchmark
def test_pull_uses_dictionary_lookup() -> None:
    """Verify pull() uses dictionary lookup instead of linear search.

    After T014, the implementation should use O(1) dictionary lookup
    for finding files in pulled artifacts.
    """
    from pathlib import Path

    client_path = (
        Path(__file__).parents[3]
        / "src"
        / "floe_core"
        / "oci"
        / "client.py"
    )
    assert client_path.exists()

    content = client_path.read_text()

    # Check for linear search pattern (current broken state)
    # Current code: for pulled_file in pulled_files: if file_path.name == "compiled_artifacts.json"
    has_linear_search = "for pulled_file in pulled_files:" in content

    # Check for dictionary lookup pattern (target state)
    # Target: files_by_name = {Path(f).name: Path(f) for f in pulled_files}
    # Target: artifacts_path = files_by_name.get("compiled_artifacts.json")
    has_dict_lookup = (
        "files_by_name" in content
        or "dict comprehension" in content.lower()
        or "{Path(f).name:" in content
    )

    # Performance target: O(1) dictionary lookup instead of O(n) linear search
    # Tests FAIL (not skip) when target not met per Constitution V
    assert not has_linear_search or has_dict_lookup, (
        "pull() should use dictionary lookup for file finding, not linear search. "
        "Implement files_by_name dict comprehension (T014)."
    )


@pytest.mark.requirement("SC-007")
def test_baseline_sequential_timing() -> None:
    """Document the baseline sequential timing for comparison.

    This test captures the current (slow) performance as a baseline.
    It's expected to pass and documents what we're improving.
    """
    tags = [f"v1.0.{i}" for i in range(20)]  # Use 20 tags for quick baseline
    latency = 0.03  # 30ms per request

    client, mock_oras = _create_mock_client(tags, latency)

    # Time the list operation
    start_time = time.monotonic()
    result = client.list()
    duration = time.monotonic() - start_time

    # Verify basic functionality
    assert len(result) == 20

    # Document the baseline
    # Expected sequential: 1 + 20 = 21 requests * 0.03s = 0.63s
    # With overhead, actual is typically 0.65-0.8s
    expected_min = (1 + len(tags)) * latency * 0.9  # Allow 10% faster
    expected_max = (1 + len(tags)) * latency * 1.5  # Allow 50% slower

    # This test just documents behavior, not a strict assertion
    # After T013, the duration will be significantly lower
    print(f"\nBaseline timing: {duration:.3f}s for {len(tags)} tags")
    print(f"Request count: {mock_oras.request_count}")
    print(f"Expected range: {expected_min:.3f}s - {expected_max:.3f}s")

    # Basic sanity check - should complete
    assert duration < 30.0, "list() is taking too long"

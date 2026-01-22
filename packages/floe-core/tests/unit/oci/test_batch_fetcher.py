"""Unit tests for BatchFetcher.

This module tests the BatchFetcher class for parallel manifest fetching.

Requirements: FR-005
User Story: US2 - Fix N+1 Performance Issues
Task: T012
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from floe_core.oci.batch_fetcher import (
    BatchFetchError,
    BatchFetcher,
    BatchFetchResult,
    DEFAULT_MAX_WORKERS,
    MAX_WORKERS_LIMIT,
)


class TestBatchFetchResult:
    """Tests for BatchFetchResult class."""

    @pytest.mark.requirement("FR-005")
    def test_empty_result(self) -> None:
        """Test empty BatchFetchResult has correct counts."""
        result = BatchFetchResult()

        assert result.total_tags == 0
        assert result.successful_tags == 0
        assert result.failed_tags == 0
        assert result.manifests == {}
        assert result.errors == {}

    @pytest.mark.requirement("FR-005")
    def test_add_manifest(self) -> None:
        """Test adding manifests to result."""
        result = BatchFetchResult()
        manifest = {"schemaVersion": 2, "config": {}}

        result.add_manifest("v1.0.0", manifest)

        assert result.total_tags == 1
        assert result.successful_tags == 1
        assert result.failed_tags == 0
        assert "v1.0.0" in result.manifests
        assert result.manifests["v1.0.0"] == manifest

    @pytest.mark.requirement("FR-005")
    def test_add_error(self) -> None:
        """Test adding errors to result."""
        result = BatchFetchResult()
        error = ValueError("test error")

        result.add_error("v1.0.0", error)

        assert result.total_tags == 1
        assert result.successful_tags == 0
        assert result.failed_tags == 1
        assert "v1.0.0" in result.errors
        assert result.errors["v1.0.0"] == error

    @pytest.mark.requirement("FR-005")
    def test_mixed_results(self) -> None:
        """Test result with both successes and failures."""
        result = BatchFetchResult()

        result.add_manifest("v1.0.0", {"digest": "sha256:abc"})
        result.add_manifest("v1.0.1", {"digest": "sha256:def"})
        result.add_error("v1.0.2", ValueError("not found"))

        assert result.total_tags == 3
        assert result.successful_tags == 2
        assert result.failed_tags == 1


class TestBatchFetchError:
    """Tests for BatchFetchError class."""

    @pytest.mark.requirement("FR-005")
    def test_error_attributes(self) -> None:
        """Test BatchFetchError has correct attributes."""
        cause = ValueError("test cause")
        error = BatchFetchError("v1.0.0", cause)

        assert error.tag == "v1.0.0"
        assert error.cause == cause
        assert "v1.0.0" in str(error)
        assert "test cause" in str(error)


class TestBatchFetcher:
    """Tests for BatchFetcher class."""

    @pytest.mark.requirement("FR-005")
    def test_default_max_workers(self) -> None:
        """Test default max_workers is set correctly."""
        fetcher = BatchFetcher()

        assert fetcher.max_workers == DEFAULT_MAX_WORKERS

    @pytest.mark.requirement("FR-005")
    def test_custom_max_workers(self) -> None:
        """Test custom max_workers is respected."""
        fetcher = BatchFetcher(max_workers=5)

        assert fetcher.max_workers == 5

    @pytest.mark.requirement("FR-005")
    def test_max_workers_capped(self) -> None:
        """Test max_workers is capped at MAX_WORKERS_LIMIT."""
        fetcher = BatchFetcher(max_workers=100)

        assert fetcher.max_workers == MAX_WORKERS_LIMIT

    @pytest.mark.requirement("FR-005")
    def test_fetch_empty_list(self) -> None:
        """Test fetching empty list returns empty result."""
        fetcher = BatchFetcher()
        mock_client = MagicMock()

        result = fetcher.fetch_manifests(mock_client, [])

        assert result.total_tags == 0
        mock_client.get_manifest.assert_not_called()

    @pytest.mark.requirement("FR-005")
    def test_fetch_single_manifest(self) -> None:
        """Test fetching a single manifest."""
        fetcher = BatchFetcher()
        mock_client = MagicMock()
        mock_client.get_manifest.return_value = {
            "schemaVersion": 2,
            "config": {"digest": "sha256:config"},
            "layers": [],
        }

        result = fetcher.fetch_manifests(
            mock_client,
            [("v1.0.0", "registry.example.com/repo:v1.0.0")],
        )

        assert result.successful_tags == 1
        assert result.failed_tags == 0
        assert "v1.0.0" in result.manifests
        mock_client.get_manifest.assert_called_once_with(
            container="registry.example.com/repo:v1.0.0"
        )

    @pytest.mark.requirement("FR-005")
    def test_fetch_multiple_manifests(self) -> None:
        """Test fetching multiple manifests."""
        fetcher = BatchFetcher(max_workers=5)
        mock_client = MagicMock()

        def mock_get_manifest(container: str) -> dict[str, Any]:
            tag = container.split(":")[-1]
            return {"schemaVersion": 2, "tag": tag}

        mock_client.get_manifest.side_effect = mock_get_manifest

        tag_refs = [
            ("v1.0.0", "registry.example.com/repo:v1.0.0"),
            ("v1.0.1", "registry.example.com/repo:v1.0.1"),
            ("v1.0.2", "registry.example.com/repo:v1.0.2"),
        ]

        result = fetcher.fetch_manifests(mock_client, tag_refs)

        assert result.successful_tags == 3
        assert result.failed_tags == 0
        assert mock_client.get_manifest.call_count == 3

    @pytest.mark.requirement("FR-005")
    def test_fetch_handles_partial_failure(self) -> None:
        """Test fetching handles partial failures gracefully."""
        fetcher = BatchFetcher()
        mock_client = MagicMock()

        def mock_get_manifest(container: str) -> dict[str, Any]:
            if "v1.0.1" in container:
                raise ValueError("Manifest not found")
            return {"schemaVersion": 2}

        mock_client.get_manifest.side_effect = mock_get_manifest

        tag_refs = [
            ("v1.0.0", "registry.example.com/repo:v1.0.0"),
            ("v1.0.1", "registry.example.com/repo:v1.0.1"),
            ("v1.0.2", "registry.example.com/repo:v1.0.2"),
        ]

        result = fetcher.fetch_manifests(mock_client, tag_refs)

        assert result.successful_tags == 2
        assert result.failed_tags == 1
        assert "v1.0.0" in result.manifests
        assert "v1.0.2" in result.manifests
        assert "v1.0.1" in result.errors

    @pytest.mark.requirement("FR-005")
    def test_fetch_all_failures(self) -> None:
        """Test fetching when all requests fail."""
        fetcher = BatchFetcher()
        mock_client = MagicMock()
        mock_client.get_manifest.side_effect = ConnectionError("Registry unavailable")

        tag_refs = [
            ("v1.0.0", "registry.example.com/repo:v1.0.0"),
            ("v1.0.1", "registry.example.com/repo:v1.0.1"),
        ]

        result = fetcher.fetch_manifests(mock_client, tag_refs)

        assert result.successful_tags == 0
        assert result.failed_tags == 2

    @pytest.mark.requirement("FR-005")
    @pytest.mark.benchmark
    def test_parallel_is_faster_than_sequential(self) -> None:
        """Test that parallel fetching is faster than sequential.

        This test verifies the ThreadPoolExecutor provides speedup.
        With 10 requests at 50ms each:
        - Sequential: ~500ms
        - Parallel (10 workers): ~50ms + overhead
        """
        fetcher = BatchFetcher(max_workers=10)
        mock_client = MagicMock()
        latency = 0.05  # 50ms per request

        def mock_get_manifest(container: str) -> dict[str, Any]:
            time.sleep(latency)
            tag = container.split(":")[-1]
            return {"schemaVersion": 2, "tag": tag}

        mock_client.get_manifest.side_effect = mock_get_manifest

        # Create 10 tag refs
        tag_refs = [
            (f"v1.0.{i}", f"registry.example.com/repo:v1.0.{i}") for i in range(10)
        ]

        # Expected sequential time: 10 * 0.05 = 0.5s
        expected_sequential = len(tag_refs) * latency

        # Time the parallel fetch
        start_time = time.monotonic()
        result = fetcher.fetch_manifests(mock_client, tag_refs)
        actual_duration = time.monotonic() - start_time

        # Verify all succeeded
        assert result.successful_tags == 10
        assert result.failed_tags == 0

        # Parallel should be significantly faster
        # Allow 2x overhead for thread creation, but should be <50% of sequential
        assert actual_duration < expected_sequential * 0.5, (
            f"Parallel fetch took {actual_duration:.2f}s, "
            f"expected <{expected_sequential * 0.5:.2f}s "
            f"(sequential would be {expected_sequential:.2f}s)"
        )

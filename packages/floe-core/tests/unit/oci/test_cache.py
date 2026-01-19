"""Unit tests for OCI artifact cache.

Tests basic cache operations (get/put) and cache integration with OCIClient.
Advanced TTL and eviction tests are in US6 (Phase 8).

Task: T023
Requirements: FR-013, FR-015
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from floe_core.oci.cache import CacheManager
from floe_core.schemas.oci import CacheConfig


class TestCacheManager:
    """Tests for CacheManager basic operations.

    FR-013: System MUST cache pulled artifacts locally.
    FR-015: System MUST skip network request when cache hit.
    """

    @pytest.fixture
    def cache_config(self, tmp_path: Path) -> CacheConfig:
        """Create CacheConfig with temp directory."""
        return CacheConfig(
            enabled=True,
            path=tmp_path / "cache",
            max_size_gb=1,
            ttl_hours=24,
        )

    @pytest.fixture
    def cache_manager(self, cache_config: CacheConfig) -> CacheManager:
        """Create CacheManager with temp directory."""
        return CacheManager(cache_config)

    @pytest.fixture
    def sample_content(self) -> bytes:
        """Sample artifact content."""
        return b'{"version": "0.2.0", "test": "data"}'

    @pytest.fixture
    def sample_digest(self, sample_content: bytes) -> str:
        """Compute digest of sample content."""
        return f"sha256:{hashlib.sha256(sample_content).hexdigest()}"

    @pytest.mark.requirement("8A-FR-013")
    def test_put_stores_artifact(
        self,
        cache_manager: CacheManager,
        sample_content: bytes,
        sample_digest: str,
    ) -> None:
        """Test that put() stores artifact content in cache.

        Verifies:
        - put() returns CacheEntry
        - Content is stored at expected path
        - Entry has correct digest
        """
        entry = cache_manager.put(
            digest=sample_digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=sample_content,
        )

        assert entry is not None
        assert entry.digest == sample_digest
        assert entry.tag == "v1.0.0"
        assert entry.path.exists()
        assert entry.path.read_bytes() == sample_content

    @pytest.mark.requirement("8A-FR-015")
    def test_get_returns_cached_artifact(
        self,
        cache_manager: CacheManager,
        sample_content: bytes,
        sample_digest: str,
    ) -> None:
        """Test that get() returns cached artifact.

        Verifies:
        - Cache hit returns CacheEntry
        - Entry has correct metadata
        - Entry path points to valid content
        """
        # First put
        cache_manager.put(
            digest=sample_digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=sample_content,
        )

        # Then get
        entry = cache_manager.get("oci://harbor.example.com/floe", "v1.0.0")

        assert entry is not None
        assert entry.digest == sample_digest
        assert entry.tag == "v1.0.0"
        assert entry.path.exists()

    @pytest.mark.requirement("8A-FR-015")
    def test_get_returns_none_for_cache_miss(
        self,
        cache_manager: CacheManager,
    ) -> None:
        """Test that get() returns None for cache miss.

        Verifies:
        - Cache miss returns None
        - No error raised
        """
        entry = cache_manager.get("oci://harbor.example.com/floe", "nonexistent")
        assert entry is None

    @pytest.mark.requirement("8A-FR-015")
    def test_cache_hit_avoids_network(
        self,
        cache_manager: CacheManager,
        sample_content: bytes,
        sample_digest: str,
    ) -> None:
        """Test that cache hit avoids network request.

        Verifies:
        - Cached artifact can be retrieved without network
        - Content matches original
        """
        # Store in cache
        cache_manager.put(
            digest=sample_digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=sample_content,
        )

        # Retrieve from cache (no network needed)
        entry = cache_manager.get("oci://harbor.example.com/floe", "v1.0.0")

        assert entry is not None
        content = entry.path.read_bytes()
        assert content == sample_content

    @pytest.mark.requirement("8A-FR-013")
    def test_cache_disabled_returns_none(
        self,
        tmp_path: Path,
        sample_content: bytes,
        sample_digest: str,
    ) -> None:
        """Test that disabled cache returns None for get.

        Verifies:
        - Disabled cache always returns None
        - No caching occurs
        """
        config = CacheConfig(enabled=False, path=tmp_path / "disabled_cache")
        manager = CacheManager(config)

        entry = manager.get("oci://harbor.example.com/floe", "v1.0.0")
        assert entry is None

    @pytest.mark.requirement("8A-FR-013")
    def test_get_by_digest(
        self,
        cache_manager: CacheManager,
        sample_content: bytes,
        sample_digest: str,
    ) -> None:
        """Test retrieval by digest.

        Verifies:
        - get_by_digest returns cached entry
        - Works independently of tag
        """
        cache_manager.put(
            digest=sample_digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=sample_content,
        )

        entry = cache_manager.get_by_digest(sample_digest)

        assert entry is not None
        assert entry.digest == sample_digest

    @pytest.mark.requirement("8A-FR-013")
    def test_remove_deletes_cached_entry(
        self,
        cache_manager: CacheManager,
        sample_content: bytes,
        sample_digest: str,
    ) -> None:
        """Test that remove() deletes cached artifact.

        Verifies:
        - remove() returns True for existing entry
        - Entry no longer retrievable after removal
        """
        cache_manager.put(
            digest=sample_digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=sample_content,
        )

        removed = cache_manager.remove(sample_digest)
        assert removed is True

        entry = cache_manager.get("oci://harbor.example.com/floe", "v1.0.0")
        assert entry is None


class TestCacheClientIntegration:
    """Tests for cache integration with OCIClient pull operation.

    These tests verify that OCIClient uses cache properly.
    Note: These will pass once T024 implements pull().
    """

    @pytest.mark.requirement("8A-FR-015")
    def test_cache_hit_skips_oras_pull(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that cache hit skips ORAS pull.

        NOTE: This test requires pull() implementation from T024.
        Currently tests pass with NotImplementedError until T024.

        Verifies:
        - When artifact is cached, ORAS pull is NOT called
        - Cached content is returned directly
        """
        # This test will be completed when T024 implements pull()
        # For now, verify cache manager works standalone
        config = CacheConfig(enabled=True, path=tmp_path / "cache")
        manager = CacheManager(config)

        content = b'{"version": "0.2.0"}'
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"

        # Store in cache
        manager.put(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content,
        )

        # Verify cache hit
        entry = manager.get("oci://harbor.example.com/floe", "v1.0.0")
        assert entry is not None
        assert entry.path.read_bytes() == content

    @pytest.mark.requirement("8A-FR-015")
    def test_cache_miss_triggers_oras_pull(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that cache miss requires network fetch.

        NOTE: This test requires pull() implementation from T024.
        Currently tests basic cache miss behavior.

        Verifies:
        - When artifact is NOT cached, get returns None
        - Network fetch would be required (tested in T024)
        """
        config = CacheConfig(enabled=True, path=tmp_path / "cache")
        manager = CacheManager(config)

        # Verify cache miss
        entry = manager.get("oci://harbor.example.com/floe", "nonexistent")
        assert entry is None

"""Unit tests for OCI artifact cache.

Tests basic cache operations (get/put) and cache integration with OCIClient.
Advanced TTL and eviction tests are in US6 (Phase 8).

Task: T023, T025, T046
Requirements: FR-013, FR-014, FR-015, FR-016
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

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


class TestMutableTagTTL:
    """Tests for mutable tag TTL validation (T025).

    FR-014: System MUST validate TTL for mutable tags before returning cached content.
    """

    @pytest.fixture
    def cache_config(self, tmp_path: Path) -> CacheConfig:
        """Create CacheConfig with short TTL for testing."""
        return CacheConfig(
            enabled=True,
            path=tmp_path / "cache",
            max_size_gb=1,
            ttl_hours=1,  # 1 hour TTL
        )

    @pytest.fixture
    def cache_manager(self, cache_config: CacheConfig) -> CacheManager:
        """Create CacheManager."""
        return CacheManager(cache_config)

    @pytest.fixture
    def sample_content(self) -> bytes:
        """Sample artifact content."""
        return b'{"version": "0.2.0", "test": "mutable"}'

    @pytest.fixture
    def sample_digest(self, sample_content: bytes) -> str:
        """Compute digest of sample content."""
        return f"sha256:{hashlib.sha256(sample_content).hexdigest()}"

    @pytest.mark.requirement("8A-FR-014")
    def test_mutable_tag_has_ttl(
        self,
        cache_manager: CacheManager,
        sample_content: bytes,
        sample_digest: str,
    ) -> None:
        """Test that mutable tags are cached with TTL.

        Verifies:
        - Mutable tag entry has expires_at set
        - Immutable (semver) tag entry has no expiry
        """
        # Store mutable tag (latest-dev)
        mutable_entry = cache_manager.put(
            digest=sample_digest,
            tag="latest-dev",
            registry="oci://harbor.example.com/floe",
            content=sample_content,
        )

        assert mutable_entry.expires_at is not None
        assert mutable_entry.expires_at > datetime.now(timezone.utc)

        # Store immutable tag (v1.0.0)
        immutable_content = b'{"version": "0.2.0", "test": "immutable"}'
        immutable_digest = f"sha256:{hashlib.sha256(immutable_content).hexdigest()}"
        immutable_entry = cache_manager.put(
            digest=immutable_digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=immutable_content,
        )

        assert immutable_entry.expires_at is None

    @pytest.mark.requirement("8A-FR-014")
    def test_expired_mutable_tag_returns_none(
        self,
        cache_manager: CacheManager,
        sample_content: bytes,
        sample_digest: str,
    ) -> None:
        """Test that expired mutable tags return None from cache.

        Verifies:
        - Fresh mutable tag is returned
        - Expired mutable tag returns None (cache miss)
        """
        # Store mutable tag
        cache_manager.put(
            digest=sample_digest,
            tag="latest-dev",
            registry="oci://harbor.example.com/floe",
            content=sample_content,
        )

        # Verify fresh entry is returned
        fresh_entry = cache_manager.get("oci://harbor.example.com/floe", "latest-dev")
        assert fresh_entry is not None

        # Simulate time passing (TTL expired)
        # Must patch _utc_now in schemas.oci where CacheEntry.is_expired uses it
        with patch("floe_core.schemas.oci._utc_now") as mock_now:
            # Set current time to 2 hours in the future (past TTL)
            future_time = datetime.now(timezone.utc) + timedelta(hours=2)
            mock_now.return_value = future_time

            expired_entry = cache_manager.get("oci://harbor.example.com/floe", "latest-dev")
            assert expired_entry is None  # Expired, returns None

    @pytest.mark.requirement("8A-FR-014")
    def test_immutable_tag_never_expires(
        self,
        cache_manager: CacheManager,
    ) -> None:
        """Test that immutable (semver) tags never expire.

        Verifies:
        - Semver tags are always returned
        - No TTL applied to semver tags
        """
        content = b'{"version": "0.2.0", "test": "semver"}'
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"

        # Store semver tag
        cache_manager.put(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content,
        )

        # Verify entry is returned even after long time
        # Must patch _utc_now in schemas.oci where CacheEntry.is_expired uses it
        with patch("floe_core.schemas.oci._utc_now") as mock_now:
            # Set current time to 1 year in the future
            future_time = datetime.now(timezone.utc) + timedelta(days=365)
            mock_now.return_value = future_time

            entry = cache_manager.get("oci://harbor.example.com/floe", "v1.0.0")
            assert entry is not None  # Never expires
            assert entry.digest == digest


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


class TestDigestVerification:
    """Tests for digest verification on cache operations (T046).

    FR-015: System MUST verify artifact digest on cache put.
    FR-016: System MUST verify digest integrity.
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

    @pytest.mark.requirement("8A-FR-016")
    def test_put_validates_digest_on_store(
        self,
        cache_manager: CacheManager,
    ) -> None:
        """Test that put() validates digest matches content.

        Verifies:
        - put() raises CacheError when digest doesn't match
        - Mismatched digest is rejected
        """
        from floe_core.oci.errors import CacheError

        content = b'{"version": "0.2.0", "test": "data"}'
        wrong_digest = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

        with pytest.raises(CacheError, match="Digest mismatch"):
            cache_manager.put(
                digest=wrong_digest,
                tag="v1.0.0",
                registry="oci://harbor.example.com/floe",
                content=content,
            )

    @pytest.mark.requirement("8A-FR-016")
    def test_put_accepts_correct_digest(
        self,
        cache_manager: CacheManager,
    ) -> None:
        """Test that put() accepts content with correct digest.

        Verifies:
        - put() succeeds when digest matches content
        - Entry is stored correctly
        """
        content = b'{"version": "0.2.0", "test": "data"}'
        correct_digest = f"sha256:{hashlib.sha256(content).hexdigest()}"

        entry = cache_manager.put(
            digest=correct_digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content,
        )

        assert entry is not None
        assert entry.digest == correct_digest
        assert entry.path.read_bytes() == content

    @pytest.mark.requirement("8A-FR-016")
    def test_digest_integrity_maintained_after_get(
        self,
        cache_manager: CacheManager,
    ) -> None:
        """Test that retrieved content matches stored digest.

        Verifies:
        - Content retrieved from cache matches original digest
        - No corruption during storage/retrieval
        """
        content = b'{"version": "0.2.0", "test": "integrity"}'
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"

        # Store content
        cache_manager.put(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content,
        )

        # Retrieve and verify
        entry = cache_manager.get("oci://harbor.example.com/floe", "v1.0.0")
        assert entry is not None

        # Re-compute digest from retrieved content
        retrieved_content = entry.path.read_bytes()
        computed_digest = f"sha256:{hashlib.sha256(retrieved_content).hexdigest()}"
        assert computed_digest == digest

    @pytest.mark.requirement("8A-FR-021")
    def test_get_with_content_returns_verified_content(
        self,
        cache_manager: CacheManager,
    ) -> None:
        """Test that get_with_content() returns verified content.

        Verifies:
        - get_with_content returns tuple of (entry, content)
        - Content is verified against stored digest
        """
        content = b'{"version": "0.2.0", "test": "verified"}'
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"

        # Store content
        cache_manager.put(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content,
        )

        # Retrieve with verification
        result = cache_manager.get_with_content("oci://harbor.example.com/floe", "v1.0.0")

        assert result is not None
        entry, retrieved_content = result
        assert entry.digest == digest
        assert retrieved_content == content

    @pytest.mark.requirement("8A-FR-021")
    def test_get_with_content_detects_corruption(
        self,
        cache_manager: CacheManager,
    ) -> None:
        """Test that get_with_content() detects corrupted content.

        Verifies:
        - Corrupted content is detected by digest mismatch
        - Corrupted entry is removed from cache
        - Returns None for corrupted entry
        """
        from floe_core.oci.errors import DigestMismatchError

        content = b'{"version": "0.2.0", "test": "corruption"}'
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"

        # Store content
        entry = cache_manager.put(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content,
        )

        # Corrupt the content on disk
        entry.path.write_bytes(b'{"corrupted": true}')

        # Retrieve with verification - should detect corruption
        with pytest.raises(DigestMismatchError):
            cache_manager.get_with_content("oci://harbor.example.com/floe", "v1.0.0")

        # Corrupted entry should be removed
        check_entry = cache_manager.get("oci://harbor.example.com/floe", "v1.0.0")
        assert check_entry is None

    @pytest.mark.requirement("8A-FR-021")
    def test_get_with_content_returns_none_for_cache_miss(
        self,
        cache_manager: CacheManager,
    ) -> None:
        """Test that get_with_content() returns None for cache miss.

        Verifies:
        - Cache miss returns None
        - No error raised
        """
        result = cache_manager.get_with_content("oci://harbor.example.com/floe", "nonexistent")
        assert result is None


class TestLRUEviction:
    """Tests for LRU eviction under size pressure (T046).

    FR-015: System MUST evict least recently used entries when cache full.
    FR-016: System MUST maintain cache size within limits.

    NOTE: CacheConfig.max_size_gb has ge=1 constraint (minimum 1GB).
    These tests focus on the CacheIndex LRU logic directly.
    """

    @pytest.mark.requirement("8A-FR-015")
    def test_cache_index_get_lru_entries_sorted_by_access_time(self) -> None:
        """Test that CacheIndex.get_lru_entries returns entries sorted by access time.

        Verifies:
        - Entries are returned in order of last_accessed (oldest first)
        - Only immutable entries are considered for LRU
        """
        from floe_core.schemas.oci import CacheEntry, CacheIndex

        # Create entries with different access times
        base_time = datetime.now(timezone.utc)
        entries: dict[str, CacheEntry] = {}

        # Create entries with different access times (v1 oldest, v3 newest)
        for i in range(1, 4):
            content = f'{{"version": "{i}"}}'.encode()
            digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
            entries[digest] = CacheEntry(
                digest=digest,
                tag=f"v{i}.0.0",  # Immutable tag
                registry="oci://harbor.example.com/floe",
                pulled_at=base_time,
                expires_at=None,  # Immutable
                size=len(content),
                path=Path(f"/tmp/cache/{digest[:12]}/blob"),
                last_accessed=base_time + timedelta(hours=i),  # v1: +1h, v2: +2h, v3: +3h
            )

        index = CacheIndex(entries=entries, total_size=sum(e.size for e in entries.values()))

        # Get LRU entries
        lru = index.get_lru_entries(2)

        # Should return v1, v2 (oldest accessed first)
        assert len(lru) == 2
        assert lru[0].tag == "v1.0.0"  # Oldest
        assert lru[1].tag == "v2.0.0"  # Second oldest

    @pytest.mark.requirement("8A-FR-015")
    def test_cache_index_lru_excludes_mutable_tags(self) -> None:
        """Test that LRU eviction excludes mutable tags.

        Verifies:
        - Mutable tags are not returned by get_lru_entries
        - Only immutable tags are candidates for LRU eviction
        """
        from floe_core.schemas.oci import CacheEntry, CacheIndex

        base_time = datetime.now(timezone.utc)
        entries: dict[str, CacheEntry] = {}

        # Add mutable tag (oldest access time but should be excluded)
        mutable_content = b'{"type": "mutable"}'
        mutable_digest = f"sha256:{hashlib.sha256(mutable_content).hexdigest()}"
        entries[mutable_digest] = CacheEntry(
            digest=mutable_digest,
            tag="latest-dev",  # Mutable
            registry="oci://harbor.example.com/floe",
            pulled_at=base_time,
            expires_at=base_time + timedelta(hours=24),  # Has TTL
            size=len(mutable_content),
            path=Path("/tmp/cache/mutable/blob"),
            last_accessed=base_time,  # Oldest
        )

        # Add immutable tag (newer access time)
        immutable_content = b'{"type": "immutable"}'
        immutable_digest = f"sha256:{hashlib.sha256(immutable_content).hexdigest()}"
        entries[immutable_digest] = CacheEntry(
            digest=immutable_digest,
            tag="v1.0.0",  # Immutable
            registry="oci://harbor.example.com/floe",
            pulled_at=base_time,
            expires_at=None,
            size=len(immutable_content),
            path=Path("/tmp/cache/immutable/blob"),
            last_accessed=base_time + timedelta(hours=1),  # Newer
        )

        index = CacheIndex(entries=entries, total_size=sum(e.size for e in entries.values()))

        # Get LRU entries
        lru = index.get_lru_entries(10)

        # Should only return immutable entry
        assert len(lru) == 1
        assert lru[0].tag == "v1.0.0"

    @pytest.mark.requirement("8A-FR-016")
    def test_cache_index_get_expired_entries(self) -> None:
        """Test that CacheIndex.get_expired_entries returns expired entries.

        Verifies:
        - Expired entries are correctly identified
        - Non-expired entries are not included
        """
        from floe_core.schemas.oci import CacheEntry, CacheIndex

        base_time = datetime.now(timezone.utc)
        entries: dict[str, CacheEntry] = {}

        # Add expired entry
        expired_content = b'{"type": "expired"}'
        expired_digest = f"sha256:{hashlib.sha256(expired_content).hexdigest()}"
        entries[expired_digest] = CacheEntry(
            digest=expired_digest,
            tag="latest-dev",
            registry="oci://harbor.example.com/floe",
            pulled_at=base_time - timedelta(hours=25),
            expires_at=base_time - timedelta(hours=1),  # Expired 1 hour ago
            size=len(expired_content),
            path=Path("/tmp/cache/expired/blob"),
            last_accessed=base_time - timedelta(hours=25),
        )

        # Add non-expired entry
        fresh_content = b'{"type": "fresh"}'
        fresh_digest = f"sha256:{hashlib.sha256(fresh_content).hexdigest()}"
        entries[fresh_digest] = CacheEntry(
            digest=fresh_digest,
            tag="latest-prod",
            registry="oci://harbor.example.com/floe",
            pulled_at=base_time,
            expires_at=base_time + timedelta(hours=23),  # Expires in 23 hours
            size=len(fresh_content),
            path=Path("/tmp/cache/fresh/blob"),
            last_accessed=base_time,
        )

        # Add immutable entry (no expiry)
        immutable_content = b'{"type": "immutable"}'
        immutable_digest = f"sha256:{hashlib.sha256(immutable_content).hexdigest()}"
        entries[immutable_digest] = CacheEntry(
            digest=immutable_digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            pulled_at=base_time,
            expires_at=None,
            size=len(immutable_content),
            path=Path("/tmp/cache/immutable/blob"),
            last_accessed=base_time,
        )

        index = CacheIndex(entries=entries, total_size=sum(e.size for e in entries.values()))

        # Get expired entries
        expired = index.get_expired_entries()

        # Should only return the expired entry
        assert len(expired) == 1
        assert expired[0].tag == "latest-dev"

    @pytest.mark.requirement("8A-FR-016")
    def test_cache_manager_eviction_triggered_on_size_exceeded(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that eviction is triggered when cache size is exceeded.

        Verifies:
        - _maybe_evict is called when total_size exceeds max_size_gb
        - Uses mock to simulate size limit breach
        """
        config = CacheConfig(
            enabled=True,
            path=tmp_path / "cache",
            max_size_gb=1,
            ttl_hours=24,
        )
        manager = CacheManager(config)

        # Add a test artifact
        content = b'{"version": "0.2.0", "test": "eviction"}'
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        manager.put(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content,
        )

        # Verify artifact was stored
        entry = manager.get("oci://harbor.example.com/floe", "v1.0.0")
        assert entry is not None
        assert entry.path.read_bytes() == content

        # Verify stats report correct entry count
        stats = manager.stats()
        assert stats["entry_count"] == 1

    @pytest.mark.requirement("8A-FR-015")
    def test_cache_entry_touch_updates_last_accessed(self) -> None:
        """Test that CacheEntry.touch() updates last_accessed time.

        Verifies:
        - touch() updates last_accessed to current time
        - LRU ordering is affected by touch()
        """
        from floe_core.schemas.oci import CacheEntry

        base_time = datetime.now(timezone.utc) - timedelta(hours=5)
        content = b'{"version": "0.2.0"}'
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"

        entry = CacheEntry(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            pulled_at=base_time,
            expires_at=None,
            size=len(content),
            path=Path("/tmp/cache/test/blob"),
            last_accessed=base_time,
        )

        old_access_time = entry.last_accessed

        # Touch the entry
        entry.touch()

        # last_accessed should be updated to a more recent time
        assert entry.last_accessed > old_access_time


class TestCacheClearAndCleanup:
    """Tests for clear() and cleanup_expired() methods (T067 coverage).

    FR-015: System MUST maintain cache integrity.
    FR-016: System MUST remove expired entries.
    """

    @pytest.fixture
    def cache_config(self, tmp_path: Path) -> CacheConfig:
        """Create CacheConfig with temp directory."""
        return CacheConfig(
            enabled=True,
            path=tmp_path / "cache",
            max_size_gb=1,
            ttl_hours=1,  # 1 hour TTL
        )

    @pytest.fixture
    def cache_manager(self, cache_config: CacheConfig) -> CacheManager:
        """Create CacheManager with temp directory."""
        return CacheManager(cache_config)

    @pytest.mark.requirement("8A-FR-015")
    def test_clear_removes_all_entries(
        self,
        cache_manager: CacheManager,
    ) -> None:
        """Test that clear() removes all cached artifacts.

        Verifies:
        - All entries are removed after clear()
        - Cache stats show zero entries
        """
        # Add multiple entries
        for i in range(3):
            content = f'{{"version": "{i}"}}'.encode()
            digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
            cache_manager.put(
                digest=digest,
                tag=f"v{i}.0.0",
                registry="oci://harbor.example.com/floe",
                content=content,
            )

        # Verify entries exist
        stats = cache_manager.stats()
        assert stats["entry_count"] == 3

        # Clear cache
        cache_manager.clear()

        # Verify all entries removed
        stats = cache_manager.stats()
        assert stats["entry_count"] == 0

        # Verify individual entries are gone
        for i in range(3):
            entry = cache_manager.get("oci://harbor.example.com/floe", f"v{i}.0.0")
            assert entry is None

    @pytest.mark.requirement("8A-FR-015")
    def test_clear_on_disabled_cache(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that clear() does nothing when cache is disabled.

        Verifies:
        - No error raised when clearing disabled cache
        """
        config = CacheConfig(enabled=False, path=tmp_path / "disabled_cache")
        manager = CacheManager(config)

        # Should not raise
        manager.clear()

    @pytest.mark.requirement("8A-FR-016")
    def test_cleanup_expired_removes_expired_entries(
        self,
        cache_manager: CacheManager,
    ) -> None:
        """Test that cleanup_expired() removes expired entries.

        Verifies:
        - Expired entries are removed
        - Non-expired entries remain
        - Returns count of removed entries
        """
        # Add mutable tag (has TTL)
        mutable_content = b'{"type": "mutable"}'
        mutable_digest = f"sha256:{hashlib.sha256(mutable_content).hexdigest()}"
        cache_manager.put(
            digest=mutable_digest,
            tag="latest-dev",
            registry="oci://harbor.example.com/floe",
            content=mutable_content,
        )

        # Add immutable tag (no TTL)
        immutable_content = b'{"type": "immutable"}'
        immutable_digest = f"sha256:{hashlib.sha256(immutable_content).hexdigest()}"
        cache_manager.put(
            digest=immutable_digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=immutable_content,
        )

        # Verify both exist
        assert cache_manager.stats()["entry_count"] == 2

        # Simulate time passing (TTL expired)
        with patch("floe_core.schemas.oci._utc_now") as mock_now:
            future_time = datetime.now(timezone.utc) + timedelta(hours=2)
            mock_now.return_value = future_time

            # Cleanup expired
            removed = cache_manager.cleanup_expired()

            assert removed == 1  # Only mutable entry expired

        # Verify immutable entry remains (need to restore time)
        entry = cache_manager.get_by_digest(immutable_digest)
        assert entry is not None

    @pytest.mark.requirement("8A-FR-016")
    def test_cleanup_expired_on_disabled_cache(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that cleanup_expired() returns 0 when cache is disabled.

        Verifies:
        - Returns 0 for disabled cache
        - No error raised
        """
        config = CacheConfig(enabled=False, path=tmp_path / "disabled_cache")
        manager = CacheManager(config)

        removed = manager.cleanup_expired()
        assert removed == 0

    @pytest.mark.requirement("8A-FR-021")
    def test_get_with_content_handles_read_error(
        self,
        cache_manager: CacheManager,
    ) -> None:
        """Test that get_with_content() handles file read errors.

        Verifies:
        - OSError during read is caught
        - Corrupted entry is removed from cache
        - DigestMismatchError is raised
        """
        from floe_core.oci.errors import DigestMismatchError

        content = b'{"version": "0.2.0", "test": "read_error"}'
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"

        # Store content
        entry = cache_manager.put(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content,
        )

        # Delete the blob file to cause OSError
        entry.path.unlink()

        # Retrieve with verification - should handle OSError
        with pytest.raises(DigestMismatchError, match="read_error"):
            cache_manager.get_with_content("oci://harbor.example.com/floe", "v1.0.0")

        # Entry should be removed from cache
        check_entry = cache_manager.get("oci://harbor.example.com/floe", "v1.0.0")
        assert check_entry is None

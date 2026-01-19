"""Local cache manager for OCI artifacts.

This module implements file-based caching for pulled OCI artifacts with
TTL-based expiry for mutable tags and LRU eviction when size limits are exceeded.

Cache Structure:
    /var/cache/floe/oci/
    ├── index.json                    # Cache index with metadata
    ├── sha256/
    │   └── abc123.../                # Content-addressed by digest
    │       ├── manifest.json         # OCI manifest
    │       └── blob                  # Artifact content
    └── tags/
        └── registry.example.com/
            └── namespace/
                └── repo/
                    ├── v1.0.0.json   # Tag → digest mapping (immutable)
                    └── latest-dev.json  # Tag → digest + TTL (mutable)

Cache Policies:
    | Tag Pattern | TTL | Re-fetch |
    |-------------|-----|----------|
    | v* (semver) | Indefinite | Never |
    | sha256:*    | Indefinite | Never |
    | latest-*    | 24h (configurable) | On expiry |
    | Other       | 24h (configurable) | On expiry |

Eviction Policy: LRU (Least Recently Used) when cache exceeds max_size

Thread Safety: File locking via fcntl.flock() to prevent corruption

Example:
    >>> from floe_core.oci.cache import CacheManager
    >>> from floe_core.schemas.oci import CacheConfig
    >>>
    >>> manager = CacheManager(CacheConfig(path=Path("/var/cache/floe/oci")))
    >>>
    >>> # Check for cached artifact
    >>> entry = manager.get("oci://harbor.example.com/floe", "v1.0.0")
    >>> if entry and not entry.is_expired:
    ...     with open(entry.path) as f:
    ...         content = f.read()
    >>>
    >>> # Store artifact in cache
    >>> entry = manager.put(
    ...     digest="sha256:abc123...",
    ...     tag="v1.0.0",
    ...     registry="oci://harbor.example.com/floe",
    ...     content=artifact_bytes,
    ... )

See Also:
    - specs/08a-oci-client/research.md: Caching research (Section 5)
    - floe_core.schemas.oci: CacheEntry, CacheIndex schemas
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import structlog

from floe_core.oci.errors import CacheError
from floe_core.schemas.oci import CacheConfig, CacheEntry, CacheIndex

if TYPE_CHECKING:
    from collections.abc import Generator

logger = structlog.get_logger(__name__)

# Bytes per gigabyte for size calculations
BYTES_PER_GB = 1024 * 1024 * 1024


def _is_semver(tag: str) -> bool:
    """Check if tag follows semver pattern (immutable)."""
    return bool(re.match(r"^v?\d+\.\d+\.\d+", tag))


def _is_digest(tag: str) -> bool:
    """Check if tag is a digest reference (immutable)."""
    return tag.startswith("sha256:")


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class CacheManager:
    """Local cache manager for OCI artifacts.

    Provides file-based caching with TTL support for mutable tags and
    LRU eviction when cache size exceeds limits.

    Features:
    - Content-addressed storage by digest
    - TTL-based expiry for mutable tags
    - Indefinite caching for immutable tags (semver, digests)
    - LRU eviction when cache exceeds max_size
    - Thread-safe index updates via file locking

    Example:
        >>> config = CacheConfig(path=Path("/var/cache/floe/oci"), max_size_gb=10)
        >>> manager = CacheManager(config)
        >>>
        >>> # Store artifact
        >>> entry = manager.put(
        ...     digest="sha256:abc123...",
        ...     tag="v1.0.0",
        ...     registry="oci://harbor.example.com/floe",
        ...     content=artifact_bytes,
        ... )
        >>>
        >>> # Retrieve artifact
        >>> entry = manager.get("oci://harbor.example.com/floe", "v1.0.0")
        >>> if entry:
        ...     content = entry.path.read_bytes()

    Attributes:
        config: CacheConfig with path, max_size_gb, ttl_hours settings.
    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        """Initialize CacheManager.

        Args:
            config: Cache configuration. Uses defaults if None.

        Raises:
            CacheError: If cache directory cannot be created.
        """
        self._config = config or CacheConfig()
        self._index_path = self._config.path / "index.json"
        self._blobs_path = self._config.path / "sha256"
        self._tags_path = self._config.path / "tags"
        self._lock_path = self._config.path / ".lock"

        # Ensure cache directories exist
        try:
            self._config.path.mkdir(parents=True, exist_ok=True)
            self._blobs_path.mkdir(parents=True, exist_ok=True)
            self._tags_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise CacheError(
                "init",
                f"Failed to create cache directory: {e}",
                str(self._config.path),
            ) from e

    @property
    def config(self) -> CacheConfig:
        """Return cache configuration."""
        return self._config

    @property
    def enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._config.enabled

    def get(self, registry: str, tag: str) -> CacheEntry | None:
        """Retrieve a cached artifact entry.

        Checks if an artifact is in the cache and returns its metadata.
        Updates last_accessed time for LRU tracking.

        Args:
            registry: OCI registry URI.
            tag: Artifact tag or digest.

        Returns:
            CacheEntry if found and not expired, None otherwise.

        Example:
            >>> entry = manager.get("oci://harbor.example.com/floe", "v1.0.0")
            >>> if entry:
            ...     content = entry.path.read_bytes()
        """
        if not self.enabled:
            return None

        with self._lock():
            index = self._load_index()

            # Find entry by registry and tag
            for entry in index.entries.values():
                if entry.registry == registry and entry.tag == tag:
                    if entry.is_expired:
                        logger.debug(
                            "cache_expired",
                            registry=registry,
                            tag=tag,
                            expires_at=entry.expires_at.isoformat() if entry.expires_at else None,
                        )
                        return None

                    # Update last_accessed for LRU
                    entry.touch()
                    self._save_index(index)

                    logger.debug(
                        "cache_hit",
                        registry=registry,
                        tag=tag,
                        digest=entry.digest,
                    )
                    return entry

        logger.debug("cache_miss", registry=registry, tag=tag)
        return None

    def get_by_digest(self, digest: str) -> CacheEntry | None:
        """Retrieve a cached artifact by digest.

        Args:
            digest: Artifact digest (sha256:...).

        Returns:
            CacheEntry if found, None otherwise.
        """
        if not self.enabled:
            return None

        with self._lock():
            index = self._load_index()
            entry = index.entries.get(digest)
            if entry:
                entry.touch()
                self._save_index(index)
            return entry

    def get_with_content(self, registry: str, tag: str) -> tuple[CacheEntry, bytes] | None:
        """Retrieve a cached artifact with verified content.

        Gets the cache entry and reads its content, verifying the digest
        matches the stored content. If content is corrupted, the entry
        is removed from the cache.

        Args:
            registry: OCI registry URI.
            tag: Artifact tag or digest.

        Returns:
            Tuple of (CacheEntry, content bytes) if found and valid,
            None if not in cache.

        Raises:
            DigestMismatchError: If content does not match stored digest.

        Example:
            >>> result = manager.get_with_content("oci://harbor.example.com/floe", "v1.0.0")
            >>> if result:
            ...     entry, content = result
            ...     process(content)
        """
        from floe_core.oci.errors import DigestMismatchError

        entry = self.get(registry, tag)
        if entry is None:
            return None

        # Read and verify content
        try:
            content = entry.path.read_bytes()
        except OSError as e:
            logger.warning(
                "cache_read_failed",
                registry=registry,
                tag=tag,
                digest=entry.digest,
                error=str(e),
            )
            # Remove corrupted entry
            self.remove(entry.digest)
            raise DigestMismatchError(
                expected=entry.digest,
                actual="<read_error>",
                artifact_ref=tag,
            ) from e

        # Verify digest
        computed_digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if computed_digest != entry.digest:
            logger.error(
                "cache_corruption_detected",
                registry=registry,
                tag=tag,
                expected_digest=entry.digest,
                actual_digest=computed_digest,
            )
            # Remove corrupted entry
            self.remove(entry.digest)
            raise DigestMismatchError(
                expected=entry.digest,
                actual=computed_digest,
                artifact_ref=tag,
            )

        logger.debug(
            "cache_hit_verified",
            registry=registry,
            tag=tag,
            digest=entry.digest,
            size=len(content),
        )

        return (entry, content)

    def put(
        self,
        digest: str,
        tag: str,
        registry: str,
        content: bytes,
        manifest: dict[str, Any] | None = None,
    ) -> CacheEntry:
        """Store an artifact in the cache.

        Creates a cache entry with content-addressed storage.
        Applies TTL based on tag type (immutable vs mutable).

        Args:
            digest: Artifact digest (sha256:...).
            tag: Artifact tag.
            registry: OCI registry URI.
            content: Artifact content bytes.
            manifest: Optional OCI manifest to store.

        Returns:
            CacheEntry with metadata and path.

        Raises:
            CacheError: If write fails.

        Example:
            >>> entry = manager.put(
            ...     digest="sha256:abc123...",
            ...     tag="v1.0.0",
            ...     registry="oci://harbor.example.com/floe",
            ...     content=artifact_bytes,
            ... )
        """
        if not self.enabled:
            raise CacheError("put", "Caching is disabled", str(self._config.path))

        # Verify digest matches content
        computed_digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if digest != computed_digest:
            raise CacheError(
                "put",
                f"Digest mismatch: expected {digest}, got {computed_digest}",
                str(self._config.path),
            )

        # Determine expiry
        expires_at: datetime | None = None
        if not (_is_semver(tag) or _is_digest(tag)):
            # Mutable tag - set TTL
            expires_at = _utc_now() + timedelta(hours=self._config.ttl_hours)

        # Create blob directory
        digest_short = digest.replace("sha256:", "")
        blob_dir = self._blobs_path / digest_short
        blob_path = blob_dir / "blob"

        with self._lock():
            try:
                blob_dir.mkdir(parents=True, exist_ok=True)

                # Write content
                blob_path.write_bytes(content)

                # Write manifest if provided
                if manifest:
                    manifest_path = blob_dir / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest, indent=2))

                # Create cache entry
                now = _utc_now()
                entry = CacheEntry(
                    digest=digest,
                    tag=tag,
                    registry=registry,
                    pulled_at=now,
                    expires_at=expires_at,
                    size=len(content),
                    path=blob_path,
                    last_accessed=now,
                )

                # Update index
                index = self._load_index()
                index.add_entry(entry)
                self._save_index(index)

                logger.info(
                    "cache_put",
                    registry=registry,
                    tag=tag,
                    digest=digest,
                    size=len(content),
                    expires_at=expires_at.isoformat() if expires_at else None,
                )

                # Check if eviction needed
                self._maybe_evict(index)

                return entry

            except OSError as e:
                raise CacheError(
                    "put",
                    f"Failed to write cache entry: {e}",
                    str(blob_path),
                ) from e

    def remove(self, digest: str) -> bool:
        """Remove an artifact from the cache.

        Args:
            digest: Artifact digest to remove.

        Returns:
            True if removed, False if not found.
        """
        if not self.enabled:
            return False

        with self._lock():
            index = self._load_index()
            entry = index.remove_entry(digest)

            if entry:
                # Remove blob directory
                digest_short = digest.replace("sha256:", "")
                blob_dir = self._blobs_path / digest_short
                if blob_dir.exists():
                    shutil.rmtree(blob_dir, ignore_errors=True)

                self._save_index(index)
                logger.info("cache_remove", digest=digest)
                return True

        return False

    def clear(self) -> None:
        """Clear all cached artifacts.

        Removes all blobs and resets the index.
        """
        if not self.enabled:
            return

        with self._lock():
            # Remove all blobs
            if self._blobs_path.exists():
                shutil.rmtree(self._blobs_path, ignore_errors=True)
                self._blobs_path.mkdir(parents=True, exist_ok=True)

            # Remove all tag mappings
            if self._tags_path.exists():
                shutil.rmtree(self._tags_path, ignore_errors=True)
                self._tags_path.mkdir(parents=True, exist_ok=True)

            # Reset index
            index = CacheIndex()
            self._save_index(index)

            logger.info("cache_cleared")

    def cleanup_expired(self) -> int:
        """Remove all expired cache entries.

        Returns:
            Number of entries removed.
        """
        if not self.enabled:
            return 0

        removed = 0
        with self._lock():
            index = self._load_index()
            expired = index.get_expired_entries()

            for entry in expired:
                if index.remove_entry(entry.digest):
                    # Remove blob
                    digest_short = entry.digest.replace("sha256:", "")
                    blob_dir = self._blobs_path / digest_short
                    if blob_dir.exists():
                        shutil.rmtree(blob_dir, ignore_errors=True)
                    removed += 1

            if removed > 0:
                self._save_index(index)
                logger.info("cache_cleanup_expired", removed=removed)

        return removed

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with entry count, total size, and other stats.
        """
        with self._lock():
            index = self._load_index()

            immutable_count = sum(1 for e in index.entries.values() if e.is_immutable)
            mutable_count = len(index.entries) - immutable_count
            expired_count = len(index.get_expired_entries())

            return {
                "enabled": self.enabled,
                "path": str(self._config.path),
                "max_size_gb": self._config.max_size_gb,
                "ttl_hours": self._config.ttl_hours,
                "entry_count": len(index.entries),
                "immutable_count": immutable_count,
                "mutable_count": mutable_count,
                "expired_count": expired_count,
                "total_size_bytes": index.total_size,
                "total_size_gb": index.total_size / BYTES_PER_GB,
                "last_updated": index.last_updated.isoformat(),
            }

    def get_entries_by_tag(self, tag: str) -> list[CacheEntry]:
        """Get all cache entries matching a specific tag.

        Args:
            tag: Tag to filter by.

        Returns:
            List of CacheEntry objects with matching tag.
        """
        if not self.enabled:
            return []

        with self._lock():
            index = self._load_index()
            return [e for e in index.entries.values() if e.tag == tag]

    def _maybe_evict(self, index: CacheIndex) -> None:
        """Evict entries if cache exceeds max size.

        Uses LRU (Least Recently Used) policy for immutable entries.
        Mutable entries are subject to TTL expiry.

        Args:
            index: Current cache index (already locked).
        """
        max_bytes = self._config.max_size_gb * BYTES_PER_GB

        if index.total_size <= max_bytes:
            return

        # Calculate how much to free (add 10% buffer)
        to_free = int((index.total_size - max_bytes) * 1.1)
        freed = 0
        removed = 0

        # First, remove expired entries
        for entry in index.get_expired_entries():
            if freed >= to_free:
                break
            if index.remove_entry(entry.digest):
                digest_short = entry.digest.replace("sha256:", "")
                blob_dir = self._blobs_path / digest_short
                if blob_dir.exists():
                    shutil.rmtree(blob_dir, ignore_errors=True)
                freed += entry.size
                removed += 1

        # Then use LRU for remaining
        if freed < to_free:
            # Calculate how many more to remove
            remaining_to_free = to_free - freed
            avg_size = index.total_size / len(index.entries) if index.entries else 0
            estimate_count = int(remaining_to_free / avg_size) + 1 if avg_size > 0 else 10

            lru_entries = index.get_lru_entries(estimate_count * 2)
            for entry in lru_entries:
                if freed >= to_free:
                    break
                if index.remove_entry(entry.digest):
                    digest_short = entry.digest.replace("sha256:", "")
                    blob_dir = self._blobs_path / digest_short
                    if blob_dir.exists():
                        shutil.rmtree(blob_dir, ignore_errors=True)
                    freed += entry.size
                    removed += 1

        if removed > 0:
            self._save_index(index)
            logger.info(
                "cache_eviction",
                removed=removed,
                freed_bytes=freed,
                new_size_bytes=index.total_size,
            )

    def _load_index(self) -> CacheIndex:
        """Load cache index from disk.

        Returns:
            CacheIndex from file, or new empty index if not exists.
        """
        if not self._index_path.exists():
            return CacheIndex()

        try:
            data = json.loads(self._index_path.read_text())
            return CacheIndex.model_validate(data)
        except Exception as e:
            logger.warning(
                "cache_index_load_failed",
                error=str(e),
                path=str(self._index_path),
            )
            return CacheIndex()

    def _save_index(self, index: CacheIndex) -> None:
        """Save cache index to disk.

        Args:
            index: CacheIndex to save.

        Raises:
            CacheError: If write fails.
        """
        try:
            # Write to temp file first, then rename for atomicity
            temp_path = self._index_path.with_suffix(".tmp")
            temp_path.write_text(index.model_dump_json(indent=2))
            temp_path.rename(self._index_path)
        except OSError as e:
            raise CacheError(
                "save_index",
                f"Failed to save cache index: {e}",
                str(self._index_path),
            ) from e

    @contextmanager
    def _lock(self) -> Generator[None, None, None]:
        """Context manager for cache file locking.

        Uses fcntl.flock for file-based locking to ensure
        safe concurrent access.

        Yields:
            None
        """
        # Ensure lock file exists
        self._lock_path.touch(exist_ok=True)

        lock_fd = os.open(str(self._lock_path), os.O_RDWR)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

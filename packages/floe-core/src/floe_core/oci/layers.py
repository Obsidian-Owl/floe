"""OCI layer operations and content management helpers.

This module provides helper classes and functions for OCI registry operations,
including content handling, tag management, and pull/push operation support.

Extracted from client.py as part of Epic 12B US4 (God Module Decomposition)
to reduce the file from 1389 lines to focused, single-responsibility modules.

Key Components:
    TagClassifier: Determines tag mutability (semver vs mutable patterns)
    PullOperations: Helper class for pull operation flow (cache, extraction)
    PushOperations: Helper class for push operation flow (immutability)
    URIParser: Utilities for OCI URI parsing and target reference building

Requirements Covered:
    - FR-004: Split oci/client.py into focused modules each ≤400 lines
    - 12B-ARCH-004: SRP decomposition of OCI client

Example:
    >>> from floe_core.oci.layers import TagClassifier, PullOperations
    >>>
    >>> classifier = TagClassifier()
    >>> classifier.is_immutable("v1.0.0")
    True
    >>> classifier.is_immutable("latest-dev")
    False
    >>>
    >>> ops = PullOperations()
    >>> artifacts_path = ops.find_artifacts_file(pulled_files, tmpdir)
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from floe_core.oci.errors import OCIError

if TYPE_CHECKING:
    from floe_core.oci.cache import CacheManager
    from floe_core.oci.metrics import OCIMetrics
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts

logger = structlog.get_logger(__name__)


# =============================================================================
# Tag Classification Constants
# =============================================================================

SEMVER_PATTERN = re.compile(r"^v?\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$")
"""Pattern matching semantic versioning tags (e.g., v1.0.0, 1.2.3-alpha)."""

MUTABLE_TAG_PATTERNS = [
    re.compile(r"^latest(-.*)?$"),  # latest, latest-dev, latest-staging
    re.compile(r"^dev(-.*)?$"),  # dev, dev-branch
    re.compile(r"^snapshot(-.*)?$"),  # snapshot, snapshot-123
]
"""Patterns for mutable tags that can be overwritten."""


# =============================================================================
# Tag Classification
# =============================================================================


class TagClassifier:
    """Classifies OCI tags as immutable (semver) or mutable.

    Semver tags (v1.0.0, 1.2.3-alpha) are considered immutable and should
    not be overwritten once pushed. Mutable patterns (latest-*, dev-*,
    snapshot-*) can be safely overwritten.

    This class provides a centralized point for tag classification logic,
    supporting immutability enforcement in push operations.

    Example:
        >>> classifier = TagClassifier()
        >>> classifier.is_immutable("v1.0.0")
        True
        >>> classifier.is_immutable("latest")
        False
        >>> classifier.is_immutable("dev-feature-branch")
        False
        >>> classifier.is_immutable("custom-tag")  # Default: immutable
        True
    """

    def __init__(
        self,
        *,
        semver_pattern: re.Pattern[str] | None = None,
        mutable_patterns: list[re.Pattern[str]] | None = None,
    ) -> None:
        """Initialize TagClassifier.

        Args:
            semver_pattern: Optional custom semver pattern. Defaults to
                standard semver (v1.0.0, 1.2.3-alpha+build).
            mutable_patterns: Optional custom mutable tag patterns.
                Defaults to latest-*, dev-*, snapshot-*.
        """
        self._semver_pattern = semver_pattern or SEMVER_PATTERN
        self._mutable_patterns = mutable_patterns or MUTABLE_TAG_PATTERNS

    def is_immutable(self, tag: str) -> bool:
        """Check if a tag is considered immutable.

        Semver tags (v1.0.0, 1.2.3-alpha) are immutable and cannot be
        overwritten once pushed.

        Mutable patterns (latest-*, dev-*, snapshot-*) can be overwritten.

        Unknown tags default to immutable (safe default).

        Args:
            tag: Tag to check.

        Returns:
            True if tag is immutable (semver), False otherwise.

        Example:
            >>> classifier = TagClassifier()
            >>> classifier.is_immutable("v1.0.0")
            True
            >>> classifier.is_immutable("latest-dev")
            False
        """
        # Check if it matches semver pattern
        if self._semver_pattern.match(tag):
            return True

        # Check if it matches any mutable pattern
        for pattern in self._mutable_patterns:
            if pattern.match(tag):
                return False

        # Default: treat as immutable (safe default)
        return True

    def is_semver(self, tag: str) -> bool:
        """Check if tag matches semver pattern.

        Args:
            tag: Tag to check.

        Returns:
            True if tag matches semver pattern.
        """
        return bool(self._semver_pattern.match(tag))

    def is_mutable(self, tag: str) -> bool:
        """Check if tag matches a mutable pattern.

        Args:
            tag: Tag to check.

        Returns:
            True if tag matches a mutable pattern.
        """
        for pattern in self._mutable_patterns:
            if pattern.match(tag):
                return True
        return False


# Module-level default instance for convenience
_default_classifier: TagClassifier | None = None


def get_tag_classifier() -> TagClassifier:
    """Get the default TagClassifier instance.

    Returns:
        The module-level TagClassifier singleton.
    """
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = TagClassifier()
    return _default_classifier


def is_tag_immutable(tag: str) -> bool:
    """Check if a tag is immutable using the default classifier.

    Convenience function that delegates to the default TagClassifier.

    Args:
        tag: Tag to check.

    Returns:
        True if tag is immutable.
    """
    return get_tag_classifier().is_immutable(tag)


# =============================================================================
# URI Parsing
# =============================================================================


class URIParser:
    """Utilities for parsing and manipulating OCI URIs.

    Handles OCI URI parsing, hostname extraction, and target reference
    building for registry operations.

    Example:
        >>> parser = URIParser("oci://harbor.example.com/namespace/repo")
        >>> parser.registry_host
        'harbor.example.com'
        >>> parser.build_target_ref("v1.0.0")
        'harbor.example.com/namespace/repo:v1.0.0'
    """

    def __init__(self, uri: str) -> None:
        """Initialize URIParser with OCI URI.

        Args:
            uri: OCI URI (e.g., oci://harbor.example.com/namespace/repo).
        """
        self._uri = uri
        self._registry_host = self._extract_registry_host(uri)

    @property
    def uri(self) -> str:
        """Return the original URI."""
        return self._uri

    @property
    def registry_host(self) -> str:
        """Return the extracted registry hostname."""
        return self._registry_host

    @staticmethod
    def _extract_registry_host(uri: str) -> str:
        """Extract registry hostname from OCI URI.

        Args:
            uri: OCI URI (e.g., oci://harbor.example.com/namespace/repo).

        Returns:
            Registry hostname (e.g., harbor.example.com).
        """
        # Remove oci:// prefix
        if uri.startswith("oci://"):
            uri = uri[6:]

        # Extract hostname (first path component)
        if "/" in uri:
            return uri.split("/")[0]
        return uri

    def build_target_ref(self, tag: str) -> str:
        """Build OCI target reference from URI and tag.

        Args:
            tag: Tag for the artifact.

        Returns:
            Full OCI reference (e.g., harbor.example.com/namespace/repo:tag).
        """
        # Remove oci:// prefix if present
        uri = self._uri
        if uri.startswith("oci://"):
            uri = uri[6:]

        # Append tag
        return f"{uri}:{tag}"

    def get_repository(self) -> str:
        """Get repository path without tag.

        Returns:
            Repository path (e.g., harbor.example.com/namespace/repo).
        """
        uri = self._uri
        if uri.startswith("oci://"):
            uri = uri[6:]
        return uri


# =============================================================================
# Pull Operations Helper
# =============================================================================


class PullOperations:
    """Helper class for pull operation flow.

    Encapsulates pull-related helper logic including:
    - Cache hit checking
    - Artifacts file location
    - Content deserialization
    - Metrics recording

    This class is designed to be used by OCIClient.pull() to reduce
    its cyclomatic complexity.

    Example:
        >>> ops = PullOperations(cache_manager=cache, metrics=metrics)
        >>> artifacts = ops.try_cache_hit("v1.0.0", registry_uri, span, log, start_time)
        >>> if artifacts is None:
        ...     # Perform actual pull
        ...     pass
    """

    def __init__(
        self,
        *,
        cache_manager: CacheManager | None = None,
        metrics: OCIMetrics | None = None,
        registry_host: str = "",
    ) -> None:
        """Initialize PullOperations.

        Args:
            cache_manager: Optional cache manager for cache operations.
            metrics: Optional metrics collector.
            registry_host: Registry hostname for metrics.
        """
        self._cache_manager = cache_manager
        self._metrics = metrics
        self._registry_host = registry_host

    def find_artifacts_file(
        self,
        pulled_files: list[str],
        tmpdir: str,
    ) -> Path:
        """Find compiled_artifacts.json in pulled files.

        Uses O(1) dictionary lookup for efficient file location.

        Args:
            pulled_files: List of file paths returned by ORAS pull.
            tmpdir: Temporary directory where files were pulled.

        Returns:
            Path to compiled_artifacts.json.

        Raises:
            OCIError: If artifacts file not found.

        Example:
            >>> ops = PullOperations()
            >>> path = ops.find_artifacts_file(
            ...     ["/tmp/xyz/compiled_artifacts.json"],
            ...     "/tmp/xyz"
            ... )
            >>> path.name
            'compiled_artifacts.json'
        """
        tmpdir_path = Path(tmpdir)

        # Build dictionary mapping filename to path for O(1) lookup
        files_by_name: dict[str, Path] = {
            Path(f).name: Path(f) for f in pulled_files
        }

        # O(1) dictionary lookup
        artifacts_path = files_by_name.get("compiled_artifacts.json")

        # Check relative paths if not found
        if artifacts_path is None:
            relative_path = tmpdir_path / "compiled_artifacts.json"
            if relative_path.exists():
                artifacts_path = relative_path

        if artifacts_path is None or not artifacts_path.exists():
            raise OCIError(
                f"Artifact pulled but compiled_artifacts.json not found. "
                f"Files: {pulled_files}"
            )

        return artifacts_path

    def try_cache_hit(
        self,
        tag: str,
        registry_uri: str,
        span: Any,
        log: Any,
        start_time: float,
    ) -> CompiledArtifacts | None:
        """Try to return artifacts from cache.

        Args:
            tag: Tag to look up in cache.
            registry_uri: Registry URI for cache key.
            span: OpenTelemetry span for recording attributes.
            log: Structured logger.
            start_time: Monotonic time when operation started.

        Returns:
            CompiledArtifacts if cache hit, None otherwise.
        """
        import time

        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        if self._cache_manager is None:
            span.set_attribute("oci.cache_hit", False)
            return None

        cache_entry = self._cache_manager.get(registry_uri, tag)
        if cache_entry is None:
            span.set_attribute("oci.cache_hit", False)
            if self._metrics:
                self._metrics.record_cache_operation("miss")
            return None

        # Cache hit
        log.info("pull_cache_hit", digest=cache_entry.digest)
        span.set_attribute("oci.cache_hit", True)
        if self._metrics:
            self._metrics.record_cache_operation("hit")
        content = cache_entry.path.read_bytes()
        artifacts = CompiledArtifacts.model_validate_json(content)

        # Record metrics
        duration = time.monotonic() - start_time
        if self._metrics:
            self._metrics.record_duration("pull", self._registry_host, duration)
            self._metrics.record_operation("pull", self._registry_host, success=True)

        return artifacts

    def record_failure_metrics(self, start_time: float) -> None:
        """Record metrics for a failed pull operation.

        Args:
            start_time: Monotonic time when operation started.
        """
        import time

        if self._metrics is None:
            return

        duration = time.monotonic() - start_time
        self._metrics.record_duration("pull", self._registry_host, duration)
        self._metrics.record_operation("pull", self._registry_host, success=False)

    def compute_digest(self, content: bytes) -> str:
        """Compute SHA256 digest for content.

        Args:
            content: Content bytes.

        Returns:
            Digest string in OCI format (sha256:...).
        """
        return f"sha256:{hashlib.sha256(content).hexdigest()}"

    def deserialize_artifacts(self, content: bytes) -> CompiledArtifacts:
        """Deserialize content to CompiledArtifacts.

        Args:
            content: JSON content bytes.

        Returns:
            CompiledArtifacts instance.

        Raises:
            OCIError: If deserialization fails.
        """
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        try:
            return CompiledArtifacts.model_validate_json(content)
        except Exception as e:
            raise OCIError(f"Failed to deserialize artifact: {e}") from e


# =============================================================================
# Push Operations Helper
# =============================================================================


class PushOperations:
    """Helper class for push operation flow.

    Encapsulates push-related helper logic including:
    - Immutability checking
    - Temp file management
    - Metrics recording

    Example:
        >>> ops = PushOperations(
        ...     tag_classifier=TagClassifier(),
        ...     metrics=metrics,
        ...     registry_host="harbor.example.com"
        ... )
        >>> ops.check_immutability("v1.0.0", tag_exists_func)  # May raise
    """

    def __init__(
        self,
        *,
        tag_classifier: TagClassifier | None = None,
        metrics: OCIMetrics | None = None,
        registry_host: str = "",
    ) -> None:
        """Initialize PushOperations.

        Args:
            tag_classifier: Tag classifier for immutability checks.
            metrics: Optional metrics collector.
            registry_host: Registry hostname for metrics.
        """
        self._tag_classifier = tag_classifier or get_tag_classifier()
        self._metrics = metrics
        self._registry_host = registry_host

    def check_immutability(
        self,
        tag: str,
        tag_exists_func: Any,
    ) -> None:
        """Check if push would violate immutability.

        Args:
            tag: Tag to push to.
            tag_exists_func: Callable that checks if tag exists.

        Raises:
            ImmutabilityViolationError: If tag is immutable and exists.
        """
        from floe_core.oci.errors import ImmutabilityViolationError

        if self._tag_classifier.is_immutable(tag):
            if tag_exists_func(tag):
                raise ImmutabilityViolationError(
                    tag=tag,
                    registry=self._registry_host,
                )

    def record_failure_metrics(self, start_time: float) -> None:
        """Record metrics for a failed push operation.

        Args:
            start_time: Monotonic time when operation started.
        """
        import time

        if self._metrics is None:
            return

        duration = time.monotonic() - start_time
        self._metrics.record_duration("push", self._registry_host, duration)
        self._metrics.record_operation("push", self._registry_host, success=False)

    def record_success_metrics(
        self,
        start_time: float,
        size: int,
    ) -> float:
        """Record metrics for a successful push operation.

        Args:
            start_time: Monotonic time when operation started.
            size: Artifact size in bytes.

        Returns:
            Duration in seconds.
        """
        import time

        duration = time.monotonic() - start_time

        if self._metrics:
            self._metrics.record_duration("push", self._registry_host, duration)
            self._metrics.record_operation("push", self._registry_host, success=True)
            self._metrics.record_artifact_size("push", size)

        return duration


# =============================================================================
# Content Utilities
# =============================================================================


def create_temp_layer_files(
    layer_content: bytes,
    config_content: bytes,
    tmpdir: Path,
) -> tuple[Path, Path]:
    """Create temporary files for layer and config content.

    Args:
        layer_content: Layer content bytes.
        config_content: Config content bytes (usually empty {}).
        tmpdir: Temporary directory path.

    Returns:
        Tuple of (layer_file_path, config_file_path).

    Example:
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     layer_path, config_path = create_temp_layer_files(
        ...         b'{"version": "1.0"}',
        ...         b'{}',
        ...         Path(tmpdir)
        ...     )
        ...     print(layer_path.exists())
        True
    """
    # Write layer content to temp file
    layer_file = tmpdir / "compiled_artifacts.json"
    layer_file.write_bytes(layer_content)

    # Write config content to temp file
    config_file = tmpdir / "config.json"
    config_file.write_bytes(config_content)

    return layer_file, config_file


__all__ = [
    # Constants
    "MUTABLE_TAG_PATTERNS",
    "SEMVER_PATTERN",
    # Tag Classification
    "TagClassifier",
    "get_tag_classifier",
    "is_tag_immutable",
    # URI Parsing
    "URIParser",
    # Operations
    "PullOperations",
    "PushOperations",
    # Utilities
    "create_temp_layer_files",
]

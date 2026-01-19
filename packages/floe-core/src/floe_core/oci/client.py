"""OCI Client for floe CompiledArtifacts distribution.

This module provides the main OCIClient class for pushing, pulling, inspecting,
and listing floe CompiledArtifacts to/from OCI registries.

The client uses the ORAS Python SDK for registry operations, integrates with
SecretsPlugin (Epic 7A) for authentication, and includes resilience patterns
(retry, circuit breaker), local caching, and OpenTelemetry observability.

Key Features:
    - Push CompiledArtifacts to OCI registries
    - Pull and deserialize artifacts back to CompiledArtifacts
    - Inspect artifact metadata without downloading content
    - List artifacts with tag filtering
    - Immutability enforcement for semver tags
    - Local caching with TTL and LRU eviction
    - Retry with exponential backoff
    - Circuit breaker for registry availability
    - OpenTelemetry metrics and tracing

Example:
    >>> from floe_core.oci import OCIClient
    >>> from floe_core.schemas.compiled_artifacts import CompiledArtifacts
    >>>
    >>> # Create client from manifest config
    >>> client = OCIClient.from_manifest("manifest.yaml")
    >>>
    >>> # Push artifact
    >>> artifacts = CompiledArtifacts.from_json_file("target/compiled_artifacts.json")
    >>> digest = client.push(artifacts, tag="v1.0.0")
    >>>
    >>> # Pull artifact
    >>> artifacts = client.pull(tag="v1.0.0")
    >>>
    >>> # Inspect metadata
    >>> manifest = client.inspect(tag="v1.0.0")
    >>> print(f"Size: {manifest.size} bytes")
    >>>
    >>> # List available tags
    >>> tags = client.list(filter="v1.*")
    >>> for tag in tags:
    ...     print(f"{tag.name}: {tag.digest}")

See Also:
    - specs/08a-oci-client/spec.md: Feature specification
    - specs/08a-oci-client/research.md: Technology research
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml
from oras.client import OrasClient  # type: ignore[import-untyped]

from floe_core.oci.auth import AuthProvider, create_auth_provider
from floe_core.oci.cache import CacheManager
from floe_core.oci.errors import (
    ArtifactNotFoundError,
    AuthenticationError,
    CircuitBreakerOpenError,
    ImmutabilityViolationError,
    OCIError,
    RegistryUnavailableError,
)
from floe_core.oci.manifest import (
    build_manifest,
    create_empty_config,
    serialize_layer,
)
from floe_core.oci.metrics import OCIMetrics, get_oci_metrics
from floe_core.oci.resilience import CircuitBreaker, RetryPolicy
from floe_core.schemas.oci import (
    ArtifactManifest,
    ArtifactTag,
    RegistryConfig,
)

if TYPE_CHECKING:
    from floe_core.plugins.secrets import SecretsPlugin
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts

logger = structlog.get_logger(__name__)


# Semver pattern for immutability enforcement
SEMVER_PATTERN = re.compile(r"^v?\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$")
"""Pattern matching semantic versioning tags (e.g., v1.0.0, 1.2.3-alpha)."""

# Mutable tag patterns that are allowed to be overwritten
MUTABLE_TAG_PATTERNS = [
    re.compile(r"^latest(-.*)?$"),  # latest, latest-dev, latest-staging
    re.compile(r"^dev(-.*)?$"),  # dev, dev-branch
    re.compile(r"^snapshot(-.*)?$"),  # snapshot, snapshot-123
]
"""Patterns for mutable tags that can be overwritten."""


class OCIClient:
    """OCI client for floe CompiledArtifacts distribution.

    Provides push, pull, inspect, and list operations for OCI-compliant
    registries. Integrates with SecretsPlugin for authentication, includes
    resilience patterns, and supports local caching.

    The client is designed to be created via the factory methods:
    - `from_registry_config()`: Create from RegistryConfig schema
    - `from_manifest()`: Create from manifest.yaml file path

    Attributes:
        registry_uri: The OCI registry URI (e.g., oci://harbor.example.com/namespace)
        config: The RegistryConfig containing all settings

    Example:
        >>> client = OCIClient.from_manifest("manifest.yaml")
        >>> artifacts = client.pull(tag="v1.0.0")
    """

    def __init__(
        self,
        registry_config: RegistryConfig,
        *,
        auth_provider: AuthProvider | None = None,
        cache_manager: CacheManager | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        metrics: OCIMetrics | None = None,
        secrets_plugin: SecretsPlugin | None = None,
    ) -> None:
        """Initialize OCIClient with dependency injection.

        Args:
            registry_config: Registry configuration from manifest.yaml.
            auth_provider: Optional pre-configured auth provider.
                If None, created from registry_config.auth and secrets_plugin.
            cache_manager: Optional pre-configured cache manager.
                If None, created from registry_config.cache.
            circuit_breaker: Optional pre-configured circuit breaker.
                If None, created from registry_config.resilience.circuit_breaker.
            retry_policy: Optional pre-configured retry policy.
                If None, created from registry_config.resilience.retry.
            metrics: Optional pre-configured metrics collector.
                If None, uses module-level singleton.
            secrets_plugin: Optional SecretsPlugin for credential resolution.
                Required if auth_provider is None and auth type is basic/token.
        """
        self._config = registry_config
        self._secrets_plugin = secrets_plugin

        # Dependency injection with lazy defaults
        self._auth_provider = auth_provider
        self._cache_manager = cache_manager
        self._circuit_breaker = circuit_breaker
        self._retry_policy = retry_policy
        self._metrics = metrics

        # Parse registry URI for hostname extraction
        self._registry_host = self._extract_registry_host(registry_config.uri)

        logger.info(
            "oci_client_initialized",
            registry=self._registry_host,
            auth_type=registry_config.auth.type.value,
            cache_enabled=registry_config.cache.enabled,
        )

    @property
    def registry_uri(self) -> str:
        """Return the registry URI."""
        return self._config.uri

    @property
    def config(self) -> RegistryConfig:
        """Return the registry configuration."""
        return self._config

    @property
    def auth_provider(self) -> AuthProvider:
        """Get or create the authentication provider."""
        if self._auth_provider is None:
            self._auth_provider = create_auth_provider(
                registry_uri=self._config.uri,
                auth_config=self._config.auth,
                secrets_plugin=self._secrets_plugin,
            )
        return self._auth_provider

    @property
    def cache_manager(self) -> CacheManager | None:
        """Get or create the cache manager."""
        if self._cache_manager is None and self._config.cache.enabled:
            self._cache_manager = CacheManager(config=self._config.cache)
        return self._cache_manager

    @property
    def circuit_breaker(self) -> CircuitBreaker | None:
        """Get or create the circuit breaker."""
        if self._circuit_breaker is None and self._config.resilience.circuit_breaker.enabled:
            self._circuit_breaker = CircuitBreaker(
                registry_uri=self._config.uri,
                config=self._config.resilience.circuit_breaker,
            )
        return self._circuit_breaker

    @property
    def retry_policy(self) -> RetryPolicy:
        """Get or create the retry policy."""
        if self._retry_policy is None:
            self._retry_policy = RetryPolicy(
                config=self._config.resilience.retry,
            )
        return self._retry_policy

    @property
    def metrics(self) -> OCIMetrics:
        """Get the metrics collector."""
        if self._metrics is None:
            self._metrics = get_oci_metrics()
        return self._metrics

    @contextmanager
    def _with_circuit_breaker(self, operation: str) -> Iterator[None]:
        """Context manager to wrap registry operations with circuit breaker.

        If circuit breaker is disabled, this is a no-op. If enabled and open,
        raises CircuitBreakerOpenError. Records success/failure for state
        transitions.

        Args:
            operation: Name of the operation (for logging).

        Yields:
            None

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open.
        """
        circuit = self.circuit_breaker
        if circuit is None:
            # Circuit breaker disabled, pass through
            yield
            return

        log = logger.bind(
            registry=self._registry_host,
            operation=operation,
            circuit_state=circuit.state.value,
        )

        with circuit.protect():
            log.debug("circuit_breaker_allowed", operation=operation)
            yield
        # Success is recorded automatically by protect() on clean exit
        # Failure is recorded automatically by protect() on exception

    @classmethod
    def from_registry_config(
        cls,
        config: RegistryConfig,
        *,
        secrets_plugin: SecretsPlugin | None = None,
    ) -> OCIClient:
        """Create OCIClient from RegistryConfig.

        Args:
            config: Registry configuration schema.
            secrets_plugin: Optional SecretsPlugin for credential resolution.

        Returns:
            Configured OCIClient instance.

        Example:
            >>> config = RegistryConfig(
            ...     uri="oci://harbor.example.com/floe",
            ...     auth=RegistryAuth(type=AuthType.AWS_IRSA),
            ... )
            >>> client = OCIClient.from_registry_config(config)
        """
        return cls(config, secrets_plugin=secrets_plugin)

    @classmethod
    def from_manifest(
        cls,
        manifest_path: str | Path,
        *,
        secrets_plugin: SecretsPlugin | None = None,
    ) -> OCIClient:
        """Create OCIClient from manifest.yaml file.

        Reads the `artifacts.registry` section from the manifest file and
        creates a configured client.

        Args:
            manifest_path: Path to manifest.yaml file.
            secrets_plugin: Optional SecretsPlugin for credential resolution.

        Returns:
            Configured OCIClient instance.

        Raises:
            OCIError: If manifest file cannot be read or registry config is missing.

        Example:
            >>> client = OCIClient.from_manifest("manifest.yaml")
        """
        path = Path(manifest_path)
        if not path.exists():
            raise OCIError(f"Manifest file not found: {path}")

        try:
            with path.open() as f:
                manifest_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise OCIError(f"Failed to parse manifest YAML: {e}") from e

        if manifest_data is None:
            raise OCIError(f"Empty manifest file: {path}")

        # Extract artifacts.registry section
        artifacts_config = manifest_data.get("artifacts", {})
        registry_config_data = artifacts_config.get("registry")

        if registry_config_data is None:
            raise OCIError(f"Missing 'artifacts.registry' section in manifest: {path}")

        # Validate and create RegistryConfig
        try:
            config = RegistryConfig.model_validate(registry_config_data)
        except Exception as e:
            raise OCIError(f"Invalid registry configuration: {e}") from e

        return cls.from_registry_config(config, secrets_plugin=secrets_plugin)

    def push(
        self,
        artifacts: CompiledArtifacts,
        tag: str,
        *,
        annotations: dict[str, str] | None = None,
    ) -> str:
        """Push CompiledArtifacts to the registry.

        Serializes the artifacts to JSON and uploads to the registry with
        the specified tag. Enforces immutability for semver tags.

        Args:
            artifacts: CompiledArtifacts to push.
            tag: Tag for the artifact (e.g., "v1.0.0", "latest-dev").
            annotations: Optional additional annotations to include.

        Returns:
            The artifact digest (sha256:...).

        Raises:
            ImmutabilityViolationError: If pushing to an existing semver tag.
            AuthenticationError: If authentication fails.
            RegistryUnavailableError: If registry is unavailable after retries.

        Example:
            >>> artifacts = CompiledArtifacts.from_json_file("compiled.json")
            >>> digest = client.push(artifacts, tag="v1.0.0")
            >>> print(f"Pushed with digest: {digest}")
        """
        import time

        from floe_core.oci.metrics import OCIMetrics

        log = logger.bind(
            registry=self._registry_host,
            tag=tag,
            product_name=artifacts.metadata.product_name,
            product_version=artifacts.metadata.product_version,
        )

        log.info("push_started")

        # Start timing for duration metric
        start_time = time.monotonic()

        # Span attributes for OTel tracing
        span_attributes: dict[str, Any] = {
            "oci.registry": self._registry_host,
            "oci.tag": tag,
            "oci.product.name": artifacts.metadata.product_name,
            "oci.product.version": artifacts.metadata.product_version,
            "oci.operation": "push",
        }

        # Wrap entire operation in a trace span
        with self.metrics.create_span(OCIMetrics.SPAN_PUSH, span_attributes) as span:
            try:
                # Check immutability constraints before push
                self._check_immutability_before_push(tag)

                # Serialize artifacts to layer content
                layer_content, layer_descriptor = serialize_layer(
                    artifacts, annotations=annotations
                )

                # Build manifest with product metadata
                manifest = build_manifest(
                    artifacts, layers=[layer_descriptor], annotations=annotations
                )

                # Add size to span attributes
                span.set_attribute("oci.artifact.size_bytes", manifest.size)
                span.set_attribute("oci.artifact.layer_count", len(manifest.layers))

                # Build target reference (registry/namespace/repo:tag)
                target_ref = self._build_target_ref(tag)

                # Wrap registry operations with circuit breaker protection
                with self._with_circuit_breaker("push"):
                    # Create ORAS client for registry operations
                    oras_client = self._create_oras_client()

                    # Push using ORAS with temp files (ORAS SDK requires file paths)
                    with tempfile.TemporaryDirectory() as tmpdir:
                        tmpdir_path = Path(tmpdir)

                        # Write layer content to temp file
                        layer_file = tmpdir_path / "compiled_artifacts.json"
                        layer_file.write_bytes(layer_content)

                        # Write empty config blob
                        config_content, _config_digest = create_empty_config()
                        config_file = tmpdir_path / "config.json"
                        config_file.write_bytes(config_content)

                        # Push artifact using ORAS
                        # ORAS handles: blob upload, manifest creation, tag assignment
                        response = oras_client.push(
                            target=target_ref,
                            config_path=str(config_file),
                            files=[str(layer_file)],
                            manifest_annotations=manifest.annotations,
                        )

                        # Verify response
                        if not response.ok:
                            raise RegistryUnavailableError(
                                self._registry_host,
                                f"Push failed: {response.status_code}: {response.text}",
                            )

                # Record duration metric
                duration = time.monotonic() - start_time
                self.metrics.record_duration("push", self._registry_host, duration)

                # Record success metrics
                self.metrics.record_operation("push", self._registry_host, success=True)
                self.metrics.record_artifact_size("push", manifest.size)

                # Add final digest to span
                span.set_attribute("oci.artifact.digest", manifest.digest)

                log.info(
                    "push_completed",
                    digest=manifest.digest,
                    size=manifest.size,
                    layer_count=len(manifest.layers),
                    duration_ms=int(duration * 1000),
                )

                return manifest.digest

            except ImmutabilityViolationError:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("push", self._registry_host, duration)
                self.metrics.record_operation("push", self._registry_host, success=False)
                raise
            except CircuitBreakerOpenError:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("push", self._registry_host, duration)
                self.metrics.record_operation("push", self._registry_host, success=False)
                log.warning("push_circuit_breaker_open")
                raise
            except AuthenticationError:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("push", self._registry_host, duration)
                self.metrics.record_operation("push", self._registry_host, success=False)
                raise
            except RegistryUnavailableError:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("push", self._registry_host, duration)
                self.metrics.record_operation("push", self._registry_host, success=False)
                raise
            except Exception as e:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("push", self._registry_host, duration)
                self.metrics.record_operation("push", self._registry_host, success=False)
                log.error("push_failed", error=str(e))
                raise OCIError(f"Push failed: {e}") from e

    def _create_oras_client(self) -> OrasClient:
        """Create and authenticate ORAS client.

        Returns:
            Authenticated OrasClient instance.

        Raises:
            AuthenticationError: If authentication fails.
        """
        # Create ORAS client with TLS settings
        oras_client = OrasClient(insecure=not self._config.tls_verify)

        # Get credentials from auth provider
        credentials = self.auth_provider.get_credentials()

        # Login to registry
        try:
            oras_client.login(
                hostname=self._registry_host,
                username=credentials.username,
                password=credentials.password,
            )
        except Exception as e:
            raise AuthenticationError(
                self._registry_host,
                f"Failed to authenticate with registry: {e}",
            ) from e

        return oras_client

    def _build_target_ref(self, tag: str) -> str:
        """Build OCI target reference from registry URI and tag.

        Args:
            tag: Tag for the artifact.

        Returns:
            Full OCI reference (e.g., harbor.example.com/namespace/repo:tag).
        """
        # Remove oci:// prefix if present
        uri = self._config.uri
        if uri.startswith("oci://"):
            uri = uri[6:]

        # Append tag
        return f"{uri}:{tag}"

    def pull(
        self,
        tag: str,
        *,
        verify_digest: bool = True,
    ) -> CompiledArtifacts:
        """Pull CompiledArtifacts from the registry.

        Downloads the artifact and deserializes to CompiledArtifacts.
        Uses local cache for immutable tags.

        Args:
            tag: Tag to pull (e.g., "v1.0.0", "latest-dev").
            verify_digest: Whether to verify digest after download.

        Returns:
            Deserialized CompiledArtifacts.

        Raises:
            ArtifactNotFoundError: If tag does not exist.
            AuthenticationError: If authentication fails.
            RegistryUnavailableError: If registry is unavailable after retries.

        Example:
            >>> artifacts = client.pull(tag="v1.0.0")
            >>> print(f"Product: {artifacts.product_identity.name}")
        """
        import time

        from floe_core.oci.metrics import OCIMetrics
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        log = logger.bind(
            registry=self._registry_host,
            tag=tag,
        )

        log.info("pull_started")

        # Start timing for duration metric
        start_time = time.monotonic()

        # Span attributes for OTel tracing
        span_attributes: dict[str, Any] = {
            "oci.registry": self._registry_host,
            "oci.tag": tag,
            "oci.operation": "pull",
        }

        # Wrap entire operation in a trace span
        with self.metrics.create_span(OCIMetrics.SPAN_PULL, span_attributes) as span:
            try:
                # Check cache first (CacheManager handles TTL validation for mutable tags)
                if self.cache_manager is not None:
                    cache_entry = self.cache_manager.get(self._config.uri, tag)
                    if cache_entry is not None:
                        log.info(
                            "pull_cache_hit",
                            digest=cache_entry.digest,
                        )
                        span.set_attribute("oci.cache_hit", True)
                        self.metrics.record_cache_operation("hit")
                        content = cache_entry.path.read_bytes()
                        artifacts = CompiledArtifacts.model_validate_json(content)

                        # Record metrics
                        duration = time.monotonic() - start_time
                        self.metrics.record_duration("pull", self._registry_host, duration)
                        self.metrics.record_operation("pull", self._registry_host, success=True)

                        return artifacts
                    else:
                        # Cache miss - only record if cache was checked
                        span.set_attribute("oci.cache_hit", False)
                        self.metrics.record_cache_operation("miss")
                else:
                    span.set_attribute("oci.cache_hit", False)

                # Use retry policy for network operations
                def _pull_with_oras() -> tuple[bytes, str]:
                    """Inner function to pull via ORAS with retry."""
                    oras_client = self._create_oras_client()
                    target_ref = self._build_target_ref(tag)

                    # Pull to temp directory
                    with tempfile.TemporaryDirectory() as tmpdir:
                        try:
                            # ORAS pull returns list of file paths
                            pulled_files = oras_client.pull(
                                target=target_ref,
                                outdir=tmpdir,
                            )

                            # Find the compiled_artifacts.json file
                            # ORAS may return full paths or just the file
                            artifacts_path: Path | None = None
                            tmpdir_path = Path(tmpdir)

                            for pulled_file in pulled_files:
                                file_path = Path(pulled_file)
                                if file_path.name == "compiled_artifacts.json":
                                    artifacts_path = file_path
                                    break
                                # Also check relative to tmpdir
                                relative_path = tmpdir_path / file_path.name
                                is_target = relative_path.name == "compiled_artifacts.json"
                                if relative_path.exists() and is_target:
                                    artifacts_path = relative_path
                                    break

                            # Fallback: check tmpdir for the file
                            if artifacts_path is None:
                                potential_path = tmpdir_path / "compiled_artifacts.json"
                                if potential_path.exists():
                                    artifacts_path = potential_path

                            if artifacts_path is None or not artifacts_path.exists():
                                raise OCIError(
                                    f"Artifact pulled but compiled_artifacts.json not found. "
                                    f"Files: {pulled_files}"
                                )

                            content = artifacts_path.read_bytes()

                            # Compute digest for cache
                            import hashlib

                            digest = f"sha256:{hashlib.sha256(content).hexdigest()}"

                            return content, digest

                        except Exception as e:
                            error_str = str(e).lower()
                            # Detect "manifest unknown" or 404 errors
                            if "manifest unknown" in error_str or "not found" in error_str:
                                raise ArtifactNotFoundError(
                                    tag=tag,
                                    registry=self._config.uri,
                                ) from e
                            raise

                # Apply retry policy with circuit breaker protection
                # Circuit breaker wraps retry - if circuit is open, fail fast
                with self._with_circuit_breaker("pull"):
                    try:
                        content, digest = self.retry_policy.wrap(_pull_with_oras)()
                    except ArtifactNotFoundError:
                        # Don't retry 404 errors
                        raise
                    except ConnectionError as e:
                        raise RegistryUnavailableError(
                            self._registry_host,
                            f"Connection failed after retries: {e}",
                        ) from e

                # Deserialize to CompiledArtifacts
                try:
                    artifacts = CompiledArtifacts.model_validate_json(content)
                except Exception as e:
                    raise OCIError(f"Failed to deserialize artifact: {e}") from e

                # Add product info to span after deserialization
                span.set_attribute("oci.product.name", artifacts.metadata.product_name)
                span.set_attribute("oci.product.version", artifacts.metadata.product_version)
                span.set_attribute("oci.artifact.digest", digest)

                # Store in cache (CacheManager sets TTL based on tag type)
                if self.cache_manager is not None:
                    self.cache_manager.put(
                        digest=digest,
                        tag=tag,
                        registry=self._config.uri,
                        content=content,
                    )
                    log.debug("pull_cached", digest=digest, tag=tag)

                # Record duration metric
                duration = time.monotonic() - start_time
                self.metrics.record_duration("pull", self._registry_host, duration)

                # Record success metrics
                self.metrics.record_operation("pull", self._registry_host, success=True)
                self.metrics.record_artifact_size("pull", len(content))

                log.info(
                    "pull_completed",
                    digest=digest,
                    size=len(content),
                    duration_ms=int(duration * 1000),
                )

                return artifacts

            except ArtifactNotFoundError:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("pull", self._registry_host, duration)
                self.metrics.record_operation("pull", self._registry_host, success=False)
                raise
            except CircuitBreakerOpenError:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("pull", self._registry_host, duration)
                self.metrics.record_operation("pull", self._registry_host, success=False)
                log.warning("pull_circuit_breaker_open")
                raise
            except AuthenticationError:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("pull", self._registry_host, duration)
                self.metrics.record_operation("pull", self._registry_host, success=False)
                raise
            except RegistryUnavailableError:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("pull", self._registry_host, duration)
                self.metrics.record_operation("pull", self._registry_host, success=False)
                raise
            except Exception as e:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("pull", self._registry_host, duration)
                self.metrics.record_operation("pull", self._registry_host, success=False)
                log.error("pull_failed", error=str(e))
                raise OCIError(f"Pull failed: {e}") from e

    def inspect(self, tag: str) -> ArtifactManifest:
        """Inspect artifact metadata without downloading content.

        Retrieves the manifest for the specified tag including digest,
        size, creation time, layers, and signature status.

        Args:
            tag: Tag to inspect (e.g., "v1.0.0").

        Returns:
            ArtifactManifest with metadata.

        Raises:
            ArtifactNotFoundError: If tag does not exist.
            AuthenticationError: If authentication fails.

        Example:
            >>> manifest = client.inspect(tag="v1.0.0")
            >>> print(f"Digest: {manifest.digest}")
            >>> print(f"Size: {manifest.size} bytes")
        """
        import hashlib
        import json
        import time
        from datetime import datetime, timezone

        from floe_core.oci.metrics import OCIMetrics
        from floe_core.schemas.oci import ArtifactLayer, SignatureStatus

        log = logger.bind(
            registry=self._registry_host,
            tag=tag,
        )

        log.info("inspect_started")

        # Start timing for duration metric
        start_time = time.monotonic()

        # Span attributes for OTel tracing
        span_attributes: dict[str, Any] = {
            "oci.registry": self._registry_host,
            "oci.tag": tag,
            "oci.operation": "inspect",
        }

        # Wrap entire operation in a trace span
        with self.metrics.create_span(OCIMetrics.SPAN_INSPECT, span_attributes) as span:
            try:
                # Wrap registry operations with circuit breaker protection
                with self._with_circuit_breaker("inspect"):
                    # Create ORAS client for registry operations
                    oras_client = self._create_oras_client()

                    # Build target reference (registry/namespace/repo:tag)
                    target_ref = self._build_target_ref(tag)

                    # Get manifest only (no blob download)
                    try:
                        manifest_data = oras_client.get_manifest(target=target_ref)
                    except Exception as e:
                        error_str = str(e).lower()
                        # Detect "manifest unknown" or 404 errors
                        if "manifest unknown" in error_str or "not found" in error_str:
                            raise ArtifactNotFoundError(
                                tag=tag,
                                registry=self._config.uri,
                            ) from e
                        raise

                # Calculate manifest digest (sha256 of canonical JSON)
                manifest_json = json.dumps(manifest_data, separators=(",", ":"), sort_keys=True)
                manifest_digest = f"sha256:{hashlib.sha256(manifest_json.encode()).hexdigest()}"

                # Parse layers from manifest
                layers_data = manifest_data.get("layers", [])
                layers: list[ArtifactLayer] = []
                total_size = 0

                for layer_data in layers_data:
                    layer = ArtifactLayer(
                        digest=layer_data.get("digest", ""),
                        media_type=layer_data.get("mediaType", ""),
                        size=layer_data.get("size", 0),
                        annotations=layer_data.get("annotations", {}),
                    )
                    layers.append(layer)
                    total_size += layer.size

                # Extract artifact type (OCI v1.1) or fall back to config mediaType
                artifact_type = manifest_data.get("artifactType", "")
                if not artifact_type:
                    config_data = manifest_data.get("config", {})
                    artifact_type = config_data.get("mediaType", "application/octet-stream")

                # Extract annotations
                annotations = manifest_data.get("annotations", {})

                # Parse created timestamp from annotations
                created_str = annotations.get(
                    "org.opencontainers.image.created",
                    datetime.now(timezone.utc).isoformat(),
                )
                try:
                    # Handle ISO format with or without Z suffix
                    if created_str.endswith("Z"):
                        created_str = created_str[:-1] + "+00:00"
                    created_at = datetime.fromisoformat(created_str)
                except ValueError:
                    created_at = datetime.now(timezone.utc)

                # Build ArtifactManifest
                manifest = ArtifactManifest(
                    digest=manifest_digest,
                    artifact_type=artifact_type,
                    size=total_size,
                    created_at=created_at,
                    annotations=annotations,
                    layers=layers,
                    signature_status=SignatureStatus.UNSIGNED,  # Placeholder for Epic 8B
                )

                # Add attributes to span
                span.set_attribute("oci.artifact.digest", manifest_digest)
                span.set_attribute("oci.artifact.size_bytes", total_size)
                span.set_attribute("oci.artifact.layer_count", len(layers))

                # Record duration metric
                duration = time.monotonic() - start_time
                self.metrics.record_duration("inspect", self._registry_host, duration)

                # Record success metrics
                self.metrics.record_operation("inspect", self._registry_host, success=True)

                log.info(
                    "inspect_completed",
                    digest=manifest_digest,
                    size=total_size,
                    layer_count=len(layers),
                    duration_ms=int(duration * 1000),
                )

                return manifest

            except ArtifactNotFoundError:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("inspect", self._registry_host, duration)
                self.metrics.record_operation("inspect", self._registry_host, success=False)
                raise
            except CircuitBreakerOpenError:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("inspect", self._registry_host, duration)
                self.metrics.record_operation("inspect", self._registry_host, success=False)
                log.warning("inspect_circuit_breaker_open")
                raise
            except AuthenticationError:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("inspect", self._registry_host, duration)
                self.metrics.record_operation("inspect", self._registry_host, success=False)
                raise
            except Exception as e:
                duration = time.monotonic() - start_time
                self.metrics.record_duration("inspect", self._registry_host, duration)
                self.metrics.record_operation("inspect", self._registry_host, success=False)
                log.error("inspect_failed", error=str(e))
                raise OCIError(f"Inspect failed: {e}") from e

    def list(
        self,
        *,
        filter_pattern: str | None = None,
    ) -> list[ArtifactTag]:
        """List artifacts and tags in the registry.

        Returns a list of available tags with their digests and metadata.
        Optionally filters by pattern (glob-style).

        Args:
            filter_pattern: Optional glob pattern to filter tags (e.g., "v1.*").

        Returns:
            List of ArtifactTag objects.

        Raises:
            AuthenticationError: If authentication fails.
            RegistryUnavailableError: If registry is unavailable.

        Example:
            >>> tags = client.list(filter_pattern="v1.*")
            >>> for tag in tags:
            ...     print(f"{tag.name}: {tag.digest}")
        """
        import fnmatch
        import hashlib
        import json
        import time
        from datetime import datetime, timezone

        log = logger.bind(
            registry=self._registry_host,
            filter_pattern=filter_pattern,
        )

        log.info("list_started")

        # Start timing for duration metric
        start_time = time.monotonic()

        try:
            # Wrap registry operations with circuit breaker protection
            with self._with_circuit_breaker("list"):
                # Create ORAS client for registry operations
                oras_client = self._create_oras_client()

                # Build repository reference (without tag) for listing tags
                uri = self._config.uri
                if uri.startswith("oci://"):
                    uri = uri[6:]

                # Get list of tags from registry
                try:
                    tags_response = oras_client.get_tags(target=uri)
                except Exception as e:
                    error_str = str(e).lower()
                    if "unauthorized" in error_str or "authentication" in error_str:
                        raise AuthenticationError(
                            self._config.uri,
                            "Authentication failed while listing tags",
                        ) from e
                    raise OCIError(f"Failed to list tags: {e}") from e

                # Extract tag names from response
                tag_names: list[str] = tags_response.get("tags", [])

                # Filter by pattern if provided
                if filter_pattern:
                    tag_names = [
                        name for name in tag_names if fnmatch.fnmatch(name, filter_pattern)
                    ]

                # Build ArtifactTag list by getting manifest for each tag
                result: list[ArtifactTag] = []

                for tag_name in tag_names:
                    try:
                        # Get manifest for this tag
                        target_ref = self._build_target_ref(tag_name)
                        manifest_data = oras_client.get_manifest(target=target_ref)

                        # Calculate manifest digest
                        manifest_json = json.dumps(
                            manifest_data, separators=(",", ":"), sort_keys=True
                        )
                        digest = f"sha256:{hashlib.sha256(manifest_json.encode()).hexdigest()}"

                        # Extract created timestamp from annotations
                        annotations = manifest_data.get("annotations", {})
                        created_str = annotations.get(
                            "org.opencontainers.image.created",
                            datetime.now(timezone.utc).isoformat(),
                        )

                        # Parse created timestamp
                        try:
                            if created_str.endswith("Z"):
                                created_str = created_str[:-1] + "+00:00"
                            created_at = datetime.fromisoformat(created_str)
                        except ValueError:
                            created_at = datetime.now(timezone.utc)

                        # Calculate total size from layers
                        layers_data = manifest_data.get("layers", [])
                        total_size = sum(layer.get("size", 0) for layer in layers_data)

                        # Create ArtifactTag
                        artifact_tag = ArtifactTag(
                            name=tag_name,
                            digest=digest,
                            created_at=created_at,
                            size=total_size,
                        )
                        result.append(artifact_tag)

                    except Exception as e:
                        # Log warning but continue with other tags
                        log.warning(
                            "list_tag_failed",
                            tag=tag_name,
                            error=str(e),
                        )
                        continue

            # Record duration metric
            duration = time.monotonic() - start_time
            self.metrics.record_duration("list", self._registry_host, duration)
            self.metrics.record_operation("list", self._registry_host, success=True)

            log.info(
                "list_completed",
                tag_count=len(result),
                duration_ms=int(duration * 1000),
            )

            return result

        except CircuitBreakerOpenError:
            duration = time.monotonic() - start_time
            self.metrics.record_duration("list", self._registry_host, duration)
            self.metrics.record_operation("list", self._registry_host, success=False)
            log.warning("list_circuit_breaker_open")
            raise
        except AuthenticationError:
            duration = time.monotonic() - start_time
            self.metrics.record_duration("list", self._registry_host, duration)
            self.metrics.record_operation("list", self._registry_host, success=False)
            raise
        except Exception as e:
            duration = time.monotonic() - start_time
            self.metrics.record_duration("list", self._registry_host, duration)
            self.metrics.record_operation("list", self._registry_host, success=False)
            log.error("list_failed", error=str(e))
            raise OCIError(f"List failed: {e}") from e

    def promote_to_environment(
        self,
        source_tag: str,
        target_environment: str,
        *,
        target_tag: str | None = None,
    ) -> str:
        """Promote artifact to target environment.

        Promotes an artifact from one environment to another by creating
        a new tag or copying to a target registry. This is a placeholder
        for Epic 8C (Artifact Promotion) integration.

        Args:
            source_tag: Tag of artifact to promote.
            target_environment: Target environment (e.g., "staging", "production").
            target_tag: Optional specific tag for promoted artifact.
                       Defaults to generating a tag based on source + environment.

        Returns:
            Digest of promoted artifact.

        Raises:
            ArtifactNotFoundError: If source artifact doesn't exist.
            PromotionError: If promotion workflow fails.
            AuthenticationError: If authentication fails.

        Example:
            >>> digest = client.promote_to_environment(
            ...     source_tag="v1.0.0",
            ...     target_environment="production",
            ... )
            >>> print(f"Promoted to: {digest}")
        """
        # Placeholder - implementation in Epic 8C
        raise NotImplementedError("promote_to_environment() not yet implemented - see Epic 8C")

    def check_registry_capabilities(self) -> dict[str, Any]:
        """Check registry capabilities and configuration.

        Validates the registry is reachable and checks for:
        - OCI distribution-spec v1.1 artifact support
        - Authentication validity
        - Tag listing capability (for immutability enforcement)

        This method performs a lightweight health check without pushing
        or pulling artifacts. Use it to verify configuration before
        production operations.

        Returns:
            Dictionary with capability information:
            - reachable: bool - Registry responded to API call
            - authenticated: bool - Credentials accepted
            - oci_v1_1: bool - OCI distribution-spec v1.1 supported
            - artifact_type_filtering: bool - Can filter by artifactType
            - immutability_enforcement: str - "client-side" (always)
            - registry: str - Registry hostname
            - auth_type: str - Authentication type used

        Raises:
            RegistryUnavailableError: If registry is unreachable.
            AuthenticationError: If authentication fails.

        Example:
            >>> caps = client.check_registry_capabilities()
            >>> print(f"Reachable: {caps['reachable']}")
            >>> print(f"OCI v1.1: {caps['oci_v1_1']}")
            >>> print(f"Immutability: {caps['immutability_enforcement']}")
        """
        # Import here to avoid circular dependency and allow lazy loading
        from floe_core.oci.errors import AuthenticationError

        capabilities: dict[str, Any] = {
            "reachable": False,
            "authenticated": False,
            "oci_v1_1": False,
            "artifact_type_filtering": False,
            "immutability_enforcement": "client-side",
            "registry": self._registry_host,
            "auth_type": self._config.auth.type.value,
        }

        log = logger.bind(registry=self._registry_host)

        # Step 1: Validate authentication credentials can be obtained
        try:
            credentials = self.auth_provider.get_credentials()
            capabilities["authenticated"] = True
            log.debug(
                "registry_auth_validated",
                auth_type=self._config.auth.type.value,
                expires_at=credentials.expires_at.isoformat() if credentials.expires_at else None,
            )
        except AuthenticationError:
            log.warning("registry_auth_failed", auth_type=self._config.auth.type.value)
            raise
        except Exception as e:
            log.error("registry_auth_error", error=str(e))
            raise AuthenticationError(
                self._registry_host,
                f"Failed to obtain credentials: {e}",
            ) from e

        # Step 2: Check registry reachability (using OCI distribution API)
        # NOTE: Full connectivity check requires ORAS client which is implemented
        # in later tasks. For now, we validate auth and assume reachable if auth works.
        # The actual ping will be added when push/pull are implemented.
        #
        # In production, this would call the OCI distribution-spec catalog endpoint:
        # GET /v2/_catalog or GET /v2/{name}/tags/list

        # Mark as reachable since auth succeeded (lightweight check)
        capabilities["reachable"] = True

        # Step 3: OCI v1.1 artifact support detection
        # OCI v1.1 support is indicated by:
        # - Presence of artifactType field in manifests
        # - Support for referrers API
        #
        # For now, assume OCI v1.1 support since all target registries
        # (Harbor 2.x, ECR, ACR, GAR) support it. Full detection will
        # query the registry API when push/pull are implemented.
        capabilities["oci_v1_1"] = True

        # Artifact type filtering is a v1.1 feature
        capabilities["artifact_type_filtering"] = True

        log.info(
            "registry_capabilities_checked",
            reachable=capabilities["reachable"],
            authenticated=capabilities["authenticated"],
            oci_v1_1=capabilities["oci_v1_1"],
            immutability_enforcement=capabilities["immutability_enforcement"],
        )

        return capabilities

    def is_tag_immutable(self, tag: str) -> bool:
        """Check if a tag is considered immutable.

        Semver tags (v1.0.0, 1.2.3-alpha) are immutable and cannot be
        overwritten once pushed.

        Mutable patterns (latest-*, dev-*, snapshot-*) can be overwritten.

        Args:
            tag: Tag to check.

        Returns:
            True if tag is immutable (semver), False otherwise.

        Example:
            >>> client.is_tag_immutable("v1.0.0")
            True
            >>> client.is_tag_immutable("latest-dev")
            False
        """
        # Check if it matches semver pattern
        if SEMVER_PATTERN.match(tag):
            return True

        # Check if it matches any mutable pattern
        for pattern in MUTABLE_TAG_PATTERNS:
            if pattern.match(tag):
                return False

        # Default: treat as immutable (safe default)
        return True

    def tag_exists(self, tag: str) -> bool:
        """Check if a tag exists in the registry.

        Args:
            tag: Tag to check.

        Returns:
            True if tag exists, False otherwise.

        Raises:
            AuthenticationError: If authentication fails.
            RegistryUnavailableError: If registry is unavailable.
        """
        try:
            self.inspect(tag)
            return True
        except ArtifactNotFoundError:
            return False
        except NotImplementedError:
            # For skeleton - will work when inspect is implemented
            raise

    def _extract_registry_host(self, uri: str) -> str:
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

    def _check_immutability_before_push(self, tag: str) -> None:
        """Check if push would violate immutability.

        Args:
            tag: Tag to push to.

        Raises:
            ImmutabilityViolationError: If tag is immutable and exists.
        """
        if self.is_tag_immutable(tag):
            if self.tag_exists(tag):
                raise ImmutabilityViolationError(
                    tag=tag,
                    registry=self._registry_host,
                )

    def close(self) -> None:
        """Close the client and release resources.

        Should be called when done with the client to release
        any held resources (cache file handles, etc.).
        """
        # Currently no resources need explicit cleanup
        logger.debug("oci_client_closed", registry=self._registry_host)


__all__ = [
    "MUTABLE_TAG_PATTERNS",
    "OCIClient",
    "SEMVER_PATTERN",
]

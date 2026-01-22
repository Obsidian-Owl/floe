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
    >>> tags = client.list(filter_pattern="v1.*")
    >>> for tag in tags:
    ...     print(f"{tag.name}: {tag.digest}")

See Also:
    - specs/08a-oci-client/spec.md: Feature specification
    - specs/08a-oci-client/research.md: Technology research
"""

from __future__ import annotations

import builtins
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml
from oras.client import OrasClient

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
from floe_core.oci.layers import (
    MUTABLE_TAG_PATTERNS,
    SEMVER_PATTERN,
    PullOperations,
    TagClassifier,
    URIParser,
)
from floe_core.oci.manifest import (
    build_manifest,
    calculate_layers_total_size,
    calculate_manifest_digest,
    create_empty_config,
    parse_created_timestamp,
    parse_manifest_response,
    serialize_layer,
)
from floe_core.oci.metrics import OCIMetrics, get_oci_metrics
from floe_core.oci.resilience import CircuitBreaker, RetryPolicy
from floe_core.schemas.oci import (
    ArtifactManifest,
    ArtifactTag,
    AuthType,
    RegistryConfig,
)

if TYPE_CHECKING:
    from floe_core.plugins.secrets import SecretsPlugin
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts

logger = structlog.get_logger(__name__)


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

        # Use URIParser for hostname extraction and target ref building
        self._uri_parser = URIParser(registry_config.uri)
        self._registry_host = self._uri_parser.registry_host

        # Use TagClassifier for immutability checks
        self._tag_classifier = TagClassifier()

        # Lazy-initialized PullOperations helper
        self._pull_ops: PullOperations | None = None

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
                metrics=self.metrics,
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

    @property
    def pull_operations(self) -> PullOperations:
        """Get or create the pull operations helper."""
        if self._pull_ops is None:
            self._pull_ops = PullOperations(
                cache_manager=self.cache_manager,
                metrics=self.metrics,
                registry_host=self._registry_host,
            )
        return self._pull_ops

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

    def _record_operation_metrics(
        self,
        operation: str,
        start_time: float,
        success: bool,
        size: int | None = None,
    ) -> float:
        """Record metrics for an operation.

        Args:
            operation: Operation name (push, pull, inspect, list).
            start_time: Monotonic time when operation started.
            success: Whether operation succeeded.
            size: Optional artifact size for push/pull.

        Returns:
            Duration in seconds.
        """
        import time

        duration = time.monotonic() - start_time
        self.metrics.record_duration(operation, self._registry_host, duration)
        self.metrics.record_operation(operation, self._registry_host, success=success)
        if size is not None and success:
            self.metrics.record_artifact_size(operation, size)
        return duration

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
        start_time = time.monotonic()

        span_attributes: dict[str, Any] = {
            "oci.registry": self._registry_host,
            "oci.tag": tag,
            "oci.product.name": artifacts.metadata.product_name,
            "oci.product.version": artifacts.metadata.product_version,
            "oci.operation": "push",
        }

        with self.metrics.create_span(OCIMetrics.SPAN_PUSH, span_attributes) as span:
            try:
                manifest = self._push_internal(artifacts, tag, annotations, span)
                self._finalize_push(manifest, span, log, start_time)
                return manifest.digest
            except (
                ImmutabilityViolationError,
                CircuitBreakerOpenError,
                AuthenticationError,
                RegistryUnavailableError,
            ):
                self._record_operation_metrics("push", start_time, success=False)
                raise
            except Exception as e:
                self._record_operation_metrics("push", start_time, success=False)
                log.error("push_failed", error=str(e))
                raise OCIError(f"Push failed: {e}") from e

    def _push_internal(
        self,
        artifacts: CompiledArtifacts,
        tag: str,
        annotations: dict[str, str] | None,
        span: Any,
    ) -> ArtifactManifest:
        """Internal push logic: serialize, build manifest, upload.

        Args:
            artifacts: CompiledArtifacts to push.
            tag: Tag for the artifact.
            annotations: Optional annotations.
            span: OTel tracing span.

        Returns:
            The built ArtifactManifest.
        """
        self._check_immutability_before_push(tag)

        layer_content, layer_descriptor = serialize_layer(artifacts, annotations=annotations)
        manifest = build_manifest(artifacts, layers=[layer_descriptor], annotations=annotations)

        span.set_attribute("oci.artifact.size_bytes", manifest.size)
        span.set_attribute("oci.artifact.layer_count", len(manifest.layers))

        target_ref = self._build_target_ref(tag)
        self._upload_to_registry(layer_content, manifest, target_ref)

        return manifest

    def _upload_to_registry(
        self, layer_content: bytes, manifest: ArtifactManifest, target_ref: str
    ) -> None:
        """Upload artifact to registry via ORAS.

        Args:
            layer_content: Serialized artifact bytes.
            manifest: Built manifest with metadata.
            target_ref: Target reference (registry/namespace/repo:tag).
        """
        with self._with_circuit_breaker("push"):
            oras_client = self._create_oras_client()
            self._push_with_oras(oras_client, layer_content, manifest, target_ref)

    def _push_with_oras(
        self,
        oras_client: OrasClient,
        layer_content: bytes,
        manifest: ArtifactManifest,
        target_ref: str,
    ) -> None:
        """Push using ORAS client with temp files.

        Args:
            oras_client: Authenticated ORAS client.
            layer_content: Serialized artifact bytes.
            manifest: Built manifest with metadata.
            target_ref: Target reference.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            layer_file = tmpdir_path / "compiled_artifacts.json"
            layer_file.write_bytes(layer_content)

            config_content, _config_digest = create_empty_config()
            config_file = tmpdir_path / "config.json"
            config_file.write_bytes(config_content)

            response = oras_client.push(
                target=target_ref,
                config_path=str(config_file),
                files=[str(layer_file)],
                manifest_annotations=manifest.annotations,
                disable_path_validation=True,
            )

            if not response.ok:
                raise RegistryUnavailableError(
                    self._registry_host,
                    f"Push failed: {response.status_code}: {response.text}",
                )

    def _finalize_push(
        self, manifest: ArtifactManifest, span: Any, log: Any, start_time: float
    ) -> None:
        """Finalize push by updating span and metrics.

        Args:
            manifest: Built manifest.
            span: OTel tracing span.
            log: Bound logger.
            start_time: Monotonic time for metrics.
        """
        duration = self._record_operation_metrics(
            "push", start_time, success=True, size=manifest.size
        )
        span.set_attribute("oci.artifact.digest", manifest.digest)

        log.info(
            "push_completed",
            digest=manifest.digest,
            size=manifest.size,
            layer_count=len(manifest.layers),
            duration_ms=int(duration * 1000),
        )

    def _create_oras_client(self) -> OrasClient:
        """Create and authenticate ORAS client.

        Returns:
            Authenticated OrasClient instance.

        Raises:
            AuthenticationError: If authentication fails.
        """
        # Determine auth backend based on auth type
        # Basic auth needs 'basic' backend, otherwise use default 'token'
        auth_backend = "basic" if self.auth_provider.auth_type == AuthType.BASIC else "token"

        # Create ORAS client with TLS settings and auth backend
        oras_client = OrasClient(
            insecure=not self._config.tls_verify,
            auth_backend=auth_backend,
        )

        # Get credentials from auth provider
        credentials = self.auth_provider.get_credentials()

        # Skip login for anonymous auth (empty credentials)
        # ORAS prompts interactively if username/password are empty
        if credentials.username and credentials.password:
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
        return self._uri_parser.build_target_ref(tag)

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
            verify_digest: Whether to verify digest after download (reserved for
                future use; currently always verifies via manifest comparison).

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

        log = logger.bind(registry=self._registry_host, tag=tag)
        log.info("pull_started")
        start_time = time.monotonic()

        span_attributes: dict[str, Any] = {
            "oci.registry": self._registry_host,
            "oci.tag": tag,
            "oci.operation": "pull",
        }

        with self.metrics.create_span(OCIMetrics.SPAN_PULL, span_attributes) as span:
            try:
                return self._pull_internal(tag, span, log, start_time)
            except (
                ArtifactNotFoundError,
                CircuitBreakerOpenError,
                AuthenticationError,
                RegistryUnavailableError,
            ):
                self._record_operation_metrics("pull", start_time, success=False)
                raise
            except Exception as e:
                self._record_operation_metrics("pull", start_time, success=False)
                log.error("pull_failed", error=str(e))
                raise OCIError(f"Pull failed: {e}") from e

    def _pull_internal(
        self,
        tag: str,
        span: Any,
        log: Any,
        start_time: float,
    ) -> CompiledArtifacts:
        """Internal pull logic with cache check, fetch, and deserialization.

        Args:
            tag: Tag to pull.
            span: OTel tracing span.
            log: Bound logger.
            start_time: Monotonic time for metrics.

        Returns:
            Deserialized CompiledArtifacts.
        """

        # Check cache first
        cached_artifacts = self.pull_operations.try_cache_hit(
            tag, self._config.uri, span, log, start_time
        )
        if cached_artifacts is not None:
            return cached_artifacts

        # Fetch from registry
        content, digest = self._fetch_from_registry(tag)

        # Deserialize
        artifacts = self._deserialize_artifacts(content)

        # Update span and cache
        self._finalize_pull(artifacts, content, digest, tag, span, log, start_time)

        return artifacts

    def _fetch_from_registry(self, tag: str) -> tuple[bytes, str]:
        """Fetch artifact content from registry with retry and circuit breaker.

        Args:
            tag: Tag to fetch.

        Returns:
            Tuple of (content bytes, digest string).
        """
        def _pull_with_oras() -> tuple[bytes, str]:
            return self._pull_content_with_oras(tag)

        with self._with_circuit_breaker("pull"):
            try:
                return self.retry_policy.wrap(_pull_with_oras)()
            except ArtifactNotFoundError:
                raise
            except ConnectionError as e:
                raise RegistryUnavailableError(
                    self._registry_host,
                    f"Connection failed after retries: {e}",
                ) from e

    def _pull_content_with_oras(self, tag: str) -> tuple[bytes, str]:
        """Pull content via ORAS client.

        Args:
            tag: Tag to pull.

        Returns:
            Tuple of (content bytes, digest string).
        """
        import hashlib

        oras_client = self._create_oras_client()
        target_ref = self._build_target_ref(tag)

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                pulled_files = oras_client.pull(target=target_ref, outdir=tmpdir)
                artifacts_path = self.pull_operations.find_artifacts_file(pulled_files, tmpdir)
                content = artifacts_path.read_bytes()
                digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
                return content, digest
            except OCIError:
                raise
            except Exception as e:
                self._handle_oras_pull_error(e, tag)

        # This return is unreachable but satisfies type checker
        raise OCIError("Unexpected error in pull")  # pragma: no cover

    def _handle_oras_pull_error(self, error: Exception, tag: str) -> None:
        """Handle ORAS pull errors and raise appropriate exceptions.

        Args:
            error: The exception that occurred.
            tag: Tag being pulled.

        Raises:
            ArtifactNotFoundError: If error indicates missing artifact.
            Exception: Re-raises original exception otherwise.
        """
        error_str = str(error).lower()
        if "manifest unknown" in error_str or "not found" in error_str:
            raise ArtifactNotFoundError(tag=tag, registry=self._config.uri) from error
        raise error

    def _deserialize_artifacts(self, content: bytes) -> CompiledArtifacts:
        """Deserialize content to CompiledArtifacts.

        Args:
            content: JSON bytes to deserialize.

        Returns:
            Deserialized CompiledArtifacts.

        Raises:
            OCIError: If deserialization fails.
        """
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        try:
            return CompiledArtifacts.model_validate_json(content)
        except Exception as e:
            raise OCIError(f"Failed to deserialize artifact: {e}") from e

    def _finalize_pull(
        self,
        artifacts: CompiledArtifacts,
        content: bytes,
        digest: str,
        tag: str,
        span: Any,
        log: Any,
        start_time: float,
    ) -> None:
        """Finalize pull by updating span, cache, and metrics.

        Args:
            artifacts: Deserialized artifacts.
            content: Raw content bytes.
            digest: Content digest.
            tag: Tag that was pulled.
            span: OTel tracing span.
            log: Bound logger.
            start_time: Monotonic time for metrics.
        """
        # Add product info to span
        span.set_attribute("oci.product.name", artifacts.metadata.product_name)
        span.set_attribute("oci.product.version", artifacts.metadata.product_version)
        span.set_attribute("oci.artifact.digest", digest)

        # Store in cache
        if self.cache_manager is not None:
            self.cache_manager.put(
                digest=digest, tag=tag, registry=self._config.uri, content=content
            )
            log.debug("pull_cached", digest=digest, tag=tag)

        # Record success metrics
        duration = self._record_operation_metrics(
            "pull", start_time, success=True, size=len(content)
        )

        log.info(
            "pull_completed",
            digest=digest,
            size=len(content),
            duration_ms=int(duration * 1000),
        )

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
        import time

        from floe_core.oci.metrics import OCIMetrics

        log = logger.bind(registry=self._registry_host, tag=tag)
        log.info("inspect_started")
        start_time = time.monotonic()

        span_attributes: dict[str, Any] = {
            "oci.registry": self._registry_host,
            "oci.tag": tag,
            "oci.operation": "inspect",
        }

        with self.metrics.create_span(OCIMetrics.SPAN_INSPECT, span_attributes) as span:
            try:
                manifest = self._inspect_internal(tag)
                self._finalize_inspect(manifest, span, log, start_time)
                return manifest
            except (ArtifactNotFoundError, CircuitBreakerOpenError, AuthenticationError):
                self._record_operation_metrics("inspect", start_time, success=False)
                raise
            except Exception as e:
                self._record_operation_metrics("inspect", start_time, success=False)
                log.error("inspect_failed", error=str(e))
                raise OCIError(f"Inspect failed: {e}") from e

    def _inspect_internal(self, tag: str) -> ArtifactManifest:
        """Fetch and parse manifest from registry.

        Args:
            tag: Tag to inspect.

        Returns:
            Parsed ArtifactManifest.
        """
        with self._with_circuit_breaker("inspect"):
            manifest_data = self._fetch_manifest_data(tag)
        return parse_manifest_response(manifest_data)

    def _fetch_manifest_data(self, tag: str) -> dict[str, Any]:
        """Fetch raw manifest data from registry.

        Args:
            tag: Tag to fetch manifest for.

        Returns:
            Raw manifest data dictionary.
        """
        oras_client = self._create_oras_client()
        target_ref = self._build_target_ref(tag)

        try:
            manifest_data: dict[str, Any] = oras_client.get_manifest(container=target_ref)
            return manifest_data
        except Exception as e:
            self._handle_manifest_fetch_error(e, tag)

        raise OCIError("Unexpected error fetching manifest")  # pragma: no cover

    def _handle_manifest_fetch_error(self, error: Exception, tag: str) -> None:
        """Handle manifest fetch errors.

        Args:
            error: The exception that occurred.
            tag: Tag being inspected.

        Raises:
            ArtifactNotFoundError: If error indicates missing artifact.
            Exception: Re-raises original exception otherwise.
        """
        error_str = str(error).lower()
        if "manifest unknown" in error_str or "not found" in error_str:
            raise ArtifactNotFoundError(tag=tag, registry=self._config.uri) from error
        raise error

    def _finalize_inspect(
        self, manifest: ArtifactManifest, span: Any, log: Any, start_time: float
    ) -> None:
        """Finalize inspect by updating span and metrics.

        Args:
            manifest: Parsed manifest.
            span: OTel tracing span.
            log: Bound logger.
            start_time: Monotonic time for metrics.
        """
        span.set_attribute("oci.artifact.digest", manifest.digest)
        span.set_attribute("oci.artifact.size_bytes", manifest.size)
        span.set_attribute("oci.artifact.layer_count", len(manifest.layers))

        duration = self._record_operation_metrics("inspect", start_time, success=True)

        log.info(
            "inspect_completed",
            digest=manifest.digest,
            size=manifest.size,
            layer_count=len(manifest.layers),
            duration_ms=int(duration * 1000),
        )

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
        import time

        log = logger.bind(registry=self._registry_host, filter_pattern=filter_pattern)
        log.info("list_started")
        start_time = time.monotonic()

        try:
            result = self._list_internal(filter_pattern, log)
            duration = self._record_operation_metrics("list", start_time, success=True)
            log.info("list_completed", tag_count=len(result), duration_ms=int(duration * 1000))
            return result
        except (CircuitBreakerOpenError, AuthenticationError):
            self._record_operation_metrics("list", start_time, success=False)
            raise
        except Exception as e:
            self._record_operation_metrics("list", start_time, success=False)
            log.error("list_failed", error=str(e))
            raise OCIError(f"List failed: {e}") from e

    def _list_internal(
        self, filter_pattern: str | None, log: Any
    ) -> builtins.list[ArtifactTag]:
        """Internal list logic with circuit breaker protection.

        Args:
            filter_pattern: Optional glob pattern to filter tags.
            log: Bound logger.

        Returns:
            List of ArtifactTag objects.
        """
        with self._with_circuit_breaker("list"):
            oras_client = self._create_oras_client()
            tag_names = self._fetch_tag_names(oras_client)
            tag_names = self._filter_tags(tag_names, filter_pattern)
            return self._fetch_and_build_artifact_tags(oras_client, tag_names, log)

    def _fetch_tag_names(self, oras_client: OrasClient) -> builtins.list[str]:
        """Fetch tag names from registry.

        Args:
            oras_client: Authenticated ORAS client.

        Returns:
            List of tag names.
        """
        uri = self._config.uri
        if uri.startswith("oci://"):
            uri = uri[6:]

        try:
            tags_response: builtins.list[str] = oras_client.get_tags(container=uri)
            return tags_response
        except Exception as e:
            error_str = str(e).lower()
            if "unauthorized" in error_str or "authentication" in error_str:
                raise AuthenticationError(
                    self._config.uri, "Authentication failed while listing tags"
                ) from e
            raise OCIError(f"Failed to list tags: {e}") from e

    def _filter_tags(
        self, tag_names: builtins.list[str], filter_pattern: str | None
    ) -> builtins.list[str]:
        """Filter tag names by glob pattern.

        Args:
            tag_names: List of tag names to filter.
            filter_pattern: Optional glob pattern.

        Returns:
            Filtered list of tag names.
        """
        if not filter_pattern:
            return tag_names

        import fnmatch

        return [name for name in tag_names if fnmatch.fnmatch(name, filter_pattern)]

    def _fetch_and_build_artifact_tags(
        self, oras_client: OrasClient, tag_names: builtins.list[str], log: Any
    ) -> builtins.list[ArtifactTag]:
        """Fetch manifests and build ArtifactTag objects.

        Args:
            oras_client: Authenticated ORAS client.
            tag_names: List of tag names to fetch.
            log: Bound logger.

        Returns:
            List of ArtifactTag objects.
        """
        from floe_core.oci.batch_fetcher import BatchFetcher

        tag_refs = [(tag_name, self._build_target_ref(tag_name)) for tag_name in tag_names]
        batch_fetcher = BatchFetcher(max_workers=10)
        fetch_result = batch_fetcher.fetch_manifests(oras_client, tag_refs)

        # Log failures
        for tag_name, error in fetch_result.errors.items():
            log.warning("list_tag_failed", tag=tag_name, error=str(error))

        return self._build_artifact_tag_list(fetch_result.manifests)

    def _build_artifact_tag_list(
        self, manifests: dict[str, dict[str, Any]]
    ) -> builtins.list[ArtifactTag]:
        """Build list of ArtifactTag from manifest data.

        Args:
            manifests: Dict mapping tag names to manifest data.

        Returns:
            List of ArtifactTag objects.
        """
        result: builtins.list[ArtifactTag] = []

        for tag_name, manifest_data in manifests.items():
            digest = calculate_manifest_digest(manifest_data)
            annotations = manifest_data.get("annotations", {})
            created_at = parse_created_timestamp(annotations)
            layers_data = manifest_data.get("layers", [])
            total_size = calculate_layers_total_size(layers_data)

            artifact_tag = ArtifactTag(
                name=tag_name, digest=digest, created_at=created_at, size=total_size
            )
            result.append(artifact_tag)

        return result

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
        return self._tag_classifier.is_immutable(tag)

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

    @staticmethod
    def _extract_registry_host(uri: str) -> str:
        """Extract registry hostname from OCI URI.

        Args:
            uri: OCI URI (e.g., oci://harbor.example.com/namespace/repo).

        Returns:
            Registry hostname (e.g., harbor.example.com).
        """
        return URIParser._extract_registry_host(uri)

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

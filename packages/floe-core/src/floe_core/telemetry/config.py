"""Telemetry configuration models (Pydantic v2).

These models define the configuration for OpenTelemetry telemetry emission.
Platform Team configures via manifest.yaml; Data Engineers inherit configuration.

Contract Version: 1.0.0

See Also:
    - specs/001-opentelemetry/contracts/telemetry_config.py: Contract source
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from typing_extensions import Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class ResourceAttributes(BaseModel):
    """OpenTelemetry resource attributes for service identification.

    Applied to all traces, metrics, and logs from the service.
    Follows OpenTelemetry semantic conventions plus Floe-specific attributes.

    Attributes:
        service_name: Service identifier (e.g., 'floe-core', 'floe-dagster')
        service_version: Service version following semver
        deployment_environment: Target environment (dev, staging, prod)
        floe_namespace: Polaris catalog namespace (mandatory per ADR-0006)
        floe_product_name: Data product name
        floe_product_version: Data product version
        floe_mode: Execution mode matching environment

    Examples:
        >>> attrs = ResourceAttributes(
        ...     service_name="floe-core",
        ...     service_version="1.0.0",
        ...     deployment_environment="prod",
        ...     floe_namespace="analytics",
        ...     floe_product_name="customer-360",
        ...     floe_product_version="2.1.0",
        ...     floe_mode="prod",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # OpenTelemetry standard attributes
    service_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Service identifier",
    )
    service_version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+.*$",
        description="Service version (semver)",
    )
    deployment_environment: Literal["dev", "staging", "prod"] = Field(
        ...,
        description="Deployment environment",
    )

    # Floe-specific semantic conventions (per ADR-0006)
    floe_namespace: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Polaris catalog namespace (mandatory)",
    )
    floe_product_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Data product name",
    )
    floe_product_version: str = Field(
        ...,
        description="Data product version",
    )
    floe_mode: Literal["dev", "staging", "prod"] = Field(
        ...,
        description="Execution mode",
    )

    def to_otel_dict(self) -> dict[str, str]:
        """Convert to OpenTelemetry resource attributes dictionary.

        Returns:
            Dictionary with OTel semantic convention keys.
        """
        return {
            "service.name": self.service_name,
            "service.version": self.service_version,
            "deployment.environment": self.deployment_environment,
            "floe.namespace": self.floe_namespace,
            "floe.product.name": self.floe_product_name,
            "floe.product.version": self.floe_product_version,
            "floe.mode": self.floe_mode,
        }


class TelemetryAuth(BaseModel):
    """Authentication for OTLP exports.

    Supports API key and bearer token authentication for
    SaaS backends (Datadog, Grafana Cloud, etc.).

    Attributes:
        auth_type: Authentication mechanism
        api_key: API key credential (SecretStr)
        bearer_token: Bearer token credential (SecretStr)
        header_name: HTTP header for credentials

    Examples:
        >>> auth = TelemetryAuth(
        ...     auth_type="api_key",
        ...     api_key=SecretStr("dd-api-key-xxx"),
        ...     header_name="DD-API-KEY",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    auth_type: Literal["api_key", "bearer"] = Field(
        ...,
        description="Authentication mechanism",
    )
    api_key: SecretStr | None = Field(
        default=None,
        description="API key (for api_key auth_type)",
    )
    bearer_token: SecretStr | None = Field(
        default=None,
        description="Bearer token (for bearer auth_type)",
    )
    header_name: str = Field(
        default="Authorization",
        description="HTTP header name for credentials",
    )

    @model_validator(mode="after")
    def validate_credentials(self) -> Self:
        """Validate that required credentials are provided."""
        if self.auth_type == "api_key" and not self.api_key:
            raise ValueError("api_key required when auth_type is 'api_key'")
        if self.auth_type == "bearer" and not self.bearer_token:
            raise ValueError("bearer_token required when auth_type is 'bearer'")
        return self


class BatchSpanProcessorConfig(BaseModel):
    """Configuration for BatchSpanProcessor.

    BatchSpanProcessor is used for async, non-blocking span export.
    Spans are buffered in a queue and exported in batches.

    Configuration guidelines by throughput:
    - Low (<100 spans/s): queue=512, batch=256, delay=10s
    - Medium (100-1000 spans/s): queue=2048, batch=512, delay=5s (default)
    - High (>1000 spans/s): queue=8192, batch=1024, delay=2s

    Attributes:
        max_queue_size: Maximum spans buffered in memory (default: 2048)
        max_export_batch_size: Spans per export batch (default: 512)
        schedule_delay_millis: Export interval in ms (default: 5000)
        export_timeout_millis: Per-batch export timeout in ms (default: 30000)

    Examples:
        >>> # Default configuration (medium throughput)
        >>> config = BatchSpanProcessorConfig()

        >>> # High throughput configuration
        >>> config = BatchSpanProcessorConfig(
        ...     max_queue_size=8192,
        ...     max_export_batch_size=1024,
        ...     schedule_delay_millis=2000,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_queue_size: int = Field(
        default=2048,
        gt=0,
        description="Maximum spans buffered in memory",
    )
    max_export_batch_size: int = Field(
        default=512,
        gt=0,
        description="Spans per export batch",
    )
    schedule_delay_millis: int = Field(
        default=5000,
        gt=0,
        description="Export interval in milliseconds",
    )
    export_timeout_millis: int = Field(
        default=30000,
        gt=0,
        description="Per-batch export timeout in milliseconds",
    )

    @model_validator(mode="after")
    def validate_batch_size_le_queue_size(self) -> Self:
        """Validate that batch size does not exceed queue size."""
        if self.max_export_batch_size > self.max_queue_size:
            raise ValueError(
                f"max_export_batch_size ({self.max_export_batch_size}) "
                f"cannot exceed max_queue_size ({self.max_queue_size})"
            )
        return self


class LoggingConfig(BaseModel):
    """Logging configuration for structured log output.

    Controls structlog configuration with trace context injection.
    Log level can be set per environment or globally.

    Attributes:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Output format - JSON (True) or console (False)

    Examples:
        >>> logging_config = LoggingConfig(log_level="DEBUG", json_output=True)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    log_level: str = Field(
        default="INFO",
        pattern=r"^(?i)(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Minimum log level (case-insensitive)",
    )
    json_output: bool = Field(
        default=True,
        description="Output format - JSON (True) or console (False)",
    )


class SamplingConfig(BaseModel):
    """Environment-based sampling configuration.

    Controls trace sampling ratio per environment to balance
    observability coverage with data volume/cost.

    Attributes:
        dev: Sampling ratio for development (default: 100%)
        staging: Sampling ratio for staging (default: 50%)
        prod: Sampling ratio for production (default: 10%)

    Examples:
        >>> sampling = SamplingConfig(dev=1.0, staging=0.5, prod=0.1)
        >>> sampling.get_ratio("prod")
        0.1
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dev: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Development sampling ratio (0.0-1.0)",
    )
    staging: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Staging sampling ratio (0.0-1.0)",
    )
    prod: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Production sampling ratio (0.0-1.0)",
    )

    def get_ratio(self, environment: str) -> float:
        """Get sampling ratio for environment.

        Args:
            environment: Target environment name

        Returns:
            Sampling ratio (0.0-1.0), defaults to 1.0 if unknown
        """
        return getattr(self, environment, 1.0)


class TelemetryConfig(BaseModel):
    """Configuration for OpenTelemetry telemetry emission.

    Central configuration included in CompiledArtifacts.
    Platform Team configures via manifest.yaml; Data Engineers inherit.

    Three-Layer Architecture (per ADR-0006, ADR-0035):
    - Layer 1 (Emission): OpenTelemetry SDK - ENFORCED
    - Layer 2 (Collection): OTLP Collector - ENFORCED
    - Layer 3 (Backend): Storage/Viz - PLUGGABLE (via TelemetryBackendPlugin)

    Attributes:
        enabled: Whether telemetry is enabled (default: True)
        otlp_endpoint: OTLP Collector endpoint
        otlp_protocol: Export protocol (grpc or http)
        sampling: Environment-based sampling configuration
        resource_attributes: Service identification attributes
        authentication: Optional OTLP authentication
        batch_processor: BatchSpanProcessor configuration for async export

    Examples:
        >>> config = TelemetryConfig(
        ...     enabled=True,
        ...     otlp_endpoint="http://otel-collector:4317",
        ...     resource_attributes=ResourceAttributes(...),
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(
        default=True,
        description="Enable telemetry emission",
    )
    otlp_endpoint: str = Field(
        default="http://otel-collector:4317",
        description="OTLP Collector endpoint (Layer 2)",
    )
    otlp_protocol: Literal["grpc", "http"] = Field(
        default="grpc",
        description="OTLP export protocol",
    )
    sampling: SamplingConfig = Field(
        default_factory=SamplingConfig,
        description="Environment-based sampling",
    )
    resource_attributes: ResourceAttributes = Field(
        ...,
        description="Service identification attributes",
    )
    authentication: TelemetryAuth | None = Field(
        default=None,
        description="Optional OTLP authentication",
    )
    batch_processor: BatchSpanProcessorConfig = Field(
        default_factory=BatchSpanProcessorConfig,
        description="BatchSpanProcessor configuration for async export",
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Structured logging configuration with trace context",
    )

    def get_sampling_ratio(self, environment: str) -> float:
        """Get sampling ratio for the specified environment.

        Args:
            environment: Target environment (dev, staging, prod)

        Returns:
            Sampling ratio (0.0-1.0)
        """
        return self.sampling.get_ratio(environment)

"""CompiledArtifacts schema for compiled output from floe compile.

CompiledArtifacts is the single source of truth for pipeline execution.
It contains resolved, validated configuration after manifest inheritance.

Contract Version: 0.1.0

See Also:
    - docs/contracts/compiled-artifacts.md: Full contract specification
    - ADR-0006: Telemetry architecture
    - ADR-0035: Plugin system architecture
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from floe_core.telemetry.config import TelemetryConfig


class CompilationMetadata(BaseModel):
    """Information about the compilation process.

    Attributes:
        compiled_at: Timestamp of compilation
        floe_version: Version of floe used for compilation
        source_hash: SHA256 hash of input files
        product_name: Name of the data product
        product_version: Version of the data product
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    compiled_at: datetime = Field(
        ...,
        description="Timestamp of compilation",
    )
    floe_version: str = Field(
        ...,
        description="Version of floe used for compilation",
    )
    source_hash: str = Field(
        ...,
        description="SHA256 hash of input files",
    )
    product_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Name of the data product",
    )
    product_version: str = Field(
        ...,
        description="Version of the data product",
    )


class ProductIdentity(BaseModel):
    """Product identity information from catalog registration.

    See ADR-0030 for the namespace-based identity model.

    Attributes:
        product_id: Fully qualified product ID (e.g., 'sales.customer_360')
        domain: Domain name (e.g., 'sales')
        repository: Source repository URL
        namespace_registered: Whether registered in catalog
        registration_timestamp: When first registered
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(
        ...,
        min_length=1,
        description="Fully qualified product ID",
    )
    domain: str = Field(
        ...,
        min_length=1,
        description="Domain name",
    )
    repository: str = Field(
        ...,
        description="Source repository URL",
    )
    namespace_registered: bool = Field(
        default=False,
        description="Whether registered in catalog",
    )
    registration_timestamp: datetime | None = Field(
        default=None,
        description="When first registered",
    )


class ManifestRef(BaseModel):
    """Reference to a manifest in the inheritance chain.

    Attributes:
        name: Manifest name
        version: Manifest version
        scope: Manifest scope (enterprise or domain)
        ref: OCI reference
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Manifest name")
    version: str = Field(..., description="Manifest version")
    scope: Literal["enterprise", "domain"] = Field(..., description="Manifest scope")
    ref: str = Field(..., description="OCI reference")


class ObservabilityConfig(BaseModel):
    """Observability settings including telemetry configuration.

    This configuration controls all observability aspects:
    - OpenTelemetry traces, metrics, and logs (via TelemetryConfig)
    - OpenLineage data lineage tracking
    - Lineage namespace for correlation

    Attributes:
        telemetry: Full OpenTelemetry configuration (TelemetryConfig)
        lineage: Whether OpenLineage is enabled
        lineage_namespace: Namespace for lineage events

    Examples:
        >>> from floe_core.telemetry.config import TelemetryConfig, ResourceAttributes
        >>> config = ObservabilityConfig(
        ...     telemetry=TelemetryConfig(
        ...         enabled=True,
        ...         resource_attributes=ResourceAttributes(
        ...             service_name="my-pipeline",
        ...             service_version="1.0.0",
        ...             deployment_environment="prod",
        ...             floe_namespace="analytics",
        ...             floe_product_name="customer-360",
        ...             floe_product_version="2.1.0",
        ...             floe_mode="prod",
        ...         ),
        ...     ),
        ...     lineage=True,
        ...     lineage_namespace="my-pipeline",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    telemetry: TelemetryConfig = Field(
        ...,
        description="OpenTelemetry configuration (traces, metrics, logs)",
    )
    lineage: bool = Field(
        default=True,
        description="Whether OpenLineage is enabled",
    )
    lineage_namespace: str = Field(
        ...,
        min_length=1,
        description="Namespace for lineage events",
    )


# Deployment mode types
DeploymentMode = Literal["simple", "centralized", "mesh"]
"""Valid deployment modes for data products.

- simple: Single floe.yaml, no inheritance
- centralized: Enterprise manifest inheritance
- mesh: Full Data Mesh with domains and contracts
"""


class CompiledArtifacts(BaseModel):
    """Output of floe compile - unified for all deployment modes.

    CompiledArtifacts is the single source of truth for pipeline execution.
    It contains resolved, validated configuration after manifest inheritance.

    The observability field contains TelemetryConfig which provides:
    - OpenTelemetry SDK configuration (Layer 1 - ENFORCED)
    - OTLP Collector endpoint (Layer 2 - ENFORCED)
    - Backend plugin selection (Layer 3 - PLUGGABLE)

    Attributes:
        version: Schema version (semver)
        metadata: Compilation metadata
        identity: Product identity from catalog
        mode: Deployment mode (simple, centralized, mesh)
        inheritance_chain: Manifest inheritance lineage
        observability: Observability configuration with TelemetryConfig

    Examples:
        >>> from datetime import datetime
        >>> from floe_core.telemetry.config import TelemetryConfig, ResourceAttributes
        >>> artifacts = CompiledArtifacts(
        ...     version="0.1.0",
        ...     metadata=CompilationMetadata(
        ...         compiled_at=datetime.now(),
        ...         floe_version="0.1.0",
        ...         source_hash="sha256:abc123",
        ...         product_name="my-pipeline",
        ...         product_version="1.0.0",
        ...     ),
        ...     identity=ProductIdentity(
        ...         product_id="default.my_pipeline",
        ...         domain="default",
        ...         repository="github.com/acme/my-pipeline",
        ...     ),
        ...     mode="simple",
        ...     observability=ObservabilityConfig(
        ...         telemetry=TelemetryConfig(
        ...             resource_attributes=ResourceAttributes(...),
        ...         ),
        ...         lineage_namespace="my-pipeline",
        ...     ),
        ... )

    See Also:
        - docs/contracts/compiled-artifacts.md: Full specification
        - TelemetryConfig: OpenTelemetry configuration
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[
        str,
        Field(
            default="0.1.0",
            pattern=r"^\d+\.\d+\.\d+$",
            description="Schema version (semver)",
        ),
    ]

    metadata: CompilationMetadata = Field(
        ...,
        description="Compilation metadata",
    )

    identity: ProductIdentity = Field(
        ...,
        description="Product identity from catalog",
    )

    mode: DeploymentMode = Field(
        default="simple",
        description="Deployment mode (simple, centralized, mesh)",
    )

    inheritance_chain: Annotated[
        list[ManifestRef],
        Field(
            default_factory=list,
            description="Manifest inheritance lineage",
        ),
    ]

    observability: ObservabilityConfig = Field(
        ...,
        description="Observability configuration with TelemetryConfig",
    )

    # Note: Additional fields (plugins, transforms, governance, etc.) will be
    # added as their respective features are implemented. This initial version
    # focuses on the observability/telemetry integration per T076.


__all__ = [
    "CompiledArtifacts",
    "CompilationMetadata",
    "DeploymentMode",
    "ManifestRef",
    "ObservabilityConfig",
    "ProductIdentity",
]

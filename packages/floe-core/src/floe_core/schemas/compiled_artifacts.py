"""CompiledArtifacts schema for compiled output from floe compile.

CompiledArtifacts is the single source of truth for pipeline execution.
It contains resolved, validated configuration after manifest inheritance.

Contract Version: 0.2.0

Version History:
    - 0.1.0: Initial version (metadata, identity, mode, observability)
    - 0.2.0: Add plugins, transforms, dbt_profiles, governance (Epic 2B)

See Also:
    - docs/contracts/compiled-artifacts.md: Full contract specification
    - ADR-0006: Telemetry architecture
    - ADR-0012: CompiledArtifacts contract
    - ADR-0035: Plugin system architecture
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

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


class PluginRef(BaseModel):
    """Reference to a resolved plugin.

    Contains the plugin type, version, and configuration after
    resolution from the platform manifest.

    Attributes:
        type: Plugin type name (e.g., "duckdb", "snowflake")
        version: Plugin version (semver)
        config: Plugin-specific configuration dictionary

    Example:
        >>> plugin = PluginRef(
        ...     type="duckdb",
        ...     version="0.9.0",
        ...     config={"threads": 4, "memory_limit": "8GB"}
        ... )
        >>> plugin.type
        'duckdb'

    See Also:
        - data-model.md: PluginRef entity specification
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str = Field(
        ...,
        min_length=1,
        description="Plugin type name (e.g., 'duckdb', 'snowflake')",
        examples=["duckdb", "snowflake", "dagster"],
    )
    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Plugin version (semver)",
        examples=["0.9.0", "1.2.3"],
    )
    config: dict[str, Any] | None = Field(
        default=None,
        description="Plugin-specific configuration",
        examples=[{"threads": 4, "memory_limit": "8GB"}],
    )


class ResolvedPlugins(BaseModel):
    """Resolved plugin selections after inheritance.

    Contains references to all resolved plugins that will be used
    for pipeline execution. Required plugins (compute, orchestrator)
    must be present; optional plugins may be None.

    Attributes:
        compute: Resolved compute plugin (required)
        orchestrator: Resolved orchestrator plugin (required)
        catalog: Resolved catalog plugin (optional)
        storage: Resolved storage plugin (optional)
        ingestion: Resolved ingestion plugin (optional)
        semantic: Resolved semantic layer plugin (optional)

    Example:
        >>> plugins = ResolvedPlugins(
        ...     compute=PluginRef(type="duckdb", version="0.9.0"),
        ...     orchestrator=PluginRef(type="dagster", version="1.5.0"),
        ...     catalog=PluginRef(type="polaris", version="0.1.0"),
        ... )
        >>> plugins.compute.type
        'duckdb'

    See Also:
        - data-model.md: ResolvedPlugins entity specification
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    compute: PluginRef = Field(
        ...,
        description="Resolved compute plugin (required)",
    )
    orchestrator: PluginRef = Field(
        ...,
        description="Resolved orchestrator plugin (required)",
    )
    catalog: PluginRef | None = Field(
        default=None,
        description="Resolved catalog plugin (optional)",
    )
    storage: PluginRef | None = Field(
        default=None,
        description="Resolved storage plugin (optional)",
    )
    ingestion: PluginRef | None = Field(
        default=None,
        description="Resolved ingestion plugin (optional)",
    )
    semantic: PluginRef | None = Field(
        default=None,
        description="Resolved semantic layer plugin (optional)",
    )


class ResolvedModel(BaseModel):
    """A transform model with resolved compute target.

    Represents a single dbt model after compilation, with the compute
    target resolved (never None - uses platform default if not specified).

    Attributes:
        name: Model name (dbt model identifier)
        compute: Resolved compute target (never None)
        tags: dbt tags for selection
        depends_on: Explicit dependencies (model names)

    Example:
        >>> model = ResolvedModel(
        ...     name="stg_customers",
        ...     compute="duckdb",
        ...     tags=["staging", "customers"],
        ...     depends_on=["raw_customers"]
        ... )
        >>> model.compute
        'duckdb'

    See Also:
        - data-model.md: ResolvedModel entity specification
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        description="Model name (dbt model identifier)",
        examples=["stg_customers", "fct_orders"],
    )
    compute: str = Field(
        ...,
        min_length=1,
        description="Resolved compute target (never None)",
        examples=["duckdb", "snowflake"],
    )
    tags: list[str] | None = Field(
        default=None,
        description="dbt tags for selection",
        examples=[["staging", "customers"]],
    )
    depends_on: list[str] | None = Field(
        default=None,
        description="Explicit dependencies (model names)",
        examples=[["raw_customers", "raw_orders"]],
    )


class ResolvedTransforms(BaseModel):
    """Compiled transform configuration.

    Contains the list of resolved models and the default compute target
    used for models that don't specify an override.

    Attributes:
        models: List of resolved models with compute targets
        default_compute: Default compute target from platform

    Example:
        >>> transforms = ResolvedTransforms(
        ...     models=[
        ...         ResolvedModel(name="stg_customers", compute="duckdb"),
        ...         ResolvedModel(name="fct_orders", compute="duckdb"),
        ...     ],
        ...     default_compute="duckdb"
        ... )
        >>> len(transforms.models)
        2

    See Also:
        - data-model.md: ResolvedTransforms entity specification
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    models: list[ResolvedModel] = Field(
        ...,
        min_length=1,
        description="List of resolved models with compute targets",
    )
    default_compute: str = Field(
        ...,
        min_length=1,
        description="Default compute target from platform",
        examples=["duckdb", "snowflake"],
    )


class ResolvedGovernance(BaseModel):
    """Governance settings after inheritance resolution.

    Contains security and compliance settings resolved from the
    inheritance chain, with child manifests unable to weaken parent policies.

    Attributes:
        pii_encryption: PII encryption policy (required or optional)
        audit_logging: Audit logging policy (enabled or disabled)
        policy_enforcement_level: Enforcement level (off, warn, strict)
        data_retention_days: Data retention period in days

    Example:
        >>> governance = ResolvedGovernance(
        ...     pii_encryption="required",
        ...     audit_logging="enabled",
        ...     policy_enforcement_level="strict",
        ...     data_retention_days=90
        ... )
        >>> governance.pii_encryption
        'required'

    See Also:
        - data-model.md: ResolvedGovernance entity specification
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pii_encryption: Literal["required", "optional"] | None = Field(
        default=None,
        description="PII encryption policy",
    )
    audit_logging: Literal["enabled", "disabled"] | None = Field(
        default=None,
        description="Audit logging policy",
    )
    policy_enforcement_level: Literal["off", "warn", "strict"] | None = Field(
        default=None,
        description="Policy enforcement level",
    )
    data_retention_days: int | None = Field(
        default=None,
        ge=1,
        description="Data retention period in days",
    )


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

    Contract Version: 0.2.0 (see docstring header for version history)

    Attributes:
        version: Schema version (semver) - default 0.2.0
        metadata: Compilation metadata
        identity: Product identity from catalog
        mode: Deployment mode (simple, centralized, mesh)
        inheritance_chain: Manifest inheritance lineage
        observability: Observability configuration with TelemetryConfig
        plugins: Resolved plugin selections (v0.2.0+)
        transforms: Compiled transform configuration (v0.2.0+)
        dbt_profiles: Generated profiles.yml content (v0.2.0+)
        governance: Resolved governance settings (v0.2.0+, optional)

    Examples:
        >>> from datetime import datetime
        >>> from floe_core.telemetry.config import TelemetryConfig, ResourceAttributes
        >>> artifacts = CompiledArtifacts(
        ...     version="0.2.0",
        ...     metadata=CompilationMetadata(
        ...         compiled_at=datetime.now(),
        ...         floe_version="0.2.0",
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
        ...     plugins=ResolvedPlugins(
        ...         compute=PluginRef(type="duckdb", version="0.9.0"),
        ...         orchestrator=PluginRef(type="dagster", version="1.5.0"),
        ...     ),
        ...     transforms=ResolvedTransforms(
        ...         models=[ResolvedModel(name="stg_customers", compute="duckdb")],
        ...         default_compute="duckdb",
        ...     ),
        ...     dbt_profiles={"default": {"target": "dev", "outputs": {...}}},
        ... )

    See Also:
        - docs/contracts/compiled-artifacts.md: Full specification
        - ADR-0012: CompiledArtifacts contract design
        - TelemetryConfig: OpenTelemetry configuration
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[
        str,
        Field(
            default="0.2.0",
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

    # Epic 2B additions (v0.2.0)
    plugins: ResolvedPlugins | None = Field(
        default=None,
        description="Resolved plugin selections (v0.2.0+, optional for backward compat)",
    )

    transforms: ResolvedTransforms | None = Field(
        default=None,
        description="Compiled transform configuration (v0.2.0+, optional for backward compat)",
    )

    dbt_profiles: dict[str, Any] | None = Field(
        default=None,
        description="Generated profiles.yml content (v0.2.0+, optional for backward compat)",
    )

    governance: ResolvedGovernance | None = Field(
        default=None,
        description="Resolved governance settings (v0.2.0+, optional)",
    )

    def to_json_file(self, path: Path) -> None:
        """Write CompiledArtifacts to a JSON file.

        Uses Pydantic's model_dump with mode='json' and by_alias=True
        for proper JSON serialization of datetime and other types.

        Args:
            path: Path to write the JSON file.

        Example:
            >>> artifacts = CompiledArtifacts(...)
            >>> artifacts.to_json_file(Path("target/compiled_artifacts.json"))

        See Also:
            - from_json_file: Load artifacts from JSON
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json", by_alias=True), indent=2)
        )

    @classmethod
    def from_json_file(cls, path: Path) -> "CompiledArtifacts":
        """Load CompiledArtifacts from a JSON file.

        Uses Pydantic's model_validate for strict validation.

        Args:
            path: Path to the JSON file.

        Returns:
            CompiledArtifacts instance.

        Raises:
            FileNotFoundError: If file does not exist.
            pydantic.ValidationError: If JSON is invalid.

        Example:
            >>> artifacts = CompiledArtifacts.from_json_file(
            ...     Path("target/compiled_artifacts.json")
            ... )
            >>> artifacts.version
            '0.2.0'

        See Also:
            - to_json_file: Write artifacts to JSON
        """
        data = json.loads(path.read_text())
        return cls.model_validate(data)

    @classmethod
    def export_json_schema(cls) -> dict[str, Any]:
        """Export JSON Schema for IDE autocomplete and external validation.

        Returns the Pydantic-generated JSON Schema with $id and $schema
        metadata for standards compliance.

        Returns:
            JSON Schema dictionary.

        Example:
            >>> schema = CompiledArtifacts.export_json_schema()
            >>> schema["$schema"]
            'https://json-schema.org/draft/2020-12/schema'
            >>> "properties" in schema
            True

        See Also:
            - model_json_schema: Underlying Pydantic method
        """
        schema = cls.model_json_schema()
        # Add standard JSON Schema metadata
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = "https://floe.dev/schemas/compiled-artifacts.json"
        return schema


__all__ = [
    # Core artifacts
    "CompiledArtifacts",
    "CompilationMetadata",
    "DeploymentMode",
    "ManifestRef",
    "ObservabilityConfig",
    "ProductIdentity",
    # Plugin resolution (v0.2.0)
    "PluginRef",
    "ResolvedPlugins",
    # Transform resolution (v0.2.0)
    "ResolvedModel",
    "ResolvedTransforms",
    # Governance resolution (v0.2.0)
    "ResolvedGovernance",
]

"""floe-core: Core plugin registry, schemas, and interfaces for the floe data platform.

This package provides:
- FloeSpec, CompiledArtifacts: Key schema types for data product definition
- compile_pipeline: 6-stage compilation pipeline (Epic 2B)
- CompilationError, CompilationStage: Structured error handling
- PluginRegistry: Singleton for discovering and managing plugins
- PluginMetadata: Base ABC for all plugin types
- PluginType: Enum defining the 12 plugin categories
- Plugin ABCs: Type-specific interfaces (ComputePlugin, etc.)
- Compute Config Models: Pydantic models for compute plugin configuration
- Errors: Custom exceptions for plugin and compute operations
- Schemas: Pydantic models for manifest validation (floe_core.schemas)
- Telemetry: OpenTelemetry SDK integration (floe_core.telemetry)

Example:
    >>> from floe_core import FloeSpec, CompiledArtifacts, compile_pipeline
    >>> artifacts = compile_pipeline(Path("floe.yaml"), Path("manifest.yaml"))
    >>> artifacts.version
    '0.2.0'

    >>> from floe_core import get_registry, PluginType
    >>> registry = get_registry()
    >>> registry.discover_all()
    >>> compute_plugins = registry.list(PluginType.COMPUTE)

    >>> from floe_core import ComputePlugin, CatalogPlugin
    >>> class MyCompute(ComputePlugin):
    ...     # Implement abstract methods
    ...     pass

    >>> from floe_core.schemas import PlatformManifest
    >>> manifest = PlatformManifest.model_validate(yaml_data)

    >>> from floe_core import TelemetryConfig, TelemetryProvider, ResourceAttributes
    >>> attrs = ResourceAttributes(service_name="my-service", ...)
    >>> config = TelemetryConfig(resource_attributes=attrs)
    >>> with TelemetryProvider(config) as provider:
    ...     pass  # Telemetry active

    >>> from floe_core import DuckDBConfig, ConnectionStatus
    >>> config = DuckDBConfig(path=":memory:", memory_limit="4GB")
    >>> status = ConnectionStatus.HEALTHY

See Also:
    - floe_core.compilation: 6-stage compilation pipeline
    - floe_core.plugins: All plugin ABCs with supporting dataclasses
    - floe_core.schemas: Manifest and FloeSpec schema definitions
    - floe_core.telemetry: OpenTelemetry integration
    - floe_core.compute_config: Compute configuration models
    - floe_core.compute_errors: Compute error hierarchy
    - docs/architecture/plugin-system/: Full architecture documentation
"""

from __future__ import annotations

__version__ = "0.1.0"

# Schemas submodule (imported for explicit re-export)
# RBAC submodule (explicit re-export)
from floe_core import rbac as rbac  # noqa: PLC0414
from floe_core import schemas as schemas  # noqa: PLC0414

# Telemetry submodule (explicit re-export)
from floe_core import telemetry as telemetry  # noqa: PLC0414

# Compilation pipeline (Epic 2B)
from floe_core.compilation.errors import (
    CompilationError,
    CompilationException,
)
from floe_core.compilation.stages import (
    CompilationStage,
    compile_pipeline,
)

# Compiler functions
from floe_core.compiler import (
    EnvironmentParityError,
    check_environment_parity,
    compile_transforms,
    resolve_transform_compute,
    resolve_transforms_compute,
    validate_environment_parity,
)

# Compute configuration models
from floe_core.compute_config import (
    WORKLOAD_PRESETS,
    AttachConfig,
    CatalogConfig,
    ComputeConfig,
    ConnectionResult,
    ConnectionStatus,
    DuckDBConfig,
    ResourceSpec,
)

# Compute error hierarchy
from floe_core.compute_errors import (
    ComputeConfigurationError,
    ComputeConnectionError,
    ComputeError,
    ComputeTimeoutError,
)

# Compute registry
from floe_core.compute_registry import ComputeRegistry

# Observability (OTel)
from floe_core.observability import (
    get_meter,
    get_tracer,
    record_validation_duration,
    record_validation_error,
    start_validation_span,
)

# Plugin error hierarchy
from floe_core.plugin_errors import (
    # Catalog operation errors
    AuthenticationError,
    CatalogError,
    CatalogUnavailableError,
    # Plugin registry errors
    CircularDependencyError,
    ConflictError,
    DuplicatePluginError,
    MissingDependencyError,
    NotFoundError,
    NotSupportedError,
    PluginConfigurationError,
    PluginError,
    PluginIncompatibleError,
    PluginNotFoundError,
    PluginStartupError,
)

# Health types and PluginMetadata ABC
from floe_core.plugin_metadata import (
    HealthState,
    HealthStatus,
    PluginMetadata,
)

# Plugin registry singleton
from floe_core.plugin_registry import (
    PluginRegistry,
    get_registry,
)

# Plugin type categories
from floe_core.plugin_types import PluginType

# Plugin ABCs (12 types)
from floe_core.plugins import (
    CatalogPlugin,
    ComputePlugin,
    DBTPlugin,
    IdentityPlugin,
    IngestionPlugin,
    LineageBackendPlugin,
    OrchestratorPlugin,
    QualityPlugin,
    SecretsPlugin,
    SemanticLayerPlugin,
    StoragePlugin,
    TelemetryBackendPlugin,
)

# Key schema exports (convenience imports from schemas submodule)
from floe_core.schemas.compiled_artifacts import CompiledArtifacts
from floe_core.schemas.floe_spec import FloeSpec

# Security configuration exports (Epic 7B convenience imports)
from floe_core.schemas.security import (
    RBACConfig,
    SecurityConfig,
)

# Telemetry public API (convenience imports)
from floe_core.telemetry import (
    ProviderState,
    ResourceAttributes,
    SamplingConfig,
    TelemetryConfig,
    TelemetryProvider,
)

# Version compatibility
from floe_core.version_compat import (
    FLOE_PLUGIN_API_MIN_VERSION,
    FLOE_PLUGIN_API_VERSION,
    is_compatible,
)

__all__: list[str] = [
    # Package version
    "__version__",
    # Schemas submodule and key exports
    "schemas",
    "CompiledArtifacts",
    "FloeSpec",
    # RBAC submodule and security exports (Epic 7B)
    "rbac",
    "RBACConfig",
    "SecurityConfig",
    # Telemetry submodule and exports
    "telemetry",
    "TelemetryConfig",
    "TelemetryProvider",
    "ResourceAttributes",
    "SamplingConfig",
    "ProviderState",
    # Compilation pipeline (Epic 2B)
    "CompilationError",
    "CompilationException",
    "CompilationStage",
    "compile_pipeline",
    # Plugin type categories
    "PluginType",
    # Plugin error hierarchy
    "CircularDependencyError",
    "DuplicatePluginError",
    "MissingDependencyError",
    "PluginConfigurationError",
    "PluginError",
    "PluginIncompatibleError",
    "PluginNotFoundError",
    "PluginStartupError",
    # Catalog operation errors
    "AuthenticationError",
    "CatalogError",
    "CatalogUnavailableError",
    "ConflictError",
    "NotFoundError",
    "NotSupportedError",
    # Compute configuration models
    "AttachConfig",
    "CatalogConfig",
    "ComputeConfig",
    "ConnectionResult",
    "ConnectionStatus",
    "DuckDBConfig",
    "ResourceSpec",
    "WORKLOAD_PRESETS",
    # Compute error hierarchy
    "ComputeConfigurationError",
    "ComputeConnectionError",
    "ComputeError",
    "ComputeTimeoutError",
    # Compute registry
    "ComputeRegistry",
    # Compiler functions
    "EnvironmentParityError",
    "check_environment_parity",
    "compile_transforms",
    "resolve_transform_compute",
    "resolve_transforms_compute",
    "validate_environment_parity",
    # Version compatibility
    "FLOE_PLUGIN_API_VERSION",
    "FLOE_PLUGIN_API_MIN_VERSION",
    "is_compatible",
    # Health types and base ABC
    "HealthState",
    "HealthStatus",
    "PluginMetadata",
    # Plugin registry
    "PluginRegistry",
    "get_registry",
    # Plugin ABCs (12 types)
    "CatalogPlugin",
    "ComputePlugin",
    "DBTPlugin",
    "IdentityPlugin",
    "IngestionPlugin",
    "LineageBackendPlugin",
    "OrchestratorPlugin",
    "QualityPlugin",
    "SecretsPlugin",
    "SemanticLayerPlugin",
    "StoragePlugin",
    "TelemetryBackendPlugin",
    # Observability (OTel)
    "get_meter",
    "get_tracer",
    "record_validation_duration",
    "record_validation_error",
    "start_validation_span",
]

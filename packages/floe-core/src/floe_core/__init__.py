"""floe-core: Core plugin registry, schemas, and interfaces for the floe data platform.

This package provides a minimal public API. For specialized functionality,
import from the appropriate submodule.

Public API (15 symbols):
- FloeSpec, CompiledArtifacts: Key schema types
- compile_pipeline, CompilationError: Compilation pipeline
- PluginRegistry, get_registry, PluginType, PluginMetadata: Plugin system
- HealthState, HealthStatus: Plugin health reporting
- schemas, telemetry, rbac, plugins: Submodule re-exports

Example:
    >>> from floe_core import FloeSpec, CompiledArtifacts, compile_pipeline
    >>> artifacts = compile_pipeline(Path("floe.yaml"), Path("manifest.yaml"))

    >>> from floe_core import get_registry, PluginType
    >>> registry = get_registry()
    >>> registry.discover_all()

    >>> from floe_core.plugins import ComputePlugin, CatalogPlugin
    >>> class MyCompute(ComputePlugin):
    ...     pass

See Also:
    - floe_core.plugins: All plugin ABCs (ComputePlugin, CatalogPlugin, etc.)
    - floe_core.schemas: Manifest and FloeSpec schema definitions
    - floe_core.telemetry: OpenTelemetry integration
    - floe_core.compute_config: Compute configuration models
    - floe_core.compute_errors: Compute error hierarchy
    - floe_core.plugin_errors: Plugin error hierarchy
    - floe_core.observability: OTel metrics and tracing helpers
"""

from __future__ import annotations

__version__ = "0.1.0"

# =============================================================================
# Submodule re-exports (explicit)
# =============================================================================
from floe_core import plugins as plugins  # noqa: PLC0414
from floe_core import rbac as rbac  # noqa: PLC0414
from floe_core import schemas as schemas  # noqa: PLC0414
from floe_core import telemetry as telemetry  # noqa: PLC0414

# =============================================================================
# Essential public API
# =============================================================================

# Compilation pipeline (Epic 2B)
from floe_core.compilation.errors import CompilationError
from floe_core.compilation.stages import compile_pipeline

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

# Key schema exports
from floe_core.schemas.compiled_artifacts import CompiledArtifacts
from floe_core.schemas.floe_spec import FloeSpec

# =============================================================================
# Backwards compatibility imports (not in __all__, use submodule imports)
# =============================================================================

# Compilation extras - use: from floe_core.compilation import ...
from floe_core.compilation.errors import CompilationException as CompilationException
from floe_core.compilation.stages import CompilationStage as CompilationStage

# Compiler functions - use: from floe_core.compiler import ...
from floe_core.compiler import (
    EnvironmentParityError as EnvironmentParityError,
    check_environment_parity as check_environment_parity,
    compile_transforms as compile_transforms,
    resolve_transform_compute as resolve_transform_compute,
    resolve_transforms_compute as resolve_transforms_compute,
    validate_environment_parity as validate_environment_parity,
)

# Compute config - use: from floe_core.compute_config import ...
from floe_core.compute_config import (
    WORKLOAD_PRESETS as WORKLOAD_PRESETS,
    AttachConfig as AttachConfig,
    CatalogConfig as CatalogConfig,
    ComputeConfig as ComputeConfig,
    ConnectionResult as ConnectionResult,
    ConnectionStatus as ConnectionStatus,
    DuckDBConfig as DuckDBConfig,
    ResourceSpec as ResourceSpec,
)

# Compute errors - use: from floe_core.compute_errors import ...
from floe_core.compute_errors import (
    ComputeConfigurationError as ComputeConfigurationError,
    ComputeConnectionError as ComputeConnectionError,
    ComputeError as ComputeError,
    ComputeTimeoutError as ComputeTimeoutError,
)

# Compute registry - use: from floe_core.compute_registry import ...
from floe_core.compute_registry import ComputeRegistry as ComputeRegistry

# Observability - use: from floe_core.observability import ...
from floe_core.observability import (
    get_meter as get_meter,
    get_tracer as get_tracer,
    record_validation_duration as record_validation_duration,
    record_validation_error as record_validation_error,
    start_validation_span as start_validation_span,
)

# Plugin errors - use: from floe_core.plugin_errors import ...
from floe_core.plugin_errors import (
    AuthenticationError as AuthenticationError,
    CatalogError as CatalogError,
    CatalogUnavailableError as CatalogUnavailableError,
    CircularDependencyError as CircularDependencyError,
    ConflictError as ConflictError,
    DuplicatePluginError as DuplicatePluginError,
    MissingDependencyError as MissingDependencyError,
    NotFoundError as NotFoundError,
    NotSupportedError as NotSupportedError,
    PluginConfigurationError as PluginConfigurationError,
    PluginError as PluginError,
    PluginIncompatibleError as PluginIncompatibleError,
    PluginNotFoundError as PluginNotFoundError,
    PluginStartupError as PluginStartupError,
)

# Plugin ABCs - use: from floe_core.plugins import ...
from floe_core.plugins import (
    CatalogPlugin as CatalogPlugin,
    ComputePlugin as ComputePlugin,
    DBTPlugin as DBTPlugin,
    IdentityPlugin as IdentityPlugin,
    IngestionPlugin as IngestionPlugin,
    LineageBackendPlugin as LineageBackendPlugin,
    OrchestratorPlugin as OrchestratorPlugin,
    QualityPlugin as QualityPlugin,
    SecretsPlugin as SecretsPlugin,
    SemanticLayerPlugin as SemanticLayerPlugin,
    StoragePlugin as StoragePlugin,
    TelemetryBackendPlugin as TelemetryBackendPlugin,
)

# Security config - use: from floe_core.schemas.security import ...
from floe_core.schemas.security import (
    RBACConfig as RBACConfig,
    SecurityConfig as SecurityConfig,
)

# Telemetry - use: from floe_core.telemetry import ...
from floe_core.telemetry import (
    ProviderState as ProviderState,
    ResourceAttributes as ResourceAttributes,
    SamplingConfig as SamplingConfig,
    TelemetryConfig as TelemetryConfig,
    TelemetryProvider as TelemetryProvider,
)

# Version compat - use: from floe_core.version_compat import ...
from floe_core.version_compat import (
    FLOE_PLUGIN_API_MIN_VERSION as FLOE_PLUGIN_API_MIN_VERSION,
    FLOE_PLUGIN_API_VERSION as FLOE_PLUGIN_API_VERSION,
    is_compatible as is_compatible,
)

# =============================================================================
# Public API (15 symbols)
# =============================================================================
__all__: list[str] = [
    # Package version
    "__version__",
    # Submodules
    "plugins",
    "rbac",
    "schemas",
    "telemetry",
    # Key schemas
    "CompiledArtifacts",
    "FloeSpec",
    # Compilation
    "CompilationError",
    "compile_pipeline",
    # Plugin system
    "get_registry",
    "PluginRegistry",
    "PluginType",
    "PluginMetadata",
    # Health reporting
    "HealthState",
    "HealthStatus",
]

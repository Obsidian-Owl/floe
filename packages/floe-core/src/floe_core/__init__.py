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

# Compilation pipeline (essential export)
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
# Backward compatibility exports (for test compatibility)
# =============================================================================
# NOTE: These are re-exports for backward compatibility with test code.
# New code should import from the specific submodule (e.g., floe_core.plugins).
# Plugin ABCs
from floe_core.plugins import (
    CatalogConfig,
    CatalogPlugin,
    ComputeConfig,
    ComputePlugin,
    ConnectionResult,
    ResourceSpec,
)

# Compute config
from floe_core.compute_config import WORKLOAD_PRESETS, ConnectionStatus

# Plugin error hierarchy
from floe_core.plugin_errors import (
    AuthenticationError,
    CatalogError,
    CatalogUnavailableError,
    ConflictError,
    NotFoundError,
    NotSupportedError,
)

# =============================================================================
# Public API (15 symbols) + Backward Compatibility Exports
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
    # Backward compatibility (plugin ABCs)
    "CatalogConfig",
    "CatalogPlugin",
    "ComputeConfig",
    "ComputePlugin",
    "ConnectionResult",
    "ResourceSpec",
    # Backward compatibility (compute config)
    "ConnectionStatus",
    "WORKLOAD_PRESETS",
    # Backward compatibility (error classes)
    "AuthenticationError",
    "CatalogError",
    "CatalogUnavailableError",
    "ConflictError",
    "NotFoundError",
    "NotSupportedError",
]

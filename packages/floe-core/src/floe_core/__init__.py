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

from importlib import import_module
from typing import Any

__version__ = "0.1.0"

_SUBMODULE_EXPORTS = {
    "plugins": "floe_core.plugins",
    "rbac": "floe_core.rbac",
    "schemas": "floe_core.schemas",
    "telemetry": "floe_core.telemetry",
}

_PUBLIC_EXPORTS = {
    "AuthenticationError": "floe_core.plugin_errors",
    "CatalogConfig": "floe_core.plugins",
    "CatalogError": "floe_core.plugin_errors",
    "CatalogPlugin": "floe_core.plugins",
    "CatalogUnavailableError": "floe_core.plugin_errors",
    "CompilationError": "floe_core.compilation.errors",
    "CompiledArtifacts": "floe_core.schemas.compiled_artifacts",
    "ComputeConfig": "floe_core.plugins",
    "ComputePlugin": "floe_core.plugins",
    "ConflictError": "floe_core.plugin_errors",
    "ConnectionResult": "floe_core.plugins",
    "ConnectionStatus": "floe_core.compute_config",
    "FloeSpec": "floe_core.schemas.floe_spec",
    "HealthState": "floe_core.plugin_metadata",
    "HealthStatus": "floe_core.plugin_metadata",
    "NotFoundError": "floe_core.plugin_errors",
    "NotSupportedError": "floe_core.plugin_errors",
    "PluginMetadata": "floe_core.plugin_metadata",
    "PluginRegistry": "floe_core.plugin_registry",
    "PluginType": "floe_core.plugin_types",
    "ResourceSpec": "floe_core.plugins",
    "WORKLOAD_PRESETS": "floe_core.compute_config",
    "compile_pipeline": "floe_core.compilation.stages",
    "get_registry": "floe_core.plugin_registry",
}


def __getattr__(name: str) -> Any:
    """Lazily load public exports to keep package import side-effect light."""
    if name in _SUBMODULE_EXPORTS:
        module = import_module(_SUBMODULE_EXPORTS[name])
        globals()[name] = module
        return module

    if name in _PUBLIC_EXPORTS:
        module = import_module(_PUBLIC_EXPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value

    raise AttributeError(f"module 'floe_core' has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return stable public attributes for interactive tooling."""
    return sorted(set(globals()) | set(__all__))


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

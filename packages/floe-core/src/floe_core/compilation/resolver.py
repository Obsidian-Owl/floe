"""Plugin and transform resolver for floe compilation pipeline.

This module provides functions to resolve:
- Plugin selections from platform manifests
- Manifest inheritance (3-tier mode)
- Transform compute targets

The resolver merges configuration from the inheritance chain and
applies governance policies.

See Also:
    - specs/2b-compilation-pipeline/spec.md: Feature specification
    - ResolvedPlugins: Resolved plugin configuration
    - ResolvedTransforms: Resolved transform configuration
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from floe_core.compilation.errors import CompilationError, CompilationException

if TYPE_CHECKING:
    from floe_core.plugin_metadata import PluginMetadata
from floe_core.compilation.stages import CompilationStage
from floe_core.schemas.compiled_artifacts import (
    PluginRef,
    ResolvedModel,
    ResolvedPlugins,
    ResolvedTransforms,
)
from floe_core.schemas.floe_spec import FloeSpec
from floe_core.schemas.manifest import PlatformManifest

# Default plugin version when not specified
DEFAULT_PLUGIN_VERSION = "0.0.0"


def _to_plugin_ref(
    plugin: object,
    default_version: str = DEFAULT_PLUGIN_VERSION,
) -> PluginRef | None:
    """Convert PluginSelection to PluginRef.

    Args:
        plugin: PluginSelection instance or None.
        default_version: Version to use if not specified.

    Returns:
        PluginRef or None if plugin is None.
    """
    if plugin is None:
        return None
    # PluginSelection has type, version, config, connection_secret_ref
    plugin_type = getattr(plugin, "type", "")
    version = getattr(plugin, "version", None) or default_version
    config = getattr(plugin, "config", None)
    return PluginRef(type=plugin_type, version=version, config=config)


def resolve_plugins(manifest: PlatformManifest) -> ResolvedPlugins:
    """Resolve plugin selections from platform manifest.

    Args:
        manifest: Platform manifest with plugin configuration.

    Returns:
        ResolvedPlugins with compute, orchestrator, and optional plugins.

    Raises:
        CompilationException: If required plugins missing or invalid.

    Example:
        >>> plugins = resolve_plugins(manifest)
        >>> plugins.compute.type
        'duckdb'
    """
    plugins = manifest.plugins

    # Validate required plugins
    if plugins.compute is None:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code="E201",
                message="Required plugin 'compute' not found in platform manifest",
                suggestion="Add a compute plugin to the manifest plugins section",
                context={"manifest": manifest.metadata.name},
            )
        )

    if plugins.orchestrator is None:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code="E201",
                message="Required plugin 'orchestrator' not found in platform manifest",
                suggestion="Add an orchestrator plugin to the manifest plugins section",
                context={"manifest": manifest.metadata.name},
            )
        )

    # Build ResolvedPlugins
    return ResolvedPlugins(
        compute=_to_plugin_ref(plugins.compute),  # type: ignore[arg-type]
        orchestrator=_to_plugin_ref(plugins.orchestrator),  # type: ignore[arg-type]
        catalog=_to_plugin_ref(plugins.catalog),
        storage=_to_plugin_ref(plugins.storage),
        ingestion=_to_plugin_ref(plugins.ingestion),
        semantic=_to_plugin_ref(plugins.semantic_layer),
        lineage_backend=_to_plugin_ref(plugins.lineage_backend),
    )


def resolve_manifest_inheritance(
    manifest: PlatformManifest,
) -> PlatformManifest:
    """Resolve manifest inheritance chain (3-tier mode).

    For enterprise/domain manifests with parent references,
    resolves the full inheritance chain and merges configuration.

    Note: Full 3-tier inheritance (OCI registry loading) is not yet
    implemented. This function currently returns the manifest as-is
    for 2-tier mode (scope=None).

    Args:
        manifest: Platform manifest (may have parent reference).

    Returns:
        Fully resolved PlatformManifest with merged configuration.

    Raises:
        CompilationException: If inheritance cycle detected or parent not found.

    Example:
        >>> resolved = resolve_manifest_inheritance(domain_manifest)
        >>> resolved.plugins.compute  # May be inherited from enterprise
    """
    # For 2-tier mode (no parent), return as-is
    if manifest.parent_manifest is None:
        return manifest

    # 3-tier mode: would need to load parent from OCI registry
    # This is deferred to a later epic (OCI registry integration)
    # For now, return the manifest as-is
    return manifest


def resolve_transform_compute(
    spec: FloeSpec,
    manifest: PlatformManifest,
) -> ResolvedTransforms:
    """Resolve compute targets for each transform.

    For each transform in FloeSpec:
    - Use explicit compute override if specified
    - Otherwise use platform default_compute

    Args:
        spec: FloeSpec with transform definitions.
        manifest: Platform manifest with default_compute.

    Returns:
        ResolvedTransforms with all models having resolved compute targets.

    Raises:
        CompilationException: If compute target not in approved_plugins.

    Example:
        >>> transforms = resolve_transform_compute(spec, manifest)
        >>> transforms.models[0].compute
        'duckdb'
    """
    # Get default compute from manifest
    default_compute = None

    # Check if manifest has defaults section with compute
    defaults = getattr(manifest, "defaults", None)
    if defaults and isinstance(defaults, dict) and "compute" in defaults:
        default_compute = defaults["compute"]

    # If no explicit default, use the compute plugin type
    if default_compute is None and manifest.plugins.compute is not None:
        default_compute = manifest.plugins.compute.type

    if default_compute is None:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code="E201",
                message="No default compute target available",
                suggestion="Add a compute plugin to the manifest or specify defaults.compute",
                context={"manifest": manifest.metadata.name},
            )
        )

    # Resolve each transform
    resolved_models: list[ResolvedModel] = []
    for transform in spec.transforms:
        # Use explicit compute override if specified, otherwise default
        compute = transform.compute if transform.compute else default_compute
        resolved_models.append(
            ResolvedModel(
                name=transform.name,
                compute=compute,
                tags=transform.tags,
                depends_on=transform.depends_on,
                quality_checks=(
                    list(transform.quality_checks) if transform.quality_checks else None
                ),
                quality_tier=transform.tier,
            )
        )

    return ResolvedTransforms(
        models=resolved_models,
        default_compute=default_compute,
    )


def get_compute_plugin(plugin_type: str) -> PluginMetadata:
    """Load a compute plugin by type name.

    Args:
        plugin_type: Plugin type (e.g., "duckdb", "snowflake").

    Returns:
        PluginMetadata instance (specifically ComputePlugin).

    Raises:
        CompilationException: If plugin not found.
    """
    from floe_core.plugin_metadata import PluginMetadata
    from floe_core.plugin_registry import get_registry
    from floe_core.plugin_types import PluginType

    try:
        registry = get_registry()
        plugin = registry.get(PluginType.COMPUTE, plugin_type)
        # registry.get returns PluginMetadata
        assert isinstance(plugin, PluginMetadata)
        return plugin
    except Exception as e:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.VALIDATE,
                code="E201",
                message=f"Compute plugin '{plugin_type}' not found",
                suggestion="Ensure the compute plugin is installed and registered",
                context={"plugin_type": plugin_type},
            )
        ) from e


def validate_compute_credentials(plugins: ResolvedPlugins) -> None:
    """Validate that required compute credentials are configured.

    Loads the compute plugin and checks its config schema for required fields.
    For plugins without a schema (like DuckDB), validation passes.
    For plugins with schemas, validates that required fields are present.

    This validation runs at the VALIDATE stage, before profile generation,
    to provide early feedback on missing configuration.

    Args:
        plugins: ResolvedPlugins with compute plugin configuration.

    Raises:
        CompilationException: If required credentials are missing (E107).

    Example:
        >>> plugins = resolve_plugins(manifest)
        >>> validate_compute_credentials(plugins)  # Raises if missing credentials
    """
    compute_ref = plugins.compute
    compute_type = compute_ref.type
    compute_config = compute_ref.config or {}

    # Load the compute plugin to get its schema
    plugin = get_compute_plugin(compute_type)

    # Get the config schema from the plugin
    schema = plugin.get_config_schema()

    # If no schema, no validation required (e.g., DuckDB)
    if schema is None:
        return

    # Get required fields from the Pydantic model schema
    # Required fields are those without defaults in model_fields
    required_fields: list[str] = []
    for field_name, field_info in schema.model_fields.items():
        # Field is required if it has no default and no default_factory
        if field_info.is_required():
            required_fields.append(field_name)

    # Check which required fields are missing from config
    missing_fields = [f for f in required_fields if f not in compute_config]

    if missing_fields:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.VALIDATE,
                code="E107",
                message=(
                    f"Missing required credentials for compute plugin '{compute_type}': "
                    f"{', '.join(missing_fields)}"
                ),
                suggestion=(
                    f"Add the following fields to the compute plugin config: "
                    f"{', '.join(missing_fields)}"
                ),
                context={
                    "plugin_type": compute_type,
                    "missing_fields": missing_fields,
                    "provided_fields": list(compute_config.keys()),
                },
            )
        )


__all__ = [
    "get_compute_plugin",
    "resolve_plugins",
    "resolve_manifest_inheritance",
    "resolve_transform_compute",
    "validate_compute_credentials",
]

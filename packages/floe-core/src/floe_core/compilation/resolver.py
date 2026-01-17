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

from floe_core.schemas.compiled_artifacts import (
    ResolvedPlugins,
    ResolvedTransforms,
)
from floe_core.schemas.floe_spec import FloeSpec
from floe_core.schemas.manifest import PlatformManifest


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
    # TODO: Implement in T031
    raise NotImplementedError("resolve_plugins not yet implemented (T031)")


def resolve_manifest_inheritance(
    manifest: PlatformManifest,
) -> PlatformManifest:
    """Resolve manifest inheritance chain (3-tier mode).

    For enterprise/domain manifests with parent references,
    resolves the full inheritance chain and merges configuration.

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
    # TODO: Implement in T032
    raise NotImplementedError("resolve_manifest_inheritance not yet implemented (T032)")


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
    # TODO: Implement in T033
    raise NotImplementedError("resolve_transform_compute not yet implemented (T033)")


__all__ = [
    "resolve_plugins",
    "resolve_manifest_inheritance",
    "resolve_transform_compute",
]

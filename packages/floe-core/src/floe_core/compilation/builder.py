"""Artifacts builder for floe compilation pipeline.

This module provides the CompiledArtifacts builder that assembles
the final output from resolved configuration.

The builder:
- Collects compilation metadata (timestamp, versions, git commit)
- Computes source hash for change detection
- Assembles all resolved configuration into CompiledArtifacts

See Also:
    - specs/2b-compilation-pipeline/spec.md: Feature specification
    - CompiledArtifacts: Output schema
"""

from __future__ import annotations

from pathlib import Path

from floe_core.schemas.compiled_artifacts import (
    CompiledArtifacts,
    ResolvedPlugins,
    ResolvedTransforms,
)
from floe_core.schemas.floe_spec import FloeSpec
from floe_core.schemas.manifest import PlatformManifest


def build_artifacts(
    spec: FloeSpec,
    manifest: PlatformManifest,
    plugins: ResolvedPlugins,
    transforms: ResolvedTransforms,
    dbt_profiles: dict[str, object],
    *,
    spec_path: Path | None = None,
    manifest_path: Path | None = None,
) -> CompiledArtifacts:
    """Build CompiledArtifacts from resolved configuration.

    Assembles all compilation outputs into the final CompiledArtifacts
    contract, including:
    - Compilation metadata (timestamp, versions, hashes)
    - Product identity from FloeSpec
    - Resolved plugins and transforms
    - Generated dbt profiles

    Args:
        spec: Validated FloeSpec.
        manifest: Resolved PlatformManifest.
        plugins: Resolved plugin selections.
        transforms: Resolved transform configuration.
        dbt_profiles: Generated dbt profiles.yml content.
        spec_path: Optional path to spec file (for source hash).
        manifest_path: Optional path to manifest file (for source hash).

    Returns:
        Complete CompiledArtifacts ready for output.

    Example:
        >>> artifacts = build_artifacts(spec, manifest, plugins, transforms, profiles)
        >>> artifacts.version
        '0.2.0'
        >>> artifacts.metadata.product_name
        'my-pipeline'
    """
    # TODO: Implement in T034
    raise NotImplementedError("build_artifacts not yet implemented (T034)")


def compute_source_hash(
    spec_path: Path | None = None,
    manifest_path: Path | None = None,
) -> str:
    """Compute SHA256 hash of input files for change detection.

    Args:
        spec_path: Path to floe.yaml file.
        manifest_path: Path to manifest.yaml file.

    Returns:
        SHA256 hash prefixed with 'sha256:'.

    Example:
        >>> compute_source_hash(Path("floe.yaml"), Path("manifest.yaml"))
        'sha256:abc123...'
    """
    # TODO: Implement in T034
    raise NotImplementedError("compute_source_hash not yet implemented (T034)")


def get_git_commit() -> str | None:
    """Get current git commit SHA if in a git repository.

    Returns:
        Git commit SHA or None if not in a git repository.

    Example:
        >>> get_git_commit()
        'abc123def456...'
    """
    # TODO: Implement in T034
    raise NotImplementedError("get_git_commit not yet implemented (T034)")


__all__ = [
    "build_artifacts",
    "compute_source_hash",
    "get_git_commit",
]

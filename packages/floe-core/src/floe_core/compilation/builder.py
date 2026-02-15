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

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from floe_core.schemas.compiled_artifacts import (
    CompilationMetadata,
    CompiledArtifacts,
    EnforcementResultSummary,
    ObservabilityConfig,
    ProductIdentity,
    ResolvedGovernance,
    ResolvedPlugins,
    ResolvedTransforms,
)
from floe_core.schemas.floe_spec import FloeSpec
from floe_core.schemas.manifest import PlatformManifest
from floe_core.schemas.quality_config import QualityConfig
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION, FLOE_VERSION
from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

# Contract version alias for backwards compatibility
CONTRACT_VERSION = COMPILED_ARTIFACTS_VERSION


def build_artifacts(
    spec: FloeSpec,
    manifest: PlatformManifest,
    plugins: ResolvedPlugins,
    transforms: ResolvedTransforms,
    dbt_profiles: dict[str, Any],
    *,
    spec_path: Path | None = None,
    manifest_path: Path | None = None,
    enforcement_result: EnforcementResultSummary | None = None,
    quality_config: QualityConfig | None = None,
    governance: ResolvedGovernance | None = None,
) -> CompiledArtifacts:
    """Build CompiledArtifacts from resolved configuration.

    Assembles all compilation outputs into the final CompiledArtifacts
    contract, including:
    - Compilation metadata (timestamp, versions, hashes)
    - Product identity from FloeSpec
    - Resolved plugins and transforms
    - Generated dbt profiles
    - Enforcement result summary (optional, v0.3.0+)
    - Quality configuration (optional, v0.4.0+)
    - Governance configuration (optional, v0.5.0+)

    Task: T063, T039, T051
    Requirements: FR-024, FR-025, FR-026 (Pipeline Integration)

    Args:
        spec: Validated FloeSpec.
        manifest: Resolved PlatformManifest.
        plugins: Resolved plugin selections.
        transforms: Resolved transform configuration.
        dbt_profiles: Generated dbt profiles.yml content.
        spec_path: Optional path to spec file (for source hash).
        manifest_path: Optional path to manifest file (for source hash).
        enforcement_result: Optional enforcement result summary (v0.3.0+).
        quality_config: Optional quality configuration (v0.4.0+).
        governance: Optional governance configuration (v0.5.0+).

    Returns:
        Complete CompiledArtifacts ready for output.

    Example:
        >>> artifacts = build_artifacts(spec, manifest, plugins, transforms, profiles)
        >>> artifacts.version
        '0.5.0'
        >>> artifacts.metadata.product_name
        'my-pipeline'
    """
    # Compute source hash
    source_hash = compute_source_hash(spec_path, manifest_path)

    # Build compilation metadata
    metadata = CompilationMetadata(
        compiled_at=datetime.now(),
        floe_version=FLOE_VERSION,
        source_hash=source_hash,
        product_name=spec.metadata.name,
        product_version=spec.metadata.version,
    )

    # Build product identity
    identity = ProductIdentity(
        product_id=f"default.{spec.metadata.name.replace('-', '_')}",
        domain="default",
        repository="",  # Would come from git remote in production
    )

    # Build observability config
    observability = ObservabilityConfig(
        telemetry=TelemetryConfig(
            enabled=True,
            resource_attributes=ResourceAttributes(
                service_name=spec.metadata.name,
                service_version=spec.metadata.version,
                deployment_environment="dev",
                floe_namespace="default",
                floe_product_name=spec.metadata.name,
                floe_product_version=spec.metadata.version,
                floe_mode="dev",
            ),
        ),
        lineage=True,
        lineage_namespace=spec.metadata.name,
    )

    return CompiledArtifacts(
        version=CONTRACT_VERSION,
        metadata=metadata,
        identity=identity,
        mode="simple",
        inheritance_chain=[],
        observability=observability,
        plugins=plugins,
        transforms=transforms,
        dbt_profiles=dbt_profiles,
        enforcement_result=enforcement_result,
        quality_config=quality_config,
        governance=governance,
    )


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
    hasher = hashlib.sha256()

    # Hash spec file if provided
    if spec_path and spec_path.exists():
        content = spec_path.read_bytes()
        hasher.update(content)

    # Hash manifest file if provided
    if manifest_path and manifest_path.exists():
        content = manifest_path.read_bytes()
        hasher.update(content)

    # If no files provided, hash empty string
    if not spec_path and not manifest_path:
        hasher.update(b"")

    return f"sha256:{hasher.hexdigest()}"


def get_git_commit() -> str | None:
    """Get current git commit SHA if in a git repository.

    Returns:
        Git commit SHA or None if not in a git repository.

    Example:
        >>> get_git_commit()
        'abc123def456...'
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


__all__ = [
    "build_artifacts",
    "compute_source_hash",
    "get_git_commit",
]

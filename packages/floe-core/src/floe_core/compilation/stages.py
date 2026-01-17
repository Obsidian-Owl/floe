"""Compilation stages for the floe compilation pipeline.

The compilation pipeline consists of 6 sequential stages that transform
FloeSpec + PlatformManifest into CompiledArtifacts.

Stages:
    1. LOAD: Parse YAML files into Pydantic models
    2. VALIDATE: Schema validation and constraint checking
    3. RESOLVE: Plugin resolution and inheritance merging
    4. ENFORCE: Policy enforcement and governance checks
    5. COMPILE: Transform compilation and dbt profile generation
    6. GENERATE: Output CompiledArtifacts JSON

Each stage can produce errors that are tagged with the stage for debugging.

See Also:
    - specs/2b-compilation-pipeline/spec.md: Pipeline specification
    - ADR-0012: CompiledArtifacts contract
"""

from __future__ import annotations

from enum import Enum


class CompilationStage(str, Enum):
    """Stage in the compilation pipeline.

    Each stage processes input from the previous stage and either
    succeeds (passing data forward) or fails with a CompilationError.

    Attributes:
        LOAD: Parse YAML files into Pydantic models
        VALIDATE: Schema validation and constraint checking
        RESOLVE: Plugin resolution and inheritance merging
        ENFORCE: Policy enforcement and governance checks
        COMPILE: Transform compilation and dbt profile generation
        GENERATE: Output CompiledArtifacts JSON

    Example:
        >>> stage = CompilationStage.VALIDATE
        >>> stage.value
        'VALIDATE'
        >>> stage.exit_code
        1

    See Also:
        - CompilationError: Uses stage for error categorization
    """

    LOAD = "LOAD"
    """Parse YAML files (floe.yaml, manifest.yaml) into Pydantic models."""

    VALIDATE = "VALIDATE"
    """Schema validation and constraint checking (C001-C010)."""

    RESOLVE = "RESOLVE"
    """Plugin resolution and manifest inheritance merging."""

    ENFORCE = "ENFORCE"
    """Policy enforcement and governance checks."""

    COMPILE = "COMPILE"
    """Transform compilation and dbt profile generation."""

    GENERATE = "GENERATE"
    """Output CompiledArtifacts JSON to target directory."""

    @property
    def exit_code(self) -> int:
        """Get the CLI exit code for errors in this stage.

        Returns:
            1 for validation-related stages (LOAD, VALIDATE)
            2 for compilation-related stages (RESOLVE, ENFORCE, COMPILE, GENERATE)

        Example:
            >>> CompilationStage.VALIDATE.exit_code
            1
            >>> CompilationStage.COMPILE.exit_code
            2
        """
        # Exit code 1: Validation errors (input problems)
        # Exit code 2: Compilation errors (processing problems)
        validation_stages = {CompilationStage.LOAD, CompilationStage.VALIDATE}
        return 1 if self in validation_stages else 2

    @property
    def description(self) -> str:
        """Get human-readable description of this stage.

        Returns:
            Description of what the stage does.

        Example:
            >>> CompilationStage.LOAD.description
            'Parse YAML files into Pydantic models'
        """
        descriptions = {
            CompilationStage.LOAD: "Parse YAML files into Pydantic models",
            CompilationStage.VALIDATE: "Schema validation and constraint checking",
            CompilationStage.RESOLVE: "Plugin resolution and inheritance merging",
            CompilationStage.ENFORCE: "Policy enforcement and governance checks",
            CompilationStage.COMPILE: "Transform compilation and dbt profile generation",
            CompilationStage.GENERATE: "Output CompiledArtifacts JSON",
        }
        return descriptions[self]


from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts

logger = structlog.get_logger(__name__)


def compile_pipeline(
    spec_path: Path,
    manifest_path: Path,
) -> "CompiledArtifacts":
    """Execute the 6-stage compilation pipeline.

    Transforms FloeSpec + PlatformManifest into CompiledArtifacts through:
    1. LOAD: Parse YAML files
    2. VALIDATE: Schema validation (done during LOAD via Pydantic)
    3. RESOLVE: Plugin and manifest inheritance resolution
    4. ENFORCE: Policy enforcement (placeholder for governance)
    5. COMPILE: Transform compilation and dbt profile generation
    6. GENERATE: Build final CompiledArtifacts

    Args:
        spec_path: Path to floe.yaml file.
        manifest_path: Path to manifest.yaml file.

    Returns:
        CompiledArtifacts ready for serialization.

    Raises:
        CompilationException: If any stage fails.

    Example:
        >>> artifacts = compile_pipeline(Path("floe.yaml"), Path("manifest.yaml"))
        >>> artifacts.version
        '0.2.0'
    """
    # Local imports to avoid circular dependency (stages <- errors <- loader <- stages)
    from floe_core.compilation.builder import build_artifacts
    from floe_core.compilation.dbt_profiles import generate_dbt_profiles
    from floe_core.compilation.loader import load_floe_spec, load_manifest
    from floe_core.compilation.resolver import (
        resolve_manifest_inheritance,
        resolve_plugins,
        resolve_transform_compute,
    )

    log = logger.bind(spec_path=str(spec_path), manifest_path=str(manifest_path))

    # Stage 1: LOAD - Parse YAML files
    log.info("compilation_stage_start", stage=CompilationStage.LOAD.value)
    spec = load_floe_spec(spec_path)
    manifest = load_manifest(manifest_path)
    log.info(
        "compilation_stage_complete",
        stage=CompilationStage.LOAD.value,
        product_name=spec.metadata.name,
    )

    # Stage 2: VALIDATE - Schema validation (done during LOAD via Pydantic)
    log.info("compilation_stage_start", stage=CompilationStage.VALIDATE.value)
    # Validation happens automatically in Pydantic models
    log.info("compilation_stage_complete", stage=CompilationStage.VALIDATE.value)

    # Stage 3: RESOLVE - Plugin and manifest inheritance resolution
    log.info("compilation_stage_start", stage=CompilationStage.RESOLVE.value)
    resolved_manifest = resolve_manifest_inheritance(manifest)
    plugins = resolve_plugins(resolved_manifest)
    transforms = resolve_transform_compute(spec, resolved_manifest)
    log.info(
        "compilation_stage_complete",
        stage=CompilationStage.RESOLVE.value,
        compute_plugin=plugins.compute.type,
        orchestrator_plugin=plugins.orchestrator.type,
        model_count=len(transforms.models),
    )

    # Stage 4: ENFORCE - Policy enforcement
    log.info("compilation_stage_start", stage=CompilationStage.ENFORCE.value)
    # Placeholder for governance enforcement (future epic)
    log.info("compilation_stage_complete", stage=CompilationStage.ENFORCE.value)

    # Stage 5: COMPILE - Transform compilation and dbt profile generation
    log.info("compilation_stage_start", stage=CompilationStage.COMPILE.value)
    # Generate dbt profiles using compute plugin
    dbt_profiles = generate_dbt_profiles(
        plugins=plugins,
        product_name=spec.metadata.name,
    )
    log.info(
        "compilation_stage_complete",
        stage=CompilationStage.COMPILE.value,
        profile_name=spec.metadata.name,
    )

    # Stage 6: GENERATE - Build final CompiledArtifacts
    log.info("compilation_stage_start", stage=CompilationStage.GENERATE.value)
    artifacts = build_artifacts(
        spec=spec,
        manifest=resolved_manifest,
        plugins=plugins,
        transforms=transforms,
        dbt_profiles=dbt_profiles,
        spec_path=spec_path,
        manifest_path=manifest_path,
    )
    log.info(
        "compilation_stage_complete",
        stage=CompilationStage.GENERATE.value,
        version=artifacts.version,
    )

    return artifacts


__all__ = ["CompilationStage", "compile_pipeline"]

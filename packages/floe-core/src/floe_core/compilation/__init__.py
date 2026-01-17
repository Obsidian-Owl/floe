"""Compilation pipeline for the floe data platform.

This module provides the compilation pipeline that transforms:
- FloeSpec (floe.yaml) + PlatformManifest (manifest.yaml)
  → CompiledArtifacts (JSON)

The compilation pipeline consists of 6 stages:
1. LOAD: Parse YAML files into Pydantic models
2. VALIDATE: Schema validation and constraint checking
3. RESOLVE: Plugin resolution and inheritance merging
4. ENFORCE: Policy enforcement (future)
5. COMPILE: Transform compilation and dbt profile generation
6. GENERATE: Output CompiledArtifacts JSON

Example:
    >>> from floe_core.compilation import compile_pipeline
    >>> artifacts = compile_pipeline(
    ...     spec_path=Path("floe.yaml"),
    ...     manifest_path=Path("manifest.yaml"),
    ... )
    >>> artifacts.to_json_file(Path("target/compiled_artifacts.json"))

See Also:
    - specs/2b-compilation-pipeline/spec.md: Feature specification
    - docs/architecture/adr/0012-compiled-artifacts.md: CompiledArtifacts ADR
"""

from __future__ import annotations

from floe_core.compilation.errors import (
    ERROR_CODES,
    CompilationError,
    CompilationException,
)
from floe_core.compilation.stages import CompilationStage

__all__ = [
    # Stages
    "CompilationStage",
    # Errors
    "CompilationError",
    "CompilationException",
    "ERROR_CODES",
]

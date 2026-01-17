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


__all__ = ["CompilationStage"]

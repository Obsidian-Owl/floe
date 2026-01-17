"""Command-line interface for the floe data platform.

This module provides CLI commands for platform operations:

Commands:
    floe compile: Compile FloeSpec + Manifest into CompiledArtifacts
        --spec PATH: Path to floe.yaml
        --manifest PATH: Path to manifest.yaml
        --output PATH: Output path for CompiledArtifacts JSON
        --dry-run: Validate without writing files
        --validate-only: Run validation stages only

Example:
    $ floe compile --spec floe.yaml --manifest manifest.yaml --output target/
    Compilation successful: target/compiled_artifacts.json

Exit Codes:
    0: Success
    1: Validation error (invalid YAML, schema validation failure)
    2: Compilation error (plugin not found, resolution failure)

See Also:
    - specs/2b-compilation-pipeline/spec.md: Feature specification
"""

from __future__ import annotations

__all__: list[str] = []

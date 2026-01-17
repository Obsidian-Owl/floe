"""YAML loader for floe compilation pipeline.

This module provides functions to load and parse YAML configuration files:
- floe.yaml → FloeSpec
- manifest.yaml → PlatformManifest

The loader handles file reading, YAML parsing, and Pydantic validation,
providing actionable error messages for common issues.

See Also:
    - specs/2b-compilation-pipeline/spec.md: Feature specification
    - FloeSpec: Data product configuration schema
    - PlatformManifest: Platform configuration schema
"""

from __future__ import annotations

from pathlib import Path

from floe_core.compilation.errors import CompilationError, CompilationException
from floe_core.compilation.stages import CompilationStage
from floe_core.schemas.floe_spec import FloeSpec
from floe_core.schemas.manifest import PlatformManifest


def load_floe_spec(path: Path) -> FloeSpec:
    """Load and validate FloeSpec from a YAML file.

    Args:
        path: Path to floe.yaml file.

    Returns:
        Validated FloeSpec instance.

    Raises:
        CompilationException: If file not found, YAML invalid, or validation fails.

    Example:
        >>> spec = load_floe_spec(Path("floe.yaml"))
        >>> spec.metadata.name
        'my-pipeline'
    """
    # TODO: Implement in T029
    raise NotImplementedError("load_floe_spec not yet implemented (T029)")


def load_manifest(path: Path) -> PlatformManifest:
    """Load and validate PlatformManifest from a YAML file.

    Args:
        path: Path to manifest.yaml file.

    Returns:
        Validated PlatformManifest instance.

    Raises:
        CompilationException: If file not found, YAML invalid, or validation fails.

    Example:
        >>> manifest = load_manifest(Path("manifest.yaml"))
        >>> manifest.metadata.name
        'acme-platform'
    """
    # TODO: Implement in T030
    raise NotImplementedError("load_manifest not yet implemented (T030)")


__all__ = ["load_floe_spec", "load_manifest"]

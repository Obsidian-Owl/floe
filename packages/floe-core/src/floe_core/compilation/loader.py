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
from typing import Any, TypeVar, cast

import yaml
from pydantic import BaseModel, ValidationError

from floe_core.compilation.errors import CompilationError, CompilationException
from floe_core.compilation.stages import CompilationStage
from floe_core.schemas.floe_spec import FloeSpec
from floe_core.schemas.manifest import PlatformManifest

T = TypeVar("T", bound=BaseModel)


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed YAML content as dictionary.

    Raises:
        CompilationException: If file not found (E001) or invalid YAML (E002).
    """
    if not path.exists():
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.LOAD,
                code="E001",
                message=f"File not found: {path}",
                suggestion=f"Ensure the file exists at: {path.absolute()}",
                context={"path": str(path)},
            )
        )

    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if data is None:
            return {}
        return cast(dict[str, Any], data)
    except yaml.YAMLError as e:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.LOAD,
                code="E002",
                message=f"Invalid YAML syntax in {path.name}: {e}",
                suggestion="Check YAML syntax - ensure proper indentation and formatting",
                context={"path": str(path), "error": str(e)},
            )
        ) from e


def _validate_model(
    data: dict[str, Any],
    model_class: type[T],
    path: Path,
) -> T:
    """Validate parsed YAML against a Pydantic model.

    Args:
        data: Parsed YAML data.
        model_class: Pydantic model class to validate against.
        path: Original file path (for error context).

    Returns:
        Validated Pydantic model instance.

    Raises:
        CompilationException: If validation fails.
    """
    try:
        return model_class.model_validate(data)
    except ValidationError as e:
        # Extract first error for message
        errors = e.errors()
        if errors:
            first_error = errors[0]
            field_path = ".".join(str(loc) for loc in first_error.get("loc", []))
            error_msg = str(first_error.get("msg", "Invalid value"))
        else:
            field_path = ""
            error_msg = "Validation failed"

        raise CompilationException(
            CompilationError(
                stage=CompilationStage.LOAD,
                code="E103",
                message=f"Validation error in {path.name}: {field_path}: {error_msg}",
                suggestion="Check the schema documentation for valid field values",
                context={
                    "path": str(path),
                    "field": field_path,
                    "message": error_msg,
                    "all_errors": [
                        {
                            "field": ".".join(str(loc) for loc in err.get("loc", [])),
                            "message": err.get("msg", ""),
                        }
                        for err in e.errors()
                    ],
                },
            )
        ) from e


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
    data = _load_yaml(path)
    return _validate_model(data, FloeSpec, path)


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
    data = _load_yaml(path)
    return _validate_model(data, PlatformManifest, path)


__all__ = ["load_floe_spec", "load_manifest"]

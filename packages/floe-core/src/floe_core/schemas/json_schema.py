"""JSON Schema export for IDE autocomplete support.

This module provides functions to export Pydantic models as JSON Schema
for IDE autocomplete and validation in editors like VS Code.

Implements:
    - FR-009: IDE Autocomplete Support
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonSchemaValidationError(Exception):
    """Raised when JSON Schema validation fails.

    Attributes:
        message: Description of the validation error
        path: JSON path to the invalid field (if available)
        value: The invalid value (if available)

    Example:
        >>> raise JsonSchemaValidationError(
        ...     message="Invalid api_version",
        ...     path="api_version",
        ...     value="invalid/v99"
        ... )
    """

    def __init__(
        self,
        message: str,
        path: str | None = None,
        value: Any = None,
    ) -> None:
        """Initialize JsonSchemaValidationError.

        Args:
            message: Description of the validation error
            path: JSON path to the invalid field
            value: The invalid value
        """
        self.path = path
        self.value = value
        if path:
            message = f"{path}: {message}"
        super().__init__(message)


# JSON Schema draft version
JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"

# Schema ID for the manifest schema
MANIFEST_SCHEMA_ID = "https://floe.dev/schemas/manifest.schema.json"


def export_json_schema() -> dict[str, Any]:
    """Export PlatformManifest as JSON Schema.

    Generates a JSON Schema from the PlatformManifest Pydantic model
    with additional metadata for IDE compatibility.

    Returns:
        JSON Schema as a dictionary with $schema, $id, title, and properties

    Example:
        >>> schema = export_json_schema()
        >>> schema["$schema"]
        'https://json-schema.org/draft/2020-12/schema'
        >>> "properties" in schema
        True
    """
    from floe_core.schemas.manifest import PlatformManifest

    # Generate JSON Schema from Pydantic model
    schema = PlatformManifest.model_json_schema(mode="serialization")

    # Add JSON Schema metadata
    schema["$schema"] = JSON_SCHEMA_DRAFT
    schema["$id"] = MANIFEST_SCHEMA_ID

    return schema


def export_json_schema_to_file(path: Path | str) -> None:
    """Export JSON Schema to a file.

    Writes the JSON Schema to the specified file path with pretty formatting.

    Args:
        path: Output file path (will be created/overwritten)

    Example:
        >>> export_json_schema_to_file("manifest.schema.json")
    """
    path = Path(path)
    schema = export_json_schema()

    # Write with pretty formatting for readability
    path.write_text(json.dumps(schema, indent=2) + "\n")


def validate_against_schema(
    data: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """Validate data against a JSON Schema.

    Uses the jsonschema library to validate data against the provided schema.
    This is useful for testing that manifests conform to the exported schema.

    Args:
        data: The data to validate (typically a manifest dict)
        schema: The JSON Schema to validate against

    Raises:
        JsonSchemaValidationError: If validation fails

    Example:
        >>> schema = export_json_schema()
        >>> manifest = {"api_version": "floe.dev/v1", ...}
        >>> validate_against_schema(manifest, schema)  # OK or raises
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError as e:
        raise ImportError(
            "jsonschema package is required for validation. Install with: pip install jsonschema"
        ) from e

    # Create validator with the schema
    validator = Draft202012Validator(schema)

    # Collect all validation errors
    errors = list(validator.iter_errors(data))

    if errors:
        # Get the first (most relevant) error
        error = errors[0]
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else None
        raise JsonSchemaValidationError(
            message=error.message,
            path=path,
            value=error.instance if error.absolute_path else None,
        )


__all__ = [
    "JsonSchemaValidationError",
    "JSON_SCHEMA_DRAFT",
    "MANIFEST_SCHEMA_ID",
    "export_json_schema",
    "export_json_schema_to_file",
    "validate_against_schema",
]

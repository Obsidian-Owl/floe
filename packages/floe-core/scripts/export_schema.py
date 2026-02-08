#!/usr/bin/env python
"""Export JSON Schema for PlatformManifest.

This script generates the JSON Schema from the PlatformManifest Pydantic model
for IDE autocomplete and validation support.

Usage:
    python -m scripts.export_schema [output_path]

    # Default output: specs/001-manifest-schema/contracts/manifest.schema.json
    python -m scripts.export_schema

    # Custom output path
    python -m scripts.export_schema /path/to/output.schema.json

Implements:
    - FR-009: IDE Autocomplete Support
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(output_path: str | None = None) -> None:
    """Export JSON Schema to the specified path.

    Args:
        output_path: Output file path. If None, uses default location.
    """
    from floe_core.schemas.json_schema import export_json_schema_to_file

    # Default output path relative to repo root
    if output_path is None:
        # Find repo root by looking for pyproject.toml
        current = Path(__file__).resolve()
        repo_root = current.parent.parent.parent.parent  # scripts -> floe-core -> packages -> repo
        output_path = str(
            repo_root / "specs" / "001-manifest-schema" / "contracts" / "manifest.schema.json"
        )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    export_json_schema_to_file(path)
    print(f"JSON Schema exported to: {path}")


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else None
    main(output)

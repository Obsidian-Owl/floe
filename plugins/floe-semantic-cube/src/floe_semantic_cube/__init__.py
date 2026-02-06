"""Cube Semantic Layer Plugin for floe.

This package provides the CubeSemanticPlugin implementation for Cube
semantic layer integration, including dbt manifest to Cube schema generation,
datasource configuration delegation, and health monitoring.

Example:
    >>> from floe_core.plugins import get_plugin
    >>> semantic = get_plugin("semantic_layer", "cube")
    >>> files = semantic.sync_from_dbt_manifest(manifest_path, output_dir)

Public API:
    - CubeSemanticPlugin: Main plugin class (implements SemanticLayerPlugin ABC)
    - CubeSemanticConfig: Configuration model for Cube connection
"""

from __future__ import annotations

__version__ = "0.1.0"

# Public API exports - import lazily to avoid circular imports during discovery.
# CubeSemanticPlugin and CubeSemanticConfig are imported here so that the
# entry point `floe_semantic_cube:CubeSemanticPlugin` resolves correctly.
from floe_semantic_cube.config import CubeSemanticConfig
from floe_semantic_cube.errors import (
    CubeDatasourceError,
    CubeHealthCheckError,
    CubeSemanticError,
    SchemaGenerationError,
)
from floe_semantic_cube.plugin import CubeSemanticPlugin
from floe_semantic_cube.schema_generator import CubeSchemaGenerator

__all__ = [
    "__version__",
    "CubeSemanticPlugin",
    "CubeSemanticConfig",
    "CubeSchemaGenerator",
    "CubeSemanticError",
    "SchemaGenerationError",
    "CubeHealthCheckError",
    "CubeDatasourceError",
]

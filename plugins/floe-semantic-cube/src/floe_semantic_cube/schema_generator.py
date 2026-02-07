"""Cube schema generator from dbt manifest.

Converts dbt manifest.json model nodes into Cube YAML schema definitions.
Supports column-to-measure/dimension inference, join conversion from ref()
relationships, pre-aggregation generation from meta tags, and model filtering.

Requirements Covered:
    - FR-010: Parse dbt manifest and convert to Cube YAML
    - FR-011: Each dbt model becomes a Cube with sql_table
    - FR-012: Numeric columns become measures
    - FR-013: Non-numeric columns become dimensions
    - FR-014: dbt ref() -> Cube joins
    - FR-015: dbt meta tags propagate to Cube metadata
    - FR-016: Filter models by schema prefix or tag
    - FR-017: Generated files are valid Cube YAML
    - FR-018: Clean output_dir before writing
    - FR-019: FileNotFoundError for missing manifest
    - FR-020: SchemaGenerationError for malformed manifest
    - FR-021: Pre-aggregations from meta tags
    - FR-022: Rollup type with measure/dimension selections
    - FR-023: refreshKey configuration
    - FR-024: partitionGranularity support
    - FR-025: No pre-aggregation when meta absent
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
import yaml

from floe_semantic_cube.errors import SchemaGenerationError

logger = structlog.get_logger(__name__)

# Numeric SQL types that map to Cube measures
_NUMERIC_TYPES: frozenset[str] = frozenset(
    {
        "integer",
        "int",
        "bigint",
        "smallint",
        "tinyint",
        "float",
        "double",
        "real",
        "decimal",
        "numeric",
        "number",
    }
)

# Time SQL types that map to Cube time dimensions
_TIME_TYPES: frozenset[str] = frozenset(
    {
        "date",
        "timestamp",
        "timestamp_tz",
        "timestamp_ntz",
        "timestamptz",
        "datetime",
        "time",
    }
)

# Boolean SQL types
_BOOLEAN_TYPES: frozenset[str] = frozenset(
    {
        "boolean",
        "bool",
    }
)


class CubeSchemaGenerator:
    """Generate Cube YAML schema files from a dbt manifest.

    Parses a dbt manifest.json, converts model nodes into Cube definitions
    with measures, dimensions, joins, and optional pre-aggregations.

    Args:
        model_filter_schemas: Only include models with matching schema prefixes.
        model_filter_tags: Only include models that have at least one matching tag.

    Example:
        >>> gen = CubeSchemaGenerator(model_filter_tags=["cube"])
        >>> paths = gen.generate(Path("manifest.json"), Path("cube_schemas/"))
    """

    def __init__(
        self,
        *,
        model_filter_schemas: list[str] | None = None,
        model_filter_tags: list[str] | None = None,
    ) -> None:
        self._filter_schemas = model_filter_schemas
        self._filter_tags = model_filter_tags

    def generate(
        self,
        manifest_path: Path,
        output_dir: Path,
    ) -> list[Path]:
        """Generate Cube schema YAML files from dbt manifest.

        Args:
            manifest_path: Path to dbt manifest.json file.
            output_dir: Directory to write generated Cube YAML files.

        Returns:
            List of paths to generated schema files.

        Raises:
            FileNotFoundError: If manifest_path does not exist.
            SchemaGenerationError: If manifest is malformed.
        """
        manifest = self._load_manifest(manifest_path)
        models = self._extract_models(manifest)
        models = self._filter_models(models)

        self._clean_output_dir(output_dir)

        written_paths: list[Path] = []
        for model in models:
            cube_def = self._convert_model_to_cube(model, models)
            file_path = self._write_cube_yaml(cube_def, model["name"], output_dir)
            written_paths.append(file_path)
            logger.debug(
                "cube_schema_generated",
                model=model["name"],
                output=str(file_path),
            )

        logger.info(
            "schema_generation_complete",
            model_count=len(written_paths),
            output_dir=str(output_dir),
        )
        return written_paths

    def _load_manifest(self, manifest_path: Path) -> dict[str, Any]:
        """Load and parse the dbt manifest.json file.

        Args:
            manifest_path: Path to manifest.json.

        Returns:
            Parsed manifest dictionary.

        Raises:
            FileNotFoundError: If the file does not exist.
            SchemaGenerationError: If JSON is invalid.
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        try:
            text = manifest_path.read_text(encoding="utf-8")
            result: dict[str, Any] = json.loads(text)
            return result
        except json.JSONDecodeError as exc:
            raise SchemaGenerationError(f"Invalid JSON in manifest: {exc}") from exc

    def _extract_models(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract model nodes from manifest.

        Args:
            manifest: Parsed manifest dictionary.

        Returns:
            List of model node dictionaries.

        Raises:
            SchemaGenerationError: If 'nodes' key is missing.
        """
        if "nodes" not in manifest:
            raise SchemaGenerationError("Manifest missing required 'nodes' key")

        nodes: dict[str, Any] = manifest["nodes"]
        models: list[dict[str, Any]] = []
        for node in nodes.values():
            if isinstance(node, dict) and node.get("resource_type") == "model":
                models.append(node)

        return models

    def _filter_models(self, models: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter models by schema and/or tag.

        Args:
            models: List of model node dictionaries.

        Returns:
            Filtered list of models.
        """
        result = models

        if self._filter_schemas:
            result = [m for m in result if m.get("schema", "") in self._filter_schemas]

        if self._filter_tags:
            filter_tags_set = set(self._filter_tags)
            result = [m for m in result if filter_tags_set.intersection(m.get("tags", []))]

        return result

    def _convert_model_to_cube(
        self,
        model: dict[str, Any],
        all_models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Convert a dbt model node into a Cube definition.

        Args:
            model: dbt model node dictionary.
            all_models: All model nodes (for resolving joins).

        Returns:
            Cube definition dictionary.
        """
        name = model["name"]
        schema = model.get("schema", "public")
        sql_table = f"{schema}.{name}"

        measures: list[dict[str, Any]] = []
        dimensions: list[dict[str, Any]] = []

        columns: dict[str, Any] = model.get("columns", {})
        for col_name, col_info in columns.items():
            data_type = col_info.get("data_type", "").lower()
            col_meta = col_info.get("meta", {})

            if self._is_numeric_type(data_type):
                measure = self._make_measure(col_name, data_type, col_meta)
                measures.append(measure)
            else:
                dimension = self._make_dimension(col_name, data_type, col_meta)
                dimensions.append(dimension)

        cube: dict[str, Any] = {
            "name": name,
            "sql_table": sql_table,
        }

        if measures:
            cube["measures"] = measures
        else:
            cube["measures"] = []

        if dimensions:
            cube["dimensions"] = dimensions
        else:
            cube["dimensions"] = []

        # Joins from depends_on
        joins = self._make_joins(model, all_models)
        if joins:
            cube["joins"] = joins

        # Pre-aggregations from meta
        pre_aggs = self._make_pre_aggregations(model)
        if pre_aggs:
            cube["pre_aggregations"] = pre_aggs

        return cube

    def _is_numeric_type(self, data_type: str) -> bool:
        """Check if a SQL data type is numeric.

        Args:
            data_type: Lowercase SQL data type string.

        Returns:
            True if the type is numeric.
        """
        return data_type in _NUMERIC_TYPES

    def _make_measure(
        self,
        col_name: str,
        data_type: str,
        meta: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a Cube measure from a numeric column.

        Args:
            col_name: Column name.
            data_type: SQL data type.
            meta: Column meta dictionary.

        Returns:
            Cube measure definition.
        """
        # Check for meta override
        measure_type = meta.get("cube_measure_type")

        if measure_type is None:
            # Heuristic: ID columns use count, others use sum
            if col_name.endswith("_id") or col_name == "id":
                measure_type = "count"
            else:
                measure_type = "sum"

        return {
            "name": col_name,
            "type": measure_type,
            "sql": col_name,
        }

    def _make_dimension(
        self,
        col_name: str,
        data_type: str,
        meta: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a Cube dimension from a non-numeric column.

        Args:
            col_name: Column name.
            data_type: SQL data type.
            meta: Column meta dictionary.

        Returns:
            Cube dimension definition.
        """
        # Check for meta override
        cube_type = meta.get("cube_type")

        if cube_type is None:
            cube_type = self._infer_dimension_type(data_type)

        return {
            "name": col_name,
            "type": cube_type,
            "sql": col_name,
        }

    def _infer_dimension_type(self, data_type: str) -> str:
        """Infer Cube dimension type from SQL data type.

        Args:
            data_type: Lowercase SQL data type string.

        Returns:
            Cube dimension type string.
        """
        if data_type in _TIME_TYPES:
            return "time"
        if data_type in _BOOLEAN_TYPES:
            return "boolean"
        return "string"

    def _make_joins(
        self,
        model: dict[str, Any],
        all_models: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Create Cube joins from dbt depends_on relationships.

        Args:
            model: The model that depends on other models.
            all_models: All models for name resolution.

        Returns:
            List of Cube join definitions.
        """
        depends_on = model.get("depends_on", {}).get("nodes", [])
        if not depends_on:
            return []

        # Build lookup for model unique_id -> name
        model_names: dict[str, str] = {m["unique_id"]: m["name"] for m in all_models}

        model_meta = model.get("meta", {})
        join_relationship_overrides: dict[str, str] = model_meta.get("cube_join_relationship", {})

        joins: list[dict[str, Any]] = []
        for dep_id in depends_on:
            dep_name = model_names.get(dep_id)
            if dep_name is None:
                # Dependency is not a model in our set, skip
                continue

            relationship = join_relationship_overrides.get(dep_name, "belongs_to")

            # Generate default join SQL using shared column name convention
            # Look for common column (e.g., customer_id in both model and dep)
            join_sql = f"{{{model['name']}}}.{dep_name}_id = {{{dep_name}}}.{dep_name}_id"

            joins.append(
                {
                    "name": dep_name,
                    "sql": join_sql,
                    "relationship": relationship,
                }
            )

        return joins

    def _make_pre_aggregations(self, model: dict[str, Any]) -> list[dict[str, Any]]:
        """Create Cube pre-aggregation definitions from meta tags.

        Args:
            model: dbt model node dictionary.

        Returns:
            List of pre-aggregation definitions, empty if no meta tags.
        """
        meta = model.get("meta", {})
        pre_agg_config: dict[str, Any] | None = meta.get("cube_pre_aggregation")

        if not pre_agg_config:
            return []

        pre_aggs: list[dict[str, Any]] = []
        for name, config in pre_agg_config.items():
            pre_agg: dict[str, Any] = {
                "name": name,
                "type": config.get("type", "rollup"),
            }

            if "measures" in config:
                pre_agg["measures"] = config["measures"]

            if "dimensions" in config:
                pre_agg["dimensions"] = config["dimensions"]

            if "time_dimension" in config:
                pre_agg["time_dimension"] = config["time_dimension"]

            if "granularity" in config:
                pre_agg["granularity"] = config["granularity"]

            if "refresh_key" in config:
                pre_agg["refresh_key"] = config["refresh_key"]

            if "partition_granularity" in config:
                pre_agg["partition_granularity"] = config["partition_granularity"]

            pre_aggs.append(pre_agg)

        return pre_aggs

    @staticmethod
    def _clean_output_dir(output_dir: Path) -> None:
        """Remove existing .yaml and .yml files from output directory.

        Args:
            output_dir: Directory to clean.
        """
        for ext in ("*.yaml", "*.yml"):
            for existing in output_dir.glob(ext):
                existing.unlink()

    @staticmethod
    def _write_cube_yaml(
        cube_def: dict[str, Any],
        model_name: str,
        output_dir: Path,
    ) -> Path:
        """Write a Cube definition to a YAML file.

        Args:
            cube_def: Cube definition dictionary.
            model_name: dbt model name for filename.
            output_dir: Directory to write to.

        Returns:
            Path to the written YAML file.

        Raises:
            SchemaGenerationError: If model_name contains path traversal.
        """
        content: dict[str, Any] = {"cubes": [cube_def]}
        file_path = output_dir / f"{model_name}.yaml"
        # Guard against path traversal from untrusted model names
        if not file_path.resolve().is_relative_to(output_dir.resolve()):
            raise SchemaGenerationError(
                f"Model name contains path traversal: {model_name}",
                model_name=model_name,
            )
        file_path.write_text(
            yaml.safe_dump(content, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        return file_path

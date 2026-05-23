"""Cube schema generator from dbt manifest semantic metadata.

Converts dbt manifest.json model nodes into Cube YAML schema definitions.
Publication is deny-by-default: only models with
``meta.floe.semantic.publish: true`` and members explicitly listed under
``meta.floe.semantic`` are emitted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import structlog
import yaml

from floe_semantic_cube.errors import SchemaGenerationError

logger = structlog.get_logger(__name__)

_MEASURE_TYPES: frozenset[str] = frozenset(
    {"avg", "count", "count_distinct", "max", "min", "number", "sum"}
)
_DIMENSION_TYPES: frozenset[str] = frozenset({"boolean", "number", "string", "time"})
_JOIN_RELATIONSHIP_ALIASES: dict[str, str] = {
    "many_to_one": "many_to_one",
    "belongs_to": "many_to_one",
    "belongsTo": "many_to_one",
    "one_to_many": "one_to_many",
    "has_many": "one_to_many",
    "hasMany": "one_to_many",
    "one_to_one": "one_to_one",
    "has_one": "one_to_one",
    "hasOne": "one_to_one",
}
_PRE_AGGREGATION_TYPES: frozenset[str] = frozenset({"rollup", "rollup_join"})
_SENSITIVE_NAME_PARTS: frozenset[str] = frozenset(
    {
        "address",
        "birth_date",
        "card_number",
        "credit_card",
        "dob",
        "email",
        "passport",
        "phone",
        "social_security",
        "ssn",
    }
)
_SENSITIVE_CLASSIFICATIONS: frozenset[str] = frozenset(
    {"confidential", "masked", "pii", "sensitive"}
)
_UNSAFE_JOIN_SQL_TOKENS: tuple[str, ...] = (";", "--", "/*", "*/")
_DEFAULT_JOIN_RELATIONSHIP = "many_to_one"


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
        models = [model for model in models if self._is_model_published(model)]

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
        semantic = self._semantic_config(model)

        measures = self._make_measures(model, semantic)
        standard_dimensions = self._make_dimensions(model, semantic)
        time_dimensions = self._make_time_dimensions(model, semantic)
        dimensions = [*standard_dimensions, *time_dimensions]

        cube: dict[str, Any] = {
            "name": name,
            "sql_table": sql_table,
            "measures": measures,
            "dimensions": dimensions,
        }

        validation_metrics = self._make_validation_metrics(semantic, measures)
        if validation_metrics:
            cube["meta"] = {"floe": {"validation_metrics": validation_metrics}}

        joins = self._make_joins(model, all_models, semantic)
        if joins:
            cube["joins"] = joins

        pre_aggs = self._make_pre_aggregations(
            model,
            semantic,
            published_measures={measure["name"] for measure in measures},
            published_dimensions={dimension["name"] for dimension in standard_dimensions},
            published_time_dimensions={dimension["name"] for dimension in time_dimensions},
        )
        if pre_aggs:
            cube["pre_aggregations"] = pre_aggs

        return cube

    def _is_model_published(self, model: dict[str, Any]) -> bool:
        """Return True when the dbt model explicitly opts into publication."""
        return self._semantic_config(model).get("publish") is True

    def _semantic_config(self, model: dict[str, Any]) -> dict[str, Any]:
        """Extract ``meta.floe.semantic`` from a dbt model node."""
        meta = model.get("meta", {})
        if not isinstance(meta, dict):
            return {}

        floe_meta = meta.get("floe", {})
        if not isinstance(floe_meta, dict):
            return {}

        semantic = floe_meta.get("semantic", {})
        if not isinstance(semantic, dict):
            return {}

        return semantic

    def _make_measures(
        self,
        model: dict[str, Any],
        semantic: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Create Cube measures from explicit semantic metadata."""
        measures_config = self._member_configs(semantic, "measures")
        measures: list[dict[str, Any]] = []
        for name, config in measures_config.items():
            measure_type = self._required_string(config, "type", "measure", name)
            if measure_type not in _MEASURE_TYPES:
                raise SchemaGenerationError(
                    f"Unsupported measure type '{measure_type}' for semantic member '{name}'",
                    model_name=model.get("name"),
                )

            member = self._make_member(model, name, config, "measure", measure_type)
            if member is None:
                continue
            measures.append(member)

        return measures

    def _make_dimensions(
        self,
        model: dict[str, Any],
        semantic: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Create Cube dimensions from explicit semantic metadata."""
        dimensions_config = self._member_configs(semantic, "dimensions")
        dimensions: list[dict[str, Any]] = []
        for name, config in dimensions_config.items():
            dimension_type = self._required_string(config, "type", "dimension", name)
            if dimension_type not in _DIMENSION_TYPES:
                raise SchemaGenerationError(
                    f"Unsupported dimension type '{dimension_type}' for semantic member '{name}'",
                    model_name=model.get("name"),
                )

            member = self._make_member(model, name, config, "dimension", dimension_type)
            if member is None:
                continue
            dimensions.append(member)

        return dimensions

    def _make_time_dimensions(
        self,
        model: dict[str, Any],
        semantic: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Create Cube time dimensions from explicit semantic metadata."""
        time_dimensions_config = self._member_configs(semantic, "time_dimensions")
        time_dimensions: list[dict[str, Any]] = []
        for name, config in time_dimensions_config.items():
            member = self._make_member(model, name, config, "time dimension", "time")
            if member is None:
                continue

            granularities = config.get("granularities")
            if granularities is not None:
                if not isinstance(granularities, list) or not all(
                    isinstance(granularity, str) for granularity in granularities
                ):
                    raise SchemaGenerationError(
                        f"Invalid granularities for semantic member '{name}'",
                        model_name=model.get("name"),
                    )
                member["granularities"] = granularities

            time_dimensions.append(member)

        return time_dimensions

    def _make_member(
        self,
        model: dict[str, Any],
        name: str,
        config: dict[str, Any],
        member_kind: str,
        member_type: str,
    ) -> dict[str, Any] | None:
        """Create a Cube member unless privacy metadata blocks publication."""
        source = self._required_string(config, "source", member_kind, name)
        self._validate_source_column(model, source, member_kind, name)
        block_reason = self._publication_block_reason(model, name, source, config)
        if block_reason is not None:
            logger.info(
                "semantic_member_blocked",
                model=model.get("name"),
                member=name,
                source=source,
                reason=block_reason,
            )
            return None

        member: dict[str, Any] = {
            "name": name,
            "type": member_type,
            "sql": source,
        }

        for key in ("description", "format"):
            if key in config:
                member[key] = config[key]
        if "filters" in config:
            member["filters"] = self._validate_member_filters(model, name, config["filters"])

        return member

    def _make_joins(
        self,
        model: dict[str, Any],
        all_models: list[dict[str, Any]],
        semantic: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Create Cube joins from explicit semantic metadata.

        Args:
            model: dbt model node dictionary.
            all_models: All models for name resolution.
            semantic: Extracted semantic publication metadata.

        Returns:
            List of Cube join definitions.
        """
        joins_config = self._member_configs(semantic, "joins")
        published_model_names = {published_model["name"] for published_model in all_models}
        joins: list[dict[str, Any]] = []
        for name, config in joins_config.items():
            if name not in published_model_names:
                raise SchemaGenerationError(
                    f"Semantic join '{name}' targets unpublished model",
                    model_name=model.get("name"),
                )

            join_sql = self._required_string(config, "sql", "join", name)
            self._validate_join_sql(model, name, join_sql)
            relationship = self._normalize_join_relationship(model, name, config)

            joins.append({"name": name, "sql": join_sql, "relationship": relationship})

        return joins

    def _normalize_join_relationship(
        self,
        model: dict[str, Any],
        name: str,
        config: dict[str, Any],
    ) -> str:
        """Return a canonical Cube relationship value for a semantic join."""
        relationship = config.get("relationship", _DEFAULT_JOIN_RELATIONSHIP)
        if not isinstance(relationship, str) or relationship not in _JOIN_RELATIONSHIP_ALIASES:
            raise SchemaGenerationError(
                f"Unsupported join relationship '{relationship}' for semantic join '{name}'",
                model_name=model.get("name"),
            )
        return _JOIN_RELATIONSHIP_ALIASES[relationship]

    def _validate_join_sql(self, model: dict[str, Any], name: str, join_sql: str) -> None:
        """Reject tokens that would turn a join expression into a SQL statement."""
        self._validate_sql_expression(model, name, "join", join_sql)

    def _validate_member_filters(
        self,
        model: dict[str, Any],
        name: str,
        filters: Any,
    ) -> list[dict[str, Any]]:
        """Validate Cube filter metadata before passing it through."""
        if not isinstance(filters, list) or not all(
            isinstance(filter_config, dict) for filter_config in filters
        ):
            raise SchemaGenerationError(
                f"Semantic member '{name}' filters must be a list of objects",
                model_name=model.get("name"),
            )

        for filter_config in filters:
            sql = filter_config.get("sql")
            if sql is None:
                continue
            if not isinstance(sql, str) or not sql:
                raise SchemaGenerationError(
                    f"Semantic member '{name}' filter sql must be a non-empty string",
                    model_name=model.get("name"),
                )
            self._validate_sql_expression(model, name, "filter", sql)

        return filters

    def _validate_sql_expression(
        self,
        model: dict[str, Any],
        name: str,
        expression_kind: str,
        sql: str,
    ) -> None:
        """Reject tokens that would turn a SQL expression into a statement."""
        for token in _UNSAFE_JOIN_SQL_TOKENS:
            if token in sql:
                raise SchemaGenerationError(
                    f"Semantic {expression_kind} '{name}' contains unsafe SQL token '{token}'",
                    model_name=model.get("name"),
                )

    def _make_pre_aggregations(
        self,
        model: dict[str, Any],
        semantic: dict[str, Any],
        *,
        published_measures: set[str],
        published_dimensions: set[str],
        published_time_dimensions: set[str],
    ) -> list[dict[str, Any]]:
        """Create Cube pre-aggregation definitions from explicit semantic metadata."""
        pre_aggregation_config = self._member_configs(semantic, "pre_aggregations")

        pre_aggregations: list[dict[str, Any]] = []
        for name, config in pre_aggregation_config.items():
            pre_aggregation_type = config.get("type", "rollup")
            if (
                not isinstance(pre_aggregation_type, str)
                or pre_aggregation_type not in _PRE_AGGREGATION_TYPES
            ):
                raise SchemaGenerationError(
                    f"Unsupported pre-aggregation type '{pre_aggregation_type}' "
                    f"for semantic pre-aggregation '{name}'"
                )

            pre_aggregation: dict[str, Any] = {
                "name": name,
                "type": pre_aggregation_type,
            }
            self._validate_pre_aggregation_references(
                model,
                name,
                config,
                published_measures=published_measures,
                published_dimensions=published_dimensions,
                published_time_dimensions=published_time_dimensions,
            )
            for key in (
                "measures",
                "dimensions",
                "time_dimension",
                "granularity",
                "refresh_key",
                "partition_granularity",
            ):
                if key in config:
                    pre_aggregation[key] = config[key]

            pre_aggregations.append(pre_aggregation)

        return pre_aggregations

    def _validate_pre_aggregation_references(
        self,
        model: dict[str, Any],
        name: str,
        config: dict[str, Any],
        *,
        published_measures: set[str],
        published_dimensions: set[str],
        published_time_dimensions: set[str],
    ) -> None:
        """Validate pre-aggregations reference only published semantic members."""
        self._validate_reference_list(
            model,
            name,
            config,
            "measures",
            published_measures,
            "measure",
        )
        self._validate_reference_list(
            model,
            name,
            config,
            "dimensions",
            published_dimensions,
            "dimension",
        )

        time_dimension = config.get("time_dimension")
        if time_dimension is None:
            return
        if not isinstance(time_dimension, str):
            raise SchemaGenerationError(
                f"Semantic pre-aggregation '{name}' time_dimension must be a string",
                model_name=model.get("name"),
            )
        if time_dimension not in published_time_dimensions:
            raise SchemaGenerationError(
                f"Semantic pre-aggregation '{name}' references unpublished "
                f"time_dimension '{time_dimension}'",
                model_name=model.get("name"),
            )

    def _validate_reference_list(
        self,
        model: dict[str, Any],
        pre_aggregation_name: str,
        config: dict[str, Any],
        key: str,
        published_names: set[str],
        member_kind: str,
    ) -> None:
        """Validate a pre-aggregation member reference list."""
        if key not in config:
            return

        references = config.get(key, [])
        if not isinstance(references, list) or not all(
            isinstance(reference, str) for reference in references
        ):
            raise SchemaGenerationError(
                f"Semantic pre-aggregation '{pre_aggregation_name}' {key} "
                "must be a list of member names",
                model_name=model.get("name"),
            )

        unpublished = [reference for reference in references if reference not in published_names]
        if unpublished:
            raise SchemaGenerationError(
                f"Semantic pre-aggregation '{pre_aggregation_name}' references "
                f"unpublished {member_kind}(s): {', '.join(sorted(unpublished))}",
                model_name=model.get("name"),
            )

    def _make_validation_metrics(
        self,
        semantic: dict[str, Any],
        measures: list[dict[str, Any]],
    ) -> list[str]:
        """Return explicit validation metrics that reference published measures."""
        validation_metrics = semantic.get("validation_metrics", [])
        if validation_metrics is None:
            return []
        if not isinstance(validation_metrics, list) or not all(
            isinstance(metric, str) for metric in validation_metrics
        ):
            raise SchemaGenerationError("validation_metrics must be a list of measure names")

        published_measure_names = {measure["name"] for measure in measures}
        unknown_metrics = [
            metric for metric in validation_metrics if metric not in published_measure_names
        ]
        if unknown_metrics:
            raise SchemaGenerationError(
                "validation_metrics references unpublished measure(s): "
                + ", ".join(sorted(unknown_metrics))
            )

        return validation_metrics

    def _member_configs(
        self,
        semantic: dict[str, Any],
        key: str,
    ) -> dict[str, dict[str, Any]]:
        """Return a semantic member mapping after validating its shape."""
        raw_config = semantic.get(key, {})
        if raw_config is None:
            return {}
        if not isinstance(raw_config, dict):
            raise SchemaGenerationError(f"meta.floe.semantic.{key} must be a mapping")

        configs: dict[str, dict[str, Any]] = {}
        for name, config in raw_config.items():
            if not isinstance(name, str) or not isinstance(config, dict):
                raise SchemaGenerationError(
                    f"meta.floe.semantic.{key} entries must map names to objects"
                )
            configs[name] = config

        return configs

    def _required_string(
        self,
        config: dict[str, Any],
        key: str,
        member_kind: str,
        name: str,
    ) -> str:
        """Read a required string value from member metadata."""
        value = config.get(key)
        if not isinstance(value, str) or not value:
            raise SchemaGenerationError(
                f"Semantic {member_kind} '{name}' requires string field '{key}'"
            )
        return value

    def _validate_source_column(
        self,
        model: dict[str, Any],
        source: str,
        member_kind: str,
        name: str,
    ) -> None:
        """Require semantic member sources to reference exact dbt manifest columns."""
        columns = model.get("columns", {})
        if not isinstance(columns, dict) or source not in columns:
            raise SchemaGenerationError(
                f"Semantic {member_kind} '{name}' source must be an exact dbt column name: "
                f"{source}",
                model_name=model.get("name"),
            )

    def _is_publication_blocked(
        self,
        model: dict[str, Any],
        member_name: str,
        source: str,
        config: dict[str, Any],
    ) -> bool:
        """Return True when a member points at a sensitive source without policy."""
        return self._publication_block_reason(model, member_name, source, config) is not None

    def _publication_block_reason(
        self,
        model: dict[str, Any],
        member_name: str,
        source: str,
        config: dict[str, Any],
    ) -> str | None:
        """Return why publication is blocked, or None when publication is allowed."""
        if self._has_safe_publication_policy(config):
            return None

        columns = model.get("columns", {})
        column_info = columns.get(source, {}) if isinstance(columns, dict) else {}
        column_meta = column_info.get("meta", {}) if isinstance(column_info, dict) else {}

        if self._has_sensitive_name(member_name):
            return "sensitive_member_name"
        if self._has_sensitive_name(source):
            return "sensitive_source_name"
        if self._has_sensitive_column_meta(column_meta):
            return "sensitive_column_metadata"
        return None

    def _has_safe_publication_policy(self, config: dict[str, Any]) -> bool:
        """Return True when member metadata explicitly permits publication."""
        policy = config.get("policy", {})
        if isinstance(policy, dict) and policy.get("safe_for_publication") is True:
            return True
        return False

    def _has_sensitive_name(self, name: str) -> bool:
        """Return True when a field name looks like direct personal data."""
        normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()
        tokens = [token for token in re.split(r"[^a-z0-9]+", normalized) if token]
        for part in _SENSITIVE_NAME_PARTS:
            part_tokens = part.split("_")
            if len(part_tokens) == 1:
                if part_tokens[0] in tokens:
                    return True
                continue
            for index in range(0, len(tokens) - len(part_tokens) + 1):
                if tokens[index : index + len(part_tokens)] == part_tokens:
                    return True
        return False

    def _has_sensitive_column_meta(self, column_meta: Any) -> bool:
        """Return True when dbt column metadata marks a source as sensitive."""
        if not isinstance(column_meta, dict):
            return False

        if column_meta.get("sensitive") is True:
            return True
        if column_meta.get("masked") is True:
            return True
        if column_meta.get("pii") is True:
            return True
        if column_meta.get("contains_pii") is True:
            return True
        # dbt masking_policy values are string policy names; any non-empty value is sensitive.
        if column_meta.get("masking_policy"):
            return True

        classification = column_meta.get("classification")
        if isinstance(classification, str):
            return classification.lower() in _SENSITIVE_CLASSIFICATIONS

        policy = column_meta.get("policy", {})
        if isinstance(policy, dict):
            sensitivity = policy.get("sensitivity")
            if isinstance(sensitivity, str):
                return sensitivity.lower() in _SENSITIVE_CLASSIFICATIONS

        return False

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

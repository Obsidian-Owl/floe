"""Unit tests for CubeSchemaGenerator.

Tests validate dbt manifest-to-Cube YAML schema generation including model
filtering, column inference, join conversion, pre-aggregation generation,
and YAML file output.

Requirements Covered:
    - FR-010: Parse dbt manifest and convert to Cube YAML
    - FR-011: Each dbt model becomes a Cube with sql_table
    - FR-012: Numeric columns become measures
    - FR-013: Non-numeric columns become dimensions
    - FR-014: dbt ref() relationships become Cube joins
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
    - SC-004: 10-model manifest < 2s
    - SC-005: Generated YAML structural validation
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

from floe_semantic_cube.errors import SchemaGenerationError
from floe_semantic_cube.schema_generator import CubeSchemaGenerator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manifest(
    nodes: dict[str, Any] | None = None,
    *,
    valid_metadata: bool = True,
) -> dict[str, Any]:
    """Build a minimal dbt manifest dict."""
    manifest: dict[str, Any] = {}
    if valid_metadata:
        manifest["metadata"] = {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12/manifest.json",
            "dbt_version": "1.9.0",
        }
    manifest["nodes"] = nodes or {}
    return manifest


def _make_model(
    name: str,
    *,
    schema: str = "gold",
    database: str = "analytics",
    columns: dict[str, dict[str, Any]] | None = None,
    depends_on_nodes: list[str] | None = None,
    meta: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal dbt model node."""
    return {
        "unique_id": f"model.analytics.{name}",
        "resource_type": "model",
        "name": name,
        "schema": schema,
        "database": database,
        "depends_on": {"nodes": depends_on_nodes or []},
        "columns": columns or {},
        "meta": meta or {},
        "tags": tags or [],
        "config": {"materialized": "table"},
    }


def _make_column(
    name: str,
    data_type: str,
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal column entry."""
    return {
        "name": name,
        "data_type": data_type,
        "meta": meta or {},
    }


def _write_manifest(tmp_path: Path, manifest: dict[str, Any]) -> Path:
    """Write manifest to a JSON file and return its path."""
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    return path


def _read_generated_yaml(path: Path) -> dict[str, Any]:
    """Read and parse a generated YAML file."""
    return yaml.safe_load(path.read_text())


# ---------------------------------------------------------------------------
# Test: Single model conversion
# ---------------------------------------------------------------------------

@pytest.mark.requirement("FR-010")
@pytest.mark.requirement("FR-011")
class TestSingleModelConversion:
    """Test basic dbt model to Cube YAML conversion."""

    def test_single_model_produces_one_yaml_file(
        self, tmp_path: Path
    ) -> None:
        """Test that a single model produces exactly one YAML file."""
        manifest = _make_manifest({
            "model.analytics.customers": _make_model(
                "customers",
                columns={
                    "customer_id": _make_column("customer_id", "integer"),
                    "name": _make_column("name", "varchar"),
                },
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        result = gen.generate(manifest_path, output_dir)

        assert len(result) == 1
        assert result[0].suffix in (".yaml", ".yml")

    def test_cube_name_matches_model_name(self, tmp_path: Path) -> None:
        """Test that generated cube name matches dbt model name."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={"order_id": _make_column("order_id", "integer")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        assert len(yaml_files) == 1
        content = _read_generated_yaml(yaml_files[0])
        cubes = content.get("cubes", [])
        assert len(cubes) == 1
        assert cubes[0]["name"] == "orders"

    def test_sql_table_uses_schema_dot_name(self, tmp_path: Path) -> None:
        """Test that sql_table is schema.model_name per FR-011."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                schema="gold",
                columns={"order_id": _make_column("order_id", "integer")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        assert content["cubes"][0]["sql_table"] == "gold.orders"


# ---------------------------------------------------------------------------
# Test: Column-to-measure inference
# ---------------------------------------------------------------------------

@pytest.mark.requirement("FR-012")
class TestNumericColumnToMeasure:
    """Test that numeric columns become Cube measures."""

    @pytest.mark.parametrize("data_type", [
        "integer", "int", "bigint", "smallint",
        "float", "double", "real",
        "decimal", "numeric", "number",
    ])
    def test_numeric_types_become_measures(
        self, tmp_path: Path, data_type: str
    ) -> None:
        """Test that various numeric SQL types map to measures."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={"amount": _make_column("amount", data_type)},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        cube = content["cubes"][0]
        measure_names = [m["name"] for m in cube.get("measures", [])]
        assert "amount" in measure_names

    def test_numeric_column_default_aggregation_is_sum(
        self, tmp_path: Path
    ) -> None:
        """Test default aggregation for non-ID numeric columns is sum."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={"total_amount": _make_column("total_amount", "decimal")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        measures = content["cubes"][0]["measures"]
        total = next(m for m in measures if m["name"] == "total_amount")
        assert total["type"] == "sum"

    def test_id_column_heuristic_uses_count(self, tmp_path: Path) -> None:
        """Test that ID columns (ending in _id) use count aggregation."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={"order_id": _make_column("order_id", "integer")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        measures = content["cubes"][0]["measures"]
        order_id = next(m for m in measures if m["name"] == "order_id")
        assert order_id["type"] == "count"

    def test_meta_cube_measure_type_overrides_default(
        self, tmp_path: Path
    ) -> None:
        """Test meta.cube_measure_type overrides default aggregation (FR-015)."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={
                    "amount": _make_column(
                        "amount", "decimal",
                        meta={"cube_measure_type": "avg"},
                    ),
                },
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        measures = content["cubes"][0]["measures"]
        amount = next(m for m in measures if m["name"] == "amount")
        assert amount["type"] == "avg"


# ---------------------------------------------------------------------------
# Test: Column-to-dimension inference
# ---------------------------------------------------------------------------

@pytest.mark.requirement("FR-013")
class TestNonNumericColumnToDimension:
    """Test that non-numeric columns become Cube dimensions."""

    @pytest.mark.parametrize("data_type,expected_type", [
        ("varchar", "string"),
        ("string", "string"),
        ("text", "string"),
        ("char", "string"),
        ("date", "time"),
        ("timestamp", "time"),
        ("timestamp_tz", "time"),
        ("datetime", "time"),
        ("boolean", "boolean"),
        ("bool", "boolean"),
    ])
    def test_non_numeric_types_become_dimensions(
        self, tmp_path: Path, data_type: str, expected_type: str
    ) -> None:
        """Test that non-numeric SQL types map to dimensions with correct Cube type."""
        manifest = _make_manifest({
            "model.analytics.customers": _make_model(
                "customers",
                columns={"col": _make_column("col", data_type)},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        cube = content["cubes"][0]
        dims = cube.get("dimensions", [])
        col_dim = next(d for d in dims if d["name"] == "col")
        assert col_dim["type"] == expected_type

    def test_meta_cube_type_overrides_inferred_type(
        self, tmp_path: Path
    ) -> None:
        """Test meta.cube_type overrides inferred dimension type (FR-015)."""
        manifest = _make_manifest({
            "model.analytics.customers": _make_model(
                "customers",
                columns={
                    "status": _make_column(
                        "status", "varchar",
                        meta={"cube_type": "number"},
                    ),
                },
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        dims = content["cubes"][0]["dimensions"]
        status = next(d for d in dims if d["name"] == "status")
        assert status["type"] == "number"


# ---------------------------------------------------------------------------
# Test: Join conversion
# ---------------------------------------------------------------------------

@pytest.mark.requirement("FR-014")
class TestRefToJoinConversion:
    """Test dbt ref() relationships convert to Cube joins."""

    def test_depends_on_creates_join(self, tmp_path: Path) -> None:
        """Test depends_on.nodes creates Cube join entries."""
        manifest = _make_manifest({
            "model.analytics.customers": _make_model(
                "customers",
                columns={"customer_id": _make_column("customer_id", "integer")},
            ),
            "model.analytics.orders": _make_model(
                "orders",
                columns={
                    "order_id": _make_column("order_id", "integer"),
                    "customer_id": _make_column("customer_id", "integer"),
                },
                depends_on_nodes=["model.analytics.customers"],
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        # Find the orders cube YAML
        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        orders_content = None
        for f in yaml_files:
            content = _read_generated_yaml(f)
            if content["cubes"][0]["name"] == "orders":
                orders_content = content
                break
        assert orders_content is not None
        joins = orders_content["cubes"][0].get("joins", [])
        assert len(joins) >= 1
        join_names = [j["name"] for j in joins]
        assert "customers" in join_names

    def test_default_join_relationship_is_belongs_to(
        self, tmp_path: Path
    ) -> None:
        """Test default join relationship is belongs_to."""
        manifest = _make_manifest({
            "model.analytics.customers": _make_model(
                "customers",
                columns={"customer_id": _make_column("customer_id", "integer")},
            ),
            "model.analytics.orders": _make_model(
                "orders",
                columns={
                    "order_id": _make_column("order_id", "integer"),
                    "customer_id": _make_column("customer_id", "integer"),
                },
                depends_on_nodes=["model.analytics.customers"],
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        for f in yaml_files:
            content = _read_generated_yaml(f)
            if content["cubes"][0]["name"] == "orders":
                joins = content["cubes"][0]["joins"]
                customer_join = next(j for j in joins if j["name"] == "customers")
                assert customer_join["relationship"] == "belongs_to"
                break

    def test_meta_cube_join_relationship_overrides_default(
        self, tmp_path: Path
    ) -> None:
        """Test meta.cube_join_relationship overrides default."""
        manifest = _make_manifest({
            "model.analytics.customers": _make_model(
                "customers",
                columns={"customer_id": _make_column("customer_id", "integer")},
            ),
            "model.analytics.orders": _make_model(
                "orders",
                columns={
                    "order_id": _make_column("order_id", "integer"),
                    "customer_id": _make_column("customer_id", "integer"),
                },
                depends_on_nodes=["model.analytics.customers"],
                meta={"cube_join_relationship": {"customers": "has_many"}},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        for f in yaml_files:
            content = _read_generated_yaml(f)
            if content["cubes"][0]["name"] == "orders":
                joins = content["cubes"][0]["joins"]
                customer_join = next(j for j in joins if j["name"] == "customers")
                assert customer_join["relationship"] == "has_many"
                break


# ---------------------------------------------------------------------------
# Test: Multi-model generation
# ---------------------------------------------------------------------------

@pytest.mark.requirement("FR-010")
@pytest.mark.requirement("FR-017")
class TestMultiModelGeneration:
    """Test multi-model manifest produces multiple YAML files."""

    def test_three_models_produce_three_yaml_files(
        self, tmp_path: Path
    ) -> None:
        """Test that three models produce three separate YAML files."""
        manifest = _make_manifest({
            "model.analytics.customers": _make_model(
                "customers",
                columns={"customer_id": _make_column("customer_id", "integer")},
            ),
            "model.analytics.orders": _make_model(
                "orders",
                columns={"order_id": _make_column("order_id", "integer")},
            ),
            "model.analytics.products": _make_model(
                "products",
                columns={"product_id": _make_column("product_id", "integer")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        result = gen.generate(manifest_path, output_dir)

        assert len(result) == 3


# ---------------------------------------------------------------------------
# Test: Model filtering
# ---------------------------------------------------------------------------

@pytest.mark.requirement("FR-016")
class TestModelFiltering:
    """Test filtering models by schema prefix or tag."""

    def test_filter_by_schema(self, tmp_path: Path) -> None:
        """Test filtering models by schema prefix."""
        manifest = _make_manifest({
            "model.analytics.customers": _make_model(
                "customers",
                schema="gold",
                columns={"customer_id": _make_column("customer_id", "integer")},
            ),
            "model.analytics.raw_events": _make_model(
                "raw_events",
                schema="staging",
                columns={"event_id": _make_column("event_id", "integer")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator(model_filter_schemas=["gold"])
        result = gen.generate(manifest_path, output_dir)

        assert len(result) == 1
        content = _read_generated_yaml(result[0])
        assert content["cubes"][0]["name"] == "customers"

    def test_filter_by_tag(self, tmp_path: Path) -> None:
        """Test filtering models by tag."""
        manifest = _make_manifest({
            "model.analytics.customers": _make_model(
                "customers",
                tags=["cube", "analytics"],
                columns={"customer_id": _make_column("customer_id", "integer")},
            ),
            "model.analytics.raw_events": _make_model(
                "raw_events",
                tags=["staging"],
                columns={"event_id": _make_column("event_id", "integer")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator(model_filter_tags=["cube"])
        result = gen.generate(manifest_path, output_dir)

        assert len(result) == 1
        content = _read_generated_yaml(result[0])
        assert content["cubes"][0]["name"] == "customers"

    def test_no_filter_includes_all_models(self, tmp_path: Path) -> None:
        """Test no filters returns all model nodes."""
        manifest = _make_manifest({
            "model.analytics.customers": _make_model(
                "customers",
                schema="gold",
                columns={"customer_id": _make_column("customer_id", "integer")},
            ),
            "model.analytics.raw_events": _make_model(
                "raw_events",
                schema="staging",
                columns={"event_id": _make_column("event_id", "integer")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        result = gen.generate(manifest_path, output_dir)

        assert len(result) == 2


# ---------------------------------------------------------------------------
# Test: Pre-aggregation generation
# ---------------------------------------------------------------------------

@pytest.mark.requirement("FR-021")
@pytest.mark.requirement("FR-022")
class TestPreAggregationGeneration:
    """Test pre-aggregation generation from meta tags."""

    def test_meta_cube_pre_aggregation_generates_block(
        self, tmp_path: Path
    ) -> None:
        """Test meta.cube_pre_aggregation triggers pre-aggregation generation."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={
                    "order_id": _make_column("order_id", "integer"),
                    "total": _make_column("total", "decimal"),
                    "order_date": _make_column("order_date", "date"),
                },
                meta={
                    "cube_pre_aggregation": {
                        "main": {
                            "type": "rollup",
                            "measures": ["total"],
                            "dimensions": ["order_date"],
                            "time_dimension": "order_date",
                            "granularity": "day",
                        },
                    },
                },
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        cube = content["cubes"][0]
        assert "pre_aggregations" in cube
        pre_aggs = cube["pre_aggregations"]
        assert len(pre_aggs) >= 1
        assert pre_aggs[0]["name"] == "main"
        assert pre_aggs[0]["type"] == "rollup"


@pytest.mark.requirement("FR-023")
class TestPreAggregationRefreshKey:
    """Test pre-aggregation refreshKey configuration."""

    def test_refresh_key_every(self, tmp_path: Path) -> None:
        """Test refreshKey with every configuration."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={
                    "total": _make_column("total", "decimal"),
                    "order_date": _make_column("order_date", "date"),
                },
                meta={
                    "cube_pre_aggregation": {
                        "main": {
                            "type": "rollup",
                            "measures": ["total"],
                            "time_dimension": "order_date",
                            "granularity": "day",
                            "refresh_key": {"every": "1 hour"},
                        },
                    },
                },
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        pre_agg = content["cubes"][0]["pre_aggregations"][0]
        assert pre_agg["refresh_key"]["every"] == "1 hour"


@pytest.mark.requirement("FR-024")
class TestPreAggregationPartitionGranularity:
    """Test pre-aggregation partitionGranularity support."""

    def test_partition_granularity(self, tmp_path: Path) -> None:
        """Test partitionGranularity in pre-aggregation."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={
                    "total": _make_column("total", "decimal"),
                    "order_date": _make_column("order_date", "date"),
                },
                meta={
                    "cube_pre_aggregation": {
                        "main": {
                            "type": "rollup",
                            "measures": ["total"],
                            "time_dimension": "order_date",
                            "granularity": "day",
                            "partition_granularity": "month",
                        },
                    },
                },
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        pre_agg = content["cubes"][0]["pre_aggregations"][0]
        assert pre_agg["partition_granularity"] == "month"


@pytest.mark.requirement("FR-025")
class TestNoPreAggregationWhenAbsent:
    """Test no pre-aggregation when meta is absent."""

    def test_no_pre_aggregation_meta_means_no_block(
        self, tmp_path: Path
    ) -> None:
        """Test that models without meta.cube_pre_aggregation have no pre_aggregations."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={"order_id": _make_column("order_id", "integer")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        cube = content["cubes"][0]
        assert "pre_aggregations" not in cube or cube.get("pre_aggregations") == []


# ---------------------------------------------------------------------------
# Test: Output directory cleanup
# ---------------------------------------------------------------------------

@pytest.mark.requirement("FR-018")
class TestOutputDirCleanup:
    """Test output_dir is cleaned before writing."""

    def test_existing_yaml_files_are_deleted(self, tmp_path: Path) -> None:
        """Test that existing .yaml files in output_dir are removed."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={"order_id": _make_column("order_id", "integer")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create pre-existing YAML files
        (output_dir / "old_cube.yaml").write_text("old: content")
        (output_dir / "another.yml").write_text("old: data")
        # Non-YAML file should NOT be deleted
        (output_dir / "keep_me.txt").write_text("keep")

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        # Old YAML files should be gone
        assert not (output_dir / "old_cube.yaml").exists()
        assert not (output_dir / "another.yml").exists()
        # Non-YAML file should remain
        assert (output_dir / "keep_me.txt").exists()


# ---------------------------------------------------------------------------
# Test: Edge cases and error handling
# ---------------------------------------------------------------------------

@pytest.mark.requirement("FR-019")
class TestMissingManifest:
    """Test FileNotFoundError for missing manifest."""

    def test_missing_manifest_raises_file_not_found(
        self, tmp_path: Path
    ) -> None:
        """Test that a missing manifest file raises FileNotFoundError."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        missing_path = tmp_path / "nonexistent_manifest.json"

        gen = CubeSchemaGenerator()
        with pytest.raises(FileNotFoundError):
            gen.generate(missing_path, output_dir)


@pytest.mark.requirement("FR-020")
class TestMalformedManifest:
    """Test SchemaGenerationError for malformed manifest."""

    def test_invalid_json_raises_schema_generation_error(
        self, tmp_path: Path
    ) -> None:
        """Test invalid JSON raises SchemaGenerationError."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("{invalid json content!!!")

        gen = CubeSchemaGenerator()
        with pytest.raises(SchemaGenerationError, match="manifest"):
            gen.generate(manifest_path, output_dir)

    def test_missing_nodes_key_raises_schema_generation_error(
        self, tmp_path: Path
    ) -> None:
        """Test manifest without 'nodes' key raises SchemaGenerationError."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"metadata": {}}))

        gen = CubeSchemaGenerator()
        with pytest.raises(SchemaGenerationError, match="nodes"):
            gen.generate(manifest_path, output_dir)


@pytest.mark.requirement("FR-010")
class TestEdgeCases:
    """Test edge cases for schema generation."""

    def test_empty_manifest_returns_empty_list(self, tmp_path: Path) -> None:
        """Test empty manifest (no model nodes) returns empty list."""
        manifest = _make_manifest({})
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        result = gen.generate(manifest_path, output_dir)

        assert result == []

    def test_model_with_no_columns_produces_cube_without_measures_or_dims(
        self, tmp_path: Path
    ) -> None:
        """Test model with no columns produces a cube with empty measures/dimensions."""
        manifest = _make_manifest({
            "model.analytics.empty_model": _make_model("empty_model"),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        result = gen.generate(manifest_path, output_dir)

        assert len(result) == 1
        content = _read_generated_yaml(result[0])
        cube = content["cubes"][0]
        assert cube.get("measures", []) == []
        assert cube.get("dimensions", []) == []

    def test_special_characters_in_model_name(self, tmp_path: Path) -> None:
        """Test model names with underscores and numbers work correctly."""
        manifest = _make_manifest({
            "model.analytics.order_items_v2": _make_model(
                "order_items_v2",
                columns={"item_id": _make_column("item_id", "integer")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        result = gen.generate(manifest_path, output_dir)

        assert len(result) == 1
        content = _read_generated_yaml(result[0])
        assert content["cubes"][0]["name"] == "order_items_v2"

    def test_non_model_nodes_are_ignored(self, tmp_path: Path) -> None:
        """Test that non-model nodes (seeds, sources) are ignored."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={"order_id": _make_column("order_id", "integer")},
            ),
            "seed.analytics.countries": {
                "unique_id": "seed.analytics.countries",
                "resource_type": "seed",
                "name": "countries",
            },
            "source.analytics.raw_data": {
                "unique_id": "source.analytics.raw_data",
                "resource_type": "source",
                "name": "raw_data",
            },
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        result = gen.generate(manifest_path, output_dir)

        assert len(result) == 1


# ---------------------------------------------------------------------------
# Test: Performance
# ---------------------------------------------------------------------------

@pytest.mark.requirement("SC-004")
class TestPerformance:
    """Test schema generation performance."""

    def test_ten_model_manifest_under_two_seconds(
        self, tmp_path: Path
    ) -> None:
        """Test 10-model manifest generates within 2 seconds (SC-004)."""
        nodes: dict[str, Any] = {}
        for i in range(10):
            name = f"model_{i}"
            nodes[f"model.analytics.{name}"] = _make_model(
                name,
                columns={
                    f"id_{i}": _make_column(f"id_{i}", "integer"),
                    f"name_{i}": _make_column(f"name_{i}", "varchar"),
                    f"amount_{i}": _make_column(f"amount_{i}", "decimal"),
                    f"created_at_{i}": _make_column(f"created_at_{i}", "timestamp"),
                },
            )
        manifest = _make_manifest(nodes)
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        start = time.perf_counter()
        result = gen.generate(manifest_path, output_dir)
        elapsed = time.perf_counter() - start

        assert len(result) == 10
        assert elapsed < 2.0


# ---------------------------------------------------------------------------
# Test: YAML structural validation
# ---------------------------------------------------------------------------

@pytest.mark.requirement("SC-005")
@pytest.mark.requirement("FR-017")
class TestYamlStructuralValidation:
    """Test generated YAML files have correct structure."""

    def test_generated_yaml_has_cubes_list(self, tmp_path: Path) -> None:
        """Test generated YAML has top-level cubes list."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={
                    "order_id": _make_column("order_id", "integer"),
                    "status": _make_column("status", "varchar"),
                },
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        for yaml_file in yaml_files:
            content = _read_generated_yaml(yaml_file)
            assert "cubes" in content
            assert isinstance(content["cubes"], list)
            for cube in content["cubes"]:
                assert "name" in cube
                assert "sql_table" in cube

    def test_measures_have_name_type_and_sql(self, tmp_path: Path) -> None:
        """Test measures have required name, type, and sql fields."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={"total": _make_column("total", "decimal")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        for measure in content["cubes"][0].get("measures", []):
            assert "name" in measure
            assert "type" in measure
            assert "sql" in measure

    def test_dimensions_have_name_type_and_sql(self, tmp_path: Path) -> None:
        """Test dimensions have required name, type, and sql fields."""
        manifest = _make_manifest({
            "model.analytics.orders": _make_model(
                "orders",
                columns={"status": _make_column("status", "varchar")},
            ),
        })
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        gen = CubeSchemaGenerator()
        gen.generate(manifest_path, output_dir)

        yaml_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
        content = _read_generated_yaml(yaml_files[0])
        for dim in content["cubes"][0].get("dimensions", []):
            assert "name" in dim
            assert "type" in dim
            assert "sql" in dim

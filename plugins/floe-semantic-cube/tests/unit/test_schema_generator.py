"""Unit tests for deny-by-default Cube schema generation.

The schema generator consumes dbt manifest model metadata from
``meta.floe.semantic`` and publishes only explicitly opted-in semantic members.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from floe_semantic_cube import schema_generator as schema_generator_module
from floe_semantic_cube.errors import SchemaGenerationError
from floe_semantic_cube.schema_generator import CubeSchemaGenerator

pytestmark = pytest.mark.requirement("SEMANTIC-PUBLICATION-UX")


def _make_manifest(nodes: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a minimal dbt manifest dict."""
    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12/manifest.json",
            "dbt_version": "1.9.0",
        },
        "nodes": nodes or {},
    }


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
    """Build a minimal dbt manifest column entry."""
    return {
        "name": name,
        "data_type": data_type,
        "meta": meta or {},
    }


def _semantic_meta(**semantic: Any) -> dict[str, Any]:
    """Wrap semantic publication metadata in the dbt meta namespace."""
    return {"floe": {"semantic": semantic}}


def _write_manifest(tmp_path: Path, manifest: dict[str, Any]) -> Path:
    """Write manifest to a JSON file and return its path."""
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _read_generated_yaml(path: Path) -> dict[str, Any]:
    """Read and parse a generated YAML file."""
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(content, dict)
    return content


def _customer_360_semantic_manifest() -> dict[str, Any]:
    """Build a Customer 360 manifest with explicit semantic publication."""
    return _make_manifest(
        {
            "model.analytics.mart_customer_360": _make_model(
                "mart_customer_360",
                columns={
                    "customer_id": _make_column("customer_id", "integer"),
                    "lifetime_value": _make_column("lifetime_value", "decimal"),
                    "is_active": _make_column("is_active", "boolean"),
                    "segment": _make_column("segment", "varchar"),
                    "signup_date": _make_column("signup_date", "date"),
                    "email": _make_column("email", "varchar", meta={"sensitive": True}),
                    "phone": _make_column("phone", "varchar", meta={"sensitive": True}),
                    "address": _make_column(
                        "address",
                        "varchar",
                        meta={"masking_policy": "mask_address"},
                    ),
                    "ssn_hash": _make_column("ssn_hash", "varchar", meta={"sensitive": True}),
                    "internal_risk_score": _make_column("internal_risk_score", "decimal"),
                },
                meta=_semantic_meta(
                    publish=True,
                    measures={
                        "total_lifetime_value": {
                            "source": "lifetime_value",
                            "type": "sum",
                        },
                        "active_customer_count": {
                            "source": "customer_id",
                            "type": "count_distinct",
                            "filters": [{"sql": "{CUBE}.is_active = true"}],
                        },
                    },
                    dimensions={
                        "customer_segment": {
                            "source": "segment",
                            "type": "string",
                        }
                    },
                    time_dimensions={
                        "signup_date": {
                            "source": "signup_date",
                            "granularities": ["day", "month"],
                        }
                    },
                    validation_metrics=["total_lifetime_value", "active_customer_count"],
                ),
                tags=["analytics", "semantic"],
            ),
        }
    )


def _generate_single_cube(tmp_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Generate one Cube schema and return its cube definition."""
    manifest_path = _write_manifest(tmp_path, manifest)
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    result = CubeSchemaGenerator().generate(manifest_path, output_dir)

    assert len(result) == 1
    content = _read_generated_yaml(result[0])
    return content["cubes"][0]


def _generate_cube_by_name(
    tmp_path: Path,
    manifest: dict[str, Any],
    cube_name: str,
) -> dict[str, Any]:
    """Generate Cube schemas and return the named cube definition."""
    manifest_path = _write_manifest(tmp_path, manifest)
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    result = CubeSchemaGenerator().generate(manifest_path, output_dir)

    for path in result:
        cube = _read_generated_yaml(path)["cubes"][0]
        if cube["name"] == cube_name:
            return cube
    raise AssertionError(f"Cube not generated: {cube_name}")


class TestDenyByDefaultPublication:
    """Test model and member publication opt-in behavior."""

    def test_unpublished_model_produces_no_schema_files(self, tmp_path: Path) -> None:
        """Models without meta.floe.semantic.publish=true are not published."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    columns={
                        "customer_id": _make_column("customer_id", "integer"),
                        "email": _make_column("email", "varchar"),
                    },
                )
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = CubeSchemaGenerator().generate(manifest_path, output_dir)

        assert result == []
        assert list(output_dir.glob("*.yml")) == []
        assert list(output_dir.glob("*.yaml")) == []

    def test_published_model_uses_only_explicit_semantic_members(self, tmp_path: Path) -> None:
        """Unannotated dbt columns are not inferred as measures or dimensions."""
        manifest = _make_manifest(
            {
                "model.analytics.customer_metrics": _make_model(
                    "customer_metrics",
                    columns={
                        "customer_id": _make_column("customer_id", "integer"),
                        "lifetime_value": _make_column("lifetime_value", "decimal"),
                        "segment": _make_column("segment", "varchar"),
                        "signup_date": _make_column("signup_date", "date"),
                        "internal_score": _make_column("internal_score", "decimal"),
                    },
                    meta=_semantic_meta(
                        publish=True,
                        measures={
                            "total_lifetime_value": {
                                "source": "lifetime_value",
                                "type": "sum",
                            }
                        },
                        dimensions={
                            "customer_segment": {
                                "source": "segment",
                                "type": "string",
                            }
                        },
                        time_dimensions={
                            "signup_date": {
                                "source": "signup_date",
                                "granularities": ["day", "month"],
                            }
                        },
                        validation_metrics=["total_lifetime_value"],
                    ),
                )
            }
        )

        cube = _generate_single_cube(tmp_path, manifest)

        assert cube["name"] == "customer_metrics"
        assert cube["sql_table"] == "gold.customer_metrics"
        assert cube["measures"] == [
            {
                "name": "total_lifetime_value",
                "type": "sum",
                "sql": "lifetime_value",
            }
        ]
        assert cube["dimensions"] == [
            {
                "name": "customer_segment",
                "type": "string",
                "sql": "segment",
            },
            {
                "name": "signup_date",
                "type": "time",
                "sql": "signup_date",
                "granularities": ["day", "month"],
            },
        ]
        assert cube["meta"]["floe"]["validation_metrics"] == ["total_lifetime_value"]
        published_member_names = {
            member["name"] for member in cube["measures"] + cube["dimensions"]
        }
        assert "customer_id" not in published_member_names
        assert "internal_score" not in published_member_names

    def test_customer_360_fixture_publishes_public_metrics_without_sensitive_fields(
        self, tmp_path: Path
    ) -> None:
        """Customer 360 publishes public semantics without email or masked fields."""
        cube = _generate_single_cube(tmp_path, _customer_360_semantic_manifest())

        measure_names = {member["name"] for member in cube["measures"]}
        dimension_names = {member["name"] for member in cube["dimensions"]}
        rendered_yaml = yaml.safe_dump({"cubes": [cube]}, sort_keys=False)

        assert measure_names == {"total_lifetime_value", "active_customer_count"}
        assert {"customer_segment", "signup_date"}.issubset(dimension_names)
        assert "email" not in rendered_yaml
        assert "phone" not in rendered_yaml
        assert "address" not in rendered_yaml
        assert "ssn" not in rendered_yaml


class TestSensitiveFieldPublication:
    """Test compact privacy guards for semantic members."""

    def test_pii_like_member_sources_are_unpublished_without_safe_policy(
        self, tmp_path: Path
    ) -> None:
        """PII-like source names require an explicit safe publication policy."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    columns={
                        "email": _make_column("email", "varchar"),
                        "customer_segment": _make_column("customer_segment", "varchar"),
                    },
                    meta=_semantic_meta(
                        publish=True,
                        dimensions={
                            "customer_email": {
                                "source": "email",
                                "type": "string",
                            },
                            "customer_segment": {
                                "source": "customer_segment",
                                "type": "string",
                            },
                        },
                    ),
                )
            }
        )

        cube = _generate_single_cube(tmp_path, manifest)

        assert cube["dimensions"] == [
            {
                "name": "customer_segment",
                "type": "string",
                "sql": "customer_segment",
            }
        ]

    def test_sensitive_and_masked_columns_are_unpublished_without_safe_policy(
        self, tmp_path: Path
    ) -> None:
        """Column metadata blocks publication unless the member has a safe policy."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    columns={
                        "customer_token": _make_column(
                            "customer_token",
                            "varchar",
                            meta={"sensitive": True},
                        ),
                        "masked_region": _make_column(
                            "masked_region",
                            "varchar",
                            meta={"masking_policy": "mask_region"},
                        ),
                        "customer_segment": _make_column("customer_segment", "varchar"),
                    },
                    meta=_semantic_meta(
                        publish=True,
                        dimensions={
                            "customer_token": {
                                "source": "customer_token",
                                "type": "string",
                            },
                            "masked_region": {
                                "source": "masked_region",
                                "type": "string",
                            },
                            "customer_segment": {
                                "source": "customer_segment",
                                "type": "string",
                            },
                        },
                    ),
                )
            }
        )

        cube = _generate_single_cube(tmp_path, manifest)

        assert [dimension["name"] for dimension in cube["dimensions"]] == ["customer_segment"]

    def test_source_expression_for_masked_column_is_rejected(self, tmp_path: Path) -> None:
        """Member sources must be exact dbt column names, not expressions."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    columns={
                        "masked_region": _make_column(
                            "masked_region",
                            "varchar",
                            meta={"masking_policy": "mask_region"},
                        ),
                    },
                    meta=_semantic_meta(
                        publish=True,
                        dimensions={
                            "region_label": {
                                "source": "coalesce(masked_region, 'unknown')",
                                "type": "string",
                            },
                        },
                    ),
                )
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(SchemaGenerationError, match="exact dbt column"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)

    def test_explicit_safe_policy_permits_sensitive_source(self, tmp_path: Path) -> None:
        """A compact safe policy can intentionally publish a sensitive source."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    columns={
                        "public_segment": _make_column(
                            "public_segment",
                            "varchar",
                            meta={"sensitive": True},
                        ),
                    },
                    meta=_semantic_meta(
                        publish=True,
                        dimensions={
                            "public_segment": {
                                "source": "public_segment",
                                "type": "string",
                                "policy": {"safe_for_publication": True},
                            },
                        },
                    ),
                )
            }
        )

        cube = _generate_single_cube(tmp_path, manifest)

        assert cube["dimensions"] == [
            {
                "name": "public_segment",
                "type": "string",
                "sql": "public_segment",
            }
        ]

    def test_flat_safe_for_publication_does_not_permit_sensitive_source(
        self, tmp_path: Path
    ) -> None:
        """Only the canonical nested policy shape permits sensitive source publication."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    columns={
                        "public_segment": _make_column(
                            "public_segment",
                            "varchar",
                            meta={"sensitive": True},
                        ),
                    },
                    meta=_semantic_meta(
                        publish=True,
                        dimensions={
                            "public_segment": {
                                "source": "public_segment",
                                "type": "string",
                                "safe_for_publication": True,
                            },
                        },
                    ),
                )
            }
        )

        cube = _generate_single_cube(tmp_path, manifest)

        assert cube["dimensions"] == []

    @pytest.mark.parametrize(
        ("column_meta", "expected_name"),
        [
            pytest.param({"pii": True}, "pii_segment", id="pii"),
            pytest.param({"contains_pii": True}, "contains_pii_segment", id="contains-pii"),
            pytest.param({"masked": True}, "masked_segment", id="masked"),
            pytest.param({"classification": "pii"}, "classified_segment", id="classification"),
            pytest.param(
                {"policy": {"sensitivity": "confidential"}},
                "policy_segment",
                id="policy-sensitivity",
            ),
        ],
    )
    def test_sensitive_column_metadata_variants_block_publication(
        self,
        tmp_path: Path,
        column_meta: dict[str, Any],
        expected_name: str,
    ) -> None:
        """Supported dbt metadata variants block publication without a safe policy."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    columns={
                        expected_name: _make_column(
                            expected_name,
                            "varchar",
                            meta=column_meta,
                        ),
                    },
                    meta=_semantic_meta(
                        publish=True,
                        dimensions={
                            expected_name: {
                                "source": expected_name,
                                "type": "string",
                            },
                        },
                    ),
                )
            }
        )

        cube = _generate_single_cube(tmp_path, manifest)

        assert cube["dimensions"] == []

    def test_benign_names_with_sensitive_substrings_are_published(self, tmp_path: Path) -> None:
        """Sensitive-name matching does not block substrings inside larger words."""
        manifest = _make_manifest(
            {
                "model.analytics.campaign_metrics": _make_model(
                    "campaign_metrics",
                    columns={
                        "readdress_flag": _make_column("readdress_flag", "boolean"),
                        "microphone_type": _make_column("microphone_type", "varchar"),
                        "adobe_tracking": _make_column("adobe_tracking", "varchar"),
                    },
                    meta=_semantic_meta(
                        publish=True,
                        dimensions={
                            "readdress_flag": {
                                "source": "readdress_flag",
                                "type": "boolean",
                            },
                            "microphone_type": {
                                "source": "microphone_type",
                                "type": "string",
                            },
                            "adobe_tracking": {
                                "source": "adobe_tracking",
                                "type": "string",
                            },
                        },
                    ),
                )
            }
        )

        cube = _generate_single_cube(tmp_path, manifest)

        assert [dimension["name"] for dimension in cube["dimensions"]] == [
            "readdress_flag",
            "microphone_type",
            "adobe_tracking",
        ]

    def test_blocked_member_is_logged(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Blocked semantic members produce a diagnostic log event."""

        class RecordingLogger:
            def __init__(self) -> None:
                self.info_events: list[tuple[str, dict[str, Any]]] = []

            def debug(self, event: str, **kwargs: Any) -> None:
                pass

            def info(self, event: str, **kwargs: Any) -> None:
                self.info_events.append((event, kwargs))

        recorder = RecordingLogger()
        monkeypatch.setattr(schema_generator_module, "logger", recorder)
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    columns={
                        "email": _make_column("email", "varchar"),
                    },
                    meta=_semantic_meta(
                        publish=True,
                        dimensions={
                            "customer_email": {
                                "source": "email",
                                "type": "string",
                            }
                        },
                    ),
                )
            }
        )

        _generate_single_cube(tmp_path, manifest)

        blocked_events = [
            kwargs for event, kwargs in recorder.info_events if event == "semantic_member_blocked"
        ]
        assert blocked_events == [
            {
                "model": "customers",
                "member": "customer_email",
                "source": "email",
                "reason": "sensitive_member_name",
            }
        ]


class TestExplicitJoinsAndPreAggregations:
    """Test joins and pre-aggregations remain explicit publication metadata."""

    def test_depends_on_does_not_create_joins_without_semantic_metadata(
        self, tmp_path: Path
    ) -> None:
        """dbt dependencies are preserved as input, not inferred as published joins."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    meta=_semantic_meta(publish=True),
                ),
                "model.analytics.orders": _make_model(
                    "orders",
                    depends_on_nodes=["model.analytics.customers"],
                    meta=_semantic_meta(publish=True),
                ),
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = CubeSchemaGenerator().generate(manifest_path, output_dir)

        orders_cube = next(
            _read_generated_yaml(path)["cubes"][0] for path in result if path.name == "orders.yaml"
        )
        assert "joins" not in orders_cube

    def test_explicit_joins_and_pre_aggregations_are_generated(self, tmp_path: Path) -> None:
        """Joins and pre-aggregations publish only from meta.floe.semantic."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    meta=_semantic_meta(publish=True),
                ),
                "model.analytics.orders": _make_model(
                    "orders",
                    columns={
                        "revenue": _make_column("revenue", "decimal"),
                        "segment": _make_column("segment", "varchar"),
                    },
                    meta=_semantic_meta(
                        publish=True,
                        measures={"total_revenue": {"source": "revenue", "type": "sum"}},
                        dimensions={
                            "customer_segment": {
                                "source": "segment",
                                "type": "string",
                            }
                        },
                        joins={
                            "customers": {
                                "sql": "{orders}.customer_id = {customers}.customer_id",
                                "relationship": "many_to_one",
                            }
                        },
                        pre_aggregations={
                            "daily_revenue": {
                                "type": "rollup",
                                "measures": ["total_revenue"],
                                "dimensions": ["customer_segment"],
                            }
                        },
                    ),
                ),
            }
        )

        cube = _generate_cube_by_name(tmp_path, manifest, "orders")

        assert cube["joins"] == [
            {
                "name": "customers",
                "sql": "{orders}.customer_id = {customers}.customer_id",
                "relationship": "many_to_one",
            }
        ]
        assert cube["pre_aggregations"] == [
            {
                "name": "daily_revenue",
                "type": "rollup",
                "measures": ["total_revenue"],
                "dimensions": ["customer_segment"],
            }
        ]

    def test_pre_aggregation_must_reference_published_members(self, tmp_path: Path) -> None:
        """Pre-aggregations fail fast when they reference unpublished members."""
        manifest = _make_manifest(
            {
                "model.analytics.orders": _make_model(
                    "orders",
                    columns={
                        "revenue": _make_column("revenue", "decimal"),
                        "email": _make_column("email", "varchar"),
                    },
                    meta=_semantic_meta(
                        publish=True,
                        measures={"total_revenue": {"source": "revenue", "type": "sum"}},
                        dimensions={
                            "customer_email": {
                                "source": "email",
                                "type": "string",
                            }
                        },
                        pre_aggregations={
                            "email_revenue": {
                                "type": "rollup",
                                "measures": ["total_revenue"],
                                "dimensions": ["customer_email"],
                            }
                        },
                    ),
                )
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(SchemaGenerationError, match="unpublished dimension"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)

    def test_pre_aggregation_member_lists_cannot_be_null(self, tmp_path: Path) -> None:
        """Pre-aggregation member lists must be explicit lists when present."""
        manifest = _make_manifest(
            {
                "model.analytics.orders": _make_model(
                    "orders",
                    columns={"revenue": _make_column("revenue", "decimal")},
                    meta=_semantic_meta(
                        publish=True,
                        measures={"total_revenue": {"source": "revenue", "type": "sum"}},
                        pre_aggregations={
                            "daily_revenue": {
                                "type": "rollup",
                                "measures": None,
                            }
                        },
                    ),
                )
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(SchemaGenerationError, match="measures must be a list"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)

    def test_join_must_target_published_model(self, tmp_path: Path) -> None:
        """Explicit joins fail when the target cube is not published."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model("customers"),
                "model.analytics.orders": _make_model(
                    "orders",
                    meta=_semantic_meta(
                        publish=True,
                        joins={
                            "customers": {
                                "sql": "{orders}.customer_id = {customers}.customer_id",
                                "relationship": "belongs_to",
                            }
                        },
                    ),
                ),
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(SchemaGenerationError, match="unpublished model"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)

    def test_join_sql_rejects_statement_separators(self, tmp_path: Path) -> None:
        """Join SQL must stay a join expression, not a multi-statement payload."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    meta=_semantic_meta(publish=True),
                ),
                "model.analytics.orders": _make_model(
                    "orders",
                    meta=_semantic_meta(
                        publish=True,
                        joins={
                            "customers": {
                                "sql": (
                                    "{orders}.customer_id = {customers}.customer_id; "
                                    "DROP TABLE users"
                                ),
                                "relationship": "belongs_to",
                            }
                        },
                    ),
                ),
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(SchemaGenerationError, match="unsafe SQL token"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)

    def test_join_relationship_defaults_to_canonical_many_to_one(self, tmp_path: Path) -> None:
        """Generated joins use Cube's canonical many_to_one default."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    meta=_semantic_meta(publish=True),
                ),
                "model.analytics.orders": _make_model(
                    "orders",
                    meta=_semantic_meta(
                        publish=True,
                        joins={
                            "customers": {
                                "sql": "{orders}.customer_id = {customers}.customer_id",
                            }
                        },
                    ),
                ),
            }
        )

        cube = _generate_cube_by_name(tmp_path, manifest, "orders")

        assert cube["joins"] == [
            {
                "name": "customers",
                "sql": "{orders}.customer_id = {customers}.customer_id",
                "relationship": "many_to_one",
            }
        ]

    def test_join_relationship_accepts_legacy_aliases_as_canonical_values(
        self, tmp_path: Path
    ) -> None:
        """Legacy Cube relationship aliases are accepted and normalized."""
        manifest = _make_manifest(
            {
                "model.analytics.customers": _make_model(
                    "customers",
                    meta=_semantic_meta(publish=True),
                ),
                "model.analytics.orders": _make_model(
                    "orders",
                    meta=_semantic_meta(
                        publish=True,
                        joins={
                            "customers": {
                                "sql": "{orders}.customer_id = {customers}.customer_id",
                                "relationship": "belongs_to",
                            }
                        },
                    ),
                ),
            }
        )

        cube = _generate_cube_by_name(tmp_path, manifest, "orders")

        assert cube["joins"] == [
            {
                "name": "customers",
                "sql": "{orders}.customer_id = {customers}.customer_id",
                "relationship": "many_to_one",
            }
        ]

    def test_member_filters_must_be_lists_of_mappings(self, tmp_path: Path) -> None:
        """Member filters must use Cube's list-of-objects shape."""
        manifest = _make_manifest(
            {
                "model.analytics.orders": _make_model(
                    "orders",
                    columns={"revenue": _make_column("revenue", "decimal")},
                    meta=_semantic_meta(
                        publish=True,
                        measures={
                            "total_revenue": {
                                "source": "revenue",
                                "type": "sum",
                                "filters": "{CUBE}.is_active = true",
                            }
                        },
                    ),
                )
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(SchemaGenerationError, match="filters must be a list"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)

    def test_member_filter_sql_rejects_statement_separators(self, tmp_path: Path) -> None:
        """Filter SQL must stay a predicate expression, not a multi-statement payload."""
        manifest = _make_manifest(
            {
                "model.analytics.orders": _make_model(
                    "orders",
                    columns={"revenue": _make_column("revenue", "decimal")},
                    meta=_semantic_meta(
                        publish=True,
                        measures={
                            "total_revenue": {
                                "source": "revenue",
                                "type": "sum",
                                "filters": [{"sql": "{CUBE}.is_active = true; DROP TABLE users"}],
                            }
                        },
                    ),
                )
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(SchemaGenerationError, match="unsafe SQL token"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)


class TestSemanticMetadataValidation:
    """Test malformed semantic publication metadata."""

    def test_unknown_measure_type_raises_schema_generation_error(self, tmp_path: Path) -> None:
        """Unknown semantic member types fail instead of generating invalid YAML."""
        manifest = _make_manifest(
            {
                "model.analytics.orders": _make_model(
                    "orders",
                    meta=_semantic_meta(
                        publish=True,
                        measures={"median_revenue": {"source": "revenue", "type": "median"}},
                    ),
                )
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(SchemaGenerationError, match="Unsupported measure type"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)

    def test_validation_metric_must_reference_published_measure(self, tmp_path: Path) -> None:
        """Validation metrics fail fast when they reference unpublished measures."""
        manifest = _make_manifest(
            {
                "model.analytics.orders": _make_model(
                    "orders",
                    columns={"revenue": _make_column("revenue", "decimal")},
                    meta=_semantic_meta(
                        publish=True,
                        measures={"total_revenue": {"source": "revenue", "type": "sum"}},
                        validation_metrics=["missing_revenue"],
                    ),
                )
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(SchemaGenerationError, match="unpublished measure"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)

    def test_missing_manifest_raises_file_not_found(self, tmp_path: Path) -> None:
        """Missing manifest files raise FileNotFoundError."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            CubeSchemaGenerator().generate(tmp_path / "missing.json", output_dir)

    def test_invalid_json_raises_schema_generation_error(self, tmp_path: Path) -> None:
        """Invalid JSON raises SchemaGenerationError."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("{invalid json", encoding="utf-8")

        with pytest.raises(SchemaGenerationError, match="manifest"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)

    def test_missing_nodes_key_raises_schema_generation_error(self, tmp_path: Path) -> None:
        """Manifest without nodes raises SchemaGenerationError."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"metadata": {}}), encoding="utf-8")

        with pytest.raises(SchemaGenerationError, match="nodes"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)

    def test_path_traversal_model_name_raises_error(self, tmp_path: Path) -> None:
        """Published model names cannot write outside the output directory."""
        manifest = _make_manifest(
            {
                "model.analytics.evil": _make_model(
                    "../../etc/cron.d/exploit",
                    meta=_semantic_meta(publish=True),
                )
            }
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(SchemaGenerationError, match="path traversal"):
            CubeSchemaGenerator().generate(manifest_path, output_dir)


class TestOutputDirectory:
    """Test filesystem behavior."""

    def test_existing_yaml_files_are_deleted_before_writing(self, tmp_path: Path) -> None:
        """Existing schema files are cleaned before generation."""
        manifest = _make_manifest(
            {"model.analytics.orders": _make_model("orders", meta=_semantic_meta(publish=True))}
        )
        manifest_path = _write_manifest(tmp_path, manifest)
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "old_cube.yaml").write_text("old: content", encoding="utf-8")
        (output_dir / "another.yml").write_text("old: data", encoding="utf-8")
        (output_dir / "keep_me.txt").write_text("keep", encoding="utf-8")

        CubeSchemaGenerator().generate(manifest_path, output_dir)

        assert not (output_dir / "old_cube.yaml").exists()
        assert not (output_dir / "another.yml").exists()
        assert (output_dir / "keep_me.txt").exists()

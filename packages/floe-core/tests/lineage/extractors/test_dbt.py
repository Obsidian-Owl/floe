"""Tests for dbt manifest lineage extractor.

This module tests the DbtLineageExtractor's ability to extract lineage
information from dbt manifest.json files, including models, sources,
tests, and column-level lineage.
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_core.lineage.extractors.dbt import DbtLineageExtractor
from floe_core.lineage.types import LineageDataset


@pytest.fixture
def realistic_manifest() -> dict[str, Any]:
    """Realistic dbt manifest fixture with 3-model chain and source.

    Structure:
        source.project.raw.customers
            ↓
        model.project.stg_customers
            ↓
        model.project.dim_customers
            ↓
        model.project.fct_orders
    """
    return {
        "nodes": {
            "model.project.stg_customers": {
                "database": "analytics",
                "schema": "staging",
                "name": "stg_customers",
                "columns": {
                    "customer_id": {"name": "customer_id", "data_type": "BIGINT"},
                    "customer_name": {"name": "customer_name", "data_type": "VARCHAR"},
                },
            },
            "model.project.dim_customers": {
                "database": "analytics",
                "schema": "marts",
                "name": "dim_customers",
                "alias": "customers",  # Test alias usage
                "columns": {
                    "customer_id": {"name": "customer_id", "data_type": "BIGINT"},
                    "customer_name": {"name": "customer_name", "data_type": "VARCHAR"},
                    "created_at": {"name": "created_at", "data_type": "TIMESTAMP"},
                },
            },
            "model.project.fct_orders": {
                "database": "analytics",
                "schema": "marts",
                "name": "fct_orders",
                "columns": {
                    "order_id": {"name": "order_id", "data_type": "BIGINT"},
                    "customer_id": {"name": "customer_id", "data_type": "BIGINT"},
                    "order_total": {"name": "order_total", "data_type": "DECIMAL"},
                },
            },
            "test.project.not_null_dim_customers_customer_id": {
                "depends_on": {"nodes": ["model.project.dim_customers"]},
            },
        },
        "sources": {
            "source.project.raw.customers": {
                "database": "raw",
                "schema": "public",
                "name": "customers",
                "columns": {
                    "id": {"name": "id", "data_type": "BIGINT"},
                    "name": {"name": "name", "data_type": "VARCHAR"},
                },
            },
        },
        "parent_map": {
            "model.project.stg_customers": ["source.project.raw.customers"],
            "model.project.dim_customers": ["model.project.stg_customers"],
            "model.project.fct_orders": ["model.project.dim_customers"],
        },
    }


class TestDbtLineageExtractor:
    """Tests for DbtLineageExtractor."""

    def test_initialization(self, realistic_manifest: dict[str, Any]) -> None:
        """Extractor initializes with manifest and default namespace."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        assert extractor.manifest == realistic_manifest
        assert extractor.default_namespace == "prod"

    def test_default_namespace(self, realistic_manifest: dict[str, Any]) -> None:
        """Extractor uses 'default' namespace when not specified."""
        extractor = DbtLineageExtractor(realistic_manifest)
        assert extractor.default_namespace == "default"

    @pytest.mark.requirement("REQ-522")
    def test_extract_protocol_method(self, realistic_manifest: dict[str, Any]) -> None:
        """extract() method implements LineageExtractor protocol."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        inputs, outputs = extractor.extract("model.project.stg_customers")

        # Should return tuple of lists
        assert isinstance(inputs, list)
        assert isinstance(outputs, list)
        assert all(isinstance(ds, LineageDataset) for ds in inputs)
        assert all(isinstance(ds, LineageDataset) for ds in outputs)

    @pytest.mark.requirement("REQ-519")
    def test_extract_model_with_source_input(self, realistic_manifest: dict[str, Any]) -> None:
        """Extract model with source as input dataset."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        inputs, outputs = extractor.extract_model("model.project.stg_customers")

        # Should have 1 input (source) and 1 output (model)
        assert len(inputs) == 1
        assert len(outputs) == 1

        # Input should be the source
        assert inputs[0].namespace == "prod"
        assert inputs[0].name == "raw.public.customers"

        # Output should be the model
        assert outputs[0].namespace == "prod"
        assert outputs[0].name == "analytics.staging.stg_customers"

    @pytest.mark.requirement("REQ-519")
    def test_extract_model_with_model_input(self, realistic_manifest: dict[str, Any]) -> None:
        """Extract model with another model as input dataset."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        inputs, outputs = extractor.extract_model("model.project.dim_customers")

        # Should have 1 input (stg_customers) and 1 output (dim_customers)
        assert len(inputs) == 1
        assert len(outputs) == 1

        # Input should be stg_customers
        assert inputs[0].name == "analytics.staging.stg_customers"

        # Output should be dim_customers (using alias)
        assert outputs[0].name == "analytics.marts.customers"

    @pytest.mark.requirement("REQ-522")
    def test_three_model_chain_lineage(self, realistic_manifest: dict[str, Any]) -> None:
        """Test 3-model chain produces correct lineage graph."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")

        # Extract lineage for each model in the chain
        stg_inputs, stg_outputs = extractor.extract_model("model.project.stg_customers")
        dim_inputs, dim_outputs = extractor.extract_model("model.project.dim_customers")
        fct_inputs, fct_outputs = extractor.extract_model("model.project.fct_orders")

        # Verify chain: source → stg → dim → fct
        assert stg_inputs[0].name == "raw.public.customers"
        assert stg_outputs[0].name == "analytics.staging.stg_customers"

        assert dim_inputs[0].name == "analytics.staging.stg_customers"
        assert dim_outputs[0].name == "analytics.marts.customers"

        assert fct_inputs[0].name == "analytics.marts.customers"
        assert fct_outputs[0].name == "analytics.marts.fct_orders"

    def test_dataset_naming_convention(self, realistic_manifest: dict[str, Any]) -> None:
        """Dataset names follow {database}.{schema}.{name} convention."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        _, outputs = extractor.extract_model("model.project.stg_customers")

        # Should be database.schema.name
        assert outputs[0].name == "analytics.staging.stg_customers"

    def test_dataset_naming_with_alias(self, realistic_manifest: dict[str, Any]) -> None:
        """Dataset names use alias when present instead of name."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        _, outputs = extractor.extract_model("model.project.dim_customers")

        # Should use alias "customers" instead of name "dim_customers"
        assert outputs[0].name == "analytics.marts.customers"

    def test_model_with_no_columns_empty_schema_facet(self) -> None:
        """Model with no columns produces dataset with empty schema facet."""
        manifest = {
            "nodes": {
                "model.project.no_columns": {
                    "database": "analytics",
                    "schema": "staging",
                    "name": "no_columns",
                    "columns": {},  # No columns
                }
            },
            "parent_map": {"model.project.no_columns": []},
        }
        extractor = DbtLineageExtractor(manifest, default_namespace="prod")
        _, outputs = extractor.extract_model("model.project.no_columns")

        # Should have output dataset but no schema facet (empty columns)
        assert len(outputs) == 1
        assert "schema" not in outputs[0].facets

    def test_model_with_columns_has_schema_facet(self, realistic_manifest: dict[str, Any]) -> None:
        """Model with columns produces dataset with schema facet."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        _, outputs = extractor.extract_model("model.project.dim_customers")

        # Should have schema facet with 3 columns
        assert "schema" in outputs[0].facets
        schema_facet = outputs[0].facets["schema"]
        assert schema_facet["_producer"] == "floe"
        assert len(schema_facet["fields"]) == 3
        assert schema_facet["fields"][0]["name"] == "customer_id"
        assert schema_facet["fields"][0]["type"] == "BIGINT"

    def test_model_with_upstream_has_column_lineage_facet(
        self, realistic_manifest: dict[str, Any]
    ) -> None:
        """Model with upstream columns produces column lineage facet."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        _, outputs = extractor.extract_model("model.project.dim_customers")

        # Should have columnLineage facet
        assert "columnLineage" in outputs[0].facets
        col_lineage = outputs[0].facets["columnLineage"]
        assert col_lineage["_producer"] == "floe"
        assert "fields" in col_lineage

        # customer_id should have upstream from stg_customers
        assert "customer_id" in col_lineage["fields"]
        customer_id_lineage = col_lineage["fields"]["customer_id"]
        assert customer_id_lineage["transformationType"] == "IDENTITY"
        assert len(customer_id_lineage["inputFields"]) == 1
        assert customer_id_lineage["inputFields"][0]["field"] == "customer_id"

    def test_extract_test_node(self, realistic_manifest: dict[str, Any]) -> None:
        """Extract datasets being tested by a test node."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        datasets = extractor.extract_test("test.project.not_null_dim_customers_customer_id")

        # Should return the model being tested
        assert len(datasets) == 1
        assert datasets[0].name == "analytics.marts.customers"

    def test_extract_test_node_not_found(self, realistic_manifest: dict[str, Any]) -> None:
        """Extract test for non-existent test node returns empty list."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        datasets = extractor.extract_test("test.project.nonexistent")

        assert datasets == []

    def test_extract_all_models(self, realistic_manifest: dict[str, Any]) -> None:
        """Extract lineage for all models in manifest."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        all_lineage = extractor.extract_all_models()

        # Should have 3 models
        assert len(all_lineage) == 3
        assert "model.project.stg_customers" in all_lineage
        assert "model.project.dim_customers" in all_lineage
        assert "model.project.fct_orders" in all_lineage

        # Each should have (inputs, outputs) tuple
        for _node_uid, (inputs, outputs) in all_lineage.items():
            assert isinstance(inputs, list)
            assert isinstance(outputs, list)
            assert len(outputs) == 1  # Each model produces 1 output

    def test_extract_model_not_found(self, realistic_manifest: dict[str, Any]) -> None:
        """Extract non-existent model returns empty lineage."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        inputs, outputs = extractor.extract_model("model.project.nonexistent")

        assert inputs == []
        assert outputs == []

    def test_fallback_to_depends_on_when_no_parent_map(self) -> None:
        """Extractor falls back to depends_on.nodes when parent_map unavailable."""
        manifest = {
            "nodes": {
                "model.project.customers": {
                    "database": "analytics",
                    "schema": "public",
                    "name": "customers",
                    "depends_on": {"nodes": ["source.project.raw.users"]},
                },
            },
            "sources": {
                "source.project.raw.users": {
                    "database": "raw",
                    "schema": "public",
                    "name": "users",
                }
            },
            # No parent_map
        }
        extractor = DbtLineageExtractor(manifest, default_namespace="prod")
        inputs, outputs = extractor.extract_model("model.project.customers")

        # Should still resolve inputs from depends_on
        assert len(inputs) == 1
        assert inputs[0].name == "raw.public.users"

    def test_missing_database_schema_defaults_to_empty(self) -> None:
        """Missing database/schema fields default to empty string."""
        manifest = {
            "nodes": {
                "model.project.minimal": {
                    # Missing database and schema
                    "name": "minimal",
                }
            },
            "parent_map": {"model.project.minimal": []},
        }
        extractor = DbtLineageExtractor(manifest, default_namespace="prod")
        _, outputs = extractor.extract_model("model.project.minimal")

        # Should create dataset with empty database/schema
        assert outputs[0].name == "..minimal"

    def test_source_resolution_from_sources_dict(self, realistic_manifest: dict[str, Any]) -> None:
        """Sources are resolved from sources dict, not nodes dict."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        inputs, _ = extractor.extract_model("model.project.stg_customers")

        # Input should be from sources dict
        assert len(inputs) == 1
        assert inputs[0].name == "raw.public.customers"

    def test_multiple_inputs(self) -> None:
        """Model with multiple inputs produces multiple input datasets."""
        manifest = {
            "nodes": {
                "model.project.joined": {
                    "database": "analytics",
                    "schema": "marts",
                    "name": "joined",
                },
                "model.project.customers": {
                    "database": "analytics",
                    "schema": "staging",
                    "name": "customers",
                },
                "model.project.orders": {
                    "database": "analytics",
                    "schema": "staging",
                    "name": "orders",
                },
            },
            "parent_map": {
                "model.project.joined": [
                    "model.project.customers",
                    "model.project.orders",
                ]
            },
        }
        extractor = DbtLineageExtractor(manifest, default_namespace="prod")
        inputs, outputs = extractor.extract_model("model.project.joined")

        # Should have 2 inputs
        assert len(inputs) == 2
        input_names = {ds.name for ds in inputs}
        assert "analytics.staging.customers" in input_names
        assert "analytics.staging.orders" in input_names

    def test_namespace_propagates_to_all_datasets(self, realistic_manifest: dict[str, Any]) -> None:
        """All datasets use the configured namespace."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="staging")
        inputs, outputs = extractor.extract_model("model.project.dim_customers")

        # All datasets should have "staging" namespace
        assert inputs[0].namespace == "staging"
        assert outputs[0].namespace == "staging"

    def test_facets_only_on_output_datasets(self, realistic_manifest: dict[str, Any]) -> None:
        """Schema and column lineage facets only added to output datasets."""
        extractor = DbtLineageExtractor(realistic_manifest, default_namespace="prod")
        inputs, outputs = extractor.extract_model("model.project.dim_customers")

        # Input datasets should not have facets
        assert inputs[0].facets == {}

        # Output dataset should have facets
        assert "schema" in outputs[0].facets
        assert "columnLineage" in outputs[0].facets

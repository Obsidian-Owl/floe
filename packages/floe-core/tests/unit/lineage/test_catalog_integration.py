"""Tests for catalog integration and namespace resolution.

This module tests namespace resolution strategies, catalog dataset resolution,
and Iceberg snapshot enrichment for OpenLineage integration.
"""

from __future__ import annotations

import pytest

from floe_core.lineage.catalog_integration import (
    CatalogDatasetResolver,
    CentralizedNamespaceStrategy,
    DataMeshNamespaceStrategy,
    NamespaceResolver,
    SimpleNamespaceStrategy,
)
from floe_core.lineage.types import LineageDataset


class TestSimpleNamespaceStrategy:
    """Tests for SimpleNamespaceStrategy."""

    @pytest.mark.requirement("REQ-517")
    def test_resolve_returns_static_namespace(self) -> None:
        """Simple strategy returns the configured static namespace."""
        strategy = SimpleNamespaceStrategy(namespace="production")
        assert strategy.resolve() == "production"

    @pytest.mark.requirement("REQ-517")
    def test_resolve_ignores_kwargs(self) -> None:
        """Simple strategy ignores any kwargs passed to resolve()."""
        strategy = SimpleNamespaceStrategy(namespace="staging")
        assert strategy.resolve(environment="prod", platform="test") == "staging"

    @pytest.mark.requirement("REQ-517")
    def test_different_namespaces(self) -> None:
        """Different instances can have different namespaces."""
        strategy1 = SimpleNamespaceStrategy(namespace="dev")
        strategy2 = SimpleNamespaceStrategy(namespace="prod")
        assert strategy1.resolve() == "dev"
        assert strategy2.resolve() == "prod"

    @pytest.mark.requirement("REQ-517")
    def test_empty_namespace(self) -> None:
        """Simple strategy allows empty namespace."""
        strategy = SimpleNamespaceStrategy(namespace="")
        assert strategy.resolve() == ""

    @pytest.mark.requirement("REQ-517")
    def test_special_characters_in_namespace(self) -> None:
        """Simple strategy preserves special characters in namespace."""
        strategy = SimpleNamespaceStrategy(namespace="prod-us-east-1.analytics")
        assert strategy.resolve() == "prod-us-east-1.analytics"


class TestCentralizedNamespaceStrategy:
    """Tests for CentralizedNamespaceStrategy."""

    @pytest.mark.requirement("REQ-517")
    def test_resolve_combines_environment_and_platform(self) -> None:
        """Centralized strategy returns {environment}.{platform}."""
        strategy = CentralizedNamespaceStrategy(
            environment="production",
            platform="data-platform",
        )
        assert strategy.resolve() == "production.data-platform"

    @pytest.mark.requirement("REQ-517")
    def test_resolve_with_different_values(self) -> None:
        """Centralized strategy works with different environment/platform values."""
        strategy = CentralizedNamespaceStrategy(
            environment="staging",
            platform="analytics",
        )
        assert strategy.resolve() == "staging.analytics"

    @pytest.mark.requirement("REQ-517")
    def test_resolve_ignores_kwargs(self) -> None:
        """Centralized strategy ignores kwargs passed to resolve()."""
        strategy = CentralizedNamespaceStrategy(
            environment="prod",
            platform="platform",
        )
        assert strategy.resolve(extra="ignored") == "prod.platform"

    @pytest.mark.requirement("REQ-517")
    def test_empty_environment_and_platform(self) -> None:
        """Centralized strategy handles empty strings."""
        strategy = CentralizedNamespaceStrategy(environment="", platform="")
        assert strategy.resolve() == "."


class TestDataMeshNamespaceStrategy:
    """Tests for DataMeshNamespaceStrategy."""

    @pytest.mark.requirement("REQ-517")
    def test_resolve_combines_domain_and_product(self) -> None:
        """Data mesh strategy returns {domain}.{product_name}."""
        strategy = DataMeshNamespaceStrategy(
            domain="customer",
            product_name="customer-360",
        )
        assert strategy.resolve() == "customer.customer-360"

    @pytest.mark.requirement("REQ-517")
    def test_resolve_with_different_values(self) -> None:
        """Data mesh strategy works with different domain/product values."""
        strategy = DataMeshNamespaceStrategy(
            domain="finance",
            product_name="revenue-analytics",
        )
        assert strategy.resolve() == "finance.revenue-analytics"

    @pytest.mark.requirement("REQ-517")
    def test_resolve_ignores_kwargs(self) -> None:
        """Data mesh strategy ignores kwargs passed to resolve()."""
        strategy = DataMeshNamespaceStrategy(
            domain="sales",
            product_name="pipeline",
        )
        assert strategy.resolve(extra="ignored") == "sales.pipeline"

    @pytest.mark.requirement("REQ-517")
    def test_empty_domain_and_product(self) -> None:
        """Data mesh strategy handles empty strings."""
        strategy = DataMeshNamespaceStrategy(domain="", product_name="")
        assert strategy.resolve() == "."


class TestNamespaceResolver:
    """Tests for NamespaceResolver."""

    @pytest.mark.requirement("REQ-517")
    def test_simple_strategy_selection(self) -> None:
        """NamespaceResolver selects simple strategy correctly."""
        resolver = NamespaceResolver(
            strategy="simple",
            default_namespace="production",
        )
        assert resolver.resolve_job_namespace() == "production"
        assert resolver.resolve_dataset_namespace() == "production"

    @pytest.mark.requirement("REQ-517")
    def test_centralized_strategy_selection(self) -> None:
        """NamespaceResolver selects centralized strategy correctly."""
        resolver = NamespaceResolver(
            strategy="centralized",
            environment="staging",
            platform="analytics",
        )
        assert resolver.resolve_job_namespace() == "staging.analytics"
        assert resolver.resolve_dataset_namespace() == "staging.analytics"

    @pytest.mark.requirement("REQ-517")
    def test_data_mesh_strategy_selection(self) -> None:
        """NamespaceResolver selects data mesh strategy correctly."""
        resolver = NamespaceResolver(
            strategy="data_mesh",
            domain="finance",
            product_name="revenue-dashboard",
        )
        assert resolver.resolve_job_namespace() == "finance.revenue-dashboard"
        assert resolver.resolve_dataset_namespace() == "finance.revenue-dashboard"

    @pytest.mark.requirement("REQ-528")
    def test_centralized_requires_environment_and_platform(self) -> None:
        """Centralized strategy requires both environment and platform."""
        with pytest.raises(ValueError, match="centralized strategy requires"):
            NamespaceResolver(strategy="centralized", environment="prod")

        with pytest.raises(ValueError, match="centralized strategy requires"):
            NamespaceResolver(strategy="centralized", platform="platform")

    @pytest.mark.requirement("REQ-528")
    def test_data_mesh_requires_domain_and_product(self) -> None:
        """Data mesh strategy requires both domain and product_name."""
        with pytest.raises(ValueError, match="data_mesh strategy requires"):
            NamespaceResolver(strategy="data_mesh", domain="customer")

        with pytest.raises(ValueError, match="data_mesh strategy requires"):
            NamespaceResolver(strategy="data_mesh", product_name="product")

    @pytest.mark.requirement("REQ-528")
    def test_unknown_strategy_raises_error(self) -> None:
        """Unknown strategy name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown strategy: invalid"):
            NamespaceResolver(strategy="invalid")

    @pytest.mark.requirement("REQ-517")
    def test_dataset_namespace_with_table_identifier(self) -> None:
        """resolve_dataset_namespace accepts table_identifier parameter."""
        resolver = NamespaceResolver(
            strategy="simple",
            default_namespace="prod",
        )
        namespace = resolver.resolve_dataset_namespace(table_identifier="bronze.customers")
        assert namespace == "prod"

    @pytest.mark.requirement("REQ-517")
    def test_default_strategy_and_namespace(self) -> None:
        """NamespaceResolver uses default strategy and namespace when not specified."""
        resolver = NamespaceResolver()
        assert resolver.resolve_job_namespace() == "default"
        assert resolver.default_namespace == "default"

    @pytest.mark.requirement("REQ-528")
    def test_centralized_missing_both_parameters(self) -> None:
        """Centralized strategy raises error when both parameters missing."""
        with pytest.raises(ValueError, match="centralized strategy requires"):
            NamespaceResolver(strategy="centralized")

    @pytest.mark.requirement("REQ-528")
    def test_data_mesh_missing_both_parameters(self) -> None:
        """Data mesh strategy raises error when both parameters missing."""
        with pytest.raises(ValueError, match="data_mesh strategy requires"):
            NamespaceResolver(strategy="data_mesh")


class MockCatalogPlugin:
    """Mock catalog plugin for testing."""

    @property
    def name(self) -> str:
        """Return mock catalog name."""
        return "polaris"


class MockCatalogPluginNonString:
    """Mock catalog plugin that returns non-string name."""

    @property
    def name(self) -> int:
        """Return non-string name to test str() conversion."""
        return 12345


class TestCatalogDatasetResolver:
    """Tests for CatalogDatasetResolver."""

    @pytest.mark.requirement("REQ-517")
    def test_resolve_namespace_with_catalog_plugin(self) -> None:
        """Resolver uses catalog plugin name when available."""
        mock_catalog = MockCatalogPlugin()
        resolver = CatalogDatasetResolver(catalog_plugin=mock_catalog)
        assert resolver.resolve_namespace() == "polaris"

    @pytest.mark.requirement("REQ-517")
    def test_resolve_namespace_without_catalog_plugin(self) -> None:
        """Resolver uses default namespace when catalog plugin is None."""
        resolver = CatalogDatasetResolver(
            catalog_plugin=None,
            default_namespace="staging",
        )
        assert resolver.resolve_namespace() == "staging"

    @pytest.mark.requirement("REQ-517")
    def test_resolve_namespace_with_non_string_plugin_name(self) -> None:
        """Resolver converts non-string catalog plugin name via str()."""
        mock_catalog = MockCatalogPluginNonString()
        resolver = CatalogDatasetResolver(catalog_plugin=mock_catalog)
        assert resolver.resolve_namespace() == "12345"

    @pytest.mark.requirement("REQ-517")
    def test_default_namespace_is_default(self) -> None:
        """CatalogDatasetResolver uses 'default' as default namespace."""
        resolver = CatalogDatasetResolver()
        assert resolver.resolve_namespace() == "default"
        assert resolver.default_namespace == "default"

    @pytest.mark.requirement("REQ-517")
    def test_resolve_dataset_with_catalog_plugin(self) -> None:
        """resolve_dataset creates LineageDataset with catalog namespace."""
        mock_catalog = MockCatalogPlugin()
        resolver = CatalogDatasetResolver(catalog_plugin=mock_catalog)

        dataset = resolver.resolve_dataset("customers")

        assert isinstance(dataset, LineageDataset)
        assert dataset.namespace == "polaris"
        assert dataset.name == "customers"
        assert dataset.facets == {}

    @pytest.mark.requirement("REQ-517")
    def test_resolve_dataset_without_catalog_plugin(self) -> None:
        """resolve_dataset uses default namespace when catalog is None."""
        resolver = CatalogDatasetResolver(default_namespace="production")

        dataset = resolver.resolve_dataset("orders")

        assert dataset.namespace == "production"
        assert dataset.name == "orders"

    @pytest.mark.requirement("REQ-517")
    def test_resolve_dataset_with_explicit_namespace(self) -> None:
        """resolve_dataset respects explicit namespace override."""
        mock_catalog = MockCatalogPlugin()
        resolver = CatalogDatasetResolver(catalog_plugin=mock_catalog)

        dataset = resolver.resolve_dataset("products", namespace="custom")

        assert dataset.namespace == "custom"
        assert dataset.name == "products"

    @pytest.mark.requirement("REQ-517")
    def test_resolve_dataset_with_qualified_table_name(self) -> None:
        """resolve_dataset handles qualified table names."""
        resolver = CatalogDatasetResolver(default_namespace="prod")

        dataset = resolver.resolve_dataset("bronze.raw_customers")

        assert dataset.name == "bronze.raw_customers"
        assert dataset.namespace == "prod"

    @pytest.mark.requirement("REQ-517")
    def test_resolve_dataset_with_empty_table_name_raises_error(self) -> None:
        """resolve_dataset raises ValidationError for empty table name."""
        from pydantic import ValidationError

        resolver = CatalogDatasetResolver(default_namespace="prod")

        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            resolver.resolve_dataset("")

    @pytest.mark.requirement("REQ-531")
    def test_enrich_with_snapshot_adds_iceberg_facet(self) -> None:
        """enrich_with_snapshot adds IcebergSnapshotFacet to dataset."""
        resolver = CatalogDatasetResolver(default_namespace="prod")
        dataset = resolver.resolve_dataset("customers")

        enriched = resolver.enrich_with_snapshot(
            dataset=dataset,
            snapshot_id=123456789,
            timestamp_ms=1609459200000,
            operation="append",
        )

        assert "icebergSnapshot" in enriched.facets
        snapshot_facet = enriched.facets["icebergSnapshot"]
        assert snapshot_facet["snapshot_id"] == 123456789
        assert snapshot_facet["timestamp_ms"] == 1609459200000
        assert snapshot_facet["operation"] == "append"
        assert snapshot_facet["_producer"] == "floe"

    @pytest.mark.requirement("REQ-531")
    def test_enrich_with_snapshot_includes_summary(self) -> None:
        """enrich_with_snapshot includes summary statistics when provided."""
        resolver = CatalogDatasetResolver(default_namespace="prod")
        dataset = resolver.resolve_dataset("orders")

        summary = {
            "added-files": "5",
            "added-records": "1000",
            "total-records": "5000",
        }

        enriched = resolver.enrich_with_snapshot(
            dataset=dataset,
            snapshot_id=987654321,
            timestamp_ms=1640995200000,
            operation="overwrite",
            summary=summary,
        )

        snapshot_facet = enriched.facets["icebergSnapshot"]
        assert snapshot_facet["summary"] == summary

    @pytest.mark.requirement("REQ-531")
    def test_enrich_with_snapshot_preserves_existing_facets(self) -> None:
        """enrich_with_snapshot preserves existing facets on dataset."""
        resolver = CatalogDatasetResolver(default_namespace="prod")

        # Create dataset with existing facets
        original_dataset = LineageDataset(
            namespace="prod",
            name="customers",
            facets={
                "schema": {"fields": [{"name": "id", "type": "INTEGER"}]},
                "quality": {"assertions": []},
            },
        )

        enriched = resolver.enrich_with_snapshot(
            dataset=original_dataset,
            snapshot_id=111222333,
            timestamp_ms=1672531200000,
            operation="append",
        )

        # Original facets preserved
        assert "schema" in enriched.facets
        assert "quality" in enriched.facets
        # New facet added
        assert "icebergSnapshot" in enriched.facets

    @pytest.mark.requirement("REQ-531")
    def test_enrich_with_snapshot_returns_new_instance(self) -> None:
        """enrich_with_snapshot returns new LineageDataset instance."""
        resolver = CatalogDatasetResolver(default_namespace="prod")
        original = resolver.resolve_dataset("products")

        enriched = resolver.enrich_with_snapshot(
            dataset=original,
            snapshot_id=999888777,
            timestamp_ms=1704067200000,
            operation="delete",
        )

        # Different instances
        assert enriched is not original
        # Original unchanged
        assert "icebergSnapshot" not in original.facets
        # Enriched has facet
        assert "icebergSnapshot" in enriched.facets

    @pytest.mark.requirement("REQ-531")
    def test_enrich_with_snapshot_empty_summary(self) -> None:
        """enrich_with_snapshot handles empty summary dict."""
        resolver = CatalogDatasetResolver(default_namespace="prod")
        dataset = resolver.resolve_dataset("events")

        enriched = resolver.enrich_with_snapshot(
            dataset=dataset,
            snapshot_id=111,
            timestamp_ms=1000,
            operation="append",
            summary={},
        )

        assert enriched.facets["icebergSnapshot"]["summary"] == {}

    @pytest.mark.requirement("REQ-531")
    def test_enrich_with_snapshot_none_summary(self) -> None:
        """enrich_with_snapshot omits summary key when None."""
        resolver = CatalogDatasetResolver(default_namespace="prod")
        dataset = resolver.resolve_dataset("events")

        enriched = resolver.enrich_with_snapshot(
            dataset=dataset,
            snapshot_id=222,
            timestamp_ms=2000,
            operation="overwrite",
            summary=None,
        )

        assert "summary" not in enriched.facets["icebergSnapshot"]

    @pytest.mark.requirement("REQ-531")
    def test_multiple_enrichments_accumulate_facets(self) -> None:
        """Multiple enrichments can add different facets."""
        resolver = CatalogDatasetResolver(default_namespace="prod")
        dataset = resolver.resolve_dataset("events")

        # First enrichment
        enriched1 = resolver.enrich_with_snapshot(
            dataset=dataset,
            snapshot_id=100,
            timestamp_ms=1000000,
            operation="append",
        )

        # Manually add another facet to simulate multiple enrichments
        enriched2 = LineageDataset(
            namespace=enriched1.namespace,
            name=enriched1.name,
            facets={
                **enriched1.facets,
                "schema": {"fields": [{"name": "event_id", "type": "BIGINT"}]},
            },
        )

        assert "icebergSnapshot" in enriched2.facets
        assert "schema" in enriched2.facets


class TestIntegration:
    """Integration tests combining resolver components."""

    @pytest.mark.requirement("REQ-517")
    def test_namespace_resolver_with_catalog_resolver(self) -> None:
        """NamespaceResolver and CatalogDatasetResolver work together."""
        ns_resolver = NamespaceResolver(
            strategy="centralized",
            environment="production",
            platform="data-platform",
        )

        catalog_resolver = CatalogDatasetResolver(
            default_namespace=ns_resolver.resolve_job_namespace()
        )

        dataset = catalog_resolver.resolve_dataset("customers")

        assert dataset.namespace == "production.data-platform"
        assert dataset.name == "customers"

    @pytest.mark.requirement("REQ-517")
    @pytest.mark.requirement("REQ-531")
    def test_full_workflow_with_enrichment(self) -> None:
        """Full workflow: namespace resolution, dataset creation, enrichment."""
        # 1. Resolve namespace using data mesh strategy
        ns_resolver = NamespaceResolver(
            strategy="data_mesh",
            domain="finance",
            product_name="revenue-analytics",
        )
        namespace = ns_resolver.resolve_dataset_namespace()

        # 2. Create catalog resolver with resolved namespace
        catalog_resolver = CatalogDatasetResolver(default_namespace=namespace)

        # 3. Resolve dataset
        dataset = catalog_resolver.resolve_dataset("revenue_summary")

        # 4. Enrich with Iceberg snapshot
        enriched = catalog_resolver.enrich_with_snapshot(
            dataset=dataset,
            snapshot_id=555666777,
            timestamp_ms=1735689600000,
            operation="append",
            summary={"added-records": "2500"},
        )

        # Verify full workflow
        assert enriched.namespace == "finance.revenue-analytics"
        assert enriched.name == "revenue_summary"
        assert "icebergSnapshot" in enriched.facets
        assert enriched.facets["icebergSnapshot"]["snapshot_id"] == 555666777

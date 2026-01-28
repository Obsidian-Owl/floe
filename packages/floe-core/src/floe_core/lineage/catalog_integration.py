"""Catalog integration for lineage namespace resolution and dataset enrichment.

This module provides namespace resolution strategies and catalog-aware dataset
resolution for OpenLineage integration. It supports multiple namespace strategies
(simple, centralized, data mesh) and enriches datasets with Iceberg snapshot metadata.

See Also:
    - ADR-0007: OpenLineage enforced
    - Epic 6B: OpenLineage Integration
    - REQ-517: Namespace resolution strategies
    - REQ-528: Namespace validation
    - REQ-531: Iceberg snapshot facets
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from floe_core.lineage.facets import IcebergSnapshotFacetBuilder
from floe_core.lineage.types import LineageDataset

if TYPE_CHECKING:
    from floe_core.plugins.catalog import CatalogPlugin


class NamespaceStrategy(ABC):
    """Abstract base class for namespace resolution strategies.

    Namespace strategies determine how lineage namespaces are resolved
    for jobs and datasets. Different strategies support different
    organizational patterns (simple, centralized, data mesh).
    """

    @abstractmethod
    def resolve(self, **kwargs: Any) -> str:
        """Resolve namespace based on strategy-specific parameters.

        Args:
            **kwargs: Strategy-specific parameters.

        Returns:
            Resolved namespace string.
        """
        ...


class SimpleNamespaceStrategy(NamespaceStrategy):
    """Simple namespace strategy that returns a static namespace.

    This strategy is useful for single-environment deployments or
    when namespace is explicitly configured.

    Examples:
        >>> strategy = SimpleNamespaceStrategy(namespace="production")
        >>> strategy.resolve()
        'production'
    """

    def __init__(self, namespace: str) -> None:
        """Initialize simple namespace strategy.

        Args:
            namespace: Static namespace to return.
        """
        self._namespace = namespace

    def resolve(self, **kwargs: Any) -> str:
        """Return the static namespace.

        Args:
            **kwargs: Ignored for simple strategy.

        Returns:
            Static namespace string.
        """
        return self._namespace


class CentralizedNamespaceStrategy(NamespaceStrategy):
    """Centralized namespace strategy using environment and platform.

    This strategy constructs namespaces as {environment}.{platform},
    suitable for centralized platform teams managing multiple environments.

    Examples:
        >>> strategy = CentralizedNamespaceStrategy(
        ...     environment="production",
        ...     platform="data-platform"
        ... )
        >>> strategy.resolve()
        'production.data-platform'
    """

    def __init__(self, environment: str, platform: str) -> None:
        """Initialize centralized namespace strategy.

        Args:
            environment: Environment name (e.g., "production", "staging").
            platform: Platform name (e.g., "data-platform", "analytics").
        """
        self._environment = environment
        self._platform = platform

    def resolve(self, **kwargs: Any) -> str:
        """Resolve namespace as {environment}.{platform}.

        Args:
            **kwargs: Ignored for centralized strategy.

        Returns:
            Namespace in format {environment}.{platform}.
        """
        return f"{self._environment}.{self._platform}"


class DataMeshNamespaceStrategy(NamespaceStrategy):
    """Data mesh namespace strategy using domain and product name.

    This strategy constructs namespaces as {domain}.{product_name},
    suitable for federated data mesh architectures with domain ownership.

    Examples:
        >>> strategy = DataMeshNamespaceStrategy(
        ...     domain="customer",
        ...     product_name="customer-360"
        ... )
        >>> strategy.resolve()
        'customer.customer-360'
    """

    def __init__(self, domain: str, product_name: str) -> None:
        """Initialize data mesh namespace strategy.

        Args:
            domain: Domain name (e.g., "customer", "finance").
            product_name: Product name (e.g., "customer-360", "revenue-analytics").
        """
        self._domain = domain
        self._product_name = product_name

    def resolve(self, **kwargs: Any) -> str:
        """Resolve namespace as {domain}.{product_name}.

        Args:
            **kwargs: Ignored for data mesh strategy.

        Returns:
            Namespace in format {domain}.{product_name}.
        """
        return f"{self._domain}.{self._product_name}"


class NamespaceResolver:
    """Resolver for lineage namespaces using pluggable strategies.

    NamespaceResolver selects and applies namespace strategies based on
    configuration. It supports simple, centralized, and data mesh strategies.

    Attributes:
        strategy: Selected namespace strategy instance.
        default_namespace: Fallback namespace if strategy cannot resolve.

    Examples:
        >>> # Simple strategy
        >>> resolver = NamespaceResolver(strategy="simple", default_namespace="prod")
        >>> resolver.resolve_job_namespace()
        'prod'

        >>> # Centralized strategy
        >>> resolver = NamespaceResolver(
        ...     strategy="centralized",
        ...     environment="staging",
        ...     platform="analytics"
        ... )
        >>> resolver.resolve_job_namespace()
        'staging.analytics'

        >>> # Data mesh strategy
        >>> resolver = NamespaceResolver(
        ...     strategy="data_mesh",
        ...     domain="finance",
        ...     product_name="revenue-dashboard"
        ... )
        >>> resolver.resolve_job_namespace()
        'finance.revenue-dashboard'
    """

    def __init__(
        self,
        strategy: str = "simple",
        default_namespace: str = "default",
        environment: str | None = None,
        platform: str | None = None,
        domain: str | None = None,
        product_name: str | None = None,
    ) -> None:
        """Initialize namespace resolver with strategy selection.

        Args:
            strategy: Strategy name ("simple", "centralized", "data_mesh").
            default_namespace: Fallback namespace for simple strategy.
            environment: Environment name for centralized strategy.
            platform: Platform name for centralized strategy.
            domain: Domain name for data mesh strategy.
            product_name: Product name for data mesh strategy.

        Raises:
            ValueError: If strategy is unknown or required parameters are missing.
        """
        self.default_namespace = default_namespace

        if strategy == "simple":
            self.strategy: NamespaceStrategy = SimpleNamespaceStrategy(namespace=default_namespace)
        elif strategy == "centralized":
            if environment is None or platform is None:
                raise ValueError("centralized strategy requires environment and platform")
            self.strategy = CentralizedNamespaceStrategy(environment=environment, platform=platform)
        elif strategy == "data_mesh":
            if domain is None or product_name is None:
                raise ValueError("data_mesh strategy requires domain and product_name")
            self.strategy = DataMeshNamespaceStrategy(domain=domain, product_name=product_name)
        else:
            raise ValueError(
                f"Unknown strategy: {strategy}. Must be one of: simple, centralized, data_mesh"
            )

    def resolve_job_namespace(self) -> str:
        """Resolve namespace for job (producer) identity.

        Returns:
            Resolved namespace string for the job.

        Examples:
            >>> resolver = NamespaceResolver(strategy="simple", default_namespace="prod")
            >>> resolver.resolve_job_namespace()
            'prod'
        """
        return self.strategy.resolve()

    def resolve_dataset_namespace(self, table_identifier: str | None = None) -> str:
        """Resolve namespace for dataset (data source) identity.

        Args:
            table_identifier: Optional table identifier for context.
                Currently unused but reserved for future enhancements.

        Returns:
            Resolved namespace string for the dataset.

        Examples:
            >>> resolver = NamespaceResolver(
            ...     strategy="centralized",
            ...     environment="prod",
            ...     platform="analytics"
            ... )
            >>> resolver.resolve_dataset_namespace()
            'prod.analytics'
        """
        return self.strategy.resolve()


class CatalogDatasetResolver:
    """Resolver for lineage datasets with catalog integration.

    CatalogDatasetResolver creates LineageDataset instances with proper
    namespace resolution and optional Iceberg snapshot enrichment.
    It gracefully handles missing catalog plugins.

    Attributes:
        catalog_plugin: Optional catalog plugin for namespace resolution.
        default_namespace: Fallback namespace when catalog is unavailable.

    Examples:
        >>> # Without catalog plugin
        >>> resolver = CatalogDatasetResolver(default_namespace="prod")
        >>> dataset = resolver.resolve_dataset("customers")
        >>> dataset.namespace
        'prod'

        >>> # With catalog plugin (mock)
        >>> class MockCatalog:
        ...     @property
        ...     def name(self) -> str:
        ...         return "polaris"
        >>> resolver = CatalogDatasetResolver(catalog_plugin=MockCatalog())
        >>> dataset = resolver.resolve_dataset("orders")
        >>> dataset.namespace
        'polaris'
    """

    def __init__(
        self,
        catalog_plugin: Any | None = None,
        default_namespace: str = "default",
    ) -> None:
        """Initialize catalog dataset resolver.

        Args:
            catalog_plugin: Optional catalog plugin with 'name' property.
                Type hint is Any to avoid hard dependency on CatalogPlugin.
            default_namespace: Fallback namespace when catalog is unavailable.
        """
        self.catalog_plugin = catalog_plugin
        self.default_namespace = default_namespace

    def resolve_namespace(self) -> str:
        """Resolve namespace from catalog plugin or default.

        Returns catalog plugin name if available, otherwise returns
        the default namespace.

        Returns:
            Resolved namespace string.

        Examples:
            >>> resolver = CatalogDatasetResolver(default_namespace="staging")
            >>> resolver.resolve_namespace()
            'staging'
        """
        if self.catalog_plugin is not None:
            return self.catalog_plugin.name
        return self.default_namespace

    def resolve_dataset(
        self,
        table_name: str,
        namespace: str | None = None,
    ) -> LineageDataset:
        """Create LineageDataset with resolved namespace.

        Args:
            table_name: Table name (e.g., "customers", "bronze.orders").
            namespace: Optional explicit namespace override.
                If None, uses resolve_namespace().

        Returns:
            LineageDataset instance with resolved namespace.

        Examples:
            >>> resolver = CatalogDatasetResolver(default_namespace="prod")
            >>> dataset = resolver.resolve_dataset("customers")
            >>> dataset.name
            'customers'
            >>> dataset.namespace
            'prod'

            >>> # With explicit namespace override
            >>> dataset = resolver.resolve_dataset("orders", namespace="staging")
            >>> dataset.namespace
            'staging'
        """
        resolved_namespace = namespace if namespace is not None else self.resolve_namespace()
        return LineageDataset(
            namespace=resolved_namespace,
            name=table_name,
            facets={},
        )

    def enrich_with_snapshot(
        self,
        dataset: LineageDataset,
        snapshot_id: int,
        timestamp_ms: int,
        operation: str,
        summary: dict[str, str] | None = None,
    ) -> LineageDataset:
        """Enrich dataset with Iceberg snapshot facet.

        Creates a new LineageDataset with the Iceberg snapshot facet added.
        Since LineageDataset is frozen, this returns a new instance.

        Args:
            dataset: Original LineageDataset to enrich.
            snapshot_id: Iceberg snapshot ID.
            timestamp_ms: Snapshot timestamp in milliseconds since epoch.
            operation: Snapshot operation (append, overwrite, delete, etc.).
            summary: Optional summary statistics dict.

        Returns:
            New LineageDataset with Iceberg snapshot facet added.

        Examples:
            >>> resolver = CatalogDatasetResolver(default_namespace="prod")
            >>> dataset = resolver.resolve_dataset("customers")
            >>> enriched = resolver.enrich_with_snapshot(
            ...     dataset=dataset,
            ...     snapshot_id=123456789,
            ...     timestamp_ms=1609459200000,
            ...     operation="append",
            ...     summary={"added-records": "1000"}
            ... )
            >>> "icebergSnapshot" in enriched.facets
            True
            >>> enriched.facets["icebergSnapshot"]["snapshot_id"]
            123456789
        """
        snapshot_facet = IcebergSnapshotFacetBuilder.from_snapshot(
            snapshot_id=snapshot_id,
            timestamp_ms=timestamp_ms,
            operation=operation,
            summary=summary,
        )

        # Create new facets dict with snapshot added
        new_facets = {**dataset.facets, "icebergSnapshot": snapshot_facet}

        # Return new dataset with enriched facets
        return LineageDataset(
            namespace=dataset.namespace,
            name=dataset.name,
            facets=new_facets,
        )


__all__ = [
    "NamespaceStrategy",
    "SimpleNamespaceStrategy",
    "CentralizedNamespaceStrategy",
    "DataMeshNamespaceStrategy",
    "NamespaceResolver",
    "CatalogDatasetResolver",
]

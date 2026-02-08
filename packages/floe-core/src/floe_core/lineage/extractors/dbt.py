"""dbt manifest lineage extractor.

This module extracts lineage information from dbt manifest.json files,
converting dbt models, sources, and tests into floe's LineageDataset format.

The extractor follows dbt's dependency graph structure:
- Uses parent_map for upstream dependencies (preferred)
- Falls back to depends_on.nodes if parent_map unavailable
- Resolves sources from the sources dict
- Adds schema facets from column metadata
- Supports column-level lineage when available

See Also:
    - ADR-0007: OpenLineage enforced
    - Epic 6B: OpenLineage Integration
    - dbt manifest spec: https://docs.getdbt.com/reference/artifacts/manifest-json
"""

from __future__ import annotations

from typing import Any

from floe_core.lineage.facets import ColumnLineageFacetBuilder, SchemaFacetBuilder
from floe_core.lineage.types import LineageDataset


class DbtLineageExtractor:
    """Extract lineage information from dbt manifest.json.

    This extractor implements the LineageExtractor protocol for dbt manifests.
    It converts dbt models, sources, and tests into LineageDataset objects
    with appropriate facets (schema, column lineage).

    Attributes:
        manifest: Parsed dbt manifest.json as a dict.
        default_namespace: Default namespace for datasets (e.g., "prod", "staging").

    Examples:
        >>> manifest = {
        ...     "nodes": {
        ...         "model.project.customers": {
        ...             "database": "analytics",
        ...             "schema": "public",
        ...             "name": "customers",
        ...             "columns": {"id": {"name": "id", "type": "INTEGER"}},
        ...         }
        ...     },
        ...     "parent_map": {"model.project.customers": []},
        ... }
        >>> extractor = DbtLineageExtractor(manifest, default_namespace="prod")
        >>> inputs, outputs = extractor.extract("model.project.customers")
        >>> outputs[0].name
        'analytics.public.customers'
    """

    def __init__(
        self, manifest: dict[str, Any], default_namespace: str = "default"
    ) -> None:
        """Initialize the dbt lineage extractor.

        Args:
            manifest: Parsed dbt manifest.json as a dict.
            default_namespace: Default namespace for datasets (e.g., "prod", "staging").
        """
        self.manifest = manifest
        self.default_namespace = default_namespace

    def extract(
        self, context: Any
    ) -> tuple[list[LineageDataset], list[LineageDataset]]:
        """Extract lineage information from execution context.

        Implements the LineageExtractor protocol. For dbt, the context is
        a node_uid string (e.g., "model.project.customers").

        Args:
            context: Node UID string (e.g., "model.project.customers").

        Returns:
            Tuple of (inputs, outputs) as LineageDataset lists.

        Examples:
            >>> manifest = {"nodes": {}, "parent_map": {}}
            >>> extractor = DbtLineageExtractor(manifest)
            >>> inputs, outputs = extractor.extract("model.project.customers")
        """
        node_uid = str(context)
        return self.extract_model(node_uid)

    def extract_model(
        self, node_uid: str
    ) -> tuple[list[LineageDataset], list[LineageDataset]]:
        """Extract lineage for a dbt model node.

        Resolves input datasets from parent_map (preferred) or depends_on.nodes,
        and creates output dataset from the model itself. Adds schema facets
        from column metadata and column lineage facets when available.

        Args:
            node_uid: The dbt node unique ID (e.g., "model.project.customers").

        Returns:
            Tuple of (inputs, outputs) as LineageDataset lists.

        Examples:
            >>> manifest = {
            ...     "nodes": {
            ...         "model.project.customers": {
            ...             "database": "analytics",
            ...             "schema": "public",
            ...             "name": "customers",
            ...             "alias": "dim_customers",
            ...             "columns": {"id": {"name": "id", "type": "INTEGER"}},
            ...         }
            ...     },
            ...     "parent_map": {"model.project.customers": ["source.project.raw.users"]},
            ...     "sources": {
            ...         "source.project.raw.users": {
            ...             "database": "raw",
            ...             "schema": "public",
            ...             "name": "users",
            ...         }
            ...     },
            ... }
            >>> extractor = DbtLineageExtractor(manifest, default_namespace="prod")
            >>> inputs, outputs = extractor.extract_model("model.project.customers")
            >>> len(inputs)
            1
            >>> inputs[0].name
            'raw.public.users'
            >>> outputs[0].name
            'analytics.public.dim_customers'
        """
        nodes = self.manifest.get("nodes", {})
        parent_map = self.manifest.get("parent_map", {})
        sources = self.manifest.get("sources", {})

        if node_uid not in nodes:
            # Node not found, return empty lineage
            return ([], [])

        node = nodes[node_uid]

        # Resolve input datasets from parent_map (preferred) or depends_on
        parent_uids = parent_map.get(node_uid)
        if parent_uids is None:
            # Fallback to depends_on.nodes
            depends_on = node.get("depends_on", {})
            parent_uids = depends_on.get("nodes", [])

        inputs: list[LineageDataset] = []
        upstream_columns: list[dict[str, Any]] = []

        for parent_uid in parent_uids:
            if parent_uid.startswith("source."):
                # Resolve from sources dict
                if parent_uid in sources:
                    source_node = sources[parent_uid]
                    dataset = self._create_dataset_from_node(source_node)
                    inputs.append(dataset)
                    # Collect upstream columns for column lineage
                    source_columns = source_node.get("columns", {})
                    for col_name in source_columns:
                        upstream_columns.append(
                            {
                                "namespace": self.default_namespace,
                                "name": dataset.name,
                                "field": col_name,
                            }
                        )
            else:
                # Resolve from nodes dict
                if parent_uid in nodes:
                    parent_node = nodes[parent_uid]
                    dataset = self._create_dataset_from_node(parent_node)
                    inputs.append(dataset)
                    # Collect upstream columns for column lineage
                    parent_columns = parent_node.get("columns", {})
                    for col_name in parent_columns:
                        upstream_columns.append(
                            {
                                "namespace": self.default_namespace,
                                "name": dataset.name,
                                "field": col_name,
                            }
                        )

        # Create output dataset from the model itself
        output_dataset = self._create_dataset_from_node(
            node, include_facets=True, upstream_columns=upstream_columns
        )
        outputs = [output_dataset]

        return (inputs, outputs)

    def extract_test(self, node_uid: str) -> list[LineageDataset]:
        """Extract datasets being tested by a dbt test node.

        Args:
            node_uid: The dbt test node unique ID (e.g., "test.project.not_null_customers_id").

        Returns:
            List of LineageDataset objects being tested.

        Examples:
            >>> manifest = {
            ...     "nodes": {
            ...         "test.project.not_null_customers_id": {
            ...             "depends_on": {"nodes": ["model.project.customers"]},
            ...         },
            ...         "model.project.customers": {
            ...             "database": "analytics",
            ...             "schema": "public",
            ...             "name": "customers",
            ...         },
            ...     },
            ...     "parent_map": {},
            ... }
            >>> extractor = DbtLineageExtractor(manifest)
            >>> datasets = extractor.extract_test("test.project.not_null_customers_id")
            >>> len(datasets)
            1
        """
        nodes = self.manifest.get("nodes", {})

        if node_uid not in nodes:
            return []

        test_node = nodes[node_uid]
        depends_on = test_node.get("depends_on", {})
        tested_node_uids = depends_on.get("nodes", [])

        datasets: list[LineageDataset] = []
        for tested_uid in tested_node_uids:
            if tested_uid in nodes:
                tested_node = nodes[tested_uid]
                dataset = self._create_dataset_from_node(tested_node)
                datasets.append(dataset)

        return datasets

    def extract_all_models(
        self,
    ) -> dict[str, tuple[list[LineageDataset], list[LineageDataset]]]:
        """Extract lineage for all model nodes in the manifest.

        Returns:
            Dict mapping node UIDs to (inputs, outputs) tuples.

        Examples:
            >>> manifest = {
            ...     "nodes": {
            ...         "model.project.customers": {
            ...             "database": "analytics",
            ...             "schema": "public",
            ...             "name": "customers",
            ...         }
            ...     },
            ...     "parent_map": {"model.project.customers": []},
            ... }
            >>> extractor = DbtLineageExtractor(manifest)
            >>> all_lineage = extractor.extract_all_models()
            >>> "model.project.customers" in all_lineage
            True
        """
        nodes = self.manifest.get("nodes", {})
        result: dict[str, tuple[list[LineageDataset], list[LineageDataset]]] = {}

        for node_uid in nodes:
            if node_uid.startswith("model."):
                result[node_uid] = self.extract_model(node_uid)

        return result

    def _create_dataset_from_node(
        self,
        node: dict[str, Any],
        include_facets: bool = False,
        upstream_columns: list[dict[str, Any]] | None = None,
    ) -> LineageDataset:
        """Create a LineageDataset from a dbt node.

        Args:
            node: dbt node dict with database, schema, name, alias, columns.
            include_facets: Whether to include schema and column lineage facets.
            upstream_columns: Upstream column info for column lineage facet.

        Returns:
            LineageDataset with appropriate name and facets.
        """
        database = node.get("database", "")
        schema = node.get("schema", "")
        # Use alias if present, else name
        name = node.get("alias") or node.get("name", "")

        # Dataset name: {database}.{schema}.{name}
        dataset_name = f"{database}.{schema}.{name}"

        facets: dict[str, Any] = {}

        if include_facets:
            # Add schema facet from columns
            columns = node.get("columns", {})
            if columns:
                column_list = [
                    {"name": col_name, "type": col_def.get("data_type", "UNKNOWN")}
                    for col_name, col_def in columns.items()
                ]
                facets["schema"] = SchemaFacetBuilder.from_columns(column_list)

                # Add column lineage facet if upstream columns available
                if upstream_columns:
                    facets["columnLineage"] = (
                        ColumnLineageFacetBuilder.from_dbt_columns(
                            columns, upstream_columns
                        )
                    )

        return LineageDataset(
            namespace=self.default_namespace,
            name=dataset_name,
            facets=facets,
        )


__all__ = [
    "DbtLineageExtractor",
]

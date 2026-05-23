# SemanticLayerPlugin

**Purpose**: Business intelligence API and semantic modeling
**Location**: `packages/floe-core/src/floe_core/plugins/semantic.py`
**Entry Point**: `floe.semantic_layers`
**ADR**: [ADR-0001: Cube Semantic Layer](../adr/0001-cube-semantic-layer.md)

SemanticLayerPlugin abstracts semantic/consumption layers (Cube, dbt Semantic Layer), enabling consistent metrics definitions and business intelligence APIs across different implementations.

## Data Engineer Publication Metadata

dbt remains the source of truth for model metadata. Data engineers publish
semantic intent with the typed `meta.floe.semantic` namespace on dbt model
nodes. Cube-specific deployment settings, datasource credentials, service
ports, and storage/catalog endpoints do not belong in this metadata.

Publication is deny-by-default:

- A model is unpublished unless `meta.floe.semantic.publish` is `true`.
- Measures, dimensions, time dimensions, validation metrics, joins, and
  pre-aggregations are unpublished unless explicitly listed under
  `meta.floe.semantic`.
- Unannotated dbt columns are ignored by schema generation. Member `source`
  values must be exact dbt manifest column names, not SQL expressions or
  aliases.
- PII-like, sensitive, or masked columns remain unpublished by default. They may
  be published only when the member metadata explicitly declares
  `policy.safe_for_publication: true`.

Supported metadata shape:

```yaml
models:
  - name: mart_revenue_summary
    meta:
      floe:
        semantic:
          publish: true
          measures:
            total_lifetime_value:
              source: lifetime_value
              type: sum
          dimensions:
            customer_segment:
              source: segment
              type: string
            public_segment:
              source: public_segment
              type: string
              policy:
                safe_for_publication: true
          time_dimensions:
            order_date:
              source: order_date
              granularities: [day, month]
          validation_metrics:
            - total_lifetime_value
          joins:
            dim_accounts:
              sql: "{mart_revenue_summary}.account_id = {dim_accounts}.account_id"
              relationship: belongs_to
          pre_aggregations:
            monthly_revenue:
              type: rollup
              measures: [total_lifetime_value]
              dimensions: [customer_segment]
              time_dimension: order_date
              granularity: month
              refresh_key:
                every: 1 hour
              partition_granularity: month
```

Supported member fields:

| Section | Required fields | Optional fields |
|---------|-----------------|-----------------|
| `measures` | `source`, `type` | `description`, `filters`, `format`, `policy.safe_for_publication` |
| `dimensions` | `source`, `type` | `description`, `filters`, `format`, `policy.safe_for_publication` |
| `time_dimensions` | `source` | `granularities`, `description`, `filters`, `format`, `policy.safe_for_publication` |
| `joins` | `sql` | `relationship` (`belongs_to`, `has_many`, or `has_one`) |
| `pre_aggregations` | none (`type` defaults to `rollup`) | `type`, `measures`, `dimensions`, `time_dimension`, `granularity`, `refresh_key`, `partition_granularity` |
| `validation_metrics` | list of published measure names | none |

Supported measure types are `avg`, `count`, `count_distinct`, `max`, `min`,
`number`, and `sum`. Supported dimension types are `boolean`, `number`,
`string`, and `time`. Time dimensions always publish as Cube `time` members.
Joins must target another published semantic model. Pre-aggregations and
validation metrics must reference published semantic members.

Member definitions use Cube-compatible primitives as adapter input, but the
publication metadata is Floe-owned and provider-neutral. A later runtime phase
maps these published members to mounted provider artifacts and semantic service
bindings.

## Interface Definition

The live ABC is `SemanticLayerPlugin` in
`packages/floe-core/src/floe_core/plugins/semantic.py`. The snippet below is a
conceptual excerpt for the public contract.

```python
# Conceptual excerpt; see packages/floe-core/src/floe_core/plugins/semantic.py
from abc import ABC, abstractmethod
from pathlib import Path

class SemanticLayerPlugin(ABC):
    """Interface for semantic/consumption layers (Cube, dbt Semantic Layer)."""

    name: str
    version: str

    @abstractmethod
    def sync_from_dbt_manifest(
        self,
        manifest_path: Path,
        output_dir: Path
    ) -> list[Path]:
        """Generate semantic models from dbt manifest.

        Args:
            manifest_path: Path to dbt manifest.json
            output_dir: Directory to write semantic model files

        Returns:
            List of generated file paths
        """
        pass

    @abstractmethod
    def get_security_context(
        self,
        namespace: str,
        roles: list[str]
    ) -> dict:
        """Build security context for data isolation.

        Args:
            namespace: Data namespace (e.g., "finance.revenue")
            roles: User roles

        Returns:
            Security context for query filtering
        """
        pass

    @abstractmethod
    def validate_schema(self, schema_dir: Path) -> list["ValidationError"]:
        """Validate semantic layer schema files.

        Args:
            schema_dir: Directory containing schema files

        Returns:
            List of validation errors (empty if valid)
        """
        pass
```

## Reference Implementations

| Plugin | Description |
|--------|-------------|
| `CubeSemanticLayerPlugin` | Cube.js semantic layer with REST/GraphQL/SQL APIs |
| `DBTSemanticLayerPlugin` | dbt Semantic Layer (dbt Cloud or OSS MetricFlow) |

## Related Documents

- [ADR-0001: Cube Semantic Layer](../adr/0001-cube-semantic-layer.md)
- [Plugin Architecture](../plugin-system/index.md)
- [ComputePlugin](compute-plugin.md) - For database connections

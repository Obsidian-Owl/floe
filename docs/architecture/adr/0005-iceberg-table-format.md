# ADR-0005: Apache Iceberg as Enforced Table Format

## Status

Accepted

## Context

floe needs a table format that supports:
- ACID transactions
- Time travel and versioning
- Schema evolution
- Partition evolution
- Multiple compute engines (DuckDB, Snowflake, Spark)

## Decision

**Enforce Apache Iceberg** as the table format (non-pluggable).

### Why Iceberg?

1. **Open standard**: Apache License, vendor-neutral
2. **Multi-engine support**: Works with DuckDB, Spark, Snowflake, BigQuery
3. **ACID guarantees**: Snapshot isolation, serializable isolation
4. **Time travel**: Query historical data via snapshot IDs
5. **Schema evolution**: Add/remove/rename columns without rewriting data
6. **Partition evolution**: Change partitioning scheme without data migration

### Why NOT pluggable?

Making table format pluggable would fragment the ecosystem:
- Different formats have incompatible metadata structures
- Cross-engine compatibility would be impossible
- Plugin implementations would need per-format logic
- Data sharing between teams would fail

## Implementation

- All dbt models write to Iceberg tables
- PyIceberg for Python interactions
- Polaris catalog (or Glue, Unity Catalog) manages Iceberg metadata
- Storage plugins (S3, GCS, Azure) provide FileIO implementations

## Consequences

### Positive

- Guaranteed cross-engine compatibility
- Time travel available everywhere
- ACID transactions by default
- Enables data sharing and collaboration

### Negative

- Teams cannot use Delta Lake or Hudi
- Requires Iceberg-compatible catalog (Polaris, Glue, Unity)
- Learning curve for Iceberg concepts

## References

- [ADR-0036: Storage Plugin Interface](0036-storage-plugin-interface.md)
- [ADR-0018: Opinionation Boundaries](0018-opinionation-boundaries.md)
- [Apache Iceberg Documentation](https://iceberg.apache.org/)

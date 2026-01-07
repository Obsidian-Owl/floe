# ADR-0014: Flink for Streaming Workloads (Deferred)

## Status

Deferred to V2.0

## Context

Floe's initial design focuses on batch-oriented data pipelines using dbt + warehouse compute (DuckDB, Snowflake, BigQuery). However, some use cases require near-real-time processing with sub-minute latency:

- CDC (Change Data Capture) streaming
- Real-time feature engineering for ML
- Event-driven transformations
- Continuous aggregations

Apache Flink is the leading open-source stream processing engine, with:
- **Stateful processing** - Windows, joins, aggregations
- **Exactly-once semantics** - Checkpointing with distributed snapshots
- **SQL support** - Flink SQL for declarative stream transformations
- **Ecosystem** - Integrates with Iceberg, Kafka, dbt (via dbt-flink adapter)

### Current Scope

**MVP (V1.0):** Batch processing only
- dbt compiles SQL to warehouse-native queries
- Dagster orchestrates scheduled runs
- No streaming workloads

**Future (V2.0+):** Streaming with Flink
- dbt SQL optionally compiles to Flink SQL
- Dagster manages Flink job lifecycle
- Continuous queries alongside batch

## Decision

**Defer Flink streaming to V2.0** until:
1. Customer demand for sub-minute latency emerges
2. dbt-flink adapter matures (currently experimental)
3. Team has capacity for Flink operational complexity

**Design for extensibility now** by:
- Keeping compute target abstraction flexible
- Designing Dagster integration to support both batch and streaming
- Documenting future Flink integration path

## Consequences

### Positive

- **Simpler MVP** - No Flink deployment, state management, or checkpointing
- **Reduced operational complexity** - Batch workloads are easier to debug and operate
- **Faster time to market** - 90% of use cases covered by batch processing
- **Mature tooling** - dbt + warehouses are production-proven

### Negative

- **No real-time processing** - Users needing sub-minute latency must use external tools
- **Future migration cost** - Pipelines may need refactoring for streaming semantics
- **Competitive gap** - Some competitors offer streaming out-of-box

### Neutral

- Batch processing (hourly/daily) covers most analytics use cases
- Streaming can be added without breaking existing pipelines

## Future Design (V2.0)

### Integration Architecture

```
floe.yaml
    ↓
floe-core Compiler
    ↓
CompiledArtifacts
    ↓
┌─────────────────────┐
│  OrchestratorPlugin │
│  (e.g., Dagster)    │
└──────────┬──────────┘
           │
      ┌────┴─────┐
      ▼          ▼
  ┌──────┐  ┌────────┐
  │ dbt  │  │ Flink  │
  │Batch │  │Streaming│
  └──────┘  └────────┘
```

### Open Questions (To Be Resolved in V2.0)

1. **dbt SQL to Flink SQL compilation**
   - How do batch semantics map to streaming? (e.g., `GROUP BY` → tumbling window?)
   - Which dbt features are unsupported in streaming mode?

2. **State management**
   - State backend: RocksDB vs in-memory?
   - Savepoint strategy for GitOps deployments?

3. **Deployment model**
   - Flink session cluster vs job cluster?
   - Auto-scaling strategy for Flink TaskManagers?

4. **Dagster integration**
   - Schedules (batch) vs always-on sensors (streaming)?
   - How to handle streaming job restarts?

5. **Observability**
   - Flink metrics → OpenTelemetry?
   - Watermark lag monitoring?

## References

- [Apache Flink](https://flink.apache.org/)
- [dbt-flink adapter](https://github.com/dbt-labs/dbt-flink) (experimental)
- [ADR-0009: dbt Owns SQL Transformations](0009-dbt-owns-sql.md)
- [ADR-0010: Target-Agnostic Compute](0010-target-agnostic-compute.md)

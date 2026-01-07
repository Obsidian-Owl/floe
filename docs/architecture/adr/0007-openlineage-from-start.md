# ADR-0007: Include OpenLineage from Start

## Status

Accepted

## Context

Data lineage is critical for:

- Understanding data dependencies
- Impact analysis for changes
- Debugging data quality issues
- Compliance and auditing

We need to decide whether to include lineage tracking in the initial scaffold or add it later.

Options considered:
- **OpenLineage from start** - Build lineage into foundation
- **Add later** - Focus on core features first
- **Custom lineage** - Build proprietary solution
- **Skip lineage** - Rely on tool-specific lineage (dbt docs, etc.)

## Decision

Include **OpenLineage** integration from the initial scaffold, with **Marquez** as the lineage backend for development.

## Consequences

### Positive

- **Foundation ready** - Lineage events from day one
- **Trace correlation** - Link lineage events to traces via trace_id
- **Standard format** - OpenLineage is becoming the industry standard
- **Tool integration** - Dagster, dbt, Spark emit OpenLineage natively
- **Future-proof** - Won't need to retrofit lineage later

### Negative

- **Additional complexity** - More to build in scaffold
- **Additional infrastructure** - Marquez deployment
- **Learning curve** - Team needs to understand OpenLineage concepts

### Neutral

- Marquez for dev/staging, may use managed service for prod
- Need to define lineage namespace strategy per project

## Implementation Pattern

```go
// OpenLineage event emission
type LineageEmitter interface {
    EmitRunStart(ctx context.Context, job Job, inputs []Dataset) error
    EmitRunComplete(ctx context.Context, job Job, outputs []Dataset) error
    EmitRunFail(ctx context.Context, job Job, err error) error
}

// Job represents a lineage job (e.g., pipeline execution)
type Job struct {
    Namespace string  // {product_name} or {domain}.{product_name}
    Name      string  // model name or job name
}

// Dataset represents a data input/output
type Dataset struct {
    Namespace string  // catalog namespace
    Name      string  // table name
}
```

## Lineage Namespace Strategy

| Mode | Format | Example |
|------|--------|---------|
| Simple | `{product_name}` | `customer-analytics` |
| Centralized | `{product_name}` | `customer-analytics` |
| Mesh | `{domain}.{product_name}` | `sales.customer-360` |

Examples:
- Simple mode: `my-pipeline`
- Data Mesh: `sales.customer-360`

## Integration Points

| Component | Lineage Events |
|-----------|----------------|
| floe (Dagster) | asset.materialize.START/COMPLETE/FAIL |
| floe (dbt) | model.run.START/COMPLETE/FAIL |
| floe (dlt) | ingestion.load.START/COMPLETE/FAIL |
| floe (Quality Checks) | quality.check.START/COMPLETE/FAIL |

## References

- [OpenLineage](https://openlineage.io/)
- [OpenLineage Specification](https://openlineage.io/spec/)
- [Marquez](https://marquezproject.ai/)

# Observability Attributes Contract

**Version:** 0.1.0

This contract defines the OpenTelemetry semantic conventions and OpenLineage attributes used by floe for consistent observability across all pipelines.

## Overview

floe uses two complementary standards:
- **OpenTelemetry** for traces and metrics
- **OpenLineage** for data lineage

Both use a consistent set of attributes prefixed with `floe.*`.

## OpenTelemetry Semantic Conventions

### Resource Attributes

These attributes are set at the resource level and apply to all spans and metrics.

| Attribute | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `floe.namespace` | string | Yes | Lineage namespace | `"my-project"` |
| `floe.product.name` | string | Yes | DataProduct name | `"customer-analytics"` |
| `floe.product.version` | string | Yes | DataProduct version | `"1.0.0"` |
| `floe.mode` | string | Yes | Deployment mode | `"simple"`, `"centralized"`, `"mesh"` |
| `floe.version` | string | Yes | floe version | `"0.1.0"` |

**Data Mesh mode only:**

| Attribute | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `floe.domain` | string | Mesh only | Domain name | `"sales"` |
| `floe.enterprise` | string | Mesh only | Enterprise name | `"acme"` |

### Span Attributes

#### Pipeline Execution

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `floe.pipeline.run_id` | string | Unique run identifier | `"run-abc123"` |
| `floe.pipeline.schedule` | string | Cron expression | `"0 6 * * *"` |
| `floe.pipeline.trigger` | string | How pipeline was triggered | `"scheduled"`, `"manual"`, `"sensor"` |

#### Transform Execution

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `floe.transform.type` | string | Transform type | `"dbt"` |
| `floe.transform.model` | string | Model name | `"silver_customers"` |
| `floe.transform.layer` | string | Data layer | `"bronze"`, `"silver"`, `"gold"` |
| `floe.transform.materialization` | string | dbt materialization | `"table"`, `"view"`, `"incremental"` |

#### Ingestion Execution

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `floe.ingestion.type` | string | Ingestion plugin | `"dlt"` |
| `floe.ingestion.source` | string | Source system | `"salesforce"` |
| `floe.ingestion.destination` | string | Destination table | `"bronze.salesforce_accounts"` |
| `floe.ingestion.write_disposition` | string | Write mode | `"append"`, `"replace"`, `"merge"` |

#### Quality Checks

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `floe.quality.test_name` | string | Test name | `"not_null"` |
| `floe.quality.model` | string | Model being tested | `"silver_customers"` |
| `floe.quality.column` | string | Column being tested | `"customer_id"` |
| `floe.quality.result` | string | Test result | `"pass"`, `"fail"`, `"warn"` |

### Metrics

#### Pipeline Metrics

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| `floe.pipeline.duration` | histogram | seconds | Pipeline run duration |
| `floe.pipeline.runs` | counter | count | Number of pipeline runs |
| `floe.pipeline.failures` | counter | count | Number of failed runs |

#### Transform Metrics

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| `floe.transform.duration` | histogram | seconds | Transform execution time |
| `floe.transform.rows_affected` | gauge | count | Rows inserted/updated |
| `floe.transform.bytes_processed` | gauge | bytes | Data processed |

#### Quality Metrics

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| `floe.quality.tests_total` | counter | count | Total tests executed |
| `floe.quality.tests_passed` | counter | count | Tests passed |
| `floe.quality.tests_failed` | counter | count | Tests failed |
| `floe.quality.coverage` | gauge | percent | Test coverage percentage |

#### Contract Monitoring Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `floe.contract.violations_total` | counter | contract, type, severity | Total contract violations |
| `floe.contract.check_duration_seconds` | histogram | contract, check_type | Contract check latency |
| `floe.contract.freshness_hours` | gauge | contract | Hours since last data update |
| `floe.contract.availability_up` | gauge | contract | 1 if available, 0 if not |
| `floe.contract.quality_score` | gauge | contract | Quality score 0-100 |
| `floe.contract.schema_drift_detected` | gauge | contract | 1 if drift detected, 0 if not |

**Labels:**

| Label | Description | Example |
|-------|-------------|---------|
| `contract` | Contract name | `"sales-customers"` |
| `type` | Violation type | `"freshness_violation"` |
| `severity` | Violation severity | `"warning"` |
| `check_type` | Type of check | `"freshness"`, `"schema_drift"`, `"quality"` |

## OpenLineage Conventions

### Namespace Format

The OpenLineage namespace identifies the source of lineage events.

| Mode | Format | Example |
|------|--------|---------|
| Simple | `{product_name}` | `my-pipeline` |
| Centralized | `{product_name}` | `customer-analytics` |
| Mesh | `{domain}.{product_name}` | `sales.customer-360` |

> **Note:** When floe is managed by Floe SaaS, the namespace format changes to `floe.{tenant_id}.{project_slug}` to include tenant context.

### Job Naming

| Component | Format | Example |
|-----------|--------|---------|
| Pipeline job | `{namespace}.{product_name}` | `sales.customer-360` |
| Transform job | `{namespace}.{model_name}` | `sales.silver_customers` |
| Ingestion job | `{namespace}.ingest.{source}` | `sales.ingest.salesforce` |

### Custom Facets

#### floe Facet

```json
{
  "floe": {
    "_producer": "floe",
    "_schemaURL": "https://floe.dev/schemas/facets/floe-facet.json",
    "version": "0.1.0",
    "mode": "mesh",
    "namespace": "sales.customer-360",
    "product": {
      "name": "customer-360",
      "version": "3.2.1"
    },
    "domain": "sales",
    "layer": "gold"
  }
}
```

#### Data Classification Facet

```json
{
  "dataClassification": {
    "_producer": "floe",
    "_schemaURL": "https://floe.dev/schemas/facets/classification-facet.json",
    "columns": [
      {
        "name": "email",
        "classification": "pii",
        "pii_type": "email",
        "sensitivity": "high"
      },
      {
        "name": "customer_id",
        "classification": "identifier"
      }
    ]
  }
}
```

#### Quality Facet

```json
{
  "quality": {
    "_producer": "floe",
    "_schemaURL": "https://floe.dev/schemas/facets/quality-facet.json",
    "tests": [
      {
        "name": "not_null",
        "column": "customer_id",
        "status": "pass"
      },
      {
        "name": "unique",
        "column": "customer_id",
        "status": "pass"
      }
    ],
    "coverage": 92
  }
}
```

#### Contract Violation Facet

Emitted when a data contract violation is detected by the ContractMonitor.
See [ADR-0028: Runtime Contract Monitoring](../architecture/adr/0028-runtime-contract-monitoring.md).

```json
{
  "contractViolation": {
    "_producer": "floe",
    "_schemaURL": "https://floe.dev/schemas/facets/contract-violation-facet.json",
    "contractName": "sales-customer-360-customers",
    "contractVersion": "2.1.0",
    "violationType": "freshness_violation",
    "severity": "warning",
    "message": "Data is 8 hours old, SLA is 6 hours",
    "element": "updated_at",
    "expectedValue": "PT6H",
    "actualValue": "PT8H",
    "timestamp": "2026-01-03T10:15:00Z"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `contractName` | string | Name of the violated contract |
| `contractVersion` | string | Semantic version of the contract |
| `violationType` | enum | Type of violation (see below) |
| `severity` | enum | `info`, `warning`, `error`, `critical` |
| `message` | string | Human-readable description |
| `element` | string | Column/field name if applicable |
| `expectedValue` | string | Expected value from contract |
| `actualValue` | string | Actual value observed |
| `timestamp` | datetime | When violation was detected |

**Violation Types:**

| Type | Description |
|------|-------------|
| `schema_mismatch` | Actual schema doesn't match contract |
| `schema_drift` | Schema changed from contract definition |
| `freshness_violation` | Data older than SLA allows |
| `availability_violation` | Data source unavailable |
| `quality_violation` | Quality check failed |
| `breaking_change` | Breaking schema change detected |
| `deprecation_warning` | Contract is deprecated |
| `deprecation_error` | Contract is sunset |

#### Contract Status Facet

Emitted on successful contract checks (for completeness in lineage).

```json
{
  "contractStatus": {
    "_producer": "floe",
    "_schemaURL": "https://floe.dev/schemas/facets/contract-status-facet.json",
    "contractName": "sales-customer-360-customers",
    "contractVersion": "2.1.0",
    "checkType": "freshness",
    "status": "pass",
    "threshold": 6.0,
    "actualValue": 2.5,
    "checkedAt": "2026-01-03T10:15:00Z"
  }
}
```

## Configuration

Observability is configured in CompiledArtifacts:

```json
{
  "observability": {
    "traces": true,
    "metrics": true,
    "lineage": true,
    "namespace": "my-project"
  }
}
```

### OTLP Export

Traces and metrics are exported via OTLP:

```yaml
# Environment variables
OTEL_EXPORTER_OTLP_ENDPOINT: "http://otel-collector:4317"
OTEL_SERVICE_NAME: "floe"
OTEL_RESOURCE_ATTRIBUTES: "floe.namespace=my-project,floe.product.name=customer-analytics"
```

### OpenLineage Export

Lineage events are sent to an OpenLineage-compatible backend:

```yaml
# Environment variables
OPENLINEAGE_URL: "http://marquez:5000"
OPENLINEAGE_NAMESPACE: "my-project"
```

## Examples

### Trace Example

```
Trace: run-abc123
└── floe.pipeline.run (10m 30s)
    ├── floe.transform.execute: bronze_salesforce_accounts (2m)
    │   └── floe.quality.test: not_null (100ms)
    ├── floe.transform.execute: silver_customers (5m)
    │   ├── floe.quality.test: not_null (100ms)
    │   ├── floe.quality.test: unique (150ms)
    │   └── floe.quality.test: freshness (200ms)
    └── floe.transform.execute: gold_revenue (3m)
        └── floe.quality.test: not_null (100ms)
```

### Lineage Event Example

```json
{
  "eventType": "COMPLETE",
  "eventTime": "2026-01-03T10:30:00Z",
  "run": {
    "runId": "run-abc123"
  },
  "job": {
    "namespace": "sales.customer-360",
    "name": "silver_customers"
  },
  "inputs": [
    {
      "namespace": "sales.customer-360",
      "name": "bronze_salesforce_accounts"
    }
  ],
  "outputs": [
    {
      "namespace": "sales.customer-360",
      "name": "silver_customers",
      "facets": {
        "floe": {
          "version": "0.1.0",
          "mode": "mesh",
          "layer": "silver"
        },
        "dataClassification": {
          "columns": [
            {"name": "email", "classification": "pii"}
          ]
        }
      }
    }
  ]
}
```

## Related Documents

- [CompiledArtifacts Contract](./compiled-artifacts.md) - Schema definition
- [datacontract.yaml Reference](./datacontract-yaml-reference.md) - Contract format
- [Glossary](./glossary.md) - Terminology
- [ADR-0006: OpenTelemetry Observability](../architecture/adr/0006-opentelemetry-observability.md)
- [ADR-0007: OpenLineage from Start](../architecture/adr/0007-openlineage-from-start.md)
- [ADR-0028: Runtime Contract Monitoring](../architecture/adr/0028-runtime-contract-monitoring.md)

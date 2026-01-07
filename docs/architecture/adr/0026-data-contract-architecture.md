# ADR-0026: Data Contract Architecture

## Status

Accepted

## Context

Data products in floe require formal contracts to define expectations between producers and consumers. Without standardized contracts, organizations face:

1. **Schema disagreements**: No formal declaration of columns, types, and constraints
2. **SLA ambiguity**: Freshness, availability, and quality expectations are undocumented
3. **Runtime blind spots**: No monitoring when contracts are violated
4. **Governance gaps**: Data classification, ownership, and terms are inconsistent

The architecture design review identified several gaps:
- **Data-001**: Data product creation flow undocumented (Critical)
- **R-006**: Data Mesh contract race conditions (High)
- **R-009**: Schema evolution undocumented (High)

### Standards Evaluated

Multiple data contract standards were evaluated:

| Standard | Maturity | Tooling | Adoption | Governance |
|----------|----------|---------|----------|------------|
| **ODCS v3** | Production | datacontract-cli | High | Linux Foundation (Bitol) |
| dbt Contracts | Limited | dbt native | High (dbt users) | dbt Labs |
| Soda Contracts | Beta | Soda CLI | Medium | Soda |
| Custom YAML | N/A | Build ourselves | N/A | Internal |

**ODCS v3 is the clear winner** based on:
- Linux Foundation backing (vendor-neutral governance)
- Comprehensive schema, SLA, and quality definitions
- datacontract-cli provides parsing, validation, and drift detection
- Growing industry adoption as the standard format

## Decision

**Enforce ODCS v3** (Open Data Contract Standard) as the data contract format. This is a **core module**, not a plugin.

### Why Enforced (Not Pluggable)?

Data contracts follow the same pattern as other enforced standards:

| Enforced Standard | Rationale |
|-------------------|-----------|
| **Apache Iceberg** (ADR-0005) | Table format cannot be swapped without fragmenting ecosystem |
| **dbt** (ADR-0009) | SQL transformation DSL cannot be swapped mid-project |
| **OpenTelemetry** (ADR-0006) | Observability format cannot vary between teams |
| **ODCS v3** (this ADR) | Contract format cannot vary between data products |

Making contracts pluggable would cause:
- **Interoperability failure**: Different teams using different formats cannot share contracts
- **Tooling fragmentation**: Each format needs separate validation, drift detection, monitoring
- **Governance chaos**: No consistent way to enforce enterprise policies
- **Unrealistic switching**: Organizations don't swap contract standards after choosing

### Architecture

```
Core Modules (enforced, not pluggable):
├── DataContract      -> Uses ODCS v3 (this ADR)
├── PolicyEnforcer    -> Compile-time validation (ADR-0015)
├── dbt               -> SQL transformation (ADR-0009)
├── Iceberg           -> Table format (ADR-0005)
└── OpenTelemetry     -> Observability (ADR-0006)

Pluggable Components (platform team selects):
├── Compute           -> DuckDB, Snowflake, Spark, etc.
├── Orchestrator      -> Dagster, Airflow 3.x
├── Catalog           -> Polaris, Glue, Hive
└── SemanticLayer     -> Cube, dbt Semantic Layer
```

### Integration Points

**1. Compile-Time (PolicyEnforcer)**

Contracts are validated during `floe compile`:
- Schema completeness
- SLA definition validity
- Classification requirements (PII, PHI)
- Version compatibility with previous contract

**2. Runtime (ContractMonitor)**

Contracts are monitored during execution:
- Freshness SLA checks
- Schema drift detection
- Quality threshold validation
- Violations emitted as OpenLineage FAIL events

**3. dbt Integration**

ODCS contracts complement dbt contracts:
- **dbt contracts**: Column-level constraints enforced at build time
- **ODCS contracts**: SLA, quality, governance enforced at runtime

```yaml
# datacontract.yaml (ODCS v3)
apiVersion: v3.0.2
kind: DataContract
name: customers
version: 2.0.0

models:
  customers:
    elements:
      customer_id:
        type: string
        required: true
        primaryKey: true
      email:
        type: string
        classification: pii

slaProperties:
  freshness:
    value: "PT6H"
```

**4. Iceberg Integration**

Contracts define expectations for Iceberg tables:
- Schema matches contract definition
- Freshness measured via table snapshots
- Quality checks run against table data

### Contract Resolution Flow

```
1. Parse data-product.yaml
   -> Extract output_ports, metadata

2. Check for datacontract.yaml
   -> If exists: Validate ODCS v3 format
   -> If absent: Generate from port definitions

3. Validate contract
   -> Schema completeness
   -> SLA validity
   -> Enterprise policy compliance

4. Store in CompiledArtifacts
   -> artifacts.data_contracts[]

5. At runtime: Register with ContractMonitor
   -> Continuous SLA monitoring
   -> Drift detection
```

### Enforcement Levels

Platform teams configure enforcement in `platform-manifest.yaml`:

```yaml
data_contracts:
  enforcement: alert_only  # off | warn | alert_only | block
  monitoring:
    enabled: true
    freshness_check_interval: 15m
    schema_drift_check_interval: 1h
```

| Level | Compile-Time | Runtime |
|-------|--------------|---------|
| `off` | No validation | No monitoring |
| `warn` | Log warnings | Log violations |
| `alert_only` | Fail on critical | Emit OpenLineage FAIL |
| `block` | Fail on any error | Block processing |

### Three-Tier Contract Inheritance

Contracts follow the Data Mesh inheritance model:

```
Enterprise Contracts (base policies)
        |
        v
Domain Contracts (domain-specific additions)
        |
        v
Data Product Contracts (specific implementations)
```

**Inheritance Rules:**
- Child contracts can only **strengthen** parent contracts
- Child contracts cannot **weaken** parent contracts
- Classifications inherit from parent if not specified

## Consequences

### Positive

1. **Consistent format**: All data products use ODCS v3
2. **Unified tooling**: datacontract-cli for all validation and monitoring
3. **Clear governance**: Linux Foundation-backed standard
4. **dbt compatibility**: Complements existing dbt contracts
5. **Runtime visibility**: SLA violations are observable
6. **Enterprise policies**: Inheritance model enforces governance

### Negative

1. **No format choice**: Teams cannot use alternative contract formats
2. **Learning curve**: Teams must learn ODCS v3 syntax
3. **Migration effort**: Existing contracts need conversion to ODCS

### Neutral

1. **datacontract-cli dependency**: Required for validation and drift detection
2. **Alert-only default**: Processing continues on violations (configurable)

## References

- [ODCS - Open Data Contract Standard](https://datacontract.com/spec/odcs) (Bitol, Linux Foundation)
- [datacontract-cli](https://github.com/datacontract/datacontract-cli)
- [ADR-0005: Apache Iceberg as Enforced Table Format](./0005-iceberg-table-format.md)
- [ADR-0006: OpenTelemetry for Observability](./0006-opentelemetry-observability.md)
- [ADR-0009: dbt Owns SQL Transformation](./0009-dbt-owns-sql.md)
- [ADR-0015: Platform Enforcement Architecture](./0015-platform-enforcement-architecture.md)

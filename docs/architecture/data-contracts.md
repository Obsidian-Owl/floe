# Data Contracts Architecture

This document describes the data contract architecture in floe, enabling computational governance through formal agreements between data producers and consumers.

## Overview

Data contracts provide a mechanism for:
- **Schema agreements**: Formal declaration of column names, types, and constraints
- **SLA definitions**: Freshness, availability, and quality guarantees
- **Runtime enforcement**: Monitoring and alerting when contracts are violated
- **Lifecycle management**: Independent versioning and deprecation workflows

```
                          COMPILE TIME                         RUNTIME
                          ──────────────                       ───────
                                │                                  │
floe.yaml ─────────────►│                                  │
       +                        │                                  │
datacontract.yaml (optional) ──►│  PolicyEnforcer                  │
                                │  (compile-time)                  │
                                │        │                         │
                                │        ▼                         │
                                │  CompiledArtifacts ──────────────┼──► ContractMonitor
                                │  (includes contracts)            │    (runtime service)
                                │                                  │         │
                                │                                  │    DataContractPlugin
                                │                                  │    (wraps datacontract-cli)
                                │                                  │         │
                                │                                  │    OrchestratorPlugin
                                │                                  │    (emits OpenLineage)
```

## Contract Model

Floe uses a **hybrid contract model**:

| Model | Description |
|-------|-------------|
| **Auto-generated** | Contracts derived from `floe.yaml` output ports |
| **Explicit** | Contracts defined in `datacontract.yaml` (ODCS format) |
| **Merged** | Explicit overrides auto-generated (default) |

### File Structure

```
data-product/
├── floe.yaml          # Required - defines ports, transforms
├── datacontract.yaml          # Optional - explicit ODCS contract
├── models/
│   └── *.sql
└── tests/
```

### Contract Resolution Flow

```
1. Parse floe.yaml
   └── Extract output_ports, input_ports, metadata

2. Generate base contract
   └── DataContractPlugin.generate_contract_from_ports()

3. Check for explicit datacontract.yaml
   ├── If exists: Parse and merge (explicit overrides generated)
   └── If not: Use generated contract as-is

4. Validate merged contract
   └── PolicyEnforcer.validate_data_contracts()

5. Store in CompiledArtifacts
   └── CompiledArtifacts.data_contracts[]

6. Register contract in catalog
   └── CatalogPlugin.register_contract()

7. At runtime: Register with ContractMonitor
   └── ContractMonitor.register_contract()
```

## Contract Identity

Contracts are uniquely identified by their fully-qualified ID:

```
Contract ID:  {domain}.{product}/{contract}:{version}
              └──────────────────┬─────────────────────┘
              "sales.customer_360/customers:1.0.0"
```

### Identity Structure

| Component | Description | Example |
|-----------|-------------|---------|
| `domain` | Parent domain | `sales` |
| `product` | Data product name | `customer_360` |
| `contract` | Contract name | `customers` |
| `version` | Semantic version | `1.0.0` |

The contract inherits the product's namespace: `sales.customer_360`

### Catalog Registration

Contracts are registered in the Iceberg catalog alongside their parent product:

```
Catalog: floe-data
├── sales.customer_360 (product namespace)
│   ├── Properties:
│   │   ├── floe.product.name = "customer_360"
│   │   ├── floe.product.repo = "github.com/acme/sales-customer-360"
│   │   └── floe.contracts = '["customers:1.0.0", "orders:2.1.0"]'
│   │
│   └── Tables:
│       └── gold.customers
```

### Registration During Compile

Contracts are registered via `CatalogPlugin.register_contract()`:

```python
# During floe compile
catalog.register_contract(
    namespace="sales.customer_360",
    contract_name="customers",
    contract_version="1.0.0",
    schema_hash="sha256:abc123...",
    metadata=ContractMetadata(
        owner="sales-analytics@acme.com",
        description="Customer master data contract",
        registered_at=datetime.utcnow(),
    ),
)
```

### Immutable Contract Versions

Once a contract version is registered, it is **immutable**:

- Schema hash prevents silent changes
- Version bump required for any modification
- Breaking changes require MAJOR version bump

See [ADR-0030: Namespace-Based Identity](adr/0030-namespace-identity.md) for the full identity model.

## Standard: ODCS v3

Floe adopts the **Open Data Contract Standard (ODCS)** v3.x:

- Linux Foundation project (via Bitol)
- Comprehensive: schema, SLAs, quality, governance
- Tooling: `datacontract-cli` for validation, drift detection
- Extensible: custom properties via additionalProperties

See [ADR-0027: ODCS Standard Adoption](adr/0027-odcs-standard-adoption.md) for rationale.

### Example Contract (ODCS v3)

```yaml
apiVersion: v3.0.2
kind: DataContract
name: sales-customer-360-customers
version: 2.1.0

owner: sales-analytics@acme.com
domain: sales

description: |
  Consolidated customer view combining CRM, transactions, and support data.

models:
  customers:
    description: Customer master data
    elements:
      customer_id:
        type: string
        required: true
        primaryKey: true
        description: Unique customer identifier

      email:
        type: string
        required: true
        format: email
        classification: pii
        unique: true

      lifetime_value:
        type: decimal
        required: false

slaProperties:
  freshness:
    value: "PT6H"     # ISO 8601 duration - 6 hours
    element: updated_at
  availability:
    value: "99.9%"

terms:
  usage: "Internal analytics only"
  retention: "7 years per compliance"

tags:
  - customer-data
  - gold-layer
```

## Enforcement Model

### Compile-Time (PolicyEnforcer)

At compile time, the PolicyEnforcer validates:

| Check | Description |
|-------|-------------|
| Schema validity | Contract schema is valid ODCS |
| Inheritance | Child contracts don't weaken parent |
| Version bump | Semantic versioning rules followed |
| Classification | PII fields properly marked |

### Runtime (ContractMonitor)

At runtime, the ContractMonitor performs:

| Check | Interval | Description |
|-------|----------|-------------|
| Freshness | 15 min | Data updated within SLA window |
| Schema drift | 1 hour | Actual schema matches contract |
| Quality | 6 hours | Data quality above threshold |
| Availability | 5 min | Data source accessible |

### Enforcement Mode: Alert-Only

Violations are emitted as alerts but do not block processing:

```yaml
# manifest.yaml
data_contracts:
  enforcement: alert_only  # off | warn | alert_only | block
```

Violations are emitted via:
- OpenLineage FAIL events with `contractViolation` facet
- Prometheus metrics (`floe_contract_violations_total`)
- Logs for debugging

## Plugin Architecture

### DataContractPlugin Interface

```python
class DataContractPlugin(ABC):
    """Interface for data contract validation and monitoring."""

    # Contract Parsing
    def parse_contract(self, contract_path: Path) -> DataContract
    def generate_contract_from_ports(self, output_ports, input_ports, metadata) -> DataContract
    def merge_contracts(self, generated, explicit) -> DataContract

    # Schema Validation
    def validate_contract(self, contract, actual_schema=None) -> ContractValidationResult
    def lint_contract_file(self, contract_path) -> ContractValidationResult

    # Schema Drift Detection
    def detect_schema_drift(self, contract, connection) -> SchemaComparisonResult
    def compare_schemas(self, old_schema, new_schema) -> SchemaComparisonResult

    # SLA Monitoring
    def check_freshness(self, contract, connection, timestamp_column) -> SLACheckResult
    def check_availability(self, contract, connection) -> SLACheckResult
    def check_quality(self, contract, connection) -> list[SLACheckResult]

    # Contract Lifecycle
    def validate_version_bump(self, old_contract, new_contract) -> tuple[bool, str]
    def check_breaking_changes(self, contract, connection) -> list[ContractViolation]
```

### Default Implementation: ODCS

The default implementation wraps `datacontract-cli`:

```python
class ODCSDataContractPlugin(DataContractPlugin):
    """ODCS implementation using datacontract-cli."""

    name = "odcs"
    version = "1.0.0"

    def __init__(self):
        from datacontract.datacontract import DataContract as DCCli
        self._cli = DCCli
```

## Lifecycle Management

### Semantic Versioning

Contracts use independent semantic versioning:

| Change Type | Version Bump |
|-------------|--------------|
| Remove column | MAJOR |
| Change column type | MAJOR |
| Add required column | MAJOR |
| Relax SLA (degradation) | MAJOR |
| Add optional column | MINOR |
| Stricter SLA (improvement) | MINOR |
| Documentation changes | PATCH |

### Deprecation Workflow

```
  ACTIVE ────► DEPRECATED ────► SUNSET ────► RETIRED
             (30 days)        (7 days)

  Normal      Warnings       Errors for     Contract
  usage       emitted        new consumers  removed
```

```yaml
# In datacontract.yaml
status: deprecated

deprecation:
  announced: "2026-01-03"
  sunset_date: "2026-02-03"
  replacement: sales-customers-v4
  migration_guide: https://wiki.acme.com/migrate-v4
```

## Three-Tier Inheritance

Contracts follow the three-tier enforcement model:

```
Enterprise Contract (base policies)
        │
        ├── All data must have owner
        ├── PII requires classification
        ├── Minimum freshness: 24h
        │
        ▼
Domain Contract (domain-specific)
        │
        ├── Sales domain freshness: 6h
        ├── Required fields for domain
        │
        ▼
Data Product Contract (implementation)
        │
        ├── Specific schema
        └── Cannot relax parent requirements
```

**Inheritance Rules:**
- Child contracts inherit parent requirements
- Child contracts can STRENGTHEN but not WEAKEN
- Violations detected at compile time

## Platform Manifest Configuration

```yaml
# manifest.yaml
data_contracts:
  enforcement: alert_only  # off | warn | alert_only | block
  standard: odcs_v3

  plugin:
    type: odcs             # datacontract-cli wrapper

  auto_generation:
    enabled: true
    from_ports: true       # Generate from input/output ports
    from_dbt_manifest: true # Enrich from dbt manifest

  monitoring:
    enabled: true
    mode: scheduled        # scheduled | continuous | on_demand
    freshness:
      check_interval: 15m
    schema_drift:
      check_interval: 1h
    quality:
      check_interval: 6h

  alerting:
    openlineage_events: true
    prometheus_metrics: true
```

## Error Codes

Contract validation produces specific error codes (FLOE-E5xx series) for actionable diagnostics:

### Contract Parsing Errors (FLOE-E500-E509)

| Code | Description | Cause |
|------|-------------|-------|
| `FLOE-E500` | Contract not found | No `datacontract.yaml` AND no `output_ports` in `floe.yaml` |
| `FLOE-E501` | Invalid ODCS syntax | YAML syntax error or missing required ODCS fields |
| `FLOE-E502` | Unsupported ODCS version | Contract uses unsupported apiVersion |
| `FLOE-E509` | Parse error | Failed to parse contract YAML |

### Inheritance Violations (FLOE-E510-E519)

| Code | Description | Cause |
|------|-------------|-------|
| `FLOE-E510` | SLA weakening | Child contract specifies weaker SLA than parent (e.g., fresher data requirement relaxed) |
| `FLOE-E511` | Classification weakening | Child contract downgrades field classification (e.g., PII to public) |
| `FLOE-E512` | Circular dependency | Contracts form a circular inheritance chain |

### Version Validation Errors (FLOE-E520-E529)

| Code | Description | Cause |
|------|-------------|-------|
| `FLOE-E520` | Breaking change without MAJOR bump | Column removed, type changed, or required column added without MAJOR version increment |
| `FLOE-E521` | Invalid version format | Version doesn't follow semantic versioning (X.Y.Z) |

### Schema Drift Errors (FLOE-E530-E539)

| Code | Description | Cause |
|------|-------------|-------|
| `FLOE-E530` | Type mismatch | Contract specifies different type than actual table schema |
| `FLOE-E531` | Missing column | Contract defines column not present in table |
| `FLOE-E532` | Extra column | Table has column not defined in contract (informational) |

### Registration Warnings (FLOE-E540-E549)

| Code | Severity | Description |
|------|----------|-------------|
| `FLOE-E540` | warning | Catalog unreachable | Contract validated but registration failed due to catalog unavailability |

### Example Error Output

```bash
$ floe compile

[3/5] Validating data contracts
      ✗ FLOE-E510: Child contract weakens 'freshness' SLA
        Parent requires PT6H, child specifies PT12H
        Suggestion: Strengthen 'freshness' to at least match parent: PT6H

      ✗ FLOE-E511: Classification weakening for field 'customers.email'
        Parent requires 'pii', child specifies 'public'
        Suggestion: Use classification 'pii' or stronger for 'customers.email'

      ✗ FLOE-E530: Type mismatch for column 'user_id'
        Contract: string, Table: integer
        Suggestion: Update contract schema or table definition to match
```

## Observability

### OpenLineage Events

Contract violations are emitted as OpenLineage FAIL events:

```json
{
  "eventType": "FAIL",
  "job": { "name": "contract_check.sales-customers" },
  "run": {
    "facets": {
      "contractViolation": {
        "contractName": "sales-customers",
        "contractVersion": "2.1.0",
        "violationType": "freshness_violation",
        "severity": "warning",
        "message": "Data is 8 hours old, SLA is 6 hours"
      }
    }
  }
}
```

### Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `floe_contract_violations_total` | Counter | Total violations |
| `floe_contract_freshness_hours` | Gauge | Hours since last update |
| `floe_contract_availability_up` | Gauge | 1 if available, 0 if not |
| `floe_contract_quality_score` | Gauge | Quality score 0-100 |

## Related Documents

- [ADR-0026: Data Contract Architecture](adr/0026-data-contract-architecture.md)
- [ADR-0027: ODCS Standard Adoption](adr/0027-odcs-standard-adoption.md)
- [ADR-0028: Runtime Contract Monitoring](adr/0028-runtime-contract-monitoring.md)
- [ADR-0029: Contract Lifecycle Management](adr/0029-contract-lifecycle-management.md)
- [ADR-0030: Namespace-Based Identity](adr/0030-namespace-identity.md)
- [Plugin Interfaces](interfaces/index.md) - Plugin interface reference
- [Compiled Artifacts](../contracts/compiled-artifacts.md) - Contract schema
- [datacontract.yaml Reference](../contracts/datacontract-yaml-reference.md)
- [Contract Monitoring Guide](../guides/contract-monitoring.md)
- [Contract Versioning Guide](../guides/contract-versioning.md)

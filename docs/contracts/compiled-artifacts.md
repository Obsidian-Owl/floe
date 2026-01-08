# CompiledArtifacts Contract

The `CompiledArtifacts` schema defines the output of `floe compile` - the resolved, validated configuration that the runtime uses for execution.

## Overview

CompiledArtifacts is the **single source of truth** for pipeline execution. It contains:
- Resolved plugin configuration (after inheritance)
- Compiled transforms
- Governance policies
- Observability settings
- Optional Data Mesh contracts

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  INPUT                                                                       │
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │    Manifest     │───►│    Manifest     │───►│   DataProduct   │          │
│  │ (enterprise)    │    │   (domain)      │    │   (floe.yaml)   │          │
│  │   [optional]    │    │   [optional]    │    │   [required]    │          │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘          │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                          ┌────────────────┐
                          │  floe compile  │
                          └────────┬───────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  OUTPUT                                                                      │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      CompiledArtifacts                               │   │
│  │                                                                      │   │
│  │  • metadata: compilation info, source hash                          │   │
│  │  • mode: "simple" | "centralized" | "mesh"                          │   │
│  │  • inheritance_chain: [manifest refs...]                            │   │
│  │  • plugins: resolved compute, orchestrator, catalog, etc.           │   │
│  │  • transforms: compiled dbt models                                  │   │
│  │  • governance: classification, quality gates                        │   │
│  │  • observability: traces, metrics, lineage config                   │   │
│  │  • output_ports: [optional, mesh only]                              │   │
│  │  • data_contracts: [optional, mesh only]                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Schema Definition

```python
from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class CompiledArtifacts(BaseModel):
    """Output of floe compile - unified for all deployment modes."""

    # Schema version
    version: str = "0.1.0"

    # Compilation metadata
    metadata: CompilationMetadata

    # Product identity (ADR-0030)
    identity: ProductIdentity

    # Deployment mode
    mode: Literal["simple", "centralized", "mesh"]

    # Inheritance chain (for auditing and debugging)
    inheritance_chain: list[ManifestRef]

    # Resolved plugin configuration
    plugins: PluginConfig

    # Core pipeline configuration
    transforms: list[CompiledTransform]
    schedule: ScheduleConfig | None
    dbt: DbtConfig

    # Governance (merged from all inheritance levels)
    governance: GovernanceConfig

    # Observability
    observability: ObservabilityConfig

    # Data Mesh (optional - only present in mesh mode)
    output_ports: list[OutputPort] | None = None
    input_ports: list[InputPort] | None = None
    data_contracts: list[DataContract] | None = None


class CompilationMetadata(BaseModel):
    """Information about the compilation process."""

    compiled_at: datetime
    floe_version: str
    source_hash: str  # SHA256 of input files
    product_name: str
    product_version: str


class ProductIdentity(BaseModel):
    """Product identity information from catalog registration.

    See ADR-0030 for the namespace-based identity model.
    """

    product_id: str              # "sales.customer_360"
    domain: str                  # "sales"
    repository: str              # "github.com/acme/sales-customer-360"
    namespace_registered: bool   # True if registered in catalog
    registration_timestamp: datetime | None  # When first registered


class ManifestRef(BaseModel):
    """Reference to a manifest in the inheritance chain."""

    name: str
    version: str
    scope: Literal["enterprise", "domain"]
    ref: str  # OCI reference
```

## Plugin Configuration

```python
class PluginConfig(BaseModel):
    """Resolved plugin configuration after inheritance."""

    compute_registry: ComputeRegistry  # All approved computes (multi-compute support)
    orchestrator: OrchestratorConfig
    catalog: CatalogConfig
    semantic_layer: SemanticLayerConfig
    ingestion: IngestionConfig
    secrets: SecretsConfig


class ComputeRegistry(BaseModel):
    """Registry of all approved compute configurations.

    Platform teams define N approved compute targets. Data engineers
    select per-transform from this approved list.
    See ADR-0010 (Multi-Compute Pipeline Architecture).
    """

    configs: dict[str, ComputeConfig]  # name → config (e.g., {"duckdb": ..., "spark": ...})
    default: str  # Fallback compute when transform doesn't specify


class ComputeConfig(BaseModel):
    """Configuration for a single compute target."""

    name: str  # "duckdb" | "spark" | "snowflake" | etc.
    connection_secret_ref: str | None = None
    properties: dict = {}


class OrchestratorConfig(BaseModel):
    """Orchestrator plugin configuration."""

    type: str  # "dagster" | "airflow" | etc.


class CatalogConfig(BaseModel):
    """Catalog plugin configuration."""

    type: str  # "polaris" | "glue" | "hive" | etc.
    uri: str | None = None


class SemanticLayerConfig(BaseModel):
    """Semantic layer plugin configuration."""

    type: str  # "cube" | "dbt_semantic_layer" | "none"
    port: int | None = None


class IngestionConfig(BaseModel):
    """Ingestion plugin configuration."""

    type: str  # "dlt" | "airbyte"
```

## Transform Configuration

```python
class CompiledTransform(BaseModel):
    """Compiled dbt transform."""

    type: Literal["dbt"]
    path: str
    models: list[str]
    manifest_path: str
    compute: str | None = None  # Selected compute (None → uses default from registry)


class DbtConfig(BaseModel):
    """dbt-specific configuration.

    Note: In multi-compute pipelines, multiple dbt profiles may be generated
    (one per approved compute). The `target` field maps to the compute name.
    """

    manifest_path: str
    project_path: str
    profiles_dir: str
    # Note: target is resolved per-transform from CompiledTransform.compute
```

## Governance Configuration

```python
class GovernanceConfig(BaseModel):
    """Merged governance configuration."""

    classification: ClassificationConfig
    quality_gates: QualityGatesConfig
    data_architecture: DataArchitectureConfig


class ClassificationConfig(BaseModel):
    """Data classification rules."""

    source: Literal["dbt_meta"]
    levels: list[str]  # e.g., ["public", "internal", "confidential", "pii"]


class QualityGatesConfig(BaseModel):
    """Quality gate requirements."""

    minimum_test_coverage: int  # percentage
    required_tests: list[str]  # e.g., ["not_null", "unique", "freshness"]
    block_on_failure: bool


class DataArchitectureConfig(BaseModel):
    """Data architecture pattern configuration."""

    pattern: Literal["medallion", "kimball", "data_vault", "hybrid"]
    layers: dict[str, LayerConfig]
    naming_enforcement: Literal["off", "warn", "strict"]


class LayerConfig(BaseModel):
    """Layer-specific configuration."""

    prefix: str
    namespace: str | None = None
    quality_gates: list[str] = []
```

## Observability Configuration

```python
class ObservabilityConfig(BaseModel):
    """Observability settings."""

    traces: bool = True
    metrics: bool = True
    lineage: bool = True
    namespace: str  # Lineage namespace (e.g., "my-project")
```

## Data Mesh Configuration (Optional)

```python
class OutputPort(BaseModel):
    """Data product output port."""

    name: str
    description: str | None = None
    table: str
    sla: SLAConfig | None = None
    access: AccessConfig | None = None


class InputPort(BaseModel):
    """Data product input port."""

    name: str
    description: str | None = None
    source: SourceConfig
    freshness_requirement: str | None = None


class SLAConfig(BaseModel):
    """Service level agreement."""

    freshness: str  # e.g., "6h"
    availability: str  # e.g., "99.9%"
    quality: dict = {}
```

## Data Contracts (ODCS v3)

Data contracts follow the Open Data Contract Standard (ODCS) v3.x.
See [ADR-0026](../architecture/adr/0026-data-contract-architecture.md) and
[ADR-0027](../architecture/adr/0027-odcs-standard-adoption.md) for background.

```python
class CompiledDataContract(BaseModel):
    """Compiled data contract (ODCS v3 format).

    Stored in CompiledArtifacts.data_contracts for runtime monitoring.
    """

    # ODCS required fields
    api_version: str = "v3.0.2"
    kind: Literal["DataContract"] = "DataContract"
    name: str
    version: str  # Semantic version, independent from data product

    # Ownership
    owner: str
    domain: str | None = None
    description: str | None = None

    # Lifecycle status
    status: Literal["active", "deprecated", "sunset", "retired"] = "active"
    deprecation: DeprecationInfo | None = None

    # Schema models
    models: list[ContractModel]

    # SLA properties
    sla: ContractSLA | None = None

    # Terms and governance
    terms: dict | None = None
    tags: list[str] = []

    # Floe-specific metadata
    source: ContractSource  # Where contract was defined
    generated_at: datetime
    generated_from: Literal["ports", "explicit", "merged"]


class ContractModel(BaseModel):
    """Schema definition for a data model in the contract."""

    name: str
    description: str | None = None
    primary_key: list[str] | None = None
    elements: list[ContractElement]


class ContractElement(BaseModel):
    """Single element (column) in a schema."""

    name: str
    type: str  # string, int, float, decimal, boolean, timestamp, date, etc.
    description: str | None = None
    required: bool = True
    primary_key: bool = False
    unique: bool = False
    classification: str | None = None  # pii, phi, sensitive, etc.
    format: str | None = None  # email, uri, uuid, date-time, etc.


class ContractSLA(BaseModel):
    """Service level agreement for contract."""

    freshness_hours: float | None = None     # Max hours since last update
    availability_percent: float | None = None # Target availability (e.g., 99.9)
    quality_score_min: float | None = None   # Minimum quality score (0-100)
    completeness_percent: float | None = None # Minimum row completeness


class DeprecationInfo(BaseModel):
    """Deprecation metadata for sunsetting contracts."""

    announced: str           # ISO date when deprecation was announced
    sunset_date: str         # ISO date when contract will be retired
    replacement: str | None  # Name of replacement contract
    migration_guide: str | None  # URL to migration documentation
    reason: str | None       # Why the contract is being deprecated


class ContractSource(BaseModel):
    """Source of contract definition."""

    type: Literal["port", "file", "merged"]
    file_path: str | None = None  # Path to datacontract.yaml if explicit
    port_name: str | None = None  # Port name if auto-generated


class ContractMonitoringConfig(BaseModel):
    """Configuration for runtime contract monitoring."""

    enabled: bool = True
    mode: Literal["scheduled", "continuous", "on_demand"] = "scheduled"
    freshness_check_interval: str = "15m"   # ISO duration
    schema_drift_check_interval: str = "1h"  # ISO duration
    quality_check_interval: str = "6h"       # ISO duration
```

## Example: Simple Mode

```json
{
  "version": "0.1.0",
  "metadata": {
    "compiled_at": "2026-01-03T10:00:00Z",
    "floe_version": "0.1.0",
    "source_hash": "sha256:abc123...",
    "product_name": "my-pipeline",
    "product_version": "1.0.0"
  },
  "identity": {
    "product_id": "default.my_pipeline",
    "domain": "default",
    "repository": "github.com/acme/my-pipeline",
    "namespace_registered": true,
    "registration_timestamp": "2026-01-01T00:00:00Z"
  },
  "mode": "simple",
  "inheritance_chain": [],
  "plugins": {
    "compute_registry": {
      "configs": {
        "duckdb": { "name": "duckdb", "properties": { "threads": 8 } }
      },
      "default": "duckdb"
    },
    "orchestrator": { "type": "dagster" },
    "catalog": { "type": "polaris", "uri": "http://polaris:8181/api/catalog" },
    "semantic_layer": { "type": "cube", "port": 4000 },
    "ingestion": { "type": "dlt" },
    "secrets": { "type": "k8s" }
  },
  "transforms": [
    {
      "type": "dbt",
      "path": "./models",
      "models": ["bronze_customers", "silver_customers", "gold_revenue"],
      "manifest_path": "/app/target/manifest.json",
      "compute": null
    }
  ],
  "schedule": {
    "cron": "0 6 * * *",
    "timezone": "UTC"
  },
  "dbt": {
    "manifest_path": "/app/target/manifest.json",
    "project_path": "/app",
    "target": "prod",
    "profiles_dir": "/app/.dbt"
  },
  "governance": {
    "classification": {
      "source": "dbt_meta",
      "levels": ["public", "internal", "confidential", "pii"]
    },
    "quality_gates": {
      "minimum_test_coverage": 80,
      "required_tests": ["not_null", "unique"],
      "block_on_failure": true
    },
    "data_architecture": {
      "pattern": "medallion",
      "layers": {
        "bronze": { "prefix": "bronze_" },
        "silver": { "prefix": "silver_" },
        "gold": { "prefix": "gold_" }
      },
      "naming_enforcement": "strict"
    }
  },
  "observability": {
    "traces": true,
    "metrics": true,
    "lineage": true,
    "namespace": "my-pipeline"
  }
}
```

## Example: Centralized Mode

```json
{
  "version": "0.1.0",
  "metadata": {
    "compiled_at": "2026-01-03T10:00:00Z",
    "floe_version": "0.1.0",
    "source_hash": "sha256:def456...",
    "product_name": "customer-analytics",
    "product_version": "1.0.0"
  },
  "identity": {
    "product_id": "analytics.customer_analytics",
    "domain": "analytics",
    "repository": "github.com/acme/customer-analytics",
    "namespace_registered": true,
    "registration_timestamp": "2026-01-01T00:00:00Z"
  },
  "mode": "centralized",
  "inheritance_chain": [
    {
      "name": "acme-platform",
      "version": "1.2.3",
      "scope": "enterprise",
      "ref": "oci://registry.acme.com/floe-platform:v1.2.3"
    }
  ],
  "plugins": {
    "compute_registry": {
      "configs": {
        "duckdb": { "name": "duckdb", "properties": { "threads": 8 } },
        "spark": { "name": "spark", "properties": { "cluster": "spark-thrift.svc" } }
      },
      "default": "duckdb"
    },
    "orchestrator": { "type": "dagster" },
    "catalog": { "type": "polaris" },
    "semantic_layer": { "type": "cube" },
    "ingestion": { "type": "dlt" },
    "secrets": { "type": "k8s" }
  },
  "transforms": [
    { "type": "dbt", "path": "./models/staging", "models": [...], "compute": "spark" },
    { "type": "dbt", "path": "./models/marts", "models": [...], "compute": "duckdb" }
  ],
  "governance": {
    "classification": {...},
    "quality_gates": {
      "minimum_test_coverage": 80,
      "required_tests": ["not_null", "unique", "freshness"],
      "block_on_failure": true
    },
    "data_architecture": {...}
  },
  "observability": {...}
}
```

## Example: Data Mesh Mode

```json
{
  "version": "0.1.0",
  "metadata": {
    "compiled_at": "2026-01-03T10:00:00Z",
    "floe_version": "0.1.0",
    "source_hash": "sha256:ghi789...",
    "product_name": "customer-360",
    "product_version": "3.2.1"
  },
  "identity": {
    "product_id": "sales.customer_360",
    "domain": "sales",
    "repository": "github.com/acme/sales-customer-360",
    "namespace_registered": true,
    "registration_timestamp": "2026-01-01T00:00:00Z"
  },
  "mode": "mesh",
  "inheritance_chain": [
    {
      "name": "acme-enterprise",
      "version": "1.0.0",
      "scope": "enterprise",
      "ref": "oci://registry.acme.com/enterprise:v1.0.0"
    },
    {
      "name": "sales-domain",
      "version": "0.1.0",
      "scope": "domain",
      "ref": "oci://registry.acme.com/domains/sales:v2.0.0"
    }
  ],
  "plugins": {
    "compute_registry": {
      "configs": {
        "spark": { "name": "spark", "properties": { "cluster": "spark-thrift.svc" } },
        "duckdb": { "name": "duckdb", "properties": { "threads": 8 } }
      },
      "default": "duckdb"
    },
    "orchestrator": { "type": "dagster" },
    "catalog": { "type": "polaris" },
    "semantic_layer": { "type": "cube" },
    "ingestion": { "type": "dlt" },
    "secrets": { "type": "external-secrets" }
  },
  "transforms": [
    { "type": "dbt", "path": "./models/ingest", "models": [...], "compute": "spark" },
    { "type": "dbt", "path": "./models/marts", "models": [...], "compute": "duckdb" }
  ],
  "governance": {...},
  "observability": {
    "traces": true,
    "metrics": true,
    "lineage": true,
    "namespace": "sales.customer-360"
  },
  "output_ports": [
    {
      "name": "customers",
      "description": "Unified customer dimension",
      "table": "sales.gold.customers",
      "sla": {
        "freshness": "6h",
        "availability": "99.9%"
      },
      "access": {
        "default": "deny",
        "grants": [
          { "domain": "marketing", "access": "read" },
          { "domain": "finance", "access": "read" }
        ]
      }
    }
  ],
  "input_ports": [
    {
      "name": "crm_data",
      "source": {
        "type": "ingestion",
        "config": { "type": "dlt", "source": "salesforce" }
      }
    },
    {
      "name": "marketing_interactions",
      "source": {
        "type": "data_product",
        "ref": "marketing.campaign-attribution.customer_interactions"
      },
      "freshness_requirement": "4h"
    }
  ],
  "data_contracts": [
    {
      "api_version": "v3.0.2",
      "kind": "DataContract",
      "name": "sales-customer-360-customers",
      "version": "2.1.0",
      "owner": "sales-analytics@acme.com",
      "domain": "sales",
      "description": "Unified customer dimension from customer-360 data product",
      "status": "active",
      "models": [
        {
          "name": "customers",
          "description": "Customer master data",
          "primary_key": ["customer_id"],
          "elements": [
            {
              "name": "customer_id",
              "type": "string",
              "required": true,
              "primary_key": true,
              "unique": true,
              "description": "Unique customer identifier"
            },
            {
              "name": "email",
              "type": "string",
              "required": true,
              "unique": true,
              "classification": "pii",
              "format": "email",
              "description": "Primary email address"
            },
            {
              "name": "name",
              "type": "string",
              "required": true,
              "classification": "pii",
              "description": "Full name"
            },
            {
              "name": "lifetime_value",
              "type": "decimal",
              "required": false,
              "description": "Calculated customer lifetime value"
            }
          ]
        }
      ],
      "sla": {
        "freshness_hours": 6.0,
        "availability_percent": 99.9,
        "quality_score_min": 95.0,
        "completeness_percent": 99.0
      },
      "terms": {
        "usage": "Internal analytics only",
        "retention": "7 years per compliance"
      },
      "tags": ["customer-data", "gold-layer", "sales-domain"],
      "source": {
        "type": "merged",
        "file_path": "data-products/customer-360/datacontract.yaml",
        "port_name": "customers"
      },
      "generated_at": "2026-01-03T10:00:00Z",
      "generated_from": "merged"
    }
  ]
}
```

## Validation

### Python

```python
from floe_core.schemas import CompiledArtifacts

# Load and validate
with open(".floe/artifacts.json") as f:
    artifacts = CompiledArtifacts.model_validate_json(f.read())

# Access configuration
print(artifacts.mode)  # "simple" | "centralized" | "mesh"
print(artifacts.plugins.compute.type)  # "duckdb"
print(artifacts.plugins.orchestrator.type)  # "dagster"

# Check inheritance
for manifest in artifacts.inheritance_chain:
    print(f"{manifest.name} ({manifest.scope}): {manifest.ref}")
```

### JSON Schema Export

```bash
floe schema export --output compiled-artifacts.schema.json
```

## Versioning

| Change | Version Impact |
|--------|----------------|
| Add optional field | Minor (1.x.0) |
| Add required field | Major (x.0.0) |
| Remove field | Major (x.0.0) |
| Change field type | Major (x.0.0) |

## Related Documents

- [Contracts Index](./index.md) - Overview of all contracts
- [Observability Attributes](./observability-attributes.md) - Telemetry conventions
- [datacontract.yaml Reference](./datacontract-yaml-reference.md) - ODCS format reference
- [Glossary](./glossary.md) - Terminology
- [Four-Layer Overview](../architecture/four-layer-overview.md) - Architecture context
- [ADR-0026: Data Contract Architecture](../architecture/adr/0026-data-contract-architecture.md)
- [ADR-0027: ODCS Standard Adoption](../architecture/adr/0027-odcs-standard-adoption.md)
- [ADR-0028: Runtime Contract Monitoring](../architecture/adr/0028-runtime-contract-monitoring.md)
- [ADR-0030: Namespace-Based Identity](../architecture/adr/0030-namespace-identity.md)

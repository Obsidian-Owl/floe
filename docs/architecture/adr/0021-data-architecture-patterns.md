# ADR-0021: Data Architecture Patterns

## Status

Accepted

## Context

Data platforms use different architectural patterns for organizing data:

**Data Modeling Patterns:**
1. **Medallion Architecture** (Bronze/Silver/Gold) - Popularized by Databricks
2. **Kimball Dimensional** (Facts/Dimensions) - Classic data warehousing
3. **Data Vault** (Hubs/Links/Satellites) - Enterprise scalability
4. **Hybrid** - Combination of patterns

**Organizational Patterns:**
5. **Data Mesh** - Federated, domain-oriented data ownership

floe needs to support these patterns while enforcing consistency within each pattern through naming conventions and quality gates.

**Key Distinction:** Data Mesh is an *organizational* pattern that defines HOW teams own data, while medallion/kimball/data_vault are *modeling* patterns that define HOW data is structured. A Data Mesh organization can use any modeling pattern within each domain.

## Decision

Support multiple data architecture patterns via `platform-manifest.yaml`, with **medallion** as the default. Additionally, support **Data Mesh** as an organizational pattern that can be layered on top of any modeling pattern.

### Supported Patterns

**Data Modeling Patterns:**

| Pattern | Default Naming | Layers/Components | Use Case |
|---------|---------------|-------------------|----------|
| **medallion** | `bronze_*`, `silver_*`, `gold_*` | Bronze, Silver, Gold | General purpose, modern data lakehouse |
| **kimball** | `dim_*`, `fact_*`, `stg_*` | Staging, Facts, Dimensions | Business intelligence, reporting |
| **data_vault** | `hub_*`, `link_*`, `sat_*` | Hubs, Links, Satellites | Enterprise, audit-heavy |
| **hybrid** | Custom per layer | Configurable | Complex requirements |

**Organizational Patterns:**

| Pattern | Configuration | Key Resources | Use Case |
|---------|--------------|---------------|----------|
| **centralized** | `Manifest` (scope: enterprise) + `DataProduct` | DataProduct | Traditional centralized data team |
| **data_mesh** | `Manifest` chain (enterprise → domain) + `DataProduct` | DataProduct, DataContract | Federated domain ownership |

### Default: Medallion Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  GOLD LAYER (Business-Ready)                                             │
│  Prefix: gold_*                                                          │
│  Purpose: Aggregated, business-specific views                           │
│  Quality: Maximum (100% coverage, documentation required)               │
│                                                                          │
│  Examples: gold_revenue_by_region, gold_customer_lifetime_value         │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ Aggregates, joins
┌─────────────────────────────────────────────────────────────────────────┐
│  SILVER LAYER (Cleaned, Conformed)                                       │
│  Prefix: silver_*                                                        │
│  Purpose: Cleaned, deduplicated, standardized data                      │
│  Quality: High (80% coverage, freshness checks)                         │
│                                                                          │
│  Examples: silver_customers, silver_orders, silver_products             │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ Cleans, deduplicates
┌─────────────────────────────────────────────────────────────────────────┐
│  BRONZE LAYER (Raw)                                                      │
│  Prefix: bronze_*                                                        │
│  Purpose: Raw ingested data, minimal transformation                     │
│  Quality: Basic (primary key not null)                                  │
│                                                                          │
│  Examples: bronze_salesforce_accounts, bronze_stripe_payments           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Consequences

### Positive

- **Consistency** - All models follow the same pattern
- **Discoverability** - Naming conventions make models easy to find
- **Quality alignment** - Quality gates match layer expectations
- **Flexibility** - Organizations can choose their preferred pattern

### Negative

- **Migration effort** - Existing projects may need renaming
- **Learning curve** - Teams must understand chosen pattern
- **Enforcement overhead** - Compile-time validation adds steps

### Neutral

- Pattern choice is made once at platform level
- Data engineers work within the chosen pattern
- Pattern can be changed (with migration)

## Configuration

### Platform Manifest

```yaml
# platform-manifest.yaml
data_architecture:
  pattern: medallion  # medallion | kimball | data_vault | hybrid

  # Medallion configuration
  layers:
    bronze:
      prefix: "bronze_"
      description: "Raw ingested data, minimal transformation"
      quality_gates:
        required_tests: [not_null_pk]
        minimum_coverage: 50
      catalog_namespace: bronze

    silver:
      prefix: "silver_"
      description: "Cleaned, conformed, deduplicated data"
      quality_gates:
        required_tests: [not_null_pk, unique_pk, freshness]
        minimum_coverage: 80
      catalog_namespace: silver

    gold:
      prefix: "gold_"
      description: "Business-ready aggregates and metrics"
      quality_gates:
        required_tests: [not_null_pk, unique_pk, freshness, documentation]
        minimum_coverage: 100
      catalog_namespace: gold

  naming:
    enforcement: strict  # off | warn | strict
    case: snake_case     # snake_case | camelCase | PascalCase
```

### Kimball Pattern

```yaml
data_architecture:
  pattern: kimball

  layers:
    staging:
      prefix: "stg_"
      description: "Staging area for raw data"
      quality_gates:
        required_tests: [not_null_pk]
        minimum_coverage: 50

    dimensions:
      prefix: "dim_"
      description: "Dimension tables (slowly changing)"
      quality_gates:
        required_tests: [not_null_pk, unique_pk, scd_validation]
        minimum_coverage: 100
      scd:
        types_allowed: [1, 2]  # Type 1: Overwrite, Type 2: Add Row
        default_type: 2

    facts:
      prefix: "fact_"
      description: "Fact tables (transactional)"
      quality_gates:
        required_tests: [not_null_pk, referential_integrity]
        minimum_coverage: 100
```

#### Slowly Changing Dimensions (SCD)

Dimension tables require SCD handling for attributes that change over time:

| SCD Type | Behavior | Use Case |
|----------|----------|----------|
| **Type 1** | Overwrite current value, no history | Current value only needed |
| **Type 2** | Add new row with effective dates | Full audit trail required |

**Type 2 Schema Requirements:**

| Column | Type | Description |
|--------|------|-------------|
| `surrogate_key` | STRING | Unique per version (facts reference this) |
| `{business_key}` | * | Natural business identifier |
| `effective_from` | TIMESTAMP | When this version became active |
| `effective_to` | TIMESTAMP | When expired (9999-12-31 for current) |
| `is_current` | BOOLEAN | Flag for current record |

**dbt Snapshot Integration:**

```sql
-- snapshots/snap_customer.sql
{% snapshot snap_customer %}
{{
    config(
      unique_key='customer_id',
      strategy='check',
      check_cols=['email', 'address', 'status']
    )
}}
SELECT * FROM {{ source('raw', 'customers') }}
{% endsnapshot %}
```

**Fact Table Joins:**

```sql
-- Fact tables join to dimension at point-in-time
SELECT f.*, d.*
FROM fact_orders f
JOIN dim_customer d
  ON f.customer_id = d.customer_id
  AND f.order_date >= d.effective_from
  AND f.order_date < d.effective_to
```

See [SCD Patterns Guide](../../guides/scd-patterns.md) for complete implementation examples.

### Data Vault Pattern

```yaml
data_architecture:
  pattern: data_vault

  layers:
    hubs:
      prefix: "hub_"
      description: "Business keys"
      quality_gates:
        required_tests: [unique_business_key, hash_key]
        minimum_coverage: 100

    links:
      prefix: "link_"
      description: "Relationships between hubs"
      quality_gates:
        required_tests: [referential_integrity]
        minimum_coverage: 100

    satellites:
      prefix: "sat_"
      description: "Descriptive attributes"
      quality_gates:
        required_tests: [load_date, record_source]
        minimum_coverage: 100
```

## Compile-Time Enforcement

```bash
$ floe compile

[1/4] Loading platform artifacts
      ✓ Pattern: medallion
      ✓ Enforcement: strict

[2/4] Validating naming conventions
      ✓ bronze_salesforce_accounts: valid (bronze layer)
      ✓ silver_customers: valid (silver layer)
      ✗ ERROR: 'stg_orders' violates naming convention
              Expected: bronze_*, silver_*, or gold_* prefix
              Model appears to be staging data → use bronze_orders

[3/4] Validating quality gates
      ✓ bronze layer: all models have not_null_pk test
      ✗ ERROR: silver_customers missing freshness test
              Required for silver layer: [not_null_pk, unique_pk, freshness]

[4/4] Compilation FAILED

Fix naming and quality violations, then re-run `floe compile`
```

## Pattern Migration

When changing patterns, a migration is required:

```bash
# 1. Update platform-manifest.yaml
data_architecture:
  pattern: kimball  # Changed from medallion

# 2. Run migration analysis
floe migrate analyze
# Output:
#   bronze_customers → stg_customers
#   silver_customers → dim_customer
#   gold_revenue → fact_revenue
#   35 models require renaming

# 3. Generate migration script
floe migrate generate --output=migrate.sql

# 4. Review and apply
floe migrate apply --dry-run
floe migrate apply
```

## dbt Integration

Naming conventions are validated against dbt models:

```yaml
# models/bronze/bronze_salesforce_accounts.yml
version: 2

models:
  - name: bronze_salesforce_accounts
    description: "Raw Salesforce account data"
    meta:
      floe:
        layer: bronze  # Optional: explicit layer declaration
    columns:
      - name: id
        tests:
          - not_null  # Required for bronze layer
```

## Layer-to-Namespace Mapping

Each layer maps to a catalog namespace:

| Layer | Namespace | Access |
|-------|-----------|--------|
| bronze | `bronze` | Data Engineers: READ_WRITE |
| silver | `silver` | Data Engineers: READ_WRITE, Analysts: READ |
| gold | `gold` | Analysts: READ, BI Tools: READ |

```yaml
# platform-manifest.yaml
catalog_structure:
  namespaces:
    - name: bronze
      grants:
        - role: data_engineers
          access: READ_WRITE
    - name: silver
      grants:
        - role: data_engineers
          access: READ_WRITE
        - role: analysts
          access: READ
    - name: gold
      grants:
        - role: analysts
          access: READ
        - role: bi_tools
          access: READ
```

---

## Data Mesh: Federated Domain Architecture

Data Mesh is an organizational architecture for analytical data that applies product thinking and domain-driven design principles. It fundamentally changes HOW data is owned and operated.

### Four Principles of Data Mesh

| Principle | Description | floe Support |
|-----------|-------------|---------------------|
| **Domain Ownership** | Domains own their data end-to-end | Domain-level platform manifests |
| **Data as a Product** | Data has clear owners, SLAs, contracts | DataProduct resource type |
| **Self-Serve Platform** | Platform enables domain autonomy | floe IS the platform |
| **Federated Governance** | Governance is automated, federated | Three-tier config inheritance |

### Three-Tier Configuration Hierarchy

Data Mesh uses floe's unified `Manifest` type with inheritance via `parent:` reference:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 1: ENTERPRISE MANIFEST                                                 │
│  Owner: Platform Team (Central)                                             │
│  Config: kind: Manifest, scope: enterprise                                  │
│  Published: oci://registry/enterprise-platform:v1.0                         │
│                                                                              │
│  Defines:                                                                    │
│  • Global governance policies (PII handling, retention)                    │
│  • Approved plugin list (which computes, catalogs are allowed)             │
│  • Minimum quality standards (all domains must meet)                       │
│  • Cross-domain interoperability rules                                     │
│  • Enterprise-wide data classification scheme                              │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ inherits via parent:
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 2: DOMAIN MANIFESTS                                                    │
│  Owner: Domain Platform Team (per domain)                                   │
│  Config: kind: Manifest, scope: domain, parent: ref to enterprise          │
│  Published: oci://registry/domains/{domain}-platform:v1.0                   │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │     SALES       │  │   MARKETING     │  │    FINANCE      │             │
│  │     DOMAIN      │  │     DOMAIN      │  │     DOMAIN      │             │
│  │                 │  │                 │  │                 │             │
│  │ compute: spark  │  │ compute: duckdb │  │ compute: snowfl │             │
│  │ pattern: medal  │  │ pattern: medal  │  │ pattern: kimball│             │
│  │                 │  │                 │  │                 │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  Each domain can:                                                           │
│  • Choose compute from approved list                                        │
│  • Choose data modeling pattern                                            │
│  • Add domain-specific policies                                            │
│  • Own domain namespace in catalog                                         │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ inherits via domain:
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 3: DATA PRODUCTS                                                       │
│  Owner: Domain Data Product Team                                            │
│  Config: kind: DataProduct, domain: ref to domain manifest                  │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  customer-360   │  │ campaign-perf   │  │ revenue-metrics │             │
│  │  (Sales)        │  │ (Marketing)     │  │ (Finance)       │             │
│  │                 │  │                 │  │                 │             │
│  │ Output ports:   │  │ Output ports:   │  │ Output ports:   │             │
│  │ • customers     │  │ • campaigns     │  │ • revenue       │             │
│  │ • segments      │  │ • attribution   │  │ • forecasts     │             │
│  │                 │  │                 │  │                 │             │
│  │ Input ports:    │  │ Input ports:    │  │ Input ports:    │             │
│  │ • crm_raw       │  │ • ad_platforms  │  │ • sales.orders  │             │
│  │ • support_tix   │  │ • sales.custs   │  │ • billing       │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Enterprise Manifest

The enterprise manifest defines global governance that ALL domains must follow:

```yaml
# enterprise-manifest.yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-enterprise
  version: "1.0.0"
  scope: enterprise

# Approved plugins - domains choose from this list
approved_plugins:
  compute:
    - duckdb      # Allowed for all domains
    - spark       # Allowed for all domains
    - snowflake   # Requires finance approval
  orchestrator:
    - dagster     # Standard
  catalog:
    - polaris     # Enterprise standard
  ingestion:
    - dlt         # Standard
    - airbyte     # Allowed for high-volume

# Global governance - applies to ALL domains
governance:
  classification:
    levels: [public, internal, confidential, pii, phi]
    pii:
      requires_encryption: true
      retention_max_days: 90
      requires_masking_in_non_prod: true

  quality_gates:
    minimum_test_coverage: 70  # All domains must meet this
    required_tests: [not_null_pk, unique_pk]

  interoperability:
    # Cross-domain data sharing rules
    data_contracts:
      required: true
      schema_registry: true
    sla_enforcement: true

# Domain registration
domains:
  - name: sales
    namespace: sales
    owners: [sales-data-team@acme.com]
  - name: marketing
    namespace: marketing
    owners: [marketing-data-team@acme.com]
  - name: finance
    namespace: finance
    owners: [finance-data-team@acme.com]
    # Finance has stricter requirements
    extra_policies:
      audit_logging: required
      compute_approved: [snowflake]  # Finance must use Snowflake
```

### Domain Manifest

Each domain has its own manifest that inherits from enterprise:

```yaml
# domains/sales/domain-manifest.yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: sales-domain
  version: "2.1.0"
  scope: domain

# Inherit from enterprise
parent:
  ref: oci://registry.acme.com/enterprise-platform:v1.0.0

# Domain identity
domain:
  name: sales
  namespace: sales
  owners:
    - team: sales-data-team
      email: sales-data-team@acme.com
      slack: "#sales-data"

# Domain plugin choices (from approved list)
plugins:
  compute:
    type: spark  # Sales chose Spark for their volume
  # Inherits: orchestrator, catalog, ingestion from enterprise

# Domain data architecture
data_architecture:
  pattern: medallion  # Sales uses medallion
  layers:
    bronze:
      prefix: "sales_bronze_"
      catalog_namespace: sales.bronze
    silver:
      prefix: "sales_silver_"
      catalog_namespace: sales.silver
    gold:
      prefix: "sales_gold_"
      catalog_namespace: sales.gold

# Domain-specific policies (additive to enterprise)
governance:
  quality_gates:
    minimum_test_coverage: 80  # Stricter than enterprise minimum of 70
    gold_layer:
      minimum_coverage: 100
      required_documentation: true

# Domain services (optional overrides)
services:
  compute:
    spark:
      executors:
        instances: 10  # Sales needs more Spark capacity
        memory: 8Gi
```

### Data Product Manifest

Data Products are the unit of deployment in Data Mesh:

```yaml
# domains/sales/products/customer-360/data-product.yaml
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-360
  version: "3.2.1"
  description: "Unified view of customer across all touchpoints"

# Inherit from domain
domain:
  ref: oci://registry.acme.com/domains/sales-platform:v2.1.0

# Product ownership
ownership:
  team: sales-analytics
  email: sales-analytics@acme.com
  slack: "#customer-360-support"

# Output ports - what this product exposes to consumers
output_ports:
  - name: customers
    description: "Unified customer dimension"
    table: sales.gold.customers
    schema:
      ref: schemas/customers.json
    sla:
      freshness: 6h          # Updated within 6 hours
      availability: 99.9%    # Uptime SLA
      quality:
        completeness: 99%
        accuracy: 98%
    access:
      default: deny
      grants:
        - domain: marketing
          access: read
        - domain: finance
          access: read
        - role: analysts
          access: read

  - name: customer_segments
    description: "Customer segmentation for targeting"
    table: sales.gold.customer_segments
    sla:
      freshness: 24h
      availability: 99%

# Input ports - dependencies on other products/sources
input_ports:
  - name: crm_data
    description: "Raw CRM data from Salesforce"
    source:
      type: ingestion
      config:
        type: dlt
        source: salesforce
    freshness_requirement: 1h

  - name: support_tickets
    description: "Support ticket data from Zendesk"
    source:
      type: ingestion
      config:
        type: dlt
        source: zendesk

  - name: marketing_interactions
    description: "Customer interactions from Marketing domain"
    source:
      type: data_product
      ref: marketing.campaign-attribution.customer_interactions
    # Creates a dependency contract

# Transforms (dbt models within this product)
transforms:
  - type: dbt
    path: models/

# Schedule
schedule:
  cron: "0 */6 * * *"  # Every 6 hours to meet SLA
```

### Cross-Domain Data Contracts

When data products depend on each other, contracts are established:

```yaml
# Automatically generated when marketing.campaign-attribution
# is declared as an input port for sales.customer-360

apiVersion: floe.dev/v1
kind: DataContract
metadata:
  name: marketing-to-sales-customer-interactions
  version: "1.0.0"

provider:
  domain: marketing
  product: campaign-attribution
  port: customer_interactions

consumer:
  domain: sales
  product: customer-360

schema:
  columns:
    - name: customer_id
      type: string
      required: true
    - name: interaction_type
      type: string
      enum: [email_open, email_click, ad_impression, ad_click]
    - name: interaction_timestamp
      type: timestamp
      required: true
    - name: campaign_id
      type: string

sla:
  freshness: 2h
  availability: 99%

# Contract validation at compile time
validation:
  schema_compatibility: backward  # Provider can add columns, not remove
  breaking_change_notification: 7d  # 7 day notice for breaking changes
```

### Catalog Structure in Data Mesh

The catalog organizes data by domain:

```
catalog/
├── enterprise/                    # Shared enterprise data
│   └── reference_data/
│       ├── countries
│       ├── currencies
│       └── fiscal_calendar
│
├── sales/                         # Sales domain
│   ├── bronze/
│   │   ├── salesforce_accounts
│   │   └── salesforce_opportunities
│   ├── silver/
│   │   ├── accounts
│   │   └── opportunities
│   └── gold/
│       ├── customers              # Output port: customer-360.customers
│       └── customer_segments      # Output port: customer-360.segments
│
├── marketing/                     # Marketing domain
│   ├── bronze/
│   ├── silver/
│   └── gold/
│       └── customer_interactions  # Output port consumed by sales
│
└── finance/                       # Finance domain
    ├── staging/                   # Kimball pattern
    ├── dimensions/
    └── facts/
```

### Data Mesh Discovery

Data products are discoverable via the catalog:

```bash
# List all data products
floe products list

# Output:
DOMAIN      PRODUCT              VERSION   OWNER               OUTPUT PORTS
sales       customer-360         3.2.1     sales-analytics     customers, customer_segments
sales       opportunity-pipeline 2.0.0     sales-ops           pipeline_stages, forecasts
marketing   campaign-attribution 1.5.0     marketing-analytics customer_interactions, attribution
finance     revenue-metrics      4.1.0     finance-analytics   revenue, forecasts

# View product details
floe products describe sales.customer-360

# Output:
Product: customer-360
Domain: sales
Version: 3.2.1
Owner: sales-analytics@acme.com

Output Ports:
  customers (sales.gold.customers)
    SLA: freshness=6h, availability=99.9%
    Consumers: marketing.campaign-attribution, finance.revenue-metrics

  customer_segments (sales.gold.customer_segments)
    SLA: freshness=24h, availability=99%
    Consumers: marketing.targeting-engine

Input Ports:
  crm_data (ingestion: salesforce)
  support_tickets (ingestion: zendesk)
  marketing_interactions (marketing.campaign-attribution.customer_interactions)
```

### Federated Governance Enforcement

```bash
$ floe compile

[1/6] Loading enterprise platform
      ✓ Enterprise: acme-enterprise v1.0.0
      ✓ Global policies loaded

[2/6] Loading domain platform
      ✓ Domain: sales v2.1.0
      ✓ Domain policies loaded (merged with enterprise)

[3/6] Validating data product
      ✓ Product: customer-360 v3.2.1
      ✓ Ownership: sales-analytics@acme.com

[4/6] Validating data contracts
      ✓ Input: marketing.campaign-attribution.customer_interactions
        ✓ Schema compatibility: OK
        ✓ SLA: provider=2h, required=4h: OK
      ✗ ERROR: Input port 'finance.revenue.invoices' not found
              The finance domain does not expose this port

[5/6] Validating governance
      ✓ PII columns: encrypted ✓, masked in non-prod ✓
      ✓ Quality gates: coverage=92% (min=80%) ✓
      ✓ Domain namespace: sales.* ✓

[6/6] Compilation FAILED

Fix data contract violation and re-run `floe compile`
```

### Data Mesh + Data Modeling Patterns

Each domain can choose its own data modeling pattern:

| Domain | Modeling Pattern | Rationale |
|--------|------------------|-----------|
| Sales | Medallion | High volume, streaming updates |
| Marketing | Medallion | Event-driven, time-series heavy |
| Finance | Kimball | BI-centric, regulatory reporting |
| Risk | Data Vault | Audit requirements, historical tracking |

This is configured per domain:

```yaml
# sales uses medallion
data_architecture:
  pattern: medallion

# finance uses kimball
data_architecture:
  pattern: kimball
```

### Data Mesh Infrastructure Topology

In Data Mesh, domains can have their own infrastructure:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SHARED PLATFORM SERVICES                                                    │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Polaris   │  │    OTLP     │  │  Prometheus │  │   Grafana   │        │
│  │  (Catalog)  │  │  Collector  │  │  (Metrics)  │  │ (Dashboards)│        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                              │
│  Shared by all domains - managed by Platform Team                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  DOMAIN-SPECIFIC SERVICES                                                    │
│                                                                              │
│  ┌───────────────────────┐  ┌───────────────────────┐                      │
│  │     SALES DOMAIN      │  │    FINANCE DOMAIN     │                      │
│  │                       │  │                       │                      │
│  │  ┌─────────────────┐  │  │  ┌─────────────────┐  │                      │
│  │  │ Dagster (sales) │  │  │  │Dagster (finance)│  │                      │
│  │  └─────────────────┘  │  │  └─────────────────┘  │                      │
│  │  ┌─────────────────┐  │  │  ┌─────────────────┐  │                      │
│  │  │ Spark Cluster   │  │  │  │ Snowflake Conn  │  │                      │
│  │  │ (self-hosted)   │  │  │  │ (cloud managed) │  │                      │
│  │  └─────────────────┘  │  │  └─────────────────┘  │                      │
│  │  ┌─────────────────┐  │  │  ┌─────────────────┐  │                      │
│  │  │ Cube (sales)    │  │  │  │ Cube (finance)  │  │                      │
│  │  └─────────────────┘  │  │  └─────────────────┘  │                      │
│  │                       │  │                       │                      │
│  │  Namespace: sales     │  │  Namespace: finance   │                      │
│  │  Compute: Spark       │  │  Compute: Snowflake   │                      │
│  │  Owner: sales-team    │  │  Owner: finance-team  │                      │
│  └───────────────────────┘  └───────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### CLI Commands for Data Mesh

```bash
# Platform commands (Platform Team)
floe platform compile              # Compile any Manifest (enterprise or domain)
floe platform publish v1.0.0       # Publish to OCI registry
floe platform deploy               # Deploy platform services

# Data Product commands (Product Team)
floe init --platform=v1.0.0        # Initialize with centralized manifest
floe init --domain=sales:v2.1.0    # Initialize with domain manifest
floe compile                       # Compile DataProduct
floe run                           # Execute pipeline

# Discovery commands
floe products list
floe products describe sales.customer-360
floe contracts list
floe contracts describe marketing-to-sales-customer-interactions
```

---

## References

- [Medallion Architecture (Databricks)](https://www.databricks.com/glossary/medallion-architecture)
- [Kimball Dimensional Modeling](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/)
- [Data Vault 2.0](https://datavaultalliance.com/)
- [Data Mesh (Zhamak Dehghani)](https://www.datamesh-architecture.com/)
- [Data Mesh Principles](https://martinfowler.com/articles/data-mesh-principles.html)
- [ADR-0012: Data Classification Governance](0012-data-classification-governance.md) - Quality gates
- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md) - Compile-time enforcement

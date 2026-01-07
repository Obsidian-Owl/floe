# ADR-0012: Data Classification and Governance Architecture

## Status

Accepted

## Context

Floe needs a coherent approach to data classification, access control, and governance that spans multiple layers:

1. **Data Classification** - Identifying sensitive data (PII, PHI, financial, etc.)
2. **Storage Access Control** - Who can read/write tables (Polaris RBAC)
3. **Query Access Control** - Row-level security, column masking (Cube)
4. **API Access Control** - Endpoint authentication (Cube APIs)

### The Challenge

Security operates at multiple layers with different responsibilities:

| Layer | Technology | Capability |
|-------|------------|------------|
| Metadata | dbt meta tags | Classification definition |
| Lineage | OpenLineage facets | Classification propagation |
| Storage | Polaris RBAC | Table/namespace access |
| Compute | Iceberg (via engines) | Row/column filtering (engine-dependent) |
| Consumption | Cube queryRewrite | Row-level security, column masking |

### Key Questions

1. Where should classification metadata live?
2. How should it propagate through the pipeline?
3. How is enforcement handled at compile time vs runtime?

## Decision

### 1. Classification Source of Truth: dbt meta tags

Data classification is defined in **dbt model YAML** using a `floe:` namespace in the `meta` field:

```yaml
# models/staging/stg_customers.yml
models:
  - name: stg_customers
    columns:
      - name: email
        meta:
          floe:
            classification: pii
            pii_type: email
            sensitivity: high

      - name: revenue
        meta:
          floe:
            classification: financial
            sensitivity: medium
```

**Rationale:**
- dbt is already the source of truth for data models
- `meta` field is designed for exactly this purpose
- Classification travels with the model definition
- No separate governance file to maintain

### 2. FloeSpec Governance Section: Policy Definition

`floe.yaml` defines **policies** for how to handle classified data:

```yaml
governance:
  classification:
    source: dbt_meta  # Where to read classifications from

  policies:
    pii:
      production:
        action: restrict  # Cube RLS enforces access
      non_production:
        action: synthesize  # Generate synthetic data

    high_sensitivity:
      production:
        action: restrict
        requires_role: [data_owner, compliance]
      non_production:
        action: redact
```

**Environment Type Mapping:**

The system supports 4 environment types (`development`, `preview`, `staging`, `production`) but governance policies use a binary classification for simplicity:

| Environment Type | Governance Category | Rationale |
|------------------|--------------------|-----------|
| `development` | `non_production` | Local development, ephemeral |
| `preview` | `non_production` | PR environments, ephemeral |
| `staging` | `non_production` | Pre-production testing, production-like controls but should not contain unmanaged sensitive data |
| `production` | `production` | Live customer data, full restrictions apply |

> **Note:** While `staging` is production-like in terms of infrastructure and access controls, it is classified as `non_production` for data governance purposes. This means staging environments should use synthetic data or sanitized datasets rather than copies of production data. This reduces exfiltration risk and simplifies compliance.

**Rationale:**
- Policies are project-level concerns (belong in floe.yaml)
- Separates "what is sensitive" (dbt meta) from "what to do about it" (policies)
- Enables different behaviors per environment
- Binary production/non_production split simplifies policy configuration while covering the common case

### 3. Classification Propagation: OpenLineage Facets

Classifications flow through the pipeline via **OpenLineage custom facets**:

```python
class FloeClassificationFacet(BaseFacet):
    """Custom OpenLineage facet for data classification."""
    _schemaURL = "https://floe.dev/spec/facets/ClassificationFacet.json"

    columns: dict[str, ColumnClassification]

@dataclass
class ColumnClassification:
    classification: str  # pii, financial, identifier, public
    pii_type: str | None  # email, phone, ssn, address, name
    sensitivity: str  # low, medium, high, critical
```

**Rationale:**
- OpenLineage is already used for lineage tracking
- Custom facets are the standard extension mechanism
- Enables downstream consumers (Marquez, DataHub) to visualize classifications
- Classification propagates automatically with lineage

### 4. Enforcement at Compile Time and Runtime

| Capability | Compile Time | Runtime |
|------------|--------------|---------|
| **Classification Validation** | Check dbt meta tags exist | N/A |
| **Policy Compliance** | Validate policies against classification | N/A |
| **Storage RBAC (Polaris)** | Validate namespace configuration | Enforce table access |
| **Query RLS (Cube)** | Validate security rules | Enforce row-level security |
| **Column Masking** | Validate masking configuration | Apply masking in queries |

## Consequences

### Positive

- **Single source of truth** - Classification lives with the data model in dbt
- **Automatic propagation** - OpenLineage carries classification through pipeline
- **Compile-time validation** - Policies validated before runtime
- **Audit trail** - Lineage + classification = compliance evidence

### Negative

- **Manual configuration** - Users must set up Polaris RBAC and Cube security
- **dbt dependency** - Classification requires dbt meta tags (no alternative for non-dbt transforms)
- **Facet adoption** - Downstream tools must understand Floe's custom facets

### Neutral

- Iceberg itself has no native FGAC - enforcement happens at compute/consumption layer
- Polaris RBAC provides table-level access but not row/column level
- Row/column security is Cube's responsibility in the Floe stack

## Implementation

### Phase 1: Classification Schema

1. Define `floe:` meta schema for dbt models
2. Add `governance:` section to Manifest/DataProduct
3. Emit FloeClassificationFacet in OpenLineage events
4. Document Cube security configuration

### Phase 2: Policy Enforcement

1. Read classification from dbt manifest
2. Generate Cube security rules from classification + policies
3. Validate policy compliance at compile time

## Classification Schema Reference

### Classification Types

| Type | Description | Example Columns |
|------|-------------|-----------------|
| `pii` | Personally Identifiable Information | email, phone, ssn |
| `phi` | Protected Health Information | diagnosis, prescription |
| `financial` | Financial data | revenue, salary, account_number |
| `identifier` | Business identifiers | customer_id, order_id |
| `public` | Non-sensitive data | product_name, category |

### PII Subtypes

| Subtype | Description | Synthetic Generator |
|---------|-------------|---------------------|
| `email` | Email addresses | Faker.email() |
| `phone` | Phone numbers | Faker.phone_number() |
| `name` | Person names | Faker.name() |
| `address` | Physical addresses | Faker.address() |
| `ssn` | Social Security Numbers | Format-preserving hash |
| `dob` | Date of birth | Age-range preserving |
| `ip_address` | IP addresses | Subnet-preserving |

### Sensitivity Levels

| Level | Description | Default Policy |
|-------|-------------|----------------|
| `low` | Minimal risk if exposed | No restrictions |
| `medium` | Business-sensitive | Role-based access |
| `high` | Regulatory concern | Strict access + audit |
| `critical` | Maximum protection | Explicit approval required |

## Quality Gates

Quality gates integrate with the governance model to enforce data quality at compile time and runtime.

### Quality Gate Configuration

Defined in `manifest.yaml` by Platform Team:

```yaml
governance:
  quality_gates:
    # Minimum requirements for all models
    minimum_test_coverage: 80  # % of columns with tests
    required_tests:
      - not_null        # Primary keys must be not null
      - unique          # Primary keys must be unique
      - freshness       # Source freshness checks

    # Enforcement behavior
    enforcement: strict  # off | warn | strict
    block_on_failure: true

    # Per-layer requirements
    layers:
      bronze:
        required_tests: [not_null_pk]
        minimum_coverage: 50
      silver:
        required_tests: [not_null_pk, unique_pk, freshness]
        minimum_coverage: 80
      gold:
        required_tests: [not_null_pk, unique_pk, freshness, documentation]
        minimum_coverage: 100
```

### Tiered Quality Approach

| Tier | Scope | Implementation | Default |
|------|-------|----------------|---------|
| **Tier 1** | dbt native | dbt tests + dbt-expectations | Always on |
| **Tier 2** | External frameworks | Great Expectations, Soda | Optional |
| **Tier 3** | Quality gates | Block/warn/notify enforcement | Configurable |

### Quality Gate Types

```yaml
# floe.yaml - Quality section
quality:
  # Tier 1: dbt native tests (always run)
  dbt_tests:
    enabled: true
    fail_on_warning: false

  # Tier 3: Quality gates (enforcement)
  gates:
    - name: staging_completeness
      scope:
        tags: [staging]
      checks:
        - type: row_count
          min: 1
        - type: null_percentage
          columns: ["*_id"]
          max: 0
      on_failure: block  # block | warn | notify

    - name: gold_freshness
      scope:
        layer: gold
      checks:
        - type: freshness
          max_age_hours: 24
      on_failure: warn
```

### Enforcement Behavior

| Level | Behavior | Use Case |
|-------|----------|----------|
| `off` | No enforcement | Development/experimentation |
| `warn` | Log warnings, continue | Soft rollout of new rules |
| `strict` | Block pipeline on violation | Production enforcement |

### Quality Integration with Classification

Quality requirements escalate based on data classification:

| Classification | Minimum Coverage | Required Tests | Additional |
|----------------|------------------|----------------|------------|
| `public` | 50% | not_null | - |
| `internal` | 80% | not_null, unique | freshness |
| `confidential` | 100% | all | audit_log |
| `pii` | 100% | all | audit_log, masking_verified |
| `phi` | 100% | all | audit_log, encryption_verified |

### Compile-Time Quality Validation

```bash
$ floe compile

[1/5] Loading platform artifacts
      ✓ Quality gates: 3 rules loaded

[2/5] Analyzing dbt project
      ✓ 24 models, 156 tests

[3/5] Checking test coverage
      ✓ bronze layer: 62% coverage (min: 50%)
      ✓ silver layer: 85% coverage (min: 80%)
      ✗ ERROR: gold layer: 78% coverage (min: 100%)
              Missing tests for: gold_revenue.margin_pct

[4/5] Validating quality gates
      ✗ ERROR: Model 'gold_revenue' missing required tests
              Required: [not_null_pk, unique_pk, freshness, documentation]
              Missing: [documentation]

[5/5] Compilation FAILED

Fix quality violations and re-run `floe compile`
```

## References

- [dbt meta configuration](https://docs.getdbt.com/reference/resource-configs/meta)
- [OpenLineage Custom Facets](https://openlineage.io/docs/spec/facets/)
- [Cube Row-Level Security](https://cube.dev/docs/product/auth/row-level-security)
- [Apache Polaris RBAC](https://polaris.apache.org/releases/1.0.0/)
- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md)

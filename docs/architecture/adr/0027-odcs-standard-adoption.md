# ADR-0027: ODCS Standard Adoption

## Status

Accepted

## Context

With the decision to implement data contracts (ADR-0026), we need to select a contract specification format. Several options exist:

### Options Considered

| Option | Description | Maturity |
|--------|-------------|----------|
| **ODCS** | Open Data Contract Standard (Bitol, Linux Foundation) | Production-ready |
| **dbt Contracts** | Native dbt schema contracts | Limited scope |
| **Soda Contracts** | Soda Core data quality agreements | Data quality focus |
| **Custom Format** | Floe-specific contract YAML | None |

### Evaluation Criteria

1. **Schema definition**: Can it define column types, nullability, constraints?
2. **SLA support**: Can it specify freshness, availability, quality thresholds?
3. **Tooling**: CLI for validation, drift detection, documentation?
4. **Governance**: Ownership, classification, lifecycle fields?
5. **Integration**: Works with our plugin architecture?
6. **Ecosystem**: Community adoption, long-term viability?

### Option Analysis

#### 1. ODCS (Open Data Contract Standard)

The Open Data Contract Standard is a Linux Foundation project (via Bitol) defining a YAML schema for data contracts.

**Strengths:**
- Comprehensive: 11 sections covering schema, SLAs, quality, governance
- Tooling: `datacontract-cli` provides validation, drift detection, documentation generation
- Standard: Linux Foundation backing ensures longevity
- Extensible: Custom properties supported via `additionalProperties`
- Multi-format: Supports multiple data sources (databases, APIs, files)

**Weaknesses:**
- Learning curve: Full spec is substantial
- Dependency: Requires datacontract-cli (Python package)

```yaml
# ODCS v3.1 example
apiVersion: v3.1.0
kind: DataContract
id: customers
version: 1.0.0
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
        primaryKey: true
      - name: email
        logicalType: string
        classification: pii
slaProperties:
  - property: freshness
    value: "PT6H"
    element: updated_at
```

#### 2. dbt Contracts

Native dbt model contracts introduced in dbt 1.5+.

**Strengths:**
- Native to dbt (no additional tools)
- Enforced at build time
- Integrated with dbt testing

**Weaknesses:**
- Schema-only: No SLA, ownership, governance fields
- dbt-coupled: Only for dbt models, not arbitrary data sources
- No runtime monitoring: Compile-time only

```yaml
# dbt contract (schema.yml)
models:
  - name: customers
    config:
      contract:
        enforced: true
    columns:
      - name: id
        data_type: string
        constraints:
          - type: not_null
          - type: primary_key
```

#### 3. Soda Contracts

Soda Core data quality contracts.

**Strengths:**
- Rich quality checks
- Good monitoring integration
- SodaCL language for complex rules

**Weaknesses:**
- Quality-focused: Less emphasis on schema definition
- Soda-specific: Tied to Soda ecosystem
- No governance fields: Missing ownership, classification

```yaml
# Soda contract
dataset: customers
data_source: warehouse
checks:
  - schema:
      fail:
        when required column missing: [id, email]
  - freshness(updated_at) < 6h
  - row_count > 0
```

#### 4. Custom Format

Define a Floe-specific contract YAML format.

**Strengths:**
- Full control over schema
- Tailored to our needs
- No external dependencies

**Weaknesses:**
- No ecosystem: We build and maintain everything
- Reinventing the wheel: Most needs covered by existing standards
- No community: Adoption limited to Floe users

## Decision

Adopt **ODCS v3.x** as the data contract standard for floe.

### Rationale

1. **Complete specification**: ODCS covers all our requirements (schema, SLAs, governance)
2. **Strong tooling**: `datacontract-cli` provides everything we need as a plugin wrapper
3. **Open standard**: Linux Foundation backing via Bitol ensures longevity
4. **Extensibility**: We can add custom facets without forking the spec
5. **Community**: Growing adoption in data engineering community

### Why Not dbt Contracts Alone?

dbt contracts are valuable for compile-time schema enforcement but insufficient for computational governance:

| Capability | dbt Contracts | ODCS |
|------------|---------------|------|
| Schema types | Yes | Yes |
| Nullability | Yes | Yes |
| Primary keys | Yes | Yes |
| Freshness SLA | No | Yes |
| Availability SLA | No | Yes |
| Quality thresholds | No | Yes |
| Ownership | No | Yes |
| Classification (PII/PHI) | No | Yes |
| Terms of use | No | Yes |
| Runtime monitoring | No | Yes (via CLI) |
| Documentation generation | No | Yes |

**Conclusion**: Use dbt contracts for compile-time enforcement AND ODCS for the full contract lifecycle. They are complementary, not competing.

### Integration Strategy

Wrap `datacontract-cli` in the `DataContractPlugin` interface:

```python
# floe_plugins/datacontract/odcs_plugin.py
from datacontract.datacontract import DataContract as DCCli
from datacontract.lint.linter import Linter
from datacontract.export.exporter import Exporter

class ODCSDataContractPlugin(DataContractPlugin):
    """ODCS implementation using datacontract-cli."""

    name = "odcs"
    version = "1.0.0"

    def parse_contract(self, contract_path: Path) -> DataContract:
        dc = DCCli(data_contract_file=str(contract_path))
        # Convert datacontract-cli model to our DataContract
        return self._to_floe_contract(dc)

    def validate_contract(
        self,
        contract: DataContract,
        actual_schema: dict | None = None,
    ) -> ContractValidationResult:
        dc = self._to_cli_contract(contract)
        result = dc.lint()  # Uses built-in linter
        return ContractValidationResult(
            valid=result.passed,
            errors=[str(e) for e in result.errors],
            warnings=[str(w) for w in result.warnings],
        )

    def detect_schema_drift(
        self,
        contract: DataContract,
        data_source_connection: dict,
    ) -> SchemaComparisonResult:
        dc = self._to_cli_contract(contract)
        dc.servers["production"] = data_source_connection
        result = dc.test()  # Test against live data
        # Parse result for schema changes
        return self._parse_drift_result(result)
```

### ODCS v3.1 Schema Overview

ODCS v3.1 contracts use a structured format with the following sections:

```yaml
# Required fields
apiVersion: v3.1.0          # ODCS version (v3.1.0+)
kind: DataContract          # Always "DataContract"
id: customers               # Contract identifier (unique ID)
version: 1.0.0              # Contract version (semantic)
status: active              # Lifecycle: active, deprecated, sunset, retired

# Optional: Identification
name: Customer Master Data  # Human-readable name
domain: sales               # Business domain

# Optional: Ownership (ODCS uses team, not owner at root level)
team:
  - name: data-team@acme.com

# Optional: Description
description:
  purpose: Customer master data for analytics
  usage: Internal analytics only
  limitations: No PII sharing

# Optional: Servers (Data Sources)
servers:
  - environment: production
    type: snowflake
    account: acme.us-east-1

# Optional: Schema (v3.1 uses schema, not models)
# schema is a list of SchemaObject, each with name and properties
schema:
  - name: customers
    description: Customer dimension table
    properties:
      - name: id
        logicalType: string
        primaryKey: true
        required: true
      - name: email
        logicalType: string
        classification: pii

# Optional: Service Level Agreements (v3.1 uses list format)
slaProperties:
  - property: freshness
    value: "PT6H"
    element: updated_at
  - property: availability
    value: "99.9%"

# Optional: Data Quality
dataQuality:
  - type: great_expectations
    specification: expectations.json

# Optional: Tags (list format)
tags:
  - gold-layer
  - customer-data

# Optional: Custom Properties (for extensions)
customProperties:
  - property: retention
    value: "7 years"
```

**Key changes in v3.1:**
- `id` is the primary identifier (not `name`)
- `schema` replaces `models` (list of SchemaObject)
- `slaProperties` is a list of objects with `property` and `value`
- `team` replaces root-level `owner`
- `description` is an object with `purpose`, `usage`, `limitations`

## Consequences

### Positive

1. **Comprehensive standard**: Covers schema, SLAs, governance, quality
2. **CLI tooling**: Validation, testing, documentation out of the box
3. **Interoperability**: Other tools adopting ODCS can consume our contracts
4. **Future-proof**: Linux Foundation project with active development
5. **Plugin abstraction**: `DataContractPlugin` allows swapping implementations

### Negative

1. **External dependency**: Requires `datacontract-cli` package
2. **Version tracking**: Must keep up with ODCS spec evolution
3. **Learning curve**: Full ODCS spec is non-trivial

### Neutral

1. **dbt compatibility**: dbt contracts still used for compile-time, ODCS for runtime
2. **Custom extensions**: May need Floe-specific facets in future

## References

- [ODCS Specification](https://datacontract.com/spec/odcs) - Full specification
- [datacontract-cli](https://github.com/datacontract/datacontract-cli) - Python CLI
- [Bitol](https://bitol.io/) - Linux Foundation project hosting ODCS
- [ADR-0026: Data Contract Architecture](./0026-data-contract-architecture.md)
- [Data Contract Best Practices](https://datacontract.com/docs/best-practices)

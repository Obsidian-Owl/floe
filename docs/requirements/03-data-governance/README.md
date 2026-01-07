# Domain 03: Data Governance

**Priority**: CRITICAL
**Total Requirements**: 50
**Status**: Complete specification

## Overview

This domain defines data governance capabilities that enforce platform policies at compile-time and monitor compliance at runtime. Data governance spans policy enforcement, data contracts, and quality gates—all designed to provide automatic governance through compile-time enforcement.

**Core Architectural Principle**: Compile-Time Enforcement (ADR-0016, ADR-0026, ADR-0027, ADR-0028)
- Non-compliant pipelines fail before runtime
- Platform configuration is immutable and versioned
- Policies defined once, enforced everywhere
- Data contracts enable computational governance

## Governance Framework

### Three-Tier Enforcement Model

```
Enterprise Manifest (Global governance)
    │ Immutable, non-negotiable
    ▼
Domain Manifest (Domain-specific extensions)
    │ Can only strengthen, not weaken
    ▼
Data Product (Pipeline execution)
    │ Inherits all parent constraints
```

**Key Principle**: Policies flow downward only. Lower tiers cannot weaken upper tier constraints.

## Governance Components (3 Major Areas)

| Component | Purpose | Requirements |
|-----------|---------|--------------|
| **Policy Enforcement** | Naming conventions, classification, quality gates | REQ-200 to REQ-220 |
| **Data Contracts** | Schema agreements, SLAs, lifecycle management | REQ-221 to REQ-240 |
| **Quality Gates** | Compile-time quality validation, runtime monitoring | REQ-241 to REQ-250 |

## Architecture Documents

- [ADR-0012: Data Classification and Governance Architecture](../../architecture/adr/0012-data-classification-governance.md) - Classification framework, Cube security
- [ADR-0016: Platform Enforcement Architecture](../../architecture/adr/0016-platform-enforcement-architecture.md) - PolicyEnforcer interface, enforcement levels
- [ADR-0021: Data Architecture Patterns](../../architecture/adr/0021-data-architecture-patterns.md) - Medallion/Kimball patterns, data mesh
- [ADR-0026: Data Contract Architecture](../../architecture/adr/0026-data-contract-architecture.md) - Contract identity, ODCS adoption
- [ADR-0027: ODCS Standard Adoption](../../architecture/adr/0027-odcs-standard-adoption.md) - OpenDataContractStandard v3
- [ADR-0028: Runtime Contract Monitoring](../../architecture/adr/0028-runtime-contract-monitoring.md) - ContractMonitor service
- [ADR-0029: Contract Lifecycle Management](../../architecture/adr/0029-contract-lifecycle-management.md) - Contract versioning, deprecation
- [ADR-0030: Namespace-Based Identity](../../architecture/adr/0030-namespace-identity.md) - Product identity, atomic registration

## Key Architectural Decisions

1. **PolicyEnforcer Interface** (ADR-0016): Platform-agnostic policy validation at compile-time
2. **ODCS v3 Standard** (ADR-0027): Industry-standard data contracts for schema + SLAs
3. **ContractMonitor Service** (ADR-0028): Kubernetes-native runtime contract monitoring
4. **Namespace-Based Identity** (ADR-0030): Atomic product registration to prevent collisions
5. **Three-Tier Inheritance** (ADR-0016, ADR-0026): Policies cannot be weakened by lower tiers

## Configuration Model

### platform-manifest.yaml (Platform Team)

Defines governance policies that ALL data products must follow:

```yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-data-platform
  version: "1.2.3"
  scope: enterprise

governance:
  classification:
    source: dbt_meta  # Classifications in dbt model meta tags

  policies:
    pii:
      production:
        action: restrict  # Cube RLS enforces access
      non_production:
        action: synthesize  # Generate synthetic data

  quality_gates:
    minimum_test_coverage: 80
    required_tests:
      - not_null
      - unique
      - freshness
    enforcement: strict  # off | warn | strict
    block_on_failure: true

  data_contracts:
    enforcement: alert_only  # off | warn | alert_only | block
    standard: odcs_v3
    plugin:
      type: odcs  # datacontract-cli wrapper
    monitoring:
      enabled: true
      freshness:
        check_interval: 15m
      schema_drift:
        check_interval: 1h
```

### floe.yaml (Data Team)

Inherits governance from platform-manifest, defines product-specific policies:

```yaml
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-360
  owner: sales-analytics@acme.com
  domain: sales
  repository: github.com/acme/sales-customer-360

platform:
  ref: oci://registry.acme.com/floe-platform:v1.2.3

transforms:
  - type: dbt
    path: models/

governance:
  classification:
    source: dbt_meta  # Inherited from platform

  policies:
    # Can only strengthen, not weaken platform policies
    high_sensitivity:
      production:
        action: restrict
        requires_role: [data_owner]
```

### datacontract.yaml (Optional, Data Team)

Explicit ODCS v3 data contract for this product:

```yaml
apiVersion: v3.0.2
kind: DataContract
name: sales-customer-360-customers
version: 2.1.0

owner: sales-analytics@acme.com
domain: sales

models:
  customers:
    elements:
      customer_id:
        type: string
        primaryKey: true
      email:
        type: string
        classification: pii

slaProperties:
  freshness:
    value: "PT6H"
    element: updated_at
```

## Requirements Files

- [01-policy-enforcement.md](01-policy-enforcement.md) - REQ-200 to REQ-220: PolicyEnforcer, compile-time validation
- [02-data-contracts.md](02-data-contracts.md) - REQ-221 to REQ-240: Data contract model, ODCS v3, lifecycle
- [03-quality-gates.md](03-quality-gates.md) - REQ-241 to REQ-250: Quality validation, runtime monitoring

## Traceability Matrix

| Requirement Range | ADR | Architecture Doc | Implementation |
|------------------|-----|------------------|-----------------|
| REQ-200 to REQ-220 | ADR-0016, ADR-0012, ADR-0021 | platform-enforcement.md | PolicyEnforcer interface, dbt-checkpoint |
| REQ-221 to REQ-240 | ADR-0026, ADR-0027, ADR-0029, ADR-0030 | data-contracts.md | DataContractPlugin, contract lifecycle |
| REQ-241 to REQ-250 | ADR-0012, ADR-0028 | platform-enforcement.md | Quality gates, ContractMonitor service |

## Plugin Interfaces

### PolicyEnforcer Interface

```python
class PolicyEnforcer(ABC):
    """Validates data products against platform constraints."""

    @abstractmethod
    def validate_data_product(
        self,
        product: DataProduct,
        manifest: Manifest
    ) -> list[ValidationError]:
        """Validate product against all platform policies."""
        pass

    @abstractmethod
    def enforce_naming(
        self,
        model_name: str,
        layer: str
    ) -> ValidationResult:
        """Enforce naming conventions."""
        pass

    @abstractmethod
    def validate_data_contracts(
        self,
        contracts: list[DataContract],
        manifest: Manifest
    ) -> list[ValidationError]:
        """Validate contracts against manifest."""
        pass

    @abstractmethod
    def check_classification_compliance(
        self,
        model: DbtModel
    ) -> list[PolicyViolation]:
        """Check classification handling."""
        pass

    @abstractmethod
    def validate_product_identity(
        self,
        product: DataProduct,
        catalog: CatalogPlugin
    ) -> list[EnforcementViolation]:
        """Validate product namespace (prevents collisions)."""
        pass
```

### DataContractPlugin Interface

```python
class DataContractPlugin(ABC):
    """Validates and monitors data contracts."""

    @abstractmethod
    def parse_contract(self, contract_path: Path) -> DataContract:
        """Parse ODCS contract file."""
        pass

    @abstractmethod
    def generate_contract_from_ports(
        self,
        output_ports,
        input_ports,
        metadata
    ) -> DataContract:
        """Auto-generate contract from product ports."""
        pass

    @abstractmethod
    def validate_contract(
        self,
        contract: DataContract,
        actual_schema=None
    ) -> ContractValidationResult:
        """Validate contract schema."""
        pass

    @abstractmethod
    def detect_schema_drift(
        self,
        contract: DataContract,
        connection
    ) -> SchemaComparisonResult:
        """Detect schema changes at runtime."""
        pass

    @abstractmethod
    def validate_version_bump(
        self,
        old_contract: DataContract,
        new_contract: DataContract
    ) -> tuple[bool, str]:
        """Validate semantic versioning rules."""
        pass
```

## Epic Mapping

This domain's requirements are satisfied across multiple Epics:

- **Epic 6: Governance Foundation** - Core governance infrastructure
  - REQ-200 to REQ-210: PolicyEnforcer interface
  - REQ-211 to REQ-220: Compile-time validation hooks
  - REQ-221 to REQ-230: Data contract model

- **Epic 7: Contract Monitoring** - Runtime enforcement
  - REQ-231 to REQ-240: Contract lifecycle, ODCS v3 adoption
  - REQ-241 to REQ-250: Quality gates, ContractMonitor service

## Validation Criteria

Domain 03 is complete when:

- [ ] All 50 requirements documented with complete template fields
- [ ] PolicyEnforcer ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] DataContractPlugin ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] Compile-time policy validation implemented
- [ ] dbt-checkpoint integration for SQL validation
- [ ] SQLFluff integration for style checking
- [ ] Great Expectations integration for data quality
- [ ] ODCS v3 contract parsing and validation
- [ ] ContractMonitor Kubernetes service deployed
- [ ] Runtime contract monitoring (freshness, schema drift, quality)
- [ ] Contract versioning and lifecycle management
- [ ] Product identity validation with atomic registration
- [ ] Contract tests validate cross-package governance
- [ ] ADRs backreference requirements
- [ ] Architecture docs backreference requirements
- [ ] Test coverage > 80% for governance infrastructure

## Notes

- **Backward Compatibility**: NONE - Governance is new capability
- **Breaking Changes**: NONE - Additive feature
- **Migration Risk**: LOW - Well-defined interfaces, extensive validation
- **Compliance Alignment**: GDPR, HIPAA, SOC 2 ready via classification + monitoring
- **Data Mesh Ready**: Three-tier inheritance model supports federated governance

## Related Domains

- **Domain 01: Plugin Architecture** - PolicyEnforcer and DataContractPlugin are pluggable
- **Domain 02: Configuration and Compilation** - Manifest parsing, compilation hooks
- **Domain 04: Artifact Distribution** - OCI artifact signing for policy immutability
- **Domain 05: Orchestration** - ContractMonitor deployed as K8s service
- **Domain 06: Observability** - OpenLineage events for governance audit trail

## Key Definitions

- **Policy**: Platform-defined constraint (naming, classification, quality gates)
- **Enforcement Level**: How policies are enforced (off, warn, strict)
- **Data Contract**: Formal agreement between producer and consumer (ODCS format)
- **Contract Violation**: Runtime breach of contract SLA or schema
- **Classification**: Data sensitivity level (public, internal, confidential, pii, phi)
- **Quality Gate**: Compile-time check that blocks non-compliant pipelines
- **PolicyEnforcer**: Interface for policy validation at compile-time
- **ContractMonitor**: Service that monitors contracts at runtime
- **Namespace**: Product identity in catalog (domain.product)

## Enforcement Levels

| Level | Behavior | Use Case |
|-------|----------|----------|
| `off` | No enforcement | Experimentation, non-production |
| `warn` | Log warnings, continue | Gradual adoption, soft rollout |
| `strict` | Block on violation | Production, hard enforcement |
| `alert_only` | Emit alerts, continue | Contract monitoring without blocking |
| `block` | Halt execution | Critical SLA violations |

## Success Metrics

- 100% of production pipelines pass compile-time governance checks
- 0 unclassified sensitive data columns in production
- <5% SLA violations on monitored contracts
- <1% schema drift incidents
- 100% audit trail coverage via OpenLineage

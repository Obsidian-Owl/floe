# ADR-0029: Contract Lifecycle Management

## Status

Accepted

## Context

Data contracts must evolve independently from the data products they describe. A contract may need updates for:

1. **Schema changes**: New columns, type changes, removed fields
2. **SLA adjustments**: Changing freshness requirements, availability targets
3. **Ownership transfers**: Team changes, domain reorganizations
4. **Deprecation**: Sunsetting data products with consumer migration

Without clear lifecycle rules, contracts become stale or consumers break unexpectedly.

### Questions to Answer

1. How do contracts version independently from data products?
2. What constitutes a breaking change?
3. How are consumers notified of changes?
4. What is the deprecation workflow?
5. How do we prevent race conditions in Data Mesh scenarios?

## Decision

Implement **decoupled contract lifecycle** with semantic versioning and breaking change detection.

### Core Principles

1. **Independent versioning**: Contract `version` is separate from data product version
2. **Semantic versioning**: Major.Minor.Patch with clear breaking change rules
3. **Producer-driven**: Data producers own and version their contracts
4. **Consumer notification**: Breaking changes require explicit notification period
5. **Compile-time detection**: Breaking changes flagged before runtime

### Semantic Versioning Rules

```
MAJOR.MINOR.PATCH

MAJOR: Breaking changes (consumers must update)
MINOR: Backward-compatible additions
PATCH: Metadata, documentation, fixes
```

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| Remove column | MAJOR | `email` field deleted |
| Change column type | MAJOR | `id: int` → `id: string` |
| Make nullable column required | MAJOR | `phone: optional` → `phone: required` |
| Add new required column | MAJOR | New `ssn` field with `required: true` |
| Add optional column | MINOR | New `middle_name` with `required: false` |
| Relax nullability | MINOR | `phone: required` → `phone: optional` |
| Change description | PATCH | Updated column documentation |
| Change classification | PATCH | `pii: false` → `pii: true` |
| Update SLA (stricter) | MINOR | Freshness 6h → 4h (improvement) |
| Update SLA (relaxed) | MAJOR | Freshness 4h → 8h (degradation) |

### Breaking Change Detection

The `DataContractPlugin.compare_schemas()` method detects breaking changes:

```python
def compare_schemas(
    self,
    old_schema: ContractSchema,
    new_schema: ContractSchema,
) -> SchemaComparisonResult:
    """Compare schemas and identify breaking changes."""

    breaking_changes = []
    additions = []
    metadata_changes = []

    old_elements = {e.name: e for e in old_schema.elements}
    new_elements = {e.name: e for e in new_schema.elements}

    # Check for removed columns (BREAKING)
    for name in old_elements:
        if name not in new_elements:
            breaking_changes.append(f"Removed column: {name}")

    # Check for type changes (BREAKING)
    for name, old_elem in old_elements.items():
        if name in new_elements:
            new_elem = new_elements[name]
            if old_elem.type != new_elem.type:
                breaking_changes.append(
                    f"Type change: {name} ({old_elem.type} → {new_elem.type})"
                )
            # Stricter nullability (BREAKING)
            if not old_elem.required and new_elem.required:
                breaking_changes.append(
                    f"Nullability stricter: {name} (optional → required)"
                )
            # Relaxed nullability (OK)
            if old_elem.required and not new_elem.required:
                additions.append(f"Nullability relaxed: {name}")

    # Check for new columns
    for name in new_elements:
        if name not in old_elements:
            new_elem = new_elements[name]
            if new_elem.required:
                breaking_changes.append(f"New required column: {name}")
            else:
                additions.append(f"New optional column: {name}")

    return SchemaComparisonResult(
        compatible=len(breaking_changes) == 0,
        breaking_changes=breaking_changes,
        additions=additions,
        metadata_changes=metadata_changes,
    )
```

### Version Validation at Compile Time

The `DataContractPlugin.validate_version_bump()` method ensures version bumps follow rules:

```python
def validate_version_bump(
    self,
    old_contract: DataContract,
    new_contract: DataContract,
) -> tuple[bool, str]:
    """Validate that version change matches change severity."""

    old_v = semver.Version.parse(old_contract.version)
    new_v = semver.Version.parse(new_contract.version)

    # Compare schemas
    for old_model in old_contract.models:
        new_model = next(
            (m for m in new_contract.models if m.name == old_model.name),
            None
        )
        if new_model:
            result = self.compare_schemas(old_model, new_model)

            if result.breaking_changes:
                # Must bump MAJOR
                if new_v.major <= old_v.major:
                    return False, (
                        f"Breaking changes require MAJOR version bump. "
                        f"Current: {old_contract.version}, "
                        f"Proposed: {new_contract.version}. "
                        f"Changes: {result.breaking_changes}"
                    )
            elif result.additions:
                # Must bump at least MINOR
                if new_v.major == old_v.major and new_v.minor <= old_v.minor:
                    return False, (
                        f"Additions require MINOR version bump. "
                        f"Current: {old_contract.version}, "
                        f"Proposed: {new_contract.version}."
                    )

    return True, "Version bump is valid"
```

### Deprecation Workflow

```
                        ┌─────────────────────────────────────────────────────────┐
                        │                    DEPRECATION WORKFLOW                  │
                        └─────────────────────────────────────────────────────────┘

    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │   ACTIVE    │────►│ DEPRECATED  │────►│  SUNSET     │────►│  RETIRED    │
    │             │     │ (30 days)   │     │ (warn only) │     │ (removed)   │
    └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
          │                   │                   │                    │
          │                   │                   │                    │
    Normal usage        Warnings in        Errors if used        Contract deleted
                       OpenLineage         No new consumers      Data may remain
```

#### Deprecation States

| State | Duration | Behavior |
|-------|----------|----------|
| `active` | Indefinite | Normal operation |
| `deprecated` | 30 days minimum | Warnings emitted, new consumers warned |
| `sunset` | 7 days | Errors for new consumers, existing warned |
| `retired` | N/A | Contract removed, data may be retained |

#### datacontract.yaml Deprecation Fields

```yaml
apiVersion: v3.0.2
kind: DataContract
name: legacy-customers
version: 3.0.0

status: deprecated  # active | deprecated | sunset | retired

deprecation:
  announced: "2026-01-03"
  sunset_date: "2026-02-03"
  replacement: sales-customers-v4
  migration_guide: https://wiki.acme.com/migrate-customers-v4
  reason: "Replacing with unified customer model"
```

#### Deprecation Notifications

```python
class ContractMonitor:

    async def check_deprecation(
        self,
        contract: DataContract,
    ) -> ContractViolation | None:
        """Check if contract is deprecated and emit warning."""

        if contract.status == "deprecated":
            return ContractViolation(
                contract_name=contract.name,
                contract_version=contract.version,
                violation_type=ViolationType.DEPRECATION_WARNING,
                severity=ContractViolationSeverity.WARNING,
                message=(
                    f"Contract {contract.name} is deprecated. "
                    f"Sunset date: {contract.deprecation.sunset_date}. "
                    f"Migrate to: {contract.deprecation.replacement}"
                ),
            )

        if contract.status == "sunset":
            return ContractViolation(
                contract_name=contract.name,
                contract_version=contract.version,
                violation_type=ViolationType.DEPRECATION_ERROR,
                severity=ContractViolationSeverity.ERROR,
                message=(
                    f"Contract {contract.name} is sunset. "
                    f"Immediate migration required to: "
                    f"{contract.deprecation.replacement}"
                ),
            )

        return None
```

### Contract Discovery

Contracts are discoverable via:

1. **Git repository**: `datacontract.yaml` alongside `floe.yaml`
2. **Compiled artifacts**: `CompiledArtifacts.data_contracts[]`
3. **Catalog integration**: Registered in Polaris/Unity Catalog metadata

```python
# Contract discovery at compile time
class PolicyEnforcer:

    def discover_contracts(
        self,
        data_product_dir: Path,
    ) -> list[DataContract]:
        """Discover contracts for a data product."""

        contracts = []

        # Check for explicit contract
        contract_path = data_product_dir / "datacontract.yaml"
        if contract_path.exists():
            contracts.append(
                self._contract_plugin.parse_contract(contract_path)
            )
        else:
            # Generate from ports
            product = self._parse_data_product(data_product_dir)
            contracts.append(
                self._contract_plugin.generate_contract_from_ports(
                    output_ports=product.output_ports,
                    input_ports=product.input_ports,
                    metadata=product.metadata,
                )
            )

        return contracts
```

### Race Condition Prevention (Data Mesh)

In Data Mesh scenarios, multiple domains may consume the same contract. Race conditions occur when:

1. Producer updates schema while consumer is reading
2. Multiple consumers have different version expectations
3. Catalog metadata is out of sync with actual schema

**Mitigations:**

| Risk | Mitigation |
|------|------------|
| Mid-flight schema change | Iceberg table versioning (time travel) |
| Version mismatch | Contract version in OpenLineage facets |
| Catalog drift | Schema drift detection in ContractMonitor |
| Consumer breakage | Major version = new table namespace |

**Major Version Strategy:**

```
# Version 1.x tables
gold.customers_v1

# Version 2.x tables (breaking change)
gold.customers_v2  ← New namespace, old consumers unaffected
```

### Three-Tier Contract Inheritance

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
        ├── Specific SLAs
        └── Cannot relax parent requirements
```

**Inheritance Rules:**
- Child contracts inherit parent requirements
- Child contracts can STRENGTHEN but not WEAKEN
- Violations of inheritance detected at compile time

```python
def validate_inheritance(
    parent: DataContract,
    child: DataContract,
) -> list[str]:
    """Validate child doesn't weaken parent contract."""

    violations = []

    # Check SLA relaxation
    if parent.sla and child.sla:
        if child.sla.freshness_hours > parent.sla.freshness_hours:
            violations.append(
                f"Child freshness ({child.sla.freshness_hours}h) "
                f"is weaker than parent ({parent.sla.freshness_hours}h)"
            )

    # Check required fields still required
    parent_required = {
        e.name for m in parent.models
        for e in m.elements if e.required
    }
    child_required = {
        e.name for m in child.models
        for e in m.elements if e.required
    }

    relaxed = parent_required - child_required
    if relaxed:
        violations.append(
            f"Child makes parent-required fields optional: {relaxed}"
        )

    return violations
```

## Consequences

### Positive

1. **Clear versioning**: Semantic versioning with automated detection
2. **Consumer protection**: Breaking changes require major version bump
3. **Graceful deprecation**: 30-day notice period for migrations
4. **Race condition mitigation**: Major versions use new namespaces
5. **Inheritance enforcement**: Children can't weaken parent contracts

### Negative

1. **Migration burden**: Major versions require consumer updates
2. **Version proliferation**: Many major versions over time
3. **Complexity**: Three-tier inheritance adds cognitive load

### Neutral

1. **Producer responsibility**: Producers must version correctly
2. **Tooling dependency**: Relies on `compare_schemas()` accuracy

## References

- [ADR-0026: Data Contract Architecture](./0026-data-contract-architecture.md)
- [ADR-0027: ODCS Standard Adoption](./0027-odcs-standard-adoption.md)
- [ADR-0028: Runtime Contract Monitoring](./0028-runtime-contract-monitoring.md)
- [Semantic Versioning 2.0.0](https://semver.org/)
- [Data Mesh Principles](https://martinfowler.com/articles/data-mesh-principles.html)

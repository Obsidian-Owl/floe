# Research: Data Contracts (Epic 3C)

**Date**: 2026-01-24
**Status**: Complete

## Prior Decisions (from Agent Memory)

- ODCS v3 adopted as the enforced data contract standard (ADR-0026, ADR-0027)
- datacontract-cli selected for ODCS parsing/linting/validation
- Contract inheritance follows manifest hierarchy (enterprise -> domain -> product)
- Schema drift detection uses IcebergTableManager from Epic 4D

---

## Research Topics

### 1. datacontract-cli Python SDK

**Question**: How to use datacontract-cli programmatically from Python?

**Findings**:

The datacontract-cli provides a Python SDK via the `datacontract` package:

```python
from datacontract.data_contract import DataContract

# Load from file
dc = DataContract(data_contract_file="datacontract.yaml")

# Load from string
dc = DataContract(data_contract_str=yaml_content)

# Lint (validate ODCS compliance)
lint_result = dc.lint()
if not lint_result.has_passed():
    for error in lint_result.errors:
        print(error)

# Test against data source (runtime - out of scope for 3C)
run = dc.test()

# Export to various formats
dc.export(format="html")  # 30+ formats supported
```

**Key Classes**:
- `DataContract` - Main entry point
- `LintResult` - Result of `lint()` with `has_passed()` and `errors`
- `TestResult` - Result of `test()` with `has_passed()` and checks

**Dependencies**: Python 3.10, 3.11, or 3.12

**Sources**:
- [datacontract-cli Documentation](https://cli.datacontract.com/)
- [GitHub: datacontract/datacontract-cli](https://github.com/datacontract/datacontract-cli)

---

### 2. ODCS v3 Schema Structure

**Question**: What fields are required in ODCS v3? What types are supported?

**Findings**:

**Required Top-Level Fields** (per ODCS spec):
- `apiVersion` - Schema version (e.g., "v3.0.2")
- `kind` - Always "DataContract"
- `id` - Unique UUID
- `version` - Contract version (semver)
- `status` - Lifecycle state

**Floe-Enforced Fields** (stricter than ODCS):
- `owner` - Contact email (optional in ODCS, required in floe)
- `models` - At least one model definition

**Optional but Recommended**:
- `name` - Human-readable identifier
- `domain` - Business domain
- `description` - With purpose, limitations, usage
- `slaProperties` - Freshness, availability, quality
- `terms` - Usage terms, retention, limitations
- `tags` - Categorization
- `links` - Documentation, dashboards

**Supported Element Types**:
```
string, date, timestamp, time, number, integer, object, array, boolean
```

**Additional Logical Types** (via logicalTypeOptions):
- `int`, `long`, `float`, `double`, `decimal`
- `bytes`

**Element Formats**:
```
email, uri, uuid, phone, date, date-time, ipv4, ipv6
```

**Classification Values**:
```
public, internal, confidential, pii, phi, sensitive, restricted
```

**SLA Duration Format** (ISO 8601):
```
PT15M (15 minutes), PT1H (1 hour), PT6H (6 hours), P1D (1 day), P7D (7 days)
```

**Sources**:
- [ODCS Fundamentals](https://bitol-io.github.io/open-data-contract-standard/latest/fundamentals/)
- [ODCS Schema](https://bitol-io.github.io/open-data-contract-standard/latest/schema/)
- [ODCS SLA](https://bitol-io.github.io/open-data-contract-standard/latest/service-level-agreement/)
- [floe datacontract-yaml-reference.md](../docs/contracts/datacontract-yaml-reference.md)

---

### 3. PolicyEnforcer Integration Pattern

**Question**: How do existing validators integrate with PolicyEnforcer?

**Findings**:

**Validator Registration** (`policy_enforcer.py:127-167`):
```python
def _run_all_validators(self, manifest, models, max_violations):
    violations = []

    # Pattern: Check config -> Run validator -> Check limit
    if self.governance_config.naming is not None:
        violations.extend(self._validate_naming(models))
        if self._limit_reached(violations, max_violations):
            return violations[:max_violations]

    # Quality gates (coverage, documentation)
    violations = self._run_quality_gate_validators(...)

    # Semantic validation (always enabled)
    violations.extend(self._validate_semantic(manifest))

    # Custom rules
    if self.governance_config.custom_rules:
        violations.extend(self._validate_custom_rules(manifest))
```

**Validator Interface Pattern**:
```python
class SomeValidator:
    def __init__(self, config: SomeConfig) -> None:
        self.config = config
        self._log = structlog.get_logger(__name__).bind(component="SomeValidator")

    def validate(self, data: SomeInput) -> list[Violation]:
        violations = []
        # Validation logic
        return violations
```

**Error Code Ranges**:
- FLOE-E2xx: Naming, coverage, documentation
- FLOE-E3xx: Semantic validation
- FLOE-E4xx: Custom rules
- FLOE-E5xx: **Data contracts (new)**

**Sources**:
- `packages/floe-core/src/floe_core/enforcement/policy_enforcer.py`
- `packages/floe-core/src/floe_core/enforcement/validators/`

---

### 4. CompiledArtifacts Extension

**Question**: How to extend CompiledArtifacts for data contracts?

**Findings**:

**Field Addition Pattern**:
```python
# New field - pre-release so no version bump needed
data_contracts: list[DataContract] | None = Field(
    default=None,
    description="Parsed and validated data contracts",
)
```

**Note**: No version bump needed - project is in pre-release development.

**Model Config**:
```python
model_config = ConfigDict(frozen=True, extra="forbid")
```

**Sources**:
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`

---

### 5. IcebergTableManager Schema Access

**Question**: How to get table schema for drift detection?

**Findings**:

**API**:
```python
from floe_iceberg import IcebergTableManager

# Check if table exists
if manager.table_exists("namespace.table_name"):
    # Load table
    table = manager.load_table("namespace.table_name")

    # Access schema (PyIceberg API)
    schema = table.schema()

    # Iterate fields
    for field in schema.fields:
        print(field.name, field.field_type)
```

**Type Mapping** (ODCS -> PyIceberg):
| ODCS Type | PyIceberg Type |
|-----------|---------------|
| string | STRING |
| int | INT |
| long | LONG |
| float | FLOAT |
| double | DOUBLE |
| decimal | DECIMAL |
| boolean | BOOLEAN |
| date | DATE |
| timestamp | TIMESTAMP |
| bytes | BINARY |
| array | LIST |
| object | STRUCT |

**Sources**:
- `packages/floe-iceberg/src/floe_iceberg/manager.py`
- `packages/floe-iceberg/src/floe_iceberg/_schema_manager.py`

---

### 6. Contract Auto-Generation

**Question**: Can contracts be auto-generated from floe.yaml ports?

**Findings**:

**Current State**: FloeSpec does NOT have `output_ports` field.

**Options Evaluated**:

1. **Add output_ports to FloeSpec** - Requires spec change, breaking for existing users
2. **Derive from dbt manifest models** - Uses existing data, no spec change
3. **Require explicit datacontract.yaml** - Simplest, most explicit

**Decision**: Option 1 selected - implement auto-generation from output_ports in Epic 3C

- Add output_ports to FloeSpec (schema change acceptable for pre-release)
- Auto-generate base contracts when no explicit `datacontract.yaml` exists
- FLOE-E500 error only when BOTH datacontract.yaml AND output_ports are missing

**Rationale**:
- Aligns with FR-003 requirement ("MUST auto-generate")
- Lowers barrier to adoption for data engineers
- Pre-release project allows spec changes without breaking users

**Sources**:
- `packages/floe-core/src/floe_core/schemas/floe_spec.py`
- spec.md FR-003

---

### 7. Version Bump Detection

**Question**: How to detect breaking changes between contract versions?

**Findings**:

**Breaking Changes** (require MAJOR bump):
- Remove element (column)
- Change element type (string -> int)
- Make optional element required
- Relax SLA (freshness 4h -> 8h, availability 99.9% -> 99%)
- Add required element

**Non-Breaking Changes** (require MINOR bump):
- Add optional element
- Make required element optional
- Stricter SLA (freshness 6h -> 4h)

**Patch Changes** (require PATCH bump):
- Update description
- Add/change tags
- Update links

**Implementation**:
1. Load baseline from catalog (FR-015)
2. Compare schemas field-by-field
3. Categorize changes
4. Validate version bump matches change type

**Sources**:
- `docs/contracts/datacontract-yaml-reference.md` (Versioning Rules section)
- spec.md FR-016, FR-017, FR-018, FR-019

---

### 8. Inheritance Validation

**Question**: How to validate contract inheritance (enterprise -> domain -> product)?

**Findings**:

**Inheritance Model**:
```
Enterprise Contract (most strict)
    ↓ inherits
Domain Contract (can strengthen, cannot weaken)
    ↓ inherits
Product Contract (can strengthen, cannot weaken)
```

**Validation Rules**:
- Child cannot weaken SLA properties (freshness, availability, quality)
- Child cannot remove or weaken explicit classifications
- Child can add new models/elements
- Child can strengthen SLAs

**Implementation Pattern** (from governance.py):
```python
# Existing pattern for inheritance validation
def validate_inheritance(parent: Contract, child: Contract) -> list[Violation]:
    violations = []

    # Check SLA weakening
    if child.sla.freshness > parent.sla.freshness:
        violations.append(Violation(
            error_code="FLOE-E510",
            message="Child contract cannot relax freshness SLA",
            expected=parent.sla.freshness,
            actual=child.sla.freshness,
        ))

    return violations
```

**Sources**:
- spec.md FR-011, FR-012, FR-013, FR-014
- `packages/floe-core/src/floe_core/schemas/governance.py`

---

## Decisions

| Decision | Rationale | Alternatives Rejected |
|----------|-----------|----------------------|
| datacontract-cli as hard dependency | Ensures ODCS ecosystem compatibility, consistency with Epic 3D | Optional (loses validation), custom parser (reinvents wheel) |
| ODCS v3.0.2 target version | Current stable release, aligns with datacontract-cli | v2.x (deprecated), bleeding edge (unstable) |
| Require explicit datacontract.yaml | Explicit > implicit, keeps MVP scope | Auto-generate from ports (complex), derive from dbt (incomplete) |
| Catalog-registered baseline for versioning | Enables offline comparison, audit trail | File-based (no audit), git-based (complex) |
| floe_core for ContractValidator | Follows existing validator pattern | floe-contracts package (unnecessary split) |
| CompiledArtifacts v0.4.0 | MINOR bump for additive field | v1.0.0 (premature), v0.3.1 (wrong semantics) |

---

## Open Questions

None - all questions resolved through research.

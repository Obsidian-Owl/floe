# Implementation Plan: Data Contracts (Epic 3C)

**Branch**: `3c-data-contracts` | **Date**: 2026-01-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/3c-data-contracts/spec.md`

## Summary

Implement compile-time data contract validation using ODCS v3 standard with `datacontract-cli` as a hard dependency. Adds ContractValidator to PolicyEnforcer chain, extends CompiledArtifacts with data_contracts field, and provides schema drift detection against actual Iceberg tables.

## Technical Context

**Language/Version**: Python 3.10+ (matches floe-core requirements)
**Primary Dependencies**: datacontract-cli (hard dependency), Pydantic v2, structlog, PyIceberg
**Storage**: Iceberg catalog namespace properties (contract registration)
**Testing**: pytest with K8s-native integration tests (Kind cluster)
**Target Platform**: Kubernetes (deployment), Linux/macOS (development)
**Project Type**: Monorepo package (floe-core extension)
**Performance Goals**: <2s validation for contracts with 50 models
**Constraints**: datacontract-cli must be installed; ODCS v3.x compliance required
**Scale/Scope**: Supports enterprise -> domain -> product inheritance chains

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core/enforcement/validators/)
- [x] No SQL parsing/validation in Python (dbt owns SQL)
- [x] No orchestration logic outside floe-dagster
- [x] datacontract-cli owns ODCS parsing/linting - floe delegates

**Principle II: Plugin-First Architecture**
- [x] ContractValidator is NOT a plugin - it's a validator in enforcement chain
- [x] Validators are internal to floe-core, not entry-point discoverable
- [N/A] PluginMetadata - validators don't need this

**Principle III: Enforced vs Pluggable**
- [x] ODCS v3 is enforced standard (per ADR-0026/0027)
- [x] datacontract-cli is enforced (not pluggable)
- [x] Contract inheritance follows manifest hierarchy (enforced pattern)

**Principle IV: Contract-Driven Integration**
- [x] CompiledArtifacts extended with data_contracts field
- [x] DataContract is Pydantic v2 model (frozen=True, extra="forbid")
- [N/A] Version bump not needed (pre-release)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster (schema drift needs Iceberg)
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (DataContract model)
- [x] No credentials in contract files (owner is email, not secret)
- [x] No shell=True (datacontract-cli invoked via Python SDK)

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward (manifest.yaml -> floe.yaml -> contract)
- [x] Governance config in manifest (Platform Team), contracts in data product (Data Team)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces for contract validation (structlog + trace context)
- [x] Contract violations included in EnforcementResult (existing SARIF export)

## Integration Design

### Entry Point Integration
- [x] Feature reachable from: CLI (`floe compile` command)
- [x] Integration point: `PolicyEnforcer._run_all_validators()` in `enforcement/policy_enforcer.py`
- [x] Wiring task needed: Yes - add `_validate_data_contracts()` method call

### Dependency Integration
| This Feature Uses | From Package | Integration Point |
|-------------------|--------------|-------------------|
| PolicyEnforcer | floe-core | Add ContractValidator to validator chain |
| CompiledArtifacts | floe-core | Extend with `data_contracts: list[DataContract]` |
| EnforcementSummary | floe-core | Add `contract_violations: int` field |
| Violation | floe-core | Add `"data_contract"` to policy_type Literal |
| IcebergTableManager | floe-iceberg | `load_table()` + `table.schema()` for drift detection |
| CatalogPlugin | floe-core | Namespace property operations for registration |
| datacontract-cli | external | `DataContract` class for parsing/linting |

### Produces for Others
| Output | Consumers | Contract |
|--------|-----------|----------|
| DataContract Pydantic model | CompiledArtifacts | `floe_core.schemas.data_contract.DataContract` |
| ContractValidationResult | EnforcementResult | Violations with FLOE-E5xx codes |
| Catalog registration | Downstream consumers | Namespace property `floe.contracts` |

### Cleanup Required
- [ ] No cleanup needed - this is additive functionality

## Project Structure

### Documentation (this feature)

```text
specs/3c-data-contracts/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (JSON schemas)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
packages/floe-core/src/floe_core/
├── enforcement/
│   ├── policy_enforcer.py    # MODIFY: Add _validate_data_contracts() call
│   ├── result.py             # MODIFY: Add contract_violations to summary, "data_contract" to policy_type
│   ├── patterns.py           # MODIFY: Add FLOE-E5xx documentation URLs
│   └── validators/
│       ├── __init__.py       # MODIFY: Export ContractValidator
│       └── data_contracts.py # NEW: ContractValidator implementation
├── schemas/
│   ├── compiled_artifacts.py # MODIFY: Add data_contracts field
│   ├── governance.py         # MODIFY: Add DataContractsConfig
│   ├── data_contract.py      # NEW: DataContract Pydantic model (ODCS v3)
│   └── manifest.py           # MODIFY: Add data_contracts to GovernanceConfig
└── contracts/
    └── generator.py          # NEW: Auto-generate contracts from ports

packages/floe-iceberg/src/floe_iceberg/
└── drift_detector.py         # NEW: Schema drift detection utility

tests/
├── contract/
│   ├── test_data_contract_schema.py           # NEW: Schema stability tests
│   └── test_core_to_iceberg_drift_contract.py # NEW: Drift detection contract
└── integration/
    └── test_data_contracts_integration.py     # NEW: Full workflow test
```

## Complexity Tracking

No constitution violations requiring justification.

---

## Phase 0: Research

See [research.md](./research.md) for detailed findings.

### Key Research Findings

#### 1. datacontract-cli Python SDK

**Programmatic Usage** (confirmed via documentation and GitHub):
```python
from datacontract.data_contract import DataContract

# Parse and validate contract
data_contract = DataContract(data_contract_file="datacontract.yaml")

# Lint (validate ODCS compliance)
lint_result = data_contract.lint()  # Returns LintResult

# Test against data source (runtime - Epic 3D)
run = data_contract.test()
if not run.has_passed():
    print("Validation failed")
```

**Key SDK Methods**:
- `DataContract(data_contract_file=...)` - Load contract from YAML
- `DataContract(data_contract_str=...)` - Load from string
- `lint()` - Validate ODCS schema compliance
- `test()` - Runtime data testing (out of scope for 3C)
- `export(format=...)` - Export to 30+ formats

**Return Types**:
- `lint()` returns `LintResult` with `has_passed()` method and violations list
- Contract data accessible via `data_contract.data` (dict) or typed properties

#### 2. ODCS v3 Schema Structure (from bitol.io)

**Required Top-Level Fields**:
- `apiVersion` - Standard version (e.g., "v3.0.2")
- `kind` - Always "DataContract"
- `id` - Unique UUID identifier
- `version` - Contract version (semver)
- `status` - Lifecycle state (active, deprecated, sunset, retired)

**Optional but Recommended**:
- `name` - Human-readable name
- `owner` - Contact email (our docs say required - stricter)
- `domain` - Business domain
- `description` - Object with purpose, limitations, usage

**Schema Structure**:
- `schema[]` - Array of objects (tables) and properties (columns)
- Each element has: `name` (required), `id`, `businessName`, `description`, `physicalName`, `physicalType`
- Logical types: `string`, `date`, `timestamp`, `time`, `number`, `integer`, `object`, `array`, `boolean`
- Properties support: partitioning, encryption, criticality

**SLA Properties**:
- Required per SLA: `property` (name) and `value`
- Optional: `id`, `element`, `unit`, `driver`, `description`, `scheduler`, `valueExt`
- Duration units: d/day/days, y/yr/years (ISO 8601)
- Drivers: `regulatory`, `analytics`, `operational`

#### 3. Existing PolicyEnforcer Integration Pattern

**Validator Registration** (`policy_enforcer.py:127-167`):
```python
def _run_all_validators(self, manifest, models, max_violations):
    violations = []

    # Pattern: Check config, run validator, check limit
    if self.governance_config.naming is not None:
        violations.extend(self._validate_naming(models))
        if self._limit_reached(violations, max_violations):
            return violations[:max_violations]

    # ... more validators ...

    # Data contracts would be added here:
    # if self.governance_config.data_contracts is not None:
    #     violations.extend(self._validate_data_contracts(manifest))
```

**Validator Interface Pattern** (all validators follow):
```python
class SomeValidator:
    def __init__(self, config: SomeConfig) -> None:
        self.config = config
        self._log = structlog.get_logger(__name__).bind(component="SomeValidator")

    def validate(self, data: SomeInput) -> list[Violation]:
        violations = []
        # ... validation logic ...
        return violations
```

#### 4. CompiledArtifacts Extension Pattern

**Field Addition Pattern**:
```python
# New field - pre-release so no version bump needed
data_contracts: list[DataContract] | None = Field(
    default=None,
    description="Parsed and validated data contracts",
)
```

**Note**: No version bump needed - project is in pre-release development.

#### 5. IcebergTableManager Schema Access

**Loading Table** (`manager.py:309-327`):
```python
# Load existing table
table = manager.load_table("namespace.table_name")

# PyIceberg Table has .schema() method returning Schema object
schema = table.schema()

# Schema has .fields property returning list of NestedField
for field in schema.fields:
    print(field.name, field.field_type)
```

**For Drift Detection**:
1. Check `manager.table_exists(identifier)` first
2. If exists, `table = manager.load_table(identifier)`
3. Compare `table.schema().fields` against contract elements
4. Type mapping: ODCS types -> PyIceberg types (see `_schema_manager.py`)

#### 6. Contract Auto-Generation from Ports

**Current State**: FloeSpec does NOT have output_ports field yet.

**Options**:
1. Add `output_ports` to FloeSpec (requires spec change)
2. Derive from dbt manifest models (simpler, no spec change)
3. Require explicit datacontract.yaml only (simplest for MVP)

**Recommendation**: Option 3 for Epic 3C MVP - require explicit contracts or fail with FLOE-E500. Port-based auto-generation can be added in future epic.

---

## Phase 1: Design

### Data Model

See [data-model.md](./data-model.md) for complete entity specifications.

#### Core Entities

**DataContract** (ODCS v3 Pydantic model):
```python
class DataContract(BaseModel):
    """ODCS v3 data contract representation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    api_version: str = Field(alias="apiVersion", pattern=r"^v3\.\d+\.\d+$")
    kind: Literal["DataContract"] = "DataContract"
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    status: ContractStatus = ContractStatus.ACTIVE
    owner: str = Field(min_length=1)  # Email address
    domain: str | None = None
    description: str | None = None
    models: list[DataContractModel]
    sla_properties: SLAProperties | None = Field(default=None, alias="slaProperties")
    terms: ContractTerms | None = None
    deprecation: DeprecationInfo | None = None
    tags: list[str] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict)

    # Validation metadata (added by floe)
    schema_hash: str | None = None
    validated_at: datetime | None = None
```

**DataContractModel**:
```python
class DataContractModel(BaseModel):
    """Individual model (table) within a contract."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    elements: list[DataContractElement]
```

**DataContractElement**:
```python
class DataContractElement(BaseModel):
    """Column/field definition within a model."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    type: ElementType  # Literal enum of valid types
    required: bool = False
    primary_key: bool = Field(default=False, alias="primaryKey")
    unique: bool = False
    format: ElementFormat | None = None  # email, uri, uuid, etc.
    classification: Classification | None = None  # pii, phi, etc.
    enum: list[str] | None = None
    description: str | None = None
```

**SLAProperties**:
```python
class FreshnessSLA(BaseModel):
    value: str = Field(pattern=r"^P(?:T?\d+[DHMS])+$")  # ISO 8601 duration
    element: str | None = None  # Column to check

class QualitySLA(BaseModel):
    completeness: str | None = None  # Percentage
    uniqueness: str | None = None
    accuracy: str | None = None

class SLAProperties(BaseModel):
    freshness: FreshnessSLA | None = None
    availability: str | None = None  # Percentage
    quality: QualitySLA | None = None
```

**ContractValidationResult**:
```python
class ContractValidationResult(BaseModel):
    """Result of contract validation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    violations: list[Violation]
    warnings: list[Violation]
    schema_hash: str
    validated_at: datetime
```

**SchemaComparisonResult**:
```python
class SchemaComparisonResult(BaseModel):
    """Result of schema drift detection."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    matches: bool
    type_mismatches: list[TypeMismatch]
    missing_columns: list[str]  # In contract, not in table
    extra_columns: list[str]    # In table, not in contract
```

**DataContractsConfig** (governance configuration):
```python
class DataContractsConfig(BaseModel):
    """Data contracts governance configuration."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    enforcement: Literal["off", "warn", "strict"] = "warn"
    auto_generation: AutoGenerationConfig | None = None
    drift_detection: DriftDetectionConfig | None = None
    inheritance_mode: Literal["strict", "permissive"] = "strict"
```

### Integration Points

#### PolicyEnforcer Integration

Add to `_run_all_validators()`:
```python
# After custom rules validation
if self.governance_config.data_contracts is not None:
    violations.extend(self._validate_data_contracts(manifest))
    if self._limit_reached(violations, max_violations):
        return violations[:max_violations]
```

New method:
```python
def _validate_data_contracts(self, manifest: dict[str, Any]) -> list[Violation]:
    """Validate data contracts against ODCS schema, inheritance, versioning."""
    config = self.governance_config.data_contracts
    if config is None or config.enforcement == "off":
        return []

    validator = ContractValidator(config, self._iceberg_manager)
    return validator.validate(manifest)
```

#### EnforcementSummary Extension

Add field:
```python
contract_violations: int = Field(default=0, ge=0, description="Data contract violations")
```

Update `_build_summary()` in PolicyEnforcer:
```python
contract_count = sum(1 for v in violations if v.policy_type == "data_contract")
```

#### Violation policy_type Extension

Update `VALID_POLICY_TYPES` in governance.py:
```python
VALID_POLICY_TYPES = frozenset({"naming", "coverage", "documentation", "semantic", "custom", "data_contract"})
```

### Error Codes

| Code | Category | Description |
|------|----------|-------------|
| FLOE-E500 | Contract Required | No datacontract.yaml and no output ports defined |
| FLOE-E501 | Schema Validation | Missing required ODCS field (apiVersion, kind, name, version, owner, models) |
| FLOE-E502 | Schema Validation | Invalid format (SLA duration, version, etc.) |
| FLOE-E503 | Schema Validation | Invalid element type (not in ODCS type system) |
| FLOE-E510 | Inheritance | Child contract weakens parent SLA |
| FLOE-E520 | Versioning | Breaking change without MAJOR version bump |
| FLOE-E530 | Schema Drift | Type mismatch between contract and table |
| FLOE-E531 | Schema Drift | Column missing from table (defined in contract) |
| FLOE-E532 | Schema Drift | Undocumented column in table (info only) |

### datacontract-cli Integration

**Installation Check**:
```python
def _check_datacontract_cli() -> None:
    """Verify datacontract-cli is installed."""
    try:
        from datacontract.data_contract import DataContract
    except ImportError:
        raise ContractValidationError(
            "datacontract-cli is required but not installed. "
            "Install with: pip install datacontract-cli"
        )
```

**Parsing and Linting**:
```python
from datacontract.data_contract import DataContract as DCContract

def parse_contract(path: Path) -> DataContract:
    """Parse contract using datacontract-cli, convert to floe model."""
    dc = DCContract(data_contract_file=str(path))
    lint_result = dc.lint()

    if not lint_result.has_passed():
        # Convert lint errors to Violations
        violations = [_lint_error_to_violation(e) for e in lint_result.errors]
        raise ContractLintError(violations)

    return _convert_to_floe_model(dc.data)
```

### Catalog Registration

**Namespace Property Storage**:
```python
def register_contract(
    catalog_plugin: CatalogPlugin,
    namespace: str,
    contract: DataContract,
) -> None:
    """Register contract metadata in catalog namespace properties."""
    props = {
        "floe.contracts": json.dumps([{
            "name": contract.name,
            "version": contract.version,
            "owner": contract.owner,
            "schema_hash": contract.schema_hash,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }]),
    }
    catalog_plugin.update_namespace_properties(namespace, props)
```

---

## Quickstart

See [quickstart.md](./quickstart.md) for usage examples.

### Basic Usage

1. Create `datacontract.yaml` in your data product:
```yaml
apiVersion: v3.0.2
kind: DataContract
name: my-customers
version: 1.0.0
owner: data-team@example.com

models:
  customers:
    elements:
      id:
        type: string
        primaryKey: true
      email:
        type: string
        format: email
        classification: pii
```

2. Enable contract validation in `manifest.yaml`:
```yaml
governance:
  data_contracts:
    enforcement: strict
    drift_detection:
      enabled: true
      enforcement: warn
```

3. Run `floe compile`:
```bash
$ floe compile
Validating data contracts...
  ✓ my-customers:1.0.0 - ODCS v3.0.2 compliant
  ✓ Schema drift check passed
Contracts registered in catalog.
```

---

## Next Steps

1. **Generate tasks**: Run `/speckit.tasks` to create actionable task list
2. **Create checklist**: Run `/speckit.checklist` to create quality checklist

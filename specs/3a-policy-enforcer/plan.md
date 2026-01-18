# Implementation Plan: Policy Enforcer Core (Epic 3A)

**Branch**: `3a-policy-enforcer` | **Date**: 2026-01-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/3a-policy-enforcer/spec.md`

## Summary

Implement a compile-time governance enforcement engine (PolicyEnforcer) as a core module in floe-core. The PolicyEnforcer validates dbt manifests against platform-defined policies including naming conventions (medallion, kimball, custom), test coverage thresholds (column-level), and documentation requirements. It integrates into the existing 6-stage compilation pipeline at Stage 4 (ENFORCE), extending the existing GovernanceConfig schema with new NamingConfig and QualityGatesConfig models.

## Technical Context

**Language/Version**: Python 3.10+ (matches floe-core requirements)
**Primary Dependencies**: Pydantic v2 (schemas), structlog (logging), opentelemetry-api (tracing)
**Storage**: N/A (PolicyEnforcer is stateless; reads dbt manifest.json)
**Testing**: pytest with K8s-native integration tests
**Target Platform**: Linux server, macOS (development)
**Project Type**: Monorepo package (floe-core)
**Performance Goals**: <5 seconds for 500 dbt models
**Constraints**: No SQL parsing (dbt owns SQL); no runtime data access
**Scale/Scope**: 500+ model dbt projects

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (`packages/floe-core/src/floe_core/enforcement/`)
- [x] No SQL parsing/validation in Python (PolicyEnforcer reads dbt manifest metadata only)
- [x] No orchestration logic outside floe-dagster

**Principle II: Plugin-First Architecture**
- [x] PolicyEnforcer is CORE MODULE, not plugin (per ADR-0015)
- [x] PluginMetadata N/A (core module, not plugin)
- [x] Entry points N/A (core module, not plugin)

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s)
- [x] Policy enforcement is ENFORCED standard per architecture

**Principle IV: Contract-Driven Integration**
- [x] GovernanceConfig, EnforcementResult are Pydantic v2 models
- [x] JSON Schema exported to contracts/
- [x] No FloeSpec passing (uses dbt manifest + GovernanceConfig)

**Principle V: K8s-Native Testing**
- [x] Integration tests will run in Kind cluster
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (GovernanceConfig, NamingConfig, etc.)
- [x] No credentials in PolicyEnforcer (reads dbt manifest only)
- [x] No shell=True, no dynamic code execution
- [x] Custom regex patterns validated before compilation (ReDoS prevention)

**Principle VII: Four-Layer Architecture**
- [x] PolicyEnforcer runs at Layer 2 (Configuration)
- [x] Configuration flows downward only (manifest → enforcement → artifacts)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry spans emitted for enforcement
- [x] structlog events for audit trail
- [x] EnforcementResult includes timing metrics

## Project Structure

### Documentation (this feature)

```text
specs/3a-policy-enforcer/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research output
├── data-model.md        # Entity definitions
├── quickstart.md        # Usage examples
├── contracts/           # JSON Schema definitions
│   ├── governance-schema.json
│   └── enforcement-result-schema.json
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
packages/floe-core/src/floe_core/
├── schemas/
│   ├── manifest.py          # EXTEND: GovernanceConfig with naming/quality_gates
│   ├── governance.py        # NEW: NamingConfig, QualityGatesConfig, LayerThresholds
│   └── validation.py        # EXTEND: Strength constants for new fields
├── enforcement/             # NEW: PolicyEnforcer module
│   ├── __init__.py
│   ├── policy_enforcer.py   # PolicyEnforcer class
│   ├── validators/
│   │   ├── __init__.py
│   │   ├── naming.py        # NamingValidator
│   │   ├── coverage.py      # CoverageValidator
│   │   └── documentation.py # DocumentationValidator
│   ├── result.py            # EnforcementResult, Violation
│   ├── errors.py            # PolicyEnforcementError
│   └── patterns.py          # Built-in regex patterns (medallion, kimball)
├── compilation/
│   └── stages.py            # MODIFY: Integrate PolicyEnforcer at Stage 4

packages/floe-core/tests/
├── unit/
│   └── enforcement/
│       ├── test_policy_enforcer.py
│       ├── test_naming_validator.py
│       ├── test_coverage_validator.py
│       └── test_documentation_validator.py
├── integration/
│   └── enforcement/
│       └── test_pipeline_enforcement.py

tests/contract/
└── test_governance_schema_stability.py  # Contract test for GovernanceConfig
```

**Structure Decision**: Single package extension (floe-core) with new enforcement module. No new packages required.

## Implementation Phases

### Phase 1: Schema Foundation (P1 - User Story 2)

**Goal**: Extend GovernanceConfig with NamingConfig and QualityGatesConfig

**Files**:
- `floe_core/schemas/governance.py` (NEW)
- `floe_core/schemas/manifest.py` (EXTEND)
- `floe_core/schemas/validation.py` (EXTEND)

**Key Tasks**:
1. Create NamingConfig Pydantic model
2. Create QualityGatesConfig Pydantic model
3. Create LayerThresholds Pydantic model
4. Extend GovernanceConfig with naming and quality_gates fields
5. Add strength constants for new fields in validation.py
6. Extend validate_security_policy_not_weakened() for new fields
7. Export JSON Schema

**Tests**: Unit tests for schema validation, inheritance strengthening

### Phase 2: PolicyEnforcer Core (P1 - User Story 1)

**Goal**: Implement PolicyEnforcer class with enforce() method

**Files**:
- `floe_core/enforcement/__init__.py` (NEW)
- `floe_core/enforcement/policy_enforcer.py` (NEW)
- `floe_core/enforcement/result.py` (NEW)
- `floe_core/enforcement/errors.py` (NEW)

**Key Tasks**:
1. Create EnforcementResult and Violation models
2. Create PolicyEnforcementError exception
3. Implement PolicyEnforcer.enforce() orchestrator
4. Add structlog audit logging
5. Add OpenTelemetry span creation

**Tests**: Unit tests for enforcement orchestration

### Phase 3: Naming Validator (P2 - User Story 3)

**Goal**: Implement naming convention validation

**Files**:
- `floe_core/enforcement/validators/naming.py` (NEW)
- `floe_core/enforcement/patterns.py` (NEW)

**Key Tasks**:
1. Define medallion pattern regex
2. Define kimball pattern regex
3. Implement custom pattern validation (ReDoS protection)
4. Implement NamingValidator.validate()
5. Generate remediation suggestions

**Tests**: Unit tests for each pattern type

### Phase 4: Coverage Validator (P2 - User Story 4)

**Goal**: Implement test coverage validation

**Files**:
- `floe_core/enforcement/validators/coverage.py` (NEW)

**Key Tasks**:
1. Parse dbt manifest for model columns
2. Parse dbt manifest for column tests
3. Implement column-level coverage calculation
4. Implement layer detection (bronze/silver/gold)
5. Implement layer-specific threshold checking
6. Generate coverage gap suggestions

**Tests**: Unit tests with sample dbt manifests

### Phase 5: Documentation Validator (P2 - User Story 5)

**Goal**: Implement documentation validation

**Files**:
- `floe_core/enforcement/validators/documentation.py` (NEW)

**Key Tasks**:
1. Check model description exists
2. Check column descriptions exist
3. Detect placeholder descriptions (TBD, TODO)
4. Generate documentation templates

**Tests**: Unit tests for description detection

### Phase 6: Pipeline Integration (P1 - User Story 1)

**Goal**: Integrate PolicyEnforcer into Stage 4 (ENFORCE)

**Files**:
- `floe_core/compilation/stages.py` (MODIFY)
- `floe_core/cli/compile.py` (MODIFY for --dry-run)

**Key Tasks**:
1. Load dbt manifest in ENFORCE stage
2. Instantiate PolicyEnforcer
3. Run enforcement with GovernanceConfig
4. Handle enforcement result (block or warn)
5. Add --dry-run flag to CLI
6. Emit OTel span attributes for enforcement result

**Tests**: Integration tests with real compilation pipeline

> **Note**: `--dry-run` is a CLI flag passed to the compilation pipeline. PolicyEnforcer remains stateless - it receives a `dry_run: bool` parameter and adjusts result severity accordingly.

### Phase 7: Audit Logging (P3 - User Story 6)

**Goal**: Add compliance audit logging

**Files**:
- `floe_core/enforcement/policy_enforcer.py` (EXTEND)

**Key Tasks**:
1. Log policy decisions with structlog
2. Include all required audit fields
3. Emit OTel span events for violations

**Tests**: Unit tests verifying log output structure

## Dependencies

### External Dependencies (from Epic 2B)
- `floe_core/compilation/stages.py` - ENFORCE stage placeholder exists
- `floe_core/schemas/manifest.py` - GovernanceConfig exists
- `floe_core/schemas/validation.py` - SecurityPolicyViolationError exists

### Internal Dependencies (within this Epic)
- Phase 2 depends on Phase 1 (schemas must exist)
- Phases 3-5 depend on Phase 2 (PolicyEnforcer must exist)
- Phase 6 depends on Phases 2-5 (all validators must exist)
- Phase 7 depends on Phase 6 (pipeline integration required)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| dbt manifest schema changes | Medium | Test against dbt 1.7, 1.8, 1.9; defensive JSON parsing |
| Custom regex ReDoS | High | Validate regex before compilation; set match timeout |
| Large project performance | Medium | Parallel validation; early exit option |
| Contract breaking changes | High | Schema versioning; contract tests in tests/contract/ |

## Complexity Tracking

> No constitution violations requiring justification.

| Design Choice | Why Chosen | Alternative Rejected |
|---------------|------------|----------------------|
| Core module (not plugin) | ADR-0015: Policy rules are configuration, not implementations | Plugin interface - no real alternative implementations exist |
| Column-level coverage | Industry standard (dbt-coverage tool) | Model-level - less granular, 1 test = 100% |
| Extend existing GovernanceConfig | Backward compatible; no schema version bump | New PolicyConfig - breaks existing manifests |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Compilation time | <5s for 500 models | Benchmark test |
| Coverage accuracy | 100% | Compare with dbt-coverage output |
| Inheritance validation | 100% | Unit tests for strengthening rules |
| Error message quality | 90% self-service | User feedback survey |

## References

- **spec.md**: Feature specification
- **research.md**: Technical research and decisions
- **data-model.md**: Entity definitions
- **quickstart.md**: Usage examples
- **ADR-0015**: Policy Enforcement as Core Module
- **ADR-0016**: Platform Enforcement Architecture
- **stages.py:232-245**: ENFORCE stage placeholder

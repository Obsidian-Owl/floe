# Data Quality Plugin Implementation

## TL;DR

> **Quick Summary**: Implement the data quality plugin interface with Great Expectations and dbt-expectations reference implementations, enabling compile-time validation, runtime quality checks, and quality scoring with OpenLineage emission.
> 
> **Deliverables**:
> - Extended QualityPlugin ABC in `floe_core/plugins/quality.py`
> - Quality schemas in `floe_core/schemas/quality_*.py`
> - `floe-quality-gx` plugin package (Great Expectations)
> - `floe-quality-dbt` plugin package (dbt-expectations)
> - Contract tests and integration tests
> 
> **Estimated Effort**: Large (106 tasks across 10 phases)
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: Phase 2 (Foundation) -> Phase 3-5 (MVP) -> Phase 6-8 (P2/P3) -> Phase 9-10 (Polish)

---

## Context

### Original Request
Implement Data Quality Plugin interface and reference implementations (Great Expectations, dbt-expectations) supporting compile-time validation and runtime data quality checks with quality scoring and OpenLineage emission.

### Pre-Existing Documentation
**All specifications are complete**:
- Spec: `/specs/5b-dataquality-plugin/spec.md` - 6 user stories, FR-001 to FR-047
- Plan: `/specs/5b-dataquality-plugin/plan.md` - Phases A-F with risk mitigation
- Tasks: `/specs/5b-dataquality-plugin/tasks.md` - 106 tasks with dependencies
- Contracts: `/specs/5b-dataquality-plugin/contracts/` - Pre-defined Pydantic schemas
- Data Model: `/specs/5b-dataquality-plugin/data-model.md` - Entity relationships

### Linear Tracking
- Project: `floe-05b-dataquality-plugin`
- Issues: FLO-1853 through FLO-1952 (100 issues in Backlog)

---

## Work Objectives

### Core Objective
Extend the existing minimal QualityPlugin ABC with compile-time validation, runtime execution, quality scoring, and provide two reference implementations (Great Expectations, dbt-expectations).

### Concrete Deliverables
1. `packages/floe-core/src/floe_core/schemas/quality_config.py` - Configuration schemas
2. `packages/floe-core/src/floe_core/schemas/quality_score.py` - Check/result schemas
3. `packages/floe-core/src/floe_core/schemas/quality_validation.py` - Validation result schemas
4. `packages/floe-core/src/floe_core/plugins/quality.py` - Extended ABC
5. `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` - v0.4.0 extension
6. `plugins/floe-quality-gx/` - Great Expectations plugin package
7. `plugins/floe-quality-dbt/` - dbt-expectations plugin package
8. `tests/contract/test_quality_plugin_contract.py` - Contract tests

### Definition of Done
- [ ] All 47 functional requirements (FR-001 to FR-047) implemented
- [ ] All 6 user stories have passing acceptance tests
- [ ] Both plugins pass compliance tests (discovery, metadata, health_check)
- [ ] CompiledArtifacts v0.4.0 is backward compatible
- [ ] `make test` passes with >80% coverage
- [ ] Linear issues marked complete

### Must Have
- QualityPlugin ABC with validate_config(), validate_quality_gates(), run_checks(), calculate_quality_score()
- Three-tier quality configuration (Enterprise -> Domain -> Product)
- Bronze/silver/gold quality gates
- Quality score calculation (0-100)
- Error codes FLOE-DQ001 through FLOE-DQ107

### Must NOT Have (Guardrails)
- NO SQL parsing/validation in Python (dbt owns SQL)
- NO hardcoded credentials (reuse ComputePlugin connection pattern)
- NO orchestration logic outside OrchestratorPlugin
- NO breaking changes to existing QualityCheckResult/QualitySuiteResult dataclasses
- NO scope creep to CLI commands or web UI

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest with `@pytest.mark.requirement()` markers)
- **User wants tests**: YES (TDD)
- **Framework**: pytest with K8s-native integration tests

### TDD Workflow
Each TODO follows RED-GREEN-REFACTOR:
1. **RED**: Write failing test first
2. **GREEN**: Implement minimum code to pass
3. **REFACTOR**: Clean up while keeping green

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately) - Setup:
├── T001: Create floe-quality-gx package structure
├── T002: Create floe-quality-dbt package structure [P]
└── T003: Add dependencies to both packages [P]

Wave 2 (After Wave 1) - Foundation (CRITICAL BLOCKING):
├── T004-T006: Core enums and DimensionWeights [P]
├── T007-T011: Configuration models [P]
├── T012-T016: Check and result models [P]
├── T017-T018: Validation result models [P]
├── T019-T024: QualityPlugin ABC extension [P]
├── T025-T028: CompiledArtifacts extension
└── T029-T033a: Unit tests for core schemas [P]

Wave 3 (After Wave 2) - MVP User Stories (US1+US2+US3):
├── US1 (T034-T039): Provider configuration
├── US2 (T040-T046): Quality check definitions
└── US3 (T047-T065a): Runtime execution (GX + dbt plugins in parallel)

Wave 4 (After Wave 3) - P2 User Stories (US4+US5):
├── US4 (T066-T076): Quality gates enforcement [P]
└── US5 (T077-T087): Quality score calculation [P]

Wave 5 (After Wave 4) - P3 + Polish:
├── US6 (T088-T094): OpenLineage integration
├── T095-T100b: Contract and integration tests
└── T101-T106: Documentation and final validation
```

### Dependency Matrix

| Phase | Depends On | Blocks | Can Parallelize |
|-------|------------|--------|-----------------|
| Setup (1) | None | Foundation | T001, T002, T003 together |
| Foundation (2) | Setup | All user stories | Many tasks within phase |
| US1 (3) | Foundation | US3, US4 | Yes - independent |
| US2 (4) | Foundation | US3 | Yes - parallel with US1 |
| US3 (5) | US1, US2 | US5, US6 | GX and dbt in parallel |
| US4 (6) | US1 | None | Yes - parallel with US5 |
| US5 (7) | US3 | None | Yes - parallel with US4 |
| US6 (8) | US3 | None | After US5 |
| Contract (9) | All US | Polish | No |
| Polish (10) | Contract | None | Many tasks parallel |

---

## TODOs

### Phase 1: Setup (Quick)

- [ ] 1. Create plugin package structures (T001-T003)

  **What to do**:
  - Create `plugins/floe-quality-gx/` with pyproject.toml, src/, tests/
  - Create `plugins/floe-quality-dbt/` with pyproject.toml, src/, tests/
  - Add `great-expectations>=1.0.0` to floe-quality-gx
  - Add `dbt-expectations>=0.10.0` to floe-quality-dbt
  - Follow pattern from `plugins/floe-compute-duckdb/pyproject.toml`

  **Must NOT do**:
  - Do not add plugin implementation code yet
  - Do not register entry points until plugin classes exist

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Package scaffolding is straightforward file creation
  - **Skills**: [`pydantic-schemas`]
    - `pydantic-schemas`: For pyproject.toml structure

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (T001, T002, T003 all start together)
  - **Blocks**: All Phase 2 tasks
  - **Blocked By**: None

  **References**:
  - `plugins/floe-compute-duckdb/pyproject.toml` - Entry point and dependency pattern
  - `plugins/floe-compute-duckdb/src/floe_compute_duckdb/` - Package structure pattern
  - `/specs/5b-dataquality-plugin/tasks.md:25-28` - Task requirements

  **Acceptance Criteria**:
  - [ ] `ls plugins/floe-quality-gx/` shows pyproject.toml, src/, tests/
  - [ ] `ls plugins/floe-quality-dbt/` shows pyproject.toml, src/, tests/
  - [ ] `grep great-expectations plugins/floe-quality-gx/pyproject.toml` returns match
  - [ ] `grep dbt-expectations plugins/floe-quality-dbt/pyproject.toml` returns match

  **Commit**: YES
  - Message: `feat(quality): add plugin package scaffolds for GX and dbt-expectations`
  - Files: `plugins/floe-quality-gx/`, `plugins/floe-quality-dbt/`

---

### Phase 2: Foundation (CRITICAL - Blocks Everything)

- [ ] 2. Implement core quality schemas (T004-T018)

  **What to do**:
  - Copy contract schemas from `/specs/5b-dataquality-plugin/contracts/` to `packages/floe-core/src/floe_core/schemas/`
  - Create `quality_config.py` with Dimension, SeverityLevel, DimensionWeights, CalculationParameters, QualityThresholds, GateTier, QualityGates, QualityConfig
  - Create `quality_score.py` with QualityCheck, QualityCheckResult, QualitySuiteResult, QualityScore, QualitySuite
  - Create `quality_validation.py` with ValidationResult, GateResult
  - Write unit tests FIRST (TDD)

  **Must NOT do**:
  - Do not modify the contract schema semantics
  - Do not add extra fields not specified in contracts

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Schema copy + minor adjustments, well-defined task
  - **Skills**: [`pydantic-schemas`, `testing`]
    - `pydantic-schemas`: Schema creation patterns
    - `testing`: TDD workflow, pytest patterns

  **Parallelization**:
  - **Can Run In Parallel**: YES (within phase, T004-T006, T007-T011, T012-T018 can parallelize)
  - **Parallel Group**: Wave 2 (multiple subgroups)
  - **Blocks**: All user story phases (3-8)
  - **Blocked By**: Phase 1 (Setup)

  **References**:
  - `/specs/5b-dataquality-plugin/contracts/quality_config.py` - Source schemas (COPY THIS)
  - `/specs/5b-dataquality-plugin/contracts/quality_score.py` - Source schemas (COPY THIS)
  - `/specs/5b-dataquality-plugin/contracts/validation_result.py` - Source schemas (COPY THIS)
  - `packages/floe-core/src/floe_core/schemas/telemetry.py` - Schema pattern to follow
  - `/specs/5b-dataquality-plugin/tasks.md:37-91` - Task list

  **Acceptance Criteria**:
  - [ ] Test file exists: `packages/floe-core/tests/unit/test_quality_config.py`
  - [ ] `cd packages/floe-core && python -m pytest tests/unit/test_quality_config.py -v` -> PASS
  - [ ] `python -c "from floe_core.schemas.quality_config import QualityConfig"` -> no error
  - [ ] `python -c "from floe_core.schemas.quality_score import QualityScore"` -> no error

  **Commit**: YES
  - Message: `feat(quality): add core quality schemas from contracts`
  - Files: `packages/floe-core/src/floe_core/schemas/quality_*.py`, `packages/floe-core/tests/unit/test_quality_*.py`

---

- [ ] 3. Extend QualityPlugin ABC (T019-T024)

  **What to do**:
  - Add abstract method `validate_config(config: QualityConfig) -> ValidationResult`
  - Add abstract method `validate_quality_gates(models: list, gates: QualityGates) -> GateResult`
  - Add abstract method `calculate_quality_score(results: QualitySuiteResult, config: QualityConfig) -> QualityScore`
  - Add abstract method `supports_dialect(dialect: str) -> bool`
  - Add abstract method `get_lineage_emitter() -> OpenLineageEmitter | None`
  - Update existing `run_checks` signature to use `QualitySuite` parameter

  **Must NOT do**:
  - Do not remove or rename existing methods
  - Do not break backward compatibility with existing dataclasses

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: ABC extension is well-defined
  - **Skills**: [`pydantic-schemas`]
    - `pydantic-schemas`: Type hints and return types

  **Parallelization**:
  - **Can Run In Parallel**: YES (T019-T024 all modify same file but different methods)
  - **Parallel Group**: Wave 2
  - **Blocks**: All user story implementation
  - **Blocked By**: TODO 2 (schemas must exist first)

  **References**:
  - `packages/floe-core/src/floe_core/plugins/quality.py:64-181` - Existing ABC
  - `/specs/5b-dataquality-plugin/plan.md:376-391` - Method signatures
  - `/specs/5b-dataquality-plugin/spec.md:122-134` - FR-001 to FR-010

  **Acceptance Criteria**:
  - [ ] `grep -c "abstractmethod" packages/floe-core/src/floe_core/plugins/quality.py` returns `8` (5 new + 3 existing)
  - [ ] `python -c "from floe_core.plugins.quality import QualityPlugin; print([m for m in dir(QualityPlugin) if not m.startswith('_')])"` lists all methods

  **Commit**: YES
  - Message: `feat(quality): extend QualityPlugin ABC with compile-time and scoring methods`
  - Files: `packages/floe-core/src/floe_core/plugins/quality.py`

---

- [ ] 4. Extend CompiledArtifacts to v0.4.0 (T025-T028)

  **What to do**:
  - Bump version constant from 0.3.0 to 0.4.0 in `versions.py`
  - Add `quality_config: QualityConfig | None` field to CompiledArtifacts
  - Add `quality_checks: list[QualityCheck] | None` and `quality_tier` fields to ResolvedModel
  - Export new schemas from `__init__.py`
  - Add to version history

  **Must NOT do**:
  - Do not make breaking changes (new fields must be optional with defaults)
  - Do not remove existing fields

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small addition to existing schema
  - **Skills**: [`pydantic-schemas`]
    - `pydantic-schemas`: Schema extension patterns

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on TODO 2 schemas)
  - **Parallel Group**: Wave 2 (after T004-T018)
  - **Blocks**: Phase 3-5 compilation features
  - **Blocked By**: TODO 2 (quality schemas)

  **References**:
  - `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py:495-634` - Existing schema
  - `packages/floe-core/src/floe_core/schemas/versions.py` - Version constant
  - `/specs/5b-dataquality-plugin/plan.md:587-619` - Extension specification

  **Acceptance Criteria**:
  - [ ] `grep COMPILED_ARTIFACTS_VERSION packages/floe-core/src/floe_core/schemas/versions.py` shows `0.4.0`
  - [ ] `python -c "from floe_core.schemas.compiled_artifacts import CompiledArtifacts; print(CompiledArtifacts.model_fields.get('quality_config'))"` returns field info

  **Commit**: YES
  - Message: `feat(quality): extend CompiledArtifacts v0.4.0 with quality_config`
  - Files: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`, `packages/floe-core/src/floe_core/schemas/versions.py`

---

### Phase 3-5: MVP User Stories (US1 + US2 + US3) - P1 Priority

- [ ] 5. US1: Platform Team Configures Data Quality Provider (T034-T039)

  **What to do**:
  - Write unit tests for manifest quality provider validation (TDD)
  - Add quality provider configuration parsing to manifest schema
  - Implement FLOE-DQ001 error for invalid provider
  - Add quality_gates configuration parsing
  - Wire quality configuration into CompiledArtifacts during compilation

  **Must NOT do**:
  - Do not add runtime execution yet (that's US3)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Manifest parsing is well-defined
  - **Skills**: [`pydantic-schemas`, `testing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (parallel with US2)
  - **Parallel Group**: Wave 3
  - **Blocks**: US3, US4
  - **Blocked By**: Phase 2 (Foundation)

  **References**:
  - `/specs/5b-dataquality-plugin/spec.md:11-24` - US1 acceptance scenarios
  - `/specs/5b-dataquality-plugin/tasks.md:96-113` - Task list
  - `packages/floe-core/src/floe_core/schemas/manifest.py` - Manifest schema (needs extension)

  **Acceptance Criteria**:
  - [ ] `cd packages/floe-core && pytest tests/unit/test_manifest_quality.py -v` -> PASS
  - [ ] Test with invalid provider returns FLOE-DQ001 error code

  **Commit**: YES
  - Message: `feat(quality): implement US1 - platform team configures quality provider`

---

- [ ] 6. US2: Data Engineer Defines Quality Checks (T040-T046)

  **What to do**:
  - Write unit tests for quality check parsing from floe.yaml (TDD)
  - Add quality_checks[] parsing to model schema in floe_spec.py
  - Implement dbt generic test mapping (not_null, unique, accepted_values, relationships)
  - Add custom expectation support
  - Implement check deduplication (dbt takes precedence)
  - Validate column references at compile-time (FLOE-DQ105)
  - Include quality checks in ResolvedModel during compilation

  **Must NOT do**:
  - Do not implement runtime execution (that's US3)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: YAML parsing and mapping is well-defined
  - **Skills**: [`pydantic-schemas`, `testing`, `dbt-transformations`]
    - `dbt-transformations`: Understanding dbt test patterns

  **Parallelization**:
  - **Can Run In Parallel**: YES (parallel with US1)
  - **Parallel Group**: Wave 3
  - **Blocks**: US3
  - **Blocked By**: Phase 2 (Foundation)

  **References**:
  - `/specs/5b-dataquality-plugin/spec.md:26-40` - US2 acceptance scenarios
  - `/specs/5b-dataquality-plugin/tasks.md:118-137` - Task list
  - `packages/floe-core/src/floe_core/schemas/floe_spec.py` - floe.yaml schema

  **Acceptance Criteria**:
  - [ ] `cd packages/floe-core && pytest tests/unit/test_floe_yaml_quality.py -v` -> PASS
  - [ ] Quality checks appear in CompiledArtifacts.transforms.models[].quality_checks

  **Commit**: YES
  - Message: `feat(quality): implement US2 - data engineer defines quality checks`

---

- [ ] 7. US3: Data Engineer Runs Quality Checks at Runtime (T047-T065a)

  **What to do**:
  - **GX Plugin** (T051-T057):
    - Create GreatExpectationsPlugin class implementing QualityPlugin ABC
    - Implement PluginMetadata (name, version, floe_api_version)
    - Implement validate_config() for GX
    - Implement run_checks() mapping QualityCheck to GX Expectations
    - Implement GX Data Source connection using ComputePlugin connection
    - Add timeout handling with FLOE-DQ106
    - Register via entry point `floe.quality`
  - **dbt Plugin** (T058-T063):
    - Create DBTExpectationsPlugin implementing QualityPlugin ABC
    - Implement run_checks() via DBTPlugin.test_models()
    - Parse run_results.json to QualitySuiteResult
    - Register via entry point
  - **Shared** (T064-T065a):
    - Implement health_check() for both plugins
    - Implement get_config_schema() for both plugins
    - Implement supports_dialect() for DuckDB, PostgreSQL, Snowflake

  **Must NOT do**:
  - Do not implement scoring (that's US5)
  - Do not implement OpenLineage emission (that's US6)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Core implementation with multiple components
  - **Skills**: [`pydantic-schemas`, `testing`, `dagster-orchestration`]
    - `dagster-orchestration`: Runtime integration patterns

  **Parallelization**:
  - **Can Run In Parallel**: YES (GX and dbt plugins are independent)
  - **Parallel Group**: Wave 3 (T051-T057 and T058-T063 run in parallel)
  - **Blocks**: US5, US6
  - **Blocked By**: US1, US2

  **References**:
  - `/specs/5b-dataquality-plugin/spec.md:42-56` - US3 acceptance scenarios
  - `/specs/5b-dataquality-plugin/tasks.md:142-183` - Task list
  - `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py` - Plugin implementation pattern
  - `packages/floe-core/src/floe_core/plugins/quality.py` - ABC to implement

  **Acceptance Criteria**:
  - [ ] `cd plugins/floe-quality-gx && pytest tests/unit/ -v` -> PASS
  - [ ] `cd plugins/floe-quality-dbt && pytest tests/unit/ -v` -> PASS
  - [ ] Plugin discovery: `python -c "from floe_core.plugin_registry import get_registry; print(list(get_registry().list('quality')))"` shows both plugins

  **Commit**: YES (multiple commits - one per plugin)
  - Message: `feat(quality): implement US3 - GreatExpectationsPlugin runtime execution`
  - Message: `feat(quality): implement US3 - DBTExpectationsPlugin runtime execution`

---

### Phase 6-7: P2 User Stories (US4 + US5)

- [ ] 8. US4: Platform Team Enforces Quality Gates (T066-T076)

  **What to do**:
  - Write unit tests for quality gate validation
  - Implement validate_quality_gates() in both plugins
  - Implement coverage calculation (% columns with tests)
  - Implement required test type detection
  - Implement three-tier inheritance resolution (Enterprise -> Domain -> Product)
  - Implement locked setting enforcement with FLOE-DQ107
  - Wire quality gate validation into compiler with FLOE-DQ103, FLOE-DQ104

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Validation logic is well-specified
  - **Skills**: [`pydantic-schemas`, `testing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (parallel with US5)
  - **Parallel Group**: Wave 4
  - **Blocks**: None (polish only)
  - **Blocked By**: US1

  **References**:
  - `/specs/5b-dataquality-plugin/spec.md:58-72` - US4 acceptance scenarios
  - `/specs/5b-dataquality-plugin/tasks.md:188-210` - Task list

  **Acceptance Criteria**:
  - [ ] `cd packages/floe-core && pytest tests/unit/test_quality_gates.py -v` -> PASS
  - [ ] Gold tier with 80% coverage fails with FLOE-DQ103

  **Commit**: YES
  - Message: `feat(quality): implement US4 - quality gates enforcement`

---

- [ ] 9. US5: Data Engineer Views Quality Score (T077-T087)

  **What to do**:
  - Write unit tests for quality score calculation
  - Implement calculate_quality_score() in both plugins
  - Implement dimension score calculation (per-dimension weighted average)
  - Implement influence capping (max_positive, max_negative)
  - Implement unified scoring combining dbt tests and plugin checks
  - Implement warn_score threshold warning emission
  - Implement min_score threshold enforcement (FLOE-DQ102 on failure)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Scoring algorithm is specified in plan.md
  - **Skills**: [`pydantic-schemas`, `testing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (parallel with US4)
  - **Parallel Group**: Wave 4
  - **Blocks**: US6
  - **Blocked By**: US3

  **References**:
  - `/specs/5b-dataquality-plugin/spec.md:74-88` - US5 acceptance scenarios
  - `/specs/5b-dataquality-plugin/tasks.md:215-238` - Task list
  - `/specs/5b-dataquality-plugin/plan.md:328-368` - Score calculation algorithm

  **Acceptance Criteria**:
  - [ ] `cd packages/floe-core && pytest tests/unit/test_quality_scoring.py -v` -> PASS
  - [ ] All checks pass -> score = 100
  - [ ] Score below warn_score emits warning

  **Commit**: YES
  - Message: `feat(quality): implement US5 - quality score calculation`

---

### Phase 8: P3 User Story (US6)

- [ ] 10. US6: Operations Team Monitors Quality via OpenLineage (T088-T094)

  **What to do**:
  - Write unit tests for OpenLineage FAIL event emission
  - Implement get_lineage_emitter() in both plugins
  - Create OpenLineage facet for quality check results
  - Implement FAIL event emission for failed checks
  - Add graceful degradation when lineage backend not configured

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Lineage integration is isolated
  - **Skills**: [`dagster-orchestration`, `testing`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on US3)
  - **Parallel Group**: Wave 5
  - **Blocks**: None
  - **Blocked By**: US3

  **References**:
  - `/specs/5b-dataquality-plugin/spec.md:90-104` - US6 acceptance scenarios
  - `/specs/5b-dataquality-plugin/tasks.md:243-260` - Task list

  **Acceptance Criteria**:
  - [ ] `cd plugins/floe-quality-gx && pytest tests/unit/test_lineage.py -v` -> PASS
  - [ ] Failed check emits OpenLineage FAIL event

  **Commit**: YES
  - Message: `feat(quality): implement US6 - OpenLineage integration`

---

### Phase 9-10: Contract Tests & Polish

- [ ] 11. Contract and Integration Tests (T095-T100b)

  **What to do**:
  - Create contract test for QualityPlugin ABC compliance (FR-039)
  - Create contract test for CompiledArtifacts v0.4.0 schema stability
  - Create contract test for floe-core -> plugin quality config passing
  - Create integration test for GreatExpectationsPlugin with DuckDB
  - Create integration test for DBTExpectationsPlugin with dbt-core
  - Create integration test for unified quality score
  - Create performance test validating 100+ checks execute in <100ms

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration tests need careful orchestration
  - **Skills**: [`testing`, `dagster-orchestration`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (contract and integration tests parallel)
  - **Parallel Group**: Wave 5
  - **Blocks**: Polish phase
  - **Blocked By**: All user stories

  **References**:
  - `/specs/5b-dataquality-plugin/tasks.md:265-283` - Task list
  - `tests/contract/` - Existing contract test patterns

  **Acceptance Criteria**:
  - [ ] `pytest tests/contract/test_quality_plugin_contract.py -v` -> PASS
  - [ ] `cd plugins/floe-quality-gx && pytest tests/integration/ -v` -> PASS
  - [ ] Performance test: 100 checks in <100ms

  **Commit**: YES
  - Message: `test(quality): add contract and integration tests`

---

- [ ] 12. Documentation and Final Validation (T101-T106)

  **What to do**:
  - Update quickstart.md with working examples for bronze/silver/gold tiers
  - Add quality plugin configuration examples to docs/
  - Validate all error codes (FLOE-DQ001-107) have proper messages
  - Add OpenTelemetry trace spans for quality check execution
  - Run /speckit.test-review to validate test quality
  - Run full test suite and verify >80% coverage

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation focus
  - **Skills**: [`testing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (T101-T104 parallel)
  - **Parallel Group**: Wave 5
  - **Blocks**: None (final)
  - **Blocked By**: Contract tests

  **References**:
  - `/specs/5b-dataquality-plugin/tasks.md:288-298` - Task list
  - `docs/guides/` - Documentation location

  **Acceptance Criteria**:
  - [ ] `grep -r "FLOE-DQ" packages/floe-core/src/` shows all 7 error codes
  - [ ] `make test` -> PASS with >80% coverage
  - [ ] Documentation files exist

  **Commit**: YES
  - Message: `docs(quality): add quality plugin documentation and finalize`

---

## Commit Strategy

| After TODO | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(quality): add plugin package scaffolds` | `plugins/floe-quality-*/` | `ls plugins/floe-quality-*` |
| 2 | `feat(quality): add core quality schemas` | `floe_core/schemas/quality_*.py` | `pytest test_quality_*.py` |
| 3 | `feat(quality): extend QualityPlugin ABC` | `floe_core/plugins/quality.py` | `python -c "import ..."` |
| 4 | `feat(quality): extend CompiledArtifacts v0.4.0` | `compiled_artifacts.py, versions.py` | `python -c "import ..."` |
| 5 | `feat(quality): implement US1` | `manifest.py, quality_validation.py` | `pytest test_manifest_quality.py` |
| 6 | `feat(quality): implement US2` | `floe_spec.py, dbt_test_mapper.py` | `pytest test_floe_yaml_quality.py` |
| 7a | `feat(quality): implement US3 GX plugin` | `plugins/floe-quality-gx/` | `pytest tests/unit/` |
| 7b | `feat(quality): implement US3 dbt plugin` | `plugins/floe-quality-dbt/` | `pytest tests/unit/` |
| 8 | `feat(quality): implement US4` | `coverage_calculator.py, inheritance_resolver.py` | `pytest test_quality_gates.py` |
| 9 | `feat(quality): implement US5` | `dimension_scorer.py, unified_scorer.py` | `pytest test_quality_scoring.py` |
| 10 | `feat(quality): implement US6` | `quality_facet.py, lineage.py` | `pytest test_lineage.py` |
| 11 | `test(quality): add contract and integration tests` | `tests/contract/, tests/integration/` | `pytest tests/` |
| 12 | `docs(quality): finalize documentation` | `docs/guides/, quickstart.md` | `make test` |

---

## Success Criteria

### Verification Commands
```bash
# Schema imports
python -c "from floe_core.schemas.quality_config import QualityConfig"
python -c "from floe_core.schemas.quality_score import QualityScore"
python -c "from floe_core.plugins.quality import QualityPlugin"

# Plugin discovery
python -c "from floe_core.plugin_registry import get_registry; print(list(get_registry().list('quality')))"

# Unit tests
cd packages/floe-core && pytest tests/unit/test_quality*.py -v

# Plugin tests
cd plugins/floe-quality-gx && pytest tests/ -v
cd plugins/floe-quality-dbt && pytest tests/ -v

# Contract tests
pytest tests/contract/test_quality_plugin_contract.py -v

# Full suite
make test  # Expected: >80% coverage, 0 failures
```

### Final Checklist
- [ ] All 47 functional requirements (FR-001 to FR-047) implemented
- [ ] All 6 user stories pass acceptance tests
- [ ] Both plugins discovered via entry points
- [ ] CompiledArtifacts v0.4.0 backward compatible
- [ ] All error codes (FLOE-DQ001-107) documented
- [ ] >80% test coverage
- [ ] Linear issues marked complete

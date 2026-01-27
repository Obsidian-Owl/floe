# Tasks: Data Quality Plugin (Epic 5B)

**Input**: Design documents from `/specs/5b-dataquality-plugin/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/
**Branch**: `5b-dataquality-plugin`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US6)

## Path Conventions

- **floe-core schemas**: `packages/floe-core/src/floe_core/schemas/`
- **floe-core plugins**: `packages/floe-core/src/floe_core/plugins/`
- **Plugin packages**: `plugins/floe-quality-{gx|dbt}/`
- **Contract tests**: `tests/contract/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for both plugin packages

- [ ] T001 Create floe-quality-gx plugin package structure in plugins/floe-quality-gx/ with pyproject.toml, src/, tests/
- [ ] T002 [P] Create floe-quality-dbt plugin package structure in plugins/floe-quality-dbt/ with pyproject.toml, src/, tests/
- [ ] T003 [P] Add great-expectations>=1.0.0 and dbt-expectations>=0.10.0 dependencies to respective plugin packages

---

## Phase 2: Foundational (Core Schemas - Blocking Prerequisites)

**Purpose**: Core schemas and ABC extensions that ALL user stories depend on. MUST complete before ANY user story work.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Core Enums and Base Models

- [ ] T004 Create Dimension enum (completeness, accuracy, validity, consistency, timeliness) in packages/floe-core/src/floe_core/schemas/quality_config.py
- [ ] T005 [P] Create SeverityLevel enum (critical, warning, info) in packages/floe-core/src/floe_core/schemas/quality_config.py
- [ ] T006 [P] Create DimensionWeights model with weights_must_sum_to_one validator in packages/floe-core/src/floe_core/schemas/quality_config.py

### Configuration Models

- [ ] T007 Create CalculationParameters model (baseline_score, max_positive_influence, max_negative_influence, severity_weights) in packages/floe-core/src/floe_core/schemas/quality_config.py
- [ ] T008 [P] Create QualityThresholds model (min_score, warn_score) in packages/floe-core/src/floe_core/schemas/quality_config.py
- [ ] T009 [P] Create GateTier model (min_test_coverage, required_tests, min_score, overridable) in packages/floe-core/src/floe_core/schemas/quality_config.py
- [ ] T010 Create QualityGates model (bronze, silver, gold tiers) with defaults in packages/floe-core/src/floe_core/schemas/quality_config.py
- [ ] T011 Create QualityConfig model with provider, quality_gates, dimension_weights, calculation, thresholds in packages/floe-core/src/floe_core/schemas/quality_config.py

### Quality Check and Result Models

- [ ] T012 Create QualityCheck model (name, type, column, dimension, severity, custom_weight, parameters, enabled) in packages/floe-core/src/floe_core/schemas/quality_score.py
- [ ] T013 [P] Create QualityCheckResult model (check_name, passed, dimension, severity, records_checked, records_failed, execution_time_ms, details, error_message) in packages/floe-core/src/floe_core/schemas/quality_score.py
- [ ] T014 [P] Create QualitySuite model (model_name, checks, timeout_seconds, fail_fast) in packages/floe-core/src/floe_core/schemas/quality_score.py
- [ ] T015 Create QualitySuiteResult model (suite_name, model_name, passed, checks, execution_time_ms, summary, timestamp) in packages/floe-core/src/floe_core/schemas/quality_score.py
- [ ] T016 Create QualityScore model (overall, dimension_scores, checks_passed, checks_failed, dbt_tests_passed, dbt_tests_failed, model_name, timestamp) in packages/floe-core/src/floe_core/schemas/quality_score.py

### Validation Result Models

- [ ] T017 Create ValidationResult model (success, errors, warnings) in packages/floe-core/src/floe_core/schemas/quality_validation.py
- [ ] T018 [P] Create GateResult model (passed, tier, coverage_actual, coverage_required, missing_tests, violations) in packages/floe-core/src/floe_core/schemas/quality_validation.py

### QualityPlugin ABC Extension

- [ ] T019 Extend QualityPlugin ABC with validate_config(config: QualityConfig) -> ValidationResult method in packages/floe-core/src/floe_core/plugins/quality.py
- [ ] T020 [P] Add validate_quality_gates(models: list, gates: QualityGates) -> GateResult method to QualityPlugin ABC in packages/floe-core/src/floe_core/plugins/quality.py
- [ ] T021 [P] Add calculate_quality_score(results: QualitySuiteResult, config: QualityConfig) -> QualityScore method to QualityPlugin ABC in packages/floe-core/src/floe_core/plugins/quality.py
- [ ] T022 [P] Add supports_dialect(dialect: str) -> bool method to QualityPlugin ABC in packages/floe-core/src/floe_core/plugins/quality.py
- [ ] T023 [P] Add get_lineage_emitter() -> OpenLineageEmitter | None method to QualityPlugin ABC in packages/floe-core/src/floe_core/plugins/quality.py
- [ ] T024 Update existing run_checks method signature to use QualitySuite and return enhanced QualitySuiteResult in packages/floe-core/src/floe_core/plugins/quality.py

### CompiledArtifacts Extension

- [ ] T025 Bump CompiledArtifacts version from 0.3.0 to 0.4.0 in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T026 Add quality_config: QualityConfig | None field to CompiledArtifacts in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T027 Add quality_checks: list[QualityCheck] | None and quality_tier fields to ResolvedModel in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py

### Schema Exports

- [ ] T028 Export all quality schemas from packages/floe-core/src/floe_core/schemas/__init__.py

### Unit Tests for Core Schemas

- [ ] T029 Create unit tests for Dimension and SeverityLevel enums in packages/floe-core/tests/unit/test_quality_config.py
- [ ] T030 [P] Create unit tests for DimensionWeights validator (must sum to 1.0) in packages/floe-core/tests/unit/test_quality_config.py
- [ ] T031 [P] Create unit tests for QualityConfig, QualityGates, GateTier models in packages/floe-core/tests/unit/test_quality_config.py
- [ ] T032 [P] Create unit tests for QualityCheck, QualitySuiteResult, QualityScore models in packages/floe-core/tests/unit/test_quality_score.py
- [ ] T033 [P] Create unit tests for ValidationResult and GateResult models in packages/floe-core/tests/unit/test_quality_validation.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Platform Team Configures Data Quality Provider (Priority: P1) 🎯 MVP

**Goal**: Platform teams can configure a quality provider and quality gates in manifest.yaml

**Independent Test**: Configure manifest.yaml with `plugins.quality.provider: great_expectations` and validate configuration is accepted

### Tests for User Story 1

- [ ] T034 [P] [US1] Create unit test for manifest quality provider validation in packages/floe-core/tests/unit/test_manifest_quality.py
- [ ] T035 [P] [US1] Create unit test for FLOE-DQ001 error on invalid provider in packages/floe-core/tests/unit/test_manifest_quality.py

### Implementation for User Story 1

- [ ] T036 [US1] Add quality provider configuration parsing to manifest schema in packages/floe-core/src/floe_core/schemas/manifest.py
- [ ] T037 [US1] Implement quality provider validation with FLOE-DQ001 error in packages/floe-core/src/floe_core/validation/quality_validation.py
- [ ] T038 [US1] Add quality_gates configuration parsing to manifest schema in packages/floe-core/src/floe_core/schemas/manifest.py
- [ ] T039 [US1] Wire quality configuration into CompiledArtifacts during compilation in packages/floe-core/src/floe_core/compiler/quality_compiler.py

**Checkpoint**: User Story 1 complete - platform teams can configure quality providers

---

## Phase 4: User Story 2 - Data Engineer Defines Quality Checks (Priority: P1)

**Goal**: Data engineers can define quality checks in floe.yaml that are included in compiled artifacts

**Independent Test**: Add quality_checks to floe.yaml and verify they appear in CompiledArtifacts

### Tests for User Story 2

- [ ] T040 [P] [US2] Create unit test for quality check parsing from floe.yaml in packages/floe-core/tests/unit/test_floe_yaml_quality.py
- [ ] T041 [P] [US2] Create unit test for dbt test mapping to quality check format in packages/floe-core/tests/unit/test_floe_yaml_quality.py

### Implementation for User Story 2

- [ ] T042 [US2] Add quality_checks[] parsing to model schema in packages/floe-core/src/floe_core/schemas/floe_spec.py
- [ ] T043 [US2] Implement dbt generic test mapping (not_null, unique, accepted_values, relationships) to QualityCheck format in packages/floe-core/src/floe_core/compiler/dbt_test_mapper.py
- [ ] T044 [US2] Add custom expectation support (expect_column_values_to_be_between, etc.) in packages/floe-core/src/floe_core/compiler/dbt_test_mapper.py
- [ ] T045 [US2] Validate quality check column references at compile-time (FLOE-DQ105) in packages/floe-core/src/floe_core/validation/quality_validation.py
- [ ] T046 [US2] Include quality checks in ResolvedModel during compilation in packages/floe-core/src/floe_core/compiler/quality_compiler.py

**Checkpoint**: User Story 2 complete - data engineers can define quality checks

---

## Phase 5: User Story 3 - Data Engineer Runs Quality Checks at Runtime (Priority: P1)

**Goal**: Quality checks execute automatically after dbt model materialization

**Independent Test**: Run a Dagster job with dbt models and quality checks, verify checks execute and return results

### Tests for User Story 3

- [ ] T047 [P] [US3] Create unit test for GreatExpectationsPlugin.run_checks() in plugins/floe-quality-gx/tests/unit/test_plugin.py
- [ ] T048 [P] [US3] Create unit test for DBTExpectationsPlugin.run_checks() in plugins/floe-quality-dbt/tests/unit/test_plugin.py
- [ ] T049 [P] [US3] Create unit test for FLOE-DQ102 error on check failures in plugins/floe-quality-gx/tests/unit/test_plugin.py
- [ ] T050 [P] [US3] Create unit test for FLOE-DQ106 timeout handling in plugins/floe-quality-gx/tests/unit/test_plugin.py

### Implementation for User Story 3 - Great Expectations Plugin

- [ ] T051 [US3] Create GreatExpectationsPlugin class implementing QualityPlugin ABC in plugins/floe-quality-gx/src/floe_quality_gx/plugin.py
- [ ] T052 [US3] Implement PluginMetadata (name, version, floe_api_version) for GreatExpectationsPlugin in plugins/floe-quality-gx/src/floe_quality_gx/plugin.py
- [ ] T053 [US3] Implement validate_config() for GX plugin in plugins/floe-quality-gx/src/floe_quality_gx/plugin.py
- [ ] T054 [US3] Implement run_checks() mapping floe QualityCheck to GX Expectations in plugins/floe-quality-gx/src/floe_quality_gx/plugin.py
- [ ] T055 [US3] Implement GX Data Source connection using ComputePlugin connection config in plugins/floe-quality-gx/src/floe_quality_gx/datasource.py
- [ ] T056 [US3] Add timeout handling with FLOE-DQ106 error in plugins/floe-quality-gx/src/floe_quality_gx/plugin.py
- [ ] T057 [US3] Register GreatExpectationsPlugin via entry point floe.quality in plugins/floe-quality-gx/pyproject.toml

### Implementation for User Story 3 - dbt-expectations Plugin

- [ ] T058 [US3] Create DBTExpectationsPlugin class implementing QualityPlugin ABC in plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py
- [ ] T059 [US3] Implement PluginMetadata for DBTExpectationsPlugin in plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py
- [ ] T060 [US3] Implement validate_config() for dbt-expectations plugin in plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py
- [ ] T061 [US3] Implement run_checks() executing quality checks as dbt tests via DBTPlugin.test_models() in plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py
- [ ] T062 [US3] Implement run_results.json parsing to QualitySuiteResult conversion in plugins/floe-quality-dbt/src/floe_quality_dbt/result_parser.py
- [ ] T063 [US3] Register DBTExpectationsPlugin via entry point floe.quality in plugins/floe-quality-dbt/pyproject.toml

### Shared Runtime Infrastructure

- [ ] T064 [US3] Implement health_check() for both plugins returning HealthStatus in plugins/floe-quality-gx/src/floe_quality_gx/plugin.py and plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py
- [ ] T065 [US3] Implement supports_dialect() for DuckDB, PostgreSQL, Snowflake in both plugins

**Checkpoint**: User Story 3 complete - quality checks execute at runtime

---

## Phase 6: User Story 4 - Platform Team Enforces Quality Gates (Priority: P2)

**Goal**: Quality gates enforce minimum coverage requirements per tier

**Independent Test**: Configure gold-tier with 100% coverage, verify compilation fails when coverage is 80%

### Tests for User Story 4

- [ ] T066 [P] [US4] Create unit test for quality gate validation (min_test_coverage) in packages/floe-core/tests/unit/test_quality_gates.py
- [ ] T067 [P] [US4] Create unit test for FLOE-DQ103 coverage violation error in packages/floe-core/tests/unit/test_quality_gates.py
- [ ] T068 [P] [US4] Create unit test for FLOE-DQ104 missing required tests error in packages/floe-core/tests/unit/test_quality_gates.py
- [ ] T069 [P] [US4] Create unit test for FLOE-DQ107 locked setting override error in packages/floe-core/tests/unit/test_quality_gates.py

### Implementation for User Story 4

- [ ] T070 [US4] Implement validate_quality_gates() in GreatExpectationsPlugin in plugins/floe-quality-gx/src/floe_quality_gx/plugin.py
- [ ] T071 [P] [US4] Implement validate_quality_gates() in DBTExpectationsPlugin in plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py
- [ ] T072 [US4] Implement coverage calculation (% columns with tests) in packages/floe-core/src/floe_core/validation/coverage_calculator.py
- [ ] T073 [US4] Implement required test type detection in packages/floe-core/src/floe_core/validation/coverage_calculator.py
- [ ] T074 [US4] Implement three-tier inheritance resolution (Enterprise → Domain → Product) in packages/floe-core/src/floe_core/compiler/inheritance_resolver.py
- [ ] T075 [US4] Implement locked setting (overridable: false) enforcement with FLOE-DQ107 in packages/floe-core/src/floe_core/compiler/inheritance_resolver.py
- [ ] T076 [US4] Wire quality gate validation into compiler with FLOE-DQ103, FLOE-DQ104 errors in packages/floe-core/src/floe_core/compiler/quality_compiler.py

**Checkpoint**: User Story 4 complete - quality gates are enforced

---

## Phase 7: User Story 5 - Data Engineer Views Quality Score (Priority: P2)

**Goal**: Data engineers can see a quality score (0-100) incorporating both dbt tests and plugin checks

**Independent Test**: Run quality checks and verify calculated score reflects weighted pass rate

### Tests for User Story 5

- [ ] T077 [P] [US5] Create unit test for quality score calculation (all pass = 100) in packages/floe-core/tests/unit/test_quality_scoring.py
- [ ] T078 [P] [US5] Create unit test for weighted score calculation with severities in packages/floe-core/tests/unit/test_quality_scoring.py
- [ ] T079 [P] [US5] Create unit test for influence capping (baseline + delta) in packages/floe-core/tests/unit/test_quality_scoring.py
- [ ] T080 [P] [US5] Create unit test for unified score with dbt tests and plugin checks in packages/floe-core/tests/unit/test_quality_scoring.py

### Implementation for User Story 5

- [ ] T081 [US5] Implement calculate_quality_score() in GreatExpectationsPlugin in plugins/floe-quality-gx/src/floe_quality_gx/plugin.py
- [ ] T082 [P] [US5] Implement calculate_quality_score() in DBTExpectationsPlugin in plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py
- [ ] T083 [US5] Implement dimension score calculation (per-dimension weighted average) in packages/floe-core/src/floe_core/scoring/dimension_scorer.py
- [ ] T084 [US5] Implement influence capping (max_positive, max_negative) in packages/floe-core/src/floe_core/scoring/score_calculator.py
- [ ] T085 [US5] Implement unified scoring combining dbt tests (from DBTRunResult) and plugin checks in packages/floe-core/src/floe_core/scoring/unified_scorer.py
- [ ] T086 [US5] Implement warn_score threshold warning emission in packages/floe-core/src/floe_core/scoring/score_calculator.py
- [ ] T087 [US5] Implement min_score threshold enforcement (FLOE-DQ102 on failure) in packages/floe-core/src/floe_core/scoring/score_calculator.py

**Checkpoint**: User Story 5 complete - quality scores are calculated and displayed

---

## Phase 8: User Story 6 - Operations Team Monitors Quality via OpenLineage (Priority: P3)

**Goal**: Quality check failures emit OpenLineage FAIL events for observability

**Independent Test**: Run failing quality checks and verify OpenLineage events are emitted

### Tests for User Story 6

- [ ] T088 [P] [US6] Create unit test for OpenLineage FAIL event emission on check failure in plugins/floe-quality-gx/tests/unit/test_lineage.py
- [ ] T089 [P] [US6] Create unit test for graceful handling when lineage backend not configured in plugins/floe-quality-gx/tests/unit/test_lineage.py

### Implementation for User Story 6

- [ ] T090 [US6] Implement get_lineage_emitter() in GreatExpectationsPlugin in plugins/floe-quality-gx/src/floe_quality_gx/plugin.py
- [ ] T091 [P] [US6] Implement get_lineage_emitter() in DBTExpectationsPlugin in plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py
- [ ] T092 [US6] Create OpenLineage facet for quality check results in packages/floe-core/src/floe_core/lineage/quality_facet.py
- [ ] T093 [US6] Implement FAIL event emission for failed checks in plugins/floe-quality-gx/src/floe_quality_gx/lineage.py
- [ ] T094 [US6] Add graceful degradation when lineage backend not configured in plugins/floe-quality-gx/src/floe_quality_gx/lineage.py

**Checkpoint**: User Story 6 complete - OpenLineage integration working

---

## Phase 9: Contract Tests & Integration

**Purpose**: Cross-package contract tests and integration validation

### Contract Tests

- [ ] T095 Create contract test for QualityPlugin ABC compliance (discovery, metadata, health_check) in tests/contract/test_quality_plugin_contract.py
- [ ] T096 [P] Create contract test for CompiledArtifacts v0.4.0 schema stability in tests/contract/test_compiled_artifacts_quality.py
- [ ] T097 [P] Create contract test for floe-core → plugin quality config passing in tests/contract/test_quality_config_contract.py

### Integration Tests

- [ ] T098 Create integration test for GreatExpectationsPlugin with DuckDB in plugins/floe-quality-gx/tests/integration/test_gx_duckdb.py
- [ ] T099 [P] Create integration test for DBTExpectationsPlugin with dbt-core in plugins/floe-quality-dbt/tests/integration/test_dbt_integration.py
- [ ] T100 Create integration test for unified quality score (dbt + plugin checks) in tests/integration/test_unified_scoring.py

**Checkpoint**: All contract and integration tests passing

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and final validation

- [ ] T101 [P] Update quickstart.md with working examples for all three tiers in specs/5b-dataquality-plugin/quickstart.md
- [ ] T102 [P] Add quality plugin configuration examples to docs/ in docs/guides/quality-plugin.md
- [ ] T103 Validate all error codes (FLOE-DQ001-107) have proper messages and resolution hints
- [ ] T104 [P] Add OpenTelemetry trace spans for quality check execution in both plugins
- [ ] T105 Run /speckit.test-review to validate test quality before PR
- [ ] T106 Run full test suite (make test) and verify >80% coverage

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phases 3-8)**: All depend on Foundational phase completion
  - US1, US2, US3 are P1 priority (implement first)
  - US4, US5 are P2 priority (implement after P1 complete)
  - US6 is P3 priority (implement last)
- **Contract Tests (Phase 9)**: Depends on all user stories
- **Polish (Phase 10)**: Depends on contract tests

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational - No dependencies on other stories
- **US2 (P1)**: Can start after Foundational - No dependencies on other stories
- **US3 (P1)**: Depends on US1 (provider config) and US2 (check definitions)
- **US4 (P2)**: Can start after US1 - depends on quality gates being parseable
- **US5 (P2)**: Depends on US3 (runtime results to score)
- **US6 (P3)**: Depends on US3 (check execution to emit events)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models/schemas before services
- Validation before compilation
- Core implementation before integration
- Plugin implementations can proceed in parallel (GX and dbt-expectations)

### Parallel Opportunities

**Phase 2 (Foundational)**:
```
T004, T005, T006 can run in parallel (different enum/models)
T007, T008, T009 can run in parallel (different config models)
T012, T013, T014 can run in parallel (different result models)
T019, T020, T021, T022, T023 can run in parallel (different ABC methods)
T029, T030, T031, T032, T033 can run in parallel (different test files)
```

**Phase 5 (US3 Runtime)**:
```
T047, T048, T049, T050 can run in parallel (unit tests)
GX plugin (T051-T057) and dbt plugin (T058-T063) can run in parallel
```

**Phase 6-8 (US4-US6)**:
```
GX and dbt plugin implementations can always run in parallel
```

---

## Parallel Example: Foundational Phase

```bash
# Launch enum and model tasks together:
Task: T004 "Create Dimension enum in quality_config.py"
Task: T005 "Create SeverityLevel enum in quality_config.py"
Task: T006 "Create DimensionWeights model in quality_config.py"

# Launch ABC extension methods together:
Task: T019 "Add validate_config method to QualityPlugin ABC"
Task: T020 "Add validate_quality_gates method to QualityPlugin ABC"
Task: T021 "Add calculate_quality_score method to QualityPlugin ABC"
Task: T022 "Add supports_dialect method to QualityPlugin ABC"
Task: T023 "Add get_lineage_emitter method to QualityPlugin ABC"
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: US1 - Provider Configuration
4. Complete Phase 4: US2 - Check Definitions
5. Complete Phase 5: US3 - Runtime Execution
6. **STOP and VALIDATE**: Test quality checks execute end-to-end
7. Deploy MVP if ready

### Incremental Delivery

1. Setup + Foundational → Core schemas ready
2. Add US1 + US2 → Configuration and definitions working
3. Add US3 → Runtime execution working (MVP!)
4. Add US4 → Quality gates enforced
5. Add US5 → Quality scores visible
6. Add US6 → OpenLineage integration
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (Provider Config) → US4 (Quality Gates)
   - Developer B: US2 (Check Definitions) → US5 (Scoring)
   - Developer C: US3 GX Plugin → US6 (Lineage)
   - Developer D: US3 dbt Plugin
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Both plugin implementations (GX and dbt-expectations) follow same ABC interface
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- FR references: See spec.md for full functional requirements

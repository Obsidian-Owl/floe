# Epic 5B Data Quality Plugin - Remaining Implementation Plan

## TL;DR

> **Quick Summary**: Complete ALL remaining Data Quality Plugin tasks - runtime execution (run_checks), quality scoring (dimension weights, influence capping), OpenLineage integration, contract tests, integration tests, and polish. NO deferrals.
> 
> **Deliverables**:
> - Fully functional run_checks/run_suite in both GX and dbt plugins
> - Quality scoring module with proper weighted calculation
> - OpenLineage FAIL event emission
> - Contract tests for QualityPlugin ABC
> - Integration tests with DuckDB
> - Performance tests for 100+ checks
> - Documentation updates
> 
> **Estimated Effort**: Large (40+ tasks across 5 phases)
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: US3 Runtime → US5 Scoring → US6 Lineage → Tests → Polish

---

## Context

### Original Request
Complete ALL remaining tasks for Epic 5B Data Quality Plugin. User explicitly stated: "All tasks must be completed - NO deferrals" and "they never agreed to defer tasks."

### Current State (Verified 2026-01-28)

**COMPLETED ✓**:
- Phase 1: Plugin package structure (both packages exist)
- Phase 2: Core schemas (quality_config.py, quality_score.py, quality_validation.py, quality_errors.py)
- US1: Platform configures quality provider
- US2: Data engineer defines quality checks
- US4: Quality gates enforcement
- Partial US3: validate_config(), validate_quality_gates(), health_check(), get_config_schema(), supports_dialect()

**INCOMPLETE ⏳**:
- US3 Runtime: run_checks/run_suite are STUBS with TODO comments
- US5 Quality Scoring: Basic calculate_quality_score exists but simplistic (100 or 0)
- US6 OpenLineage: get_lineage_emitter() returns None
- Contract/Integration tests: Not started
- Polish: Not started

### Key File Locations

```
# Existing Plugin Files (need completion)
plugins/floe-quality-gx/src/floe_quality_gx/plugin.py      # run_checks TODO at line 117
plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py    # run_checks TODO at line 117

# Existing Core Schemas
packages/floe-core/src/floe_core/schemas/quality_config.py
packages/floe-core/src/floe_core/schemas/quality_score.py
packages/floe-core/src/floe_core/schemas/quality_validation.py
packages/floe-core/src/floe_core/quality_errors.py

# To Be Created
packages/floe-core/src/floe_core/scoring/dimension_scorer.py
packages/floe-core/src/floe_core/scoring/score_calculator.py
packages/floe-core/src/floe_core/scoring/unified_scorer.py
packages/floe-core/src/floe_core/lineage/quality_facet.py
plugins/floe-quality-gx/src/floe_quality_gx/datasource.py
plugins/floe-quality-gx/src/floe_quality_gx/lineage.py
plugins/floe-quality-dbt/src/floe_quality_dbt/result_parser.py
tests/contract/test_quality_plugin_contract.py
```

---

## Work Objectives

### Core Objective
Complete all remaining Data Quality Plugin implementation to enable runtime quality check execution, proper quality scoring, and OpenLineage observability.

### Concrete Deliverables
1. Working run_checks() that executes Great Expectations validations
2. Working run_checks() that executes dbt tests via DBTPlugin
3. Quality scoring module with dimension weights and influence capping
4. OpenLineage FAIL event emission on check failures
5. Contract tests validating QualityPlugin ABC compliance
6. Integration tests with real DuckDB database
7. Performance tests validating 100+ checks in <100ms

### Definition of Done
- [ ] `cd plugins/floe-quality-gx && pytest tests/ -v` → ALL PASS
- [ ] `cd plugins/floe-quality-dbt && pytest tests/ -v` → ALL PASS
- [ ] `pytest tests/contract/test_quality_plugin_contract.py -v` → PASS
- [ ] `make test` → >80% coverage, 0 failures
- [ ] All error codes (FLOE-DQ001-107) documented with resolution hints

### Must Have
- run_checks() returns real check results (not empty stubs)
- Quality score uses three-layer calculation (dimensions, severity, influence capping)
- OpenLineage FAIL events emitted for failed checks
- Contract tests verify ABC compliance
- Integration tests with DuckDB

### Must NOT Have (Guardrails)
- NO SQL parsing in Python (dbt owns SQL)
- NO hardcoded database credentials
- NO breaking changes to existing schemas
- NO scope creep to CLI or UI
- NO changes to already-completed phases (US1, US2, US4)
- NO additional quality providers (only GX and dbt-expectations)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest with @pytest.mark.requirement)
- **User wants tests**: YES (TDD)
- **Framework**: pytest with fixtures in conftest.py

### TDD Workflow
Each TODO follows RED-GREEN-REFACTOR:
1. **RED**: Write failing test first
2. **GREEN**: Implement minimum code to pass
3. **REFACTOR**: Clean up while keeping green

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately) - US3 Runtime Tests + Implementation:
├── TODO 1: GX run_checks unit tests (T047, T049, T050, T050a)
├── TODO 2: dbt run_checks unit tests (T048)
├── TODO 3: GX run_checks implementation (T051-T056)
└── TODO 4: dbt run_checks implementation (T058-T062)

Wave 2 (After Wave 1) - US5 Quality Scoring:
├── TODO 5: Quality scoring unit tests (T077-T080)
└── TODO 6: Quality scoring implementation (T081-T087)

Wave 3 (After Wave 2) - US6 OpenLineage:
├── TODO 7: OpenLineage unit tests (T088-T089)
└── TODO 8: OpenLineage implementation (T090-T094)

Wave 4 (After Wave 3) - Contract/Integration/Polish:
├── TODO 9: Contract tests (T095-T097)
├── TODO 10: Integration tests (T098-T100b)
└── TODO 11: Documentation and polish (T101-T106)
```

### Dependency Matrix

| TODO | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 (GX tests) | None | 3 | 2, 4 |
| 2 (dbt tests) | None | 4 | 1, 3 |
| 3 (GX impl) | 1 | 5, 6, 7 | 4 |
| 4 (dbt impl) | 2 | 5, 6, 7 | 3 |
| 5 (score tests) | None | 6 | 7 |
| 6 (score impl) | 3, 4, 5 | 9, 10 | 8 |
| 7 (lineage tests) | None | 8 | 5 |
| 8 (lineage impl) | 3, 4, 7 | 9, 10 | 6 |
| 9 (contract) | 6, 8 | 11 | 10 |
| 10 (integration) | 6, 8 | 11 | 9 |
| 11 (polish) | 9, 10 | None | None |

---

## TODOs

### TODO 1: GX Plugin run_checks Unit Tests (T047, T049, T050, T050a)

**What to do**:
- Enhance existing test_plugin.py with tests for ACTUAL GX execution
- Add test for run_checks with mocked GX context returning real results
- Add test for FLOE-DQ102 error emission when checks fail
- Add test for FLOE-DQ106 timeout handling (use pytest timeout)
- Add test for fail_fast behavior (stops on first failure)

**Must NOT do**:
- Do not require real GX installation for unit tests (mock it)
- Do not change existing passing tests

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: Well-defined test additions following existing patterns
- **Skills**: [`testing`]
  - `testing`: TDD patterns, pytest fixtures, mocking

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with TODO 2, 3, 4)
- **Blocks**: TODO 3 (implementation)
- **Blocked By**: None

**References**:
- `plugins/floe-quality-gx/tests/unit/test_plugin.py:108-122` - Existing run_checks tests (enhance these)
- `plugins/floe-quality-gx/tests/conftest.py` - Fixture patterns
- `/specs/5b-dataquality-plugin/tasks.md:150-155` - Task requirements (T047, T049, T050, T050a)
- `packages/floe-core/src/floe_core/quality_errors.py:44-60` - FLOE-DQ102 error class
- `packages/floe-core/src/floe_core/quality_errors.py:111-130` - FLOE-DQ106 timeout error

**Acceptance Criteria**:
- [ ] Test file: `plugins/floe-quality-gx/tests/unit/test_plugin.py`
- [ ] Test added: `test_run_checks_with_gx_context_mock` with @pytest.mark.requirement("FR-004")
- [ ] Test added: `test_run_checks_failure_raises_dq102` with @pytest.mark.requirement("FR-042")
- [ ] Test added: `test_run_checks_timeout_raises_dq106` with @pytest.mark.requirement("FR-032", "FR-046")
- [ ] Test added: `test_run_checks_fail_fast_stops_on_first_failure` with @pytest.mark.requirement("FR-004")
- [ ] `cd plugins/floe-quality-gx && pytest tests/unit/test_plugin.py -v -k "run_checks"` → tests run (may fail until impl)

**Commit**: YES
- Message: `test(quality-gx): add comprehensive run_checks unit tests T047-T050a`
- Files: `plugins/floe-quality-gx/tests/unit/test_plugin.py`

---

### TODO 2: dbt Plugin run_checks Unit Tests (T048)

**What to do**:
- Enhance existing test_plugin.py with tests for dbt test execution
- Add test for run_checks that mocks DBTPlugin.test_models()
- Add test for run_results.json parsing to QualitySuiteResult
- Add test for FLOE-DQ102 error when dbt tests fail

**Must NOT do**:
- Do not require real dbt installation for unit tests (mock it)
- Do not change existing passing tests

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: Well-defined test additions following existing patterns
- **Skills**: [`testing`, `dbt-transformations`]
  - `testing`: TDD patterns, pytest fixtures
  - `dbt-transformations`: Understanding dbt test output format

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with TODO 1, 3, 4)
- **Blocks**: TODO 4 (implementation)
- **Blocked By**: None

**References**:
- `plugins/floe-quality-dbt/tests/unit/test_plugin.py:108-122` - Existing run_checks tests
- `/specs/5b-dataquality-plugin/tasks.md:151` - Task T048 requirements
- Example dbt run_results.json structure (search for dbt artifacts documentation)

**Acceptance Criteria**:
- [ ] Test file: `plugins/floe-quality-dbt/tests/unit/test_plugin.py`
- [ ] Test added: `test_run_checks_calls_dbt_test` with @pytest.mark.requirement("FR-004")
- [ ] Test added: `test_run_results_parsing_to_suite_result` with @pytest.mark.requirement("FR-004")
- [ ] `cd plugins/floe-quality-dbt && pytest tests/unit/test_plugin.py -v -k "run_checks"` → tests run

**Commit**: YES
- Message: `test(quality-dbt): add run_checks unit tests for dbt integration T048`
- Files: `plugins/floe-quality-dbt/tests/unit/test_plugin.py`

---

### TODO 3: GX Plugin run_checks Implementation (T051-T056)

**What to do**:
- Implement `run_checks()` to execute Great Expectations validations
- Create `datasource.py` for GX Data Source connection using connection_config
- Map QualityCheck to GX Expectations dynamically
- Parse GX validation results to QualityCheckResult
- Add timeout handling with FLOE-DQ106 error
- Implement fail_fast behavior (stop on first failure)
- Update run_suite() to use the new implementation

**Must NOT do**:
- Do not hardcode database credentials
- Do not import GX at module level (lazy import for optional dep)
- Do not break validate_config or validate_quality_gates

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
  - Reason: Core implementation requiring GX library integration
- **Skills**: [`pydantic-schemas`, `testing`]
  - `pydantic-schemas`: Schema mapping patterns

**Parallelization**:
- **Can Run In Parallel**: YES (with TODO 4)
- **Parallel Group**: Wave 1
- **Blocks**: TODO 6 (scoring), TODO 8 (lineage), TODO 9-10 (tests)
- **Blocked By**: TODO 1 (tests first - TDD)

**References**:
- `plugins/floe-quality-gx/src/floe_quality_gx/plugin.py:111-136` - Current stubs
- `/specs/5b-dataquality-plugin/tasks.md:157-164` - Tasks T051-T056
- `/specs/5b-dataquality-plugin/plan.md:463-490` - GX integration design
- Great Expectations docs: https://docs.greatexpectations.io/docs/core/run_validations/run_a_checkpoint

**Acceptance Criteria**:
- [ ] File created: `plugins/floe-quality-gx/src/floe_quality_gx/datasource.py`
- [ ] `run_checks()` no longer has TODO comment
- [ ] `run_suite()` executes checks and returns populated QualitySuiteResult
- [ ] Timeout handling raises QualityTimeoutError (FLOE-DQ106)
- [ ] `cd plugins/floe-quality-gx && pytest tests/unit/ -v` → ALL PASS
- [ ] `python -c "from floe_quality_gx import GreatExpectationsPlugin; p = GreatExpectationsPlugin(); print(p.run_checks('test', 'test'))"` → returns QualitySuiteResult (not empty)

**Commit**: YES
- Message: `feat(quality-gx): implement run_checks with GX integration T051-T056`
- Files: `plugins/floe-quality-gx/src/floe_quality_gx/plugin.py`, `plugins/floe-quality-gx/src/floe_quality_gx/datasource.py`

---

### TODO 4: dbt Plugin run_checks Implementation (T058-T062)

**What to do**:
- Implement `run_checks()` to execute dbt tests via subprocess or DBTPlugin
- Create `result_parser.py` to parse run_results.json to QualitySuiteResult
- Map dbt test results to QualityCheckResult with proper dimensions
- Handle dbt test failures and map to FLOE-DQ102
- Update run_suite() to use the new implementation

**Must NOT do**:
- Do not import dbt at module level (lazy import for optional dep)
- Do not execute dbt commands that modify database state
- Do not break validate_config or validate_quality_gates

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
  - Reason: Core implementation requiring dbt integration
- **Skills**: [`dbt-transformations`, `testing`]
  - `dbt-transformations`: dbt test execution and artifacts

**Parallelization**:
- **Can Run In Parallel**: YES (with TODO 3)
- **Parallel Group**: Wave 1
- **Blocks**: TODO 6 (scoring), TODO 8 (lineage), TODO 9-10 (tests)
- **Blocked By**: TODO 2 (tests first - TDD)

**References**:
- `plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py:111-136` - Current stubs
- `/specs/5b-dataquality-plugin/tasks.md:167-174` - Tasks T058-T062
- `/specs/5b-dataquality-plugin/plan.md:492-519` - dbt integration design
- dbt docs: run_results.json artifact structure

**Acceptance Criteria**:
- [ ] File created: `plugins/floe-quality-dbt/src/floe_quality_dbt/result_parser.py`
- [ ] `run_checks()` no longer has TODO comment
- [ ] `run_suite()` executes dbt tests and returns populated QualitySuiteResult
- [ ] `cd plugins/floe-quality-dbt && pytest tests/unit/ -v` → ALL PASS

**Commit**: YES
- Message: `feat(quality-dbt): implement run_checks with dbt test integration T058-T062`
- Files: `plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py`, `plugins/floe-quality-dbt/src/floe_quality_dbt/result_parser.py`

---

### TODO 5: Quality Scoring Unit Tests (T077-T080)

**What to do**:
- Create test file for scoring module
- Test: All checks pass → score = 100
- Test: Weighted score calculation with severities (critical=3.0, warning=1.0, info=0.5)
- Test: Influence capping (baseline=70, max_pos=+30, max_neg=-50)
- Test: Unified score combining dbt tests and plugin checks
- Test: Per-dimension score calculation

**Must NOT do**:
- Do not test in plugin packages (scoring is in floe-core)

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: Well-defined test creation
- **Skills**: [`testing`]
  - `testing`: TDD patterns for scoring algorithms

**Parallelization**:
- **Can Run In Parallel**: YES (with TODO 7)
- **Parallel Group**: Wave 2
- **Blocks**: TODO 6 (implementation)
- **Blocked By**: None (tests can be written before impl exists)

**References**:
- `/specs/5b-dataquality-plugin/tasks.md:220-227` - Tasks T077-T080
- `/specs/5b-dataquality-plugin/plan.md:328-368` - Scoring algorithm specification
- `packages/floe-core/src/floe_core/schemas/quality_config.py:52-77` - CalculationParameters defaults

**Acceptance Criteria**:
- [ ] File created: `packages/floe-core/tests/unit/test_quality_scoring.py`
- [ ] Test: `test_all_checks_pass_score_100` with @pytest.mark.requirement("FR-005")
- [ ] Test: `test_weighted_score_with_severities` with @pytest.mark.requirement("FR-005")
- [ ] Test: `test_influence_capping_positive` with @pytest.mark.requirement("FR-005")
- [ ] Test: `test_influence_capping_negative` with @pytest.mark.requirement("FR-005")
- [ ] Test: `test_unified_score_dbt_plus_plugin_checks` with @pytest.mark.requirement("FR-005")
- [ ] `cd packages/floe-core && pytest tests/unit/test_quality_scoring.py -v` → tests run (fail until impl)

**Commit**: YES
- Message: `test(quality): add quality scoring unit tests T077-T080`
- Files: `packages/floe-core/tests/unit/test_quality_scoring.py`

---

### TODO 6: Quality Scoring Implementation (T081-T087)

**What to do**:
- Create `packages/floe-core/src/floe_core/scoring/` directory
- Implement `dimension_scorer.py` - per-dimension weighted average calculation
- Implement `score_calculator.py` - influence capping (baseline ± delta)
- Implement `unified_scorer.py` - combine dbt tests and plugin checks
- Update calculate_quality_score() in both plugins to use unified_scorer
- Implement warn_score threshold warning (emit to logger)
- Implement min_score enforcement (raise FLOE-DQ102 if below)

**Must NOT do**:
- Do not change the QualityScore schema (use existing)
- Do not break existing plugin functionality

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: Algorithm implementation with clear specification
- **Skills**: [`pydantic-schemas`, `testing`]
  - `pydantic-schemas`: Schema usage patterns

**Parallelization**:
- **Can Run In Parallel**: YES (with TODO 8)
- **Parallel Group**: Wave 2
- **Blocks**: TODO 9-10 (contract/integration tests)
- **Blocked By**: TODO 3, 4 (run_checks must work), TODO 5 (tests first)

**References**:
- `/specs/5b-dataquality-plugin/tasks.md:230-238` - Tasks T081-T087
- `/specs/5b-dataquality-plugin/plan.md:328-368` - Three-layer scoring model
- `packages/floe-core/src/floe_core/schemas/quality_config.py:52-77` - CalculationParameters
- `packages/floe-core/src/floe_core/schemas/quality_score.py:82-101` - QualityScore schema

**Acceptance Criteria**:
- [ ] Directory created: `packages/floe-core/src/floe_core/scoring/`
- [ ] File created: `packages/floe-core/src/floe_core/scoring/__init__.py`
- [ ] File created: `packages/floe-core/src/floe_core/scoring/dimension_scorer.py`
- [ ] File created: `packages/floe-core/src/floe_core/scoring/score_calculator.py`
- [ ] File created: `packages/floe-core/src/floe_core/scoring/unified_scorer.py`
- [ ] Both plugins use unified_scorer in calculate_quality_score()
- [ ] `cd packages/floe-core && pytest tests/unit/test_quality_scoring.py -v` → ALL PASS
- [ ] Score calculation: 70 (baseline) + weighted_delta, capped at 70±30/-50

**Commit**: YES
- Message: `feat(quality): implement quality scoring module with dimension weights T081-T087`
- Files: `packages/floe-core/src/floe_core/scoring/`, plugin updates

---

### TODO 7: OpenLineage Unit Tests (T088-T089)

**What to do**:
- Create test file for OpenLineage integration in GX plugin
- Test: Failed check emits OpenLineage FAIL event with proper facet
- Test: Graceful handling when lineage backend not configured (no error)
- Test: Event contains correct dataset name and check details

**Must NOT do**:
- Do not require real OpenLineage backend for unit tests (mock it)

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: Well-defined test creation
- **Skills**: [`testing`, `dagster-orchestration`]
  - `dagster-orchestration`: OpenLineage event patterns

**Parallelization**:
- **Can Run In Parallel**: YES (with TODO 5, 6)
- **Parallel Group**: Wave 2/3
- **Blocks**: TODO 8 (implementation)
- **Blocked By**: None

**References**:
- `/specs/5b-dataquality-plugin/tasks.md:249-252` - Tasks T088-T089
- `packages/floe-core/src/floe_core/plugins/quality.py:55-62` - OpenLineageEmitter protocol
- OpenLineage facet specification: https://openlineage.io/docs/spec/facets/

**Acceptance Criteria**:
- [ ] File created: `plugins/floe-quality-gx/tests/unit/test_lineage.py`
- [ ] Test: `test_fail_event_emitted_on_check_failure` with @pytest.mark.requirement("FR-006")
- [ ] Test: `test_graceful_handling_no_backend` with @pytest.mark.requirement("FR-006")
- [ ] `cd plugins/floe-quality-gx && pytest tests/unit/test_lineage.py -v` → tests run

**Commit**: YES
- Message: `test(quality-gx): add OpenLineage integration tests T088-T089`
- Files: `plugins/floe-quality-gx/tests/unit/test_lineage.py`

---

### TODO 8: OpenLineage Implementation (T090-T094)

**What to do**:
- Create `packages/floe-core/src/floe_core/lineage/quality_facet.py` - OpenLineage facet for quality results
- Create `plugins/floe-quality-gx/src/floe_quality_gx/lineage.py` - emitter implementation
- Update get_lineage_emitter() in both plugins to return configured emitter
- Implement FAIL event emission on check failures
- Add graceful degradation when backend not configured (log warning, return None)

**Must NOT do**:
- Do not emit events for passing checks (only FAIL)
- Do not require backend to be configured (optional feature)

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: Isolated feature with clear specification
- **Skills**: [`dagster-orchestration`]
  - `dagster-orchestration`: OpenLineage event patterns

**Parallelization**:
- **Can Run In Parallel**: YES (with TODO 6)
- **Parallel Group**: Wave 3
- **Blocks**: TODO 9-10 (contract/integration tests)
- **Blocked By**: TODO 3, 4 (run_checks must emit), TODO 7 (tests first)

**References**:
- `/specs/5b-dataquality-plugin/tasks.md:255-260` - Tasks T090-T094
- `/specs/5b-dataquality-plugin/plan.md:540-575` - OpenLineage design
- `packages/floe-core/src/floe_core/plugins/quality.py:55-62` - OpenLineageEmitter protocol

**Acceptance Criteria**:
- [ ] File created: `packages/floe-core/src/floe_core/lineage/quality_facet.py`
- [ ] File created: `plugins/floe-quality-gx/src/floe_quality_gx/lineage.py`
- [ ] get_lineage_emitter() returns emitter when configured, None otherwise
- [ ] FAIL events emitted only for failed checks
- [ ] `cd plugins/floe-quality-gx && pytest tests/unit/test_lineage.py -v` → ALL PASS

**Commit**: YES
- Message: `feat(quality): implement OpenLineage FAIL event emission T090-T094`
- Files: `packages/floe-core/src/floe_core/lineage/`, `plugins/floe-quality-gx/src/floe_quality_gx/lineage.py`

---

### TODO 9: Contract Tests (T095-T097)

**What to do**:
- Create `tests/contract/test_quality_plugin_contract.py` - QualityPlugin ABC compliance
- Create `tests/contract/test_compiled_artifacts_quality.py` - CompiledArtifacts v0.4.0 stability
- Create `tests/contract/test_quality_config_contract.py` - floe-core → plugin config passing
- Test: Both plugins discovered via entry point
- Test: Both plugins implement all required methods
- Test: health_check returns HealthStatus
- Test: get_config_schema returns Pydantic model

**Must NOT do**:
- Do not require external services for contract tests

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: Contract test patterns are established
- **Skills**: [`testing`]
  - `testing`: Contract test patterns

**Parallelization**:
- **Can Run In Parallel**: YES (with TODO 10)
- **Parallel Group**: Wave 4
- **Blocks**: TODO 11 (polish)
- **Blocked By**: TODO 6, 8 (all features implemented)

**References**:
- `/specs/5b-dataquality-plugin/tasks.md:269-277` - Tasks T095-T097
- `tests/contract/` - Existing contract test patterns (if any)
- `packages/floe-core/src/floe_core/plugins/quality.py` - ABC to test against

**Acceptance Criteria**:
- [ ] File created: `tests/contract/test_quality_plugin_contract.py`
- [ ] File created: `tests/contract/test_compiled_artifacts_quality.py`
- [ ] File created: `tests/contract/test_quality_config_contract.py`
- [ ] Test: `test_gx_plugin_discovered` with @pytest.mark.requirement("FR-039")
- [ ] Test: `test_dbt_plugin_discovered` with @pytest.mark.requirement("FR-039")
- [ ] Test: `test_plugins_implement_all_methods` with @pytest.mark.requirement("FR-039")
- [ ] `pytest tests/contract/test_quality*.py -v` → ALL PASS

**Commit**: YES
- Message: `test(quality): add contract tests for QualityPlugin ABC T095-T097`
- Files: `tests/contract/test_quality_*.py`

---

### TODO 10: Integration Tests (T098-T100b)

**What to do**:
- Create `plugins/floe-quality-gx/tests/integration/test_gx_duckdb.py` - GX with real DuckDB
- Create `plugins/floe-quality-dbt/tests/integration/test_dbt_integration.py` - dbt with dbt-core
- Create `tests/integration/test_unified_scoring.py` - dbt + plugin checks combined
- Create `tests/integration/test_quality_job_failure.py` - job failure when score < min_score
- Create `tests/integration/test_quality_performance.py` - 100+ checks in <100ms

**Must NOT do**:
- Do not require external databases (use DuckDB in-memory)
- Do not run in CI without proper markers

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
  - Reason: Integration tests require careful orchestration
- **Skills**: [`testing`, `duckdb-lakehouse`, `dbt-transformations`]
  - Multiple skills needed for multi-technology integration

**Parallelization**:
- **Can Run In Parallel**: YES (with TODO 9)
- **Parallel Group**: Wave 4
- **Blocks**: TODO 11 (polish)
- **Blocked By**: TODO 6, 8 (all features implemented)

**References**:
- `/specs/5b-dataquality-plugin/tasks.md:280-283` - Tasks T098-T100b
- `/specs/5b-dataquality-plugin/spec.md:208-212` - SC-010 performance requirement

**Acceptance Criteria**:
- [ ] File created: `plugins/floe-quality-gx/tests/integration/test_gx_duckdb.py`
- [ ] File created: `plugins/floe-quality-dbt/tests/integration/test_dbt_integration.py`
- [ ] File created: `tests/integration/test_unified_scoring.py`
- [ ] File created: `tests/integration/test_quality_performance.py`
- [ ] Performance test: 100 checks calculated in <100ms
- [ ] `pytest tests/integration/test_quality*.py -v -m integration` → ALL PASS (when run with deps)

**Commit**: YES
- Message: `test(quality): add integration and performance tests T098-T100b`
- Files: `plugins/*/tests/integration/`, `tests/integration/test_quality*.py`

---

### TODO 11: Documentation and Polish (T101-T106)

**What to do**:
- Update `specs/5b-dataquality-plugin/quickstart.md` with working examples for all tiers
- Create `docs/guides/quality-plugin.md` with configuration examples
- Validate all error codes (FLOE-DQ001-107) have proper messages and resolution hints
- Add OpenTelemetry trace spans to quality check execution in both plugins
- Run full test suite and verify >80% coverage
- Update Linear issues if configured

**Must NOT do**:
- Do not add features - documentation only
- Do not change implementation logic

**Recommended Agent Profile**:
- **Category**: `writing`
  - Reason: Documentation focus
- **Skills**: [`testing`]
  - `testing`: For coverage verification

**Parallelization**:
- **Can Run In Parallel**: NO (depends on everything else)
- **Parallel Group**: Wave 4 (final)
- **Blocks**: None (completion)
- **Blocked By**: TODO 9, 10 (all tests passing)

**References**:
- `/specs/5b-dataquality-plugin/tasks.md:288-298` - Tasks T101-T106
- `packages/floe-core/src/floe_core/quality_errors.py` - All error codes
- `docs/guides/` - Documentation location

**Acceptance Criteria**:
- [ ] File updated: `specs/5b-dataquality-plugin/quickstart.md` with bronze/silver/gold examples
- [ ] File created: `docs/guides/quality-plugin.md`
- [ ] `grep -r "FLOE-DQ" packages/floe-core/src/` shows all 7 error codes with resolution hints
- [ ] OpenTelemetry spans added to run_checks in both plugins
- [ ] `make test` → >80% coverage, 0 failures

**Commit**: YES
- Message: `docs(quality): finalize documentation and add telemetry T101-T106`
- Files: `specs/5b-dataquality-plugin/quickstart.md`, `docs/guides/quality-plugin.md`, plugin updates

---

## Commit Strategy

| After TODO | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `test(quality-gx): add comprehensive run_checks unit tests` | `plugins/floe-quality-gx/tests/` | pytest runs |
| 2 | `test(quality-dbt): add run_checks unit tests` | `plugins/floe-quality-dbt/tests/` | pytest runs |
| 3 | `feat(quality-gx): implement run_checks with GX integration` | `plugins/floe-quality-gx/src/` | pytest passes |
| 4 | `feat(quality-dbt): implement run_checks with dbt integration` | `plugins/floe-quality-dbt/src/` | pytest passes |
| 5 | `test(quality): add quality scoring unit tests` | `packages/floe-core/tests/` | pytest runs |
| 6 | `feat(quality): implement quality scoring module` | `packages/floe-core/src/floe_core/scoring/` | pytest passes |
| 7 | `test(quality-gx): add OpenLineage integration tests` | `plugins/floe-quality-gx/tests/` | pytest runs |
| 8 | `feat(quality): implement OpenLineage FAIL event emission` | `packages/floe-core/src/floe_core/lineage/` | pytest passes |
| 9 | `test(quality): add contract tests` | `tests/contract/` | pytest passes |
| 10 | `test(quality): add integration and performance tests` | `tests/integration/`, `plugins/*/tests/integration/` | pytest passes |
| 11 | `docs(quality): finalize documentation and telemetry` | `docs/`, `specs/` | make test passes |

---

## Success Criteria

### Verification Commands
```bash
# Unit tests
cd plugins/floe-quality-gx && pytest tests/unit/ -v
cd plugins/floe-quality-dbt && pytest tests/unit/ -v
cd packages/floe-core && pytest tests/unit/test_quality*.py -v

# Contract tests
pytest tests/contract/test_quality*.py -v

# Integration tests (requires deps)
pytest tests/integration/test_quality*.py -v -m integration

# Full suite
make test  # Expected: >80% coverage, 0 failures

# Plugin discovery
python -c "from floe_core.plugin_registry import get_registry; print(list(get_registry().list('quality')))"
# Expected: ['great_expectations', 'dbt_expectations']

# Run checks verification
python -c "
from floe_quality_gx import GreatExpectationsPlugin
p = GreatExpectationsPlugin()
result = p.run_checks('test', 'test')
print(f'Result: {result.passed}, checks: {len(result.checks)}')
"
```

### Final Checklist
- [ ] run_checks() returns populated results (not empty stubs)
- [ ] Quality score uses three-layer calculation
- [ ] OpenLineage FAIL events emitted on failures
- [ ] All contract tests pass
- [ ] All integration tests pass
- [ ] Performance: 100 checks in <100ms
- [ ] >80% test coverage
- [ ] All error codes documented
- [ ] Documentation complete

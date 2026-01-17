# Tasks: Compilation Pipeline

**Input**: Design documents from `/specs/2b-compilation-pipeline/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

## Path Conventions

- **Monorepo package**: `packages/floe-core/src/floe_core/`
- **Tests**: `packages/floe-core/tests/` and `tests/contract/` (root-level for cross-package)
- Paths follow plan.md structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and directory structure

- [ ] T001 Create compilation module directory at packages/floe-core/src/floe_core/compilation/
- [ ] T002 Create CLI module directory at packages/floe-core/src/floe_core/cli/
- [ ] T003 [P] Create __init__.py for compilation module at packages/floe-core/src/floe_core/compilation/__init__.py
- [ ] T004 [P] Create __init__.py for CLI module at packages/floe-core/src/floe_core/cli/__init__.py
- [ ] T005 [P] Create test directories at packages/floe-core/tests/unit/compilation/ and packages/floe-core/tests/unit/cli/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schemas and entities that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### FloeSpec Schema (Required by US1, US2)

- [ ] T006 Create FloeMetadata model in packages/floe-core/src/floe_core/schemas/floe_spec.py
- [ ] T007 Create TransformSpec model with name/compute/tags/depends_on in packages/floe-core/src/floe_core/schemas/floe_spec.py
- [ ] T008 Create ScheduleSpec model with cron/timezone/enabled in packages/floe-core/src/floe_core/schemas/floe_spec.py
- [ ] T009 Create PlatformRef model with manifest field in packages/floe-core/src/floe_core/schemas/floe_spec.py
- [ ] T010 Create FloeSpec root model with apiVersion/kind/metadata/platform/transforms/schedule in packages/floe-core/src/floe_core/schemas/floe_spec.py
- [ ] T011 Add validators for DNS-compatible name (C001) and semver version (C002) in packages/floe-core/src/floe_core/schemas/floe_spec.py
- [ ] T012 Add environment-agnostic validator (C004, FR-014) rejecting forbidden fields in packages/floe-core/src/floe_core/schemas/floe_spec.py

### CompiledArtifacts Extensions (Required by US1, US4)

- [ ] T013 Create PluginRef model with type/version/config in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T014 Create ResolvedPlugins model with compute/orchestrator/catalog/storage fields in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T015 Create ResolvedModel model with name/compute/tags/depends_on in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T016 Create ResolvedTransforms model with models/default_compute in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T017 Create ResolvedGovernance model in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T018 Extend CompiledArtifacts with plugins/transforms/dbt_profiles/governance fields in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T019 Update CompiledArtifacts version from 0.1.0 to 0.2.0 in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py

### Compilation Error Handling (Required by US1, US3)

- [ ] T020 Create CompilationError Pydantic model with stage/code/message/suggestion fields in packages/floe-core/src/floe_core/compilation/errors.py
- [ ] T021 [P] Create CompilationStage enum (LOAD, VALIDATE, RESOLVE, ENFORCE, COMPILE, GENERATE) in packages/floe-core/src/floe_core/compilation/stages.py

### Unit Tests for Foundational Schemas

- [ ] T022 [P] Write unit tests for FloeSpec validation in packages/floe-core/tests/unit/schemas/test_floe_spec.py
- [ ] T023 [P] Write unit tests for CompiledArtifacts extension fields in packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Compile Data Product Configuration (Priority: P1) 🎯 MVP

**Goal**: Data engineers can run `floe compile` to transform floe.yaml + manifest into CompiledArtifacts JSON with dbt profiles and metadata.

**Independent Test**: Run `floe compile --spec floe.yaml --manifest manifest.yaml` and verify CompiledArtifacts JSON output contains correct dbt profiles, transforms, and metadata.

### Tests for User Story 1

- [ ] T024 [P] [US1] Write contract test for CompiledArtifacts schema stability in tests/contract/test_compiled_artifacts_schema.py
- [ ] T025 [P] [US1] Write unit tests for YAML loader in packages/floe-core/tests/unit/compilation/test_loader.py
- [ ] T026 [P] [US1] Write unit tests for plugin resolver in packages/floe-core/tests/unit/compilation/test_resolver.py
- [ ] T027 [P] [US1] Write unit tests for artifacts builder in packages/floe-core/tests/unit/compilation/test_builder.py
- [ ] T028 [P] [US1] Write unit tests for compile CLI command in packages/floe-core/tests/unit/cli/test_compile.py

### Implementation for User Story 1

- [ ] T029 [US1] Implement YAML loader for floe.yaml → FloeSpec in packages/floe-core/src/floe_core/compilation/loader.py
- [ ] T030 [US1] Implement YAML loader for manifest.yaml → PlatformManifest in packages/floe-core/src/floe_core/compilation/loader.py
- [ ] T031 [US1] Implement plugin resolver to resolve compute/orchestrator from manifest in packages/floe-core/src/floe_core/compilation/resolver.py
- [ ] T032 [US1] Implement manifest inheritance resolution (3-tier mode) in packages/floe-core/src/floe_core/compilation/resolver.py
- [ ] T033 [US1] Implement transform compiler using existing resolve_transform_compute() in packages/floe-core/src/floe_core/compilation/resolver.py
- [ ] T034 [US1] Implement CompiledArtifacts builder with metadata (git commit, timestamp, versions) in packages/floe-core/src/floe_core/compilation/builder.py
- [ ] T035 [US1] Implement compile orchestrator executing 6-stage pipeline in packages/floe-core/src/floe_core/compilation/stages.py
- [ ] T036 [US1] Add structured logging with structlog for each compilation stage in packages/floe-core/src/floe_core/compilation/stages.py
- [ ] T037 [US1] Implement argparse CLI for `floe compile` with --spec/--manifest/--output args in packages/floe-core/src/floe_core/cli/compile.py
- [ ] T038 [US1] Implement exit codes (0=success, 1=validation error, 2=compilation error) in packages/floe-core/src/floe_core/cli/compile.py
- [ ] T039 [US1] Register CLI entry point in packages/floe-core/pyproject.toml as `floe = "floe_core.cli:main"`
- [ ] T040 [US1] Add actionable error messages with suggested fixes (FR-002, SC-002) in packages/floe-core/src/floe_core/compilation/errors.py

**Checkpoint**: User Story 1 complete - basic compilation works end-to-end

---

## Phase 4: User Story 2 - Generate dbt Profiles Automatically (Priority: P1)

**Goal**: dbt profiles.yml generated automatically from platform configuration with credential placeholders for runtime resolution.

**Independent Test**: Compile a manifest with DuckDB compute plugin and verify profiles.yml contains valid DuckDB target configuration.

### Tests for User Story 2

- [ ] T041 [P] [US2] Write unit tests for dbt profile generation in packages/floe-core/tests/unit/compilation/test_dbt_profiles.py
- [ ] T042 [P] [US2] Write integration test for DuckDB profile generation in packages/floe-core/tests/integration/test_dbt_profile_generation.py

### Implementation for User Story 2

- [ ] T043 [US2] Implement dbt profile generator using ComputePlugin.generate_dbt_profile() in packages/floe-core/src/floe_core/compilation/resolver.py
- [ ] T044 [US2] Add credential placeholder generation using {{ env_var('X') }} syntax in packages/floe-core/src/floe_core/compilation/resolver.py
- [ ] T045 [US2] Integrate dbt profiles into CompiledArtifacts.dbt_profiles field in packages/floe-core/src/floe_core/compilation/builder.py
- [ ] T046 [US2] Add validation for missing required compute credentials in packages/floe-core/src/floe_core/compilation/resolver.py

**Checkpoint**: User Story 2 complete - dbt profiles generated automatically

---

## Phase 5: User Story 3 - Validate Before Deployment (Priority: P2)

**Goal**: Data engineers can validate configuration without generating artifacts using --dry-run and --validate-only flags.

**Independent Test**: Run `floe compile --dry-run` and verify no files are written, only validation messages displayed.

### Tests for User Story 3

- [ ] T047 [P] [US3] Write unit tests for --dry-run flag behavior in packages/floe-core/tests/unit/cli/test_compile.py
- [ ] T048 [P] [US3] Write unit tests for --validate-only flag behavior in packages/floe-core/tests/unit/cli/test_compile.py

### Implementation for User Story 3

- [ ] T049 [US3] Implement --dry-run flag that validates without writing files in packages/floe-core/src/floe_core/cli/compile.py
- [ ] T050 [US3] Implement --validate-only flag that skips dbt/Dagster compilation in packages/floe-core/src/floe_core/cli/compile.py
- [ ] T051 [US3] Add "Validation successful" message output for successful dry-run in packages/floe-core/src/floe_core/cli/compile.py
- [ ] T052 [US3] Ensure no side effects (no files, no network calls) during dry-run modes in packages/floe-core/src/floe_core/compilation/stages.py

**Checkpoint**: User Story 3 complete - validation modes work

---

## Phase 6: User Story 4 - CompiledArtifacts as Integration Contract (Priority: P2)

**Goal**: CompiledArtifacts is a stable, versioned contract with round-trip serialization and backward compatibility.

**Independent Test**: Serialize CompiledArtifacts to JSON, deserialize, and verify all fields are preserved with identical values.

### Tests for User Story 4

- [ ] T053 [P] [US4] Write contract test for round-trip serialization in tests/contract/test_compiled_artifacts_schema.py
- [ ] T054 [P] [US4] Write contract test for backward compatibility in tests/contract/test_compiled_artifacts_schema.py
- [ ] T055 [P] [US4] Write contract test for immutability (frozen=True) in tests/contract/test_compiled_artifacts_schema.py

### Implementation for User Story 4

- [ ] T056 [US4] Implement to_json_file(path) method on CompiledArtifacts in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T057 [US4] Implement from_json_file(path) classmethod on CompiledArtifacts in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T058 [US4] Add JSON Schema export for IDE autocomplete in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T059 [US4] Ensure frozen=True and extra="forbid" on all nested models in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py

**Checkpoint**: User Story 4 complete - contract is stable and serializable

---

## Phase 7: User Story 5 - Multiple Output Formats (Priority: P3)

**Goal**: Output compiled artifacts in JSON (default) or YAML format via --format flag.

**Independent Test**: Compile to both JSON and YAML, compare data content, verify semantic identity.

### Tests for User Story 5

- [ ] T060 [P] [US5] Write unit tests for YAML serialization in packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py
- [ ] T061 [P] [US5] Write unit tests for --format flag handling in packages/floe-core/tests/unit/cli/test_compile.py

### Implementation for User Story 5

- [ ] T062 [US5] Implement to_yaml_file(path) method on CompiledArtifacts in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T063 [US5] Implement from_yaml_file(path) classmethod on CompiledArtifacts in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T064 [US5] Add --format flag (json/yaml) to CLI in packages/floe-core/src/floe_core/cli/compile.py
- [ ] T065 [US5] Implement format detection from output file extension in packages/floe-core/src/floe_core/cli/compile.py

**Checkpoint**: User Story 5 complete - multiple output formats supported

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T066 [P] Add OpenTelemetry traces for compilation stages (FR-013) in packages/floe-core/src/floe_core/compilation/stages.py
- [ ] T067 [P] Add timing information logging for each stage in packages/floe-core/src/floe_core/compilation/stages.py
- [ ] T068 [P] Write cross-package contract test for floe-dagster consumption in tests/contract/test_core_to_dagster_contract.py
- [ ] T069 [P] Update package exports in packages/floe-core/src/floe_core/__init__.py
- [ ] T070 [P] Add --verbose and --quiet flags to CLI in packages/floe-core/src/floe_core/cli/compile.py
- [ ] T071 Run quickstart.md validation with test floe.yaml and manifest.yaml
- [ ] T072 Performance validation: ensure compilation <5s for 10-50 models (SC-001)
- [ ] T073 Performance validation: ensure dry-run <2s (SC-006)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (P1) and US2 (P1) can proceed in parallel
  - US3 (P2) depends on US1 CLI implementation
  - US4 (P2) can proceed in parallel with US3
  - US5 (P3) depends on US4 serialization methods
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Integrates with US1 resolver
- **User Story 3 (P2)**: Depends on US1 CLI being implemented (T037)
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) - No dependencies on CLI
- **User Story 5 (P3)**: Depends on US4 serialization methods (T056, T057)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before CLI
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks can run in parallel
- Foundational schema tasks T006-T12 can run sequentially (same file)
- Foundational tests T022-T023 can run in parallel
- US1 tests T024-T028 can run in parallel
- US2 tests T041-T042 can run in parallel
- US3, US4, US5 tests can run in parallel within their phases
- Different user stories can be worked on in parallel by different team members (US1+US2, US3+US4)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract test for CompiledArtifacts schema stability"
Task: "Unit tests for YAML loader"
Task: "Unit tests for plugin resolver"
Task: "Unit tests for artifacts builder"
Task: "Unit tests for compile CLI command"

# After tests fail, implement in order:
# 1. Loader (T029, T030)
# 2. Resolver (T031, T032, T033)
# 3. Builder (T034)
# 4. Stages orchestrator (T035, T036)
# 5. CLI (T037, T038, T039, T040)
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (basic compilation)
4. Complete Phase 4: User Story 2 (dbt profiles)
5. **STOP and VALIDATE**: Test `floe compile` with real floe.yaml and manifest
6. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → `floe compile` works (MVP!)
3. Add User Story 2 → Test independently → dbt profiles generated
4. Add User Story 3 → Test independently → validation modes work
5. Add User Story 4 → Test independently → contract stable
6. Add User Story 5 → Test independently → multiple formats
7. Each story adds value without breaking previous stories

### Requirement Traceability

| Task Range | Requirement | User Story |
|------------|-------------|------------|
| T006-T012 | FR-003, FR-014 | Foundational |
| T013-T019 | FR-003, FR-007 | Foundational |
| T024-T040 | FR-001, FR-002, FR-008, FR-012, FR-013 | US1 |
| T041-T046 | FR-005, FR-006 | US2 |
| T047-T052 | FR-009, FR-010 | US3 |
| T053-T059 | FR-004 | US4 |
| T060-T065 | FR-011 | US5 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total tasks: 73
- All tests follow TDD approach per Constitution V
- All schemas use Pydantic v2 with frozen=True, extra="forbid" per Constitution IV

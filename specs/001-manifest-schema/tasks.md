# Tasks: Manifest Schema

**Input**: Design documents from `/specs/001-manifest-schema/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test tasks are included per constitution Principle V (K8s-Native Testing) and testing standards.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md project structure:
- **Package**: `packages/floe-core/`
- **Source**: `packages/floe-core/src/floe_core/schemas/`
- **Unit tests**: `packages/floe-core/tests/unit/schemas/`
- **Contract tests**: `tests/contract/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and schema module structure

- [ ] T001 Create schemas directory at `packages/floe-core/src/floe_core/schemas/`
- [ ] T002 Create `__init__.py` with public exports in `packages/floe-core/src/floe_core/schemas/__init__.py`
- [ ] T003 [P] Create test directory at `packages/floe-core/tests/unit/schemas/`
- [ ] T004 [P] Add Pydantic v2 and PyYAML dependencies to `packages/floe-core/pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Base models and enums that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create `SecretSource` enum in `packages/floe-core/src/floe_core/schemas/secrets.py` (env, kubernetes, vault, external-secrets)
- [ ] T006 [P] Create `MergeStrategy` enum in `packages/floe-core/src/floe_core/schemas/inheritance.py` (OVERRIDE, EXTEND, FORBID)
- [ ] T007 [P] Create `ManifestMetadata` model in `packages/floe-core/src/floe_core/schemas/metadata.py` (name, version, owner, description with validation patterns)
- [ ] T008 Create `SecretReference` model in `packages/floe-core/src/floe_core/schemas/secrets.py` (source, name, key with pattern validation)
- [ ] T009 Unit test for `ManifestMetadata` validation in `packages/floe-core/tests/unit/schemas/test_metadata.py`
- [ ] T010 [P] Unit test for `SecretReference` validation in `packages/floe-core/tests/unit/schemas/test_secrets.py`

**Checkpoint**: Foundation ready - base models validated and tested

---

## Phase 3: User Story 1 - Platform Configuration Definition (Priority: P1) 🎯 MVP

**Goal**: Platform teams can define and validate platform configuration in manifest.yaml

**Independent Test**: Load a valid manifest.yaml file → system validates and returns structured PlatformManifest object

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T011 [P] [US1] Unit test for valid manifest loading in `packages/floe-core/tests/unit/schemas/test_manifest.py`
- [ ] T012 [P] [US1] Unit test for missing required field error in `packages/floe-core/tests/unit/schemas/test_manifest.py`
- [ ] T013 [P] [US1] Unit test for invalid field value error in `packages/floe-core/tests/unit/schemas/test_manifest.py`
- [ ] T014 [P] [US1] Unit test for unknown field warning (forward compatibility) in `packages/floe-core/tests/unit/schemas/test_manifest.py`
- [ ] T015 [P] [US1] Contract test for manifest schema stability in `tests/contract/test_manifest_schema.py`

### Implementation for User Story 1

- [ ] T016 [P] [US1] Create `PluginSelection` model in `packages/floe-core/src/floe_core/schemas/plugins.py` (type, config, connection_secret_ref)
- [ ] T017 [P] [US1] Create `PluginsConfig` model in `packages/floe-core/src/floe_core/schemas/plugins.py` (11 plugin categories: compute, orchestrator, catalog, storage, semantic_layer, ingestion, secrets, observability, identity, dbt, quality)
- [ ] T018 [P] [US1] Create `GovernanceConfig` model in `packages/floe-core/src/floe_core/schemas/manifest.py` (pii_encryption, audit_logging, policy_enforcement_level, data_retention_days)
- [ ] T019 [US1] Create `PlatformManifest` model in `packages/floe-core/src/floe_core/schemas/manifest.py` (apiVersion, kind, metadata, scope, parent_manifest, plugins, governance, approved_plugins, approved_products)
- [ ] T020 [US1] Add scope field validation: scope=None (2-tier), scope="enterprise"/"domain" (3-tier) in `packages/floe-core/src/floe_core/schemas/manifest.py`
- [ ] T021 [US1] Add model_validator for scope constraints (enterprise=no parent, domain=requires parent, None=no parent) in `packages/floe-core/src/floe_core/schemas/manifest.py`
- [ ] T022 [US1] Add forward compatibility: `extra="allow"` with warning validator in `packages/floe-core/src/floe_core/schemas/manifest.py`
- [ ] T023 [US1] Export `PlatformManifest`, `PluginsConfig`, `GovernanceConfig` from `packages/floe-core/src/floe_core/schemas/__init__.py`

**Checkpoint**: User Story 1 complete - manifests can be loaded, validated, and return structured objects

---

## Phase 4: User Story 2 - Configuration Inheritance (Priority: P1)

**Goal**: Child configurations can inherit from and extend parent configurations (3-tier mode)

**Independent Test**: Load child manifest with parent_manifest reference → system resolves inheritance and merges configurations

### Tests for User Story 2

- [ ] T024 [P] [US2] Unit test for 2-tier mode (scope=None, no inheritance) in `packages/floe-core/tests/unit/schemas/test_inheritance.py`
- [ ] T025 [P] [US2] Unit test for parent-child merge (child overrides parent) in `packages/floe-core/tests/unit/schemas/test_inheritance.py`
- [ ] T026 [P] [US2] Unit test for list merge (extend vs replace) in `packages/floe-core/tests/unit/schemas/test_inheritance.py`
- [ ] T027 [P] [US2] Unit test for circular dependency detection in `packages/floe-core/tests/unit/schemas/test_inheritance.py`
- [ ] T028 [P] [US2] Unit test for security policy immutability (cannot weaken) in `packages/floe-core/tests/unit/schemas/test_governance.py`
- [ ] T029 [P] [US2] Unit test for security policy strengthening (allowed) in `packages/floe-core/tests/unit/schemas/test_governance.py`

### Implementation for User Story 2

- [ ] T030 [P] [US2] Create `FIELD_MERGE_STRATEGIES` mapping in `packages/floe-core/src/floe_core/schemas/inheritance.py` (plugins=OVERRIDE, governance=FORBID, approved_plugins=FORBID)
- [ ] T031 [P] [US2] Create policy strength ordering constants in `packages/floe-core/src/floe_core/schemas/validation.py` (PII_ENCRYPTION_STRENGTH, AUDIT_LOGGING_STRENGTH, POLICY_LEVEL_STRENGTH)
- [ ] T032 [US2] Create `validate_security_policy_not_weakened()` function in `packages/floe-core/src/floe_core/schemas/validation.py`
- [ ] T033 [US2] Create `InheritanceChain` model in `packages/floe-core/src/floe_core/schemas/inheritance.py` (enterprise, domain, product, resolved, field_sources)
- [ ] T034 [US2] Implement `merge_manifests()` function in `packages/floe-core/src/floe_core/schemas/inheritance.py` (applies merge strategies per field)
- [ ] T035 [US2] Implement `detect_circular_inheritance()` function in `packages/floe-core/src/floe_core/schemas/inheritance.py`
- [ ] T036 [US2] Create `SecurityPolicyViolationError` and `InheritanceError` exceptions in `packages/floe-core/src/floe_core/schemas/validation.py`
- [ ] T037 [US2] Export inheritance utilities from `packages/floe-core/src/floe_core/schemas/__init__.py`

**Checkpoint**: User Story 2 complete - inheritance chains resolve correctly with security policy enforcement

---

## Phase 5: User Story 3 - Plugin Selection (Priority: P1)

**Goal**: Platform teams can select and configure plugins for each platform capability

**Independent Test**: Define plugin selections → system validates against plugin registry and accepts plugin-specific config

### Tests for User Story 3

- [ ] T038 [P] [US3] Unit test for valid plugin selection in `packages/floe-core/tests/unit/schemas/test_plugins.py`
- [ ] T039 [P] [US3] Unit test for invalid plugin name error in `packages/floe-core/tests/unit/schemas/test_plugins.py`
- [ ] T040 [P] [US3] Unit test for plugin-specific configuration in `packages/floe-core/tests/unit/schemas/test_plugins.py`
- [ ] T041 [P] [US3] Unit test for domain plugin whitelist validation in `packages/floe-core/tests/unit/schemas/test_plugins.py`

### Implementation for User Story 3

- [ ] T042 [US3] Create `get_available_plugins()` function in `packages/floe-core/src/floe_core/schemas/plugins.py` (reads from entry points `floe.{category}`)
- [ ] T043 [US3] Create `validate_plugin_selection()` function in `packages/floe-core/src/floe_core/schemas/plugins.py` (checks plugin exists in registry)
- [ ] T044 [US3] Add field_validator to `PluginSelection` for runtime plugin validation in `packages/floe-core/src/floe_core/schemas/plugins.py`
- [ ] T045 [US3] Create `validate_domain_plugin_whitelist()` function in `packages/floe-core/src/floe_core/schemas/validation.py` (domain plugins within enterprise approved_plugins)
- [ ] T046 [US3] Add helpful error messages listing available plugins per category in `packages/floe-core/src/floe_core/schemas/plugins.py`

**Checkpoint**: User Story 3 complete - plugin selections validated against registry with clear error messages

---

## Phase 6: User Story 4 - IDE Autocomplete Support (Priority: P2)

**Goal**: Generate JSON Schema for IDE autocomplete in manifest.yaml files

**Independent Test**: Generate schema → VS Code provides autocomplete when editing manifest.yaml with schema reference

### Tests for User Story 4

- [ ] T047 [P] [US4] Unit test for JSON Schema export in `packages/floe-core/tests/unit/schemas/test_json_schema.py`
- [ ] T048 [P] [US4] Contract test for JSON Schema validity in `tests/contract/test_manifest_json_schema.py`

### Implementation for User Story 4

- [ ] T049 [US4] Create `export_json_schema()` function in `packages/floe-core/src/floe_core/schemas/manifest.py` (uses model_json_schema() with $id and $schema)
- [ ] T050 [US4] Generate and commit `specs/001-manifest-schema/contracts/manifest.schema.json` from Pydantic model
- [ ] T051 [US4] Add CLI command or script to regenerate schema: `packages/floe-core/scripts/export_schema.py`
- [ ] T052 [US4] Document schema usage in quickstart.md (yaml-language-server: $schema=...)

**Checkpoint**: User Story 4 complete - JSON Schema enables IDE autocomplete for manifest.yaml

---

## Phase 7: User Story 5 - Secret Reference Handling (Priority: P2)

**Goal**: Define secret references that remain placeholders until runtime resolution

**Independent Test**: Load manifest with secret references → references validated but not resolved

### Tests for User Story 5

- [ ] T053 [P] [US5] Unit test for secret reference format validation in `packages/floe-core/tests/unit/schemas/test_secrets.py`
- [ ] T054 [P] [US5] Unit test for secret reference placeholder preservation in `packages/floe-core/tests/unit/schemas/test_secrets.py`

### Implementation for User Story 5

- [ ] T055 [US5] Add `connection_secret_ref` validation pattern to `PluginSelection` in `packages/floe-core/src/floe_core/schemas/plugins.py`
- [ ] T056 [US5] Create `to_env_var_syntax()` method on `SecretReference` for dbt integration in `packages/floe-core/src/floe_core/schemas/secrets.py`
- [ ] T057 [US5] Document secret reference patterns in quickstart.md

**Checkpoint**: User Story 5 complete - secrets are referenced safely without exposing values

---

## Phase 8: User Story 6 - Environment-Agnostic Configuration (Priority: P2)

**Goal**: Compiled artifacts are environment-agnostic; FLOE_ENV determines runtime behavior

**Independent Test**: Compile manifest → same artifact works with FLOE_ENV=dev and FLOE_ENV=production

### Tests for User Story 6

- [ ] T058 [P] [US6] Unit test for environment-agnostic compilation in `packages/floe-core/tests/unit/schemas/test_manifest.py`
- [ ] T059 [P] [US6] Unit test for FLOE_ENV runtime resolution concept in `packages/floe-core/tests/unit/schemas/test_manifest.py`

### Implementation for User Story 6

- [ ] T060 [US6] Add validation that manifest contains NO env_overrides field in `packages/floe-core/src/floe_core/schemas/manifest.py`
- [ ] T061 [US6] Document runtime environment resolution in quickstart.md (FLOE_ENV usage)
- [ ] T062 [US6] Update manifest schema to reject environment-specific sections with clear error

**Checkpoint**: User Story 6 complete - manifests are environment-agnostic by design

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, and cleanup

- [ ] T063 [P] Validate all models pass `mypy --strict` in `packages/floe-core/src/floe_core/schemas/`
- [ ] T064 [P] Ensure all test files have `@pytest.mark.requirement()` markers
- [ ] T065 [P] Run Ruff linting and formatting on all new files
- [ ] T066 Run quickstart.md validation (execute Python examples)
- [ ] T067 Verify JSON Schema matches Pydantic model (contract test)
- [ ] T068 Update `packages/floe-core/src/floe_core/__init__.py` to export schema module
- [ ] T069 Add requirement traceability comments linking to FR-001 through FR-018

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-8)**: All depend on Foundational phase completion
  - US1, US2, US3 (P1): Start after Phase 2, can run in parallel if staffed
  - US4, US5, US6 (P2): Start after P1 stories complete (or in parallel with sufficient resources)
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational - No dependencies on other stories
- **US2 (P1)**: Depends on US1 (needs PlatformManifest, GovernanceConfig for inheritance)
- **US3 (P1)**: Can start after Foundational - Uses PluginSelection from US1 but models defined in parallel
- **US4 (P2)**: Depends on US1 (needs PlatformManifest for JSON Schema export)
- **US5 (P2)**: Can start after Foundational - Uses SecretReference from Phase 2
- **US6 (P2)**: Depends on US1 (validates against PlatformManifest schema)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before validators
- Validators before exports
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes:
  - US1 and US3 can start in parallel
  - US2 depends on US1 model definitions
- All tests for a user story marked [P] can run in parallel
- P2 stories (US4, US5, US6) can run in parallel once P1 dependencies exist

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test manifest loading independently
5. Demo: Load and validate a manifest.yaml file

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 → Test independently → Demo (MVP: manifest validation)
3. Add US2 → Test independently → Demo (Inheritance support)
4. Add US3 → Test independently → Demo (Plugin validation)
5. Add US4 → Test independently → Demo (IDE autocomplete)
6. Add US5/US6 → Polish and complete

### Requirement Traceability

| Task Range | Requirements Covered |
|------------|---------------------|
| T011-T023 | FR-001, FR-002, FR-012, FR-013, FR-016 |
| T024-T037 | FR-003, FR-004, FR-005, FR-014, FR-017 |
| T038-T046 | FR-006, FR-007, FR-008, FR-018 |
| T047-T052 | FR-009 |
| T053-T057 | FR-010 |
| T058-T062 | FR-011, FR-015 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Constitution Principle V: All tests run in K8s (Kind cluster) for integration tests
- Constitution Principle VI: Use SecretStr for credentials, validate all input with Pydantic

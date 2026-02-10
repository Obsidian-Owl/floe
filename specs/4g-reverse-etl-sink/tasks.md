# Tasks: Epic 4G — Reverse ETL (SinkConnector)

**Input**: Design documents from `/specs/4g-reverse-etl-sink/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: TDD approach — test tasks precede implementation tasks in each phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## User Story Mapping

| Story | Title | Priority | Spec FRs |
|-------|-------|----------|----------|
| US1 | SinkConnector ABC Definition | P0 | FR-001, FR-002, FR-003, FR-004, FR-014, FR-015 |
| US2 | dlt Reverse ETL Implementation | P0 | FR-005, FR-006, FR-007, FR-008, FR-009, FR-010, FR-013, FR-016 |
| US3 | Egress Configuration in floe.yaml | P1 | FR-011, FR-012, FR-018 |
| US4 | Egress Governance via Manifest Whitelist | P1 | FR-017 |

---

## Phase 1: Setup

**Purpose**: No new project setup needed — this epic modifies 2 existing packages (floe-core, floe-ingestion-dlt). Setup ensures contracts/ spec is registered.

- [ ] T001 Verify `specs/4g-reverse-etl-sink/contracts/sink-connector-contract.md` exists and matches the implemented ABC. No-op if file already exists from planning phase.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create the `sink.py` module and export it from `floe_core.plugins`. All user stories depend on this.

**CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 Create `packages/floe-core/src/floe_core/plugins/sink.py` with SinkConfig dataclass, EgressResult dataclass, and SinkConnector ABC (4 abstract methods). Mirror `ingestion.py` patterns: `@dataclass` for DTOs, `field(default_factory=list)` for mutable defaults, `ABC` base class only (not PluginMetadata), `Any` return types. Ref: FR-001, FR-002, FR-003, FR-014, FR-015.
- [ ] T003 Add SinkConnector, SinkConfig, EgressResult exports to `packages/floe-core/src/floe_core/plugins/__init__.py`. Add `# Sink/Egress plugin (Epic 4G)` comment header, imports from `floe_core.plugins.sink`, and entries in `__all__`.

**Checkpoint**: `from floe_core.plugins import SinkConnector, SinkConfig, EgressResult` works.

---

## Phase 3: User Story 1 — SinkConnector ABC Definition (Priority: P0)

**Goal**: Plugin developers have a clear, well-defined interface for reverse ETL. The ABC enforces the 4-method contract, supports standalone and mixin usage, and enables `isinstance()` capability detection.

**Independent Test**: Create a mock class implementing SinkConnector, verify abstract method enforcement, confirm isinstance() detection.

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T004 [P] [US1] Write ABC enforcement tests in `packages/floe-core/tests/unit/test_sink_connector.py`: test_cannot_instantiate_abstract_directly (TypeError), test_incomplete_implementation_raises_type_error, test_complete_implementation_succeeds. Use `@pytest.mark.requirement("4G-FR-001")`.
- [ ] T005 [P] [US1] Write standalone/mixin tests in `packages/floe-core/tests/unit/test_sink_connector.py`: test_standalone_without_ingestion_plugin (FR-015), test_mixin_with_ingestion_plugin (isinstance True for both), test_plain_ingestion_plugin_not_sink_connector (isinstance False for SinkConnector). Use `@pytest.mark.requirement("4G-FR-004")` and `@pytest.mark.requirement("4G-FR-015")`.
- [ ] T006 [P] [US1] Write dataclass tests in `packages/floe-core/tests/unit/test_sink_connector.py`: test_sink_config_defaults, test_sink_config_with_all_fields, test_egress_result_defaults, test_egress_result_with_empty_rows (rows_delivered=0 is valid), test_egress_result_mutable_default_isolation (list fields don't share state). Use `@pytest.mark.requirement("4G-FR-002")` and `@pytest.mark.requirement("4G-FR-003")`.
- [ ] T007 [P] [US1] Write ABC contract test in `tests/contract/test_sink_connector_contract.py`: test_sink_connector_importable_from_plugins, test_sink_config_importable_from_plugins, test_egress_result_importable_from_plugins, test_sink_connector_has_exactly_4_abstract_methods, test_sink_connector_does_not_inherit_plugin_metadata, test_sink_config_fields_match_contract, test_egress_result_fields_match_contract. Use `@pytest.mark.requirement("4G-SC-006")`.

### Implementation for User Story 1

> Tests T004-T007 should already exist and FAIL. Implementation makes them pass.

- [ ] T008 [US1] Implement SinkConfig dataclass in `packages/floe-core/src/floe_core/plugins/sink.py` with fields: sink_type (str), connection_config (dict, default {}), field_mapping (dict|None, default None), retry_config (dict|None, default None), batch_size (int|None, default None). Ref: FR-002, FR-014.
- [ ] T009 [US1] Implement EgressResult dataclass in `packages/floe-core/src/floe_core/plugins/sink.py` with fields: success (bool), rows_delivered (int=0), bytes_transmitted (int=0), duration_seconds (float=0.0), checksum (str=""), delivery_timestamp (str=""), idempotency_key (str=""), destination_record_ids (list, default_factory), errors (list, default_factory). Ref: FR-003.
- [ ] T010 [US1] Implement SinkConnector(ABC) in `packages/floe-core/src/floe_core/plugins/sink.py` with 4 abstract methods: list_available_sinks, create_sink, write, get_source_config. Add docstrings documenting pyarrow.Table runtime type for `data` parameter. Ref: FR-001, FR-015.
- [ ] T011 [US1] Verify all US1 tests pass. Run `pytest packages/floe-core/tests/unit/test_sink_connector.py tests/contract/test_sink_connector_contract.py -v`.

**Checkpoint**: SinkConnector ABC is defined, exported, and independently testable. Plugin developers can code against the contract.

---

## Phase 4: User Story 2 — dlt Reverse ETL Implementation (Priority: P0)

**Goal**: DltIngestionPlugin gains SinkConnector capability, enabling bidirectional data movement via dlt's destination API with OTel tracing and structured error handling.

**Independent Test**: Configure a dlt sink to write to a mock endpoint, execute write with sample data, verify EgressResult metrics and OTel spans.

### Tests for User Story 2

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T012 [P] [US2] Write error class tests in `plugins/floe-ingestion-dlt/tests/unit/test_dlt_sink_errors.py`: test_sink_connection_error_default_category (TRANSIENT), test_sink_write_error_default_category (TRANSIENT), test_sink_configuration_error_default_category (CONFIGURATION), test_sink_errors_include_context_suffix, test_sink_errors_inherit_from_ingestion_error. Use `@pytest.mark.requirement("4G-FR-013")`.
- [ ] T013 [P] [US2] Write OTel tracing tests in `plugins/floe-ingestion-dlt/tests/unit/test_dlt_sink_tracing.py`: test_egress_span_creates_span_with_attributes, test_egress_span_sets_ok_status_on_success, test_egress_span_sets_error_status_on_exception, test_record_egress_result_sets_all_attributes, test_record_egress_error_truncates_message. Use `@pytest.mark.requirement("4G-FR-010")`.
- [ ] T014 [P] [US2] Write DltIngestionPlugin sink method tests in `plugins/floe-ingestion-dlt/tests/unit/test_dlt_sink_connector.py`: test_isinstance_sink_connector (True), test_list_available_sinks_returns_list, test_create_sink_with_valid_config, test_create_sink_with_invalid_config_raises_error, test_write_with_mock_data_returns_egress_result, test_write_with_empty_table_succeeds, test_write_with_batch_size_chunks, test_get_source_config_returns_iceberg_config, test_get_source_config_missing_table_raises_error, test_sink_methods_require_started_state. Use `@pytest.mark.requirement("4G-FR-005")` through `@pytest.mark.requirement("4G-FR-009")`.

### Implementation for User Story 2

- [ ] T015 [P] [US2] Add SinkConnectionError, SinkWriteError, SinkConfigurationError to `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/errors.py`. Follow existing IngestionError pattern: keyword-only params, default ErrorCategory per subclass, context suffix auto-appended. Ref: FR-013.
- [ ] T016 [P] [US2] Add egress OTel constants and functions to `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py`: ATTR_SINK_TYPE, ATTR_SINK_DESTINATION, ATTR_SINK_ROWS_WRITTEN, ATTR_SINK_DURATION_MS, ATTR_SINK_STATUS constants. Add egress_span() context manager, record_egress_result(), record_egress_error() functions mirroring ingestion tracing. Ref: FR-010.
- [ ] T017 [US2] Add SinkConnector mixin to DltIngestionPlugin class declaration in `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`. Change to `class DltIngestionPlugin(IngestionPlugin, SinkConnector):`. Import SinkConnector, SinkConfig, EgressResult from floe_core.plugins. Ref: FR-005.
- [ ] T018 [US2] Implement list_available_sinks() and get_source_config() methods in `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`. list_available_sinks returns ["rest_api", "sql_database"]. get_source_config builds Iceberg Gold layer read config from catalog_config. Both wrapped in egress_span(), both check self._started. Ref: FR-006, FR-009.
- [ ] T019 [US2] Implement create_sink() method in `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`. Validates SinkConfig, creates dlt destination via dlt.destination() API. Raises SinkConfigurationError on invalid config. Wrapped in egress_span(). Ref: FR-007.
- [ ] T020 [US2] Implement write() method in `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`. Pushes Arrow table to destination, handles batch_size auto-chunking, generates SHA-256 checksum, generates idempotency_key, builds EgressResult with metrics. Rate limiting via tenacity backoff. Raises SinkWriteError/SinkConnectionError on failure. Wrapped in egress_span(). Ref: FR-008, FR-013, FR-016.
- [ ] T021 [US2] Update exports in `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/__init__.py`. Add new error classes (SinkConnectionError, SinkWriteError, SinkConfigurationError) and tracing functions (egress_span, record_egress_result, record_egress_error) to imports and __all__.
- [ ] T022 [US2] Verify all US2 tests pass. Run `pytest plugins/floe-ingestion-dlt/tests/unit/test_dlt_sink_*.py -v`.

**Checkpoint**: DltIngestionPlugin supports bidirectional data movement. Plugin developers can see a working reference implementation.

---

## Phase 5: User Story 3 — Egress Configuration in floe.yaml (Priority: P1)

**Goal**: Data engineers can declare reverse ETL destinations in floe.yaml alongside transforms, with full Pydantic validation and backwards compatibility.

**Independent Test**: Write a floe.yaml with a destinations: section, load via FloeSpec, verify schema validation.

### Tests for User Story 3

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T023 [P] [US3] Write DestinationConfig schema tests in `packages/floe-core/tests/unit/test_floe_spec_destinations.py`: test_destination_config_with_required_fields, test_destination_config_with_all_fields, test_destination_config_rejects_extra_fields (frozen), test_destination_config_rejects_empty_name, test_destination_config_validates_secret_ref_pattern, test_destination_config_rejects_hardcoded_credentials (FORBIDDEN_ENVIRONMENT_FIELDS), test_destination_config_batch_size_ge_1. Use `@pytest.mark.requirement("4G-FR-011")` and `@pytest.mark.requirement("4G-FR-018")`.
- [ ] T024 [P] [US3] Write FloeSpec destinations integration tests in `packages/floe-core/tests/unit/test_floe_spec_destinations.py`: test_floe_spec_with_destinations_validates, test_floe_spec_without_destinations_validates (FR-012 backwards compat), test_floe_spec_with_multiple_destinations, test_floe_spec_rejects_duplicate_destination_names. Use `@pytest.mark.requirement("4G-FR-012")`.
- [ ] T025 [P] [US3] Write egress schema contract test in `tests/contract/test_egress_schema_contract.py`: test_destination_config_schema_matches_contract, test_floe_spec_json_schema_includes_destinations, test_backwards_compat_existing_fixtures_validate. Use `@pytest.mark.requirement("4G-SC-004")`.

### Implementation for User Story 3

- [ ] T026 [US3] Add DestinationConfig Pydantic model to `packages/floe-core/src/floe_core/schemas/floe_spec.py`. ConfigDict(frozen=True, extra="forbid"). Fields: name (str, min_length=1, max_length=100), sink_type (str, min_length=1), connection_secret_ref (str, SECRET_NAME_PATTERN, max_length=253), source_table (str|None), config (dict|None), field_mapping (dict|None), batch_size (int|None, ge=1). Add validate_name and validate_connection_secret_ref field validators. Ref: FR-011, FR-018.
- [ ] T027 [US3] Add `destinations: list[DestinationConfig] | None = Field(default=None)` to FloeSpec model in `packages/floe-core/src/floe_core/schemas/floe_spec.py`. Ensure FORBIDDEN_ENVIRONMENT_FIELDS recursive check covers destination configs. Add unique destination name validator. Ref: FR-012.
- [ ] T028 [US3] Add DestinationConfig to schema exports in `packages/floe-core/src/floe_core/schemas/__init__.py`. Add to imports and __all__.
- [ ] T029 [US3] Verify all US3 tests pass. Run `pytest packages/floe-core/tests/unit/test_floe_spec_destinations.py tests/contract/test_egress_schema_contract.py -v`.

**Checkpoint**: Data engineers can define destinations in floe.yaml with full validation. Existing floe.yaml files validate unchanged.

---

## Phase 6: User Story 4 — Egress Governance via Manifest Whitelist (Priority: P1)

**Goal**: Platform engineers can restrict which sink types data engineers target via approved_sinks whitelist in manifest.yaml, consistent with the approved_plugins pattern.

**Independent Test**: Define approved_sinks whitelist in manifest fixture, verify compiler rejects unapproved sinks and accepts approved ones.

### Tests for User Story 4

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T030 [P] [US4] Write manifest approved_sinks tests in `packages/floe-core/tests/unit/test_manifest_approved_sinks.py`: test_approved_sinks_field_on_manifest, test_approved_sinks_none_allows_all (backwards compat), test_approved_sinks_only_valid_for_enterprise_scope, test_approved_sinks_rejected_for_domain_scope, test_approved_sinks_rejected_for_no_scope. Use `@pytest.mark.requirement("4G-FR-017")`.
- [ ] T031 [P] [US4] Write SinkWhitelistError and validation tests in `packages/floe-core/tests/unit/test_manifest_approved_sinks.py`: test_sink_whitelist_error_raised_for_unapproved, test_sink_whitelist_error_not_raised_for_approved, test_validate_sink_whitelist_with_empty_list, test_sink_whitelist_error_attributes. Use `@pytest.mark.requirement("4G-FR-017")`.
- [ ] T032 [P] [US4] Write governance contract test in `tests/contract/test_egress_schema_contract.py`: test_manifest_json_schema_includes_approved_sinks, test_sink_whitelist_error_importable. Use `@pytest.mark.requirement("4G-SC-005")`.

### Implementation for User Story 4

- [ ] T033 [US4] Add SinkWhitelistError exception class to `packages/floe-core/src/floe_core/schemas/plugins.py`. Mirror PluginWhitelistError: attributes sink_type (str), approved_sinks (list[str]). Add validate_sink_whitelist() function mirroring validate_domain_plugin_whitelist(). Ref: FR-017.
- [ ] T034 [US4] Add `approved_sinks: list[str] | None = Field(default=None)` to PlatformManifest in `packages/floe-core/src/floe_core/schemas/manifest.py`. Add scope constraint check in validate_scope_constraints(): approved_sinks only valid for scope="enterprise" (mirror C004 pattern for approved_plugins). Ref: FR-017.
- [ ] T035 [US4] Add SinkWhitelistError and validate_sink_whitelist to exports in `packages/floe-core/src/floe_core/schemas/__init__.py` and `packages/floe-core/src/floe_core/schemas/plugins.py` __all__.
- [ ] T036 [US4] Verify all US4 tests pass. Run `pytest packages/floe-core/tests/unit/test_manifest_approved_sinks.py tests/contract/test_egress_schema_contract.py -v`.

**Checkpoint**: Platform engineers can govern egress destinations. approved_sinks=None (default) allows all sinks for backwards compatibility.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, cross-story integration, and quality checks.

- [ ] T037 [P] Run full unit test suite: `make test-unit` — ensure no regressions
- [ ] T038 [P] Run contract test suite: `pytest tests/contract/test_sink_connector_contract.py tests/contract/test_egress_schema_contract.py -v`
- [ ] T039 Run type checking: `mypy --strict packages/floe-core/src/floe_core/plugins/sink.py plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- [ ] T040 Run linting: `ruff check packages/floe-core/ plugins/floe-ingestion-dlt/`
- [ ] T041 Validate quickstart.md examples are accurate against implemented code. Confirm a developer can follow the SinkConnector implementation example to create a working plugin (SC-001 proxy).
- [ ] T042 Verify backwards compatibility: existing FloeSpec and PlatformManifest fixtures validate without modification
- [ ] T043 Write performance smoke test in `plugins/floe-ingestion-dlt/tests/unit/test_dlt_sink_connector.py`: test_write_completes_within_5s_for_1000_rows -- create 1000-row Arrow table, mock destination, verify write() completes within 5 seconds. Use `@pytest.mark.requirement("4G-SC-007")`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — immediate
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1 - ABC)**: Depends on Phase 2 — BLOCKS US2
- **Phase 4 (US2 - dlt impl)**: Depends on Phase 3 (imports SinkConnector)
- **Phase 5 (US3 - FloeSpec)**: Depends on Phase 2 only — can parallelize with Phase 3/4
- **Phase 6 (US4 - Governance)**: Depends on Phase 2 only — can parallelize with Phase 3/4/5
- **Phase 7 (Polish)**: Depends on all prior phases

### User Story Dependencies

- **US1 (ABC)**: Foundation — no dependencies on other stories
- **US2 (dlt impl)**: Depends on US1 (imports SinkConnector ABC)
- **US3 (FloeSpec)**: Independent of US1/US2 — only needs Phase 2 exports
- **US4 (Governance)**: Independent of US1/US2/US3 — only needs Phase 2

### Parallelization Opportunities

After Phase 2 completes:
- **US1** can start immediately (P0)
- **US3** can start in parallel with US1 (different packages/files)
- **US4** can start in parallel with US1 and US3 (different packages/files)
- **US2** must wait for US1 completion (imports SinkConnector)

Within each story, all test tasks marked [P] can run in parallel.

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Dataclass/model tasks before ABC/service tasks
- Core implementation before integration
- Story complete before moving to next priority

---

## Parallel Example: After Phase 2

```bash
# Stream A: US1 (ABC definition) — P0, foundation for US2
Task T004: "Write ABC enforcement tests"
Task T005: "Write standalone/mixin tests"
Task T006: "Write dataclass tests"
Task T007: "Write ABC contract test"
# Then T008-T011 sequentially

# Stream B: US3 (FloeSpec schema) — P1, independent of US1
Task T023: "Write DestinationConfig schema tests"
Task T024: "Write FloeSpec destinations tests"
Task T025: "Write egress schema contract test"
# Then T026-T029 sequentially

# Stream C: US4 (Governance) — P1, independent of US1 and US3
Task T030: "Write manifest approved_sinks tests"
Task T031: "Write SinkWhitelistError tests"
Task T032: "Write governance contract test"
# Then T033-T036 sequentially

# After US1 completes → Start US2
# All test tasks within US2 (T012, T013, T014) can run in parallel
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (exports)
3. Complete Phase 3: US1 — ABC definition + tests
4. Complete Phase 4: US2 — dlt implementation + tests
5. **STOP and VALIDATE**: Core reverse ETL works end-to-end

### Incremental Delivery

1. Setup + Foundational → Exports ready
2. US1 (ABC) → Plugin developers can code against contract
3. US2 (dlt impl) → Data engineers can push data to destinations
4. US3 (FloeSpec) → Declarative config in floe.yaml
5. US4 (Governance) → Platform team can govern destinations
6. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group (300-600 LOC atomic commits)
- Stop at any checkpoint to validate story independently

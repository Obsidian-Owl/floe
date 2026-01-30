# Tasks: Artifact Promotion Lifecycle

**Input**: Design documents from `/specs/8c-promotion-lifecycle/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included - TDD approach with tests written before implementation

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

All paths relative to `packages/floe-core/`:
- **Source**: `src/floe_core/`
- **Tests**: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Schema definitions, manifest extension, and foundational types

- [ ] T001 [P] Create PromotionGate enum in `packages/floe-core/src/floe_core/schemas/promotion.py`
- [ ] T001a Create ArtifactsConfig schema with PromotionConfig in `packages/floe-core/src/floe_core/schemas/manifest.py`
  - ArtifactsConfig contains: registry (RegistryConfig), promotion (PromotionConfig | None)
  - Add `artifacts: ArtifactsConfig | None` field to PlatformManifest class
  - Export JSON Schema for IDE autocomplete
  - @pytest.mark.requirement("FR-009a")
- [ ] T001b [P] Unit tests for ArtifactsConfig and PlatformManifest.artifacts field in `packages/floe-core/tests/unit/schemas/test_manifest_artifacts.py`
  - Test default environments [dev, staging, prod] when not specified
  - Test custom environment configuration parsing
  - Test JSON Schema export
- [ ] T002 [P] Create GateStatus enum with PASSED/FAILED/SKIPPED/WARNING values in `packages/floe-core/src/floe_core/schemas/promotion.py`
  - Use str, Enum pattern for JSON serialization
  - Values must be lowercase strings: "passed", "failed", "skipped", "warning"
- [ ] T003 [P] Create AuditBackend enum in `packages/floe-core/src/floe_core/schemas/promotion.py`
- [ ] T004 Create GateResult Pydantic model with validation in `packages/floe-core/src/floe_core/schemas/promotion.py`
  - Include security_summary field for security gate results
- [ ] T005 Create EnvironmentConfig Pydantic model with policy_compliance always-true validation in `packages/floe-core/src/floe_core/schemas/promotion.py`
  - Include authorization: AuthorizationConfig | None field
  - Include lock: EnvironmentLock | None field
- [ ] T005a [P] Create AuthorizationConfig Pydantic model in `packages/floe-core/src/floe_core/schemas/promotion.py`
  - allowed_groups: list[str] | None
  - allowed_operators: list[str] | None
  - separation_of_duties: bool = False
  - @pytest.mark.requirement("FR-046", "FR-047")
- [ ] T005b [P] Create EnvironmentLock Pydantic model in `packages/floe-core/src/floe_core/schemas/promotion.py`
  - locked: bool
  - reason: str | None
  - locked_by: str | None
  - locked_at: datetime | None
  - @pytest.mark.requirement("FR-035")
- [ ] T005c [P] Create WebhookConfig Pydantic model in `packages/floe-core/src/floe_core/schemas/promotion.py`
  - url: str (HttpUrl)
  - events: list[str] (validate: ["promote", "rollback"])
  - headers: dict[str, str] | None
  - timeout_seconds: int = 30
  - retry_count: int = 3
  - @pytest.mark.requirement("FR-040", "FR-044")
- [ ] T005d [P] Create SecurityGateConfig Pydantic model in `packages/floe-core/src/floe_core/schemas/promotion.py`
  - command: str
  - block_on_severity: list[str] = ["CRITICAL", "HIGH"]
  - ignore_unfixed: bool = False
  - scanner_format: str = "trivy"  # trivy, grype
  - timeout_seconds: int = 600
  - @pytest.mark.requirement("FR-054", "FR-055", "FR-057")
- [ ] T005e [P] Create SecurityScanResult Pydantic model in `packages/floe-core/src/floe_core/schemas/promotion.py`
  - critical_count: int
  - high_count: int
  - medium_count: int
  - low_count: int
  - blocking_cves: list[str]
  - ignored_unfixed: int
  - @pytest.mark.requirement("FR-056")
- [ ] T006 Create PromotionConfig Pydantic model with default environments [dev, staging, prod] in `packages/floe-core/src/floe_core/schemas/promotion.py`
  - Include webhooks: list[WebhookConfig] | None field
  - Include gate_commands: dict[str, str | SecurityGateConfig] | None field
- [ ] T007 Create PromotionRecord Pydantic model with OCI annotation conversion methods in `packages/floe-core/src/floe_core/schemas/promotion.py`
  - Include trace_id: str field for observability linking
  - Include authorization_passed: bool | None field
  - Include authorized_via: str | None field (group name or operator)
- [ ] T008 Create RollbackImpactAnalysis Pydantic model in `packages/floe-core/src/floe_core/schemas/promotion.py`
- [ ] T009 Create RollbackRecord Pydantic model with OCI annotation conversion in `packages/floe-core/src/floe_core/schemas/promotion.py`
  - Include trace_id: str field for observability linking
- [ ] T010 Create promotion-specific exceptions in `packages/floe-core/src/floe_core/oci/errors.py`
  - GateValidationError(OCIError): exit_code=8, attrs: gate, details
  - InvalidTransitionError(OCIError): exit_code=9, attrs: from_env, to_env, reason
  - TagExistsError(OCIError): exit_code=10, attrs: tag, existing_digest
  - VersionNotPromotedError(OCIError): exit_code=11, attrs: tag, environment, available_versions
  - AuthorizationError(OCIError): exit_code=12, attrs: operator, required_groups, reason
  - EnvironmentLockedError(OCIError): exit_code=13, attrs: environment, locked_by, locked_at, reason
  - NOTE: Reuse existing SignatureVerificationError (exit_code=6) - do NOT create duplicate
- [ ] T011 Export new schemas from `packages/floe-core/src/floe_core/schemas/__init__.py`
- [ ] T012 [P] Unit tests for all enums and models in `packages/floe-core/tests/unit/schemas/test_promotion_schemas.py`

**Checkpoint**: All schemas validated, manifest extended, tests passing

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core PromotionController infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T013 Create PromotionController class skeleton in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T014 Implement PromotionController.__init__ accepting OCIClient, PromotionConfig, PolicyEnforcer in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T014a [P] Contract test for PolicyEnforcer integration in `tests/contract/test_promotion_policy_contract.py`
  - Verify PolicyEnforcer can be instantiated and called from PromotionController context
  - Verify EnforcementResult.passed is boolean
  - Verify EnforcementResult.violations is iterable
  - @pytest.mark.requirement("FR-010")
- [ ] T015 Implement PromotionController.validate_transition() for environment order validation in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T016 Implement PromotionController._get_environment_config() to lookup env by name in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T017 Implement PromotionController._run_gate() for single gate execution with timeout in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Use subprocess with timeout parameter
  - Handle subprocess.TimeoutExpired → GateResult(status=FAILED, error="Gate execution timed out...")
  - Send SIGTERM on timeout, SIGKILL after 5s grace period
  - Record duration_ms even for timed-out gates
- [ ] T017a [P] Unit test for gate timeout handling in `packages/floe-core/tests/unit/oci/test_gate_timeout.py`
  - Test gate completing within timeout → PASSED
  - Test gate exceeding timeout → FAILED with timeout error
  - Test SIGTERM/SIGKILL escalation
  - @pytest.mark.requirement("FR-012a", "FR-012b", "FR-012c")
- [ ] T018 Implement PromotionController._run_policy_compliance_gate() using PolicyEnforcer in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Import PolicyEnforcer from floe_core.enforcement
  - Call PolicyEnforcer.enforce() with dry_run parameter
  - Convert EnforcementResult to GateResult
  - Handle PolicyEnforcer exceptions gracefully
- [ ] T019 Implement PromotionController._run_all_gates() orchestrating all required gates in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T020 Implement PromotionController._verify_signature() using existing verification.py in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T021 Implement PromotionController._create_env_tag() for immutable tag creation in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T022 Implement PromotionController._update_latest_tag() for mutable tag update in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T023 Implement PromotionController._store_promotion_record() for OCI annotation storage in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T024a Add OpenTelemetry span for PromotionController.promote() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Span name: "floe.oci.promote"
  - Attributes: artifact_ref, from_env, to_env, dry_run
  - Record gate durations as child spans
  - Extract and return trace_id for CLI output
- [ ] T024b Add OpenTelemetry span for PromotionController.rollback() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Span name: "floe.oci.rollback"
  - Attributes: artifact_ref, environment, reason
  - Extract and return trace_id for CLI output
- [ ] T024c Add OpenTelemetry span for PromotionController._run_gate() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Span name: "floe.oci.gate.{gate_name}"
  - Attributes: gate_type, timeout_seconds
  - Record gate duration_ms
- [ ] T024d Add OpenTelemetry span for PromotionController._verify_signature() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Span name: "floe.oci.promote.verify"
  - Attributes: enforcement_mode, cached
- [ ] T024e [P] Unit test for promotion OpenTelemetry spans in `packages/floe-core/tests/unit/oci/test_promotion_telemetry.py`
  - Use in-memory span exporter to verify spans are created
  - Verify span hierarchy (promote → gate → verify)
  - Verify trace_id is extracted and returned
  - @pytest.mark.requirement("FR-024", "FR-033")
- [ ] T025 Export PromotionController from `packages/floe-core/src/floe_core/oci/__init__.py`
- [ ] T026 Unit tests for PromotionController with mocked OCIClient in `packages/floe-core/tests/unit/oci/test_promotion_controller.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Promote Artifact to Next Environment (Priority: P1) 🎯 MVP

**Goal**: Platform engineers can promote validated artifacts between environments with gate validation and signature verification

**Independent Test**: Run `floe platform promote v1.2.3 --from=dev --to=staging` and verify artifact tagged with `v1.2.3-staging`

**Requirements**: FR-001, FR-001a, FR-001b, FR-002, FR-003, FR-004, FR-005, FR-006, FR-008, FR-009, FR-010, FR-011, FR-012

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T027 [P] [US1] Contract test for promote command exit codes in `packages/floe-core/tests/contract/test_promote_contract.py`
- [ ] T028 [P] [US1] Unit test for PromotionController.promote() success path in `packages/floe-core/tests/unit/oci/test_promotion_promote.py`
- [ ] T029 [P] [US1] Unit test for PromotionController.promote() gate failure path in `packages/floe-core/tests/unit/oci/test_promotion_promote.py`
- [ ] T030 [P] [US1] Unit test for PromotionController.promote() signature failure path in `packages/floe-core/tests/unit/oci/test_promotion_promote.py`
- [ ] T031 [P] [US1] Integration test for full promotion workflow in `packages/floe-core/tests/integration/oci/test_promotion_workflow.py`
  - MUST inherit from IntegrationTestBase
  - required_services = [("registry", 30500)]
  - Use generate_unique_namespace() for test isolation
  - Call check_infrastructure() before operations
- [ ] T031a [P] [US1] Unit test for promotion failure recovery in `packages/floe-core/tests/unit/oci/test_promotion_recovery.py`
  - Test retry when env tag exists with matching digest (idempotent)
  - Test failure when env tag exists with different digest
  - Test latest tag update retry
  - @pytest.mark.requirement("NFR-004")
- [ ] T031b [P] [US1] Unit test for registry unavailable mid-promotion in `packages/floe-core/tests/unit/oci/test_promotion_resilience.py`
  - Mock OCIClient to fail after gate pass but before tag creation
  - Verify no partial state created
  - Verify error message is actionable
- [ ] T031c [P] [US1] Unit test for OCI annotation size limit in `packages/floe-core/tests/unit/oci/test_promotion_annotations.py`
  - Create PromotionRecord that exceeds 64KB when serialized
  - Verify graceful degradation (truncate details, keep core fields)
  - Verify warning logged
  - @pytest.mark.requirement("NFR-005")
- [ ] T031d [P] [US1] Unit test for concurrent promotion to same environment in `packages/floe-core/tests/unit/oci/test_promotion_concurrency.py`
  - Simulate two promotions racing to create same tag
  - Verify one succeeds, one fails with TagExistsError
  - Verify no data corruption

### Implementation for User Story 1

- [ ] T032 [US1] Implement PromotionController.promote() full flow in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T032a [US1] Implement promotion failure recovery logic in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Check if env tag already exists with matching digest → skip tag creation
  - Check if latest tag points to correct digest → skip update
  - Retry OCI annotation write on transient failures
  - Log warning for partial promotion state
- [ ] T033 [US1] Create promote CLI command with options in `packages/floe-core/src/floe_core/cli/platform/promote.py`
- [ ] T034 [US1] Implement promote command argument parsing (tag, --from, --to, --manifest) in `packages/floe-core/src/floe_core/cli/platform/promote.py`
- [ ] T035 [US1] Implement promote command success output formatting in `packages/floe-core/src/floe_core/cli/platform/promote.py`
- [ ] T036 [US1] Implement promote command error output with exit codes in `packages/floe-core/src/floe_core/cli/platform/promote.py`
- [ ] T037 [US1] Wire promote command to platform Click group in `packages/floe-core/src/floe_core/cli/platform/__init__.py`
- [ ] T038 [US1] Add @pytest.mark.requirement decorators for FR-001 through FR-012 to tests
- [ ] T038a Create contract test for PromotionRecord schema stability in `tests/contract/test_promotion_record_contract.py`
  - Verify PromotionRecord has all required fields for Epic 9B consumers
  - Verify JSON Schema export works
  - Verify OCI annotation key patterns (dev.floe.promotion.*)
  - Test round-trip serialization (model → JSON → model)
  - @pytest.mark.requirement("FR-023", "FR-027")

**Checkpoint**: `floe platform promote` works end-to-end with gates and signatures

---

## Phase 4: User Story 2 - Dry-Run Promotion (Priority: P1)

**Goal**: Platform engineers can preview promotion impact before executing

**Independent Test**: Run `floe platform promote v1.2.3 --from=staging --to=prod --dry-run` and verify no tags created, gates listed

**Requirements**: FR-007

### Tests for User Story 2 ⚠️

- [ ] T039 [P] [US2] Unit test for PromotionController.promote(dry_run=True) in `packages/floe-core/tests/unit/oci/test_promotion_dryrun.py`
- [ ] T040 [P] [US2] Unit test for dry-run output formatting in `packages/floe-core/tests/unit/cli/test_promote_cli.py`

### Implementation for User Story 2

- [ ] T041 [US2] Implement dry_run logic in PromotionController.promote() in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T042 [US2] Add --dry-run flag to promote CLI command in `packages/floe-core/src/floe_core/cli/platform/promote.py`
- [ ] T043 [US2] Implement dry-run output format (gates to validate, signature status, estimated time) in `packages/floe-core/src/floe_core/cli/platform/promote.py`
- [ ] T044 [US2] Add @pytest.mark.requirement("FR-007") to tests

**Checkpoint**: `floe platform promote --dry-run` shows accurate preview

---

## Phase 5: User Story 3 - Rollback to Previous Version (Priority: P2)

**Goal**: Platform engineers can rollback environments to previously promoted versions

**Independent Test**: Run `floe platform rollback v1.2.2 --env=prod` and verify latest-prod updated

**Requirements**: FR-013, FR-014, FR-015, FR-016, FR-017

### Tests for User Story 3 ⚠️

- [ ] T045 [P] [US3] Contract test for rollback command exit codes in `packages/floe-core/tests/contract/test_rollback_contract.py`
- [ ] T046 [P] [US3] Unit test for PromotionController.rollback() success path in `packages/floe-core/tests/unit/oci/test_promotion_rollback.py`
- [ ] T047 [P] [US3] Unit test for PromotionController.rollback() version-not-found path in `packages/floe-core/tests/unit/oci/test_promotion_rollback.py`
- [ ] T048 [P] [US3] Unit test for PromotionController.analyze_rollback_impact() in `packages/floe-core/tests/unit/oci/test_promotion_rollback.py`
- [ ] T049 [P] [US3] Integration test for rollback workflow in `packages/floe-core/tests/integration/oci/test_rollback_workflow.py`

### Implementation for User Story 3

- [ ] T050 [US3] Implement PromotionController.rollback() in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T051 [US3] Implement PromotionController.analyze_rollback_impact() in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T052 [US3] Implement PromotionController._store_rollback_record() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Query existing rollback tags to determine next sequence number
  - Create immutable rollback tag with incremented suffix (e.g., v1.2.2-prod-rollback-2)
  - Update latest-{env} to point to rollback tag
  - Store RollbackRecord in OCI annotations
- [ ] T053 [US3] Create rollback CLI command with options in `packages/floe-core/src/floe_core/cli/platform/rollback.py`
- [ ] T054 [US3] Implement rollback command argument parsing (tag, --env, --reason, --dry-run) in `packages/floe-core/src/floe_core/cli/platform/rollback.py`
- [ ] T055 [US3] Implement rollback dry-run with impact analysis output in `packages/floe-core/src/floe_core/cli/platform/rollback.py`
- [ ] T056 [US3] Implement rollback success output formatting in `packages/floe-core/src/floe_core/cli/platform/rollback.py`
- [ ] T057 [US3] Wire rollback command to platform Click group in `packages/floe-core/src/floe_core/cli/platform/__init__.py`
- [ ] T058 [US3] Add @pytest.mark.requirement decorators for FR-013 through FR-017 to tests

**Checkpoint**: `floe platform rollback` works with impact analysis

---

## Phase 6: User Story 4 - Query Promotion Status (Priority: P2)

**Goal**: Platform operators can query current promotion status across all environments

**Independent Test**: Run `floe platform status` and verify table shows all environments with versions

**Requirements**: FR-023, FR-024, FR-027

### Tests for User Story 4 ⚠️

- [ ] T059 [P] [US4] Unit test for PromotionController.get_status() in `packages/floe-core/tests/unit/oci/test_promotion_status.py`
- [ ] T060 [P] [US4] Unit test for status table/json/yaml formatting in `packages/floe-core/tests/unit/cli/test_status_cli.py`

### Implementation for User Story 4

- [ ] T061 [US4] Implement PromotionController.get_status() in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T062 [US4] Implement PromotionController._get_promotion_history() for history queries in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T063 [US4] Update status CLI command with promotion status in `packages/floe-core/src/floe_core/cli/platform/status.py`
- [ ] T064 [US4] Implement --env filter for single environment status in `packages/floe-core/src/floe_core/cli/platform/status.py`
- [ ] T065 [US4] Implement --history=N for promotion history in `packages/floe-core/src/floe_core/cli/platform/status.py`
- [ ] T066 [US4] Implement --format=table|json|yaml output formatting in `packages/floe-core/src/floe_core/cli/platform/status.py`
- [ ] T067 [US4] Add @pytest.mark.requirement decorators for FR-023, FR-024, FR-027 to tests

**Checkpoint**: `floe platform status` shows complete promotion state

---

## Phase 7: User Story 5 - Verification Before Artifact Use (Priority: P1)

**Goal**: Artifacts are verified before use based on enforcement policy (enforce/warn/off)

**Independent Test**: Run with unsigned artifact when enforcement=enforce and verify failure

**Requirements**: FR-018, FR-019, FR-020, FR-021, FR-022

### Tests for User Story 5 ⚠️

- [ ] T068 [P] [US5] Unit test for verification with enforcement=enforce in `packages/floe-core/tests/unit/oci/test_verification_enforcement.py`
- [ ] T069 [P] [US5] Unit test for verification with enforcement=warn in `packages/floe-core/tests/unit/oci/test_verification_enforcement.py`
- [ ] T070 [P] [US5] Unit test for verification with enforcement=off in `packages/floe-core/tests/unit/oci/test_verification_enforcement.py`
- [ ] T071 [P] [US5] Unit test for verification result caching in `packages/floe-core/tests/unit/oci/test_verification_enforcement.py`

### Implementation for User Story 5

- [ ] T072 [US5] Implement verification caching in PromotionController (reuse digest-based cache) in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T073 [US5] Implement enforcement policy handling (enforce/warn/off) in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T074 [US5] Add "Signature verified" / "WARNING: Artifact is unsigned" messages to CLI output in `packages/floe-core/src/floe_core/cli/platform/promote.py`
- [ ] T075 [US5] Add @pytest.mark.requirement decorators for FR-018 through FR-022 to tests

**Checkpoint**: Verification respects enforcement policy with caching

---

## Phase 8: User Story 6 - Cross-Registry Sync (Priority: P3)

**Goal**: Artifacts can be promoted to multiple registries for disaster recovery

**Independent Test**: Configure two registries, promote artifact, verify both have matching digests

**Requirements**: FR-028, FR-029, FR-030

### Tests for User Story 6 ⚠️

- [ ] T076 [P] [US6] Unit test for multi-registry promotion success in `packages/floe-core/tests/unit/oci/test_promotion_multiregistry.py`
- [ ] T077 [P] [US6] Unit test for partial success (secondary fails) in `packages/floe-core/tests/unit/oci/test_promotion_multiregistry.py`
- [ ] T078 [P] [US6] Unit test for digest verification across registries in `packages/floe-core/tests/unit/oci/test_promotion_multiregistry.py`

### Implementation for User Story 6

- [ ] T079 [US6] Extend PromotionConfig to support secondary registries in `packages/floe-core/src/floe_core/schemas/promotion.py`
- [ ] T080 [US6] Implement PromotionController._sync_to_registries() for parallel registry push in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T081 [US6] Implement digest verification across registries in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T082 [US6] Implement partial success handling (primary ok, secondary failed = warning) in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T083 [US6] Add registry sync status to PromotionRecord in `packages/floe-core/src/floe_core/schemas/promotion.py`
- [ ] T084 [US6] Add @pytest.mark.requirement decorators for FR-028 through FR-030 to tests

**Checkpoint**: Multi-registry sync works with partial failure handling

---

## Phase 9: User Story 7 - CI/CD Automation Integration (Priority: P1)

**Goal**: DevOps engineers can fully automate promotion pipelines with structured JSON output and documented exit codes

**Independent Test**: Run `floe platform promote v1.2.3 --from=dev --to=staging --output=json` and verify structured JSON with trace_id

**Requirements**: FR-031, FR-032, FR-033, FR-034

### Tests for User Story 7 ⚠️

- [ ] T085 [P] [US7] Unit test for --output=json flag on promote command in `packages/floe-core/tests/unit/cli/test_promote_json.py`
  - Verify JSON includes: success, promotion_id, artifact_digest, gate_results, trace_id
  - Verify error case includes error field
  - @pytest.mark.requirement("FR-031", "FR-034")
- [ ] T086 [P] [US7] Unit test for --output=json flag on rollback command in `packages/floe-core/tests/unit/cli/test_rollback_json.py`
  - Verify JSON includes: success, rollback_id, artifact_digest, trace_id
  - @pytest.mark.requirement("FR-031")
- [ ] T087 [P] [US7] Unit test for --output=json flag on status command in `packages/floe-core/tests/unit/cli/test_status_json.py`
  - Verify JSON array of environment statuses
  - @pytest.mark.requirement("FR-031")
- [ ] T088 [P] [US7] Contract test for exit codes in `packages/floe-core/tests/contract/test_exit_codes_contract.py`
  - 0 = success
  - 8 = gate failure (GateValidationError)
  - 9 = invalid transition (InvalidTransitionError)
  - 10 = tag exists (TagExistsError)
  - 11 = version not promoted (VersionNotPromotedError)
  - 12 = authorization failed (AuthorizationError)
  - 13 = environment locked (EnvironmentLockedError)
  - @pytest.mark.requirement("FR-032")
- [ ] T089 [P] [US7] Unit test for trace_id inclusion in CLI output in `packages/floe-core/tests/unit/cli/test_trace_id_output.py`
  - Verify trace_id appears in both human and JSON output
  - @pytest.mark.requirement("FR-033")

### Implementation for User Story 7

- [ ] T090 [US7] Add --output=json|table flag to promote command in `packages/floe-core/src/floe_core/cli/platform/promote.py`
- [ ] T091 [US7] Implement JSON output formatting for promote command in `packages/floe-core/src/floe_core/cli/platform/promote.py`
  - success: bool, promotion_id: str, artifact_digest: str, gate_results: list, trace_id: str
- [ ] T092 [US7] Add --output=json flag to rollback command in `packages/floe-core/src/floe_core/cli/platform/rollback.py`
- [ ] T093 [US7] Add --output=json flag to status command in `packages/floe-core/src/floe_core/cli/platform/status.py`
- [ ] T094 [US7] Implement exit code mapping from exceptions in `packages/floe-core/src/floe_core/cli/platform/promote.py`
  - Map each promotion exception type to its exit code
- [ ] T095 [US7] Add trace_id to human-readable CLI output in `packages/floe-core/src/floe_core/cli/platform/promote.py`
- [ ] T096 [US7] Add @pytest.mark.requirement decorators for FR-031 through FR-034 to tests

**Checkpoint**: `floe platform promote --output=json` returns structured JSON with trace_id and correct exit codes

---

## Phase 10: User Story 8 - Environment Lock/Freeze (Priority: P1)

**Goal**: SREs can lock environments during incidents to prevent promotions

**Independent Test**: Run `floe platform lock --env=prod --reason="Incident #123"` then attempt promotion and verify rejection

**Requirements**: FR-035, FR-036, FR-037, FR-038, FR-039

### Tests for User Story 8 ⚠️

- [ ] T097 [P] [US8] Unit test for PromotionController.lock_environment() in `packages/floe-core/tests/unit/oci/test_environment_lock.py`
  - Verify lock is stored in OCI annotations
  - Verify lock includes: reason, locked_by, locked_at
  - @pytest.mark.requirement("FR-035")
- [ ] T098 [P] [US8] Unit test for PromotionController.unlock_environment() in `packages/floe-core/tests/unit/oci/test_environment_lock.py`
  - Verify lock is removed
  - Verify unlock event is recorded
  - @pytest.mark.requirement("FR-037")
- [ ] T099 [P] [US8] Unit test for promotion rejection on locked environment in `packages/floe-core/tests/unit/oci/test_environment_lock.py`
  - Verify EnvironmentLockedError raised with exit_code=13
  - Verify error includes: locked_by, locked_at, reason
  - @pytest.mark.requirement("FR-036")
- [ ] T100 [P] [US8] Unit test for lock status in status command output in `packages/floe-core/tests/unit/cli/test_status_lock.py`
  - Verify locked environments shown with lock icon/indicator
  - Verify lock reason and operator displayed
  - @pytest.mark.requirement("FR-039")
- [ ] T101 [P] [US8] Integration test for lock/unlock workflow in `packages/floe-core/tests/integration/oci/test_lock_workflow.py`
  - Test full cycle: lock → reject promotion → unlock → promotion succeeds
  - @pytest.mark.requirement("FR-035", "FR-036", "FR-037")

### Implementation for User Story 8

- [ ] T102 [US8] Implement PromotionController.lock_environment() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Store EnvironmentLock in OCI annotations
  - Record lock event in audit trail
- [ ] T103 [US8] Implement PromotionController.unlock_environment() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Remove lock from OCI annotations
  - Record unlock event in audit trail with reason
- [ ] T104 [US8] Add lock check to PromotionController.promote() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Query lock status before running gates
  - Raise EnvironmentLockedError if locked
- [ ] T105 [US8] Create lock CLI command in `packages/floe-core/src/floe_core/cli/platform/lock.py`
  - `floe platform lock --env=<env> --reason=<reason>`
- [ ] T106 [US8] Create unlock CLI command in `packages/floe-core/src/floe_core/cli/platform/lock.py`
  - `floe platform unlock --env=<env> --reason=<reason>`
- [ ] T107 [US8] Wire lock/unlock commands to platform Click group in `packages/floe-core/src/floe_core/cli/platform/__init__.py`
- [ ] T108 [US8] Update status command to show lock status in `packages/floe-core/src/floe_core/cli/platform/status.py`
  - Add lock indicator column
  - Show lock reason and operator in detailed view
- [ ] T109 [US8] Add @pytest.mark.requirement decorators for FR-035 through FR-039 to tests

**Checkpoint**: `floe platform lock/unlock` works, promotions blocked on locked environments

---

## Phase 11: User Story 9 - Webhook Notifications (Priority: P2)

**Goal**: SREs receive real-time notifications of promotion and rollback events via webhooks

**Independent Test**: Configure webhook URL, promote artifact, verify POST request sent with event payload

**Requirements**: FR-040, FR-041, FR-042, FR-043, FR-044

### Tests for User Story 9 ⚠️

- [ ] T110 [P] [US9] Unit test for WebhookNotifier.notify() on promotion in `packages/floe-core/tests/unit/oci/test_webhooks.py`
  - Verify payload includes: event_type, promotion_id, artifact_tag, source_env, target_env, operator, timestamp, trace_id
  - @pytest.mark.requirement("FR-040", "FR-042")
- [ ] T111 [P] [US9] Unit test for WebhookNotifier.notify() on rollback in `packages/floe-core/tests/unit/oci/test_webhooks.py`
  - Verify payload includes: event_type="rollback", reason, impact_analysis
  - @pytest.mark.requirement("FR-041", "FR-042")
- [ ] T112 [P] [US9] Unit test for non-blocking webhook delivery in `packages/floe-core/tests/unit/oci/test_webhooks.py`
  - Verify promotion succeeds even when webhook fails
  - Verify warning logged for webhook failure
  - @pytest.mark.requirement("FR-043")
- [ ] T113 [P] [US9] Unit test for parallel webhook delivery in `packages/floe-core/tests/unit/oci/test_webhooks.py`
  - Configure 3 webhooks, verify all called in parallel
  - @pytest.mark.requirement("FR-044")
- [ ] T114 [P] [US9] Integration test for webhook with mock server in `packages/floe-core/tests/integration/oci/test_webhook_workflow.py`
  - Start mock HTTP server
  - Promote artifact
  - Verify mock received correct payload

### Implementation for User Story 9

- [ ] T115 [US9] Create WebhookNotifier class in `packages/floe-core/src/floe_core/oci/webhooks.py`
  - __init__(webhooks: list[WebhookConfig])
  - async notify(event_type: str, payload: dict) -> list[WebhookResult]
- [ ] T116 [US9] Implement WebhookNotifier._build_payload() in `packages/floe-core/src/floe_core/oci/webhooks.py`
  - Build event payload with all required fields
  - Include trace_id from current span context
- [ ] T117 [US9] Implement WebhookNotifier._send_webhook() with retry in `packages/floe-core/src/floe_core/oci/webhooks.py`
  - Use httpx for async HTTP
  - Implement configurable retry with exponential backoff
  - Respect timeout_seconds from WebhookConfig
- [ ] T118 [US9] Implement parallel webhook delivery using asyncio.gather() in `packages/floe-core/src/floe_core/oci/webhooks.py`
- [ ] T119 [US9] Integrate WebhookNotifier into PromotionController.promote() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Call webhooks after successful promotion
  - Log warnings for failed webhooks but don't raise
- [ ] T120 [US9] Integrate WebhookNotifier into PromotionController.rollback() in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T121 [US9] Add @pytest.mark.requirement decorators for FR-040 through FR-044 to tests

**Checkpoint**: Webhook notifications sent on promotion/rollback events

---

## Phase 12: User Story 10 - Authorization and Access Control (Priority: P1)

**Goal**: Security engineers can configure environment-specific authorization rules

**Independent Test**: Configure prod to require "platform-admins" group, attempt promotion with non-admin, verify rejection

**Requirements**: FR-045, FR-046, FR-047, FR-048, FR-049

### Tests for User Story 10 ⚠️

- [ ] T122 [P] [US10] Unit test for AuthorizationChecker.check_authorization() in `packages/floe-core/tests/unit/oci/test_authorization.py`
  - Verify group-based authorization
  - Verify operator-based authorization
  - @pytest.mark.requirement("FR-046", "FR-047")
- [ ] T123 [P] [US10] Unit test for authorization failure error message in `packages/floe-core/tests/unit/oci/test_authorization.py`
  - Verify error includes: operator, required groups, reason
  - @pytest.mark.requirement("FR-049")
- [ ] T124 [P] [US10] Unit test for authorization decision audit in `packages/floe-core/tests/unit/oci/test_authorization.py`
  - Verify PromotionRecord includes authorization_passed and authorized_via
  - @pytest.mark.requirement("FR-048")
- [ ] T125 [P] [US10] Contract test for operator identity from registry auth in `packages/floe-core/tests/contract/test_authorization_contract.py`
  - Verify operator identity extracted from OCIClient auth context
  - @pytest.mark.requirement("FR-045")
- [ ] T126 [P] [US10] Integration test for authorization workflow in `packages/floe-core/tests/integration/oci/test_authorization_workflow.py`
  - Configure authorization rules
  - Test authorized and unauthorized operators

### Implementation for User Story 10

- [ ] T127 [US10] Create AuthorizationChecker class in `packages/floe-core/src/floe_core/oci/authorization.py`
  - __init__(config: AuthorizationConfig)
  - check_authorization(operator: str, groups: list[str]) -> AuthorizationResult
- [ ] T128 [US10] Implement AuthorizationChecker._get_operator_identity() in `packages/floe-core/src/floe_core/oci/authorization.py`
  - Extract operator identity from OCIClient auth context
  - Support OIDC claims and basic auth username
- [ ] T129 [US10] Implement AuthorizationChecker._get_operator_groups() in `packages/floe-core/src/floe_core/oci/authorization.py`
  - Extract groups from OIDC claims if available
  - Support external group membership lookup (future extensibility)
- [ ] T130 [US10] Implement group-based authorization check in `packages/floe-core/src/floe_core/oci/authorization.py`
  - Check if operator's groups intersect with allowed_groups
- [ ] T131 [US10] Integrate AuthorizationChecker into PromotionController.promote() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Check authorization before running gates
  - Raise AuthorizationError with exit_code=12 if unauthorized
  - Record authorization decision in PromotionRecord
- [ ] T132 [US10] Export AuthorizationChecker from `packages/floe-core/src/floe_core/oci/__init__.py`
- [ ] T133 [US10] Add @pytest.mark.requirement decorators for FR-045 through FR-049 to tests

**Checkpoint**: Authorization checks enforced with clear error messages

---

## Phase 13: User Story 11 - Separation of Duties (Priority: P2)

**Goal**: Compliance officers can enforce that the same operator cannot promote through all environments

**Independent Test**: Enable separation-of-duties, have same operator promote dev→staging→prod, verify final promotion rejected

**Requirements**: FR-050, FR-051, FR-052, FR-053

### Tests for User Story 11 ⚠️

- [ ] T134 [P] [US11] Unit test for separation of duties violation detection in `packages/floe-core/tests/unit/oci/test_separation_of_duties.py`
  - Same operator promoted staging and attempts prod → REJECT
  - @pytest.mark.requirement("FR-051")
- [ ] T135 [P] [US11] Unit test for separation of duties success in `packages/floe-core/tests/unit/oci/test_separation_of_duties.py`
  - Different operator promoted staging, different attempts prod → ALLOW
  - @pytest.mark.requirement("FR-051")
- [ ] T136 [P] [US11] Unit test for separation of duties disabled in `packages/floe-core/tests/unit/oci/test_separation_of_duties.py`
  - separation_of_duties=false, same operator → ALLOW
  - @pytest.mark.requirement("FR-053")
- [ ] T137 [P] [US11] Unit test for separation of duties violation audit in `packages/floe-core/tests/unit/oci/test_separation_of_duties.py`
  - Verify violation logged with operator details
  - @pytest.mark.requirement("FR-052")
- [ ] T138 [P] [US11] Integration test for separation of duties workflow in `packages/floe-core/tests/integration/oci/test_separation_workflow.py`

### Implementation for User Story 11

- [ ] T139 [US11] Implement AuthorizationChecker.check_separation_of_duties() in `packages/floe-core/src/floe_core/oci/authorization.py`
  - Query promotion history for artifact
  - Check if current operator promoted to previous environment
  - Return violation if same operator in consecutive environments
- [ ] T140 [US11] Implement promotion history query for separation check in `packages/floe-core/src/floe_core/oci/authorization.py`
  - Get previous promotions for specific artifact version
  - Extract operator from each PromotionRecord
- [ ] T141 [US11] Integrate separation of duties into PromotionController.promote() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Check separation_of_duties if enabled in AuthorizationConfig
  - Raise AuthorizationError with clear violation message
  - Record violation in audit trail
- [ ] T142 [US11] Add @pytest.mark.requirement decorators for FR-050 through FR-053 to tests

**Checkpoint**: Separation of duties enforced when enabled

---

## Phase 14: User Story 12 - Security Gate Configuration (Priority: P1)

**Goal**: Security engineers can configure security scan severity thresholds

**Independent Test**: Configure security gate to block on CRITICAL/HIGH only, promote artifact with MEDIUM vulnerabilities, verify success

**Requirements**: FR-054, FR-055, FR-056, FR-057

### Tests for User Story 12 ⚠️

- [ ] T143 [P] [US12] Unit test for Trivy JSON output parsing in `packages/floe-core/tests/unit/oci/test_security_gate.py`
  - Parse Trivy JSON output
  - Count vulnerabilities by severity
  - @pytest.mark.requirement("FR-057")
- [ ] T144 [P] [US12] Unit test for Grype JSON output parsing in `packages/floe-core/tests/unit/oci/test_security_gate.py`
  - Parse Grype JSON output
  - Count vulnerabilities by severity
  - @pytest.mark.requirement("FR-057")
- [ ] T145 [P] [US12] Unit test for severity threshold blocking in `packages/floe-core/tests/unit/oci/test_security_gate.py`
  - block_on_severity=[CRITICAL, HIGH], artifact has HIGH → FAIL
  - block_on_severity=[CRITICAL, HIGH], artifact has only MEDIUM → PASS with warning
  - @pytest.mark.requirement("FR-054")
- [ ] T146 [P] [US12] Unit test for ignore_unfixed option in `packages/floe-core/tests/unit/oci/test_security_gate.py`
  - ignore_unfixed=true, unfixed HIGH vuln → not counted
  - ignore_unfixed=false, unfixed HIGH vuln → counted
  - @pytest.mark.requirement("FR-055")
- [ ] T147 [P] [US12] Unit test for security summary in gate result in `packages/floe-core/tests/unit/oci/test_security_gate.py`
  - Verify GateResult includes SecurityScanResult
  - Verify counts by severity and blocking CVE IDs
  - @pytest.mark.requirement("FR-056")
- [ ] T148 [P] [US12] Integration test for security gate workflow in `packages/floe-core/tests/integration/oci/test_security_gate_workflow.py`

### Implementation for User Story 12

- [ ] T149 [US12] Create SecurityGateRunner class in `packages/floe-core/src/floe_core/oci/security_gate.py`
  - __init__(config: SecurityGateConfig)
  - run(artifact_ref: str) -> GateResult
- [ ] T150 [US12] Implement Trivy JSON parser in `packages/floe-core/src/floe_core/oci/security_gate.py`
  - Parse Trivy JSON output structure
  - Extract severity, CVE ID, fixed_version
- [ ] T151 [US12] Implement Grype JSON parser in `packages/floe-core/src/floe_core/oci/security_gate.py`
  - Parse Grype JSON output structure
  - Extract severity, CVE ID, fixed_version
- [ ] T152 [US12] Implement severity threshold evaluation in `packages/floe-core/src/floe_core/oci/security_gate.py`
  - Filter vulnerabilities by severity threshold
  - Apply ignore_unfixed filter
  - Determine pass/fail based on blocking vulnerabilities
- [ ] T153 [US12] Implement SecurityScanResult population in `packages/floe-core/src/floe_core/oci/security_gate.py`
  - Count by severity
  - List blocking CVE IDs
  - Count ignored unfixed vulnerabilities
- [ ] T154 [US12] Integrate SecurityGateRunner into PromotionController._run_gate() in `packages/floe-core/src/floe_core/oci/promotion.py`
  - Detect security_scan gate type
  - Use SecurityGateRunner instead of generic command execution
- [ ] T155 [US12] Add security summary to CLI output in `packages/floe-core/src/floe_core/cli/platform/promote.py`
  - Show vulnerability counts on success/warning
  - Show blocking CVEs on failure
- [ ] T156 [US12] Add @pytest.mark.requirement decorators for FR-054 through FR-057 to tests

**Checkpoint**: Security gate respects severity thresholds with detailed output

---

## Phase 15: Audit Backend Plugin (Priority: P2)

**Purpose**: Pluggable audit storage backends per FR-025

**Requirements**: FR-025, FR-025a, FR-025b, FR-025c, FR-026

### Tests for Audit Backend ⚠️

- [ ] T157 [P] Contract test for AuditBackendPlugin ABC in `tests/contract/test_audit_backend_contract.py`
  - Verify store_promotion() signature
  - Verify store_rollback() signature
  - Verify query_history() signature
  - @pytest.mark.requirement("FR-025")
- [ ] T158 [P] Unit test for OCIAuditBackend in `packages/floe-core/tests/unit/oci/test_audit_oci.py`
  - Test store_promotion writes to OCI annotations
  - Test store_rollback writes to OCI annotations
  - Test query_history reads from registry
  - @pytest.mark.requirement("FR-025a")
- [ ] T159 [P] Unit test for S3AuditBackend in `packages/floe-core/tests/unit/oci/test_audit_s3.py`
  - Test append-only S3 writes
  - Test query_history from S3
  - @pytest.mark.requirement("FR-025b")

### Implementation for Audit Backend

- [ ] T160 Create AuditBackendPlugin ABC in `packages/floe-core/src/floe_core/plugin_interfaces/audit_backend.py`
  - Define store_promotion(record: PromotionRecord) -> None
  - Define store_rollback(record: RollbackRecord) -> None
  - Define query_history(env: str, limit: int) -> list[PromotionRecord | RollbackRecord]
- [ ] T161 Implement OCIAuditBackend (default) in `packages/floe-core/src/floe_core/oci/audit.py`
  - Store records in OCI manifest annotations
  - Handle 64KB annotation limit with truncation
- [ ] T162 Implement S3AuditBackend in `packages/floe-core/src/floe_core/oci/audit_s3.py`
  - Use append-only S3 object naming (timestamp-based)
  - Support configurable bucket and prefix
- [ ] T163 Register audit backend plugins via entry point `floe.audit_backends` in `pyproject.toml`
- [ ] T164 Update PromotionController to use AuditBackendPlugin interface in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T165 Add audit backend selection to PromotionConfig in `packages/floe-core/src/floe_core/schemas/promotion.py`
- [ ] T166 Add @pytest.mark.requirement decorators for FR-025 through FR-026 to tests

**Checkpoint**: Audit backend is pluggable with OCI and S3 implementations

---

## Phase 16: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T167 [P] Update OCIClient.promote_to_environment() to delegate to PromotionController in `packages/floe-core/src/floe_core/oci/client.py`
- [ ] T168 [P] Add comprehensive docstrings to all public methods in `packages/floe-core/src/floe_core/oci/promotion.py`
- [ ] T169 [P] Add comprehensive docstrings to all CLI commands in `packages/floe-core/src/floe_core/cli/platform/`
- [ ] T170 [P] Verify all integration tests have @pytest.mark.requirement() decorators in `packages/floe-core/tests/integration/`
- [ ] T171 [P] Generate JSON Schema for PromotionConfig for IDE autocomplete in `packages/floe-core/src/floe_core/schemas/promotion.py`
- [ ] T172 Run `/speckit.test-review` to validate test quality
- [ ] T173 Run `/speckit.wiring-check` to verify CLI integration
- [ ] T174 Validate quickstart.md examples work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ──────────────┐
                             ▼
Phase 2: Foundational ───────┤ (BLOCKING - no stories until complete)
                             │
         ┌───────────────────┼───────────────────┬───────────────────┐
         ▼                   ▼                   ▼                   ▼
Phase 3: US1 (P1)    Phase 4: US2 (P1)   Phase 7: US5 (P1)   Phase 9: US7 (P1)
(Core Promote)       (Dry-Run)            (Verification)       (CI/CD JSON)
         │                   │                   │                   │
         │           Phase 5: US3 (P2)   Phase 10: US8 (P1)  Phase 12: US10 (P1)
         │           (Rollback)          (Env Lock)           (Authorization)
         │                   │                   │                   │
         │           Phase 6: US4 (P2)   Phase 11: US9 (P2)  Phase 13: US11 (P2)
         │           (Status)            (Webhooks)           (Sep of Duties)
         │                   │                   │                   │
         │           Phase 8: US6 (P3)                       Phase 14: US12 (P1)
         │           (Multi-Registry)                        (Security Gates)
         │                   │                   │                   │
         └───────────────────┴───────────────────┴───────────────────┘
                             ▼
                    Phase 15: Audit Backend
                             ▼
                    Phase 16: Polish
```

### User Story Dependencies

- **User Story 1 (P1)**: Core promotion - no dependencies on other stories
- **User Story 2 (P1)**: Dry-run - shares code with US1, can parallelize with US1 tests
- **User Story 3 (P2)**: Rollback - independent of US1/US2
- **User Story 4 (P2)**: Status - reads data from US1/US3 but independently testable
- **User Story 5 (P1)**: Verification - integrates into US1 promote flow
- **User Story 6 (P3)**: Multi-registry - extends US1, can be skipped for MVP
- **User Story 7 (P1)**: CI/CD JSON - extends US1/US2/US3/US4 CLI commands
- **User Story 8 (P1)**: Environment Lock - independent, integrates into US1 promote flow
- **User Story 9 (P2)**: Webhooks - independent, integrates into US1/US3 after success
- **User Story 10 (P1)**: Authorization - integrates into US1 promote flow
- **User Story 11 (P2)**: Separation of Duties - extends US10 authorization
- **User Story 12 (P1)**: Security Gate - extends US1 gate system

### Within Each User Story

1. Tests MUST be written and FAIL before implementation
2. Controller methods before CLI commands
3. Core implementation before integration
4. Story complete before moving to next priority

### Parallel Opportunities

| Phase | Parallel Tasks |
|-------|----------------|
| Setup | T001, T002, T003, T005a-e, T012 |
| Foundational | T024-T26 (OpenTelemetry + exports + tests) |
| US1 | T027-T031d (all tests), then T033-T037 (CLI tasks) |
| US2 | T039-T040 (tests) |
| US3 | T045-T049 (all tests) |
| US4 | T059-T060 (tests) |
| US5 | T068-T071 (all tests) |
| US6 | T076-T078 (tests) |
| US7 | T085-T089 (all tests) |
| US8 | T097-T101 (all tests) |
| US9 | T110-T114 (all tests) |
| US10 | T122-T126 (all tests) |
| US11 | T134-T138 (all tests) |
| US12 | T143-T148 (all tests) |
| Audit | T157-T159 (all tests) |
| Polish | T167-T171 (all independent) |

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract test for promote command exit codes in tests/contract/test_promote_contract.py"
Task: "Unit test for PromotionController.promote() success path"
Task: "Unit test for PromotionController.promote() gate failure path"
Task: "Unit test for PromotionController.promote() signature failure path"
Task: "Integration test for full promotion workflow"

# After tests fail, launch implementation:
Task: "Implement PromotionController.promote() full flow"

# Then CLI in parallel after controller:
Task: "Create promote CLI command with options"
Task: "Implement promote command argument parsing"
Task: "Implement promote command success output formatting"
Task: "Implement promote command error output with exit codes"
```

---

## Implementation Strategy

### MVP First (User Stories 1, 2, 5, 7, 8, 10, 12)

1. Complete Phase 1: Setup (schemas)
2. Complete Phase 2: Foundational (controller skeleton)
3. Complete Phase 3: User Story 1 (core promote)
4. Complete Phase 4: User Story 2 (dry-run)
5. Complete Phase 7: User Story 5 (verification)
6. Complete Phase 9: User Story 7 (CI/CD JSON output)
7. Complete Phase 10: User Story 8 (environment lock)
8. Complete Phase 12: User Story 10 (authorization)
9. Complete Phase 14: User Story 12 (security gates)
10. **STOP and VALIDATE**: Test full promote flow with gates, auth, locking, JSON output
11. Deploy/demo: `floe platform promote --output=json` with all gates

### Full Feature Delivery

1. Complete MVP (above)
2. Add Phase 5: User Story 3 (rollback)
3. Add Phase 6: User Story 4 (status)
4. Add Phase 11: User Story 9 (webhooks)
5. Add Phase 13: User Story 11 (separation of duties)
6. **VALIDATE**: All core functionality complete
7. Add Phase 8: User Story 6 (multi-registry) if needed
8. Complete Phase 15: Audit Backend
9. Complete Phase 16: Polish

### Parallel Team Strategy

With 2 developers after Foundational phase:

- **Developer A**: US1 → US3 → US6 → US9 → Audit Backend
- **Developer B**: US2 → US4 → US5 → US7 → US8 → US10 → US11 → US12 → Polish

---

## Task Summary

| Phase | Tasks | Parallel |
|-------|-------|----------|
| Setup | 17 | 9 |
| Foundational | 14 | 3 |
| US1 (Promote) | 16 | 9 |
| US2 (Dry-Run) | 6 | 2 |
| US3 (Rollback) | 14 | 5 |
| US4 (Status) | 9 | 2 |
| US5 (Verification) | 8 | 4 |
| US6 (Multi-Registry) | 9 | 3 |
| US7 (CI/CD JSON) | 12 | 5 |
| US8 (Env Lock) | 13 | 5 |
| US9 (Webhooks) | 12 | 5 |
| US10 (Authorization) | 12 | 5 |
| US11 (Sep of Duties) | 9 | 5 |
| US12 (Security Gates) | 14 | 6 |
| Audit Backend | 10 | 3 |
| Polish | 8 | 5 |
| **Total** | **174** | **76** |

### Per User Story

| Story | Priority | Tasks | Test Tasks | Impl Tasks |
|-------|----------|-------|------------|------------|
| US1 | P1 | 16 | 9 | 7 |
| US2 | P1 | 6 | 2 | 4 |
| US3 | P2 | 14 | 5 | 9 |
| US4 | P2 | 9 | 2 | 7 |
| US5 | P1 | 8 | 4 | 4 |
| US6 | P3 | 9 | 3 | 6 |
| US7 | P1 | 12 | 5 | 7 |
| US8 | P1 | 13 | 5 | 8 |
| US9 | P2 | 12 | 5 | 7 |
| US10 | P1 | 12 | 5 | 7 |
| US11 | P2 | 9 | 5 | 4 |
| US12 | P1 | 14 | 6 | 8 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Requirement coverage: FR-001 through FR-057 mapped to tasks via @pytest.mark.requirement
- Exit codes: 0=success, 8=gate failure, 9=invalid transition, 10=tag exists, 11=version not promoted, 12=authorization failed, 13=environment locked

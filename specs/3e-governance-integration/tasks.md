# Tasks: Epic 3E — Governance Integration

**Input**: Design documents from `/specs/3e-governance-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks grouped by user story. Tests written first (TDD). Each story independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create module structure and shared types needed by all stories

- [ ] T001 Create governance module structure: `packages/floe-core/src/floe_core/governance/__init__.py` with public API stubs
- [ ] T002 [P] Create governance types module with SecretFinding and GovernanceCheckResult models in `packages/floe-core/src/floe_core/governance/types.py`
- [ ] T003 [P] Create governance test directory structure: `packages/floe-core/tests/unit/governance/conftest.py` with shared test fixtures

---

## Phase 2: Foundational (Blocking Prerequisites — Schema Extensions)

**Purpose**: Extend existing schemas and contracts that ALL user stories depend on. No user story can begin until these schema changes land.

**CRITICAL**: These modifications touch shared contracts (Violation, GovernanceConfig, EnforcementSummary). All downstream code depends on them.

### Contract Tests (TDD — write first, must fail)

- [ ] T004 [P] Write contract test for GovernanceConfig backward compatibility in `tests/contract/test_governance_contract.py` — verify existing configs without rbac/secret_scanning/network_policies still parse (FR-031, FR-032)
- [ ] T005 [P] Write contract test for Violation.policy_type extension in `tests/contract/test_governance_contract.py` — verify old types still valid plus new types accepted (FR-032)
- [ ] T006 [P] Write contract test for EnforcementResultSummary extension in `tests/contract/test_governance_contract.py` — verify old summaries parse, new fields have defaults (FR-005, FR-032)

### Schema Implementation

- [ ] T007 [P] Extend Violation.policy_type Literal in `packages/floe-core/src/floe_core/enforcement/result.py` — add "rbac", "secret_scanning", "network_policy" to Literal at line 84
- [ ] T008 [P] Extend VALID_POLICY_TYPES frozenset in `packages/floe-core/src/floe_core/schemas/governance.py` — add "rbac", "secret_scanning", "network_policy" at line 596
- [ ] T009 [P] Add rbac_violations, secret_violations, network_policy_violations counters to EnforcementSummary in `packages/floe-core/src/floe_core/enforcement/result.py` (default=0, ge=0)
- [ ] T010 Add RBACConfig, SecretPattern, SecretScanningConfig, NetworkPoliciesConfig models to `packages/floe-core/src/floe_core/schemas/manifest.py` and add rbac, secret_scanning, network_policies fields to GovernanceConfig
- [ ] T011 Extend EnforcementResultSummary with rbac_principal and secrets_scanned fields in `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` (default values for backward compat)
- [ ] T012 Bump COMPILED_ARTIFACTS_VERSION in `packages/floe-core/src/floe_core/schemas/versions.py` (MINOR version bump)
- [ ] T013 Update create_enforcement_summary() helper in `packages/floe-core/src/floe_core/enforcement/result.py` to populate new summary counters (rbac_violations, secret_violations, network_policy_violations)
- [ ] T014 Run contract tests (T004-T006) and verify all pass — schema foundation is stable

**Checkpoint**: Schema foundation complete — all contract tests green. User stories can now begin.

---

## Phase 3: User Story 2 — Secret Scanning Module with Plugin Interface (Priority: P0)

**Goal**: Built-in regex secret scanner with pluggable ABC. Detects AWS keys, passwords, API tokens, private keys across project files.

**Independent Test**: Place files with known secret patterns in a test project, run scanner, verify all patterns detected with correct file/line references.

**Why US2 before US1**: US1 (compile-time enforcement) orchestrates all checks including secret scanning. Building the secret scanner first means US1 can wire it in directly.

### Tests for US2 (TDD — write first, must fail)

- [ ] T015 [P] [US2] Write unit tests for SecretScannerPlugin ABC compliance in `packages/floe-core/tests/unit/governance/test_secret_scanner_plugin.py` — verify ABC methods, PluginMetadata inheritance (FR-009)
- [ ] T016 [P] [US2] Write unit tests for built-in regex scanner in `packages/floe-core/tests/unit/governance/test_secrets.py` — test detection of AWS keys (AKIA pattern), passwords, API tokens, private keys, high-entropy strings; test exclude patterns; test custom patterns (FR-008, FR-010, FR-011, FR-012)
- [ ] T017 [P] [US2] Write unit test for --allow-secrets flag downgrading severity in `packages/floe-core/tests/unit/governance/test_secrets.py` (FR-013)

### Implementation for US2

- [ ] T018 [P] [US2] Create SecretScannerPlugin ABC in `packages/floe-core/src/floe_core/plugins/secret_scanner.py` with scan_file(), scan_directory(), get_supported_patterns() abstract methods (FR-009)
- [ ] T019 [US2] Implement BuiltinSecretScanner in `packages/floe-core/src/floe_core/governance/secrets.py` — regex patterns for AWS keys (AKIA), passwords, API tokens, private keys (PEM headers), high-entropy strings; exclude pattern support; SecretFinding to Violation conversion (FR-008, FR-010, FR-011, FR-012)
- [ ] T020 [US2] Add --allow-secrets support to BuiltinSecretScanner — downgrade error to warning severity when flag is set (FR-013)
- [ ] T021 [US2] Run US2 tests and verify all pass

**Checkpoint**: Secret scanner works independently. Can scan files, detect patterns, respect excludes.

---

## Phase 4: User Story 1 — Compile-Time Governance Enforcement (Priority: P0) MVP

**Goal**: GovernanceIntegrator wires PolicyEnforcer + RBAC checker + secret scanner into compilation pipeline. All violations merged into unified EnforcementResultSummary.

**Independent Test**: Run `floe compile` against a spec with intentional violations (leaked secret, missing RBAC role) and verify compilation fails with correct violation details.

### Tests for US1 (TDD — write first, must fail)

- [ ] T022 [P] [US1] Write unit tests for RBACChecker in `packages/floe-core/tests/unit/governance/test_rbac_checker.py` — test valid token flow, expired token, missing token, insufficient role, principal fallback (FR-002, FR-003)
- [ ] T023 [P] [US1] Write unit tests for GovernanceIntegrator in `packages/floe-core/tests/unit/governance/test_integrator.py` — test orchestration of PolicyEnforcer + RBAC + secrets; collect-all pattern; dry-run mode; enforcement levels (off/warn/strict) (FR-001, FR-004, FR-005, FR-006, FR-031)
- [ ] T024 [P] [US1] Write unit test for OTel span emission in `packages/floe-core/tests/unit/governance/test_integrator.py` — verify spans created for each check type with timing/result attributes (FR-007)

### Implementation for US1

- [ ] T025 [US1] Implement RBACChecker in `packages/floe-core/src/floe_core/governance/rbac_checker.py` — accept token from FLOE_TOKEN env or --token arg; call IdentityPlugin.validate_token(); check roles against rbac.required_role; support --principal/FLOE_PRINCIPAL fallback; return list[Violation] with policy_type="rbac" (FR-002, FR-003)
- [ ] T026 [US1] Implement GovernanceIntegrator in `packages/floe-core/src/floe_core/governance/integrator.py` — orchestrate PolicyEnforcer.enforce() + RBACChecker.check() + SecretScanner.scan(); merge all violations; create EnforcementResult; support dry_run and enforcement_level; emit OTel spans per check (FR-001, FR-004, FR-005, FR-006, FR-007, FR-031)
- [ ] T027 [US1] Wire GovernanceIntegrator into run_enforce_stage() in `packages/floe-core/src/floe_core/compilation/stages.py` — replace direct PolicyEnforcer instantiation with GovernanceIntegrator call; pass token, principal, allow_secrets from caller context (FR-031)
- [ ] T028 [US1] Export GovernanceIntegrator public API from `packages/floe-core/src/floe_core/governance/__init__.py`
- [ ] T029 [US1] Run US1 tests and verify all pass

**Checkpoint**: Compile-time governance enforcement works end-to-end. PolicyEnforcer + RBAC + secrets all orchestrated through single GovernanceIntegrator entry point.

---

## Phase 5: User Story 3 — Policy-as-Code Framework (Priority: P1)

**Goal**: Custom governance policies in manifest.yaml evaluated during compilation. Built-in policies for required tags, naming conventions, max transforms. PolicyEnforcer (sealed) handles custom rules via existing CustomRuleValidator.

**Independent Test**: Define 3-4 custom policies in manifest, compile specs that both satisfy and violate each, verify correct action (warn/error/block).

### Tests for US3 (TDD — write first, must fail)

- [ ] T030 [P] [US3] Write unit tests for policy-as-code evaluation in `packages/floe-core/tests/unit/governance/test_policy_framework.py` — test required_tags, naming_convention, max_transforms built-in policies; test warn/error/block actions; test empty policies config (FR-015, FR-016, FR-017, FR-018)

### Implementation for US3

- [ ] T031 [US3] Verify GovernanceIntegrator correctly delegates custom policy evaluation to PolicyEnforcer's existing CustomRuleValidator — the existing custom_rules config (3B) already handles this. Add integration wiring if needed in `packages/floe-core/src/floe_core/governance/integrator.py` (FR-015, FR-016, FR-017, FR-019)
- [ ] T032 [US3] Implement safe condition evaluator for custom policy expressions in `packages/floe-core/src/floe_core/governance/policy_evaluator.py` — Pydantic-validated condition DSL, no eval/exec (FR-018)
- [ ] T033 [US3] Run US3 tests and verify all pass

**Checkpoint**: Policy-as-code framework validates custom policies through compilation pipeline.

---

## Phase 6: User Story 4 — Network Policy Generation in Helm (Priority: P1)

**Goal**: Network policy generation driven by governance configuration in manifest. Delegates to existing NetworkSecurityPlugin (7C).

**Independent Test**: Enable network policies in manifest, render Helm templates, verify generated NetworkPolicy YAML includes default-deny and correct allow rules.

### Tests for US4 (TDD — write first, must fail)

- [ ] T034 [P] [US4] Write unit tests for network policy integration in `packages/floe-core/tests/unit/governance/test_network_policies.py` — test default-deny generation, platform service allow rules, disabled=no policies, custom egress merge (FR-020, FR-021, FR-022, FR-023)

### Implementation for US4

- [ ] T035 [US4] Implement network policy check in GovernanceIntegrator — when governance.network_policies.enabled, delegate to NetworkSecurityPlugin.generate_default_deny_policies() and generate_network_policy(); validate generated policies; add violations for failures in `packages/floe-core/src/floe_core/governance/integrator.py` (FR-020, FR-021, FR-022, FR-023)
- [ ] T036 [US4] Run US4 tests and verify all pass

**Checkpoint**: Network policy generation controlled by governance config, integrated into compilation.

---

## Phase 7: User Story 6 — Contract Monitoring Integration Tests (Priority: P1)

**Goal**: Close the integration test gap for Epic 3D contract monitoring. Add tests with real PostgreSQL.

**Independent Test**: Run monitoring integration test suite against Kind cluster with PostgreSQL, verify all check types execute, alerts fire, SLA metrics recorded.

### Tests for US6 (these ARE the deliverables)

- [ ] T037 [US6] Create integration test conftest with PostgreSQL fixtures in `packages/floe-core/tests/integration/contracts/monitoring/conftest.py` — async engine setup, table creation via migrations, cleanup (FR-027)
- [ ] T038 [US6] Implement ContractMonitor orchestrator integration test in `packages/floe-core/tests/integration/contracts/monitoring/test_monitor_integration.py` — test check execution, result persistence to real PostgreSQL, alert routing (FR-027)
- [ ] T039 [P] [US6] Implement check type integration tests in `packages/floe-core/tests/integration/contracts/monitoring/test_check_types.py` — test freshness, schema drift, quality, availability checks with real data (FR-028)
- [ ] T040 [P] [US6] Implement SLA compliance integration test in `packages/floe-core/tests/integration/contracts/monitoring/test_sla_compliance.py` — test threshold evaluation, incident creation with real database (FR-029)
- [ ] T041 [P] [US6] Implement AlertRouter integration test in `packages/floe-core/tests/integration/contracts/monitoring/test_alert_routing.py` — test webhook delivery with mock HTTP server (FR-030)
- [ ] T042 [US6] Run US6 integration tests against Kind cluster and verify all pass

**Checkpoint**: Contract monitoring has real integration test coverage. All 4 check types + alert routing validated against PostgreSQL.

---

## Phase 8: User Story 5 — Governance CLI Commands (Priority: P2)

**Goal**: `floe governance status|audit|report` commands for operators to inspect governance state.

**Independent Test**: Run each CLI command against a configured project, verify correct output format and content.

### Tests for US5 (TDD — write first, must fail)

- [ ] T043 [P] [US5] Write unit tests for governance CLI commands in `packages/floe-core/tests/unit/governance/test_cli.py` — test status output, audit execution, report format flags (sarif/json/html) (FR-024, FR-025, FR-026)

### Implementation for US5

- [ ] T044 [US5] Create governance CLI group in `packages/floe-core/src/floe_core/cli/governance/__init__.py` — @click.group(name="governance") with help text
- [ ] T045 [P] [US5] Implement `floe governance status` command in `packages/floe-core/src/floe_core/cli/governance/status.py` — display enabled checks, last enforcement result, violation counts (FR-024)
- [ ] T046 [P] [US5] Implement `floe governance audit` command in `packages/floe-core/src/floe_core/cli/governance/audit.py` — execute all governance checks without producing artifacts, display results (FR-025)
- [ ] T047 [P] [US5] Implement `floe governance report` command in `packages/floe-core/src/floe_core/cli/governance/report.py` — --format sarif|json|html flag, delegate to existing exporters (FR-026)
- [ ] T048 [US5] Register governance group in `packages/floe-core/src/floe_core/cli/main.py` — add `cli.add_command(governance)`
- [ ] T049 [US5] Run US5 tests and verify all pass

**Checkpoint**: Governance CLI commands work independently. Operators can inspect, audit, and export governance reports.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: SARIF extension, test fixtures, and final integration

### SARIF Export Extension

- [ ] T050 [P] Write unit tests for SARIF E5xx/E6xx rule definitions in `packages/floe-core/tests/unit/enforcement/test_sarif_exporter.py` — verify new rule definitions present, RBAC and secret violations export correctly (FR-014)
- [ ] T051 [P] Extend SARIF rule definitions in `packages/floe-core/src/floe_core/enforcement/exporters/sarif_exporter.py` — add E501-E505 (RBAC), E601-E606 (secrets), E701-E702 (network) to RULE_DEFINITIONS dict (FR-014)

### Test Fixtures

- [ ] T052 Create reusable governance test fixtures in `testing/fixtures/governance.py` — valid/invalid/expired tokens, GovernanceConfig presets (rbac-enabled, scanning-enabled, all-enabled, all-disabled), secret-laden test files, policy violation scenarios (FR-033)

### Final Verification

- [ ] T053 Run full unit test suite: `make test-unit` and verify >80% coverage on governance module (SC-005)
- [ ] T054 Run full contract test suite: verify all governance contracts stable (SC-005)
- [ ] T055 Run quickstart.md validation — execute all examples from quickstart.md and verify expected outputs
- [ ] T056 Verify requirement traceability: `uv run python -m testing.traceability --all --threshold 100` — all 33 FRs covered (SC-005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US2 Secret Scanning (Phase 3)**: Depends on Foundational — builds scanner used by US1
- **US1 Compile-Time Enforcement (Phase 4)**: Depends on Foundational + US2 (uses secret scanner)
- **US3 Policy-as-Code (Phase 5)**: Depends on Foundational + US1 (uses GovernanceIntegrator)
- **US4 Network Policies (Phase 6)**: Depends on Foundational + US1 (uses GovernanceIntegrator)
- **US6 Contract Monitoring Tests (Phase 7)**: Depends on Foundational ONLY (independent of governance code)
- **US5 Governance CLI (Phase 8)**: Depends on US1 (CLI calls GovernanceIntegrator)
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1: Setup
    │
    ▼
Phase 2: Foundational (schemas)
    │
    ├──────────────────────────────┐
    ▼                              ▼
Phase 3: US2 (Secrets)       Phase 7: US6 (3D Tests) ← INDEPENDENT
    │
    ▼
Phase 4: US1 (Enforcement) ← MVP
    │
    ├───────────┐
    ▼           ▼
Phase 5: US3  Phase 6: US4  ← CAN PARALLELIZE
    │           │
    ▼           ▼
Phase 8: US5 (CLI)
    │
    ▼
Phase 9: Polish
```

### Within Each User Story

1. Tests written FIRST and verified to FAIL
2. Implementation follows TDD order
3. Tests re-run and verified to PASS
4. Story checkpoint validates independent functionality

### Parallel Opportunities

- **Phase 1**: T002 and T003 can run in parallel
- **Phase 2**: T004-T006 (contract tests) can all run in parallel; T007-T009 (schema changes) can all run in parallel
- **Phase 3**: T015-T017 (US2 tests) can all run in parallel
- **Phase 4**: T022-T024 (US1 tests) can all run in parallel
- **Phase 7**: US6 is FULLY INDEPENDENT of all governance work — can start as soon as Phase 2 completes, and run in parallel with US2/US1
- **Phases 5+6**: US3 and US4 can run in parallel (both depend on US1 but don't depend on each other)
- **Phase 9**: T050-T052 can all run in parallel

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch all contract tests in parallel (TDD — write first):
Task: "Contract test for GovernanceConfig backward compat in tests/contract/test_governance_contract.py"
Task: "Contract test for Violation.policy_type extension in tests/contract/test_governance_contract.py"
Task: "Contract test for EnforcementResultSummary extension in tests/contract/test_governance_contract.py"

# Then launch all schema changes in parallel:
Task: "Extend Violation.policy_type Literal in enforcement/result.py"
Task: "Extend VALID_POLICY_TYPES in schemas/governance.py"
Task: "Add counters to EnforcementSummary in enforcement/result.py"
Task: "Add RBACConfig, SecretScanningConfig, NetworkPoliciesConfig to manifest.py"
```

## Parallel Example: US6 + US2 (fully independent)

```bash
# These can run simultaneously after Phase 2:
Task: "US6 — Contract monitoring integration test conftest (postgres fixtures)"
Task: "US2 — SecretScannerPlugin ABC in plugins/secret_scanner.py"
```

---

## Implementation Strategy

### MVP First (US2 + US1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational schemas (CRITICAL — blocks everything)
3. Complete Phase 3: US2 Secret Scanner (builds component US1 needs)
4. Complete Phase 4: US1 Compile-Time Enforcement
5. **STOP and VALIDATE**: Test `floe compile` with intentional violations — RBAC, secrets, policies all working

### Incremental Delivery

1. Setup + Foundational → Schema contracts stable
2. US2 (Secret Scanner) → Independent scanning capability
3. US1 (Enforcement) → Full compile-time governance → **MVP**
4. US6 (3D Tests) → Test infrastructure gap closed (can be done in parallel with US2/US1)
5. US3 (Policy-as-Code) + US4 (Network Policies) → Enhanced governance capabilities
6. US5 (CLI) → Operator tooling
7. Polish → SARIF, fixtures, coverage validation

### Task Count Summary

| Phase | Story | Tasks | Parallelizable |
|-------|-------|-------|----------------|
| 1: Setup | — | 3 | 2 |
| 2: Foundational | — | 11 | 6 |
| 3: US2 Secrets | US2 (P0) | 7 | 4 |
| 4: US1 Enforcement | US1 (P0) | 8 | 3 |
| 5: US3 Policy-as-Code | US3 (P1) | 4 | 1 |
| 6: US4 Network Policies | US4 (P1) | 3 | 1 |
| 7: US6 3D Tests | US6 (P1) | 6 | 3 |
| 8: US5 CLI | US5 (P2) | 7 | 4 |
| 9: Polish | — | 7 | 3 |
| **Total** | | **56** | **27** |

---

## Requirement Traceability

| Requirement | Task(s) |
|-------------|---------|
| FR-001 | T023, T026 |
| FR-002 | T022, T025 |
| FR-003 | T022, T025 |
| FR-004 | T023, T026 |
| FR-005 | T006, T023, T026 |
| FR-006 | T023, T026 |
| FR-007 | T024, T026 |
| FR-008 | T016, T019 |
| FR-009 | T015, T018 |
| FR-010 | T016, T019 |
| FR-011 | T016, T019 |
| FR-012 | T016, T019 |
| FR-013 | T017, T020 |
| FR-014 | T050, T051 |
| FR-015 | T030, T031 |
| FR-016 | T030, T031 |
| FR-017 | T030, T031 |
| FR-018 | T030, T032 |
| FR-019 | T030, T031 |
| FR-020 | T034, T035 |
| FR-021 | T034, T035 |
| FR-022 | T034, T035 |
| FR-023 | T034, T035 |
| FR-024 | T043, T045 |
| FR-025 | T043, T046 |
| FR-026 | T043, T047 |
| FR-027 | T037, T038 |
| FR-028 | T039 |
| FR-029 | T040 |
| FR-030 | T041 |
| FR-031 | T004, T023, T026, T027 |
| FR-032 | T004, T005, T006 |
| FR-033 | T052 |

**Coverage**: All 33 functional requirements mapped to at least 1 task. 100% traceability.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- PolicyEnforcer (3A) remains SEALED and UNMODIFIED throughout — GovernanceIntegrator wraps it
- All schema changes are ADDITIVE with defaults — MINOR contract version bump
- US6 (3D integration tests) is independent of all governance implementation — can be parallelized freely
- TDD enforced: tests written and failing before implementation in every phase
- Atomic commits: each task is 100-500 LOC, suitable for a single commit

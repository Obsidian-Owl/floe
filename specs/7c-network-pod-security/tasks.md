# Tasks: Network and Pod Security (Epic 7C)

**Input**: Design documents from `/specs/7c-network-pod-security/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per floe constitution (TDD required, K8s-native testing)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Core schemas**: `packages/floe-core/src/floe_core/`
- **Plugin**: `plugins/floe-network-security-k8s/src/floe_network_security_k8s/`
- **CLI**: `packages/floe-cli/src/floe_cli/commands/network/`
- **Tests**: `tests/contract/`, `plugins/floe-network-security-k8s/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create plugin package structure at `plugins/floe-network-security-k8s/` with pyproject.toml
- [ ] T002 [P] Create network module directory at `packages/floe-core/src/floe_core/network/`
- [ ] T003 [P] Create CLI command group directory at `packages/floe-cli/src/floe_cli/commands/network/`
- [ ] T004 [P] Add entry point for `floe.network_security` in plugin pyproject.toml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schemas and ABC that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Contract Tests (TDD - Write FIRST)

- [ ] T005 [P] Contract test for SecurityConfig extension in `tests/contract/test_security_config_extension.py`
- [ ] T006 [P] Contract test for NetworkSecurityPlugin ABC in `tests/contract/test_network_security_plugin_contract.py`
- [ ] T007 [P] Contract test for NetworkPolicyConfig schema in `tests/contract/test_network_policy_schemas.py`

### Core Schemas

- [ ] T008 [P] Create PortRule schema in `packages/floe-core/src/floe_core/network/schemas.py`
- [ ] T009 [P] Create EgressRule and IngressRule schemas in `packages/floe-core/src/floe_core/network/schemas.py`
- [ ] T010 Create NetworkPolicyConfig schema with to_k8s_manifest() method in `packages/floe-core/src/floe_core/network/schemas.py`
- [ ] T011 [P] Create EgressAllowRule schema in `packages/floe-core/src/floe_core/network/schemas.py`
- [ ] T012 Create NetworkPoliciesConfig schema in `packages/floe-core/src/floe_core/network/schemas.py`
- [ ] T013 Extend SecurityConfig with network_policies field in `packages/floe-core/src/floe_core/security.py`

### Plugin ABC

- [ ] T014 Create NetworkSecurityPlugin ABC with PluginMetadata in `packages/floe-core/src/floe_core/plugins/network_security.py`
- [ ] T015 Define abstract methods: generate_network_policy, generate_default_deny_policies, generate_dns_egress_rule in ABC
- [ ] T016 Define abstract methods: generate_pod_security_context, generate_container_security_context, generate_writable_volumes in ABC

### Result and Audit

- [ ] T017 [P] Create NetworkPolicyGenerationResult dataclass in `packages/floe-core/src/floe_core/network/result.py`
- [ ] T018 [P] Create NetworkPolicyAuditEvent class in `packages/floe-core/src/floe_core/network/audit.py`

### Module Exports

- [ ] T019 Export all schemas and ABC in `packages/floe-core/src/floe_core/network/__init__.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Default Deny Network Isolation for Job Pods (Priority: P0) 🎯 MVP

**Goal**: Generate default-deny NetworkPolicies for `floe-jobs` namespace with explicit egress allowlists

**Independent Test**: Deploy job pod, verify allowed egress (Polaris, OTel, MinIO) succeeds, unauthorized egress blocked

**Requirements**: FR-010, FR-011, FR-030, FR-031, FR-032, FR-033

### Tests for User Story 1

- [ ] T020 [P] [US1] Unit test for default-deny policy generation in `plugins/floe-network-security-k8s/tests/unit/test_default_deny.py`
- [ ] T021 [P] [US1] Unit test for jobs namespace egress allowlist in `plugins/floe-network-security-k8s/tests/unit/test_jobs_egress.py`
- [ ] T022 [P] [US1] Integration test for jobs NetworkPolicy enforcement in `plugins/floe-network-security-k8s/tests/integration/test_jobs_network_isolation.py`

### Implementation for User Story 1

- [ ] T023 [US1] Implement generate_default_deny_policies() for floe-jobs in `plugins/floe-network-security-k8s/src/floe_network_security_k8s/plugin.py`
- [ ] T024 [US1] Implement jobs egress allowlist generation (Polaris 8181, OTel 4317/4318, MinIO 9000) in plugin.py
- [ ] T025 [US1] Implement custom egress rules from jobs_egress_allow config in plugin.py
- [ ] T026 [US1] Add K8s NetworkPolicy YAML serialization for jobs policies in plugin.py

**Checkpoint**: Jobs namespace has default-deny with required egress allowlists

---

## Phase 4: User Story 2 - Platform Services Network Segmentation (Priority: P0)

**Goal**: Generate NetworkPolicies for `floe-platform` namespace with ingress from ingress controller and intra-namespace communication

**Independent Test**: Verify ingress traffic works, inter-service communication works, direct pod-to-pod from floe-jobs blocked

**Requirements**: FR-020, FR-021, FR-022, FR-023

### Tests for User Story 2

- [ ] T027 [P] [US2] Unit test for platform intra-namespace policy in `plugins/floe-network-security-k8s/tests/unit/test_platform_policies.py`
- [ ] T028 [P] [US2] Unit test for ingress controller allowlist in `plugins/floe-network-security-k8s/tests/unit/test_ingress_allow.py`
- [ ] T029 [P] [US2] Integration test for platform NetworkPolicy enforcement in `plugins/floe-network-security-k8s/tests/integration/test_platform_network_isolation.py`

### Implementation for User Story 2

- [ ] T030 [US2] Implement generate_default_deny_policies() for floe-platform in plugin.py
- [ ] T031 [US2] Implement intra-namespace allow policy for floe-platform in plugin.py
- [ ] T032 [US2] Implement ingress controller namespace allowlist (configurable namespace) in plugin.py
- [ ] T033 [US2] Implement platform egress rules (K8s API, DNS, external HTTPS) in plugin.py
- [ ] T034 [US2] Add custom egress rules from platform_egress_allow config in plugin.py

**Checkpoint**: Platform namespace has segmentation with ingress controller and inter-service communication

---

## Phase 5: User Story 3 - Pod Security Standards Enforcement (Priority: P0)

**Goal**: Generate namespace labels for PSS enforcement (restricted for jobs, baseline for platform)

**Independent Test**: Attempt to deploy privileged pod, verify admission controller rejection

**Requirements**: FR-050, FR-051, FR-052, FR-053, FR-054

### Tests for User Story 3

- [ ] T035 [P] [US3] Unit test for PSS label generation in `plugins/floe-network-security-k8s/tests/unit/test_pss_labels.py`
- [ ] T036 [P] [US3] Integration test for PSS enforcement rejection in `plugins/floe-network-security-k8s/tests/integration/test_pss_enforcement.py`

### Implementation for User Story 3

- [ ] T037 [P] [US3] Create PodSecurityContextConfig schema extension in `packages/floe-core/src/floe_core/network/schemas.py`
- [ ] T038 [P] [US3] Create NamespaceSecurityConfig schema with PSS labels in `packages/floe-core/src/floe_core/network/schemas.py`
- [ ] T039 [US3] Implement generate_namespace_pss_labels() method in plugin.py
- [ ] T040 [US3] Implement configurable PSS levels via security.pod_security.{namespace}_level in plugin.py
- [ ] T041 [US3] Generate namespace manifest with PSS enforce/audit/warn labels in plugin.py

**Checkpoint**: Namespaces have PSS labels, admission controller enforces security baselines

---

## Phase 6: User Story 4 - Secure Container Runtime Configuration (Priority: P1)

**Goal**: Generate hardened securityContext for job pods (runAsNonRoot, readOnlyRootFilesystem, capabilities drop)

**Independent Test**: Inspect generated pod specs, verify all required security context fields present

**Requirements**: FR-060, FR-061, FR-062, FR-063, FR-064

### Tests for User Story 4

- [ ] T042 [P] [US4] Unit test for pod securityContext generation in `plugins/floe-network-security-k8s/tests/unit/test_security_context.py`
- [ ] T043 [P] [US4] Unit test for emptyDir volume generation in `plugins/floe-network-security-k8s/tests/unit/test_writable_volumes.py`

### Implementation for User Story 4

- [ ] T044 [US4] Implement generate_pod_security_context() returning runAsNonRoot, runAsUser, fsGroup, seccompProfile in plugin.py
- [ ] T045 [US4] Implement generate_container_security_context() returning allowPrivilegeEscalation=false, capabilities.drop=[ALL], readOnlyRootFilesystem=true in plugin.py
- [ ] T046 [US4] Implement generate_writable_volumes() for /tmp, /home/floe emptyDir mounts in plugin.py
- [ ] T047 [US4] Support configurable writable_paths via security.pod_security.writable_paths in plugin.py

**Checkpoint**: Generated pod specs include all hardening settings

---

## Phase 7: User Story 5 - NetworkPolicy Manifest Generation (Priority: P1)

**Goal**: Generate NetworkPolicy YAML files to target/network/ directory

**Independent Test**: Run floe compile, verify target/network/ contains valid YAML, kubectl apply --dry-run=server passes

**Requirements**: FR-001, FR-002, FR-003, FR-004, FR-070, FR-071, FR-072, FR-073

### Tests for User Story 5

- [ ] T048 [P] [US5] Contract test for NetworkPolicyManifestGenerator in `tests/contract/test_network_policy_generator.py`
- [ ] T049 [P] [US5] Unit test for YAML file output in `packages/floe-core/tests/unit/test_network_generator.py`

### Implementation for User Story 5

- [ ] T050 [US5] Create NetworkPolicyManifestGenerator class in `packages/floe-core/src/floe_core/network/generator.py`
- [ ] T051 [US5] Implement generate() method that produces dict[namespace, list[NetworkPolicyConfig]] in generator.py
- [ ] T052 [US5] Implement write_manifests() method that writes YAML files to target/network/ in generator.py
- [ ] T053 [US5] Implement NETWORK-POLICY-SUMMARY.md generation documenting all policies in generator.py
- [ ] T054 [US5] Implement policy merging to consolidate overlapping egress rules in generator.py
- [ ] T055 [US5] Add floe.dev/managed-by: floe label to all generated NetworkPolicies in generator.py

**Checkpoint**: floe compile generates NetworkPolicy YAMLs in target/network/

---

## Phase 8: User Story 6 - DNS Egress Allow by Default (Priority: P1)

**Goal**: DNS egress (UDP 53 to kube-system) always included in default-deny policies

**Independent Test**: Deploy pod with default-deny, verify DNS resolution works, arbitrary egress blocked

**Requirements**: FR-012

### Tests for User Story 6

- [ ] T056 [P] [US6] Unit test for DNS egress rule generation in `plugins/floe-network-security-k8s/tests/unit/test_dns_egress.py`
- [ ] T057 [P] [US6] Integration test for DNS resolution with policies in `plugins/floe-network-security-k8s/tests/integration/test_dns_egress.py`

### Implementation for User Story 6

- [ ] T058 [US6] Implement generate_dns_egress_rule() returning UDP 53 to kube-system in plugin.py
- [ ] T059 [US6] Ensure DNS rule is ALWAYS included in all default-deny policies (not configurable to disable) in generator.py
- [ ] T060 [US6] Document DNS auto-inclusion in NETWORK-POLICY-SUMMARY.md in generator.py

**Checkpoint**: DNS egress always works, cannot be accidentally disabled

---

## Phase 9: User Story 7 - Telemetry Egress for Observability (Priority: P1)

**Goal**: Job pods can send telemetry to OTel Collector on ports 4317/4318

**Independent Test**: Deploy job with tracing, verify spans received by OTel Collector

**Requirements**: Part of FR-031

### Tests for User Story 7

- [ ] T061 [P] [US7] Unit test for OTel egress rules in `plugins/floe-network-security-k8s/tests/unit/test_otel_egress.py`
- [ ] T062 [P] [US7] Integration test for telemetry egress in `plugins/floe-network-security-k8s/tests/integration/test_telemetry_egress.py`

### Implementation for User Story 7

- [ ] T063 [US7] Implement OTel Collector egress rule generation (4317 gRPC, 4318 HTTP to floe-platform) in plugin.py
- [ ] T064 [US7] Verify OTel rules included in floe-jobs egress allowlist in generator.py

**Checkpoint**: Jobs can emit traces and metrics to OTel Collector

---

## Phase 10: User Story 8 - Network Policy Validation and Audit (Priority: P2)

**Goal**: CLI commands for network audit, validate, diff, check-cni

**Independent Test**: Run floe network audit, review generated report

**Requirements**: FR-080, FR-081, FR-082, FR-083, FR-084, FR-091, FR-092, FR-093

### Tests for User Story 8

- [ ] T065 [P] [US8] Unit test for audit command in `packages/floe-cli/tests/unit/test_network_audit.py`
- [ ] T066 [P] [US8] Unit test for validate command in `packages/floe-cli/tests/unit/test_network_validate.py`
- [ ] T067 [P] [US8] Unit test for diff command in `packages/floe-cli/tests/unit/test_network_diff.py`
- [ ] T068 [P] [US8] Unit test for check-cni command in `packages/floe-cli/tests/unit/test_network_check_cni.py`

### Implementation for User Story 8

- [ ] T069 [US8] Create `floe network generate` command in `packages/floe-cli/src/floe_cli/commands/network/generate.py`
- [ ] T070 [US8] Create `floe network validate` command with kubectl --dry-run=server in `packages/floe-cli/src/floe_cli/commands/network/validate.py`
- [ ] T071 [US8] Implement validate.py to check manifests against cluster CNI capabilities
- [ ] T072 [US8] Create `floe network audit` command in `packages/floe-cli/src/floe_cli/commands/network/audit.py`
- [ ] T073 [US8] Implement audit.py to report all NetworkPolicies and warn on missing default-deny
- [ ] T074 [US8] Create `floe network diff` command in `packages/floe-cli/src/floe_cli/commands/network/diff.py`
- [ ] T075 [US8] Implement diff.py to show expected vs deployed policy differences
- [ ] T076 [US8] Create `floe network check-cni` command in `packages/floe-cli/src/floe_cli/commands/network/check_cni.py`
- [ ] T077 [US8] Implement check_cni.py to verify CNI plugin supports NetworkPolicies
- [ ] T078 [US8] Register network command group in CLI main.py

**Checkpoint**: CLI commands available for audit, validate, diff, check-cni

---

## Phase 11: User Story 9 - Domain Namespace Network Isolation (Priority: P2)

**Goal**: Domain namespaces (floe-{domain}-domain) have isolated NetworkPolicies

**Independent Test**: Create two domain namespaces, verify cross-domain access blocked

**Requirements**: FR-040, FR-041, FR-042, FR-043

### Tests for User Story 9

- [ ] T079 [P] [US9] Unit test for domain namespace policy generation in `plugins/floe-network-security-k8s/tests/unit/test_domain_policies.py`
- [ ] T080 [P] [US9] Integration test for cross-domain isolation in `plugins/floe-network-security-k8s/tests/integration/test_domain_isolation.py`

### Implementation for User Story 9

- [ ] T081 [US9] Implement domain namespace detection from manifest.yaml domains config in generator.py
- [ ] T082 [US9] Generate default-deny ingress/egress for each domain namespace in plugin.py
- [ ] T083 [US9] Implement domain egress to shared platform services (Polaris, OTel) in plugin.py
- [ ] T084 [US9] Ensure no cross-domain ingress allowed in domain policies in plugin.py
- [ ] T085 [US9] Add domain labels (floe.dev/domain, floe.dev/layer) to domain NetworkPolicies in plugin.py

**Checkpoint**: Domain namespaces are isolated, can access platform services, cannot access each other

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and documentation

- [ ] T086 [P] Update quickstart.md with actual CLI output examples
- [ ] T087 [P] Run full integration test suite in Kind cluster
- [ ] T088 [P] Verify all requirement traceability markers present
- [ ] T089 Run `floe network audit` on demo deployment for validation
- [ ] T090 Final code cleanup and docstring review

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational - Default-deny for jobs (P0)
- **US2 (Phase 4)**: Depends on Foundational - Platform segmentation (P0)
- **US3 (Phase 5)**: Depends on Foundational - PSS enforcement (P0)
- **US4 (Phase 6)**: Depends on Foundational - SecurityContext (P1)
- **US5 (Phase 7)**: Depends on US1, US2 - Manifest generation needs policies
- **US6 (Phase 8)**: Depends on Foundational - DNS egress (P1)
- **US7 (Phase 9)**: Depends on US6 - OTel egress (P1)
- **US8 (Phase 10)**: Depends on US5 - CLI needs generator (P2)
- **US9 (Phase 11)**: Depends on US1, US2 - Domain isolation (P2)
- **Polish (Phase 12)**: Depends on all desired user stories complete

### User Story Dependencies

```
Foundational (Phase 2)
    ├── US1: Jobs Default-Deny (P0) ─────────────┐
    ├── US2: Platform Segmentation (P0) ─────────┤
    ├── US3: PSS Enforcement (P0) ───────────────┤
    ├── US4: SecurityContext (P1) ───────────────┤
    ├── US6: DNS Egress (P1) ─────────────────┐  │
    │   └── US7: OTel Egress (P1) ────────────┤  │
    └── US5: Manifest Generation (P1) ◄───────┼──┘
        ├── US8: CLI Audit/Validate (P2) ◄────┘
        └── US9: Domain Isolation (P2) ◄────────
```

### Within Each User Story

1. Tests MUST be written and FAIL before implementation
2. Schemas before plugin implementation
3. Plugin implementation before generator integration
4. Core implementation before CLI commands

### Parallel Opportunities

**After Foundational completes:**
- US1, US2, US3 can run in parallel (all P0, independent namespaces)
- US4 can run in parallel with US1-3 (independent security context)
- US6 can run in parallel with US1-4 (DNS is separate concern)

**After US1, US2 complete:**
- US5 (generator) can start
- US7 can start (after US6)
- US9 can start

**After US5 completes:**
- US8 (CLI) can start

---

## Parallel Example: Foundational Phase

```bash
# Launch all contract tests in parallel:
Task: "Contract test for SecurityConfig extension"
Task: "Contract test for NetworkSecurityPlugin ABC"
Task: "Contract test for NetworkPolicyConfig schema"

# Launch independent schemas in parallel:
Task: "Create PortRule schema"
Task: "Create EgressRule and IngressRule schemas"
Task: "Create EgressAllowRule schema"
```

## Parallel Example: P0 User Stories

```bash
# After Foundational, launch P0 stories in parallel:
# Developer A: US1 (Jobs Default-Deny)
Task: "Unit test for default-deny policy generation"
Task: "Implement generate_default_deny_policies() for floe-jobs"

# Developer B: US2 (Platform Segmentation)
Task: "Unit test for platform intra-namespace policy"
Task: "Implement generate_default_deny_policies() for floe-platform"

# Developer C: US3 (PSS Enforcement)
Task: "Unit test for PSS label generation"
Task: "Implement generate_namespace_pss_labels()"
```

---

## Implementation Strategy

### MVP First (P0 Stories Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: US1 - Jobs Default-Deny
4. Complete Phase 4: US2 - Platform Segmentation
5. Complete Phase 5: US3 - PSS Enforcement
6. **STOP and VALIDATE**: Test in Kind cluster
7. Deploy/demo if ready - basic network security in place

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1, US2, US3 (P0) → Core network isolation (MVP!)
3. Add US4, US5, US6, US7 (P1) → Full policy generation with CLI generate
4. Add US8, US9 (P2) → Audit, validation, domain isolation
5. Each increment adds value without breaking previous stories

### Parallel Team Strategy

With 3 developers:

1. Team completes Setup + Foundational together
2. Once Foundational done:
   - Developer A: US1 (Jobs) + US6 (DNS) + US7 (OTel)
   - Developer B: US2 (Platform) + US5 (Generator)
   - Developer C: US3 (PSS) + US4 (SecurityContext)
3. After P0/P1 complete:
   - Developer A: US8 (CLI Audit)
   - Developer B: US9 (Domain Isolation)
   - Developer C: Polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Requirement markers: @pytest.mark.requirement("FR-XXX") on all tests

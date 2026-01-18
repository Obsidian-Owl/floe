# Tasks: Epic 7A - Identity & Secrets Plugin System

**Input**: Design documents from `/specs/7a-identity-secrets/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)

## User Story Mapping

| Story | Title | Priority | Plugin |
|-------|-------|----------|--------|
| US1 | SecretReference Runtime Resolution | P0 | floe-core (existing) |
| US2 | Kubernetes Secrets Backend | P0 | floe-secrets-k8s |
| US3 | Infisical Secrets Backend | P1 | floe-secrets-infisical |
| US4 | OAuth2/OIDC Authentication | P1 | floe-identity-keycloak |
| US5 | Secret Audit Logging | P2 | Cross-cutting |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create plugin package scaffolding for all three plugins

- [ ] T001 Create plugin directory structure for floe-secrets-k8s in plugins/floe-secrets-k8s/
- [ ] T002 [P] Create plugin directory structure for floe-secrets-infisical in plugins/floe-secrets-infisical/
- [ ] T003 [P] Create plugin directory structure for floe-identity-keycloak in plugins/floe-identity-keycloak/
- [ ] T004 [P] Create pyproject.toml with entry point for floe-secrets-k8s in plugins/floe-secrets-k8s/pyproject.toml
- [ ] T005 [P] Create pyproject.toml with entry point for floe-secrets-infisical in plugins/floe-secrets-infisical/pyproject.toml
- [ ] T006 [P] Create pyproject.toml with entry point for floe-identity-keycloak in plugins/floe-identity-keycloak/pyproject.toml
- [ ] T007 [P] Create __init__.py with public exports for floe-secrets-k8s in plugins/floe-secrets-k8s/src/floe_secrets_k8s/__init__.py
- [ ] T008 [P] Create __init__.py with public exports for floe-secrets-infisical in plugins/floe-secrets-infisical/src/floe_secrets_infisical/__init__.py
- [ ] T009 [P] Create __init__.py with public exports for floe-identity-keycloak in plugins/floe-identity-keycloak/src/floe_identity_keycloak/__init__.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**Dependencies**: Verify existing ABCs in floe-core, add missing data types

- [ ] T010 Verify IdentityPlugin ABC exists with required methods in packages/floe-core/src/floe_core/plugins/identity.py
- [ ] T011 [P] Verify SecretsPlugin ABC exists with required methods in packages/floe-core/src/floe_core/plugins/secrets.py
- [ ] T012 [P] Verify SecretReference model exists with to_env_var_syntax() in packages/floe-core/src/floe_core/schemas/secrets.py
- [ ] T013 Add OIDCConfig dataclass to floe-core identity module in packages/floe-core/src/floe_core/plugins/identity.py
- [ ] T014 [P] Add HealthStatus enum and health_check() to PluginMetadata if missing in packages/floe-core/src/floe_core/plugin_metadata.py
- [ ] T015 [P] Create BaseSecretsPluginTests compliance test base in testing/base_classes/base_secrets_plugin_tests.py
- [ ] T016 [P] Create BaseIdentityPluginTests compliance test base in testing/base_classes/base_identity_plugin_tests.py
- [ ] T017 Register SECRETS and IDENTITY plugin types in plugin_types.py in packages/floe-core/src/floe_core/plugin_types.py

**Checkpoint**: Foundation ready - plugin implementations can now begin

---

## Phase 3: User Story 2 - Kubernetes Secrets Backend (Priority: P0) MVP

**Goal**: Provide K8sSecretsPlugin as default secrets backend with zero external dependencies

**Independent Test**: Create K8s Secret, configure plugin, verify get_secret/set_secret/list_secrets work

**Why P0 before US1**: US1 (SecretReference resolution) depends on having at least one working SecretsPlugin implementation

### Tests for User Story 2

- [ ] T018 [P] [US2] Unit test for K8sSecretsConfig validation in plugins/floe-secrets-k8s/tests/unit/test_config.py
- [ ] T019 [P] [US2] Unit test for K8sSecretsPlugin with mocked kubernetes client in plugins/floe-secrets-k8s/tests/unit/test_plugin.py
- [ ] T020 [P] [US2] Unit test for generate_pod_env_spec() in plugins/floe-secrets-k8s/tests/unit/test_env_injection.py
- [ ] T021 [P] [US2] Integration test for plugin entry point discovery in plugins/floe-secrets-k8s/tests/integration/test_discovery.py
- [ ] T022 [US2] Integration test for K8s Secrets operations in Kind cluster in plugins/floe-secrets-k8s/tests/integration/test_k8s_secrets.py

### Implementation for User Story 2

- [ ] T023 [US2] Create K8sSecretsConfig Pydantic model in plugins/floe-secrets-k8s/src/floe_secrets_k8s/config.py
- [ ] T024 [P] [US2] Create custom exceptions (SecretsPluginError) in plugins/floe-secrets-k8s/src/floe_secrets_k8s/errors.py
- [ ] T025 [US2] Implement K8sSecretsPlugin with kubernetes client in plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py
- [ ] T026 [US2] Add auto-detection for in-cluster vs kubeconfig auth in plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py
- [ ] T027 [US2] Implement get_secret() with namespace-scoped access in plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py
- [ ] T028 [US2] Implement set_secret() with create-or-update logic in plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py
- [ ] T029 [US2] Implement list_secrets() with prefix filtering in plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py
- [ ] T030 [US2] Implement generate_pod_env_spec() for envFrom injection in plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py
- [ ] T031 [US2] Implement health_check() verifying K8s API connectivity in plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py
- [ ] T032 [US2] Add OpenTelemetry tracing to all secret operations in plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py
- [ ] T033 [US2] Create test fixtures and conftest.py in plugins/floe-secrets-k8s/tests/conftest.py

**Checkpoint**: K8sSecretsPlugin fully functional - can retrieve/store K8s Secrets

---

## Phase 4: User Story 1 - SecretReference Runtime Resolution (Priority: P0)

**Goal**: Ensure secrets are resolved at runtime, never appearing in configuration files

**Independent Test**: Configure SecretReference in manifest, run floe compile, verify profiles.yml contains only env_var() references

**Dependencies**: Requires K8sSecretsPlugin (US2) as reference implementation for testing

### Tests for User Story 1

- [ ] T034 [P] [US1] Contract test for SecretReference.to_env_var_syntax() in tests/contract/test_secret_reference_contract.py
- [ ] T035 [P] [US1] Unit test for env var name generation patterns in packages/floe-core/tests/unit/test_secret_reference.py
- [ ] T036 [US1] Integration test for compile output verification in tests/integration/test_secret_resolution.py

### Implementation for User Story 1

- [ ] T037 [US1] Verify SecretReference.to_env_var_syntax() generates correct dbt syntax in packages/floe-core/src/floe_core/schemas/secrets.py
- [ ] T038 [US1] Add multi-key secret support to SecretReference in packages/floe-core/src/floe_core/schemas/secrets.py
- [ ] T039 [US1] Update compiler to use SecretReference for profiles.yml generation in packages/floe-core/src/floe_core/compiler/
- [ ] T040 [US1] Add validation that no secret values appear in CompiledArtifacts in packages/floe-core/src/floe_core/compiler/

**Checkpoint**: SecretReference resolution works end-to-end with K8s backend

---

## Phase 5: User Story 3 - Infisical Secrets Backend (Priority: P1)

**Goal**: Provide InfisicalSecretsPlugin for centralized OSS secrets management with auto-reload

**Independent Test**: Configure InfisicalSecret CRs, verify K8s Secret sync and pod auto-reload

### Tests for User Story 3

- [ ] T041 [P] [US3] Unit test for InfisicalSecretsConfig validation in plugins/floe-secrets-infisical/tests/unit/test_config.py
- [ ] T042 [P] [US3] Unit test for InfisicalSecretsPlugin with mocked SDK in plugins/floe-secrets-infisical/tests/unit/test_plugin.py
- [ ] T043 [P] [US3] Integration test for plugin entry point discovery in plugins/floe-secrets-infisical/tests/integration/test_discovery.py
- [ ] T044 [US3] Integration test for Infisical operations (optional, requires Infisical) in plugins/floe-secrets-infisical/tests/integration/test_infisical.py

### Implementation for User Story 3

- [ ] T045 [US3] Create InfisicalSecretsConfig Pydantic model with SecretStr in plugins/floe-secrets-infisical/src/floe_secrets_infisical/config.py
- [ ] T046 [P] [US3] Create custom exceptions in plugins/floe-secrets-infisical/src/floe_secrets_infisical/errors.py
- [ ] T047 [US3] Implement InfisicalSecretsPlugin with infisicalsdk in plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py
- [ ] T048 [US3] Implement Universal Auth authentication flow in plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py
- [ ] T049 [US3] Implement get_secret() with path-based organization in plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py
- [ ] T050 [US3] Implement set_secret() for secret creation/updates in plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py
- [ ] T051 [US3] Implement list_secrets() with path prefix filtering in plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py
- [ ] T052 [US3] Implement health_check() verifying Infisical connectivity in plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py
- [ ] T053 [US3] Add support for self-hosted and cloud Infisical URLs in plugins/floe-secrets-infisical/src/floe_secrets_infisical/config.py
- [ ] T054 [US3] Add OpenTelemetry tracing to all operations in plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py
- [ ] T055 [US3] Create test fixtures and conftest.py in plugins/floe-secrets-infisical/tests/conftest.py
- [ ] T056 [US3] Document InfisicalSecret CRD integration in specs/7a-identity-secrets/quickstart.md

**Checkpoint**: InfisicalSecretsPlugin fully functional with Universal Auth

---

## Phase 6: User Story 4 - OAuth2/OIDC Authentication (Priority: P1)

**Goal**: Provide KeycloakIdentityPlugin for enterprise SSO via OIDC

**Independent Test**: Configure Keycloak realm/client, verify authenticate() and validate_token() work

### Tests for User Story 4

- [ ] T057 [P] [US4] Unit test for KeycloakIdentityConfig validation in plugins/floe-identity-keycloak/tests/unit/test_config.py
- [ ] T058 [P] [US4] Unit test for token validation with mocked JWKS in plugins/floe-identity-keycloak/tests/unit/test_token_validation.py
- [ ] T059 [P] [US4] Unit test for UserInfo extraction from claims in plugins/floe-identity-keycloak/tests/unit/test_user_info.py
- [ ] T060 [P] [US4] Integration test for plugin entry point discovery in plugins/floe-identity-keycloak/tests/integration/test_discovery.py
- [ ] T061 [US4] Integration test for Keycloak authentication in Kind cluster in plugins/floe-identity-keycloak/tests/integration/test_keycloak.py

### Implementation for User Story 4

- [ ] T062 [US4] Create KeycloakIdentityConfig Pydantic model in plugins/floe-identity-keycloak/src/floe_identity_keycloak/config.py
- [ ] T063 [P] [US4] Create custom exceptions in plugins/floe-identity-keycloak/src/floe_identity_keycloak/errors.py
- [ ] T064 [US4] Implement JWKSCache for token validation performance in plugins/floe-identity-keycloak/src/floe_identity_keycloak/jwks_cache.py
- [ ] T065 [US4] Implement KeycloakIdentityPlugin with python-keycloak in plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py
- [ ] T066 [US4] Implement authenticate() for credential exchange in plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py
- [ ] T067 [US4] Implement get_user_info() from token claims in plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py
- [ ] T068 [US4] Implement validate_token() with JWKS verification in plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py
- [ ] T069 [US4] Implement get_oidc_config() returning OIDCConfig in plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py
- [ ] T070 [US4] Implement health_check() verifying Keycloak connectivity in plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py
- [ ] T071 [US4] Add support for realm-based multi-tenancy in plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py
- [ ] T072 [US4] Add OpenTelemetry tracing to authentication operations in plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py
- [ ] T073 [US4] Create test fixtures and conftest.py in plugins/floe-identity-keycloak/tests/conftest.py
- [ ] T074 [US4] Create Keycloak test deployment manifest in testing/k8s/services/keycloak.yaml

**Checkpoint**: KeycloakIdentityPlugin fully functional with JWKS caching

---

## Phase 7: User Story 5 - Secret Audit Logging (Priority: P2)

**Goal**: Add audit logging to all secret access operations for compliance

**Independent Test**: Access secrets, verify audit log entries contain requester identity and timestamp

### Tests for User Story 5

- [ ] T075 [P] [US5] Unit test for audit log event structure in tests/unit/test_audit_logging.py
- [ ] T076 [US5] Integration test for audit log capture in tests/integration/test_audit_logging.py

### Implementation for User Story 5

- [ ] T077 [US5] Add audit logging decorator to SecretsPlugin base in packages/floe-core/src/floe_core/plugins/secrets.py
- [ ] T078 [US5] Implement AuditEvent dataclass with fields: timestamp (ISO8601), requester_id (str), secret_path (str), operation (get|set|list|delete), source_ip (str|None), trace_id (str|None), result (success|denied|error) in packages/floe-core/src/floe_core/audit.py
- [ ] T079 [US5] Add structlog audit logger with OTel trace context in packages/floe-core/src/floe_core/audit.py
- [ ] T080 [US5] Integrate audit logging into K8sSecretsPlugin in plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py
- [ ] T081 [US5] Integrate audit logging into InfisicalSecretsPlugin in plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py
- [ ] T082 [US5] Document audit log format and querying in specs/7a-identity-secrets/quickstart.md

**Checkpoint**: All secret access operations produce audit log entries

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Contract tests, documentation, and final validation

- [ ] T083 [P] Run BaseSecretsPluginTests against K8sSecretsPlugin in plugins/floe-secrets-k8s/tests/integration/test_compliance.py
- [ ] T084 [P] Run BaseSecretsPluginTests against InfisicalSecretsPlugin in plugins/floe-secrets-infisical/tests/integration/test_compliance.py
- [ ] T085 [P] Run BaseIdentityPluginTests against KeycloakIdentityPlugin in plugins/floe-identity-keycloak/tests/integration/test_compliance.py
- [ ] T086 [P] Contract test for IdentityPlugin ABC compliance in tests/contract/test_identity_secrets_contracts.py
- [ ] T087 [P] Contract test for SecretsPlugin ABC compliance in tests/contract/test_identity_secrets_contracts.py
- [ ] T088 Validate quickstart.md examples work end-to-end in specs/7a-identity-secrets/quickstart.md
- [ ] T089 [P] Add type hints and mypy --strict validation to all plugin code
- [ ] T090 [P] Security scan with bandit on all plugin code
- [ ] T091 Update CLAUDE.md with new plugin types and dependencies
- [ ] T092 Final PR review with /speckit.test-review

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup
    ↓
Phase 2: Foundational (BLOCKS all user stories)
    ↓
Phase 3: US2 - K8s Secrets (P0) ─────┬───→ Phase 4: US1 - SecretReference (P0)
                                     │
Phase 5: US3 - Infisical (P1) ───────┤
                                     │
Phase 6: US4 - Keycloak (P1) ────────┤
                                     │
                                     ↓
Phase 7: US5 - Audit Logging (P2) ───→ Phase 8: Polish
```

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US2 (K8s Secrets) | Foundational | - |
| US1 (SecretReference) | US2 (needs a working plugin) | - |
| US3 (Infisical) | Foundational | US2, US4 |
| US4 (Keycloak) | Foundational | US2, US3 |
| US5 (Audit) | US2, US3 (to add logging) | - |

### Within Each User Story

1. Tests MUST be written first and FAIL before implementation
2. Config models before plugin implementation
3. Core methods (get/set/list) before auxiliary (health_check, generate_pod_env_spec)
4. OTel tracing added after core functionality works
5. Story complete before marking checkpoint

### Parallel Opportunities

**Phase 1 (All parallel)**:
```bash
# Launch all package scaffolding in parallel
T001, T002, T003  # Directory structures
T004, T005, T006  # pyproject.toml files
T007, T008, T009  # __init__.py files
```

**Phase 2 (Most parallel)**:
```bash
# Launch foundational tasks in parallel
T010, T011, T012  # Verify existing ABCs
T014, T015, T016  # Create test bases
```

**User Story Tests (All parallel within story)**:
```bash
# US2 tests can all run in parallel
T018, T019, T020, T021  # Unit + discovery tests
```

**Cross-Story Parallelism**:
```bash
# After Foundational, US2, US3, US4 can start in parallel
# US3 (Infisical) and US4 (Keycloak) are independent
```

---

## Parallel Example: Phase 3 (US2 - K8s Secrets)

```bash
# Launch all US2 unit tests together:
T018: "Unit test for K8sSecretsConfig validation"
T019: "Unit test for K8sSecretsPlugin with mocked kubernetes client"
T020: "Unit test for generate_pod_env_spec()"
T021: "Integration test for plugin entry point discovery"

# After tests fail, launch config and errors in parallel:
T023: "Create K8sSecretsConfig Pydantic model"
T024: "Create custom exceptions (SecretsPluginError)"

# Then sequential implementation:
T025 → T026 → T027 → T028 → T029 → T030 → T031 → T032
```

---

## Implementation Strategy

### MVP First (P0 Stories Only)

1. Complete Phase 1: Setup (all 3 plugin scaffolds)
2. Complete Phase 2: Foundational (ABCs, test bases)
3. Complete Phase 3: US2 - K8s Secrets Backend (P0)
4. Complete Phase 4: US1 - SecretReference Resolution (P0)
5. **STOP and VALIDATE**: Test K8s secrets end-to-end
6. Deploy/demo with K8s-only secrets

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US2 (K8s Secrets) → Test independently → Deploy (MVP!)
3. Add US1 (SecretReference) → Verify compile output → Demo
4. Add US3 (Infisical) → Test independently → Deploy (OSS option)
5. Add US4 (Keycloak) → Test independently → Deploy (SSO)
6. Add US5 (Audit) → Test independently → Deploy (Compliance)
7. Polish → PR ready

### Parallel Team Strategy

With 2+ developers:

1. All complete Setup + Foundational together
2. Once Foundational done:
   - Developer A: US2 (K8s Secrets) → US1 (SecretReference)
   - Developer B: US3 (Infisical) and US4 (Keycloak) in parallel
3. Both reconvene for US5 (Audit) and Polish

---

## Task Summary

| Phase | Story | Task Count | Parallel Tasks |
|-------|-------|------------|----------------|
| 1 | Setup | 9 | 8 |
| 2 | Foundational | 8 | 6 |
| 3 | US2 - K8s Secrets | 16 | 5 |
| 4 | US1 - SecretReference | 7 | 2 |
| 5 | US3 - Infisical | 16 | 4 |
| 6 | US4 - Keycloak | 18 | 5 |
| 7 | US5 - Audit | 8 | 1 |
| 8 | Polish | 10 | 6 |
| **Total** | | **92** | **37** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- All tests use `@pytest.mark.requirement()` for traceability
- Integration tests inherit from `IntegrationTestBase`
- No `pytest.skip()` - tests FAIL if infrastructure missing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently

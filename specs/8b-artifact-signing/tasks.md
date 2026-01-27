# Tasks: Artifact Signing

**Input**: Design documents from `/specs/8b-artifact-signing/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete), data-model.md (complete), contracts/ (complete), quickstart.md (complete)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US5)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- **Source**: `packages/floe-core/src/floe_core/`
- **Tests**: `packages/floe-core/tests/`
- **OCI modules**: `packages/floe-core/src/floe_core/oci/`
- **CLI commands**: `packages/floe-core/src/floe_core/cli/artifact/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project dependencies and base structure

- [ ] T001 Add sigstore>=3.0.0 dependency to packages/floe-core/pyproject.toml
- [ ] T002 [P] Document cosign CLI and syft CLI as external requirements in packages/floe-core/README.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Schemas (All Stories Depend On These)

- [ ] T003 [P] Create SigningConfig Pydantic model in packages/floe-core/src/floe_core/schemas/signing.py
- [ ] T004 [P] Create VerificationPolicy and TrustedIssuer Pydantic models in packages/floe-core/src/floe_core/schemas/signing.py
- [ ] T005 [P] Create SignatureMetadata Pydantic model with to_annotations/from_annotations methods in packages/floe-core/src/floe_core/schemas/signing.py
- [ ] T006 [P] Create VerificationResult and SignatureStatus enum in packages/floe-core/src/floe_core/schemas/signing.py
- [ ] T007 [P] Create EnvironmentPolicy Pydantic model for per-environment overrides in packages/floe-core/src/floe_core/schemas/signing.py
- [ ] T008 Add SignatureVerificationError class (exit_code=6) to packages/floe-core/src/floe_core/oci/errors.py
- [ ] T009 Export signing schemas from packages/floe-core/src/floe_core/schemas/__init__.py

### Schema Integration

- [ ] T010 Extend RegistryConfig with optional signing and verification fields in packages/floe-core/src/floe_core/schemas/oci.py

### Unit Tests for Schemas

- [ ] T011 [P] Create unit tests for SigningConfig validation in packages/floe-core/tests/unit/schemas/test_signing.py
- [ ] T012 [P] Create unit tests for VerificationPolicy validation in packages/floe-core/tests/unit/schemas/test_signing.py
- [ ] T013 [P] Create unit tests for SignatureMetadata annotation serialization in packages/floe-core/tests/unit/schemas/test_signing.py

**Checkpoint**: Foundational schemas complete - user story implementation can now begin

---

## Phase 3: User Story 1 - Keyless Signing in CI/CD (Priority: P0) 🎯 MVP

**Goal**: CI/CD pipelines sign artifacts using OIDC identity without managing keys

**Independent Test**: Run `floe artifact sign --keyless <artifact-ref>` in GitHub Actions, verify signature stored in registry and logged to Rekor

### Implementation for User Story 1

- [ ] T014 [US1] Create SigningClient class with keyless signing support using sigstore-python in packages/floe-core/src/floe_core/oci/signing.py
- [ ] T015 [US1] Implement OIDC token acquisition for CI/CD environments (GitHub Actions, GitLab CI) in packages/floe-core/src/floe_core/oci/signing.py
- [ ] T016 [US1] Implement Sigstore Bundle creation and serialization for OCI annotations in packages/floe-core/src/floe_core/oci/signing.py
- [ ] T017 [US1] Implement Rekor transparency log integration in packages/floe-core/src/floe_core/oci/signing.py
- [ ] T018 [US1] Add OCIClient.sign() method that calls SigningClient and updates artifact annotations in packages/floe-core/src/floe_core/oci/client.py
- [ ] T019 [US1] Create `floe artifact sign` CLI command with --keyless flag in packages/floe-core/src/floe_core/cli/artifact/sign.py
- [ ] T020 [US1] Add --sign flag to existing `floe artifact push` command in packages/floe-core/src/floe_core/cli/artifact/push.py
- [ ] T021 [US1] Register sign command in artifact CLI group in packages/floe-core/src/floe_core/cli/artifact/__init__.py
- [ ] T022 [US1] Add OpenTelemetry tracing for signing operations in packages/floe-core/src/floe_core/oci/signing.py

### Unit Tests for User Story 1

- [ ] T023 [P] [US1] Create unit tests for SigningClient keyless mode in packages/floe-core/tests/unit/oci/test_signing.py
- [ ] T024 [P] [US1] Create unit tests for OIDC token acquisition with mocks in packages/floe-core/tests/unit/oci/test_signing.py
- [ ] T025 [P] [US1] Create unit tests for Rekor log entry creation in packages/floe-core/tests/unit/oci/test_signing.py
- [ ] T026 [P] [US1] Create CLI unit tests for artifact sign command in packages/floe-core/tests/unit/cli/test_artifact_sign.py

**Checkpoint**: Keyless signing functional - can sign artifacts in CI/CD environments

---

## Phase 4: User Story 2 - Signature Verification Before Deployment (Priority: P0)

**Goal**: System automatically verifies signatures during pull, rejecting untrusted artifacts

**Independent Test**: Push signed artifact, pull with verification enabled (should pass); attempt to pull unsigned artifact (should reject)

### Implementation for User Story 2

- [ ] T027 [US2] Create VerificationClient class with keyless verification support in packages/floe-core/src/floe_core/oci/verification.py
- [ ] T028 [US2] Implement identity policy matching (issuer + subject) for trusted_issuers in packages/floe-core/src/floe_core/oci/verification.py
- [ ] T029 [US2] Implement Rekor transparency log verification in packages/floe-core/src/floe_core/oci/verification.py
- [ ] T030 [US2] Add verification hook to OCIClient.pull() after _fetch_from_registry() before _deserialize_artifacts() in packages/floe-core/src/floe_core/oci/client.py
- [ ] T031 [US2] Implement enforcement levels (enforce/warn/off) with appropriate error handling in packages/floe-core/src/floe_core/oci/verification.py
- [ ] T032 [US2] Create `floe artifact verify` CLI command in packages/floe-core/src/floe_core/cli/artifact/verify.py
- [ ] T033 [US2] Register verify command in artifact CLI group in packages/floe-core/src/floe_core/cli/artifact/__init__.py
- [ ] T034 [US2] Add OpenTelemetry tracing for verification operations in packages/floe-core/src/floe_core/oci/verification.py
- [ ] T035 [US2] Implement audit logging for verification attempts (success/failure, signer identity) in packages/floe-core/src/floe_core/oci/verification.py

### Unit Tests for User Story 2

- [ ] T036 [P] [US2] Create unit tests for VerificationClient with valid signatures in packages/floe-core/tests/unit/oci/test_verification.py
- [ ] T037 [P] [US2] Create unit tests for VerificationClient with invalid signatures in packages/floe-core/tests/unit/oci/test_verification.py
- [ ] T038 [P] [US2] Create unit tests for enforcement levels (enforce/warn/off) in packages/floe-core/tests/unit/oci/test_verification.py
- [ ] T039 [P] [US2] Create unit tests for identity policy matching in packages/floe-core/tests/unit/oci/test_verification.py
- [ ] T040 [P] [US2] Create CLI unit tests for artifact verify command in packages/floe-core/tests/unit/cli/test_artifact_verify.py

**Checkpoint**: Signature verification functional - pull operations verify signatures automatically

---

## Phase 5: User Story 3 - SBOM Generation and Attestation (Priority: P1)

**Goal**: Security engineers generate SBOM and attach as attestation for compliance

**Independent Test**: Run `floe artifact sbom --generate`, verify SBOM lists dependencies, attach to artifact, retrieve via inspect

### Implementation for User Story 3

- [ ] T041 [US3] Create AttestationManifest and Subject Pydantic models in packages/floe-core/src/floe_core/schemas/signing.py
- [ ] T042 [US3] Create attestation module with syft CLI integration for SBOM generation in packages/floe-core/src/floe_core/oci/attestation.py
- [ ] T043 [US3] Implement SPDX SBOM generation from Python and dbt dependencies in packages/floe-core/src/floe_core/oci/attestation.py
- [ ] T044 [US3] Implement in-toto attestation attachment using cosign attest in packages/floe-core/src/floe_core/oci/attestation.py
- [ ] T045 [US3] Implement SBOM retrieval from artifact attestations in packages/floe-core/src/floe_core/oci/attestation.py
- [ ] T046 [US3] Create `floe artifact sbom` CLI command with --generate, --attach, --show flags in packages/floe-core/src/floe_core/cli/artifact/sbom.py
- [ ] T047 [US3] Add --show-sbom flag to `floe artifact inspect` command in packages/floe-core/src/floe_core/cli/artifact/inspect.py
- [ ] T048 [US3] Register sbom command in artifact CLI group in packages/floe-core/src/floe_core/cli/artifact/__init__.py

### Unit Tests for User Story 3

- [ ] T049 [P] [US3] Create unit tests for SBOM generation with mocked syft CLI in packages/floe-core/tests/unit/oci/test_attestation.py
- [ ] T050 [P] [US3] Create unit tests for attestation attachment in packages/floe-core/tests/unit/oci/test_attestation.py
- [ ] T051 [P] [US3] Create CLI unit tests for artifact sbom command in packages/floe-core/tests/unit/cli/test_artifact_sbom.py

**Checkpoint**: SBOM generation and attestation functional

---

## Phase 6: User Story 4 - Verification Policy Configuration (Priority: P1)

**Goal**: Platform operators configure verification policies with per-environment enforcement

**Independent Test**: Configure policies in manifest.yaml, verify artifacts accepted/rejected based on policy rules

### Implementation for User Story 4

- [ ] T052 [US4] Implement get_enforcement_for_env() method on VerificationPolicy in packages/floe-core/src/floe_core/schemas/signing.py
- [ ] T053 [US4] Add environment context to OCIClient for policy lookup in packages/floe-core/src/floe_core/oci/client.py
- [ ] T054 [US4] Implement require_sbom validation during verification in packages/floe-core/src/floe_core/oci/verification.py
- [ ] T055 [US4] Add --environment flag to `floe artifact pull` command in packages/floe-core/src/floe_core/cli/artifact/pull.py
- [ ] T056 [US4] Add FLOE_ENVIRONMENT env var support in CLI commands in packages/floe-core/src/floe_core/cli/artifact/pull.py

### Unit Tests for User Story 4

- [ ] T057 [P] [US4] Create unit tests for per-environment policy lookup in packages/floe-core/tests/unit/schemas/test_signing.py
- [ ] T058 [P] [US4] Create unit tests for require_sbom enforcement in packages/floe-core/tests/unit/oci/test_verification.py
- [ ] T059 [P] [US4] Create CLI unit tests for --environment flag in packages/floe-core/tests/unit/cli/test_artifact_pull.py

**Checkpoint**: Verification policies with per-environment enforcement functional

---

## Phase 7: User Story 5 - Key-Based Signing for Air-Gapped (Priority: P2)

**Goal**: Enterprise users sign artifacts with pre-distributed keys, no internet required

**Independent Test**: Generate key pair, sign artifact with private key, verify with public key offline

### Implementation for User Story 5

- [x] T060 [US5] Extend SigningClient with key-based signing support in packages/floe-core/src/floe_core/oci/signing.py
- [x] T061 [US5] Implement private key file loading and KMS key reference support in packages/floe-core/src/floe_core/oci/signing.py
- [x] T062 [US5] Extend VerificationClient with key-based verification (public key) in packages/floe-core/src/floe_core/oci/verification.py
- [x] T063 [US5] Implement offline verification without Rekor in packages/floe-core/src/floe_core/oci/verification.py
- [x] T064 [US5] Add --key flag to `floe artifact sign` command in packages/floe-core/src/floe_core/cli/artifact/sign.py
- [x] T065 [US5] Add --key flag to `floe artifact verify` command in packages/floe-core/src/floe_core/cli/artifact/verify.py

### Unit Tests for User Story 5

- [x] T066 [P] [US5] Create unit tests for key-based signing with mock keys in packages/floe-core/tests/unit/oci/test_signing.py
- [x] T067 [P] [US5] Create unit tests for key-based verification in packages/floe-core/tests/unit/oci/test_verification.py
- [x] T068 [P] [US5] Create unit tests for offline verification (no Rekor) in packages/floe-core/tests/unit/oci/test_verification.py

**Checkpoint**: Key-based signing and offline verification functional

---

## Phase 8: Integration Tests

**Purpose**: End-to-end tests with real OCI registry (Harbor in Kind cluster)

- [ ] T069 Create E2E test for keyless signing flow in packages/floe-core/tests/integration/oci/test_signing_e2e.py
- [ ] T070 Create E2E test for verification during pull in packages/floe-core/tests/integration/oci/test_verification_e2e.py
- [ ] T071 Create E2E test for SBOM generation and attestation in packages/floe-core/tests/integration/oci/test_attestation_e2e.py
- [ ] T072 Create E2E test for per-environment policy enforcement in packages/floe-core/tests/integration/oci/test_verification_e2e.py
- [ ] T073 [P] Create performance benchmark test for verification (< 2s target per SC-006) in packages/floe-core/tests/integration/oci/test_verification_perf.py
- [ ] T074 [P] Create E2E test for certificate rotation grace period (FR-012) in packages/floe-core/tests/integration/oci/test_verification_e2e.py
- [ ] T075 [P] Create E2E test for offline verification bundle export/import (FR-015) in packages/floe-core/tests/integration/oci/test_verification_e2e.py

---

## Phase 9: Cross-Cutting Concerns

**Purpose**: Requirements coverage gaps, edge cases, and observability

### FR-011: Signature Metadata in Annotations

- [ ] T076 [US1] Implement SignatureMetadata.to_annotations() integration in SigningClient.sign() in packages/floe-core/src/floe_core/oci/signing.py
- [ ] T077 [P] [US1] Create unit test verifying signature metadata stored in OCI annotations in packages/floe-core/tests/unit/oci/test_signing.py

### FR-012: Certificate Rotation Support

- [ ] T078 [US5] Implement certificate chain validation with grace period in packages/floe-core/src/floe_core/oci/verification.py
- [ ] T079 [US5] Add certificate_valid_until and grace_period_days to VerificationPolicy schema in packages/floe-core/src/floe_core/schemas/signing.py
- [ ] T080 [P] [US5] Create unit tests for certificate rotation grace period in packages/floe-core/tests/unit/oci/test_verification.py

### FR-013: Audit Logging Schema

- [ ] T081 [US2] Define structured audit log schema (SigningAuditEvent, VerificationAuditEvent) in packages/floe-core/src/floe_core/schemas/signing.py
- [ ] T082 [US2] Implement structured audit logging with trace context in packages/floe-core/src/floe_core/oci/verification.py
- [ ] T083 [P] [US2] Create unit test for audit log format validation in packages/floe-core/tests/unit/oci/test_verification.py

### FR-015: Offline Verification Bundles

- [ ] T084 [US5] Implement VerificationBundle export (bundle + cert chain + Rekor entry) in packages/floe-core/src/floe_core/oci/verification.py
- [ ] T085 [US5] Add `floe artifact verify --export-bundle` and `--bundle` flags in packages/floe-core/src/floe_core/cli/artifact/verify.py
- [ ] T086 [P] [US5] Create unit test for offline bundle creation and verification in packages/floe-core/tests/unit/oci/test_verification.py

### SC-007: OpenTelemetry Trace Specification

- [ ] T087 [P] Document OTel trace span names and attributes in specs/8b-artifact-signing/research.md
- [ ] T088 [P] Create unit test verifying OTel spans emitted for sign/verify operations in packages/floe-core/tests/unit/oci/test_signing.py

### Edge Cases (from spec.md)

- [ ] T089 [US1] Implement atomic operations for concurrent signing (file locking or OCI tag locking) in packages/floe-core/src/floe_core/oci/signing.py
- [ ] T090 [US1] Implement OIDC token refresh with exponential backoff retry in packages/floe-core/src/floe_core/oci/signing.py
- [ ] T091 [P] [US1] Create unit tests for concurrent signing behavior in packages/floe-core/tests/unit/oci/test_signing.py
- [ ] T092 [P] [US1] Create unit tests for OIDC token refresh/retry logic in packages/floe-core/tests/unit/oci/test_signing.py

---

## Phase 10: Polish & Documentation

**Purpose**: Documentation, error handling, and final validation

- [ ] T093 [P] Add actionable error messages with remediation steps for all SignatureVerificationError cases in packages/floe-core/src/floe_core/oci/errors.py
- [ ] T094 [P] Create unit test validating error message quality (actionable, includes remediation) in packages/floe-core/tests/unit/oci/test_errors.py
- [ ] T095 [P] Update ADR-0041 with implementation notes in docs/architecture/adr/0041-artifact-signing-verification.md
- [ ] T096 Validate quickstart.md scenarios work end-to-end
- [ ] T097 [P] Add help text and examples to all CLI commands
- [ ] T098 [P] Add cross-reference from spec.md FR-001 to research.md (sigstore-python primary, cosign fallback)
- [ ] T099 Consolidate CLI registration into single task per phase (document pattern in CONTRIBUTING.md)
- [ ] T100 Verify all subprocess calls avoid shell=True (constitution VI compliance audit)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on Foundational (can parallel with US1)
- **User Story 3 (Phase 5)**: Depends on Foundational (can parallel with US1/US2)
- **User Story 4 (Phase 6)**: Depends on US2 (builds on verification infrastructure)
- **User Story 5 (Phase 7)**: Depends on US1 and US2 (extends signing and verification)
- **Integration Tests (Phase 8)**: Depends on all user stories
- **Cross-Cutting (Phase 9)**: Depends on US1, US2, US5 (extends core functionality)
- **Polish (Phase 10)**: Depends on all implementation phases

### User Story Dependencies

| Story | Priority | Depends On | Can Parallel With |
|-------|----------|------------|-------------------|
| US1 (Keyless Signing) | P0 | Foundational | US2, US3 |
| US2 (Verification) | P0 | Foundational | US1, US3 |
| US3 (SBOM) | P1 | Foundational | US1, US2 |
| US4 (Policies) | P1 | US2 | - |
| US5 (Key-Based) | P2 | US1, US2 | - |

### Within Each User Story

- Schemas/models before clients
- Clients before CLI commands
- Core implementation before unit tests
- CLI integration after core modules

### Parallel Opportunities

**Phase 2 (Foundational)**:
```bash
# All schema tasks can run in parallel:
T003: SigningConfig model
T004: VerificationPolicy model
T005: SignatureMetadata model
T006: VerificationResult model
T007: EnvironmentPolicy model

# All unit tests can run in parallel:
T011: SigningConfig tests
T012: VerificationPolicy tests
T013: SignatureMetadata tests
```

**After Foundational, User Stories in Parallel**:
```bash
# Team member A: User Story 1 (Signing)
# Team member B: User Story 2 (Verification)
# Team member C: User Story 3 (SBOM)
```

---

## Implementation Strategy

### MVP First (P0 Stories)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational schemas
3. Complete Phase 3: User Story 1 (Keyless Signing)
4. Complete Phase 4: User Story 2 (Verification)
5. **STOP and VALIDATE**: End-to-end signing and verification works
6. Deploy/demo if ready

### Incremental Delivery

| Milestone | Stories Included | Deliverable |
|-----------|------------------|-------------|
| MVP | US1 + US2 | Sign and verify artifacts |
| v1.1 | + US3 | SBOM support |
| v1.2 | + US4 | Per-environment policies |
| v1.3 | + US5 | Air-gapped support |

### Task Count Summary

| Phase | Task Count |
|-------|------------|
| Setup | 2 |
| Foundational | 11 |
| US1 (Keyless Signing) | 13 |
| US2 (Verification) | 14 |
| US3 (SBOM) | 11 |
| US4 (Policies) | 8 |
| US5 (Key-Based) | 9 |
| Integration Tests | 7 |
| Cross-Cutting (FR/SC gaps) | 17 |
| Polish & Documentation | 8 |
| **Total** | **100** |

---

## Notes

- [P] tasks = different files, no dependencies - can run in parallel
- [Story] label maps task to specific user story for traceability
- All signing operations use sigstore-python for keyless, cosign CLI for key-based/KMS
- Verification hooks integrate INTO OCIClient.pull() - cannot be bypassed
- Signatures stored as OCI annotations, not separate artifacts
- External CLIs (cosign, syft) invoked via subprocess with proper error handling

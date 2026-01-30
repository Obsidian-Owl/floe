# Implementation Plan: Artifact Promotion Lifecycle

**Branch**: `8c-promotion-lifecycle` | **Date**: 2026-01-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/8c-promotion-lifecycle/spec.md`

## Summary

Implement artifact promotion lifecycle for moving CompiledArtifacts through user-configurable environments (default: dev → staging → prod) with validation gates, signature verification (Epic 8B integration), rollback support with impact analysis, and immutable audit trails.

**Key User Outcomes** (from persona analysis):
- **Data Engineers**: Self-service promotion of Data Products through authorized environments
- **Platform Engineers**: Fully automated CI/CD with JSON output, structured exit codes, and environment locks
- **SREs**: Webhook notifications, trace ID linking, and environment freeze during incidents
- **Security Engineers**: Authorization controls, separation of duties, and configurable security gate thresholds

**Technical Approach**: Extend existing OCIClient with PromotionController that orchestrates gate validation, signature verification, authorization checks, tag creation, and audit logging. Leverage complete implementations from Epic 8A (OCI), 8B (Signing), and 3B (PolicyEnforcer).

## Technical Context

**Language/Version**: Python 3.10+ (matches floe-core requirements)
**Primary Dependencies**: oras (OCI operations), cosign (signing via Epic 8B), pydantic>=2.0 (schemas), click>=8.1 (CLI), structlog (logging)
**Storage**: OCI registry (immutable tags) + OCI annotations (audit metadata)
**Testing**: pytest with K8s-native integration (Kind cluster + registry)
**Target Platform**: Linux containers (K8s native), macOS/Linux development
**Project Type**: Monorepo package (floe-core extension)
**Performance Goals**: Promotion <30s (excluding gate time), verification <5s
**Constraints**: 64KB OCI annotation limit, immutable semver tags
**Scale/Scope**: 5+ logical environments, 3+ registries, 100+ promotions/day

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core/oci/, floe-core/cli/platform/)
- [x] No SQL parsing/validation in Python (N/A - no SQL in promotion)
- [x] No orchestration logic outside floe-dagster (N/A - promotion is platform, not orchestration)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (Gate validators are pluggable via command execution)
- [x] Plugin registered via entry point (Audit backends could be pluggable - future)
- [x] PluginMetadata declares name, version, floe_api_version (N/A - core module, not plugin)

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s)
- [x] Pluggable choices documented in manifest.yaml (environments, gates, audit backend)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (Promotion operates on OCI artifacts)
- [x] Pydantic v2 models for all schemas (PromotionRecord, GateResult, etc.)
- [x] Contract changes follow versioning rules (New schemas, no breaking changes)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster (With registry)
- [x] No `pytest.skip()` usage (Tests fail if registry unavailable)
- [x] `@pytest.mark.requirement()` on all integration tests (FR-001 through FR-057)

**Principle VI: Security First**
- [x] Input validation via Pydantic (All schemas use Field validation)
- [x] Credentials use SecretStr (Reuse from RegistryConfig)
- [x] No shell=True, no dynamic code execution on untrusted data (Gate commands use subprocess list form)

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml → promotion → deployment)
- [x] Layer ownership respected (Platform Team owns promotion config)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (Promotion spans with gate timing)
- [x] OpenLineage events for data transformations (N/A - no data transformation)

## Integration Design

### Entry Point Integration
- [x] Feature reachable from: CLI (`floe platform promote/rollback/status`)
- [x] Integration point: `packages/floe-core/src/floe_core/cli/platform/` (add promote.py, rollback.py, status.py)
- [x] Wiring task needed: Yes - Add commands to platform Click group

### Dependency Integration

| This Feature Uses | From Package | Integration Point |
|-------------------|--------------|-------------------|
| OCIClient | floe-core | `from floe_core.oci import OCIClient` |
| SigningClient | floe-core | `from floe_core.oci import SigningClient` |
| VerificationPolicy | floe-core | `from floe_core.schemas.signing import VerificationPolicy` |
| PolicyEnforcer | floe-core | `from floe_core.enforcement import PolicyEnforcer` |
| RegistryConfig | floe-core | `from floe_core.schemas.oci import RegistryConfig` |
| EnforcementResult | floe-core | `from floe_core.enforcement import EnforcementResult` |

### Produces for Others

| Output | Consumers | Contract |
|--------|-----------|----------|
| PromotionRecord | Epic 9B Helm, Audit systems | Pydantic model + OCI annotations |
| Environment tags (v1.2.3-staging) | GitOps/ArgoCD | OCI tag naming convention |
| Audit events | SIEM, compliance systems | OpenTelemetry traces |
| latest-{env} tags | Epic 9A deployment | Mutable OCI tags |

### Cleanup Required
- [x] Old code to remove: `OCIClient.promote_to_environment()` placeholder (raises NotImplementedError)
- [ ] Old tests to remove: None (no existing promotion tests)
- [ ] Old docs to update: None

## Project Structure

### Documentation (this feature)

```text
specs/8c-promotion-lifecycle/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0 research (complete)
├── data-model.md        # Entity definitions (complete)
├── quickstart.md        # Usage examples (complete)
├── contracts/           # API contracts
│   └── promotion-api.yaml
├── checklists/
│   └── requirements.md  # Quality checklist (complete)
└── tasks.md             # Implementation tasks (pending /speckit.tasks)
```

### Source Code (repository root)

```text
packages/floe-core/src/floe_core/
├── schemas/
│   ├── oci.py           # Existing: PromotionStatus enum
│   ├── signing.py       # Existing: VerificationPolicy, EnvironmentPolicy
│   └── promotion.py     # NEW: PromotionRecord, GateResult, EnvironmentConfig,
│                        #      AuthorizationConfig, EnvironmentLock, WebhookConfig,
│                        #      SecurityGateConfig
│
├── oci/
│   ├── client.py        # Existing: OCIClient (extend promote_to_environment)
│   ├── signing.py       # Existing: SigningClient
│   ├── verification.py  # Existing: signature verification
│   ├── promotion.py     # NEW: PromotionController
│   ├── authorization.py # NEW: AuthorizationChecker
│   ├── webhooks.py      # NEW: WebhookNotifier
│   └── audit.py         # NEW: AuditBackendPlugin, OCIAuditBackend
│
├── enforcement/
│   └── policy_enforcer.py  # Existing: PolicyEnforcer (used by gates)
│
└── cli/
    └── platform/
        ├── __init__.py  # Existing: platform group
        ├── compile.py   # Existing
        ├── promote.py   # NEW: floe platform promote
        ├── rollback.py  # NEW: floe platform rollback
        ├── status.py    # UPDATE: Add promotion status
        └── lock.py      # NEW: floe platform lock/unlock

packages/floe-core/tests/
├── unit/
│   ├── schemas/
│   │   └── test_promotion_schemas.py  # NEW
│   └── oci/
│       └── test_promotion_controller.py  # NEW
└── integration/
    └── oci/
        └── test_promotion_workflow.py  # NEW (Kind + registry)
```

**Structure Decision**: Single package extension (floe-core). No new packages required. All promotion logic added to existing `oci/` module.

## Phase 0: Research Summary

Research completed in [research.md](./research.md). Key findings:

1. **Epic 8A, 8B, 3B all complete** - Full OCI client, signing, and policy enforcement available
2. **PromotionStatus enum exists** - Ready for integration in oci.py
3. **VerificationPolicy.environments** - Already supports per-environment policies
4. **PolicyEnforcer.enforce()** - Returns EnforcementResult for gate validation
5. **Tag strategy defined** - Immutable env tags + mutable latest-{env}

No blocking issues. All dependencies ready.

## Phase 1: Design Summary

Design artifacts completed:
- [data-model.md](./data-model.md) - All entities defined with validation rules
- [contracts/promotion-api.yaml](./contracts/promotion-api.yaml) - CLI and Python API
- [quickstart.md](./quickstart.md) - Usage examples and patterns

Key design decisions:
1. **PromotionController** orchestrates all operations
2. **Gates are pluggable** via command execution (not built-in runners)
3. **Audit in OCI annotations** with optional backend extension
4. **Environment order enforced** - must follow configured path

## Complexity Tracking

No constitution violations. Design is straightforward extension of existing components.

## Implementation Phases

### Phase 2.1: Schemas (Day 1)

1. Create `promotion.py` schema module:
   - PromotionGate enum
   - GateResult model
   - EnvironmentConfig model
   - PromotionConfig model
   - PromotionRecord model
   - RollbackRecord model
   - RollbackImpactAnalysis model

2. Unit tests for all schema validation

### Phase 2.2: PromotionController (Day 1-2)

1. Create `oci/promotion.py`:
   - `PromotionController.__init__()` - Accept OCIClient, config
   - `PromotionController.validate_transition()` - Check environment order
   - `PromotionController._run_gate()` - Execute single gate
   - `PromotionController._run_all_gates()` - Execute all required gates
   - `PromotionController.promote()` - Full promotion flow
   - `PromotionController.rollback()` - Rollback flow
   - `PromotionController.get_status()` - Query current state
   - `PromotionController.analyze_rollback_impact()` - Impact analysis

2. Integration with:
   - OCIClient for tag operations
   - SigningClient for verification
   - PolicyEnforcer for policy_compliance gate

3. Unit tests with mocked dependencies

### Phase 2.3: CLI Commands (Day 2)

1. Create `cli/platform/promote.py`:
   - Click command with options
   - Dry-run output formatting
   - Error handling and exit codes

2. Create `cli/platform/rollback.py`:
   - Click command with options
   - Impact analysis output
   - Reason prompting

3. Update `cli/platform/status.py`:
   - Add promotion history
   - Table/JSON/YAML formatting

4. Wire commands to platform group

### Phase 2.4: Integration Tests (Day 3)

1. Create Kind cluster test fixtures:
   - Registry setup (distribution registry)
   - Pre-push test artifacts
   - Signing configuration

2. Integration tests:
   - Full promotion workflow (dev → staging → prod)
   - Gate validation (pass/fail scenarios)
   - Signature verification (enforce/warn/off)
   - Rollback with impact analysis
   - Status queries

3. Requirement traceability (FR-001 through FR-030)

### Phase 2.5: CI/CD Automation (Day 3)

1. Add JSON output mode (`--output=json`) to all CLI commands
2. Document and implement exit codes (0, 8, 9, 10, 11, 12, 13)
3. Include `trace_id` in all CLI output
4. Contract tests for exit code behavior

### Phase 2.6: Environment Lock/Freeze (Day 3-4)

1. Create `cli/platform/lock.py`:
   - `floe platform lock --env=<env> --reason=<reason>`
   - `floe platform unlock --env=<env> --reason=<reason>`
2. Implement EnvironmentLock storage in OCI annotations
3. Integrate lock check into promote flow
4. Unit and integration tests

### Phase 2.7: Authorization & Separation of Duties (Day 4)

1. Create `oci/authorization.py`:
   - `AuthorizationChecker.check_authorization()` - verify operator permissions
   - `AuthorizationChecker.check_separation_of_duties()` - verify different operators
2. Integrate authorization into promote flow
3. Add authorization fields to PromotionRecord
4. Unit tests with mocked group membership

### Phase 2.8: Webhook Notifications (Day 4-5)

1. Create `oci/webhooks.py`:
   - `WebhookNotifier.notify()` - async webhook delivery
   - `WebhookNotifier.build_payload()` - construct event payload
2. Configure webhooks from manifest.yaml
3. Non-blocking delivery with retry
4. Integration tests with mock webhook server

### Phase 2.9: Security Gate Configuration (Day 5)

1. Extend GateResult with SecurityScanResult
2. Implement Trivy/Grype JSON parser
3. Configurable severity thresholds
4. Unit tests for scanner output parsing

### Phase 2.10: Documentation & Cleanup (Day 5)

1. Update OCIClient.promote_to_environment() to delegate to PromotionController
2. Add OpenTelemetry spans for all operations
3. Run `/speckit.test-review` to validate test quality
4. Run `/speckit.wiring-check` to verify CLI integration

## Success Criteria Mapping

| Criteria | Implementation | Test |
|----------|---------------|------|
| SC-001: Promote <30s | PromotionController with parallel gate option | Integration timing test |
| SC-002: Verify <5s | Cached verification results | Unit timing test |
| SC-003: 100% audit trail | OCI annotations + traces | Integration audit test |
| SC-004: Rollback <60s | Direct tag update | Integration timing test |
| SC-005: Dry-run fidelity | Same gate logic, skip tag creation | Unit comparison test |
| SC-006: 3+ registries | Parallel registry sync | Integration multi-registry test |
| SC-007: Actionable errors | Structured error messages | Unit error format test |
| SC-008: CI/CD automation | JSON output + exit codes | Contract test for exit codes |
| SC-009: Lock/unlock <5s | EnvironmentLock OCI annotation | Unit + integration test |
| SC-010: Security gate config | SecurityGateConfig schema | Unit test for severity parsing |
| SC-011: Webhooks <30s | Async webhook delivery | Integration webhook test |
| SC-012: Authorization logging | AuthorizationChecker audit | Integration audit trail test |
| SC-013: Separation of duties | PromotionController checks | Unit test for operator tracking |

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Gate timeout blocking promotion | Configurable timeout per gate, async option |
| OCI annotation size limit | Compress audit data, link to external storage |
| Registry unavailable mid-promotion | Transaction-like behavior (create temp tag, then rename) |
| Signature cache invalidation | TTL-based cache with digest verification |

## Next Steps

Run `/speckit.tasks` to generate detailed implementation task list with Linear integration.

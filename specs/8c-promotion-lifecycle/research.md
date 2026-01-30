# Research: Epic 8C - Promotion Lifecycle

**Date**: 2026-01-30
**Epic**: 8C (Promotion Lifecycle)
**Status**: Complete

## Prior Decisions (from Agent Memory)

Agent memory search returned context on artifact promotion architecture:
- GitOps workflow for promotion
- Authentication mechanisms for OCI registries
- Sigstore/cosign for signature verification (implemented in Epic 8B)

## Technical Context Research

### 1. Existing Implementation State

#### Epic 8A: OCI Client (COMPLETE)
**Location**: `packages/floe-core/src/floe_core/oci/`

| Component | Status | Key Classes |
|-----------|--------|-------------|
| `client.py` | ✅ Complete | `OCIClient` - push, pull, inspect, list, sign |
| `schemas/oci.py` | ✅ Complete | `RegistryConfig`, `ArtifactManifest`, `PromotionStatus` |
| `auth.py` | ✅ Complete | Auth providers (Basic, Token, AWS IRSA, Azure MI, GCP WI) |
| `cache.py` | ✅ Complete | LRU cache with TTL for mutable tags |
| `resilience.py` | ✅ Complete | Circuit breaker, retry with backoff |

**Promotion Placeholder**: `OCIClient.promote_to_environment()` exists but raises `NotImplementedError`

**Key Insight**: `PromotionStatus` enum already defined:
```python
class PromotionStatus(str, Enum):
    NOT_PROMOTED = "not_promoted"
    PROMOTED = "promoted"
    PENDING = "pending"
```

#### Epic 8B: Artifact Signing (COMPLETE)
**Location**: `packages/floe-core/src/floe_core/oci/signing.py`

| Component | Status | Key Classes |
|-----------|--------|-------------|
| `signing.py` | ✅ Complete | `SigningClient` - sign with keyless/key-based |
| `schemas/signing.py` | ✅ Complete | `SigningConfig`, `VerificationPolicy`, `EnvironmentPolicy` |
| `verification.py` | ✅ Complete | Signature verification with cosign |

**Key Insight**: `VerificationPolicy.environments: dict[str, EnvironmentPolicy]` already supports per-environment enforcement. This is the integration point for Epic 8C.

#### Epic 3B: PolicyEnforcer (COMPLETE)
**Location**: `packages/floe-core/src/floe_core/enforcement/`

| Component | Status | Key Classes |
|-----------|--------|-------------|
| `policy_enforcer.py` | ✅ Complete | `PolicyEnforcer.enforce()` |
| `result.py` | ✅ Complete | `EnforcementResult`, `Violation` |
| `exporters/` | ✅ Complete | SARIF, JSON, HTML exporters |

**Integration Point**: `PolicyEnforcer.enforce(manifest, dry_run=bool)` returns `EnforcementResult` with pass/fail status.

#### CLI Structure (COMPLETE)
**Location**: `packages/floe-core/src/floe_core/cli/`

- `platform/` - compile, deploy, publish, status commands
- `artifact/` - push, pull, sign, verify, inspect, sbom commands

**Decision**: Add `promote`, `rollback` to `platform/` group (platform team operations)

### 2. Promotion Workflow Design

#### Tag Strategy
Based on existing `ArtifactTag.is_mutable` logic:

| Tag Type | Pattern | Mutable? | Example |
|----------|---------|----------|---------|
| Semver | `v\d+\.\d+\.\d+` | No | `v1.2.3` |
| Environment | `v\d+\.\d+\.\d+-{env}` | No | `v1.2.3-staging` |
| Latest | `latest-{env}` | Yes | `latest-prod` |
| Rollback | `v\d+\.\d+\.\d+-{env}-rollback-\d+` | No | `v1.2.2-prod-rollback-1` |

**Decision**: Promotion creates immutable env-specific tag AND updates mutable latest-{env} tag.

#### Validation Gate Integration

From spec FR-008, gates include:
1. `policy_compliance` (MANDATORY) - Uses `PolicyEnforcer` from Epic 3B
2. `tests` - External test runner invocation
3. `security_scan` - External scanner integration
4. `cost_analysis` - Cost estimation check
5. `performance_baseline` - Performance threshold check

**Decision**: Gates 2-5 are pluggable via command execution. `policy_compliance` is built-in.

#### Audit Trail Storage

Options evaluated:
1. **OCI Annotations Only** - Limited to 64KB, sufficient for single promotion record
2. **OCI + S3 Append-Only** - For full history, compliance requirements
3. **OCI + Database** - For queryable history

**Decision**: OCI annotations for current state (PromotionRecord) + configurable backend for history (default: OCI-only, optional: S3/database).

### 3. Schema Design

#### New Schemas (packages/floe-core/src/floe_core/schemas/promotion.py)

```python
class PromotionGate(str, Enum):
    """Validation gate types."""
    POLICY_COMPLIANCE = "policy_compliance"  # Always runs
    TESTS = "tests"
    SECURITY_SCAN = "security_scan"
    COST_ANALYSIS = "cost_analysis"
    PERFORMANCE_BASELINE = "performance_baseline"

class GateResult(BaseModel):
    """Individual gate execution result."""
    gate: PromotionGate
    status: Literal["passed", "failed", "skipped", "warning"]
    duration_ms: int
    error: str | None = None
    details: dict[str, Any] = {}

class PromotionRecord(BaseModel):
    """Complete promotion event record."""
    promotion_id: str  # UUID
    artifact_digest: str
    artifact_tag: str
    source_environment: str
    target_environment: str
    gate_results: list[GateResult]
    signature_verified: bool
    signature_status: VerificationResult | None
    operator: str  # Identity from OIDC or key
    promoted_at: datetime
    dry_run: bool = False

class RollbackRecord(BaseModel):
    """Rollback event record."""
    rollback_id: str
    artifact_digest: str  # Target version digest
    environment: str
    previous_digest: str  # What we're rolling back from
    reason: str
    operator: str
    rolled_back_at: datetime
    impact_analysis: RollbackImpactAnalysis | None

class EnvironmentConfig(BaseModel):
    """Per-environment configuration."""
    name: str
    gates: dict[PromotionGate, bool]  # Which gates are required
    gate_timeout_seconds: int = 300
```

#### Manifest Schema Extension (manifest.yaml)

```yaml
artifacts:
  promotion:
    environments:
      - name: dev
        gates:
          policy_compliance: true  # Always true, cannot disable
      - name: qa
        gates:
          policy_compliance: true
          tests: true
      - name: staging
        gates:
          policy_compliance: true
          tests: true
          security_scan: true
      - name: prod
        gates:
          policy_compliance: true
          tests: true
          security_scan: true
          cost_analysis: true
          performance_baseline: true
    audit:
      backend: "oci"  # oci | s3 | database
      s3_bucket: null  # Required if backend=s3
```

### 4. Integration Design

#### Entry Point Integration
- **CLI**: `floe platform promote`, `floe platform rollback`, `floe platform status`
- **Integration Point**: `packages/floe-core/src/floe_core/cli/platform/`
- **Wiring**: Add commands to `platform` Click group

#### Dependency Integration

| This Feature Uses | From Package | Integration Point |
|-------------------|--------------|-------------------|
| OCIClient | floe-core | `from floe_core.oci import OCIClient` |
| SigningClient | floe-core | `from floe_core.oci import SigningClient` |
| VerificationPolicy | floe-core | `from floe_core.schemas.signing import VerificationPolicy` |
| PolicyEnforcer | floe-core | `from floe_core.enforcement import PolicyEnforcer` |
| RegistryConfig | floe-core | `from floe_core.schemas.oci import RegistryConfig` |

#### Produces for Others

| Output | Consumers | Contract |
|--------|-----------|----------|
| PromotionRecord | Epic 9B Helm, Audit systems | Pydantic model + OCI annotations |
| Environment tags | GitOps/ArgoCD | OCI tag naming convention |
| Audit events | SIEM, compliance | OpenTelemetry traces |

#### Cleanup Required
- Remove `NotImplementedError` from `OCIClient.promote_to_environment()`
- Update method signature to match new design

### 5. Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Gate execution | subprocess + timeout | Pluggable, language-agnostic |
| Audit storage | OCI annotations primary | Keeps metadata with artifact |
| Environment order | Ordered list in manifest | Explicit, user-configurable |
| Rollback mechanism | Update mutable tag only | Immutable history preserved |
| Signature cache | Reuse Epic 8B cache | Avoid re-verification of same digest |

### 6. Alternatives Considered

#### Environment Model
- **Rejected**: Hardcoded dev/staging/prod - Inflexible for enterprises
- **Chosen**: User-configurable list in manifest.yaml (ADR-0042)

#### Audit Storage
- **Rejected**: Database-only - Adds infrastructure dependency
- **Rejected**: S3-only - Not all users have S3
- **Chosen**: OCI annotations + pluggable backend

#### Gate Execution
- **Rejected**: Built-in test runners - Too opinionated
- **Chosen**: Command execution with exit code semantics

## Conclusion

Epic 8C builds on solid foundations from Epic 8A (OCI client), 8B (signing), and 3B (policy enforcement). The implementation requires:

1. **New schemas**: `promotion.py` with PromotionRecord, GateResult, etc.
2. **New module**: `promotion.py` with PromotionController class
3. **CLI commands**: promote, rollback, status in platform group
4. **Tests**: Unit + integration with registry

All dependencies are complete and well-tested. No blocking issues identified.

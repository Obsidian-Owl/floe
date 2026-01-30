# Data Model: Epic 8C - Promotion Lifecycle

**Date**: 2026-01-30
**Epic**: 8C (Promotion Lifecycle)

## Entity Relationship Diagram

```
┌─────────────────────────┐     ┌─────────────────────────┐
│   AuthorizationConfig   │     │    EnvironmentLock      │
├─────────────────────────┤     ├─────────────────────────┤
│ allowed_groups: list    │     │ locked: bool            │
│ allowed_operators: list │     │ reason: str             │
│ separation_of_duties    │     │ locked_by: str          │
└──────────┬──────────────┘     │ locked_at: datetime     │
           │ 0:1                └───────────┬─────────────┘
           │                                │ 0:1
           ▼                                ▼
┌─────────────────────────────────────────────────┐
│              EnvironmentConfig                   │
├─────────────────────────────────────────────────┤
│ name: str                                        │──┐
│ gates: dict[PromotionGate, bool|SecurityGateCfg]│  │
│ gate_timeout: int                                │  │
│ authorization: AuthorizationConfig?              │  │
│ lock: EnvironmentLock?                           │  │
└─────────────────────────────────────────────────┘  │
                                                     │ ordered list
                                                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    PromotionConfig                           │
├─────────────────────────────────────────────────────────────┤
│ environments: list[EnvironmentConfig]                        │
│ audit_backend: AuditBackend                                  │
│ default_timeout: int                                         │
│ webhooks: list[WebhookConfig]                                │
│ gate_commands: dict[str, GateCommandConfig]                  │
└─────────────────────────────────────────────────────────────┘
           │
           │ uses
           ▼
┌─────────────────────────────────────────────────────────────┐
│                  PromotionController                         │
├─────────────────────────────────────────────────────────────┤
│ promote(tag, from_env, to_env)                               │
│ rollback(tag, env)                                           │
│ status(env?)                                                 │
│ lock(env, reason) / unlock(env, reason)                      │
│ dry_run(tag, from_env, to_env)                               │
└─────────────────────────────────────────────────────────────┘
           │
           │ produces
           ▼
┌───────────────────────────────────────┐       ┌─────────────────────────────┐
│          PromotionRecord              │       │        GateResult           │
├───────────────────────────────────────┤       ├─────────────────────────────┤
│ promotion_id: UUID                    │◄──────│ gate: PromotionGate         │
│ artifact_digest: str                  │ 1:N   │ status: GateStatus          │
│ artifact_tag: str                     │       │ duration_ms: int            │
│ source_environment: str               │       │ error: str?                 │
│ target_environment: str               │       │ details: dict               │
│ gate_results: list[GateResult]        │       │ security_summary?           │
│ signature_verified: bool              │       └─────────────────────────────┘
│ signature_status: VerificationResult  │───────┐
│ operator: str                         │       │ from Epic 8B
│ promoted_at: datetime                 │       ▼
│ dry_run: bool                         │  ┌────────────────────────┐
│ trace_id: str                         │  │  VerificationResult    │
│ authorization_passed: bool            │  │  (schemas/signing.py)  │
│ authorized_via: str?                  │  └────────────────────────┘
└───────────────────────────────────────┘

┌───────────────────────────────────────┐
│          RollbackRecord               │
├───────────────────────────────────────┤
│ rollback_id: UUID                     │
│ artifact_digest: str                  │
│ environment: str                      │
│ previous_digest: str                  │
│ reason: str                           │       ┌────────────────────────┐
│ operator: str                         │       │ RollbackImpactAnalysis │
│ rolled_back_at: datetime              │◄──────├────────────────────────┤
│ trace_id: str                         │ 0:1   │ breaking_changes: list │
│ impact_analysis: Impact?              │       │ affected_products: list│
└───────────────────────────────────────┘       │ recommendations: list  │
                                                └────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    WebhookConfig                             │
├─────────────────────────────────────────────────────────────┤
│ url: str                                                     │
│ events: list[str]                                            │
│ headers: dict[str, str]                                      │
│ timeout_seconds: int                                         │
│ retry_count: int                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  SecurityGateConfig                          │
├─────────────────────────────────────────────────────────────┤
│ command: str                                                 │
│ block_on_severity: list[str]                                 │
│ ignore_unfixed: bool                                         │
│ scanner_format: str                                          │
│ timeout_seconds: int                                         │
└─────────────────────────────────────────────────────────────┘
```

## Entities

### PromotionGate (Enum)

Validation gate types for environment promotion.

| Value | Description | Mandatory |
|-------|-------------|-----------|
| `policy_compliance` | Policy validation via PolicyEnforcer | Yes (always runs) |
| `tests` | External test execution | No |
| `security_scan` | Security vulnerability scan | No |
| `cost_analysis` | Cost estimation validation | No |
| `performance_baseline` | Performance threshold check | No |

### GateStatus (Enum)

Result status for validation gate execution.

| Value | Description |
|-------|-------------|
| `PASSED` | Gate validation succeeded |
| `FAILED` | Gate validation failed (blocks promotion) |
| `SKIPPED` | Gate not configured for this environment |
| `WARNING` | Gate passed with warnings (non-blocking) |

```python
class GateStatus(str, Enum):
    """Gate execution result status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"
```

**Note**: `FAILED` status with any gate blocks promotion (except dry-run mode).

### GateResult

Individual gate execution result.

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `gate` | PromotionGate | Gate type | Yes |
| `status` | GateStatus | Execution result | Yes |
| `duration_ms` | int | Execution time | Yes |
| `error` | str | Error message if failed | No |
| `details` | dict | Gate-specific output | No |
| `security_summary` | SecurityScanResult | Security gate details | No |

**Validation Rules**:
- `duration_ms >= 0`
- `error` required if `status == "failed"`
- `security_summary` populated only for `security_scan` gate

### EnvironmentConfig

Per-environment configuration for promotion gates, authorization, and lock state.

| Field | Type | Description | Required | Default |
|-------|------|-------------|----------|---------|
| `name` | str | Environment name | Yes | - |
| `gates` | dict[PromotionGate, bool] | Gate requirements | Yes | - |
| `gate_timeout_seconds` | int | Max gate execution time | No | 300 |
| `authorization` | AuthorizationConfig | Access control rules | No | None (allow all) |
| `lock` | EnvironmentLock | Current lock state | No | None (unlocked) |

**Validation Rules**:
- `name` must be unique within promotion config
- `policy_compliance` gate cannot be disabled (always true)
- `gate_timeout_seconds` must be 30-3600

**Example**:
```yaml
name: prod
gates:
  policy_compliance: true  # Cannot be false
  tests: true
  security_scan: true
gate_timeout_seconds: 600
authorization:
  allowed_groups: [platform-admins, release-managers]
  separation_of_duties: true
```

### PromotionConfig

Top-level promotion configuration from manifest.yaml.

| Field | Type | Description | Required | Default |
|-------|------|-------------|----------|---------|
| `environments` | list[EnvironmentConfig] | Ordered environment list | No | [dev, staging, prod] |
| `audit_backend` | AuditBackend | Audit storage type | No | "oci" |
| `default_timeout` | int | Default gate timeout | No | 300 |
| `webhooks` | list[WebhookConfig] | Notification webhooks | No | [] |
| `gate_commands` | dict[str, GateCommandConfig] | Custom gate commands | No | {} |

**State Transitions**: Environments form an ordered promotion path (index-based):
```
environments[0] → environments[1] → ... → environments[n]
```

### PromotionRecord

Complete promotion event record stored in OCI annotations and audit backend.

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `promotion_id` | UUID | Unique promotion identifier | Yes |
| `artifact_digest` | str | SHA256 digest of artifact | Yes |
| `artifact_tag` | str | Source tag (e.g., v1.2.3-dev) | Yes |
| `source_environment` | str | Source environment name | Yes |
| `target_environment` | str | Target environment name | Yes |
| `gate_results` | list[GateResult] | All gate execution results | Yes |
| `signature_verified` | bool | Signature check passed | Yes |
| `signature_status` | VerificationResult | Full verification details | No |
| `operator` | str | Identity of promoter | Yes |
| `promoted_at` | datetime | Promotion timestamp (UTC) | Yes |
| `dry_run` | bool | Was this a dry-run? | Yes |
| `trace_id` | str | OpenTelemetry trace ID for linking | Yes |
| `authorization_passed` | bool | Authorization check result | Yes |
| `authorized_via` | str | How authorization was verified (group, operator) | No |

**Validation Rules**:
- `artifact_digest` matches pattern `^sha256:[a-f0-9]{64}$`
- `source_environment` must be before `target_environment` in order
- All gate_results must have `status != "failed"` for real promotion

**OCI Annotation Keys**:
```
dev.floe.promotion.id
dev.floe.promotion.source-env
dev.floe.promotion.target-env
dev.floe.promotion.operator
dev.floe.promotion.promoted-at
dev.floe.promotion.gates-passed
```

### RollbackRecord

Rollback event record.

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `rollback_id` | UUID | Unique rollback identifier | Yes |
| `artifact_digest` | str | Target version digest | Yes |
| `environment` | str | Environment being rolled back | Yes |
| `previous_digest` | str | Current version before rollback | Yes |
| `reason` | str | Operator-provided reason | Yes |
| `operator` | str | Identity of operator | Yes |
| `rolled_back_at` | datetime | Rollback timestamp (UTC) | Yes |
| `impact_analysis` | RollbackImpactAnalysis | Pre-rollback analysis | No |
| `trace_id` | str | OpenTelemetry trace ID for linking | Yes |

**OCI Annotation Keys**:
```
dev.floe.rollback.id
dev.floe.rollback.reason
dev.floe.rollback.operator
dev.floe.rollback.rolled-back-at
dev.floe.rollback.previous-digest
```

### Rollback Tag Numbering

Rollback tags use sequential numbering per environment-version combination:

| Sequence | Tag | Meaning |
|----------|-----|---------|
| 1st rollback to v1.2.2 in prod | `v1.2.2-prod-rollback-1` | First time prod rolled back to v1.2.2 |
| 2nd rollback to v1.2.2 in prod | `v1.2.2-prod-rollback-2` | Second time prod rolled back to v1.2.2 |
| 1st rollback to v1.2.2 in staging | `v1.2.2-staging-rollback-1` | Independent sequence for staging |

**Suffix Determination Algorithm**:
1. Query registry for existing tags matching `{version}-{env}-rollback-*`
2. Extract highest suffix number (default: 0 if none exist)
3. Create tag with suffix = highest + 1

**Immutability**: Rollback tags are immutable once created. The `latest-{env}` mutable tag points to the rollback tag.

### RollbackImpactAnalysis

Pre-rollback analysis showing potential impacts.

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `breaking_changes` | list[str] | Schema/API breaking changes | Yes |
| `affected_products` | list[str] | Data products using this artifact | Yes |
| `recommendations` | list[str] | Operator recommendations | Yes |
| `estimated_downtime` | str | Estimated impact duration | No |

### AuditBackend (Enum)

| Value | Description |
|-------|-------------|
| `oci` | OCI annotations only (default) |
| `s3` | S3 append-only log |
| `database` | Database storage |

### AuditBackendPlugin (ABC)

Plugin interface for audit storage backends.

| Method | Signature | Description |
|--------|-----------|-------------|
| `store_promotion` | `(record: PromotionRecord) -> None` | Store promotion event |
| `store_rollback` | `(record: RollbackRecord) -> None` | Store rollback event |
| `query_history` | `(env: str, limit: int) -> list[PromotionRecord \| RollbackRecord]` | Query promotion/rollback history |

**Plugin Registration**: Entry point `floe.audit_backends` in pyproject.toml.

**Default Implementation**: `OCIAuditBackend` stores records in OCI manifest annotations.

### EnvironmentLock

Lock state for an environment to prevent promotions.

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `locked` | bool | Whether environment is locked | Yes |
| `reason` | str | Why environment was locked | Yes |
| `locked_by` | str | Operator who locked | Yes |
| `locked_at` | datetime | When lock was applied (UTC) | Yes |
| `unlock_reason` | str | Why environment was unlocked | No |
| `unlocked_by` | str | Operator who unlocked | No |
| `unlocked_at` | datetime | When lock was removed (UTC) | No |

**Example**:
```json
{
  "locked": true,
  "reason": "Incident #123 - Database migration in progress",
  "locked_by": "sre@acme.com",
  "locked_at": "2026-01-15T10:30:00Z"
}
```

**OCI Annotation Keys**:
```
dev.floe.lock.status
dev.floe.lock.reason
dev.floe.lock.locked-by
dev.floe.lock.locked-at
```

### AuthorizationConfig

Per-environment authorization rules.

| Field | Type | Description | Required | Default |
|-------|------|-------------|----------|---------|
| `allowed_groups` | list[str] | Groups allowed to promote | No | [] (allow all) |
| `allowed_operators` | list[str] | Specific operators allowed | No | [] |
| `separation_of_duties` | bool | Prevent same operator consecutive envs | No | false |

**Validation Rules**:
- If both `allowed_groups` and `allowed_operators` are empty, all authenticated operators are allowed
- `separation_of_duties` only checked for the immediate prior promotion

**Example**:
```yaml
authorization:
  allowed_groups:
    - platform-admins
    - release-managers
  separation_of_duties: true
```

### WebhookConfig

Webhook notification configuration.

| Field | Type | Description | Required | Default |
|-------|------|-------------|----------|---------|
| `url` | str | Webhook endpoint URL | Yes | - |
| `events` | list[str] | Events to notify (promote, rollback, lock) | No | [promote, rollback] |
| `headers` | dict[str, str] | Custom headers (e.g., auth) | No | {} |
| `timeout_seconds` | int | Request timeout | No | 30 |
| `retry_count` | int | Number of retries on failure | No | 3 |

**Example**:
```yaml
webhooks:
  - url: https://hooks.slack.com/services/T00/B00/XXX
    events: [promote, rollback]
  - url: https://api.pagerduty.com/webhooks
    events: [rollback]
    headers:
      Authorization: Token ${PAGERDUTY_TOKEN}
```

### SecurityGateConfig

Security gate configuration for vulnerability scanning.

| Field | Type | Description | Required | Default |
|-------|------|-------------|----------|---------|
| `command` | str | Scanner command with ${ARTIFACT_REF} placeholder | Yes | - |
| `block_on_severity` | list[str] | Severities that block promotion | No | [CRITICAL] |
| `ignore_unfixed` | bool | Ignore vulnerabilities without fixes | No | false |
| `scanner_format` | str | Output format (trivy, grype) | No | trivy |
| `timeout_seconds` | int | Scanner timeout | No | 600 |

**Validation Rules**:
- `block_on_severity` values must be: CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN
- `scanner_format` must be: trivy, grype

**Example**:
```yaml
gates:
  security_scan:
    command: "trivy image ${ARTIFACT_REF} --format json"
    block_on_severity: [CRITICAL, HIGH]
    ignore_unfixed: true
```

### SecurityScanResult

Security gate execution result details.

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `total_vulnerabilities` | int | Total CVEs found | Yes |
| `by_severity` | dict[str, int] | Count per severity level | Yes |
| `blocking_cves` | list[str] | CVE IDs that blocked promotion | Yes |
| `ignored_unfixed` | int | Count of ignored unfixed CVEs | No |

**Example**:
```json
{
  "total_vulnerabilities": 15,
  "by_severity": {"CRITICAL": 0, "HIGH": 2, "MEDIUM": 8, "LOW": 5},
  "blocking_cves": ["CVE-2024-1234", "CVE-2024-5678"],
  "ignored_unfixed": 3
}
```

### Promotion Transaction Semantics

Promotion is NOT atomic but provides best-effort cleanup and idempotent retry:

**Success Path**:
1. Verify artifact exists with source tag
2. Verify signature (if enforcement enabled)
3. Run all gates
4. Create immutable environment tag (`v1.2.3-staging`)
5. Update mutable latest tag (`latest-staging`)
6. Write promotion record to OCI annotations

**Failure Handling**:

| Failure Point | Behavior |
|---------------|----------|
| Before tag creation (steps 1-3) | No cleanup needed, nothing created |
| After env tag, before latest tag | Env tag exists (immutable), promotion marked incomplete |
| After latest tag, before record | Tags exist, record creation retried |

**Idempotency**: Promotion with `--force` can retry incomplete promotions. System checks if env tag exists with matching digest before reporting error.

**Recovery**: Failed promotions can be retried. System detects existing tags and skips creation if digests match.

## Relationships

1. **PromotionConfig → EnvironmentConfig**: One-to-many ordered list
2. **PromotionRecord → GateResult**: One-to-many (all gates for this promotion)
3. **PromotionRecord → VerificationResult**: One-to-one optional (from Epic 8B)
4. **RollbackRecord → RollbackImpactAnalysis**: One-to-one optional

## Existing Schemas to Reuse

From `packages/floe-core/src/floe_core/schemas/`:

| Schema | Location | Usage |
|--------|----------|-------|
| VerificationResult | signing.py | Signature verification outcome |
| VerificationPolicy | signing.py | Environment-specific verification |
| EnvironmentPolicy | signing.py | Per-env verification override |
| PromotionStatus | oci.py | Artifact promotion state enum |
| ArtifactManifest | oci.py | Artifact metadata with promotion_status |

## State Diagram: Promotion Status

```
                    ┌──────────────┐
                    │ NOT_PROMOTED │
                    └──────┬───────┘
                           │
                           │ promote(from=none, to=dev)
                           ▼
                    ┌──────────────┐
                    │   PROMOTED   │◄────────────────┐
                    │   (to dev)   │                 │
                    └──────┬───────┘                 │
                           │                        │
                           │ promote(from=dev,      │ promote(from=staging,
                           │         to=staging)    │         to=prod)
                           ▼                        │
                    ┌──────────────┐                │
                    │   PROMOTED   │────────────────┘
                    │ (to staging) │
                    └──────────────┘

Note: PENDING state used during async gate execution
```

## Index and Query Patterns

### By Environment
```
SELECT * FROM promotions WHERE target_environment = 'prod'
ORDER BY promoted_at DESC
```

### By Artifact
```
SELECT * FROM promotions WHERE artifact_digest = 'sha256:...'
ORDER BY promoted_at ASC
```

### By Operator
```
SELECT * FROM promotions WHERE operator = 'ci@github.com'
```

## JSON Schema Export

All new schemas will export JSON Schema for IDE autocomplete:
- `promotion.schema.json` - PromotionRecord, GateResult
- `manifest.promotion.schema.json` - PromotionConfig section

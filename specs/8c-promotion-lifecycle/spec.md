# Feature Specification: Artifact Promotion Lifecycle

**Epic**: 8C (Promotion Lifecycle)
**Feature Branch**: `8c-promotion-lifecycle`
**Created**: 2026-01-30
**Status**: Draft
**Input**: User description: "Implement artifact promotion lifecycle for moving CompiledArtifacts through dev→staging→prod environments with validation gates, signature verification, rollback support, and audit trails."

## Overview

This feature implements the complete artifact promotion lifecycle for floe platform. Promotion moves **immutable OCI artifacts** (CompiledArtifacts) through **user-configurable environments** (default: dev → staging → prod, but enterprises can define custom paths like dev → qa → uat → staging → prod) with:

- **Validation gates** per environment (policy compliance, tests, security scans)
- **Signature verification** before promotion (Epic 8B integration)
- **Rollback support** with impact analysis
- **Immutable audit trails** for compliance

### Architectural Context

The promotion lifecycle operates across the four-layer architecture:

```
Layer 1: Foundation     → PromotionController, VerificationClient (Python code)
Layer 2: Configuration  → manifest.yaml promotion gates, RegistryConfig
Layer 3: Services       → OCI Registry (Harbor/ECR/ACR), Audit storage
Layer 4: Data           → N/A (promotion operates on Layer 2 artifacts)
```

**Key Constraint**: Artifacts are **immutable** once published. Promotion creates **new tags** pointing to the same digest, never modifies content.

### Relationship to Epic 9B (Helm Charts)

This epic produces **runtime configuration** that Epic 9B consumes to generate Helm values:

```
CompiledArtifacts (8C output)
     ↓
Epic 9B Helm Generator
     ↓
Helm values.yaml (per environment)
     ├─ Plugin-specific K8s configs
     ├─ Secret references (via SecretReference)
     └─ Resource limits, replicas, etc.
```

Promotion gates validate that artifacts are **ready for Helm deployment** before creating environment tags.

#### Separation of Concerns: Logical vs Physical Environments

**Epic 8C owns**: Logical environment promotion
- User-defined environment names and order (e.g., `[dev, qa, uat, staging, prod]`)
- Per-environment validation gates and policies
- Artifact tagging (`v1.2.3-qa`, `v1.2.3-staging`, etc.)
- Promotion audit trail and signature verification

**Epic 9B owns**: Physical cluster deployment mapping
- Mapping logical environments to physical K8s clusters
- Example: `qa`, `uat`, `staging` all deploy to `non-prod` cluster
- Example: `prod` deploys to `prod` cluster
- Namespace isolation, RBAC, NetworkPolicy per logical environment within shared cluster

This separation enables enterprises to:
1. Define 5+ logical promotion stages with different validation rigor
2. Deploy to only 2 physical clusters (cost optimization)
3. Use Kubernetes namespace isolation for logical environment separation
4. Apply different resource quotas, network policies per logical environment

## Scope

### In Scope

- CLI commands: `floe platform promote`, `floe platform rollback`, `floe platform status`
- Promotion gate validation (policy, tests, security)
- Signature verification before promotion (integrate Epic 8B SigningClient)
- Environment-specific tag creation (v1.2.3-dev → v1.2.3-staging → v1.2.3-prod)
- Rollback with impact analysis
- Promotion audit records (OCI annotations + append-only log)
- Promotion metadata schema (PromotionRecord, ValidationGateResult)
- Cross-registry artifact sync (optional, for multi-region DR)

### Out of Scope

- Approval workflows (external to floe - GitHub Environments, CI/CD approval rules)
- Helm chart generation (Epic 9B)
- Deployment to K8s (Epic 9A)

**Note**: Data product promotion uses the same infrastructure as platform artifact promotion. Data Engineers can promote their own CompiledArtifacts using the same CLI commands with appropriate authorization.

### Integration Points

**Entry Point**: `floe platform promote/rollback/status` CLI commands (floe-cli package)

**Dependencies**:
- `floe-core`: CompiledArtifacts, OCIClient, SigningClient (Epic 8A, 8B)
- `floe-core`: PolicyEnforcer (Epic 3B) for validation gates
- OCI Registry: Harbor/ECR/ACR with immutable tag support

**Produces**:
- `PromotionRecord` schema (new, added to floe-core/schemas/)
- `VerificationClient` class (new, floe-core/oci/verification.py)
- Audit log entries (OCI annotations + configurable backend)
- Environment-tagged artifacts in registry

**Used By**:
- Epic 9B: Helm charts pull promoted artifacts from registry
- Epic 9A: K8s deployment uses latest-{env} mutable tags
- Platform operators: Query promotion history for compliance

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Promote Artifact to Next Environment (Priority: P1)

As a **platform engineer**, I want to promote a validated artifact from dev to staging so that the artifact is available for staging integration tests without re-building.

**Why this priority**: Core promotion flow - without this, no artifacts can move through environments.

**Independent Test**: Can be fully tested by running `floe platform promote v1.2.3 --from=dev --to=staging` and verifying the artifact is tagged in the registry with `v1.2.3-staging`.

**Acceptance Scenarios**:

1. **Given** an artifact `v1.2.3-dev` exists in registry with valid signature, **When** I run `floe platform promote v1.2.3 --from=dev --to=staging`, **Then** a new immutable tag `v1.2.3-staging` is created pointing to the same digest, mutable tag `latest-staging` is updated, and a promotion record is stored.

2. **Given** an artifact `v1.2.3-dev` exists but has invalid signature, **When** I run `floe platform promote v1.2.3 --from=dev --to=staging`, **Then** promotion fails with "Signature verification failed" error and artifact is NOT tagged.

3. **Given** manifest.yaml defines `staging.gates.tests: true`, **When** I promote to staging and tests fail, **Then** promotion fails with "Gate 'tests' failed" error and artifact is NOT tagged.

---

### User Story 2 - Dry-Run Promotion (Priority: P1)

As a **platform engineer**, I want to preview what a promotion would do before actually executing it so that I can verify gate requirements and catch issues early.

**Why this priority**: Critical for safe operations - prevents accidental promotions to production.

**Independent Test**: Run `floe platform promote v1.2.3 --from=staging --to=prod --dry-run` and verify it outputs the gates that would run, estimated duration, and any blocking issues without creating tags.

**Acceptance Scenarios**:

1. **Given** an artifact ready for production promotion, **When** I run `floe platform promote v1.2.3 --from=staging --to=prod --dry-run`, **Then** I see a summary of: gates to be validated, estimated time, current signature status, and "Promotion would succeed" or blocking reasons.

2. **Given** an artifact with failed policy compliance, **When** I run dry-run, **Then** I see "BLOCKED: Policy compliance gate would fail" with specific violations listed.

---

### User Story 3 - Rollback to Previous Version (Priority: P2)

As a **platform engineer**, I want to rollback production to a previous artifact version when issues are discovered so that I can quickly restore a known-good state.

**Why this priority**: Essential for operational safety - enables rapid recovery from bad deployments.

**Independent Test**: Run `floe platform rollback v1.2.2 --env=prod` and verify `latest-prod` now points to v1.2.2 digest with a rollback audit record.

**Acceptance Scenarios**:

1. **Given** `v1.2.3-prod` is current and `v1.2.2-prod` exists, **When** I run `floe platform rollback v1.2.2 --env=prod`, **Then** mutable tag `latest-prod` is updated to point to v1.2.2 digest, a rollback audit record is created, and immutable tags remain unchanged.

2. **Given** I want to rollback, **When** I run `floe platform rollback v1.2.2 --env=prod --dry-run`, **Then** I see impact analysis: breaking changes between versions, affected data products, estimated downtime (if any).

3. **Given** v1.2.0-prod does not exist (never promoted to prod), **When** I run rollback to v1.2.0, **Then** I get error "Version v1.2.0 was never promoted to prod. Available versions: v1.2.1-prod, v1.2.2-prod".

---

### User Story 4 - Query Promotion Status (Priority: P2)

As a **platform operator**, I want to query the current promotion status across environments so that I can understand what versions are deployed where.

**Why this priority**: Essential for operational visibility and troubleshooting.

**Independent Test**: Run `floe platform status` and verify it shows current versions in each environment with promotion timestamps.

**Acceptance Scenarios**:

1. **Given** promotions have occurred, **When** I run `floe platform status`, **Then** I see a table:
   ```
   Environment   Version     Digest          Promoted By        At
   dev           v1.2.3      sha256:abc...   ci@github.com      2026-01-15 10:30
   staging       v1.2.3      sha256:abc...   platform@acme.com  2026-01-15 14:45
   prod          v1.2.2      sha256:def...   platform@acme.com  2026-01-14 09:00
   ```

2. **Given** I want details on a specific environment, **When** I run `floe platform status --env=prod --history=5`, **Then** I see the last 5 promotion/rollback events for production.

---

### User Story 5 - Verification Before Artifact Use (Priority: P1)

As a **data engineer**, when I run `floe init --platform=v1.2.3`, the system should verify the artifact signature before using it so that I'm protected against tampered artifacts.

**Why this priority**: Security foundation - ensures artifact integrity across the platform.

**Independent Test**: Run `floe init --platform=v1.2.3` with a tampered artifact (modified after signing) and verify it fails with signature verification error.

**Acceptance Scenarios**:

1. **Given** verification.enforcement is "enforce" in manifest.yaml, **When** I init with a validly signed artifact, **Then** artifact is used and CLI confirms "Signature verified".

2. **Given** verification.enforcement is "enforce", **When** I init with an unsigned artifact, **Then** init fails with "Artifact is unsigned and enforcement is enabled".

3. **Given** verification.enforcement is "warn", **When** I init with an unsigned artifact, **Then** init succeeds with warning "WARNING: Artifact is unsigned".

4. **Given** verification.enforcement is "off", **When** I init with any artifact, **Then** no verification is performed.

---

### User Story 6 - Cross-Registry Sync (Priority: P3)

As a **platform engineer** in a multi-region setup, I want artifact promotion to sync to backup registries so that disaster recovery is enabled.

**Why this priority**: Advanced feature for enterprise deployments with DR requirements.

**Independent Test**: Configure two registries in manifest.yaml, promote an artifact, verify it appears in both registries with matching digests.

**Acceptance Scenarios**:

1. **Given** manifest.yaml defines primary and secondary registries, **When** I promote an artifact, **Then** it is pushed to both registries with the same tag and promotion record indicates sync status for each.

2. **Given** secondary registry is temporarily unavailable, **When** I promote, **Then** primary succeeds, secondary fails with warning, and promotion record shows partial success.

---

### User Story 7 - CI/CD Automation Integration (Priority: P1)

As a **DevOps engineer**, I want structured JSON output and documented exit codes so that I can fully automate promotion pipelines without parsing human-readable text.

**Why this priority**: Full CI/CD automation is critical for enterprise adoption - enables GitOps workflows.

**Independent Test**: Run `floe platform promote v1.2.3 --from=dev --to=staging --output=json` and verify structured JSON output with exit code 0.

**Acceptance Scenarios**:

1. **Given** I run any promotion command with `--output=json`, **When** the command completes, **Then** I receive structured JSON with fields: `success`, `promotion_id`, `artifact_digest`, `gate_results[]`, `trace_id`, `error` (if failed).

2. **Given** a promotion fails due to gate failure, **When** I check the exit code, **Then** exit code is 8 (gate failure) and JSON output includes `gate_results` with failure details.

3. **Given** I run status command with `--output=json`, **When** it completes, **Then** I receive JSON array of environment statuses suitable for parsing.

4. **Given** any promotion/rollback operation, **When** it completes, **Then** the CLI output includes `trace_id` for linking to observability dashboards.

---

### User Story 8 - Environment Lock/Freeze (Priority: P1)

As an **SRE**, during an active incident I want to lock an environment to prevent promotions so that I can stabilize the system without worrying about changes.

**Why this priority**: Operational safety during incidents - prevents cascading failures.

**Independent Test**: Run `floe platform lock --env=prod --reason="Incident #123"` then attempt promotion and verify it's rejected.

**Acceptance Scenarios**:

1. **Given** an environment is not locked, **When** I run `floe platform lock --env=prod --reason="Incident #123"`, **Then** the environment is locked and lock status is recorded with timestamp and operator.

2. **Given** production is locked, **When** I attempt `floe platform promote --to=prod`, **Then** promotion fails with "Environment 'prod' is locked. Reason: Incident #123. Locked by: sre@acme.com at 2026-01-15 10:30".

3. **Given** production is locked, **When** I run `floe platform unlock --env=prod --reason="Incident resolved"`, **Then** the lock is released and unlock event is recorded.

4. **Given** I want to see lock status, **When** I run `floe platform status`, **Then** locked environments are clearly marked with lock reason and operator.

---

### User Story 9 - Webhook Notifications (Priority: P2)

As an **SRE**, I want promotion and rollback events to trigger webhooks so that I can integrate with Slack, PagerDuty, and other alerting systems.

**Why this priority**: Operational visibility - SREs need real-time notification of changes.

**Independent Test**: Configure webhook URL in manifest.yaml, promote an artifact, verify webhook is called with event payload.

**Acceptance Scenarios**:

1. **Given** a webhook URL is configured in manifest.yaml, **When** a promotion succeeds, **Then** a POST request is sent to the webhook with payload containing: event_type, promotion_id, artifact_tag, source_env, target_env, operator, timestamp.

2. **Given** a webhook URL is configured, **When** a rollback occurs, **Then** a POST request is sent with event_type="rollback", reason, and impact_analysis.

3. **Given** webhook delivery fails, **When** the promotion completes, **Then** a warning is logged but promotion is NOT blocked (non-blocking webhook).

4. **Given** multiple webhooks are configured, **When** a promotion occurs, **Then** all webhooks are called in parallel.

---

### User Story 10 - Authorization and Access Control (Priority: P1)

As a **security engineer**, I want environment-specific authorization rules so that only approved operators can promote to production.

**Why this priority**: Security and compliance - separation of duties is required for SOX/SOC2.

**Independent Test**: Configure prod to require "platform-admins" group, attempt promotion with non-admin user, verify rejection.

**Acceptance Scenarios**:

1. **Given** authorization is configured for production environment, **When** an unauthorized operator attempts promotion to prod, **Then** promotion fails with "Unauthorized: Operator 'dev@acme.com' is not authorized to promote to 'prod'. Required groups: [platform-admins]".

2. **Given** authorization rules exist, **When** an authorized operator promotes to prod, **Then** promotion succeeds and authorization check is recorded in audit trail.

3. **Given** manifest.yaml defines environment-specific authorization, **When** I promote to staging (less restrictive), **Then** authorization check passes for broader set of operators.

4. **Given** I want to audit authorization decisions, **When** I query promotion history, **Then** each record includes authorization_check_passed and authorized_by fields.

---

### User Story 11 - Separation of Duties (Priority: P2)

As a **compliance officer**, I want to enforce that the same operator cannot promote through all environments so that we meet SOX/SOC2 separation of duties requirements.

**Why this priority**: Compliance requirement for regulated industries.

**Independent Test**: Enable separation-of-duties policy, have same operator promote dev→staging→prod, verify final promotion is rejected.

**Acceptance Scenarios**:

1. **Given** separation-of-duties is enabled for production, **When** the operator who promoted to staging attempts to promote the same artifact to prod, **Then** promotion fails with "Separation of duties violation: Operator 'platform@acme.com' promoted this artifact to staging and cannot also promote to prod".

2. **Given** separation-of-duties is enabled, **When** a different operator promotes to prod, **Then** promotion succeeds.

3. **Given** separation-of-duties is optional, **When** it's disabled in manifest.yaml, **Then** same operator can promote through all environments.

4. **Given** separation-of-duties is enabled, **When** I query promotion history, **Then** violations are clearly logged for compliance reporting.

---

### User Story 12 - Security Gate Configuration (Priority: P1)

As a **security engineer**, I want to configure security scan severity thresholds so that only vulnerabilities above a threshold block promotion.

**Why this priority**: Security gates need configurability - not all CVEs should block deployment.

**Independent Test**: Configure security gate to block on CRITICAL/HIGH only, promote artifact with MEDIUM vulnerabilities, verify success.

**Acceptance Scenarios**:

1. **Given** security gate is configured with `block_on_severity: [CRITICAL, HIGH]`, **When** artifact has only MEDIUM vulnerabilities, **Then** promotion succeeds with warning listing MEDIUM issues.

2. **Given** security gate is configured with `block_on_severity: [CRITICAL, HIGH]`, **When** artifact has HIGH vulnerability, **Then** promotion fails with details of blocking vulnerabilities.

3. **Given** security gate is configured with `ignore_unfixed: true`, **When** artifact has unfixed vulnerabilities, **Then** those vulnerabilities are not counted toward blocking threshold.

4. **Given** I want to see security gate results, **When** I view promotion record, **Then** it includes full vulnerability summary (counts by severity, CVE IDs).

---

### Edge Cases

- What happens when promoting an artifact that doesn't exist? → Error with suggested versions
- What happens when target environment tag already exists? → Error "Already promoted, use --force to re-promote"
- What happens during promotion if registry connection fails mid-operation? → Transaction aborted, no partial tags created
- What happens when rolling back to a version with incompatible schema? → Impact analysis warns of breaking changes
- What happens when OIDC token expires during verification? → Retry with backoff (reuse Epic 8B patterns)
- What happens when promotion gates timeout? → Configurable timeout, fail-safe behavior

## Requirements *(mandatory)*

### Functional Requirements

#### Promotion Core

- **FR-001**: System MUST support promoting artifacts between user-defined environments configured in manifest.yaml (unidirectional, following configured promotion path)
- **FR-001a**: System MUST allow defining custom environment names and promotion order in manifest.yaml `artifacts.promotion.environments` section (e.g., `[dev, qa, uat, staging, prod]`)
- **FR-001b**: System MUST provide sensible defaults (`[dev, staging, prod]`) when no custom environments are configured
- **FR-002**: System MUST create immutable environment-specific tags (e.g., `v1.2.3-staging`) on promotion
- **FR-003**: System MUST update mutable "latest" tags (e.g., `latest-staging`) to point to promoted artifact
- **FR-004**: System MUST verify artifact signature before promotion when `verification.enforcement` is "enforce" or "warn"
- **FR-005**: System MUST fail promotion if signature verification fails and enforcement is "enforce"
- **FR-006**: System MUST run configured validation gates before allowing promotion
- **FR-007**: System MUST support dry-run mode that shows what would happen without making changes

#### Validation Gates

- **FR-008**: System MUST support the following gate types: `policy_compliance`, `tests`, `security_scan`, `cost_analysis`, `performance_baseline`
- **FR-009**: System MUST load gate configuration from manifest.yaml `artifacts.promotion.gates` section
- **FR-009a**: System MUST extend PlatformManifest schema with `artifacts.promotion` configuration section
- **FR-010**: Gates `policy_compliance` MUST always run (cannot be disabled) using PolicyEnforcer from Epic 3B
- **FR-011**: System MUST record gate execution results (passed/failed/skipped/warning) in promotion record
- **FR-012**: System MUST allow environment-specific gate configurations (e.g., staging requires tests, prod requires all)

#### Gate Timeout and Execution

- **FR-012a**: System MUST support configurable timeout per gate with default of 300 seconds
- **FR-012b**: System MUST terminate gate execution when timeout is exceeded
- **FR-012c**: System MUST record timeout as `GateStatus.FAILED` with error "Gate execution timed out after {N} seconds"
- **FR-012d**: System MUST support per-environment gate timeout override via `gate_timeout_seconds` in EnvironmentConfig

#### Rollback

- **FR-013**: System MUST support rollback to any previously promoted version for an environment
- **FR-014**: System MUST create rollback-specific tags using pattern `v{X.Y.Z}-{env}-rollback-{N}` where N is a sequential number per environment-version combination
- **FR-015**: System MUST update mutable "latest" tag to rolled-back version
- **FR-016**: System MUST provide impact analysis in dry-run mode: breaking changes, affected products
- **FR-017**: System MUST record rollback in audit trail with reason and operator identity

#### Verification

- **FR-018**: System MUST implement full signature verification using cosign/sigstore
- **FR-019**: System MUST support keyless verification (Rekor transparency log)
- **FR-020**: System MUST support key-based verification (public key file)
- **FR-021**: System MUST respect `verification.enforcement` policy: "off", "warn", "enforce"
- **FR-022**: System MUST cache verification results to avoid re-verifying immutable artifacts

#### Audit Trail

- **FR-023**: System MUST store promotion metadata in OCI manifest annotations
- **FR-024**: System MUST emit OpenTelemetry traces for all promotion operations with span hierarchy (promote → gate → verify)
- **FR-025**: System MUST support configurable audit log backend via AuditBackendPlugin interface
- **FR-025a**: System MUST provide OCIAuditBackend as default implementation (stores in OCI annotations)
- **FR-025b**: System SHOULD provide S3AuditBackend for append-only S3 storage (optional plugin)
- **FR-025c**: System SHOULD provide DatabaseAuditBackend for queryable storage (optional plugin)
- **FR-026**: Audit records MUST be immutable once written
- **FR-027**: Audit records MUST include: promotion_id, artifact_digest, source_env, target_env, operator, timestamp, gate_results, signature_status

#### Cross-Registry Sync (Optional)

- **FR-028**: System SHOULD support promotion to multiple registries concurrently
- **FR-029**: System SHOULD verify digest match across all registries after sync
- **FR-030**: System SHOULD continue with primary if secondary registries fail (with warnings)

#### CI/CD Automation

- **FR-031**: System MUST provide structured JSON output mode (`--output=json`) for all CLI commands
- **FR-032**: System MUST return documented exit codes for scripting (0=success, 8=gate failure, 9=invalid transition, 10=tag exists, 11=version not promoted, 12=authorization failed, 13=environment locked)
- **FR-033**: System MUST include `trace_id` in CLI output for linking to observability dashboards
- **FR-034**: JSON output MUST include: success, promotion_id, artifact_digest, gate_results, trace_id, error (if failed)

#### Environment Lock/Freeze

- **FR-035**: System MUST support environment locking via `floe platform lock --env=<env> --reason=<reason>`
- **FR-036**: System MUST reject promotions to locked environments with clear error message including lock reason, operator, and timestamp
- **FR-037**: System MUST support environment unlocking via `floe platform unlock --env=<env> --reason=<reason>`
- **FR-038**: System MUST record lock/unlock events in audit trail
- **FR-039**: System MUST display lock status in `floe platform status` output

#### Webhook Notifications

- **FR-040**: System SHOULD support webhook notification for promotion events via manifest.yaml configuration
- **FR-041**: System SHOULD support webhook notification for rollback events
- **FR-042**: Webhook payload MUST include: event_type, promotion_id/rollback_id, artifact_tag, environment(s), operator, timestamp, trace_id
- **FR-043**: Webhook failures MUST NOT block promotion/rollback operations (non-blocking, warning only)
- **FR-044**: System SHOULD support multiple webhook endpoints called in parallel

#### Authorization and Access Control

- **FR-045**: System MUST verify operator identity via registry authentication (inherits from OCIClient)
- **FR-046**: System MUST support environment-specific authorization rules in manifest.yaml
- **FR-047**: Authorization rules MUST support group-based access (e.g., `allowed_groups: [platform-admins]`)
- **FR-048**: System MUST record authorization decisions in audit trail
- **FR-049**: System MUST provide clear error messages for authorization failures including required permissions

#### Separation of Duties

- **FR-050**: System SHOULD support optional separation-of-duties policy per environment
- **FR-051**: When enabled, system MUST prevent same operator from promoting same artifact through consecutive environments
- **FR-052**: System MUST record separation-of-duties violations in audit trail
- **FR-053**: Separation-of-duties policy MUST be configurable in manifest.yaml

#### Security Gate Configuration

- **FR-054**: Security gate MUST support configurable severity thresholds (`block_on_severity: [CRITICAL, HIGH]`)
- **FR-055**: Security gate MUST support `ignore_unfixed: true|false` option
- **FR-056**: Security gate results MUST include vulnerability summary (counts by severity, CVE IDs)
- **FR-057**: Security gate MUST accept standard scanner output formats (Trivy JSON, Grype JSON)

### Key Entities

- **EnvironmentConfig**: Defines the promotion path as an ordered list of environment names with per-environment gate configurations, authorization rules, and lock status
- **PromotionRecord**: Complete promotion event with artifact reference, source/target environments, gate results, signature verification, operator identity, authorization decision, and trace_id
- **ValidationGateResult**: Individual gate execution result with name, status (passed/failed/skipped/warning), duration, error details, and security_summary (for security gates)
- **RollbackImpactAnalysis**: Pre-rollback analysis showing breaking changes, affected products, and recommendations
- **VerificationResult**: Signature verification outcome with mode (keyless/key-based), issuer, subject, and certificate fingerprint
- **AuditBackendPlugin**: Plugin interface for audit storage backends (OCI annotations, S3 append-only, database)
- **EnvironmentLock**: Lock state for an environment with reason, operator, locked_at timestamp, and unlock_reason
- **AuthorizationConfig**: Per-environment authorization rules with allowed_groups, allowed_operators, and separation_of_duties flag
- **WebhookConfig**: Webhook notification configuration with url, events (promote/rollback), and retry settings
- **SecurityGateConfig**: Security gate configuration with block_on_severity, ignore_unfixed, and scanner_format

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Platform engineers can promote an artifact from dev to staging in under 30 seconds (excluding gate execution time)
- **SC-002**: Signature verification adds less than 5 seconds overhead to artifact pull operations
- **SC-003**: 100% of promotions have complete audit trails queryable within 1 hour of occurrence
- **SC-004**: Rollback operation completes in under 60 seconds for any environment
- **SC-005**: Dry-run mode accurately predicts promotion outcome with 100% fidelity (same gates, same checks)
- **SC-006**: System handles promotion to 3+ registries concurrently without data inconsistency
- **SC-007**: All promotion failures are clearly attributable to specific gate failures with actionable error messages
- **SC-008**: CI/CD pipelines can fully automate promotion using JSON output and exit codes without parsing human text
- **SC-009**: SREs can lock/unlock environments within 5 seconds, preventing all promotions during incidents
- **SC-010**: Security teams can configure security gates with severity thresholds without code changes
- **SC-011**: Webhook notifications are delivered within 30 seconds of promotion/rollback events
- **SC-012**: Authorization violations are clearly logged with required permissions for compliance reporting
- **SC-013**: Separation of duties violations are prevented and logged when policy is enabled

### Non-Functional Requirements

- **NFR-001**: Gate timeout default MUST be 300 seconds
- **NFR-002**: Gate timeout MUST be configurable between 30-3600 seconds
- **NFR-003**: Timed-out gate MUST be killable (SIGTERM, then SIGKILL after 5s grace period)
- **NFR-004**: Promotion transaction MUST provide idempotent retry capability for incomplete operations
- **NFR-005**: OCI annotation payload MUST gracefully handle 64KB size limit with truncation

## Assumptions

1. **Registry supports immutable tags**: Target registries (Harbor, ECR, ACR) support tag immutability or provide it via policy
2. **Signing is already implemented**: Epic 8B SigningClient is complete and functional
3. **PolicyEnforcer is available**: Epic 3B PolicyEnforcer can be imported and used for policy_compliance gate
4. **OCI annotations are sufficient for metadata**: 64KB OCI annotation limit is adequate for promotion records
5. **Single environment per registry namespace**: Each environment (dev/staging/prod) maps to one registry namespace
6. **Unidirectional promotion**: Follows configured environment order; no backward promotion (use rollback instead)

## Open Questions

None - all critical decisions documented in ADRs and Epic 8A/8B implementations.

## Glossary

| Term | Definition |
|------|------------|
| **Environment** | A logical stage in the promotion pipeline (e.g., dev, qa, uat, staging, prod) - user-configurable |
| **Promotion** | Creating new environment tag pointing to existing artifact digest |
| **Immutable tag** | Tag that cannot be reassigned to different digest (e.g., v1.2.3-prod) |
| **Mutable tag** | Tag that can be updated to point to new digest (e.g., latest-prod) |
| **Validation gate** | Pre-promotion check that must pass before artifact can be promoted |
| **Rollback** | Updating mutable tag to point to previous version's digest |
| **Audit trail** | Immutable record of all promotion/rollback operations |
| **Logical environment** | Environment defined by configuration/policy, not necessarily a separate cluster |
| **Physical environment** | Actual K8s cluster or infrastructure deployment target |

## Clarifications

- Q: Should environments be user-configurable in manifest.yaml (allowing 4+ environments like dev → qa → uat → staging → prod)? A: **Yes - Logical Environment Model**. User-defined environments in manifest.yaml. Supports 4+ logical envs. Physical deployment is a separate concern (handled by Epic 9B Helm).

- Q: Should Epic 8C focus purely on logical environment promotion (gates, audit, tagging) while physical cluster deployment remains a separate concern for Epic 9B Helm charts? A: **Yes - Logical Environments Only**. Epic 8C defines logical envs with gates/policies. Physical cluster mapping handled by Epic 9B Helm (e.g., `qa` and `staging` both deploy to non-prod cluster). This enables enterprises to deploy 2 physical clusters (prod, non-prod) while having 5+ logical promotion stages with different validation gates and policies.

## References

- **ADR-0039**: Validation gates configuration
- **ADR-0040**: Immutability enforcement
- **ADR-0041**: Artifact signing (Epic 8B)
- **ADR-0042**: Logical vs Physical Environment Model (NEW - Epic 8C/9B boundary)
- **Epic 8A**: OCI client implementation
- **Epic 8B**: Artifact signing implementation
- **Epic 3B**: PolicyEnforcer for policy_compliance gate
- **Epic 9B**: Helm charts (consumer of promoted artifacts, owns physical cluster mapping)

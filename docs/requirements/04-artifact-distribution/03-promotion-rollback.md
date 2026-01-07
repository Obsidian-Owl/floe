# REQ-326 to REQ-340: Environment Promotion and Rollback

**Domain**: Artifact Distribution
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines multi-environment promotion workflows and rollback mechanisms. Promotion enables platform teams to validate artifacts in dev/staging before production.

**Key Principle**: Progressive promotion through environments with validation gates (ADR-0039)

## Requirements

### REQ-326: Multi-Environment Promotion Workflow **[New]**

**Requirement**: System MUST support promoting platform artifacts through environments (dev → staging → prod) with validation gates and approval workflows.

**Rationale**: Enables safe rollout of platform changes with progressive validation.

**Acceptance Criteria**:
- [ ] Environments defined: dev, staging, prod (customizable)
- [ ] Promotion flow: dev → staging → prod (unidirectional)
- [ ] Validation gates: tests, policy checks before promotion
- [ ] Approval workflow: human approval gates between environments
- [ ] Configuration: promotion rules, approval requirements
- [ ] Command: `floe platform promote <version> <from-env> → <to-env>`
- [ ] Promotion logging with audit trail
- [ ] Rollback capability after failed validation

**Enforcement**:
- Promotion workflow tests
- Validation gate tests
- Approval workflow tests
- Audit logging tests

**Constraints**:
- MUST enforce unidirectional promotion (dev → staging → prod)
- MUST validate before promoting
- MUST require approval for prod promotion
- FORBIDDEN to skip validation gates

**Configuration**:
```yaml
# manifest.yaml
environments:
  dev:
    registry: oci://dev-registry.example.com/floe
  staging:
    registry: oci://staging-registry.example.com/floe
    require_approval: true
  prod:
    registry: oci://prod-registry.example.com/floe
    require_approval: true
    approval_teams: [platform-leads, security]

promotion:
  path: dev → staging → prod
  validation_gates:
    - policy_compliance
    - integration_tests
    - security_scan
```

**Example Workflow**:
```bash
# 1. Develop in dev environment
$ floe platform publish v1.2.3-dev

# 2. Run tests and validation in staging
$ floe platform promote v1.2.3-dev staging
Validating...
  ✓ Policy compliance check passed
  ✓ Integration tests passed (integration/test_*. py)
  ✓ Security scan passed (no vulnerabilities)

# 3. Request approval for prod
$ floe platform promote v1.2.3-dev prod --request-approval
Approval request sent to: platform-leads@acme.com
Waiting for approval...

# 4. Approval granted, promote to prod
Approval granted by: engineering-lead@acme.com
Promoting to prod...
  ✓ Promoted to oci://prod-registry.example.com/floe-platform:v1.2.3
```

**Test Coverage**: `tests/integration/test_promotion_workflow.py`

**Traceability**:
- platform-artifacts.md
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-327: Environment-Specific Tags **[New]**

**Requirement**: System MUST tag artifacts with environment identifiers enabling environment-specific references and tracking.

**Rationale**: Enables clear identification of artifact promotion status.

**Acceptance Criteria**:
- [ ] Tag format: `<version>-<environment>`
- [ ] Examples: `v1.2.3-dev`, `v1.2.3-staging`, `v1.2.3-prod`
- [ ] Latest per environment: `latest-dev`, `latest-staging`, `latest-prod`
- [ ] Automatic tagging: on promotion
- [ ] Manual tagging: `floe platform tag <version> <env>`
- [ ] Tag query: `floe platform list --environment=prod`
- [ ] Tag immutability: per-environment tags follow immutability rules

**Enforcement**:
- Tag creation tests
- Tag immutability tests
- Query tests

**Constraints**:
- MUST use consistent tag format
- MUST tag on promotion
- FORBIDDEN to manually reassign environment tags

**Example Tags**:
```
oci://registry.example.com/floe-platform:v1.2.3         # Release
oci://registry.example.com/floe-platform:v1.2.3-prod    # Prod promotion
oci://registry.example.com/floe-platform:v1.2.3-staging # Staging promotion
oci://registry.example.com/floe-platform:v1.2.3-dev     # Dev version
oci://registry.example.com/floe-platform:latest-prod    # Latest prod
```

**Test Coverage**: `tests/unit/test_environment_tagging.py`

**Traceability**:
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-328: Validation Gates During Promotion **[New]**

**Requirement**: System MUST run configurable validation gates during promotion (policy compliance, integration tests, security scans) and prevent promotion on failures.

**Rationale**: Ensures only validated artifacts reach production.

**Acceptance Criteria**:
- [ ] Gate 1: Policy compliance check (governance policies)
- [ ] Gate 2: Integration tests (E2E pipeline tests)
- [ ] Gate 3: Security scan (vulnerability scanning)
- [ ] Gate 4: Performance baseline (optional)
- [ ] Gate 5: Cost analysis (optional)
- [ ] Configurable gates: teams choose which gates to enforce
- [ ] Clear pass/fail: green check or red X
- [ ] Failure messages: explain why gate failed
- [ ] Retry: fix issues and re-promote
- [ ] Override: emergency bypass (with audit log)

**Enforcement**:
- Gate execution tests
- Pass/fail determination tests
- Override audit logging

**Constraints**:
- MUST run all configured gates
- MUST fail on any gate failure
- MUST log gate results
- FORBIDDEN to skip gates

**Configuration**:
```yaml
# manifest.yaml
promotion:
  validation_gates:
    - name: policy_compliance
      enabled: true
      command: floe policy check
      timeout: 300s
    - name: integration_tests
      enabled: true
      command: make test-integration
      timeout: 600s
    - name: security_scan
      enabled: true
      command: cosign verify <artifact>
      timeout: 60s
    - name: performance_baseline
      enabled: false  # Optional
    - name: cost_analysis
      enabled: false  # Optional
```

**Example Gate Failure**:
```bash
$ floe platform promote v1.2.3-dev staging
Running validation gates...
  ✓ Policy compliance check (2s)
  ✗ Integration tests (timeout after 600s)
    Failure: Pipeline test timeout
    Output: tests/e2e/test_demo_flow.py timed out after 10 minutes
    Resolution: Check pipeline logs, optimize tests, retry
  ⏭ Security scan (skipped due to previous failure)

Promotion blocked: 1 gate failed
To override: floe platform promote --force v1.2.3-dev staging
```

**Test Coverage**: `tests/integration/test_validation_gates.py`

**Traceability**:
- platform-enforcement.md
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-329: Promotion Approval Workflow **[New]**

**Requirement**: System MUST implement approval workflow for environment promotion, supporting team-based approval and audit trail.

**Rationale**: Ensures proper change control and accountability.

**Acceptance Criteria**:
- [ ] Approval requirement: configurable per environment
- [ ] Approval teams: list of required approvers
- [ ] Approval request: sent to teams via email/Slack
- [ ] Approval status: pending, approved, denied
- [ ] Approver identity: who approved and when
- [ ] Audit trail: all approval decisions logged
- [ ] Timeout: request expires after N days (default 7)
- [ ] Command: `floe platform approve/deny <version> <env>`
- [ ] API integration: webhook for automated approval (policy-based)

**Enforcement**:
- Approval request tests
- Approver identity tests
- Audit logging tests
- Timeout tests

**Constraints**:
- MUST require approval before prod promotion
- MUST log approver identity
- FORBIDDEN to promote without approval
- MUST expire old requests

**Configuration**:
```yaml
# manifest.yaml
environments:
  prod:
    require_approval: true
    approval_teams:
      - platform-leads
      - security-team
    approval_timeout_days: 7
```

**Example Approval Workflow**:
```bash
# 1. Request approval
$ floe platform promote v1.2.3-dev prod --request-approval
Approval request sent to:
  - @platform-leads (Slack channel)
  - platform-leads@acme.com (Email)
Request ID: req-12345-67890
Expires: 2024-01-22 (7 days from now)

# 2. Approver reviews and approves
# (Via email link or Slack command)

# 3. Check approval status
$ floe platform approval status req-12345-67890
Status: approved
Approved by: engineering-lead@acme.com (2024-01-15 14:30:00Z)
Approved by: security-lead@acme.com (2024-01-15 14:35:00Z)

# 4. Proceed with promotion
$ floe platform promote v1.2.3-dev prod
Approval verified
Promoting to prod...
  ✓ Promoted to oci://prod-registry.example.com/floe-platform:v1.2.3
```

**Test Coverage**: `tests/integration/test_approval_workflow.py`

**Traceability**:
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-330: Promotion Audit Trail **[New]**

**Requirement**: System MUST maintain immutable audit trail of all promotion activities (request, validation, approval, execution) for compliance and troubleshooting.

**Rationale**: Enables compliance verification and security investigation.

**Acceptance Criteria**:
- [ ] Audit log entry for each promotion activity
- [ ] Logged events: request, validation gate result, approval decision, promotion start/end
- [ ] Structured logging (JSON)
- [ ] Immutable storage (append-only)
- [ ] Retention: configurable (default 2 years)
- [ ] Searchable: by artifact, environment, user
- [ ] Compliance export: audit trail export for reviews
- [ ] Real-time monitoring: alerts for suspicious activity

**Enforcement**:
- Audit logging tests
- Immutability tests
- Export functionality tests

**Constraints**:
- MUST log every promotion activity
- MUST include user identity
- MUST NOT modify logs after creation
- FORBIDDEN to delete logs

**Example Audit Entry**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "event": "promotion_requested",
  "artifact": "oci://registry.example.com/floe-platform:v1.2.3-dev",
  "from_env": "dev",
  "to_env": "staging",
  "user": "platform-engineer@acme.com",
  "request_id": "req-12345-67890"
}
```

**Test Coverage**: `tests/unit/test_promotion_audit_trail.py`

**Traceability**:
- security.md
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-331: Rollback Mechanism **[New]**

**Requirement**: System MUST support rolling back to previous artifact version when promotion fails or issues discovered in production.

**Rationale**: Enables rapid recovery from problematic deployments.

**Acceptance Criteria**:
- [ ] Rollback command: `floe platform rollback <version> <env> --to=<previous-version>`
- [ ] Version history: track all promoted versions
- [ ] Automatic rollback: trigger on validation failure
- [ ] Manual rollback: operator initiates rollback
- [ ] Rollback approval: may require approval
- [ ] Rollback validation: re-validate after rollback
- [ ] Clear rollback status: success or failure
- [ ] Rollback logging with timestamp and requester

**Enforcement**:
- Rollback command tests
- Version history tests
- Rollback approval tests
- Validation tests

**Constraints**:
- MUST support rollback to any previous version
- MUST validate after rollback
- FORBIDDEN to rollback without approval (if configured)
- MUST log rollback action

**Configuration**:
```yaml
# manifest.yaml
promotion:
  rollback:
    require_approval: true
    approval_teams: [platform-leads, incident-commander]
    auto_rollback_on_failure: false  # Manual only
```

**Example Rollback Workflow**:
```bash
# 1. Issue discovered in production
$ floe platform rollback v1.2.3-prod --to=v1.2.2

Initiating rollback...
  ✓ Validation gate: Policy compliance check (passed)
  ✓ Approval request sent to: platform-leads@acme.com

# 2. Approval granted
$ floe platform rollback v1.2.3-prod --to=v1.2.2 --approve

Approval verified
Rolling back...
  ✓ Rolled back to oci://prod-registry.example.com/floe-platform:v1.2.2

# 3. Verify rollback
$ floe platform status prod
Current: v1.2.2 (rolled back from v1.2.3)
Previous: v1.2.3 (failed, rolled back 2024-01-15 14:45:00Z)
```

**Test Coverage**: `tests/integration/test_rollback_mechanism.py`

**Traceability**:
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-332: Rollback Impact Analysis **[New]**

**Requirement**: System MUST perform impact analysis before rollback to identify affected data products and workloads.

**Rationale**: Enables informed decision-making before rolling back.

**Acceptance Criteria**:
- [ ] Impact query: which data products use the artifact
- [ ] Dependency analysis: what workloads would be affected
- [ ] Estimated downtime: how long rollback would take
- [ ] Data impact: whether data would be lost or reset
- [ ] Pre-rollback report: shows impact summary
- [ ] Rollback recommendation: safe to rollback? risks?
- [ ] Clear warnings: highlight critical impact

**Enforcement**:
- Impact analysis tests
- Dependency analysis tests
- Recommendation tests

**Constraints**:
- MUST perform impact analysis before rollback
- MUST warn about critical impacts
- FORBIDDEN to proceed with high-risk rollback without confirmation

**Example Impact Analysis**:
```bash
$ floe platform rollback v1.2.3-prod --to=v1.2.2 --analyze-impact

Impact Analysis: Rollback from v1.2.3-prod to v1.2.2-prod

Affected Data Products: 5
  1. customer-insights (5 pipelines, 100 GB storage)
  2. orders-analytics (3 pipelines, 50 GB storage)
  3. product-catalog (2 pipelines, 10 GB storage)
  4. inventory-levels (1 pipeline, 5 GB storage)
  5. fraud-detection (2 pipelines, 25 GB storage)

Workload Impact: 13 total pipelines
  ✓ Safe: 8 pipelines (no state dependencies)
  ⚠ Cautious: 5 pipelines (have state, will reset)

Estimated Downtime: 5-10 minutes
  - Platform artifact swap: <1 minute
  - Policy enforcement reload: 1-2 minutes
  - Pipeline restart: 4-8 minutes

Data Impact: Data loss risk: LOW
  - New tables created in v1.2.3: 2
  - These tables will be dropped on rollback
  - Existing data preserved

Rollback Risk: MEDIUM
  - Reason: 5 pipelines will reset state
  - Mitigation: Monitor pipeline execution after rollback

Recommendation: SAFE TO ROLLBACK
  - Pre-requisites: 1. Notify data teams, 2. Schedule maintenance window

Continue? (y/n): y
```

**Test Coverage**: `tests/integration/test_rollback_impact_analysis.py`

**Traceability**:
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-333: Version Pinning and Constraints **[New]**

**Requirement**: System MUST support version pinning and constraints enabling data teams to use specific artifact versions or version ranges.

**Rationale**: Enables version stability and controlled upgrades.

**Acceptance Criteria**:
- [ ] Exact pin: `v1.2.3` (immutable)
- [ ] Patch pin: `v1.2.*` (allow patch updates)
- [ ] Minor pin: `v1.*.*` (allow minor + patch)
- [ ] Latest: `latest` (mutable, always newest)
- [ ] Range: `>=v1.0.0,<v2.0.0`
- [ ] Prerelease: `v1.2.3-rc1`
- [ ] Configuration: pin in manifest.yaml or floe.yaml
- [ ] Update check: show available updates

**Enforcement**:
- Pin parsing tests
- Constraint validation tests
- Update checking tests

**Constraints**:
- MUST support semver syntax
- MUST validate constraints
- FORBIDDEN to use invalid versions

**Configuration**:
```yaml
# floe.yaml
platform:
  ref: oci://registry.example.com/floe-platform:v1.2.*  # Allow patch updates

# OR

platform:
  ref: oci://registry.example.com/floe-platform:v1.2.3  # Exact pin
```

**Example**:
```bash
# Check available updates
$ floe platform available-updates
Current: v1.2.3
Constraint: v1.2.*
Available updates:
  v1.2.4 (patch, 2024-01-20)
  v1.2.5 (patch, 2024-01-22) ← Latest patch
Recommended: upgrade to v1.2.5 (no breaking changes)

# Update to latest matching constraint
$ floe platform update
Updating from v1.2.3 to v1.2.5...
  ✓ Pulled v1.2.5
  ✓ Validated schema compatibility
  ✓ Updated floe.yaml
```

**Test Coverage**: `tests/unit/test_version_constraints.py`

**Traceability**:
- platform-artifacts.md lines 311-333
- pydantic-contracts.md (versioning)

---

### REQ-334: Artifact Retention Policy **[New]**

**Requirement**: System MUST implement retention policies for artifacts, automatically deleting old versions while protecting production-critical versions.

**Rationale**: Reduces storage costs and cleans up obsolete artifacts.

**Acceptance Criteria**:
- [ ] Protection rules: never delete latest X versions, protected tags
- [ ] Retention window: delete artifacts older than N days
- [ ] Tag-based protection: protect semver tags, release tags
- [ ] Automatic cleanup: scheduled job (daily/weekly)
- [ ] Manual cleanup: `floe platform gc --dry-run` (test) / `--apply` (execute)
- [ ] Cost savings report: how much space freed
- [ ] Before/after cleanup report
- [ ] Audit log: what was deleted and why

**Enforcement**:
- Retention policy tests
- Cleanup job tests
- Protection rule tests
- Audit logging tests

**Constraints**:
- MUST protect configured versions
- MUST NOT delete in-use artifacts
- FORBIDDEN to delete without warning
- MUST support dry-run mode

**Configuration**:
```yaml
# manifest.yaml
artifacts:
  retention:
    keep_last_versions: 10          # Keep latest 10 releases
    keep_duration_days: 90          # Keep last 90 days
    protected_tags:
      - "v*"                        # All semver tags
      - "release-*"                 # Release tags
    delete_schedule: daily          # Run daily at 2 AM
```

**Example Cleanup**:
```bash
$ floe platform gc --dry-run

Garbage Collection Plan (dry-run)
Total artifacts: 150
Can delete: 85 (not protected)
Will keep: 65 (protected or within retention window)

Space to be freed: 250 GB
Estimated cost savings: $22.50/month (at ECR rates)

Details:
  Delete v0.1.0-v0.5.0 (50 artifacts, 120 GB)
  Keep v0.6.0-v1.2.3 (65 artifacts, 130 GB, within 90 days)
  Keep latest 10: v1.2.3, v1.2.2, v1.2.1, ... v1.1.4

To apply: floe platform gc --apply
```

**Test Coverage**: `tests/integration/test_retention_policy.py`

**Traceability**:
- ADR-0040 (Artifact Immutability & GC)

---

### REQ-335: Promotion Status Dashboard **[New]**

**Requirement**: System MUST provide visibility into promotion status across environments via CLI and optional web UI.

**Rationale**: Enables teams to understand artifact promotion pipeline status.

**Acceptance Criteria**:
- [ ] Status command: `floe platform status --environment=all`
- [ ] Shows: current artifact per environment, promotion history
- [ ] Timeline: visual display of promotion flow through environments
- [ ] Health status: ✓ healthy, ⚠ warning, ✗ failed
- [ ] Last update: when was this environment last updated
- [ ] Pending approvals: what's waiting for approval
- [ ] JSON output: for dashboards/monitoring
- [ ] Optional web UI: browser-based status view

**Enforcement**:
- Status command tests
- Format tests
- Monitoring integration tests

**Constraints**:
- MUST show current status
- MUST include promotion history
- FORBIDDEN to show sensitive data
- MUST support programmatic output

**Example Status**:
```bash
$ floe platform status --environment=all

Promotion Status: floe-platform

dev
  Current: v1.2.4-dev
  Status: ✓ Healthy
  Updated: 2024-01-15 15:45:00Z
  History: v1.2.3-dev (yesterday), v1.2.2-dev (2 days ago)

staging
  Current: v1.2.3-staging
  Status: ✓ Healthy
  Updated: 2024-01-14 10:30:00Z
  Promoted from: dev v1.2.3-dev
  Pending approvals: None
  History: v1.2.2-staging (1 week ago), v1.2.1-staging (2 weeks ago)

prod
  Current: v1.2.2-prod
  Status: ⚠ Out-of-date
  Updated: 2024-01-10 09:00:00Z
  Latest available: v1.2.3
  Pending promotion: v1.2.3-staging → prod (approval required)
  Approvers: @platform-leads, @security-team
  History: v1.2.1-prod (1 month ago), v1.2.0-prod (2 months ago)
```

**Test Coverage**: `tests/integration/test_promotion_status_dashboard.py`

**Traceability**:
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-336: Conditional Promotion Based on Policy **[New]**

**Requirement**: System MUST support policy-based promotion rules enabling automatic promotion when criteria are met (e.g., all tests pass for N days).

**Rationale**: Enables faster feedback loops for non-production environments.

**Acceptance Criteria**:
- [ ] Policy definition: conditions for automatic promotion
- [ ] Conditions: all tests pass, no regressions, 7 days in staging
- [ ] Automatic action: promote without manual request
- [ ] Notification: teams notified of automatic promotion
- [ ] Opt-out: manual promotion still possible
- [ ] Dry-run: test policy before enabling
- [ ] Audit log: automatic promotions logged

**Enforcement**:
- Policy evaluation tests
- Automatic promotion tests
- Condition evaluation tests

**Constraints**:
- MUST evaluate conditions
- MUST NOT promote without conditions met
- FORBIDDEN to bypass approval for prod
- MUST log automatic promotions

**Configuration**:
```yaml
# manifest.yaml
promotion:
  policies:
    - name: auto-promote-staging-to-prod
      enabled: true
      from_env: staging
      to_env: prod
      conditions:
        - all_tests_pass: true
        - days_in_staging: 7
        - no_regressions: true
      approval: required  # Still require approval for prod
      notification: teams@acme.com
```

**Test Coverage**: `tests/unit/test_policy_based_promotion.py`

**Traceability**:
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-337: Cross-Registry Promotion **[New]**

**Requirement**: System MUST support promoting artifacts across multiple registries (e.g., from primary ECR to secondary Harbor for disaster recovery).

**Rationale**: Enables multi-region and DR scenarios.

**Acceptance Criteria**:
- [ ] Promotion between registries supported
- [ ] Registry configuration: primary, secondary, tertiary
- [ ] Artifact copy: replicate artifact to target registry
- [ ] Signature preservation: signatures copied as well
- [ ] Metadata preservation: all metadata replicated
- [ ] Verify integrity: digest verified after copy
- [ ] Status tracking: promotion status per registry

**Enforcement**:
- Cross-registry promotion tests
- Signature preservation tests
- Integrity verification tests

**Constraints**:
- MUST verify digest after copy
- MUST replicate signatures
- FORBIDDEN to modify artifacts during copy
- MUST preserve all metadata

**Example**:
```bash
$ floe platform promote v1.2.3 staging \
  --to-registries=primary,secondary

Promoting to staging across registries...
  ✓ Primary registry (ECR): pushed 8.6 KB
  ✓ Secondary registry (Harbor): pushed 8.6 KB
  ✓ Signatures: replicated to both registries
  ✓ Integrity: verified on both registries
```

**Test Coverage**: `tests/integration/test_cross_registry_promotion.py`

**Traceability**:
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-338: Promotion Dry-Run Mode **[New]**

**Requirement**: System MUST support dry-run mode for promotions, showing what would happen without actually promoting.

**Rationale**: Enables testing promotion workflow before actual execution.

**Acceptance Criteria**:
- [ ] Dry-run flag: `--dry-run` on promote command
- [ ] Shows: what would be validated, approved, promoted
- [ ] No side effects: actual promotion does not occur
- [ ] Complete output: matches actual execution
- [ ] Validation simulation: runs validation gates
- [ ] Cost estimation: estimated storage after promotion

**Enforcement**:
- Dry-run command tests
- No-side-effects tests
- Output comparison tests

**Constraints**:
- MUST NOT modify state in dry-run
- MUST show complete output
- FORBIDDEN to promote in dry-run mode

**Example**:
```bash
$ floe platform promote v1.2.3-dev staging --dry-run

DRY-RUN MODE: No changes will be made

Promotion Plan: v1.2.3-dev → staging

Validation Gates:
  [1/3] Policy compliance check
    Status: PASS (simulated)
    Duration: ~2s
  [2/3] Integration tests
    Status: PASS (simulated)
    Duration: ~600s
  [3/3] Security scan
    Status: PASS (simulated)
    Duration: ~60s

Promotion Steps:
  1. Request approval from: platform-leads@acme.com
     Status: PENDING (would be sent in actual run)
  2. Await approval timeout: 7 days
  3. Copy artifact to staging registry
     Artifact size: 8.6 KB
     Estimated time: 5s
  4. Tag artifact: v1.2.3-staging
  5. Run post-promotion validation
     Status: PASS (simulated)

Summary: Ready to promote (0 issues found)
To proceed: floe platform promote v1.2.3-dev staging
```

**Test Coverage**: `tests/unit/test_promotion_dry_run.py`

**Traceability**:
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-339: Promotion Notifications and Alerts **[New]**

**Requirement**: System MUST send notifications/alerts for promotion events (request, approval, completion, failure) via multiple channels (email, Slack, webhooks).

**Rationale**: Enables team visibility and quick response to issues.

**Acceptance Criteria**:
- [ ] Notification events: promotion-requested, approved, denied, started, succeeded, failed
- [ ] Channels: email, Slack, webhooks
- [ ] Customizable recipients: different per event/environment
- [ ] Rich content: includes artifact, environment, approvers, timeline
- [ ] Severity levels: info, warning, critical
- [ ] Muting: teams can opt-out of certain notifications

**Enforcement**:
- Notification sending tests
- Format tests
- Channel tests

**Constraints**:
- MUST send notifications
- MUST include actionable information
- FORBIDDEN to send sensitive details in notifications
- MUST respect muting preferences

**Configuration**:
```yaml
# manifest.yaml
notifications:
  channels:
    email:
      enabled: true
      smtp_server: smtp.example.com
      from: platform@acme.com
    slack:
      enabled: true
      webhook_url: https://hooks.slack.com/...
      channel: "#platform-deployments"
    webhooks:
      enabled: true
      url: https://webhook-receiver.example.com/promote

  events:
    promotion_requested:
      channels: [email, slack]
      recipients: [platform-leads@acme.com, "@platform-team"]
    promotion_approved:
      channels: [email, slack]
      recipients: [platform-engineer@acme.com]
    promotion_failed:
      channels: [email, slack]
      severity: critical
      recipients: [platform-leads@acme.com, "@incident-commander"]
```

**Example Notifications**:
```
# Slack message
Promotion Requested
Artifact: floe-platform v1.2.3-dev
From: dev
To: staging
Requester: @platform-engineer
Status: Awaiting approval
Approval needed from: @platform-leads, @security-team
Request ID: req-12345

[View Details] [Approve] [Deny]
```

**Test Coverage**: `tests/integration/test_promotion_notifications.py`

**Traceability**:
- ADR-0039 (Multi-Environment Promotion)

---

### REQ-340: Artifact Lifecycle and EOL Management **[New]**

**Requirement**: System MUST track artifact lifecycle (creation, promotion, in-use, deprecated, EOL) and notify teams of upcoming end-of-life dates.

**Rationale**: Enables planned deprecation and migration planning.

**Acceptance Criteria**:
- [ ] Lifecycle states: active, deprecated, eol
- [ ] EOL date: configurable per artifact
- [ ] Deprecation warning: shown when using deprecated artifact
- [ ] Migration path: suggested replacement artifact
- [ ] In-use tracking: which environments/teams use artifact
- [ ] EOL notification: reminder emails before EOL date
- [ ] Support window: how long artifact is supported
- [ ] Forced upgrade: block EOL artifacts from being used (optional)

**Enforcement**:
- Lifecycle state tests
- Deprecation warning tests
- EOL notification tests
- In-use tracking tests

**Constraints**:
- MUST track lifecycle
- MUST warn about deprecated artifacts
- FORBIDDEN to allow EOL artifacts without warning
- MUST provide migration path

**Configuration**:
```yaml
# manifest.yaml
artifacts:
  lifecycle:
    v1.0.0:
      status: eol
      eol_date: 2023-12-31
      deprecation_date: 2023-06-30
      replacement: v1.1.0
      support_window: 12 months
```

**Example Lifecycle Tracking**:
```bash
$ floe platform lifecycle v1.2.3

Artifact: floe-platform v1.2.3
Status: active
Created: 2024-01-15
Estimated EOL: 2025-01-15 (1 year support)
Deprecation date: 2024-12-15 (2 months before EOL)

In-use:
  Environments: prod (customer-insights, orders-analytics)
  Teams: 3 data teams
  Workloads: 5 data products, 13 pipelines

Upcoming milestones:
  2024-12-15: Deprecation date (warnings begin)
  2025-01-15: End-of-life (no longer supported)

Recommended action: Plan upgrade to v1.3.0 before EOL
```

**Test Coverage**: `tests/unit/test_artifact_lifecycle.py`

**Traceability**:
- ADR-0040 (Artifact Immutability & GC)

---

## Domain Acceptance Criteria

Environment Promotion and Rollback (REQ-326 to REQ-340) is complete when:

- [ ] All 15 requirements have complete template fields
- [ ] Multi-environment promotion workflow implemented
- [ ] Environment-specific tags working
- [ ] Validation gates enforced
- [ ] Approval workflow tested
- [ ] Rollback mechanism functional
- [ ] Impact analysis implemented
- [ ] Audit trail complete
- [ ] Retention policy enforced
- [ ] Status dashboard working
- [ ] Policy-based promotion tested
- [ ] Cross-registry promotion tested
- [ ] Notifications/alerts working
- [ ] Dry-run mode functioning
- [ ] All promotion/rollback tests pass (>80% coverage)
- [ ] Documentation updated
- [ ] ADRs backreference requirements

## Epic Mapping

These requirements are satisfied across epics:
- **Epic 6: OCI Registry** Phase 4C (REQ-326 to REQ-340 planning)
- **Epic 7: Enforcement Engine** Phase 5A-5B (REQ-326 to REQ-340 implementation)

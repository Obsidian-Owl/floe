# ADR-0039: Multi-Environment Artifact Promotion

## Status

Accepted

## Context

Platform artifacts (manifest.yaml + policies) need to progress through environments with validation gates and approval workflows:

```
dev → staging → production
```

### Requirements from EPIC-06

- **REQ-326**: Multi-environment promotion workflow
- **REQ-327**: Environment-specific tagging strategy
- **REQ-328**: Validation gates during promotion
- **REQ-329**: Approval workflow (team-based, configurable)
- **REQ-330**: Promotion audit trail (immutable log)
- **REQ-331**: Rollback mechanism
- **REQ-332**: Rollback impact analysis
- **REQ-333**: Version pinning and constraints
- **REQ-335**: Promotion status dashboard
- **REQ-336**: Policy-based promotion (auto-promote when criteria met)
- **REQ-337**: Cross-registry promotion (multi-region, DR)
- **REQ-338**: Promotion dry-run mode
- **REQ-339**: Promotion notifications

### Current Challenges

- No standardized promotion workflow
- Manual artifact copying between environments
- No validation gates before production
- No audit trail of what was promoted when
- Difficult to rollback problematic versions
- No impact analysis before rollback

### Industry Context (2025)

GitOps has become the standard delivery model with stronger integrations for policy, security, and cost governance. Industry best practices from 2025 research:

1. **Artifacts built once, promoted everywhere** - Same digest across all environments
2. **GitOps-based promotion** - PR-based workflows for audit trails
3. **Validation gates** - Policy compliance, security scans, tests before promotion
4. **Hybrid approval** - Automated for dev/staging, manual for production
5. **Policy-as-code** - All promotion rules codified and versioned

**Sources:**
- [GitOps Best Practices 2025](https://akuity.io/blog/gitops-best-practices-whitepaper)
- [Continuous Deployment Best Practices 2025](https://moss.sh/deployment/continuous-deployment-best-practices-2025/)
- [GitOps Environment Promotion Guide](https://octopus.com/devops/gitops/gitops-environments/)

## Decision

Adopt **GitOps-based promotion workflow** with configurable validation gates and flexible approval models.

### Architecture Principles

1. **Artifacts are immutable** - Same OCI artifact digest promoted across environments
2. **Promotion is unidirectional** - dev → staging → prod (no backward promotion)
3. **Validation gates are configurable** - Platform teams define requirements per environment
4. **Approval workflows are external** - floe validates and tags, CI/CD handles approvals
5. **Audit trail is complete** - Every promotion logged with who, what, when, why

### Environment Tagging Strategy

**Tag Format:** `<version>-<environment>`

```
Immutable tags (never change):
- v1.2.3-dev         # Promoted to dev
- v1.2.3-staging     # Promoted to staging
- v1.2.3-prod        # Promoted to production

Mutable tags (updated on promotion):
- latest-dev         # Current dev version
- latest-staging     # Current staging version
- latest-prod        # Current production version
```

**Promotion Flow:**
```bash
# Step 1: Build and push to dev
floe platform publish --version=v1.2.3
# Creates: v1.2.3-dev, updates latest-dev

# Step 2: Promote to staging (after validation)
floe platform promote v1.2.3 --from=dev --to=staging
# Creates: v1.2.3-staging, updates latest-staging

# Step 3: Promote to production (after approval)
floe platform promote v1.2.3 --from=staging --to=prod
# Creates: v1.2.3-prod, updates latest-prod
```

### Validation Gates

**Configurable per environment in manifest.yaml:**

```yaml
# manifest.yaml
artifacts:
  promotion:
    gates:
      dev:
        policy_compliance: true     # MANDATORY
        tests: false                # Optional
        security_scan: false        # Optional

      staging:
        policy_compliance: true     # MANDATORY
        tests: true                 # Run integration tests
        security_scan: true         # CVE scan + cosign verify
        cost_analysis: false        # Optional

      production:
        policy_compliance: true     # MANDATORY
        tests: true                 # Full test suite
        security_scan: true         # CVE scan + cosign verify
        cost_analysis: true         # Estimate infrastructure cost
        performance_baseline: true  # Compare against SLO
```

**Validation Gate Implementations:**

| Gate | Implementation | Exit Code on Fail |
|------|----------------|-------------------|
| **policy_compliance** | `floe platform validate --strict` | 1 |
| **tests** | User-provided test command | 1 |
| **security_scan** | `cosign verify` + `trivy scan` | 1 |
| **cost_analysis** | Infracost estimate | Warn only (0) |
| **performance_baseline** | User-provided benchmark | Warn only (0) |

### Approval Workflow Integration

**floe does NOT manage approvals** - delegates to CI/CD:

```yaml
# .github/workflows/promote-to-production.yml
name: Promote to Production

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to promote'
        required: true

jobs:
  promote:
    runs-on: ubuntu-latest
    environment: production  # GitHub environment protection rules

    steps:
      - name: Run validation gates
        run: floe platform promote ${{ inputs.version }} --to=prod --dry-run

      # GitHub requires manual approval here (configured in repo settings)

      - name: Execute promotion
        run: floe platform promote ${{ inputs.version }} --from=staging --to=prod
```

**Recommended Approval Patterns:**
- **GitOps PR-based**: Create PR to update production environment config, require approvals
- **CI/CD environments**: GitHub Environments, GitLab Environments with protection rules
- **External tools**: Integrate with PagerDuty, OpsGenie for on-call approval

### Rollback Mechanism

**REQ-331: Rollback to previous version**

```bash
# Check current production version
floe platform status --env=production
# Output: v1.2.3-prod (deployed 2024-01-15 14:30:00)

# Analyze rollback impact
floe platform rollback v1.2.2 --env=production --dry-run
# Output:
#   Affected data products: 12
#   Breaking changes: 2 (quality gate threshold increased)
#   Estimated downtime: 2 minutes (re-deploy jobs)
#   Recommendation: SAFE to rollback

# Execute rollback
floe platform rollback v1.2.2 --env=production
# Creates: v1.2.2-prod-rollback, updates latest-prod
```

**Rollback Impact Analysis (REQ-332):**
- Compare schema versions (detect breaking changes)
- List affected data products
- Estimate deployment time
- Check policy compatibility
- Provide recommendation (SAFE, RISKY, BLOCKED)

### Version Pinning Strategies

**REQ-333: Data products pin to platform versions**

```yaml
# floe.yaml (data product)
platform:
  version: ">=1.2.0, <2.0.0"  # Semver range (recommended)
  # OR
  version: "1.2.3"             # Exact pin (strict)
  # OR
  version: "^1.2.0"            # Caret range (patch updates)
  # OR
  version: "latest-prod"       # Mutable tag (not recommended)
```

**Version Resolution:**
- Exact pins checked first
- Semver ranges validated against available versions
- Mutable tags resolved at runtime (with warning)

### Cross-Registry Promotion

**REQ-337: Multi-region and DR scenarios**

```yaml
# manifest.yaml
artifacts:
  registry:
    primary:
      type: harbor
      url: harbor-us-east.acme.com
    secondary:
      type: ecr
      url: 123456789.dkr.ecr.us-west-2.amazonaws.com
    tertiary:
      type: acr
      url: acmedata.azurecr.io

  promotion:
    cross_registry_sync: true  # Sync artifacts to all registries
    verification: digest_match  # Ensure same digest across registries
```

**Promotion with Multi-Registry:**
```bash
floe platform promote v1.2.3 --to=prod --sync-registries
# Promotes to production in ALL configured registries
# Verifies digest matches across all registries
```

### Audit Trail

**REQ-330: Immutable promotion log**

Every promotion creates audit record:
```json
{
  "promotion_id": "prom-123456",
  "artifact": {
    "version": "v1.2.3",
    "digest": "sha256:abc123..."
  },
  "source_env": "staging",
  "target_env": "production",
  "timestamp": "2024-01-15T14:30:00Z",
  "promoted_by": "user@acme.com",
  "approval": {
    "required": true,
    "approvers": ["manager@acme.com"],
    "approval_timestamp": "2024-01-15T14:25:00Z"
  },
  "validation_gates": {
    "policy_compliance": "PASSED",
    "tests": "PASSED",
    "security_scan": "PASSED",
    "cost_analysis": "PASSED"
  },
  "result": "SUCCESS"
}
```

Stored in:
- OCI registry as annotation
- OpenTelemetry traces (searchable)
- Audit log file (append-only)

### Promotion Status Dashboard

**REQ-335: CLI + web UI visibility**

```bash
floe platform promote status

Environment  Version      Promoted At           Promoted By        Gates
-----------  -----------  --------------------  -----------------  ------
dev          v1.2.4-dev   2024-01-15 15:00:00  ci-bot@acme.com    ✓✓✗✗
staging      v1.2.3-stg   2024-01-15 14:45:00  alice@acme.com     ✓✓✓✓
production   v1.2.3-prod  2024-01-15 14:30:00  bob@acme.com       ✓✓✓✓

Pending Promotions:
- v1.2.4-dev → staging (blocked: security scan failed)
```

## Consequences

### Positive

- **Predictable promotions** - Same artifact (digest) across all environments
- **Audit compliance** - Complete trail of who promoted what when
- **Safety gates** - Catch issues before production (policy, security, tests)
- **Flexible approval** - Platform teams choose approval model (GitOps PR, CI/CD, manual)
- **Multi-registry support** - DR and multi-region via cross-registry sync
- **Rollback safety** - Impact analysis before rollback
- **GitOps aligned** - Industry standard workflow (2025)

### Negative

- **Complexity** - More moving parts than manual copying
- **Validation time** - Gates add latency to promotion
- **External dependency** - Requires CI/CD integration for approvals
- **Cross-registry cost** - Bandwidth for multi-registry sync

### Neutral

- Promotion is unidirectional (prevents accidental downgrades)
- Validation gates configurable (teams choose safety vs speed)
- Approval workflow external (floe validates, CI/CD approves)

## Implementation

### CLI Commands

```bash
# Promote artifact
floe platform promote <version> --from=<env> --to=<env> [--dry-run]

# Rollback to previous version
floe platform rollback <version> --env=<env> [--dry-run]

# Check promotion status
floe platform promote status [--env=<env>]

# List available versions
floe platform list --env=<env>
```

### Configuration Schema

```yaml
# manifest.yaml
artifacts:
  promotion:
    gates:  # Per-environment validation gates
      <environment>:
        policy_compliance: bool
        tests: bool
        security_scan: bool
        cost_analysis: bool
        performance_baseline: bool

    notifications:
      slack:
        webhook: ${SLACK_WEBHOOK}
        channels: ["#platform-ops"]
      email:
        recipients: ["ops@acme.com"]

    cross_registry_sync: bool
    verification: digest_match | signature_match
```

## References

- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md) - OCI registry decision
- [ADR-0040: Artifact Immutability & GC](0040-artifact-immutability-gc.md) - Tag immutability
- [EPIC-06: OCI Artifact System](../../plan/epics/EPIC-06.md) - Implementation epic
- [REQ-326 to REQ-340](../../plan/requirements/04-artifact-distribution/03-promotion-rollback.md) - Promotion requirements
- **Industry Sources:**
  - [GitOps Best Practices 2025 (Akuity)](https://akuity.io/blog/gitops-best-practices-whitepaper)
  - [Continuous Deployment Best Practices (MOSS)](https://moss.sh/deployment/continuous-deployment-best-practices-2025/)
  - [GitOps Environment Promotion (Octopus)](https://octopus.com/devops/gitops/gitops-environments/)

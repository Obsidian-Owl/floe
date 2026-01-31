# Quickstart: Epic 8C - Promotion Lifecycle

**Date**: 2026-01-30
**Epic**: 8C (Promotion Lifecycle)

## Prerequisites

- Epic 8A (OCI Client) - Complete
- Epic 8B (Artifact Signing) - Complete
- Epic 3B (PolicyEnforcer) - Complete
- OCI Registry with immutable tag support (Harbor, ECR, ACR)

## Getting Started

### 1. Configure Environments in manifest.yaml

```yaml
# manifest.yaml
artifacts:
  registry:
    uri: oci://harbor.example.com/floe-platform
    auth:
      type: aws-irsa
    signing:
      mode: keyless
      oidc_issuer: https://token.actions.githubusercontent.com
    verification:
      enabled: true
      enforcement: enforce
      trusted_issuers:
        - issuer: https://token.actions.githubusercontent.com
          subject_regex: "^repo:acme/floe-platform:.*$"

  promotion:
    environments:
      - name: dev
        gates:
          policy_compliance: true
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
      backend: oci
```

### 2. Publish Initial Artifact

```bash
# Compile and publish to dev
floe platform compile --spec floe.yaml --manifest manifest.yaml
floe artifact push -a target/compiled_artifacts.json -r oci://harbor.example.com/floe-platform -t v1.0.0

# Sign the artifact
floe artifact sign -r oci://harbor.example.com/floe-platform -t v1.0.0

# Promote to dev (first environment)
floe platform promote v1.0.0 --from=none --to=dev
```

### 3. Promote Through Environments

```bash
# Check current status
floe platform status

# Output:
# Environment   Version     Digest          Promoted By        At
# ───────────────────────────────────────────────────────────────
# dev           v1.0.0      sha256:abc...   ci@github.com      2026-01-15 10:30
# staging       -           -               -                  -
# prod          -           -               -                  -

# Dry-run to preview staging promotion
floe platform promote v1.0.0 --from=dev --to=staging --dry-run

# Output:
# [DRY RUN] Would promote v1.0.0 from dev to staging
# Gates to validate:
#   - policy_compliance: required
#   - tests: required
#   - security_scan: required
# Signature status: valid
# Estimated time: ~60s

# Execute promotion
floe platform promote v1.0.0 --from=dev --to=staging

# Output:
# Promoted v1.0.0 from dev to staging
# New tag: v1.0.0-staging
# Latest tag updated: latest-staging
# Gates passed: 3/3
# Signature: verified (keyless, GitHub Actions)
# Trace ID: abc123def456  # Link to observability dashboard
```

### 4. Rollback if Needed

```bash
# Preview rollback impact
floe platform rollback v0.9.0 --env=staging --dry-run

# Output:
# [DRY RUN] Would rollback staging to v0.9.0
#
# Impact Analysis:
# - Breaking changes: 1
#   - Removed field: config.new_feature
# - Affected products: 2
#   - analytics-pipeline
#   - reporting-dashboard
# - Recommendations:
#   - Notify downstream teams before rollback

# Execute rollback with reason
floe platform rollback v0.9.0 --env=staging --reason="Performance regression"

# Output:
# Rolled back staging to v0.9.0
# Previous version: v1.0.0
# Latest tag updated: latest-staging -> v0.9.0
# Reason: "Performance regression"
```

### 5. View Promotion History

```bash
# Full history for production
floe platform status --env=prod --history=5

# Output:
# Environment: prod
# Current: v1.0.0 (sha256:abc...)
#
# History:
#   2026-01-16 09:00  PROMOTED   v1.0.0  platform@acme.com
#   2026-01-15 14:30  ROLLBACK   v0.9.0  platform@acme.com  "Performance fix"
#   2026-01-15 09:00  PROMOTED   v1.0.0  platform@acme.com
#   2026-01-14 16:00  PROMOTED   v0.9.0  ci@github.com
#   2026-01-13 11:00  PROMOTED   v0.8.0  ci@github.com

# JSON output for scripting
floe platform status --format=json | jq '.[] | select(.environment == "prod")'
```

## Common Patterns

### CI/CD Integration

```yaml
# GitHub Actions example
jobs:
  promote-to-staging:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Promote to Staging
        run: |
          floe platform promote ${{ github.event.inputs.version }} \
            --from=dev \
            --to=staging

  promote-to-prod:
    runs-on: ubuntu-latest
    environment: production  # Requires approval
    steps:
      - uses: actions/checkout@v4

      - name: Promote to Production
        run: |
          floe platform promote ${{ github.event.inputs.version }} \
            --from=staging \
            --to=prod
```

### Custom Gate Configuration

```yaml
# manifest.yaml - External gate commands
artifacts:
  promotion:
    gate_commands:
      tests:
        command: "pytest tests/ --tb=short"
        timeout_seconds: 300
      security_scan:
        command: "trivy image ${ARTIFACT_REF}"
        timeout_seconds: 600
      cost_analysis:
        command: "./scripts/cost-check.sh ${ARTIFACT_DIGEST}"
        timeout_seconds: 60
      performance_baseline:
        command: "./scripts/perf-check.sh ${ARTIFACT_TAG}"
        timeout_seconds: 120
```

### Multi-Registry Sync

```yaml
# manifest.yaml - Cross-registry sync for DR
artifacts:
  registries:
    primary:
      uri: oci://harbor.us-east.example.com/floe
      auth:
        type: aws-irsa
    secondary:
      uri: oci://harbor.eu-west.example.com/floe
      auth:
        type: aws-irsa

  promotion:
    sync_to_secondary: true  # Sync on promotion
```

### Environment Lock/Freeze (SRE Pattern)

```bash
# Lock production during incident
floe platform lock --env=prod --reason="Incident #123 - Database migration"

# Output:
# Environment 'prod' is now locked
# Locked by: sre@acme.com
# Reason: Incident #123 - Database migration
# To unlock: floe platform unlock --env=prod --reason="<resolution>"

# Attempt promotion to locked environment (fails)
floe platform promote v1.1.0 --from=staging --to=prod

# ERROR: Environment 'prod' is locked
# Reason: Incident #123 - Database migration
# Locked by: sre@acme.com at 2026-01-15 10:30
# Unlock first: floe platform unlock --env=prod --reason="<resolution>"

# Unlock after incident resolution
floe platform unlock --env=prod --reason="Incident #123 resolved - migration complete"

# Output:
# Environment 'prod' is now unlocked
# Unlock reason: Incident #123 resolved - migration complete
```

### CI/CD JSON Output

```bash
# Get structured JSON for pipeline parsing
floe platform promote v1.0.0 --from=dev --to=staging --output=json

# Output:
# {
#   "success": true,
#   "promotion_id": "550e8400-e29b-41d4-a716-446655440000",
#   "artifact_digest": "sha256:abc123...",
#   "artifact_tag": "v1.0.0",
#   "source_environment": "dev",
#   "target_environment": "staging",
#   "gate_results": [
#     {"gate": "policy_compliance", "status": "passed", "duration_ms": 1234},
#     {"gate": "tests", "status": "passed", "duration_ms": 45000},
#     {"gate": "security_scan", "status": "warning", "duration_ms": 120000}
#   ],
#   "trace_id": "abc123def456",
#   "promoted_at": "2026-01-15T14:45:00Z"
# }

# Check exit codes in scripts
floe platform promote v1.0.0 --from=dev --to=staging --output=json
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
  echo "Promotion succeeded"
elif [ $EXIT_CODE -eq 8 ]; then
  echo "Gate failure"
elif [ $EXIT_CODE -eq 12 ]; then
  echo "Authorization failed"
elif [ $EXIT_CODE -eq 13 ]; then
  echo "Environment locked"
fi
```

### Authorization and Access Control

```yaml
# manifest.yaml - Environment-specific authorization
artifacts:
  promotion:
    environments:
      - name: dev
        gates:
          policy_compliance: true
        # No authorization - anyone can promote to dev

      - name: staging
        gates:
          policy_compliance: true
          tests: true
        authorization:
          allowed_groups: [developers, platform-team]

      - name: prod
        gates:
          policy_compliance: true
          tests: true
          security_scan:
            command: "trivy image ${ARTIFACT_REF} --format json"
            block_on_severity: [CRITICAL, HIGH]
            ignore_unfixed: true
        authorization:
          allowed_groups: [platform-admins, release-managers]
          separation_of_duties: true  # SOX/SOC2 compliance
```

```bash
# Unauthorized promotion attempt
floe platform promote v1.0.0 --from=staging --to=prod

# ERROR: Authorization failed
# Operator 'dev@acme.com' is not authorized to promote to 'prod'
# Required groups: [platform-admins, release-managers]
# Your groups: [developers]
# Exit code: 12

# Separation of duties violation
floe platform promote v1.0.0 --from=staging --to=prod

# ERROR: Separation of duties violation
# Operator 'platform@acme.com' promoted this artifact to staging
# A different operator must promote to prod
# Exit code: 12
```

### Webhook Notifications

```yaml
# manifest.yaml - Configure webhook notifications
artifacts:
  promotion:
    webhooks:
      - url: https://hooks.slack.com/services/T00/B00/XXX
        events: [promote, rollback]
      - url: https://api.pagerduty.com/webhooks
        events: [rollback]
        headers:
          Authorization: Token ${PAGERDUTY_TOKEN}
```

### Security Gate Configuration

```yaml
# manifest.yaml - Security gate with severity thresholds
artifacts:
  promotion:
    environments:
      - name: prod
        gates:
          security_scan:
            command: "trivy image ${ARTIFACT_REF} --format json"
            block_on_severity: [CRITICAL, HIGH]
            ignore_unfixed: true
            timeout_seconds: 600
```

```bash
# Promotion with security gate details
floe platform promote v1.0.0 --from=staging --to=prod

# ERROR: Gate 'security_scan' failed
# Blocking vulnerabilities found:
#   - CVE-2024-1234 (HIGH): libssl 1.1.1 - Remote code execution
#   - CVE-2024-5678 (CRITICAL): curl 7.88 - Buffer overflow
#
# Total vulnerabilities: 15
#   CRITICAL: 1
#   HIGH: 1
#   MEDIUM: 8 (not blocking)
#   LOW: 5 (not blocking)
#
# Ignored (unfixed): 3
#
# Fix blocking vulnerabilities and retry.
```

## Troubleshooting

### Gate Failures

```bash
# Get detailed gate failure info
floe platform promote v1.0.0 --from=dev --to=staging 2>&1

# ERROR: Gate 'tests' failed
# Command: pytest tests/ --tb=short
# Exit code: 1
# Output:
#   FAILED tests/test_api.py::test_endpoint - AssertionError
#   FAILED tests/test_config.py::test_validation - ValueError
#
# Fix tests and retry promotion.
```

### Signature Verification Failures

```bash
# Check signature status
floe artifact verify -r oci://harbor.example.com/floe -t v1.0.0

# If unsigned:
floe artifact sign -r oci://harbor.example.com/floe -t v1.0.0
```

### Invalid Environment Transition

```bash
# ERROR: Cannot promote from 'dev' to 'prod'
# Reason: Must promote through intermediate environments
# Required path: dev -> staging -> prod

# Promote to staging first
floe platform promote v1.0.0 --from=dev --to=staging
floe platform promote v1.0.0 --from=staging --to=prod
```

## Next Steps

- [Full Specification](./spec.md)
- [Data Model](./data-model.md)
- [API Contract](./contracts/promotion-api.yaml)
- [ADR-0042: Environment Model](../../docs/architecture/adr/ADR-0042-environment-model.md)

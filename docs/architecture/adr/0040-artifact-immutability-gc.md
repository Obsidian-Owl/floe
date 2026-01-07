# ADR-0040: Artifact Immutability and Garbage Collection

## Status

Accepted

## Context

OCI artifacts in floe represent immutable platform configurations. Once published, these artifacts must:
- Never change (immutability guarantee)
- Be safely cleaned up when no longer needed (garbage collection)
- Protect critical versions from deletion (retention policies)

### Requirements from EPIC-06

- **REQ-313**: Artifact immutability enforcement
- **REQ-334**: Artifact retention policy
- **REQ-340**: Artifact lifecycle and EOL management

### Current Challenges

- No automated cleanup of old artifacts (storage costs grow unbounded)
- Risk of deleting in-use artifacts
- No protection for critical versions (production, latest releases)
- Manual cleanup is error-prone
- No cost visibility for artifact storage

### Industry Context (2025)

Based on 2025 research into container registry best practices:

**Tag Immutability:**
- Major cloud providers (AWS ECR, Azure ACR, GCP GAR) support registry-native tag immutability
- Harbor (CNCF graduated) offers rules to control tag immutability
- GitHub Container Registry, JFrog Artifactory, Sonatype Nexus lack native immutability (as of 2025)
- Best practice: Use unique, predictable tags (semver, calver, datetime) rather than mutable tags like "latest"

**Garbage Collection:**
- Industry standard retention: 10 versions or 90 days (conservative)
- Kubernetes defaults: imageGCHighThresholdPercent=85%, imageGCLowThresholdPercent=80%
- Registry policies: typically 7-365 days retention configurable
- Best practice: Lifecycle policies in CI/CD workflows, not manual cleanup

**Sources:**
- [ECR Repository Tag Immutability](https://cloud-kb.sentinelone.com/ecr-repository-tag-immutability)
- [Immutable Container Image Tags](https://www.proactiveops.io/archive/immutable-container-image-tags/)
- [Kubernetes Garbage Collection Best Practices](https://www.groundcover.com/learn/storage/kubernetes-garbage-collection)
- [Azure Container Registry Retention Policy](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-retention-policy)

## Decision

Adopt **registry-native tag immutability** with **configurable garbage collection** and **lifecycle management**.

### Architecture Principles

1. **Semver tags are immutable** - Once `v1.2.3` is published, it can never be reassigned
2. **Mutable tags allowed** - `latest-dev`, `latest-staging`, `latest-prod` can be updated
3. **Registry-native enforcement** - Prefer registries with native immutability (Harbor, ECR, ACR, GAR)
4. **Automatic garbage collection** - Scheduled cleanup based on retention policies
5. **Protected versions** - Never delete production, latest N versions, or tagged releases

### Tag Immutability Enforcement

**Registry Support Matrix:**

| Registry | Native Immutability | Recommended For | Notes |
|----------|---------------------|-----------------|-------|
| **Harbor** | ✅ Yes | OSS default, air-gapped | CNCF graduated, full feature set |
| **AWS ECR** | ✅ Yes | AWS deployments | Managed, integrates with IRSA |
| **Azure ACR** | ✅ Yes | Azure deployments | Managed, integrates with MI |
| **GCP Artifact Registry** | ✅ Yes | GCP deployments | Managed, integrates with WI |
| **GitHub Container Registry** | ❌ No | Open source projects | Public/private, PAT auth |
| **JFrog Artifactory** | ❌ No | Enterprise (commercial) | Not recommended without immutability |
| **Sonatype Nexus** | ❌ No | Enterprise (commercial) | Not recommended without immutability |

**Platform Requirement:**

```yaml
# platform-manifest.yaml
artifacts:
  registry:
    type: harbor  # MUST be: harbor | ecr | acr | gar
    # GitHub CR, JFrog, Nexus NOT supported for production (lack immutability)

    immutability:
      enforcement: registry_native  # Require registry-level immutability
      semver_tags: immutable        # v1.2.3, v2.0.0-beta.1 are immutable
      environment_tags: immutable   # v1.2.3-dev, v1.2.3-prod are immutable
      latest_tags: mutable          # latest-dev, latest-staging, latest-prod can be updated
```

**Immutability Enforcement:**

When tag immutability is enforced (registry-level):
- ✅ Can push `v1.2.3` first time
- ❌ Cannot push `v1.2.3` again (even if same digest)
- ❌ Cannot delete `v1.2.3` manifest
- ❌ Cannot delete blobs referenced by `v1.2.3`
- ❌ Cannot remove tag from manifest
- ✅ Can update `latest-dev` tag (mutable tags allowed)

**Client-Side Validation (Safety Net):**

Even with registry-native enforcement, floe validates before push:

```python
# floe-core/src/floe_core/oci/client.py
def push_artifact(version: str, environment: str) -> None:
    """Push artifact with immutability validation."""
    tag = f"{version}-{environment}"

    # Check if tag already exists
    if self.tag_exists(tag):
        # Check immutability rule
        if self._is_immutable_tag(tag):
            raise ImmutabilityViolation(
                f"Tag {tag} is immutable and already exists. "
                f"Cannot overwrite semver or environment-specific tags."
            )

    # Proceed with push
    self.oras_client.push(target=tag, files=artifacts)
```

### Garbage Collection Strategy

**REQ-334: Retention Policy Configuration**

**Default Policy (Conservative):**
```yaml
# platform-manifest.yaml
artifacts:
  retention:
    keep_last_versions: 10          # Latest 10 releases (user-selected: conservative)
    keep_duration_days: 90          # Last 90 days (user-selected: conservative)

    protected_tags:
      - "v*"                        # All semver tags (v1.2.3)
      - "release-*"                 # Release tags
      - "*-prod"                    # All production tags
      - "latest-*"                  # Latest per environment

    delete_schedule:
      frequency: daily              # Run GC daily
      time: "02:00"                 # 2 AM UTC
      timezone: UTC

    dry_run: false                  # Set true to audit without deletion
```

**Retention Policy Tiers (Examples):**

| Tier | keep_last_versions | keep_duration_days | Use Case |
|------|-------------------|-------------------|----------|
| **Conservative** | 10 | 90 | Mission-critical, regulated environments |
| **Balanced** | 5 | 30 | Standard production environments |
| **Aggressive** | 3 | 14 | Fast-iterating dev/staging only |

Platform teams choose tier via configuration.

**Garbage Collection Algorithm:**

```python
# Simplified GC algorithm
def garbage_collect(policy: RetentionPolicy) -> GCResult:
    """Run garbage collection based on retention policy."""
    artifacts = list_all_artifacts()

    # Step 1: Apply protection rules (never delete)
    protected = apply_protection_rules(artifacts, policy.protected_tags)

    # Step 2: Keep last N versions
    candidates = artifacts - protected
    sorted_versions = sort_by_version(candidates)
    keep_by_count = sorted_versions[:policy.keep_last_versions]

    # Step 3: Keep artifacts within duration
    cutoff_date = now() - policy.keep_duration_days
    keep_by_date = [a for a in candidates if a.created > cutoff_date]

    # Step 4: Combine protection rules
    keep = protected | keep_by_count | keep_by_date
    delete = artifacts - keep

    # Step 5: Safety checks before deletion
    for artifact in delete:
        if is_referenced_by_data_products(artifact):
            log.warning(f"Skipping {artifact}: still referenced")
            delete.remove(artifact)

    return GCResult(kept=keep, deleted=delete)
```

**Cost Optimization Reporting:**

```bash
floe platform gc --dry-run --report
# Output:
Retention Policy Analysis
─────────────────────────────────────────────────────
Total artifacts: 45
Protected (keep):
  - Latest 10 versions: 10 artifacts
  - Within 90 days: 12 artifacts
  - Protected tags (v*, *-prod): 8 artifacts
  - Total protected: 18 artifacts (overlap removed)

Candidates for deletion: 27 artifacts
  - Storage: 2.4 GB
  - Est. monthly cost: $0.06/GB = $0.14/month

After GC:
  - Remaining storage: 1.1 GB
  - Est. monthly cost: $0.06/GB = $0.07/month
  - Savings: $0.07/month (50% reduction)
```

### Artifact Lifecycle Management

**REQ-340: Artifact states and EOL**

**Lifecycle States:**

```
active → deprecated → eol → deleted
```

| State | Description | Actions Allowed | Data Products |
|-------|-------------|-----------------|---------------|
| **active** | Current recommended version | Pull, promote, pin | Full support |
| **deprecated** | Older version, still supported | Pull, pin (with warning) | Limited support |
| **eol** | End-of-life, no support | Pull only (strong warning) | No support |
| **deleted** | Removed by GC | None | Migration required |

**Lifecycle Configuration:**

```yaml
# platform-manifest.yaml
artifacts:
  lifecycle:
    deprecation_policy:
      auto_deprecate_after: 180   # Mark as deprecated after 6 months
      deprecation_warning: true   # Warn users on pull

    eol_policy:
      auto_eol_after: 365         # Mark EOL after 1 year
      eol_blocking: false         # Don't block pulls, just warn

    notifications:
      deprecated:
        slack: "#platform-ops"
        email: ["ops@acme.com"]
      eol:
        slack: "#platform-ops"
        email: ["ops@acme.com", "leadership@acme.com"]
```

**Lifecycle Metadata (OCI Annotations):**

```json
{
  "manifest": {
    "annotations": {
      "org.opencontainers.image.created": "2024-01-15T10:30:00Z",
      "dev.floe.lifecycle.state": "active",
      "dev.floe.lifecycle.deprecated_at": null,
      "dev.floe.lifecycle.eol_at": null,
      "dev.floe.lifecycle.support_until": "2025-01-15T00:00:00Z"
    }
  }
}
```

**User Experience:**

```bash
floe init --platform=v1.2.3
# If v1.2.3 is deprecated:
[WARN] Platform version v1.2.3 is deprecated (deprecated on 2024-07-15)
[WARN] Recommended version: v2.0.1
[WARN] Support ends: 2025-01-15
Continue? [y/N]

# If v1.2.3 is EOL:
[ERROR] Platform version v1.2.3 has reached end-of-life (EOL on 2024-12-31)
[ERROR] No support available. Migration required.
[ERROR] Latest version: v2.0.1
[ERROR] Migration guide: https://docs.floe.dev/migration/v1-to-v2
Abort initialization.
```

### Manual Garbage Collection

**CLI Commands:**

```bash
# Dry-run GC (show what would be deleted)
floe platform gc --dry-run

# Execute GC
floe platform gc --apply

# GC with custom retention
floe platform gc --apply --keep-last=5 --keep-days=30

# Force delete specific version (dangerous)
floe platform delete v1.2.3 --force --confirm

# Show storage usage
floe platform storage-report
```

**Storage Report Example:**

```bash
floe platform storage-report

Platform Artifact Storage Report
─────────────────────────────────────────────────────
Registry: harbor.acme.com/floe-artifacts

By Environment:
  dev:        45 artifacts,  2.1 GB  ($0.13/month)
  staging:    18 artifacts,  0.8 GB  ($0.05/month)
  production: 12 artifacts,  0.5 GB  ($0.03/month)

By Age:
  < 30 days:  28 artifacts,  1.2 GB
  30-90 days: 32 artifacts,  1.5 GB
  > 90 days:  15 artifacts,  0.7 GB

Protected Tags:
  v* tags:    42 artifacts,  1.9 GB
  *-prod:     12 artifacts,  0.5 GB
  latest-*:    3 artifacts,  0.1 GB

Total:        75 artifacts,  3.4 GB  ($0.20/month)

Recommendations:
  - Run GC to remove 27 artifacts (save $0.07/month)
  - Consider aggressive retention for dev environment
```

## Consequences

### Positive

- **Cost control** - Automatic cleanup prevents unbounded storage growth
- **Safety** - Protected tags prevent accidental deletion of critical versions
- **Immutability** - Registry-native enforcement prevents tag reassignment attacks
- **Lifecycle clarity** - Users know when versions are deprecated/EOL
- **Audit trail** - All GC operations logged
- **Visibility** - Storage reports show cost breakdown

### Negative

- **Registry limitation** - GitHub CR, JFrog, Nexus not supported for production (lack immutability)
- **Storage costs** - Conservative retention policy (10 versions, 90 days) may retain more than needed
- **Complexity** - Lifecycle states add cognitive overhead
- **Manual intervention** - May need to override protection rules in rare cases

### Neutral

- GC runs automatically (less manual work, but need to monitor)
- Deprecated versions still usable (gradual migration, but lingering technical debt)
- Immutability prevents fixes (cannot patch published version, must release new version)

## Implementation

### Registry Configuration

**Harbor Setup (Default OSS):**

```yaml
# charts/floe-platform/values.yaml
harbor:
  enabled: true
  database:
    type: internal  # Or external PostgreSQL
  redis:
    type: internal  # Or external Redis
  core:
    immutableTagRules:
      - pattern: "v*"              # All semver tags immutable
        immutable: true
      - pattern: "*-dev"           # Environment tags immutable
        immutable: true
      - pattern: "*-staging"
        immutable: true
      - pattern: "*-prod"
        immutable: true
      - pattern: "latest-*"        # Latest tags mutable
        immutable: false
```

**Cloud Registry Setup:**

```yaml
# platform-manifest.yaml (AWS ECR)
artifacts:
  registry:
    type: ecr
    url: 123456789.dkr.ecr.us-east-1.amazonaws.com
    project: floe-artifacts

    # ECR-specific immutability (via AWS API)
    immutability:
      imageTagMutability: IMMUTABLE  # All tags immutable except lifecycle policy exclusions
```

### Garbage Collection Job

**Kubernetes CronJob:**

```yaml
# charts/floe-platform/templates/gc-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: floe-artifact-gc
spec:
  schedule: "0 2 * * *"  # 2 AM UTC daily
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: gc
            image: floe-cli:latest
            command:
            - floe
            - platform
            - gc
            - --apply
            - --config=/etc/floe/platform-manifest.yaml
          restartPolicy: OnFailure
```

### Configuration Schema

```yaml
# platform-manifest.yaml
artifacts:
  registry:
    type: harbor | ecr | acr | gar  # MUST have native immutability
    url: string
    project: string

    immutability:
      enforcement: registry_native
      semver_tags: immutable
      environment_tags: immutable
      latest_tags: mutable

  retention:
    keep_last_versions: int        # 10 (conservative), 5 (balanced), 3 (aggressive)
    keep_duration_days: int        # 90, 30, 14
    protected_tags: list[string]   # Glob patterns
    delete_schedule:
      frequency: daily | weekly
      time: string  # HH:MM format
      timezone: string
    dry_run: bool

  lifecycle:
    deprecation_policy:
      auto_deprecate_after: int    # Days
      deprecation_warning: bool
    eol_policy:
      auto_eol_after: int          # Days
      eol_blocking: bool
    notifications:
      deprecated:
        slack: string
        email: list[string]
      eol:
        slack: string
        email: list[string]
```

## References

- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md) - OCI registry decision
- [ADR-0039: Multi-Environment Promotion](0039-multi-environment-promotion.md) - Promotion workflows
- [EPIC-06: OCI Artifact System](../../plan/epics/EPIC-06.md) - Implementation epic
- [REQ-313, REQ-334, REQ-340](../../plan/requirements/04-artifact-distribution/01-oci-operations.md) - Immutability & GC requirements
- **Industry Sources:**
  - [ECR Repository Tag Immutability](https://cloud-kb.sentinelone.com/ecr-repository-tag-immutability)
  - [Immutable Container Image Tags (ProactiveOps)](https://www.proactiveops.io/archive/immutable-container-image-tags/)
  - [Kubernetes GC Best Practices (Groundcover)](https://www.groundcover.com/learn/storage/kubernetes-garbage-collection)
  - [Azure Container Registry Retention Policy](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-retention-policy)

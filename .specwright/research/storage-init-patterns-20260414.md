# Research Brief: S3/MinIO Bucket Provisioning for Data Platform Helm Charts

**Date**: 2026-04-14
**Status**: AUTO-APPROVED (all tracks >= MEDIUM confidence)
**Consumed by**: sw-design (storage initialization gap)

## Summary

The floe-platform Helm chart has a **critical storage initialization gap**: `minio.defaultBuckets`
is configured in values files but the Bitnami MinIO subchart ignores this parameter without
`provisioning.enabled: true`. Result: MinIO deploys with **zero buckets**. All Iceberg operations,
dbt seed/run, Dagster materialization, and E2E tests fail with HTTP 404 / NoSuchBucketException.

## Track 1: MinIO Helm Chart Bucket Provisioning Mechanisms (HIGH confidence)

### Official MinIO Chart (minio/minio)

Two mechanisms:

1. **`buckets[]` array + `makeBucketJob`**: Buckets declared via values are created by a
   `post-install,post-upgrade` Helm hook Job running `mc mb`. Idempotent via `--ignore-existing`.
   ```yaml
   buckets:
     - name: floe-iceberg
       policy: none
       purge: false
       versioning: false
       objectlocking: false
   ```

2. **`defaultBuckets`**: Comma-separated list for standalone mode only. Race condition in
   distributed mode — all nodes start simultaneously.

### Bitnami MinIO Chart (bitnami/charts — our subchart)

Uses `provisioning` section, NOT `defaultBuckets`:
```yaml
provisioning:
  enabled: true
  buckets:
    - name: floe-iceberg
      versioning: false
      withLock: false
```

**Critical finding**: Our chart sets `minio.defaultBuckets: "floe-iceberg"` but does NOT set
`provisioning.enabled: true`. The Bitnami chart silently ignores unrecognized top-level values.

**Known issue**: Bitnami provisioning Job `sleepTime` default (5s) is insufficient for clustered
MinIO — bitnami/charts issues #8042, #30597.

Sources:
- https://github.com/minio/minio/blob/master/helm/minio/values.yaml
- https://github.com/bitnami/charts/blob/main/bitnami/minio/values.yaml
- https://github.com/bitnami/charts/issues/30597

## Track 2: Iceberg Lakehouse Storage Initialization Patterns (HIGH confidence)

**Bucket creation is a prerequisite, not part of catalog setup.**

- **Apache Polaris + Ozone reference**: Sequential steps — deploy storage, create bucket,
  create credential Secret, deploy Polaris, configure catalog via REST API.
- **Nessie**: "the database and the schema must be created beforehand, as the Helm chart
  will not create them for you."
- **Iceberg lifecycle policies**: Use `expire_snapshots` / `VACUUM` for cleanup. AWS recommends
  S3 Intelligent-Tiering but warns against Archive/Deep Archive tiers on Iceberg data.

Sources:
- https://polaris.apache.org/blog/2026/04/04/build-a-local-open-data-lakehouse-with-k3d-apache-ozone-apache-polaris-and-trino/
- https://projectnessie.org/guides/kubernetes/
- https://docs.aws.amazon.com/prescriptive-guidance/latest/apache-iceberg-on-aws/best-practices-storage.html

## Track 3: Kubernetes Init Patterns for Storage Bootstrapping (HIGH confidence)

| Pattern | Ordering | Blocks App? | Idempotent? | Best For |
|---------|----------|-------------|-------------|----------|
| Helm post-install hook Job | Release-level (weight-ordered) | No (unless --wait) | mc mb --ignore-existing | Bucket creation after MinIO ready |
| Init container | Pod-level (sequential) | Yes | Must implement | Waiting for external service |
| Operator CRD | Reconciliation loop | Automatic | Built-in | Production MinIO Operator |

**Canonical pattern**: post-install Job with `mc mb --ignore-existing`, `restartPolicy: OnFailure`,
`hook-delete-policy: hook-succeeded,before-hook-creation`.

Sources:
- https://helm.sh/docs/v3/topics/charts_hooks/
- https://kubernetes.io/docs/concepts/workloads/pods/init-containers/
- https://github.com/helm/charts/blob/master/stable/minio/templates/post-install-create-bucket-job.yaml

## Track 4: S3 Security & Policy for Iceberg Buckets (MEDIUM confidence)

### Required bucket policies for Iceberg warehouse:

| Setting | Required | Notes |
|---------|----------|-------|
| Block Public Access | Yes | Never expose warehouse data publicly |
| SSE-S3 encryption | Default (AWS) | Must configure for MinIO |
| TLS-only (SecureTransport) | Yes | Deny non-TLS requests via bucket policy |
| Abort incomplete multipart uploads | Yes | 14-day lifecycle rule prevents cost leak |
| Remove expired delete markers | Yes | Prevents ListObjectVersions degradation |

### IAM permissions for Iceberg (write access):
`s3:GetBucketLocation`, `s3:GetObject`, `s3:ListBucket`, `s3:PutObject`, `s3:DeleteObject`,
`s3:GetObjectVersion`, `s3:DeleteObjectVersion`

### AWS Prescriptive Guidance bucket separation:
Minimum 3 buckets: raw, stage, analytics. Separate IAM policies per bucket.
(Our single `floe-iceberg` bucket is acceptable for dev/test but may need splitting for production.)

Sources:
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html
- https://docs.snowflake.com/en/user-guide/tables-iceberg-storage
- https://medium.com/datamindedbe/two-lifecycle-policies-every-s3-bucket-should-have-f5e51436c060

## Current State in floe-platform Chart

| Component | Config | Status |
|-----------|--------|--------|
| `minio.defaultBuckets` | Set to `"floe-iceberg"` | **Silently ignored** (Bitnami chart) |
| `provisioning.enabled` | Not set | **Missing** — no provisioning Job created |
| Polaris bootstrap job | Checks bucket exists, fails on 404 | **Correct guard, wrong dependency** |
| Bucket creation Job | Does not exist | **GAP** |

## Recommendations (for sw-design consumption)

1. **Immediate**: Enable Bitnami `provisioning` — set `minio.provisioning.enabled: true` and
   `minio.provisioning.buckets[0].name: floe-iceberg`
2. **Or**: Add a custom `post-install` Helm hook Job using `mc mb --ignore-existing` that runs
   before the Polaris bootstrap job (lower hook weight)
3. **Polaris bootstrap**: Add init container that waits for bucket to exist before running
   the bootstrap script (currently races)
4. **Production**: Consider MinIO Operator with `Tenant` CRD for declarative bucket management
5. **Bucket policy**: Apply lifecycle rules for orphan file cleanup and multipart upload abort

## Open Questions

- Should floe-platform own bucket lifecycle policies (encryption, versioning) or delegate to
  the cluster operator?
- Is the single `floe-iceberg` bucket sufficient, or should we separate raw/staging/analytics?
- Should the Polaris bootstrap job create the bucket if missing, or should it remain a pure
  catalog bootstrapper?

## Caveats

- Bitnami provisioning Job `sleepTime` may need tuning for slower clusters
- `defaultBuckets` parameter may work in some Bitnami chart versions — version-dependent
- MinIO Operator CRD does not expose a standalone `versioning` field (only via `objectLock`)

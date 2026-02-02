# floe-jobs Helm Chart

Helm chart for deploying floe data product jobs (dbt runs, data ingestion, etc.) as Kubernetes Jobs or CronJobs.

## Prerequisites

- Kubernetes 1.23+
- Helm 3.8+
- (Optional) floe-platform chart deployed for service discovery

## Installation

```bash
# Add floe Helm repository (when published)
helm repo add floe https://charts.floe.dev
helm repo update

# Install with default values
helm install my-jobs floe/floe-jobs

# Install with dbt job enabled
helm install my-jobs floe/floe-jobs \
  --set dbt.enabled=true \
  --set dbt.schedule="0 */6 * * *"
```

### Install from Local Chart

```bash
helm install my-jobs ./charts/floe-jobs \
  --set dbt.enabled=true
```

## Configuration

### Global Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.imagePullPolicy` | Image pull policy | `IfNotPresent` |
| `global.imagePullSecrets` | Image pull secrets | `[]` |
| `global.commonLabels` | Labels applied to all resources | `{}` |
| `global.commonAnnotations` | Annotations applied to all resources | `{}` |

### Job Defaults

| Parameter | Description | Default |
|-----------|-------------|---------|
| `defaults.restartPolicy` | Pod restart policy | `Never` |
| `defaults.backoffLimit` | Job backoff limit | `3` |
| `defaults.ttlSecondsAfterFinished` | TTL for finished jobs | `3600` |
| `defaults.activeDeadlineSeconds` | Job timeout | `null` |
| `defaults.resources.requests.cpu` | CPU request | `100m` |
| `defaults.resources.requests.memory` | Memory request | `256Mi` |
| `defaults.resources.limits.cpu` | CPU limit | `1000m` |
| `defaults.resources.limits.memory` | Memory limit | `1Gi` |

### dbt Job

| Parameter | Description | Default |
|-----------|-------------|---------|
| `dbt.enabled` | Enable dbt job | `false` |
| `dbt.image.repository` | dbt image repository | `ghcr.io/dbt-labs/dbt-core` |
| `dbt.image.tag` | dbt image tag | `1.8.0` |
| `dbt.command` | Container command | `["dbt"]` |
| `dbt.args` | Container arguments | `["run", "--profiles-dir", "/etc/dbt", "--project-dir", "/dbt"]` |
| `dbt.schedule` | CronJob schedule (empty = one-time Job) | `""` |
| `dbt.cronJob.concurrencyPolicy` | CronJob concurrency policy | `Forbid` |
| `dbt.cronJob.successfulJobsHistoryLimit` | Successful jobs to keep | `3` |
| `dbt.cronJob.failedJobsHistoryLimit` | Failed jobs to keep | `1` |

### Ingestion Job

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingestion.enabled` | Enable ingestion job | `false` |
| `ingestion.image.repository` | Ingestion image | `""` |
| `ingestion.image.tag` | Ingestion image tag | `""` |
| `ingestion.schedule` | CronJob schedule | `""` |

### Custom Jobs

Define additional custom jobs:

```yaml
customJobs:
  - name: my-custom-job
    image:
      repository: my-image
      tag: latest
    command: ["python"]
    args: ["-m", "my_module"]
    env:
      - name: MY_VAR
        value: "my-value"
    schedule: "0 * * * *"  # Optional: makes it a CronJob
```

### Platform Integration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `platform.releaseName` | floe-platform release name | `""` |
| `platform.namespace` | floe-platform namespace | `""` |
| `platform.polarisEndpoint` | Explicit Polaris endpoint | `""` |
| `platform.otelEndpoint` | Explicit OTel endpoint | `""` |

When `platform.releaseName` is set, the chart automatically discovers:
- Polaris catalog endpoint
- OpenTelemetry collector endpoint

### Service Account

| Parameter | Description | Default |
|-----------|-------------|---------|
| `serviceAccount.create` | Create service account | `true` |
| `serviceAccount.name` | Service account name | `""` |
| `serviceAccount.annotations` | Service account annotations | `{}` |

## Examples

### Scheduled dbt Run

```yaml
dbt:
  enabled: true
  image:
    repository: ghcr.io/dbt-labs/dbt-core
    tag: "1.8.0"
  schedule: "0 */6 * * *"  # Every 6 hours
  volumeMounts:
    - name: dbt-project
      mountPath: /dbt
    - name: dbt-profiles
      mountPath: /etc/dbt
  volumes:
    - name: dbt-project
      persistentVolumeClaim:
        claimName: dbt-project-pvc
    - name: dbt-profiles
      secret:
        secretName: dbt-profiles

platform:
  releaseName: floe
```

### Data Ingestion with dlt

```yaml
ingestion:
  enabled: true
  image:
    repository: my-registry/dlt-pipeline
    tag: v1.0.0
  command: ["python", "-m", "dlt"]
  args: ["run", "my_pipeline"]
  schedule: "0 2 * * *"  # Daily at 2 AM
  envFrom:
    - secretRef:
        name: source-credentials
```

### Multiple Custom Jobs

```yaml
customJobs:
  - name: data-quality
    image:
      repository: my-registry/data-quality
      tag: v1.0.0
    command: ["python"]
    args: ["check.py"]
    schedule: "30 * * * *"

  - name: cleanup
    image:
      repository: my-registry/cleanup
      tag: v1.0.0
    command: ["./cleanup.sh"]
    schedule: "0 0 * * 0"  # Weekly
```

## Security

The chart applies security best practices by default:

- Pods run as non-root user (UID 1000)
- Read-only root filesystem
- No privilege escalation
- All capabilities dropped

Override in `defaults.securityContext` and `defaults.containerSecurityContext`.

## Integration with floe-platform

This chart is designed to work alongside [floe-platform](../floe-platform/). When deployed together:

1. Set `platform.releaseName` to your floe-platform release name
2. Jobs automatically discover Polaris and OTel endpoints
3. Use shared PostgreSQL for dbt metadata (via external secret)

```bash
# Deploy platform first
helm install floe ./charts/floe-platform

# Then deploy jobs
helm install floe-jobs ./charts/floe-jobs \
  --set platform.releaseName=floe \
  --set dbt.enabled=true
```

## Troubleshooting

### Job Not Starting

1. Check pod status: `kubectl get pods -l app.kubernetes.io/name=floe-jobs`
2. Check events: `kubectl describe job <job-name>`
3. Check logs: `kubectl logs job/<job-name>`

### CronJob Not Triggering

1. Verify schedule: `kubectl get cronjob <name> -o yaml | grep schedule`
2. Check if suspended: `kubectl get cronjob <name> -o jsonpath='{.spec.suspend}'`
3. Check last schedule: `kubectl get cronjob <name> -o jsonpath='{.status.lastScheduleTime}'`

## License

Apache 2.0

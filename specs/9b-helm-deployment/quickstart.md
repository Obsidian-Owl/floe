# Quickstart: Epic 9B - Helm Charts and Kubernetes Deployment

This guide provides quick-start instructions for developers working on Epic 9B.

## Prerequisites

- Helm 3.12+
- kubectl configured for target cluster
- Kind (for local testing)
- Access to OCI registry (for chart publishing)

## Quick Commands

### Local Development with Kind

```bash
# Create Kind cluster with floe configuration
make kind-create

# Build and deploy platform to Kind
make helm-install-dev

# View deployed services
kubectl get pods -n floe-dev

# Access Dagster UI
kubectl port-forward svc/floe-platform-dagster-webserver 3000:3000 -n floe-dev
open http://localhost:3000
```

### Generate Helm Values from Artifacts

```bash
# From local CompiledArtifacts
floe helm generate \
  --artifact target/compiled_artifacts.json \
  --env dev \
  --output values-generated.yaml

# From OCI registry
floe helm generate \
  --artifact oci://registry.example.com/floe/artifacts:v1.2.3-staging \
  --env staging \
  --output values-staging.yaml
```

### Chart Development

```bash
# Lint chart
helm lint charts/floe-platform

# Template preview
helm template floe-platform charts/floe-platform \
  -f values-dev.yaml \
  --debug

# Install to Kind cluster
helm install floe-platform charts/floe-platform \
  --namespace floe-dev \
  --create-namespace \
  -f values-dev.yaml

# Upgrade existing installation
helm upgrade floe-platform charts/floe-platform \
  --namespace floe-dev \
  -f values-dev.yaml

# Run chart tests
helm test floe-platform -n floe-dev
```

### Data Product Jobs

```bash
# Install floe-jobs chart for dbt execution
helm install my-pipeline charts/floe-jobs \
  --namespace floe-dev \
  --set job.name=my-dbt-run \
  --set job.image=floe/dbt-runner:latest \
  --set job.command="dbt run --select my_model"

# View job status
kubectl get jobs -n floe-dev
kubectl logs job/my-dbt-run -n floe-dev
```

## Environment Files

| File | Purpose |
|------|---------|
| `values.yaml` | Chart defaults |
| `values-dev.yaml` | Local development (Kind) |
| `values-staging.yaml` | Staging environment |
| `values-prod.yaml` | Production with HA |

## Chart Structure

```
charts/
├── floe-platform/           # Platform services umbrella chart
│   ├── Chart.yaml          # Dependencies: dagster, otel, minio
│   ├── values.yaml         # Default values
│   ├── values.schema.json  # JSON Schema validation
│   ├── templates/
│   │   ├── _helpers.tpl    # Template helpers
│   │   ├── configmap.yaml  # OTel/platform config
│   │   ├── secret.yaml     # Credential references
│   │   ├── networkpolicy.yaml
│   │   ├── ingress.yaml
│   │   └── NOTES.txt       # Post-install instructions
│   └── charts/             # Vendored subcharts
│
├── floe-jobs/              # Data product job chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── job.yaml        # K8s Job template
│       └── cronjob.yaml    # CronJob template
│
└── testing/
    └── kind-values.yaml    # Kind-specific overrides
```

## Testing

```bash
# Run all Helm tests
make helm-test

# Lint only
make helm-lint

# Integration test in Kind
make helm-integration-test
```

## GitOps Deployment

### ArgoCD

```bash
# Apply ApplicationSet for multi-environment deployment
kubectl apply -f examples/argocd/applicationset.yaml

# Check sync status
argocd app list
```

### Flux

```bash
# Apply HelmRelease
kubectl apply -f examples/flux/helmrelease.yaml

# Check reconciliation
flux get helmreleases
```

## Troubleshooting

### Common Issues

**Chart dependency not found:**
```bash
helm dependency update charts/floe-platform
```

**Schema validation failed:**
```bash
# Check values against schema
helm template floe-platform charts/floe-platform \
  -f your-values.yaml \
  --validate
```

**Pod not starting:**
```bash
kubectl describe pod <pod-name> -n floe-dev
kubectl logs <pod-name> -n floe-dev --previous
```

### Debug Mode

```bash
# Enable verbose Helm output
helm install floe-platform charts/floe-platform \
  --namespace floe-dev \
  --debug \
  --dry-run
```

## Next Steps

1. Review [spec.md](./spec.md) for full requirements
2. Check [research.md](./research.md) for design decisions
3. See [data-model.md](./data-model.md) for entity definitions
4. Run `/speckit.tasks` to generate implementation tasks

# floe-platform Helm Chart

Production-ready Helm chart for deploying the floe data platform on Kubernetes.

## Overview

This umbrella chart deploys the complete floe platform including:

- **Dagster** - Orchestration engine for data pipelines
- **Polaris** - Iceberg REST catalog for data lakehouse
- **PostgreSQL** - Metadata storage for Dagster and Polaris
- **MinIO** - S3-compatible object storage (non-prod)
- **OpenTelemetry Collector** - Observability and tracing

## Prerequisites

- Kubernetes 1.25+
- Helm 3.12+
- kubectl configured for target cluster

## Quick Start

### From Helm Repository

```bash
# Add the floe Helm repository
helm repo add floe https://obsidian-owl.github.io/floe
helm repo update

# Install with default values (dev environment)
helm install floe floe/floe-platform --namespace floe-dev --create-namespace

# Install for production
helm install floe floe/floe-platform \
  --namespace floe-prod --create-namespace \
  --set global.environment=prod \
  --set autoscaling.enabled=true \
  --set podDisruptionBudget.enabled=true
```

### From OCI Registry

```bash
# Install from GHCR OCI registry
helm install floe oci://ghcr.io/obsidian-owl/charts/floe-platform \
  --namespace floe-dev --create-namespace

# Install specific version
helm install floe oci://ghcr.io/obsidian-owl/charts/floe-platform \
  --version 1.0.0 \
  --namespace floe-prod --create-namespace
```

### From Local Chart

```bash
# Add dependencies
helm dependency update ./charts/floe-platform

# Install with default values (dev environment)
helm install floe ./charts/floe-platform --namespace floe-dev --create-namespace

# Install for staging
helm install floe ./charts/floe-platform \
  -f values.yaml \
  -f values-staging.yaml \
  --namespace floe-staging --create-namespace

# Install for production
helm install floe ./charts/floe-platform \
  -f values.yaml \
  -f values-prod.yaml \
  --namespace floe-prod --create-namespace
```

## Environment Configuration

### Cluster Mapping

The chart supports logical-to-physical environment mapping via `clusterMapping`:

```yaml
clusterMapping:
  nonProd:
    cluster: "aks-nonprod"
    environments: ["dev", "qa", "staging"]
    namespaceTemplate: "floe-{{ .Values.global.environment }}"
    resourcePreset: small
  prod:
    cluster: "aks-prod"
    environments: ["prod"]
    namespaceTemplate: "floe-prod"
    resourcePreset: large
```

This allows multiple logical environments to share a physical cluster with namespace isolation.

### Resource Presets

Three resource presets are available:

| Preset | CPU Request | Memory Request | Use Case |
|--------|-------------|----------------|----------|
| small  | 100m        | 256Mi          | Development |
| medium | 250m        | 512Mi          | Staging |
| large  | 500m        | 1Gi            | Production |

### Environment-Specific Values

Use environment-specific values files:

- `values.yaml` - Base configuration (required)
- `values-dev.yaml` - Development overrides
- `values-staging.yaml` - Staging overrides
- `values-prod.yaml` - Production overrides

## Security Features

### Network Policies

Enable network isolation between components:

```yaml
networkPolicy:
  enabled: true  # Recommended for staging/prod
```

This creates policies for:
- Default deny ingress
- Dagster to PostgreSQL/Polaris egress
- Polaris to PostgreSQL/MinIO egress
- OTel Collector ingress from all pods

### RBAC

The chart creates:
- ServiceAccount for Dagster components
- Role with K8sRunLauncher permissions
- RoleBinding to connect them

## High Availability (Production)

Enable HA features for production:

```yaml
autoscaling:
  enabled: true

podDisruptionBudget:
  enabled: true
  minAvailable: 1

# In values-prod.yaml
dagster:
  dagster-webserver:
    replicaCount: 2
```

## Configuration Reference

### Global Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.environment` | Environment name | `dev` |
| `global.commonLabels` | Labels for all resources | `{}` |

### Namespace

| Parameter | Description | Default |
|-----------|-------------|---------|
| `namespace.name` | Namespace name | `floe-dev` |
| `namespace.create` | Create namespace | `true` |

### Dagster

See [Dagster Helm Chart](https://docs.dagster.io/deployment/guides/kubernetes/deploying-with-helm) for full options.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `dagster.enabled` | Enable Dagster | `true` |
| `dagster.dagster-webserver.replicaCount` | Webserver replicas | `1` |

### PostgreSQL

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.enabled` | Enable PostgreSQL | `true` |
| `postgresql.primary.persistence.size` | Storage size | `10Gi` |

### Polaris

| Parameter | Description | Default |
|-----------|-------------|---------|
| `polaris.enabled` | Enable Polaris | `true` |
| `polaris.replicaCount` | Replicas | `1` |

### MinIO

| Parameter | Description | Default |
|-----------|-------------|---------|
| `minio.enabled` | Enable MinIO | `true` |
| `minio.mode` | Deployment mode | `standalone` |

### Ingress

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `false` |
| `ingress.className` | Ingress class | `nginx` |
| `ingress.hosts` | Ingress hosts | `[]` |

## GitOps Deployment

### ArgoCD

Start with the public examples in [charts/examples/argocd/](../examples/argocd/).
They stay focused on the operator entry points and avoid duplicating the chart
README with a second full GitOps walkthrough.

### Flux CD

Use the public Flux examples in [charts/examples/flux/](../examples/flux/).
For the supported operator workflow, including the compile-to-ConfigMap flow,
OCI chart source, version knob, and `valuesFrom` integration, follow the
dedicated [GitOps with Flux guide](../../docs/guides/deployment/gitops-flux.md).

## Upgrade Guide

```bash
# Update dependencies
helm dependency update ./charts/floe-platform

# Upgrade release
helm upgrade floe ./charts/floe-platform \
  -f values.yaml \
  -f values-staging.yaml \
  --namespace floe-staging
```

## Troubleshooting

### Check pod status
```bash
kubectl get pods -n floe-staging
```

### View Dagster logs
```bash
kubectl logs -l app.kubernetes.io/name=dagster -n floe-staging
```

### Validate chart
```bash
helm template floe ./charts/floe-platform -f values.yaml --debug
```

## Compatibility Matrix

| Chart Version | floe-core | Kubernetes | Helm | Dagster Chart | OTel Chart |
|---------------|-----------|------------|------|---------------|------------|
| 0.1.x         | >=0.5.0   | >=1.28     | >=3.12 | 1.9.6       | 0.108.0    |

### Subchart Versions

| Component | Version | Notes |
|-----------|---------|-------|
| Dagster   | 1.9.6   | Orchestration platform |
| OpenTelemetry Collector | 0.108.0 | Observability |
| MinIO (Bitnami) | 14.8.5 | Dev/Demo only |

### Image Versions

| Component | Default Image | Tag |
|-----------|---------------|-----|
| Polaris   | apache/polaris | 0.9.0 |
| PostgreSQL | postgres | 16-alpine |
| Marquez (optional) | marquezproject/marquez | 0.49.0 |

## Related Documentation

- [Epic 9B Specification](../../specs/9b-helm-deployment/spec.md)
- [floe-jobs Chart](../floe-jobs/README.md)
- [Dagster Helm Docs](https://docs.dagster.io/deployment/guides/kubernetes)

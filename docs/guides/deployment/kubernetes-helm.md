# Kubernetes (Helm)

This document covers Helm-based Kubernetes deployment for floe.

> **Note**: For the latest chart documentation, see:
> - [floe-platform Chart README](../../../charts/floe-platform/README.md)
> - [floe-jobs Chart README](../../../charts/floe-jobs/README.md)

---

## Quick Start

```bash
helm dependency update ./charts/floe-platform
helm upgrade --install floe ./charts/floe-platform \
  --namespace floe-dev \
  --create-namespace
```

For published chart validation, use the release artifact path documented in the release checklist for the version you are installing.

## 1. Chart Structure

`charts/floe-platform` is the alpha platform chart. It uses direct Helm values and chart dependencies; this guide does not claim manifest-driven chart assembly.

```
charts/
+-- floe-platform/
|   +-- Chart.yaml
|   +-- values.yaml
|   +-- templates/
|       +-- _helpers.tpl
|       +-- deployment-polaris.yaml
|       +-- deployment-marquez.yaml
|       +-- service-polaris.yaml
|       +-- service-postgresql.yaml
|       +-- statefulset-postgresql.yaml
|       +-- ingress.yaml
|
+-- floe-jobs/
    +-- Chart.yaml
    +-- values.yaml
    +-- templates/
```

`Chart.yaml` declares the current subchart dependencies for Dagster, OpenTelemetry, Jaeger, and MinIO. Floe-owned templates in `templates/` render Polaris, Marquez, PostgreSQL, bootstrap jobs, RBAC, network policy, ingress, and tests.

---

## 2. Alpha Deployment Model

The alpha chart deploys platform services into a Kubernetes namespace using Helm. Defaults are optimized for local/dev evaluation, not production hardening.

Service names come from two naming rules:

- Parent-chart Floe services use `fullnameOverride` when set. The default is `floe-platform`, so Polaris renders as `floe-platform-polaris` and PostgreSQL renders as `floe-platform-postgresql`.
- The upstream Dagster subchart prefixes the webserver service with the Helm release name. With `helm upgrade --install floe ...`, the webserver service is `floe-dagster-webserver`.

---

## 3. Current Values Excerpt

The excerpt below uses real keys from `charts/floe-platform/values.yaml`. Keep environment overrides small and verify them with `helm template` before applying.

```yaml
global:
  environment: dev
  imagePullPolicy: IfNotPresent
  storageClass: ""
  commonLabels: {}
  commonAnnotations: {}

namespace:
  create: false
  name: ""

fullnameOverride: floe-platform

clusterMapping:
  nonProd:
    cluster: ""
    environments:
      - dev
      - qa
      - staging
    namespaceTemplate: "floe-{{ .environment }}"
    resources:
      preset: small
  prod:
    cluster: ""
    environments:
      - prod
    namespaceTemplate: "floe-prod"
    resources:
      preset: large

resourcePresets:
  small:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi

dagster:
  enabled: true
  dagsterWebserver:
    replicaCount: 1
    service:
      type: ClusterIP
      port: 80
  dagsterDaemon:
    enabled: true

polaris:
  enabled: true
  service:
    type: ClusterIP
    port: 8181
    managementPort: 8182

otel:
  enabled: true
  mode: deployment

postgresql:
  enabled: true
  auth:
    database: floe
    username: floe
    password: ""
    existingSecret: ""

minio:
  enabled: false

jaeger:
  enabled: true

marquez:
  enabled: true

networkPolicy:
  enabled: false

ingress:
  enabled: false
```

---

## 4. Secrets And Credentials

The alpha chart supports existing Kubernetes Secrets for sensitive values. Do not put long-lived credentials directly in committed values files.

Useful current keys include:

| Purpose | Values keys |
|---------|-------------|
| PostgreSQL password | `postgresql.auth.password`, `postgresql.auth.existingSecret`, `postgresql.auth.existingSecretKey` |
| Polaris bootstrap credentials | `polaris.auth.existingSecret`, `polaris.auth.bootstrapCredentials.clientId`, `polaris.auth.bootstrapCredentials.clientSecret` |
| MinIO local/demo credentials | `minio.auth.rootUser`, `minio.auth.rootPassword`, `minio.auth.existingSecret` |
| External Secrets integration | `externalSecrets.enabled`, `externalSecrets.polaris.enabled`, `externalSecrets.postgresql.enabled` |

---

## 5. Default Resource Shape

These are chart defaults for alpha evaluation. They are not production capacity recommendations.

| Component | Default request | Default limit |
|-----------|-----------------|---------------|
| Dagster webserver | 100m CPU, 256Mi memory | 500m CPU, 512Mi memory |
| Dagster daemon | 100m CPU, 256Mi memory | 500m CPU, 512Mi memory |
| Dagster run pods | 100m CPU, 256Mi memory | 1000m CPU, 1Gi memory |
| Polaris | 200m CPU, 512Mi memory | 1000m CPU, 1Gi memory |
| PostgreSQL | 100m CPU, 256Mi memory | 500m CPU, 512Mi memory |

---

## Related Documentation

- [floe-platform Chart](../../../charts/floe-platform/README.md) - Platform services chart
- [floe-jobs Chart](../../../charts/floe-jobs/README.md) - Jobs and pipelines chart
- [Production considerations](production.md) - Planned HA, scaling, and monitoring considerations, not alpha-validated operations
- [Two-Layer Model](two-layer-model.md) - Deployment model overview
- [Local Development](local-development.md) - Development setup

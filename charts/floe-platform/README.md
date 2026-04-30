# floe-platform Helm Chart

Alpha Helm chart for evaluating Floe platform services on Kubernetes.

This chart is currently validated for local/dev and Customer 360 alpha paths. It is not a supported production runbook, and production hardening remains planned/not alpha-proven.

## What This Chart Deploys

The default `values.yaml` renders these platform services:

- Dagster orchestration, including the webserver, daemon, and workspace wiring.
- Polaris Iceberg REST catalog.
- PostgreSQL metadata storage shared by platform services.
- OpenTelemetry Collector for telemetry ingestion.
- Jaeger all-in-one trace backend.
- Marquez lineage service.

Optional components:

- MinIO is available for local/demo object storage, but is disabled by default.
- Cube is present as a local semantic-layer dependency, but is disabled by default with `cube.enabled: false`.
- Contract monitor and chart test jobs are opt-in.

## Prerequisites

- Kubernetes 1.28 or newer.
- Helm 3.12 or newer.
- `kubectl` configured for the target cluster.

## Local/Dev Quick Start

Run from the repository root:

```bash
helm dependency update ./charts/floe-platform
helm upgrade --install floe ./charts/floe-platform \
  --namespace floe-dev \
  --create-namespace
```

Validate the rendered chart before applying overrides:

```bash
helm template floe ./charts/floe-platform \
  --namespace floe-dev
```

Access Dagster with the default chart values:

```bash
kubectl port-forward -n floe-dev svc/floe-dagster-webserver 3100:80
```

Then open `http://localhost:3100`.

The demo values override the Dagster service port to `3000`, so demo-specific helpers can render `3100:3000` while the default chart remains `3100:80`.

## Current Values Shape

These keys are verified against the current `values.yaml`.

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
    environments: [dev, qa, staging]
    namespaceTemplate: "floe-{{ .environment }}"
    resources:
      preset: small
  prod:
    cluster: ""
    environments: [prod]
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
  dagster-user-deployments:
    enabled: true
    enableSubchart: false
    deployments: []

polaris:
  enabled: true
  service:
    type: ClusterIP
    port: 8181
    managementPort: 8182

postgresql:
  enabled: true
  auth:
    database: floe
    username: floe
    password: ""
    existingSecret: ""
    existingSecretKey: password

otel:
  enabled: true
  fullnameOverride: floe-platform-otel
  mode: deployment

jaeger:
  enabled: true

marquez:
  enabled: true

minio:
  enabled: false

cube:
  enabled: false

networkPolicy:
  enabled: false

ingress:
  enabled: false

podDisruptionBudget:
  enabled: false

autoscaling:
  enabled: false
```

## Naming And Access

Parent-chart Floe services use `fullnameOverride` when set. The default is `floe-platform`, so Polaris renders as `floe-platform-polaris` and PostgreSQL renders as `floe-platform-postgresql`.

`otel.fullnameOverride` controls the OTel subchart service and resource name. If
you change it, also override the Dagster webserver and daemon
`OTEL_EXPORTER_OTLP_ENDPOINT` env values to the matching
`http://<otel-service>:4317` endpoint. The Dagster subchart renders those env
values as static YAML, not templates.

The upstream Dagster subchart uses the Helm release name for the webserver service. With `helm upgrade --install floe ...`, Dagster renders as `floe-dagster-webserver`.

## Secrets

Do not commit long-lived credentials in values files. Current secret-related keys include:

| Purpose | Values keys |
| --- | --- |
| PostgreSQL password | `postgresql.auth.password`, `postgresql.auth.existingSecret`, `postgresql.auth.existingSecretKey` |
| Polaris bootstrap credentials | `polaris.auth.existingSecret`, `polaris.auth.bootstrapCredentials.clientId`, `polaris.auth.bootstrapCredentials.clientSecret` |
| MinIO local/demo credentials | `minio.auth.rootUser`, `minio.auth.rootPassword`, `minio.auth.existingSecret` |
| External Secrets integration | `externalSecrets.enabled`, `externalSecrets.postgresql.enabled`, `externalSecrets.minio.enabled`, `externalSecrets.secrets` |

## Production Hardening Status

The chart contains configurable primitives for ingress, network policies, pod disruption budgets, HPAs, resource quotas, and external secret integration. Those primitives are not yet a validated alpha production operations path.

Before treating this chart as a production baseline, validate at least:

- External object storage and catalog credentials.
- Backup and restore for PostgreSQL and catalog metadata.
- TLS, ingress, identity, and secret rotation.
- Resource sizing, HA behavior, and disruption budgets under load.
- Upgrade and rollback behavior for your selected values stack.

For current capability truth, see [Capability Status](../../docs/architecture/capability-status.md).

## GitOps Examples

- Argo CD examples live in [charts/examples/argocd/](../examples/argocd/).
- Flux examples live in [charts/examples/flux/](../examples/flux/).
- The public Flux workflow is documented in [GitOps with Flux](../../docs/guides/deployment/gitops-flux.md).

## Troubleshooting

Check pod status:

```bash
kubectl get pods -n floe-dev
```

View release status:

```bash
helm status floe -n floe-dev
```

Render with debug output:

```bash
helm template floe ./charts/floe-platform \
  --namespace floe-dev \
  --debug
```

## Related Documentation

- [Kubernetes Helm guide](../../docs/guides/deployment/kubernetes-helm.md)
- [Local Kind evaluation](../../docs/guides/deployment/local-development.md)
- [floe-jobs chart](../floe-jobs/README.md)

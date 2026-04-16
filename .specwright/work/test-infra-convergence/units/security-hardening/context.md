# Context: Security Hardening (Unit 3)

## Problem

Base chart `values.yaml` defines PSS restricted security contexts (lines 652-682)
but they are NOT propagated to subcharts. Dagster, Jaeger, OTel collector, and MinIO
all use their own defaults (empty `{}`). Additionally, kubeconform, kubesec, and
helm-unittest require host installation — containerizing them eliminates this dependency.

## Subchart Security Context Key Paths (VERIFIED)

| Subchart | Pod-level key | Container-level key |
|----------|--------------|---------------------|
| Dagster webserver | `dagster.dagsterWebserver.podSecurityContext` | `dagster.dagsterWebserver.securityContext` |
| Dagster daemon | `dagster.dagsterDaemon.podSecurityContext` | `dagster.dagsterDaemon.securityContext` |
| Dagster run launcher | `dagster.runLauncher.config.k8sRunLauncher.podSecurityContext` | `dagster.runLauncher.config.k8sRunLauncher.securityContext` |
| Dagster user deployments | `dagster.dagsterUserDeployments.deployments[0].podSecurityContext` | `dagster.dagsterUserDeployments.deployments[0].securityContext` |
| Jaeger all-in-one | `jaeger.allInOne.podSecurityContext` | `jaeger.allInOne.securityContext` |
| OTel collector | `opentelemetry-collector.podSecurityContext` | `opentelemetry-collector.securityContext` |
| MinIO | `minio.podSecurityContext.enabled` + subkeys | `minio.containerSecurityContext.enabled` + subkeys |

Jaeger already runs as non-root (UID 10001). MinIO uses Bitnami schema with `enabled`
flag. All verified via `helm show values`.

## Marquez Exception

Marquez runs as root (UID 0). Upstream issue #3060 open, no fix. Accepted and documented
per D-6. PSS admission is namespace-scoped — no pod-level exemption without Kyverno/OPA.
This unit does NOT address Marquez. Documented in AUDIT.md as known gap.

## Existing Security Contexts

`charts/floe-platform/values.yaml:666-682`:
```yaml
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault

containerSecurityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
  capabilities:
    drop:
      - ALL
```

These contexts are used by floe's own templates (Polaris, PostgreSQL) but NOT
passed to subcharts.

## Containerized Tools

| Tool | Official Image | Purpose |
|------|---------------|---------|
| kubeconform | `ghcr.io/yannh/kubeconform:latest` | K8s manifest validation |
| kubesec | `kubesec/kubesec:v2` | Security scanning of K8s manifests |
| helm-unittest | `helmunittest/helm-unittest:latest` | Helm chart unit testing |

## File Paths

- `charts/floe-platform/values.yaml` — add YAML anchors and subchart mappings
- `charts/floe-platform/values-dev.yaml` — propagate to dev overlay if needed
- `Makefile` — add containerized tool targets
- `tests/contract/` — new contract test for security context validation

# Research: Epic 9B - Helm Charts and Kubernetes Deployment

**Date**: 2026-02-01
**Epic**: 9B (merged with 9A)
**Status**: Complete

## Executive Summary

This research consolidates findings from codebase exploration and external documentation research to inform the Epic 9B implementation plan. Key decisions have been made regarding subchart strategies, deployment patterns, and integration approaches.

---

## 1. Current Implementation State

### What EXISTS (Production-Ready)

| Component | Location | Status |
|-----------|----------|--------|
| Plugin `get_helm_values()` pattern | `plugins/floe-orchestrator-dagster/` | Complete |
| CompiledArtifacts v0.5.0 schema | `packages/floe-core/` | Complete (817 lines) |
| Testing K8s manifests | `testing/k8s/services/` | 12 services |
| Kind cluster setup | `testing/k8s/kind-config.yaml` | Complete |
| Epic 8C promotion lifecycle | `packages/floe-core/` | Just completed |
| CLI platform group | `packages/floe-core/src/floe_core/cli/platform/` | Stub exists |

### What is MISSING (Epic 9B Must Create)

| Component | Priority | Notes |
|-----------|----------|-------|
| `charts/floe-platform/` | P0 | No production Helm charts exist |
| `charts/floe-jobs/` | P0 | No data product job chart |
| `floe helm generate` CLI | P1 | Values generation from artifacts |
| GitOps templates | P2 | ArgoCD/Flux ApplicationSet |
| Chart CI/CD | P2 | Lint, test, publish workflow |

---

## 2. Subchart Strategy Decisions

### Decision: Official Charts Where Available

| Component | Strategy | Rationale |
|-----------|----------|-----------|
| **Dagster** | Official Helm chart subchart | Mature, well-maintained, complex internals |
| **OTel Collector** | Official Helm chart subchart | Active community, proven patterns |
| **Polaris** | Official Apache chart | Available in incubator, production-ready |
| **Marquez** | In-repo chart from MarquezProject | No official Helm repo, chart in main repo |
| **PostgreSQL** | CloudNativePG Operator | Production HA, backups; StatefulSet for non-prod |
| **MinIO** | Official Bitnami chart | Dev/demo only; WARNING for production |

### Chart.yaml Dependencies Pattern

```yaml
# charts/floe-platform/Chart.yaml
apiVersion: v2
name: floe-platform
version: 0.1.0
appVersion: "1.0.0"

dependencies:
  - name: dagster
    version: "1.12.13"
    repository: "https://dagster-io.github.io/helm"
    condition: dagster.enabled

  - name: opentelemetry-collector
    version: "0.85.0"
    repository: "https://open-telemetry.github.io/opentelemetry-helm-charts"
    condition: otel.enabled

  - name: minio
    version: "14.0.0"
    repository: "https://charts.bitnami.com/bitnami"
    condition: minio.enabled
```

---

## 3. OTel Collector Configuration

### Decision: Deployment (Gateway Mode) with HPA

**Rationale**: Centralized collector is simpler than DaemonSet for app-level traces. Dagster/dbt jobs send traces directly to collector endpoint.

### Key Configuration Pattern

```yaml
# values.yaml for OTel Collector
otel:
  enabled: true
  mode: deployment  # NOT daemonset

  replicaCount: 2  # Minimum for HA

  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70

  config:
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318

    processors:
      memory_limiter:
        check_interval: 5s
        limit_percentage: 80
      batch:
        send_batch_size: 1024
        timeout: 10s

    exporters:
      otlp:
        endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}

    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [memory_limiter, batch]
          exporters: [otlp]
```

### Health Endpoints

- Liveness/Readiness: `/healthz` on port 13133
- Resource limits REQUIRED for HPA to function

---

## 4. PostgreSQL Strategy

### Decision: Environment-Specific Configuration

| Environment | Strategy | Operator |
|-------------|----------|----------|
| **Production** | PostgreSQL Operator | CloudNativePG (preferred) or Zalando |
| **Non-Prod** | Simple StatefulSet | Built-in, no operator dependency |
| **Testing** | Built-in StatefulSet | Matches `testing/k8s/services/postgres.yaml` |

### CloudNativePG Integration Pattern

```yaml
# External PostgreSQL (prod)
postgresql:
  enabled: false  # Disable built-in
  external:
    host: "floe-postgresql-rw.floe.svc.cluster.local"
    port: 5432
    secretName: "floe-postgresql-app"
    database: "dagster"
```

### StatefulSet Pattern (non-prod)

```yaml
# Built-in PostgreSQL (non-prod)
postgresql:
  enabled: true
  persistence:
    size: 8Gi
  auth:
    existingSecret: "floe-postgresql-secret"
```

---

## 5. Testing Manifests Analysis

### Baseline Patterns from `testing/k8s/services/`

**Dagster (`dagster.yaml`):**
- ConfigMap: dagster.yaml + workspace.yaml
- Secret: PostgreSQL credentials (envFrom)
- ServiceAccount + RBAC (Role, RoleBinding)
- Init container: wait-for-postgres with pg_isready
- Probes: `/server_info` on port 3000
- Resources: 100m/256Mi request, 500m/512Mi limit

**Polaris (`polaris.yaml`):**
- ConfigMap: polaris-server.yml
- In-memory metastore (test-only)
- Probes: `/healthcheck` on port 8182
- Resources: 200m/512Mi request, 1000m/1Gi limit

**Key Patterns to Preserve:**
1. Init containers with polling for dependencies
2. Separate webserver and daemon deployments for Dagster
3. ConfigMap mounting for configuration files
4. Secret references via envFrom or secretKeyRef
5. NodePort services for testing, ClusterIP for production

---

## 6. Plugin `get_helm_values()` Pattern

### Current Implementation (DagsterOrchestratorPlugin)

```python
def get_helm_values(self) -> dict[str, Any]:
    """Return Helm chart values for deploying orchestration services."""
    return {
        "dagster-webserver": {
            "enabled": True,
            "replicaCount": 1,
            "resources": {
                "requests": {"cpu": "100m", "memory": "256Mi"},
                "limits": {"cpu": "500m", "memory": "512Mi"}
            }
        },
        "dagster-daemon": {...},
        "dagster-user-code": {...},
        "postgresql": {"enabled": True}
    }
```

### Integration with Helm Values Generator

```python
# HelmValuesGenerator (to be implemented)
class HelmValuesGenerator:
    def generate(self, artifacts: CompiledArtifacts, env: str) -> dict[str, Any]:
        values = self._load_chart_defaults()

        # Get plugin-specific values
        for plugin in artifacts.plugins.all_resolved():
            if hasattr(plugin, 'get_helm_values'):
                plugin_values = plugin.get_helm_values()
                values = deep_merge(values, plugin_values)

        # Apply environment overrides
        values = self._apply_env_overrides(values, env)

        return values
```

---

## 7. CLI Integration Points

### Current State

- `floe platform deploy` exists as STUB (`deploy.py`)
- Click command group structure in place
- Pattern: subcommands under `floe platform`

### New Commands for 9B

| Command | Purpose | Priority |
|---------|---------|----------|
| `floe helm generate` | Generate values.yaml from artifacts | P1 |
| `floe helm template` | Preview rendered templates | P2 |
| `floe helm lint` | Validate chart syntax | P2 |

### Implementation Pattern

```python
@click.command()
@click.option("--artifact", required=True, help="OCI artifact reference or local path")
@click.option("--env", default="dev", help="Target environment")
@click.option("--output", "-o", default="-", help="Output file or - for stdout")
def helm_generate(artifact: str, env: str, output: str) -> None:
    """Generate Helm values from CompiledArtifacts."""
    artifacts = load_artifacts(artifact)
    generator = HelmValuesGenerator()
    values = generator.generate(artifacts, env)
    write_yaml(values, output)
```

---

## 8. GitOps Integration

### ArgoCD ApplicationSet Pattern

```yaml
# examples/argocd/applicationset.yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: floe-platform
spec:
  generators:
    - list:
        elements:
          - env: dev
            cluster: non-prod
            namespace: floe-dev
          - env: staging
            cluster: non-prod
            namespace: floe-staging
          - env: prod
            cluster: prod
            namespace: floe-prod
  template:
    metadata:
      name: 'floe-platform-{{env}}'
    spec:
      project: default
      source:
        repoURL: 'oci://registry/floe-platform'
        chart: floe-platform
        targetRevision: '{{env == "prod" ? "1.0.0" : "latest"}}'
        helm:
          valueFiles:
            - values-{{env}}.yaml
      destination:
        server: '{{cluster}}'
        namespace: '{{namespace}}'
```

---

## 9. Cluster Mapping Design

### ADR-0042 Implementation

**Epic 8C**: Logical environments (dev, qa, uat, staging, prod)
**Epic 9B**: Physical cluster mapping

```yaml
# values.yaml
clusterMapping:
  non-prod:
    cluster: aks-shared-nonprod
    environments: [dev, qa, uat, staging]
    namespaceTemplate: "floe-{{.environment}}"
    resources:
      preset: small  # dev/staging resource limits

  prod:
    cluster: aks-shared-prod
    environments: [prod]
    namespaceTemplate: "floe-prod"
    resources:
      preset: large  # production resource limits
```

---

## 10. Prior Decisions from Agent Memory

**Memory Search Results:**
1. Infrastructure parity: Tests run in same environment as production (K8s)
2. Chart structure: Organize into templates, values, charts directories
3. Helm v3 conventions: API version v2, dependency management via Chart.yaml

---

## Alternatives Considered

### PostgreSQL Strategy

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **A: Operator always** | Consistent, HA everywhere | Operator overhead for dev | Rejected |
| **B: StatefulSet always** | Simple | No HA for prod | Rejected |
| **C: Environment-specific** | Right-sized per env | Complexity | **Selected** |

### OTel Collector Mode

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **A: DaemonSet** | Node-level metrics | Overkill for app traces | Rejected |
| **B: Deployment** | Simpler, HPA works | Single point of collection | **Selected** |
| **C: Sidecar** | Per-pod isolation | Resource overhead | Rejected |

### Subchart Strategy

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **A: All custom** | Full control | Maintenance burden | Rejected |
| **B: All official** | Less maintenance | Some don't exist | Rejected |
| **C: Hybrid** | Best of both | Complexity | **Selected** |

---

## References

- [Dagster Helm Charts](https://dagster-io.github.io/helm/)
- [OpenTelemetry Collector Helm](https://open-telemetry.github.io/opentelemetry-helm-charts)
- [Apache Polaris Helm](https://polaris.apache.org/in-dev/unreleased/helm/)
- [Marquez Chart](https://github.com/MarquezProject/marquez/tree/main/chart)
- [CloudNativePG Documentation](https://cloudnative-pg.io/documentation/)
- ADR-0042: Logical vs Physical Environment Model

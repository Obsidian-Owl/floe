# Domain 07: Deployment and Operations

**Priority**: CRITICAL
**Total Requirements**: 50
**Status**: Complete specification

## Overview

This domain defines Kubernetes-native deployment patterns, Helm chart architecture, and testing infrastructure that enable floe to be deployed as a cloud-native data platform. All deployments use Kubernetes natively—no Docker Compose, no testcontainers, no local mock services.

**Core Architectural Principles**:
- **K8s-native only** (ADR-0017) - All tests and production deployments use Kubernetes
- **Infrastructure parity** (ADR-0017) - Tests run in Kind clusters with same Helm charts as production
- **Four-layer model** (four-layer-overview.md) - Layer 3 (Services) as Deployments, Layer 4 (Data) as Jobs
- **Configuration as code** (ADR-0019) - Helm charts versioned in repository

## Deployment Types (3 Total)

| Layer | Component | K8s Resource | Purpose | Requirements |
|-------|-----------|--------------|---------|--------------|
| Layer 3 | Services | Deployment, StatefulSet | Long-lived platforms (Dagster, Polaris, OTLP Collector, etc.) | REQ-600 to REQ-620 |
| Layer 3 | Databases | StatefulSet | Data stores (PostgreSQL, Redis, MinIO) | REQ-600 to REQ-620 |
| Layer 4 | Pipelines | Job, CronJob | Run-to-completion data jobs (dbt, dlt, quality checks) | REQ-600 to REQ-620 |

## Helm Charts (4 Total)

| Chart | Purpose | Configurable | Requirements |
|-------|---------|-------------|--------------|
| `charts/floe-platform/` | Meta-chart: deploys all platform services | Yes (values.yaml) | REQ-621 to REQ-635 |
| `charts/otel-collector/` | OTLP Collector and observability stack | Yes (values.yaml) | REQ-621 to REQ-635 |
| `charts/floe-jobs/` | Base chart for pipeline job templates | Yes (values.yaml) | REQ-621 to REQ-635 |
| `charts/floe-services/` | Optional: replaces floe-platform for minimal deployments | Yes (values.yaml) | REQ-621 to REQ-635 |

## Testing Infrastructure (K8s-Native)

| Level | Infrastructure | Use Case | Requirements |
|-------|----------------|----------|--------------|
| Unit | None (CI runner) | Fast, isolated logic tests | REQ-636 to REQ-650 |
| Integration | Kind cluster (1-2 nodes) | Component integration with minimal services | REQ-636 to REQ-650 |
| E2E | Kind cluster (3+ nodes) | Full platform workflow validation | REQ-636 to REQ-650 |
| Staging | EKS/GKE (external) | Soak tests, performance benchmarks | REQ-636 to REQ-650 |

## Key Architectural Decisions

- **ADR-0017**: Kubernetes-Based Testing Infrastructure
- **ADR-0019**: Platform Services Lifecycle
- **ADR-0016**: Platform Enforcement Architecture (validation in K8s)
- **four-layer-overview.md**: Four-layer architecture model

## Requirements Files

- [01-kubernetes-model.md](01-kubernetes-model.md) - REQ-600 to REQ-620: K8s resources, networking, resource management
- [02-helm-charts.md](02-helm-charts.md) - REQ-621 to REQ-635: Helm chart structure and configuration
- [03-testing-infrastructure.md](03-testing-infrastructure.md) - REQ-636 to REQ-650: Kind clusters, test execution, result collection

## Traceability Matrix

| Requirement Range | ADR | Architecture Doc | Implementation |
|------------------|-----|------------------|-----------------|
| REQ-600 to REQ-620 | ADR-0017, ADR-0016 | four-layer-overview.md, platform-services.md | K8s manifests in charts/ |
| REQ-621 to REQ-635 | ADR-0019 | helm-deployment-guide.md | Helm charts (floe-platform, otel-collector, floe-jobs) |
| REQ-636 to REQ-650 | ADR-0017 | TESTING.md | testing/k8s/, tests/integration/, tests/e2e/ |

## Epic Mapping

This domain's requirements are satisfied across Epics:

- **Epic 2: K8s-Native Testing** (Phase 2A-2C)
  - REQ-636 to REQ-650: Kind clusters, test execution, test organization

- **Epic 6: OCI Registry** (Phase 4B-4C)
  - REQ-600 to REQ-620: Container image distribution
  - REQ-621 to REQ-635: Helm chart distribution (OCI registry)

- **Epic 7: Enforcement Engine** (Phase 5A-5B)
  - REQ-600 to REQ-620: K8s resource constraints enforce platform governance

## Validation Criteria

Domain 07 is complete when:

- [ ] All 50 requirements documented with complete template fields
- [ ] Helm charts pass `helm lint` for all environments (dev, staging, prod)
- [ ] Kind cluster creation and tear-down automated in CI
- [ ] All integration and E2E tests run in Kind clusters
- [ ] Test runner image built and published to GitHub Container Registry
- [ ] Helm chart validation tests pass (chart deploys, services ready)
- [ ] K8s resource limits and requests documented and enforced
- [ ] Network policies defined and tested
- [ ] ADRs backreference requirements
- [ ] Architecture docs backreference requirements
- [ ] TESTING.md updated with K8s-native testing guidance

## Notes

- **Breaking Change**: Docker Compose is REMOVED in target state (requires K8s for all deployments)
- **Migration Path**: See MIGRATION-ROADMAP.md Epic 2 for Docker Compose → Kind migration
- **Local Development**: Developers run Kind clusters locally with `make test-k8s`
- **CI/CD**: GitHub Actions workflows use `helm/kind-action` for ephemeral clusters
- **Production**: Same Helm charts used in dev/staging/production (environment-specific values.yaml overrides)

## Layer 3/4 Integration

**Layer 3 (Services)**: Long-lived Kubernetes Deployments
```
Dagster Webserver (Deployment)
├─ PostgreSQL (StatefulSet)
├─ Dagster Daemon (Deployment)
└─ Worker nodes (scaling)

Polaris Catalog Server (Deployment)
├─ PostgreSQL (StatefulSet)
└─ Iceberg Metadata (Iceberg Catalog)

OTLP Collector (Deployment)
├─ Jaeger Backend (StatefulSet, optional)
├─ Prometheus (StatefulSet, optional)
└─ Grafana (Deployment, optional)

Cube Semantic Layer (Deployment)
├─ Redis (StatefulSet)
└─ PostgreSQL (StatefulSet)
```

**Layer 4 (Data)**: Kubernetes Jobs
```
dbt run (K8s Job)
├─ Input: Iceberg tables via Polaris catalog
└─ Output: Transformed Iceberg tables

dlt ingestion (K8s Job)
├─ Input: External system (API, database)
└─ Output: Raw Iceberg tables

Quality checks (K8s Job)
├─ Input: Iceberg tables
└─ Output: Quality metrics (success/failure)

Dagster-orchestrated jobs (K8s Job)
├─ Input: Asset definitions
├─ Execution: dbt, dlt, quality checks
└─ Output: Materialized assets
```

## References

- **ADR-0017**: Kubernetes-Based Testing Infrastructure
- **ADR-0019**: Platform Services Lifecycle
- **ADR-0016**: Platform Enforcement Architecture
- **four-layer-overview.md**: Four-layer architecture
- **TESTING.md**: Testing strategy and execution
- **MIGRATION-ROADMAP.md**: Epic 2 for K8s migration

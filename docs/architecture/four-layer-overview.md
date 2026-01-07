# Four-Layer Architecture Overview

This document provides a comprehensive overview of floe's four-layer architecture.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: DATA LAYER (Ephemeral Jobs)                                        │
│  Owner: Data Engineers                                                       │
│  K8s Resources: Jobs (run-to-completion)                                    │
│  Config: floe.yaml                                                          │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  • dbt run pods           → Execute transformations                   │  │
│  │  • dlt ingestion jobs     → Load external data                       │  │
│  │  • Quality check jobs     → Validate data quality                    │  │
│  │  • Orchestrator workers   → Scaled by orchestrator as needed         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Lifecycle: Run-to-completion, stateless, per-execution pods               │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      │ Connects to (K8s Service Discovery)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: SERVICES LAYER (Long-lived)                                        │
│  Owner: Platform Engineers                                                   │
│  K8s Resources: Deployments, StatefulSets                                   │
│  Deployment: `floe platform deploy`                                         │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ORCHESTRATOR          CATALOG           SEMANTIC        OBSERVABILITY│   │
│  │  ┌─────────────┐      ┌─────────────┐   ┌──────────┐   ┌───────────┐ │   │
│  │  │ Dagster     │      │ Polaris     │   │ Cube     │   │ OTLP      │ │   │
│  │  │ Webserver   │      │ Server      │   │ Server   │   │ Collector │ │   │
│  │  │ Daemon      │      │             │   │          │   │ Prometheus│ │   │
│  │  │ PostgreSQL  │      │ PostgreSQL  │   │ Redis    │   │ Grafana   │ │   │
│  │  └─────────────┘      └─────────────┘   └──────────┘   └───────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Lifecycle: Always running, rolling updates, stateful (databases, caches)  │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      │ Configured by
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: CONFIGURATION LAYER (Enforcement)                                  │
│  Owner: Platform Engineers                                                   │
│  Storage: OCI Registry (immutable, versioned)                               │
│  Config: manifest.yaml                                             │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  • Plugin selection (compute, orchestrator, catalog, semantic)      │    │
│  │  • Governance policies (classification, access control, retention)  │    │
│  │  • Data architecture rules (medallion/kimball, naming conventions)  │    │
│  │  • Quality gates (test coverage, required tests, block/warn/notify) │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Lifecycle: Versioned artifacts, rarely changes, published to OCI registry │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      │ Built on
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: FOUNDATION LAYER (Framework Code)                                  │
│  Owner: floe Maintainers                                            │
│  Distribution: PyPI, Helm registry                                          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  floe-core      │ Schemas, interfaces, enforcement engine           │    │
│  │  floe-cli       │ CLI for Platform Team and Data Team               │    │
│  │  floe-dbt       │ dbt framework (ENFORCED); runtime PLUGGABLE       │    │
│  │  floe-iceberg   │ Iceberg utilities (ENFORCED)                      │    │
│  │  plugins/*      │ Pluggable implementations                         │    │
│  │  charts/*       │ Helm charts for deployment                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ENFORCED STANDARDS: Iceberg, OTel, OpenLineage, dbt framework, K8s-native │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Layer Details

### Layer 1: Foundation

The Foundation layer contains the core framework code that defines floe's capabilities.

| Package | Purpose | Distribution |
|---------|---------|--------------|
| `floe-core` | Schemas, interfaces, enforcement engine | PyPI |
| `floe-cli` | CLI for both personas | PyPI |
| `floe-dbt` | dbt framework integration (enforced); runtime via DBTPlugin (pluggable) | PyPI |
| `floe-iceberg` | Iceberg utilities (enforced) | PyPI |
| `plugins/*` | Pluggable implementations | PyPI |
| `charts/*` | Helm charts | Helm registry |

**Enforced Standards:**
- Apache Iceberg (table format)
- OpenTelemetry (observability)
- OpenLineage (data lineage)
- dbt (transformation framework - SQL compilation ENFORCED; execution environment PLUGGABLE via ADR-0043)
- Kubernetes-native (deployment)

### Layer 2: Configuration

The Configuration layer contains platform artifacts that enforce guardrails.

**Artifact Storage:** OCI Registry (immutable, versioned, signed)

**Contents:**
- Plugin selection configuration
- Governance policies (classification, access control)
- Data architecture rules (naming conventions, layer constraints)
- Quality gates (test coverage, required tests)

**Workflow:**
```bash
floe platform compile    # Build artifacts
floe platform test       # Run policy tests
floe platform publish    # Push to OCI registry
```

### Layer 3: Services

The Services layer contains long-lived services that support data operations.

| Service Type | Examples | K8s Resource |
|--------------|----------|--------------|
| Orchestrator | Dagster webserver, daemon | Deployment |
| Catalog | Polaris server | Deployment |
| Semantic Layer | Cube server | Deployment |
| Observability | OTLP Collector, Prometheus | Deployment |
| Databases | PostgreSQL | StatefulSet |
| Caches | Redis | StatefulSet |
| Storage | MinIO | StatefulSet |

**Deployment:**
```bash
floe platform deploy     # Deploy all services
floe platform status     # Check health
floe platform logs       # View logs
```

### Layer 4: Data

The Data layer contains ephemeral jobs that execute data operations.

| Job Type | Trigger | K8s Resource |
|----------|---------|--------------|
| dbt run | Schedule/manual | Job |
| dbt test | Post-run | Job |
| dlt ingestion | Schedule | Job |
| Quality checks | Post-run | Job |

**Execution:**
```bash
floe init --platform=v1.2.3  # Pull platform artifacts
floe compile                  # Validate against platform
floe run                      # Execute pipeline
```

## Layer Boundaries

| Aspect | Layer 3 (Services) | Layer 4 (Data) |
|--------|-------------------|----------------|
| K8s Resource | Deployment, StatefulSet | Job |
| Lifecycle | Long-lived, upgraded | Run-to-completion |
| State | Stateful | Stateless |
| Scaling | Fixed replicas or HPA | Per-execution |
| Owner | Platform Team | Data Team (execution) |
| Deployment | `floe platform deploy` | Triggered by orchestrator |

## Ownership Model

| Layer | Owner | Responsibilities |
|-------|-------|-----------------|
| Foundation | floe maintainers | Framework code, releases |
| Configuration | Platform Team | Plugin selection, policies, architecture |
| Services | Platform Team | Deploy, upgrade, operate |
| Data | Data Team | Pipeline code, transforms, schedules |

## Data Mesh Extension

The four-layer architecture extends to support Data Mesh deployments with federated domain ownership:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 4: DATA PRODUCTS (Ephemeral)                                          │
│  • Data product pipelines run as K8s Jobs                                   │
│  • Each product has defined input/output ports                              │
│  • Cross-domain dependencies tracked via data contracts                     │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┴────────────────────────────────────────┐
│  Layer 3: DOMAIN SERVICES (Long-lived, per-domain)                           │
│  • Orchestrator per domain (domain autonomy)                                │
│  • Domain-specific semantic layer                                           │
│  • Connected to shared catalog and observability                            │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┴────────────────────────────────────────┐
│  Layer 2: FEDERATED CONFIGURATION                                            │
│  • Enterprise manifest: Global governance, approved plugins                 │
│  • Domain manifest: Domain-specific choices, namespace                      │
│  • Inheritance: Enterprise → Domain → Product                               │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┴────────────────────────────────────────┐
│  Layer 1: FOUNDATION (Same as centralized)                                   │
│  • Additional schemas: EnterpriseManifest, DomainManifest, DataProduct     │
│  • Additional CLI: floe enterprise/domain/product commands                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

See [ADR-0021: Data Architecture Patterns](adr/0021-data-architecture-patterns.md) for full Data Mesh documentation.

## Related Documents

- [ADR-0016: Platform Enforcement Architecture](adr/0016-platform-enforcement-architecture.md)
- [ADR-0019: Platform Services Lifecycle](adr/0019-platform-services-lifecycle.md)
- [ADR-0021: Data Architecture Patterns](adr/0021-data-architecture-patterns.md)
- [Platform Enforcement](platform-enforcement.md)
- [Platform Services](platform-services.md)

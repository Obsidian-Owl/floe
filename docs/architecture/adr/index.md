# Architecture Decision Records

This directory contains all Architecture Decision Records (ADRs) for floe.

## ADR Numbering Policy

ADR numbers are **immutable** once assigned. Gaps in numbering occur when:
- ADRs are rejected or withdrawn
- ADRs are superseded and merged into others
- Numbers are reserved for future use

**Missing Numbers**:
- **0002, 0003, 0004**: Historical gaps (pre-documentation system)
- **0013**: Merged into ADR-0012 (Data Classification)

## ADR Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-cube-semantic-layer.md) | Use Cube for Semantic/Consumption Layer | Accepted |
| [0005](0005-iceberg-table-format.md) | Apache Iceberg as Enforced Table Format | Accepted |
| [0006](0006-opentelemetry-observability.md) | Use OpenTelemetry for Observability | Accepted |
| [0007](0007-openlineage-from-start.md) | Include OpenLineage from Start | Accepted |
| [0008](0008-repository-split.md) | Standalone Repository Architecture | Accepted |
| [0009](0009-dbt-owns-sql.md) | dbt Owns SQL Transformation | Accepted |
| [0010](0010-target-agnostic-compute.md) | Target-Agnostic Compute | Accepted |
| [0011](0011-pluggable-orchestration.md) | Pluggable Orchestration via OrchestratorPlugin | Accepted |
| [0012](0012-data-classification-governance.md) | Data Classification and Governance | Accepted |
| [0014](0014-flink-streaming-deferred.md) | Flink for Streaming Workloads | Deferred |
| [0015](0015-policy-enforcement.md) | Policy Enforcement Plugin Interface | Accepted |
| [0016](0016-platform-enforcement-architecture.md) | Platform Enforcement Architecture | Accepted |
| [0017](0017-k8s-testing-infrastructure.md) | Kubernetes-Based Testing Infrastructure | Accepted |
| [0018](0018-opinionation-boundaries.md) | Opinionation Boundaries | Accepted |
| [0019](0019-platform-services-lifecycle.md) | Platform Services Lifecycle | Accepted |
| [0020](0020-ingestion-plugins.md) | Ingestion Plugins | Accepted |
| [0021](0021-data-architecture-patterns.md) | Data Architecture Patterns | Accepted |
| [0022](0022-security-rbac-model.md) | Security & RBAC Model | Accepted |
| [0023](0023-secrets-management.md) | Secrets Management Architecture | Accepted |
| [0024](0024-identity-access-management.md) | Identity and Access Management | Accepted |
| [0025](0025-plugin-error-taxonomy.md) | Plugin Error Taxonomy | Accepted |
| [0026](0026-data-contract-architecture.md) | Data Contract Architecture | Accepted |
| [0027](0027-odcs-standard-adoption.md) | ODCS Standard Adoption | Accepted |
| [0028](0028-runtime-contract-monitoring.md) | Runtime Contract Monitoring | Accepted |
| [0029](0029-contract-lifecycle-management.md) | Contract Lifecycle Management | Accepted |
| [0030](0030-namespace-identity.md) | Namespace-Based Identity | Accepted |
| [0031](0031-infisical-secrets.md) | Infisical as Default Secrets Management | Accepted |
| [0032](0032-cube-compute-integration.md) | Semantic Layer Compute Plugin Integration | Accepted |
| [0033](0033-airflow-3x.md) | Target Airflow 3.x | Accepted |
| [0034](0034-dbt-duckdb-iceberg.md) | dbt-duckdb Iceberg Catalog Workaround | Accepted |
| [0035](0035-observability-plugin-interface.md) | Observability Plugin Interface | Accepted |
| [0036](0036-storage-plugin-interface.md) | Storage Plugin Interface | Accepted |
| [0037](0037-composability-principle.md) | Composability as Core Principle | Accepted |
| [0038](0038-data-mesh-architecture.md) | Data Mesh Architecture | Accepted |
| [0039](0039-multi-environment-promotion.md) | Multi-Environment Artifact Promotion | Accepted |
| [0040](0040-artifact-immutability-gc.md) | Artifact Immutability and Garbage Collection | Accepted |
| [0041](0041-artifact-signing-verification.md) | Artifact Signing and Verification | Accepted |
| [0042](0042-linear-beads-traceability.md) | Linear + Beads Traceability Integration | Accepted |
| [0043](0043-dbt-runtime-abstraction.md) | dbt Compilation Environment Abstraction | Accepted |
| [0044](0044-unified-data-quality-plugin.md) | Unified Data Quality Plugin Architecture | Accepted |
| [0045](0045-compilation-caching-strategy.md) | Compilation Caching Strategy | Accepted |
| [0046](0046-agent-memory-architecture.md) | Agent Memory Architecture (Cognee) | Proposed |

## Categories

### Foundation
- [0005](0005-iceberg-table-format.md) - **Apache Iceberg as enforced table format**
- [0008](0008-repository-split.md) - Repository structure and plugin architecture
- [0016](0016-platform-enforcement-architecture.md) - Four-layer architecture and platform enforcement
- [0017](0017-k8s-testing-infrastructure.md) - Testing infrastructure
- [0018](0018-opinionation-boundaries.md) - Enforced vs pluggable boundaries
- [0037](0037-composability-principle.md) - **Composability as core architectural principle**

### Data Pipeline
- [0009](0009-dbt-owns-sql.md) - dbt as transformation engine
- [0010](0010-target-agnostic-compute.md) - Compute target flexibility
- [0020](0020-ingestion-plugins.md) - dlt/Airbyte ingestion
- [0021](0021-data-architecture-patterns.md) - Medallion, Data Mesh patterns
- [0034](0034-dbt-duckdb-iceberg.md) - **dbt-duckdb Iceberg catalog workaround (CRITICAL)**
- [0038](0038-data-mesh-architecture.md) - **Data Mesh with unified Manifest schema**
- [0043](0043-dbt-runtime-abstraction.md) - **dbt compilation environment abstraction (local/fusion/cloud)**
- [0045](0045-compilation-caching-strategy.md) - **Content-addressable caching for compilation stages**

### Observability & Governance
- [0006](0006-opentelemetry-observability.md) - OpenTelemetry integration
- [0007](0007-openlineage-from-start.md) - OpenLineage lineage tracking
- [0012](0012-data-classification-governance.md) - Data classification
- [0015](0015-policy-enforcement.md) - **Policy enforcement plugin interface (compile-time code quality)**
- [0044](0044-unified-data-quality-plugin.md) - **Unified data quality plugin (Great Expectations, Soda, custom)**

### Platform Services
- [0001](0001-cube-semantic-layer.md) - Cube semantic layer
- [0011](0011-pluggable-orchestration.md) - **Pluggable orchestration via OrchestratorPlugin (Dagster, Airflow, Prefect)**
- [0019](0019-platform-services-lifecycle.md) - Service lifecycle management
- [0032](0032-cube-compute-integration.md) - **Cube delegates to compute plugin (DuckDB-first)**
- [0033](0033-airflow-3x.md) - **Target Airflow 3.x orchestration**
- [0035](0035-observability-plugin-interface.md) - **Pluggable observability backends (Jaeger, Datadog, Grafana Cloud)**
- [0036](0036-storage-plugin-interface.md) - **Pluggable storage backends (S3, GCS, Azure, MinIO)**

### Security
- [0022](0022-security-rbac-model.md) - RBAC, network policies, pod security
- [0023](0023-secrets-management.md) - Secrets management architecture (superseded by 0031)
- [0024](0024-identity-access-management.md) - Identity providers (Keycloak, Dex, Okta)
- [0031](0031-infisical-secrets.md) - **Infisical as default OSS secrets (supersedes 0023)**

### Data Contracts
- [0026](0026-data-contract-architecture.md) - Data contract architecture and enforcement
- [0027](0027-odcs-standard-adoption.md) - ODCS v3 standard adoption
- [0028](0028-runtime-contract-monitoring.md) - Runtime contract monitoring
- [0029](0029-contract-lifecycle-management.md) - Contract versioning and lifecycle
- [0030](0030-namespace-identity.md) - Namespace-based product and contract identity

### Artifact Distribution
- [0039](0039-multi-environment-promotion.md) - **Multi-environment promotion with GitOps workflows (dev → staging → prod)**
- [0040](0040-artifact-immutability-gc.md) - **Artifact immutability and garbage collection (Harbor, ECR, ACR, GAR)**
- [0041](0041-artifact-signing-verification.md) - **Artifact signing and verification (Cosign, keyless + key-based signing)**

### Deferred
- [0014](0014-flink-streaming-deferred.md) - Streaming workloads (V2.0)

### Contributor Tooling
- [0042](0042-linear-beads-traceability.md) - **Linear + Beads for requirements traceability**
- [0046](0046-agent-memory-architecture.md) - **Cognee integration for AI agent persistent memory**

## Related Documentation

- [Architecture Overview](../ARCHITECTURE-SUMMARY.md)
- [Contracts](../../contracts/index.md)
- [Guides](../../guides/index.md)

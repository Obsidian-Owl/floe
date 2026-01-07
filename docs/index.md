# floe Documentation

This directory contains documentation for floe - the open source Data Execution Layer.

## Overview

floe is an Apache 2.0 licensed Python framework that provides:
- Data pipeline orchestration (Dagster)
- SQL transformations (dbt)
- Open table format (Apache Iceberg)
- Iceberg catalog (Apache Polaris)
- Semantic layer (Cube)
- Observability (OpenTelemetry, OpenLineage)

## Documentation Structure

| Section | Description |
|---------|-------------|
| [architecture/](./architecture/) | Runtime architecture documentation |
| [architecture/adr/](./architecture/adr/) | Architecture Decision Records |
| [contracts/](./contracts/) | Interface contracts (schema ownership) |
| [guides/](./guides/) | arc42 implementation guides |

## Architecture Documentation

| Document | Description |
|----------|-------------|
| [four-layer-overview](./architecture/four-layer-overview.md) | Four-layer architecture |
| [platform-enforcement](./architecture/platform-enforcement.md) | Platform enforcement model |
| [platform-services](./architecture/platform-services.md) | Long-lived services |
| [plugin-architecture](./architecture/plugin-architecture.md) | Plugin system design |
| [interfaces](./architecture/interfaces/index.md) | Plugin interface definitions |
| [opinionation-boundaries](./architecture/opinionation-boundaries.md) | Enforced vs pluggable |
| [platform-artifacts](./architecture/platform-artifacts.md) | OCI artifact storage |
| [compiled-artifacts](./contracts/compiled-artifacts.md) | Compiled artifacts schema |

## arc42 Guides

| Document | Description |
|----------|-------------|
| [00-overview](./guides/00-overview.md) | Document overview |
| [01-constraints](./guides/01-constraints.md) | Technical constraints |
| [02-context](./guides/02-context.md) | System context |
| [03-solution-strategy](./guides/03-solution-strategy.md) | Solution strategy |
| [04-building-blocks](./guides/04-building-blocks.md) | Building blocks |
| [05-runtime-view](./guides/05-runtime-view.md) | Runtime behavior |
| [06-deployment-view](./guides/06-deployment-view.md) | Deployment |
| [07-crosscutting](./guides/07-crosscutting.md) | Cross-cutting concerns |
| [10-glossary](./guides/10-glossary.md) | Terminology |

## Architecture Decision Records

| ADR | Title |
|-----|-------|
| [0001](./architecture/adr/0001-cube-semantic-layer.md) | Cube Semantic Layer |
| [0006](./architecture/adr/0006-opentelemetry-observability.md) | OpenTelemetry Observability |
| [0007](./architecture/adr/0007-openlineage-from-start.md) | OpenLineage from Start |
| [0008](./architecture/adr/0008-repository-split.md) | Repository Split |
| [0009](./architecture/adr/0009-dbt-owns-sql.md) | dbt Owns SQL |
| [0010](./architecture/adr/0010-target-agnostic-compute.md) | Target-Agnostic Compute |
| [0012](./architecture/adr/0012-data-classification-governance.md) | Data Classification Governance |
| [0014](./architecture/adr/0014-flink-streaming-deferred.md) | Flink Streaming Deferred |
| [0016](./architecture/adr/0016-platform-enforcement-architecture.md) | Platform Enforcement Architecture |
| [0017](./architecture/adr/0017-k8s-testing-infrastructure.md) | K8s Testing Infrastructure |
| [0018](./architecture/adr/0018-opinionation-boundaries.md) | Opinionation Boundaries |
| [0019](./architecture/adr/0019-platform-services-lifecycle.md) | Platform Services Lifecycle |
| [0020](./architecture/adr/0020-ingestion-plugins.md) | Ingestion Plugins |
| [0021](./architecture/adr/0021-data-architecture-patterns.md) | Data Architecture Patterns |
| [0022](./architecture/adr/0022-security-rbac-model.md) | Security & RBAC Model |
| [0023](./architecture/adr/0023-secrets-management.md) | Secrets Management |
| [0024](./architecture/adr/0024-identity-access-management.md) | Identity Access Management |

## Contracts

| Contract | Description |
|----------|-------------|
| [CompiledArtifacts](./contracts/compiled-artifacts.md) | Runtime configuration schema |
| [Observability Attributes](./contracts/observability-attributes.md) | OpenTelemetry conventions |
| [Glossary](./contracts/glossary.md) | Shared terminology |

## Related Documentation

- [Contracts](./contracts/) - Interface contract specifications

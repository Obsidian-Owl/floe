# Architecture Documentation

This directory contains the architectural documentation for floe.

## Overview

- [Architecture Summary](ARCHITECTURE-SUMMARY.md) - Executive overview of floe architecture

## Core Architecture

| Document | Description |
|----------|-------------|
| [Four-Layer Overview](four-layer-overview.md) | Foundation, Configuration, Services, and Data layers |
| [Platform Enforcement](platform-enforcement.md) | How platform constraints are enforced at compile time |
| [Platform Services](platform-services.md) | Layer 3 long-lived services (Dagster, Polaris, Cube, etc.) |
| [Plugin Architecture](plugin-system/index.md) | Plugin system design and entry point registration |
| [Opinionation Boundaries](opinionation-boundaries.md) | What's enforced vs pluggable |
| [Interfaces](interfaces/index.md) | Abstract Base Classes for all plugin types |
| [Platform Artifacts](platform-artifacts.md) | OCI registry storage for platform configurations |
| [Storage Integration](storage-integration.md) | Object storage (MinIO/S3/GCS/Azure) + Iceberg |
| [OCI Registry Requirements](oci-registry-requirements.md) | Registry configuration, signing, air-gapped deployment |

## Architecture Decision Records

See [ADR Index](adr/index.md) for all Architecture Decision Records.

### Key ADRs

| ADR | Decision |
|-----|----------|
| [0016](adr/0016-platform-enforcement-architecture.md) | Four-layer architecture with compile-time enforcement |
| [0018](adr/0018-opinionation-boundaries.md) | Enforced (Iceberg, dbt, K8s) vs Pluggable (compute, orchestrator) |
| [0021](adr/0021-data-architecture-patterns.md) | Medallion default, Data Mesh support |
| [0022](adr/0022-security-rbac-model.md) | Security: RBAC, network policies, pod security |
| [0023](adr/0023-secrets-management.md) | Secrets: K8s Secrets, ESO, Vault backends |
| [0024](adr/0024-identity-access-management.md) | Identity: Keycloak default, pluggable IdPs |

## Related Documentation

- [Contracts](../contracts/index.md) - Interface contracts and schemas
- [Guides](../guides/index.md) - Implementation guides (Arc42 structure)
- [floe Root](../index.md) - Main documentation index

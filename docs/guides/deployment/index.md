# 06. Deployment View

This document describes deployment architecture for floe, covering the separation between platform services (long-lived) and pipeline jobs (ephemeral).

## Deployment Options Overview

| Option | Use Case | Complexity |
|--------|----------|------------|
| **Local (uv)** | Development, single user | Low |
| **Docker Compose** | Development, evaluation | Low |
| **Kubernetes (Helm)** | Production, team use | Medium |

## Section Index

| Section | Description |
|---------|-------------|
| [Two-Layer Model](two-layer-model.md) | Platform Services vs Pipeline Jobs |
| [Local Development](local-development.md) | Local (uv) and Docker Compose setup |
| [Kubernetes Helm](kubernetes-helm.md) | Helm chart structure and installation |
| [Production](production.md) | HA, scaling, monitoring, backups |
| [Data Mesh](data-mesh.md) | Federated Data Mesh deployment topology |

## Deployment Comparison

| Aspect | Local | Docker Compose | Kubernetes | Data Mesh |
|--------|-------|----------------|------------|-----------|
| **Setup time** | 5 min | 10 min | 30 min | 1+ hour |
| **Scalability** | Single user | Single host | Multi-node | Multi-cluster |
| **HA** | No | No | Yes | Yes |
| **Persistence** | File-based | Docker volumes | PVCs + RDS | PVCs + RDS |
| **Observability** | Minimal | Full stack | Full stack | Federated |
| **Cost** | Free | Free | Cloud costs | Higher cloud costs |
| **Use case** | Development | Evaluation | Production | Enterprise |
| **Domain isolation** | N/A | N/A | Namespaces | Namespaces or clusters |

## Quick Navigation

### Getting Started
- [Two-Layer Model](two-layer-model.md) - Understand the deployment model
- [Local Development](local-development.md) - Start developing locally

### Production Deployment
- [Kubernetes Helm](kubernetes-helm.md) - Deploy to Kubernetes
- [Production](production.md) - Production-ready configuration
- [Data Mesh](data-mesh.md) - Multi-domain enterprise deployment

## Related Documentation

- [Platform Services](../../architecture/platform-services.md) - Layer 3 services detail
- [ADR-0019: Platform Services Lifecycle](../../architecture/adr/0019-platform-services-lifecycle.md) - Lifecycle decisions

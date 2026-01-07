# 06. Deployment View

> **This document has been split for LLM context efficiency.**
>
> The deployment documentation is now organized in the [`deployment/`](deployment/index.md) directory.

## Quick Navigation

| Section | Description |
|---------|-------------|
| [Deployment Overview](deployment/index.md) | Main index and comparison |
| [Two-Layer Model](deployment/two-layer-model.md) | Platform Services vs Pipeline Jobs |
| [Local Development](deployment/local-development.md) | Local (uv) and Docker Compose setup |
| [Kubernetes Helm](deployment/kubernetes-helm.md) | Helm chart structure and installation |
| [Production](deployment/production.md) | HA, scaling, monitoring, backups |
| [Data Mesh](deployment/data-mesh.md) | Federated Data Mesh deployment topology |

## Deployment Options Overview

| Option | Use Case | Complexity |
|--------|----------|------------|
| **Local (uv)** | Development, single user | Low |
| **Docker Compose** | Development, evaluation | Low |
| **Kubernetes (Helm)** | Production, team use | Medium |

For complete documentation, see [deployment/index.md](deployment/index.md).

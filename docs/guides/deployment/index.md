# Deployment Guides

Floe's product deployment model is bring any conformant Kubernetes cluster. Platform Engineers deploy Floe with manifests, Helm, and their organization's Kubernetes access model.

## Current Deployment Paths

| Path | Status | Use Case |
| --- | --- | --- |
| Kubernetes with Helm | Alpha-supported | Deploy Floe platform services to a Kubernetes cluster |
| Local Kind evaluation | Alpha-supported for evaluation and contributor smoke checks | Try Floe on a disposable local cluster |
| GitOps with Flux | Implemented example | Deploy public OCI chart releases and compiled values through Flux |
| Data Mesh operations | Implemented primitives and planned operations | Understand the architecture without treating it as an alpha deployment path |

## Start Here

- [Platform Engineer first platform guide](../../platform-engineers/first-platform.md)
- [Kubernetes Helm](kubernetes-helm.md)
- [Local Kind evaluation](local-development.md)
- [GitOps with Flux](gitops-flux.md)
- [Data Mesh status](data-mesh.md)
- [Capability status](../../architecture/capability-status.md)

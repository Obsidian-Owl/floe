# ADR-0042: Logical vs Physical Environment Model

**Status**: Accepted
**Date**: 2026-01-30
**Deciders**: Platform Team
**Epic**: 8C (Promotion Lifecycle), 9B (Helm Charts)

## Context

Enterprise deployments require flexibility in environment configuration:
- Some organizations need 3 environments (dev, staging, prod)
- Others need 5+ (dev, qa, uat, performance, staging, prod)
- Cost optimization often requires sharing physical clusters across multiple logical environments

The question is: should the promotion lifecycle (Epic 8C) be aware of physical cluster topology, or should it operate purely on logical environments?

## Decision

**We separate logical environments (Epic 8C) from physical deployment targets (Epic 9B).**

### Epic 8C: Logical Environment Promotion

Epic 8C manages the **logical promotion pipeline**:
- User-defined environment names and promotion order via `manifest.yaml`
- Per-environment validation gates and policies
- Artifact tagging with environment suffixes (`v1.2.3-qa`, `v1.2.3-prod`)
- Promotion audit trail and signature verification

Configuration in `manifest.yaml`:
```yaml
artifacts:
  promotion:
    environments:
      - name: dev
        gates:
          policy_compliance: true
      - name: qa
        gates:
          policy_compliance: true
          tests: true
      - name: uat
        gates:
          policy_compliance: true
          tests: true
          security_scan: true
      - name: staging
        gates:
          policy_compliance: true
          tests: true
          security_scan: true
      - name: prod
        gates:
          policy_compliance: true
          tests: true
          security_scan: true
          cost_analysis: true
          performance_baseline: true
```

Default if not specified: `[dev, staging, prod]`

### Epic 9B: Physical Cluster Mapping

Epic 9B (Helm Charts) manages the **physical deployment topology**:
- Maps logical environments to physical K8s clusters
- Configures namespace isolation within shared clusters
- Applies per-environment RBAC, NetworkPolicy, ResourceQuotas

Example configuration in Helm values:
```yaml
# values-production.yaml
clusterMapping:
  # Multiple logical environments share one physical cluster
  non-prod:
    cluster: aks-shared-nonprod
    environments:
      - dev
      - qa
      - uat
      - staging
    isolation: namespace  # Each env gets its own namespace

  prod:
    cluster: aks-shared-prod
    environments:
      - prod
    isolation: namespace
```

### Enterprise Pattern Support

This separation enables the common enterprise "hybrid" pattern:

```
Logical Environments (Epic 8C):    Physical Clusters (Epic 9B):
┌─────────────────────────────┐    ┌─────────────────────────┐
│  dev → qa → uat → staging   │ →  │  aks-shared-nonprod     │
│          (validation gates)  │    │  (namespace isolation)  │
└─────────────────────────────┘    └─────────────────────────┘
              │
              ▼
┌─────────────────────────────┐    ┌─────────────────────────┐
│           prod              │ →  │  aks-shared-prod        │
│   (strictest gates)         │    │  (dedicated cluster)    │
└─────────────────────────────┘    └─────────────────────────┘
```

## Rationale

### Why Logical-Only for Epic 8C?

1. **Separation of Concerns**: Promotion validation (is this artifact ready?) is distinct from deployment location (where does it run?)

2. **Flexibility**: Organizations can change physical topology without modifying promotion pipelines

3. **Cost Optimization**: Multiple logical environments can share physical infrastructure while maintaining distinct validation gates

4. **Kubernetes Best Practices**: Aligns with [GKE enterprise multi-tenancy](https://cloud.google.com/kubernetes-engine/docs/best-practices/enterprise-multitenancy) patterns where namespace isolation provides logical separation within shared clusters

### Why Physical Mapping in Epic 9B?

1. **Helm's Responsibility**: Helm charts already handle cluster-specific configuration (ingress, storage classes, secrets)

2. **Infrastructure Coupling**: Physical cluster details (endpoints, credentials) belong in deployment tooling, not promotion logic

3. **GitOps Compatibility**: Environment-to-cluster mapping is typically managed via ArgoCD/Flux ApplicationSets

## Consequences

### Positive

- Enterprises can define 5+ logical environments with different validation rigor
- Organizations can optimize costs with 2 physical clusters (prod, non-prod)
- Promotion logic is portable across different physical topologies
- Clear contract between Epic 8C and Epic 9B

### Negative

- Two-step mental model (logical promotion, then physical deployment)
- Epic 9B must handle the cluster mapping complexity

### Neutral

- Existing `VerificationPolicy.environments` dict already supports arbitrary environment names
- No breaking changes to current schemas

## References

- [Google GKE Enterprise Multi-Tenancy](https://cloud.google.com/kubernetes-engine/docs/best-practices/enterprise-multitenancy)
- [Kubernetes Multi-Tenancy Guide 2024](https://overcast.blog/kubernetes-multi-tenancy-a-guide-for-2024-e485c048eae5)
- [Microsoft AKS Shared Clusters](https://techcommunity.microsoft.com/blog/azureinfrastructureblog/building-enterprise-grade-shared-aks-clusters-a-guide-to-multi-tenant-kubernetes/4468563)
- Epic 8C: Promotion Lifecycle spec
- Epic 9B: Helm Charts (pending specification)

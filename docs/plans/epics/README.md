# Epic Index

This directory contains detailed documentation for each of the 21 Epics.

---

## Status Legend

| Status | Meaning |
|--------|---------|
| Planned | Epic documented, not started |
| Spec | spec.md created via SpecKit |
| Tasks | tasks.md generated |
| Linear | Issues created in Linear |
| Active | Implementation in progress |
| Complete | All tasks done, tests passing |

---

## Epic Summary

| Epic | Title | Reqs | Status | Linear Project |
|------|-------|------|--------|----------------|
| **Foundation** |
| [1](01-foundation/epic-01-plugin-registry.md) | Plugin Registry | 10 | Planned | [floe-01-plugin-registry](https://linear.app/obsidianowl/project/floe-01-plugin-registry-c25c7e7d9d53) |
| **Configuration** |
| [2A](02-configuration/epic-02a-manifest-schema.md) | Manifest Schema | 16 | Planned | [floe-02a-manifest-schema](https://linear.app/obsidianowl/project/floe-02a-manifest-schema-56626c900a2b) |
| [2B](02-configuration/epic-02b-compilation-pipeline.md) | Compilation Pipeline | 13 | Planned | [floe-02b-compilation](https://linear.app/obsidianowl/project/floe-02b-compilation-3b5102b58136) |
| **Enforcement** |
| [3A](03-enforcement/epic-03a-policy-enforcer-core.md) | Policy Enforcer Core | 15 | Planned | [floe-03a-policy-enforcer](https://linear.app/obsidianowl/project/floe-03a-policy-enforcer-08a4f4df013c) |
| [3B](03-enforcement/epic-03b-policy-validation.md) | Policy Validation | 21 | Planned | [floe-03b-policy-validation](https://linear.app/obsidianowl/project/floe-03b-policy-validation-388fcbc3817f) |
| [3C](03-enforcement/epic-03c-data-contracts.md) | Data Contracts | 20 | Planned | [floe-03c-data-contracts](https://linear.app/obsidianowl/project/floe-03c-data-contracts-4b302490a939) |
| [3D](03-enforcement/epic-03d-contract-monitoring.md) | Contract Monitoring | 15 | Planned | [floe-03d-contract-monitoring](https://linear.app/obsidianowl/project/floe-03d-contract-monitoring-59262510ce7f) |
| **Core Plugins** |
| [4A](04-core-plugins/epic-04a-compute-plugin.md) | Compute Plugin | 10 | Planned | [floe-04a-compute-plugin](https://linear.app/obsidianowl/project/floe-04a-compute-plugin-3dce91e48fe9) |
| [4B](04-core-plugins/epic-04b-orchestrator-plugin.md) | Orchestrator Plugin | 10 | Planned | [floe-04b-orchestrator-plugin](https://linear.app/obsidianowl/project/floe-04b-orchestrator-plugin-1eb3abdc05d5) |
| [4C](04-core-plugins/epic-04c-catalog-plugin.md) | Catalog Plugin | 10 | Planned | [floe-04c-catalog-plugin](https://linear.app/obsidianowl/project/floe-04c-catalog-plugin-6cda94e2eb31) |
| [4D](04-core-plugins/epic-04d-storage-plugin.md) | Storage Plugin | 10 | Planned | [floe-04d-storage-plugin](https://linear.app/obsidianowl/project/floe-04d-storage-plugin-bb164b41d4c3) |
| **Transformation** |
| [5A](05-transformation/epic-05a-dbt-plugin.md) | dbt Plugin | 15 | Planned | [floe-05a-dbt-plugin](https://linear.app/obsidianowl/project/floe-05a-dbt-plugin-fc0710ba388c) |
| [5B](05-transformation/epic-05b-dataquality-plugin.md) | Data Quality Plugin | 10 | Planned | [floe-05b-dataquality-plugin](https://linear.app/obsidianowl/project/floe-05b-dataquality-plugin-f4a912739ba9) |
| **Observability** |
| [6A](06-observability/epic-06a-opentelemetry.md) | OpenTelemetry | 20 | Planned | [floe-06a-opentelemetry](https://linear.app/obsidianowl/project/floe-06a-opentelemetry-0e2e698e1f9b) |
| [6B](06-observability/epic-06b-openlineage.md) | OpenLineage | 21 | Planned | [floe-06b-openlineage](https://linear.app/obsidianowl/project/floe-06b-openlineage-674cba04e924) |
| **Security** |
| [7A](07-security/epic-07a-identity-secrets.md) | Identity & Secrets | 25 | Planned | [floe-07a-identity-secrets](https://linear.app/obsidianowl/project/floe-07a-identity-secrets-f4ffc9929758) |
| [7B](07-security/epic-07b-k8s-rbac.md) | K8s RBAC | 16 | Planned | [floe-07b-k8s-rbac](https://linear.app/obsidianowl/project/floe-07b-k8s-rbac-f6aa70e4c792) |
| [7C](07-security/epic-07c-network-pod-security.md) | Network & Pod Security | 27 | Planned | [floe-07c-network-pod-security](https://linear.app/obsidianowl/project/floe-07c-network-pod-security-900c829e6300) |
| **Artifact Distribution** |
| [8A](08-artifact-distribution/epic-08a-oci-client.md) | OCI Client | 16 | Planned | [floe-08a-oci-client](https://linear.app/obsidianowl/project/floe-08a-oci-client-a33dd725a781) |
| [8B](08-artifact-distribution/epic-08b-artifact-signing.md) | Artifact Signing | 10 | Planned | [floe-08b-artifact-signing](https://linear.app/obsidianowl/project/floe-08b-artifact-signing-f7781634af80) |
| [8C](08-artifact-distribution/epic-08c-promotion-lifecycle.md) | Promotion Lifecycle | 14 | Planned | [floe-08c-promotion-lifecycle](https://linear.app/obsidianowl/project/floe-08c-promotion-lifecycle-78acaf0b1d18) |
| **Deployment** |
| [9A](09-deployment/epic-09a-k8s-deployment.md) | K8s Deployment | 21 | Planned | [floe-09a-k8s-deployment](https://linear.app/obsidianowl/project/floe-09a-k8s-deployment-ac56ffa47013) |
| [9B](09-deployment/epic-09b-helm-charts.md) | Helm Charts | 15 | Planned | [floe-09b-helm-charts](https://linear.app/obsidianowl/project/floe-09b-helm-charts-14ba871f8309) |
| [9C](09-deployment/epic-09c-testing-infrastructure.md) | Testing Infrastructure | 15 | Planned | [floe-09c-testing-infra](https://linear.app/obsidianowl/project/floe-09c-testing-infra-bc1023480bf2) |

---

## By Category

### Foundation (Epic 1)
The blocking foundation - must complete before other work.
- [Epic 1: Plugin Registry](01-foundation/epic-01-plugin-registry.md)

### Configuration (Epics 2A-2B)
Schema and compilation pipeline.
- [Epic 2A: Manifest Schema](02-configuration/epic-02a-manifest-schema.md)
- [Epic 2B: Compilation Pipeline](02-configuration/epic-02b-compilation-pipeline.md)

### Enforcement (Epics 3A-3D)
Policy enforcement and data contracts.
- [Epic 3A: Policy Enforcer Core](03-enforcement/epic-03a-policy-enforcer-core.md)
- [Epic 3B: Policy Validation](03-enforcement/epic-03b-policy-validation.md)
- [Epic 3C: Data Contracts](03-enforcement/epic-03c-data-contracts.md)
- [Epic 3D: Contract Monitoring](03-enforcement/epic-03d-contract-monitoring.md)

### Core Plugins (Epics 4A-4D)
Plugin interfaces and reference implementations.
- [Epic 4A: Compute Plugin](04-core-plugins/epic-04a-compute-plugin.md)
- [Epic 4B: Orchestrator Plugin](04-core-plugins/epic-04b-orchestrator-plugin.md)
- [Epic 4C: Catalog Plugin](04-core-plugins/epic-04c-catalog-plugin.md)
- [Epic 4D: Storage Plugin](04-core-plugins/epic-04d-storage-plugin.md)

### Transformation (Epics 5A-5B)
dbt and data quality.
- [Epic 5A: dbt Plugin](05-transformation/epic-05a-dbt-plugin.md)
- [Epic 5B: Data Quality Plugin](05-transformation/epic-05b-dataquality-plugin.md)

### Observability (Epics 6A-6B)
OpenTelemetry and OpenLineage.
- [Epic 6A: OpenTelemetry](06-observability/epic-06a-opentelemetry.md)
- [Epic 6B: OpenLineage](06-observability/epic-06b-openlineage.md)

### Security (Epics 7A-7C)
Identity, RBAC, and network security.
- [Epic 7A: Identity & Secrets](07-security/epic-07a-identity-secrets.md)
- [Epic 7B: K8s RBAC](07-security/epic-07b-k8s-rbac.md)
- [Epic 7C: Network & Pod Security](07-security/epic-07c-network-pod-security.md)

### Artifact Distribution (Epics 8A-8C)
OCI registry and promotion workflow.
- [Epic 8A: OCI Client](08-artifact-distribution/epic-08a-oci-client.md)
- [Epic 8B: Artifact Signing](08-artifact-distribution/epic-08b-artifact-signing.md)
- [Epic 8C: Promotion Lifecycle](08-artifact-distribution/epic-08c-promotion-lifecycle.md)

### Deployment (Epics 9A-9C)
K8s deployment and testing infrastructure.
- [Epic 9A: K8s Deployment](09-deployment/epic-09a-k8s-deployment.md)
- [Epic 9B: Helm Charts](09-deployment/epic-09b-helm-charts.md)
- [Epic 9C: Testing Infrastructure](09-deployment/epic-09c-testing-infrastructure.md)

---

## Next Steps

1. Start with **Epic 1** (Plugin Registry) - it's the blocking foundation
2. Once Epic 1 is complete, **Wave 2** Epics can start in parallel
3. Use `/speckit.specify` to generate spec.md for each Epic
4. Use `/speckit.tasks` to generate tasks.md
5. Use `/speckit.taskstolinear` to create Linear issues
6. Use `/speckit.implement` to execute tasks

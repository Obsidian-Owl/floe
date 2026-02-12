# Epic Index

This directory contains detailed documentation for each of the 26 Epics.

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
| [3E](03-enforcement/epic-03e-governance-integration.md) | Governance Integration | 6 | Planned | [epic-3e-governance-integration](https://linear.app/obsidianowl/project/epic-3e-governance-integration-2ba5462f1c22) |
| **Core Plugins** |
| [4A](04-core-plugins/epic-04a-compute-plugin.md) | Compute Plugin | 10 | Planned | [floe-04a-compute-plugin](https://linear.app/obsidianowl/project/floe-04a-compute-plugin-3dce91e48fe9) |
| [4B](04-core-plugins/epic-04b-orchestrator-plugin.md) | Orchestrator Plugin | 10 | Planned | [floe-04b-orchestrator-plugin](https://linear.app/obsidianowl/project/floe-04b-orchestrator-plugin-1eb3abdc05d5) |
| [4C](04-core-plugins/epic-04c-catalog-plugin.md) | Catalog Plugin | 10 | Planned | [floe-04c-catalog-plugin](https://linear.app/obsidianowl/project/floe-04c-catalog-plugin-6cda94e2eb31) |
| [4D](04-core-plugins/epic-04d-storage-plugin.md) | Storage Plugin | 10 | Planned | [floe-04d-storage-plugin](https://linear.app/obsidianowl/project/floe-04d-storage-plugin-bb164b41d4c3) |
| [4E](04-core-plugins/epic-04e-semantic-layer-plugin.md) | Semantic Layer Plugin | 6 | Planned | [epic-4e-semantic-layer-plugin](https://linear.app/obsidianowl/project/epic-4e-semantic-layer-plugin-3c5addd80c14) |
| [4F](04-core-plugins/epic-04f-ingestion-plugin.md) | Ingestion Plugin | 6 | Planned | [epic-4f-ingestion-plugin](https://linear.app/obsidianowl/project/epic-4f-ingestion-plugin-0547e9605dc7) |
| [4G](04-core-plugins/epic-04g-reverse-etl.md) | Reverse ETL (SinkConnector) | 5 | Planned | [epic-4g-reverse-etl-sinkconnector](https://linear.app/obsidianowl/project/epic-4g-reverse-etl-sinkconnector-b69dd02b131d) |
| **Transformation** |
| [5A](05-transformation/epic-05a-dbt-plugin.md) | dbt Plugin | 15 | Planned | [floe-05a-dbt-plugin](https://linear.app/obsidianowl/project/floe-05a-dbt-plugin-fc0710ba388c) |
| [5B](05-transformation/epic-05b-dataquality-plugin.md) | Data Quality Plugin | 10 | Planned | [floe-05b-dataquality-plugin](https://linear.app/obsidianowl/project/floe-05b-dataquality-plugin-f4a912739ba9) |
| **Observability** |
| [6A](06-observability/epic-06a-opentelemetry.md) | OpenTelemetry | 20 | Planned | [floe-06a-opentelemetry](https://linear.app/obsidianowl/project/floe-06a-opentelemetry-0e2e698e1f9b) |
| [6B](06-observability/epic-06b-openlineage.md) | OpenLineage | 21 | Planned | [floe-06b-openlineage](https://linear.app/obsidianowl/project/floe-06b-openlineage-674cba04e924) |
| [6C](06-observability/epic-06c-otel-instrumentation.md) | OTel Code Instrumentation | 7 | Planned | [epic-6c-otel-code-instrumentation](https://linear.app/obsidianowl/project/epic-6c-otel-code-instrumentation-390eeee4c4ac) |
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
| **Contributor Tooling** |
| [10A](10-contributor/epic-10a-agent-memory.md) | Agent Memory (Cognee) | 12 | Planned | TBD |
| [10B](10-contributor/epic-10b-agent-memory-validation.md) | Agent Memory Validation | 8 | Planned | TBD |
| **Tech Debt** |
| [12A](12-tech-debt/epic-12a-jan2026-tech-debt.md) | January 2026 Tech Debt | 19 | Planned | [Epic 12A: Tech Debt Q1 2026](https://linear.app/obsidianowl/project/epic-12a-tech-debt-q1-2026-3797f63d2107) |
| **Quality** |
| [15](15-e2e-platform-gaps/epic-15-e2e-platform-gaps.md) | E2E Test Infra & Platform Gaps | 15 | Planned | [Epic 15](https://linear.app/obsidianowl/project/epic-15-e2e-test-infrastructure-and-platform-gaps-fee2596b0f75) |

---

## By Category

### Foundation (Epic 1)
The blocking foundation - must complete before other work.
- [Epic 1: Plugin Registry](01-foundation/epic-01-plugin-registry.md)

### Configuration (Epics 2A-2B)
Schema and compilation pipeline.
- [Epic 2A: Manifest Schema](02-configuration/epic-02a-manifest-schema.md)
- [Epic 2B: Compilation Pipeline](02-configuration/epic-02b-compilation-pipeline.md)

### Enforcement (Epics 3A-3E)
Policy enforcement, data contracts, and governance integration.
- [Epic 3A: Policy Enforcer Core](03-enforcement/epic-03a-policy-enforcer-core.md)
- [Epic 3B: Policy Validation](03-enforcement/epic-03b-policy-validation.md)
- [Epic 3C: Data Contracts](03-enforcement/epic-03c-data-contracts.md)
- [Epic 3D: Contract Monitoring](03-enforcement/epic-03d-contract-monitoring.md)
- [Epic 3E: Governance Integration](03-enforcement/epic-03e-governance-integration.md) - *Compile-time RBAC, secrets, policies*

### Core Plugins (Epics 4A-4G)
Plugin interfaces and reference implementations.
- [Epic 4A: Compute Plugin](04-core-plugins/epic-04a-compute-plugin.md)
- [Epic 4B: Orchestrator Plugin](04-core-plugins/epic-04b-orchestrator-plugin.md)
- [Epic 4C: Catalog Plugin](04-core-plugins/epic-04c-catalog-plugin.md)
- [Epic 4D: Storage Plugin](04-core-plugins/epic-04d-storage-plugin.md)
- [Epic 4E: Semantic Layer Plugin](04-core-plugins/epic-04e-semantic-layer-plugin.md) - *Cube integration*
- [Epic 4F: Ingestion Plugin](04-core-plugins/epic-04f-ingestion-plugin.md) - *dlt integration*
- [Epic 4G: Reverse ETL](04-core-plugins/epic-04g-reverse-etl.md) - *SinkConnector mixin, dlt @dlt.destination*

### Transformation (Epics 5A-5B)
dbt and data quality.
- [Epic 5A: dbt Plugin](05-transformation/epic-05a-dbt-plugin.md)
- [Epic 5B: Data Quality Plugin](05-transformation/epic-05b-dataquality-plugin.md)

### Observability (Epics 6A-6C)
OpenTelemetry, OpenLineage, and code instrumentation.
- [Epic 6A: OpenTelemetry](06-observability/epic-06a-opentelemetry.md) - *SDK setup, provider config*
- [Epic 6B: OpenLineage](06-observability/epic-06b-openlineage.md) - *Lineage backend*
- [Epic 6C: OTel Code Instrumentation](06-observability/epic-06c-otel-instrumentation.md) - *Spans in floe-core, Dagster*

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

### Contributor Tooling (Epics 10A-10B)
Internal tooling for AI coding agents and maintainers contributing to floe.
- [Epic 10A: Agent Memory (Cognee)](10-contributor/epic-10a-agent-memory.md)
- [Epic 10B: Agent Memory Validation](10-contributor/epic-10b-agent-memory-validation.md)

### Tech Debt (Epic 12A)
Periodic technical debt reduction sprints.
- [Epic 12A: January 2026 Tech Debt](12-tech-debt/epic-12a-jan2026-tech-debt.md)

### Quality (Epic 15)
E2E test infrastructure and platform gap remediation.
- [Epic 15: E2E Test Infra & Platform Gaps](15-e2e-platform-gaps/epic-15-e2e-platform-gaps.md) - *11 root causes, 61 test failures*

---

## Next Steps

1. Start with **Epic 1** (Plugin Registry) - it's the blocking foundation
2. Once Epic 1 is complete, **Wave 2** Epics can start in parallel
3. Use `/speckit.specify` to generate spec.md for each Epic
4. Use `/speckit.tasks` to generate tasks.md
5. Use `/speckit.taskstolinear` to create Linear issues
6. Use `/speckit.implement` to execute tasks

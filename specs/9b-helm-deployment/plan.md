# Implementation Plan: Helm Charts and Kubernetes Deployment

**Branch**: `9b-helm-deployment` | **Date**: 2026-02-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/9b-helm-deployment/spec.md`

## Summary

Epic 9B delivers production-ready Kubernetes deployment infrastructure for the floe platform. This includes:

1. **floe-platform umbrella chart** - Dagster, Polaris, OTel Collector, Marquez (optional), PostgreSQL, MinIO (dev)
2. **floe-jobs chart** - dbt runs as K8s Jobs/CronJobs triggered by Dagster
3. **Helm Values Generator** - CLI command to produce values.yaml from CompiledArtifacts
4. **GitOps templates** - ArgoCD ApplicationSet and Flux HelmRelease examples
5. **Environment cluster mapping** - Multiple logical environments on 2 physical clusters

The implementation uses official Helm charts as subcharts where available (Dagster, OTel Collector) and creates custom charts for components without official charts (Polaris wrapper, Marquez).

## Technical Context

**Language/Version**: Python 3.11 (CLI), Go templating (Helm)
**Primary Dependencies**: Helm 3.12+, Dagster Helm chart 1.12.x, OTel Collector chart 0.85.x
**Storage**: PostgreSQL (CloudNativePG for prod, StatefulSet for non-prod), S3/MinIO
**Testing**: helm lint, helm template, ct (chart-testing), pytest for CLI, Kind cluster
**Target Platform**: Kubernetes 1.28+, tested on Kind, GKE, EKS, AKS
**Project Type**: Single (monorepo with charts/ directory)
**Performance Goals**: Platform deploy in <10 minutes, dbt job launch in <30 seconds
**Constraints**: Charts must pass helm lint, kubesec score >7, PSS restricted profile
**Scale/Scope**: 5 logical environments on 2 physical clusters, ~10 platform pods

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (`charts/` for Helm, `floe-core/cli/` for CLI)
- [x] No SQL parsing/validation in Python (dbt owns SQL)
- [x] No orchestration logic outside floe-dagster (Dagster Helm chart handles orchestration)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (`plugin.get_helm_values()` pattern)
- [x] Plugin values merged via HelmValuesGenerator (not hardcoded)
- [x] PluginMetadata not applicable (Helm charts, not Python plugins)

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (OTel for observability, OpenLineage via Marquez)
- [x] Pluggable choices documented (PostgreSQL Operator vs StatefulSet)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (values generated from artifacts)
- [x] Pydantic v2 models for HelmValuesGenerator, ClusterMapping entities
- [x] Contract changes follow versioning (chart versions independent, compatibility matrix)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster (chart installation tests)
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests for CLI

**Principle VI: Security First**
- [x] Input validation via Pydantic (HelmValuesGenerator)
- [x] Credentials use SecretStr / External Secrets (no hardcoded credentials)
- [x] No shell=True (Helm subprocess calls use list args)

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml → CompiledArtifacts → Helm values)
- [x] Layer ownership respected (Platform Team owns Helm charts)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry Collector deployed as platform component
- [x] OpenLineage via Marquez (optional subchart)

## Integration Design

### Entry Point Integration
- [x] Feature reachable from: CLI (`floe helm generate`)
- [x] Integration point: `packages/floe-core/src/floe_core/cli/helm/generate.py` (new)
- [x] Wiring task needed: Yes - add `helm` command group to CLI

### Dependency Integration
| This Feature Uses | From Package | Integration Point |
|-------------------|--------------|-------------------|
| CompiledArtifacts | floe-core | `CompiledArtifacts.from_json_file()` |
| OCIClient | floe-core | Pull promoted artifacts from registry |
| PluginRegistry | floe-core | Resolve plugins for `get_helm_values()` |
| ResolvedPlugins | floe-core | Access orchestrator, catalog plugins |

### Produces for Others
| Output | Consumers | Contract |
|--------|-----------|----------|
| `charts/floe-platform/` | Platform operators, GitOps | Chart.yaml, values.schema.json |
| `charts/floe-jobs/` | Data engineers, Dagster | Chart.yaml, Job templates |
| HelmValuesGenerator | CLI, CI/CD | Pydantic model in floe-core |
| values-{env}.yaml | ArgoCD, Flux | Generated Helm values |

### Cleanup Required
- [ ] Old code to remove: `testing/k8s/services/*.yaml` (replaced by Helm charts)
- [ ] Old tests to remove: None
- [ ] Old docs to update: `docs/guides/deployment.md`, `TESTING.md` (reference Helm-based test infra)
- [ ] Scripts to update: `testing/k8s/setup-cluster.sh` (migrate to Helm install)

## Test Infrastructure Convergence Strategy

**Decision**: Helm charts REPLACE the existing test infrastructure (Option A).

### Current State
```
testing/k8s/services/*.yaml  →  15 raw K8s manifests (kubectl apply)
testing/k8s/kind-config.yaml →  Kind cluster configuration (KEEP)
testing/k8s/setup-cluster.sh →  Uses kubectl apply (MODIFY)
Makefile: make kind-up       →  Calls setup-cluster.sh (MODIFY)
```

### Target State
```
charts/floe-platform/values-test.yaml  →  Test-specific overrides (NEW)
testing/k8s/kind-config.yaml           →  KEEP unchanged (port mappings)
testing/k8s/setup-cluster.sh           →  Uses helm install (MODIFY)
testing/k8s/services/                  →  DELETED (empty directory)
Makefile: make kind-up                 →  helm install floe-platform
```

### Sync Mechanism

The Helm chart is the **single source of truth**. Environment-specific configurations are layered:

```
values.yaml (defaults)
  └── values-dev.yaml (local dev)
  └── values-test.yaml (CI/CD testing)
  └── values-staging.yaml (pre-prod)
  └── values-prod.yaml (production)
```

**Invariant**: `values-test.yaml` ONLY contains overrides. New chart features automatically propagate.

### values-test.yaml Design

```yaml
# Test-specific overrides - minimal resources, in-memory backends
global:
  environment: test

# Single replicas for speed
dagster:
  dagsterWebserver:
    replicaCount: 1
  dagsterDaemon:
    replicaCount: 1

# In-memory for test isolation
polaris:
  persistence:
    type: in-memory

# No autoscaling in tests
otel:
  replicaCount: 1
  autoscaling:
    enabled: false

# Test credentials (non-production)
postgresql:
  auth:
    password: floe_test_password

# Always enabled for tests
minio:
  enabled: true
marquez:
  enabled: true

# NodePort for Kind access
services:
  type: NodePort
```

### Migration Order

1. Complete US1 (Platform Chart) - chart exists and works
2. Create `values-test.yaml` with test overrides
3. Modify `setup-cluster.sh` to use Helm
4. Validate all tests pass with Helm-based infrastructure
5. Delete `testing/k8s/services/*.yaml`
6. Update TESTING.md documentation

### Benefits

| Benefit | Description |
|---------|-------------|
| **No Drift** | Single source of truth for K8s manifests |
| **Production Parity** | Tests use exact production templates |
| **Automatic Propagation** | Chart changes affect tests without manual sync |
| **Schema Validation** | Invalid test config caught by values.schema.json |

## Project Structure

### Documentation (this feature)

```text
specs/9b-helm-deployment/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research findings
├── data-model.md        # Entity definitions
├── quickstart.md        # Developer quick-start
├── contracts/           # API contracts
│   └── helm-values-schema.json
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
charts/
├── floe-platform/               # Umbrella chart for platform services
│   ├── Chart.yaml              # Dependencies: dagster, otel, minio
│   ├── Chart.lock              # Locked dependency versions
│   ├── values.yaml             # Default values
│   ├── values.schema.json      # JSON Schema for validation
│   ├── values-dev.yaml         # Kind/dev overrides
│   ├── values-staging.yaml     # Staging configuration
│   ├── values-prod.yaml        # Production with HA
│   ├── README.md               # Configuration reference
│   ├── templates/
│   │   ├── _helpers.tpl        # Naming, labels, selectors
│   │   ├── configmap-otel.yaml # OTel Collector config
│   │   ├── configmap-polaris.yaml
│   │   ├── deployment-polaris.yaml
│   │   ├── service-polaris.yaml
│   │   ├── secret.yaml         # External Secrets references
│   │   ├── serviceaccount.yaml
│   │   ├── role.yaml           # RBAC for Dagster jobs
│   │   ├── rolebinding.yaml
│   │   ├── networkpolicy.yaml
│   │   ├── ingress.yaml
│   │   ├── hpa.yaml            # HorizontalPodAutoscaler
│   │   ├── pdb.yaml            # PodDisruptionBudget
│   │   ├── resourcequota.yaml
│   │   ├── tests/              # Helm test pods
│   │   │   └── test-connection.yaml
│   │   └── NOTES.txt           # Post-install instructions
│   └── charts/                 # Vendored/bundled subcharts
│       └── (dagster, otel pulled via dependency)
│
├── floe-jobs/                  # Data product job chart
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values.schema.json
│   ├── README.md
│   └── templates/
│       ├── _helpers.tpl
│       ├── job.yaml            # dbt run Job template
│       ├── cronjob.yaml        # Scheduled dbt runs
│       ├── configmap.yaml      # CompiledArtifacts mount
│       └── tests/
│           └── test-job.yaml
│
└── examples/                   # GitOps examples
    ├── argocd/
    │   ├── application.yaml
    │   └── applicationset.yaml
    └── flux/
        ├── helmrelease.yaml
        └── kustomization.yaml

packages/floe-core/src/floe_core/
├── cli/
│   ├── helm/                   # NEW: Helm CLI command group
│   │   ├── __init__.py
│   │   ├── generate.py         # floe helm generate
│   │   ├── template.py         # floe helm template (wrapper)
│   │   └── lint.py             # floe helm lint (wrapper)
│   └── main.py                 # Add helm group import
│
└── helm/                       # NEW: Helm utilities
    ├── __init__.py
    ├── generator.py            # HelmValuesGenerator class
    ├── schemas.py              # Pydantic models (ClusterMapping, etc.)
    └── merger.py               # Deep merge for values

tests/
├── integration/
│   └── helm/                   # Chart installation tests
│       ├── conftest.py
│       ├── test_platform_install.py
│       └── test_jobs_chart.py
└── unit/
    └── helm/                   # Generator unit tests
        ├── test_generator.py
        └── test_merger.py
```

**Structure Decision**: Monorepo with `charts/` at root (parallel to `packages/`). CLI commands in `floe-core/cli/helm/`. Helm utilities in `floe-core/helm/`.

## Complexity Tracking

No constitution violations requiring justification. Design follows existing patterns.

---

## Implementation Phases

### Phase 1: Infrastructure Charts (P0)

**Goal**: Working floe-platform chart deployable to Kind.

**Tasks**:
1. Create `charts/floe-platform/Chart.yaml` with dependencies
2. Configure Dagster subchart (external PostgreSQL, workspace)
3. Configure OTel Collector subchart (gateway mode, HPA)
4. Create Polaris templates (no official chart dependency)
5. Create PostgreSQL StatefulSet (non-prod mode)
6. Create MinIO subchart configuration (dev/demo)
7. Add RBAC templates (ServiceAccount, Role, RoleBinding)
8. Add production features (HPA, PDB, NetworkPolicy, Ingress)
9. Create `values.schema.json` for validation
10. Write README.md with configuration reference

**Dependencies**: None (greenfield)

**Verification**:
- `helm lint charts/floe-platform` passes
- `helm template` renders without errors
- `helm install` in Kind succeeds, all pods ready

### Phase 2: Data Product Chart (P0)

**Goal**: Working floe-jobs chart for dbt execution.

**Tasks**:
1. Create `charts/floe-jobs/Chart.yaml`
2. Create Job template with configurable command
3. Create CronJob template for scheduled runs
4. Add ConfigMap template for CompiledArtifacts
5. Add Secret mounting for credentials
6. Add resource limit configuration
7. Create `values.schema.json`
8. Write README.md

**Dependencies**: Phase 1 (uses same namespace, PostgreSQL)

**Verification**:
- Job template renders with correct dbt command
- CronJob schedule works
- Integration test creates Job, runs to completion

### Phase 3: Helm Values Generator (P1)

**Goal**: `floe helm generate` CLI command producing values.yaml.

**Tasks**:
1. Create `HelmValuesGenerator` class in `floe-core/helm/`
2. Implement plugin value collection (`get_helm_values()` calls)
3. Implement deep merge for values
4. Create Pydantic models for ClusterMapping, ResourcePreset
5. Add CLI command `floe helm generate`
6. Support `--artifact` (local file or OCI reference)
7. Support `--env` for environment-specific generation
8. Support `--output` for file or stdout
9. Add validation against values.schema.json
10. Unit tests for generator, merger
11. Integration test with sample artifacts

**Dependencies**: Phase 1 (chart must exist for schema validation)

**Verification**:
- `floe helm generate --artifact target/compiled_artifacts.json --env dev` produces valid YAML
- Generated values pass schema validation
- Plugin values correctly merged

### Phase 4: Environment Mapping (P1)

**Goal**: Support 5 logical environments on 2 physical clusters.

**Tasks**:
1. Implement ClusterMapping in values.yaml
2. Add namespace template rendering
3. Add environment-specific resource presets
4. Add environment labels to all resources
5. Add NetworkPolicy for cross-environment isolation
6. Document cluster mapping in README
7. Create values-staging.yaml, values-prod.yaml examples
8. Integration test with multiple namespaces

**Dependencies**: Phase 1

**Verification**:
- Deploy to floe-dev and floe-staging in same cluster
- Resources have correct environment labels
- NetworkPolicy blocks cross-namespace traffic

### Phase 5: GitOps Integration (P2)

**Goal**: ArgoCD and Flux deployment examples.

**Tasks**:
1. Create ArgoCD Application template
2. Create ArgoCD ApplicationSet for multi-environment
3. Create Flux HelmRelease template
4. Create Flux Kustomization for overlays
5. Document GitOps deployment in README
6. Add CI job to publish chart to OCI registry

**Dependencies**: Phase 1, Phase 4

**Verification**:
- ArgoCD syncs and deploys chart
- Flux reconciles HelmRelease
- Chart published to OCI registry

### Phase 6: Chart Testing & CI (P1)

**Goal**: Automated testing and publishing workflow.

**Tasks**:
1. Add `helm lint` to pre-commit or CI
2. Add `helm template` validation
3. Add chart-testing (ct) lint
4. Add chart-testing (ct) install
5. Create Kind cluster job for integration tests
6. Add Helm test pods (test-connection.yaml)
7. Add `helm test` execution in CI
8. Create chart release workflow (OCI + GitHub Pages)
9. Add security scanning (kubesec, trivy)

**Dependencies**: All previous phases

**Verification**:
- CI passes on all charts
- `helm test floe-platform` passes
- Chart published on release

### Phase 7: E2E Integration Validation (P0)

**Goal**: Validate complete platform vision - deploy and run data products with single configuration.

**Tasks**:
1. Create E2E workflow test (deploy → register → trigger → validate)
2. Validate dbt Job completes successfully after Helm deployment
3. Validate OpenLineage events emitted to Marquez
4. Validate OTel traces appear in collector
5. Create NetworkPolicy enforcement test
6. Create upgrade path test (rolling update validation)
7. Create automated quickstart validation script

**Dependencies**: Phase 1, Phase 2, Phase 6

**Verification**:
- E2E test passes: platform deploy → job execution → output validation
- Observability data flows through OTel Collector
- Lineage data appears in Marquez (when enabled)
- Upgrade from previous chart version succeeds without downtime

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Dagster chart version incompatibility | Pin exact version, test upgrades |
| CloudNativePG operator not installed | Graceful fallback to StatefulSet |
| OCI registry authentication | Document setup, test with ghcr.io |
| Chart size limits (OCI) | Monitor chart size, avoid large assets |

---

## Success Criteria Mapping

| Success Criteria | Phase | Verification |
|------------------|-------|--------------|
| SC-001: Deploy in <10 min | 1 | Time `helm install` in Kind |
| SC-002: Job launch <30s | 2 | Time from trigger to pod running |
| SC-003: helm lint zero warnings | 6 | CI gate |
| SC-004: Works on Kind/GKE/EKS/AKS | 6 | Multi-cluster test matrix |
| SC-005: Schema catches errors | 1-3 | Test invalid values |
| SC-006: GitOps works | 5 | ArgoCD/Flux test |
| SC-007: kubesec score >7 | 6 | Security scan in CI |
| SC-008: Rolling upgrade | 7 | E2E upgrade path test |
| SC-009: 5 envs on 2 clusters | 4 | Multi-namespace test |
| SC-010: Generate values <10s | 3 | Performance test |
| SC-011: E2E workflow works | 7 | Deploy → Run → Validate output |
| SC-012: Observability flows | 7 | OTel traces + OpenLineage events |

---

## Next Steps

1. Run `/speckit.tasks` to generate detailed task list
2. Create Linear issues via `/speckit.taskstolinear`
3. Begin Phase 1 implementation

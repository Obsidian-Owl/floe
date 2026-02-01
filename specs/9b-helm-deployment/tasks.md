# Tasks: Helm Charts and Kubernetes Deployment (Epic 9B)

**Input**: Design documents from `/specs/9b-helm-deployment/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

```text
charts/
├── floe-platform/     # Umbrella chart for platform services
└── floe-jobs/         # Data product job chart

packages/floe-core/src/floe_core/
├── cli/helm/          # CLI commands
└── helm/              # Helm utilities

tests/
├── integration/helm/  # Chart installation tests
└── unit/helm/         # Generator unit tests
```

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create chart directory structure and foundational files

- [ ] T001 Create `charts/floe-platform/` directory structure per plan.md
- [ ] T002 Create `charts/floe-jobs/` directory structure per plan.md
- [ ] T003 [P] Create `charts/examples/argocd/` directory for GitOps templates
- [ ] T004 [P] Create `charts/examples/flux/` directory for GitOps templates
- [ ] T005 [P] Create `packages/floe-core/src/floe_core/helm/` module directory
- [ ] T006 [P] Create `packages/floe-core/src/floe_core/cli/helm/` command directory
- [ ] T007 [P] Create `tests/integration/helm/` test directory
- [ ] T008 [P] Create `tests/unit/helm/` test directory

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core templates and helpers that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T009 Create `charts/floe-platform/Chart.yaml` with Dagster/OTel dependencies (FR-001, FR-010)
- [ ] T010 Create `charts/floe-platform/values.yaml` with default configuration
- [ ] T011 Create `charts/floe-platform/templates/_helpers.tpl` with naming/label functions
- [ ] T012 [P] Create Pydantic models in `packages/floe-core/src/floe_core/helm/schemas.py` (ClusterMapping, ResourcePreset, ResourceSpec)
- [ ] T013 [P] Create deep merge utility in `packages/floe-core/src/floe_core/helm/merger.py`
- [ ] T014 [P] Create `packages/floe-core/src/floe_core/helm/__init__.py` with exports
- [ ] T015 [P] Create `packages/floe-core/src/floe_core/cli/helm/__init__.py` command group
- [ ] T016 Wire helm command group to CLI main.py in `packages/floe-core/src/floe_core/cli/main.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Deploy Platform Services (Priority: P0)

**Goal**: Platform operators can deploy entire floe platform with single Helm command

**Independent Test**: `helm install floe-platform charts/floe-platform -f values-dev.yaml` in Kind cluster, verify all pods healthy

**Requirements**: FR-001, FR-003, FR-010, FR-011, FR-012, FR-013, FR-014, FR-014a, FR-016

### Tests for User Story 1

- [ ] T017 [P] [US1] Create `tests/integration/helm/conftest.py` with Kind cluster fixtures
- [ ] T018 [P] [US1] Create chart lint test in `tests/integration/helm/test_platform_lint.py` (FR-080)
- [ ] T019 [P] [US1] Create template render test in `tests/integration/helm/test_platform_template.py` (FR-081)
- [ ] T020 [US1] Create chart installation test in `tests/integration/helm/test_platform_install.py` (FR-082)

### Implementation for User Story 1

#### Dagster Subchart Configuration

- [ ] T021 [US1] Configure Dagster subchart in `charts/floe-platform/values.yaml` (webserver, daemon) (FR-010, FR-011)
- [ ] T022 [US1] Create workspace ConfigMap template in `charts/floe-platform/templates/configmap-dagster-workspace.yaml`
- [ ] T023 [US1] Create Dagster secret template in `charts/floe-platform/templates/secret-dagster.yaml` (FR-043)

#### Polaris Catalog (Custom Templates)

- [ ] T024 [P] [US1] Create Polaris ConfigMap in `charts/floe-platform/templates/configmap-polaris.yaml`
- [ ] T025 [P] [US1] Create Polaris Deployment in `charts/floe-platform/templates/deployment-polaris.yaml` (FR-012)
- [ ] T026 [P] [US1] Create Polaris Service in `charts/floe-platform/templates/service-polaris.yaml` (FR-016)

#### OTel Collector Subchart

- [ ] T027 [US1] Configure OTel Collector subchart in `charts/floe-platform/values.yaml` (gateway mode, HPA) (FR-013)
- [ ] T028 [US1] Create OTel Collector config in `charts/floe-platform/templates/configmap-otel.yaml`

#### PostgreSQL (StatefulSet for non-prod)

- [ ] T029 [US1] Create PostgreSQL StatefulSet in `charts/floe-platform/templates/statefulset-postgresql.yaml` (FR-014)
- [ ] T030 [US1] Create PostgreSQL Service in `charts/floe-platform/templates/service-postgresql.yaml`
- [ ] T031 [US1] Create PostgreSQL Secret template in `charts/floe-platform/templates/secret-postgresql.yaml`

#### MinIO (Dev/Demo)

- [ ] T032 [US1] Configure MinIO subchart in `charts/floe-platform/Chart.yaml` (FR-014a)
- [ ] T033 [US1] Add MinIO warning to NOTES.txt recommending external S3 for production

#### RBAC

- [ ] T034 [P] [US1] Create ServiceAccount in `charts/floe-platform/templates/serviceaccount.yaml` (FR-035)
- [ ] T035 [P] [US1] Create Role in `charts/floe-platform/templates/role.yaml` (FR-035)
- [ ] T036 [P] [US1] Create RoleBinding in `charts/floe-platform/templates/rolebinding.yaml` (FR-035)

#### Services and Networking

- [ ] T037 [US1] Create Ingress template in `charts/floe-platform/templates/ingress.yaml` (FR-033)
- [ ] T038 [US1] Create NOTES.txt post-install instructions in `charts/floe-platform/templates/NOTES.txt`

#### Environment Values

- [ ] T039 [P] [US1] Create `charts/floe-platform/values-dev.yaml` for Kind/dev configuration
- [ ] T040 [US1] Run `helm dependency update charts/floe-platform` to pull subcharts
- [ ] T041 [US1] Validate with `helm lint charts/floe-platform` and `helm template`

**Checkpoint**: User Story 1 complete - platform deploys to Kind with all pods healthy

---

## Phase 4: User Story 2 - Deploy Data Product Jobs (Priority: P0)

**Goal**: Data engineers can run dbt models as K8s Jobs triggered by Dagster

**Independent Test**: Deploy floe-jobs chart with sample dbt command, verify Job completes successfully

**Requirements**: FR-002, FR-003, FR-020, FR-021, FR-022, FR-023, FR-024

### Tests for User Story 2

- [ ] T042 [P] [US2] Create chart lint test in `tests/integration/helm/test_jobs_lint.py` (FR-080)
- [ ] T043 [P] [US2] Create template render test in `tests/integration/helm/test_jobs_template.py` (FR-081)
- [ ] T044 [US2] Create chart installation test in `tests/integration/helm/test_jobs_chart.py` (FR-082)

### Implementation for User Story 2

- [ ] T045 [US2] Create `charts/floe-jobs/Chart.yaml` (FR-002)
- [ ] T046 [US2] Create `charts/floe-jobs/values.yaml` with job defaults
- [ ] T047 [US2] Create `charts/floe-jobs/templates/_helpers.tpl`
- [ ] T048 [US2] Create Job template in `charts/floe-jobs/templates/job.yaml` (FR-020)
- [ ] T049 [US2] Create CronJob template in `charts/floe-jobs/templates/cronjob.yaml` (FR-021)
- [ ] T050 [US2] Create ConfigMap for artifacts in `charts/floe-jobs/templates/configmap.yaml` (FR-022)
- [ ] T051 [US2] Create Secret template in `charts/floe-jobs/templates/secret.yaml` (FR-023)
- [ ] T052 [US2] Add resource limits configuration to Job/CronJob templates (FR-024)
- [ ] T053 [US2] Create `charts/floe-jobs/README.md` with configuration reference (FR-005)
- [ ] T054 [US2] Validate with `helm lint charts/floe-jobs`

**Checkpoint**: User Story 2 complete - Jobs execute dbt runs successfully

---

## Phase 5: User Story 3 - Generate Helm Values from Artifacts (Priority: P1)

**Goal**: `floe helm generate` CLI command produces values.yaml from CompiledArtifacts

**Independent Test**: `floe helm generate --artifact target/compiled_artifacts.json --env dev` produces valid YAML

**Requirements**: FR-060, FR-061, FR-062, FR-063, FR-064, FR-065

### Tests for User Story 3

- [ ] T055 [P] [US3] Create unit test for merger in `tests/unit/helm/test_merger.py`
- [ ] T056 [P] [US3] Create unit test for generator in `tests/unit/helm/test_generator.py`
- [ ] T057 [US3] Create integration test in `tests/integration/helm/test_generate_command.py`

### Implementation for User Story 3

- [ ] T058 [US3] Implement HelmValuesGenerator class in `packages/floe-core/src/floe_core/helm/generator.py` (FR-060)
- [ ] T059 [US3] Add plugin value collection (`get_helm_values()` calls) to generator (FR-062)
- [ ] T060 [US3] Implement deep merge for values in generator (FR-063)
- [ ] T061 [US3] Add environment-specific generation logic (FR-064)
- [ ] T062 [US3] Create `floe helm generate` CLI command in `packages/floe-core/src/floe_core/cli/helm/generate.py`
- [ ] T063 [US3] Add `--artifact` option for local file or OCI reference (FR-061)
- [ ] T064 [US3] Add `--env` option for environment selection (FR-064)
- [ ] T065 [US3] Add `--output` option for file or stdout (FR-065)
- [ ] T066 [US3] Wire generate command to helm group in `packages/floe-core/src/floe_core/cli/helm/__init__.py`

**Checkpoint**: User Story 3 complete - values.yaml generated from artifacts

---

## Phase 6: User Story 4 - Environment Cluster Mapping (Priority: P1)

**Goal**: Support 5 logical environments on 2 physical clusters via namespace isolation

**Independent Test**: Deploy to `floe-dev` and `floe-staging` namespaces, verify correct labels and NetworkPolicy

**Requirements**: FR-050, FR-051, FR-052, FR-053

### Tests for User Story 4

- [ ] T067 [P] [US4] Create unit test for ClusterMapping validation in `tests/unit/helm/test_schemas.py`
- [ ] T068 [US4] Create integration test for multi-namespace in `tests/integration/helm/test_cluster_mapping.py`

### Implementation for User Story 4

- [ ] T069 [US4] Add clusterMapping section to `charts/floe-platform/values.yaml` (FR-050)
- [ ] T070 [US4] Implement namespace template rendering in `_helpers.tpl` (FR-051)
- [ ] T071 [US4] Add environment labels to all resource templates (FR-052)
- [ ] T072 [US4] Create NetworkPolicy template in `charts/floe-platform/templates/networkpolicy.yaml` (FR-032)
- [ ] T073 [US4] Create `charts/floe-platform/values-staging.yaml` for staging config
- [ ] T074 [US4] Create `charts/floe-platform/values-prod.yaml` for production config
- [ ] T075 [US4] Document cluster mapping in `charts/floe-platform/README.md`

**Checkpoint**: User Story 4 complete - multi-environment deployment works

---

## Phase 7: User Story 5 - Values Schema Validation (Priority: P1)

**Goal**: JSON Schema validates values.yaml before deployment

**Independent Test**: `helm install` with invalid values.yaml fails with clear schema error

**Requirements**: FR-004

### Tests for User Story 5

- [ ] T076 [P] [US5] Create schema validation test in `tests/integration/helm/test_values_schema.py`

### Implementation for User Story 5

- [ ] T077 [US5] Create `charts/floe-platform/values.schema.json` from contract schema (FR-004)
- [ ] T078 [US5] Create `charts/floe-jobs/values.schema.json` (FR-004)
- [ ] T079 [US5] Add schema validation to generator in `packages/floe-core/src/floe_core/helm/generator.py`
- [ ] T080 [US5] Test schema rejects invalid configurations

**Checkpoint**: User Story 5 complete - schema catches configuration errors

---

## Phase 8: User Story 6 - GitOps Deployment (Priority: P2)

**Goal**: ArgoCD/Flux templates for multi-environment GitOps deployment

**Independent Test**: Apply ArgoCD ApplicationSet, verify Application created per environment

**Requirements**: FR-070, FR-071, FR-072, FR-073, FR-074

### Implementation for User Story 6

- [ ] T081 [P] [US6] Create ArgoCD Application template in `charts/examples/argocd/application.yaml` (FR-070)
- [ ] T082 [P] [US6] Create ArgoCD ApplicationSet in `charts/examples/argocd/applicationset.yaml` (FR-071)
- [ ] T083 [P] [US6] Create Flux HelmRelease template in `charts/examples/flux/helmrelease.yaml` (FR-072)
- [ ] T084 [P] [US6] Create Flux Kustomization in `charts/examples/flux/kustomization.yaml`
- [ ] T085 [US6] Document GitOps deployment in `charts/floe-platform/README.md`

**Checkpoint**: User Story 6 complete - GitOps templates ready

---

## Phase 9: User Story 7 - Chart Testing (Priority: P1)

**Goal**: Automated chart testing in CI

**Independent Test**: `make helm-test` passes lint, template, and install tests

**Requirements**: FR-080, FR-081, FR-082, FR-083, FR-084

### Implementation for User Story 7

- [ ] T086 [US7] Create Helm test pod in `charts/floe-platform/templates/tests/test-connection.yaml` (FR-084)
- [ ] T087 [US7] Create Helm test pod in `charts/floe-jobs/templates/tests/test-job.yaml` (FR-084)
- [ ] T088 [US7] Add `helm-lint` target to Makefile (FR-080)
- [ ] T089 [US7] Add `helm-template` target to Makefile (FR-081)
- [ ] T090 [US7] Add `helm-test` target to Makefile (FR-083)
- [ ] T091 [US7] Add `helm-integration-test` target for Kind testing (FR-082)
- [ ] T092 [US7] Create `.github/workflows/helm-ci.yaml` for chart CI

**Checkpoint**: User Story 7 complete - chart testing automated

---

## Phase 10: User Story 8 - Chart Publishing (Priority: P2)

**Goal**: Charts published to OCI registry

**Independent Test**: `helm pull oci://registry/floe-platform:0.1.0` succeeds

**Requirements**: FR-073, FR-074

### Implementation for User Story 8

- [ ] T093 [US8] Create chart release workflow in `.github/workflows/helm-release.yaml` (FR-073)
- [ ] T094 [US8] Add OCI registry push step to release workflow
- [ ] T095 [US8] Add GitHub Pages index.yaml generation (FR-074)
- [ ] T096 [US8] Document chart installation from registry in README

**Checkpoint**: User Story 8 complete - charts published

---

## Phase 11: User Story 9 - Production Security (Priority: P1)

**Goal**: Charts follow K8s security best practices (PSS restricted, kubesec >7)

**Independent Test**: Deploy chart, verify pods run as non-root with read-only filesystem

**Requirements**: FR-030, FR-031, FR-032, FR-036, FR-040, FR-041, FR-042

### Implementation for User Story 9

- [ ] T097 [P] [US9] Create HPA template in `charts/floe-platform/templates/hpa.yaml` (FR-030)
- [ ] T098 [P] [US9] Create PDB template in `charts/floe-platform/templates/pdb.yaml` (FR-031)
- [ ] T099 [P] [US9] Create ResourceQuota template in `charts/floe-platform/templates/resourcequota.yaml` (FR-034)
- [ ] T100 [US9] Add Pod Security Standards configuration to values.yaml (FR-036)
- [ ] T101 [US9] Add securityContext to all pod templates (non-root, read-only) (FR-036)
- [ ] T102 [US9] Create External Secrets template in `charts/floe-platform/templates/externalsecret.yaml` (FR-040)
- [ ] T103 [US9] Add security scanning (kubesec) to CI workflow with score assertion in `tests/integration/helm/test_security_scan.py` (SC-007)
- [ ] T104 [US9] Create kubesec score verification test that fails CI if score <=7 on any chart

**Checkpoint**: User Story 9 complete - production security hardened

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and final validation

- [ ] T105 Create comprehensive `charts/floe-platform/README.md` with all configuration options (FR-005)
- [ ] T106 Add compatibility matrix to README (chart version → floe-core version) (FR-006)
- [ ] T107 Create `charts/floe-jobs/README.md` with job configuration options (FR-005)
- [ ] T108 [P] Update `docs/guides/deployment.md` to reference new Helm charts
- [ ] T109 [P] Add Marquez optional subchart to `charts/floe-platform/Chart.yaml` (FR-015)
- [ ] T110 Run `helm lint` on all charts and fix any warnings (SC-003)
- [ ] T111 Run full integration test suite in Kind cluster: `make helm-integration-test` must pass all tests
- [ ] T112 Manual validation: execute all quickstart.md commands and document results in `specs/9b-helm-deployment/validation-log.md`
- [ ] T113 Performance test: verify platform deploys in <10 minutes (SC-001)
- [ ] T114 Performance test: verify `floe helm generate` completes in <10 seconds (SC-010)

---

## Phase 13: E2E Integration Validation (Priority: P0)

**Purpose**: Validate Helm charts enable the complete platform vision - deploy platform and run data products with a single configuration

**Independent Test**: Deploy platform via Helm → register code location → trigger dbt Job → validate output exists

**Requirements**: E2E-001, E2E-002, E2E-003, SC-008

### Tests for E2E Validation

- [ ] T115 [E2E] Create upgrade test in `tests/integration/helm/test_platform_upgrade.py` - validates rolling update works (SC-008)
- [ ] T116 [E2E] Create E2E workflow test in `tests/e2e/test_helm_workflow.py` - deploy platform → register code location → trigger job
- [ ] T117 [E2E] Validate dbt Job completes successfully after Helm deployment in `tests/e2e/test_helm_workflow.py`
- [ ] T118 [E2E] Validate OpenLineage events emitted to Marquez after Job execution (FR-015, observability)
- [ ] T119 [E2E] Validate OTel traces appear in collector after Job execution (FR-013, observability)
- [ ] T120 [E2E] Create NetworkPolicy enforcement test in `tests/integration/helm/test_networkpolicy.py` (FR-032)
- [ ] T121 [E2E] Create automated quickstart validation script `scripts/validate-helm-quickstart.sh`

**Checkpoint**: E2E Integration complete - full platform vision validated end-to-end

---

## Phase 14: Test Infrastructure Migration (Priority: P0)

**Purpose**: Replace raw K8s manifests with Helm-based test infrastructure (single source of truth)

**Independent Test**: Run `make kind-up && make test-integration` with Helm-based setup

**Requirements**: FR-090, FR-091, FR-092, FR-093, FR-094, FR-095, SC-011, SC-012

### User Story 10 Tasks

- [ ] T122 [US10] Create `charts/floe-platform/values-test.yaml` with test-specific overrides (single replica, in-memory Polaris, minimal resources)
- [ ] T123 [US10] Create `charts/floe-jobs/values-test.yaml` with test job configuration
- [ ] T124 [US10] Modify `testing/k8s/setup-cluster.sh` to use `helm install floe-platform -f values-test.yaml`
- [ ] T125 [US10] Add Helm deployment to `Makefile` targets (`helm-install-test`, `helm-upgrade-test`, `helm-uninstall-test`)
- [ ] T126 [US10] Validate all existing integration tests pass with Helm-based infrastructure
- [ ] T127 [US10] Delete `testing/k8s/services/dagster.yaml` (replaced by Helm)
- [ ] T128 [US10] Delete `testing/k8s/services/polaris.yaml` (replaced by Helm)
- [ ] T129 [US10] Delete `testing/k8s/services/postgres.yaml` (replaced by Helm)
- [ ] T130 [US10] Delete `testing/k8s/services/minio.yaml` (replaced by Helm)
- [ ] T131 [US10] Delete `testing/k8s/services/marquez.yaml` (replaced by Helm)
- [ ] T132 [P] [US10] Delete remaining `testing/k8s/services/*.yaml` files (jaeger, keycloak, infisical, registry, metrics-server)
- [ ] T133 [US10] Keep `testing/k8s/kind-config.yaml` (Kind cluster config unchanged)
- [ ] T134 [US10] Keep `testing/k8s/namespace.yaml` OR migrate namespace creation to Helm pre-install hook
- [ ] T135 [US10] Update `TESTING.md` to document Helm-based test infrastructure
- [ ] T136 [US10] Update `.github/workflows/ci.yaml` to use Helm-based Kind deployment
- [ ] T137 [US10] Add CI validation that `values-test.yaml` passes schema validation
- [ ] T138 [US10] Create drift detection script `scripts/validate-test-values.sh` that verifies values-test.yaml is subset of schema

### Cleanup Tasks (Post-Migration)

- [ ] T139 [US10] Delete or migrate `testing/k8s/scripts/init-polaris.sh` to Helm post-install hook
- [ ] T140 [US10] Delete or migrate `testing/k8s/scripts/init-keycloak.sh` to Helm post-install hook (if Keycloak needed)
- [ ] T141 [US10] Delete or migrate `testing/k8s/scripts/init-infisical.sh` to Helm post-install hook (if Infisical needed)
- [ ] T142 [US10] Update `testing/k8s/cleanup-cluster.sh` to use `helm uninstall floe-platform floe-jobs`
- [ ] T143 [US10] Delete `testing/k8s/helm-values/infisical.yaml` (replaced by chart values)
- [ ] T144 [US10] Review `testing/k8s/jobs/test-runner.yaml` - KEEP if used for pytest execution, DELETE if replaced
- [ ] T145 [P] [US10] Remove `.gitkeep` files from emptied directories and delete empty `testing/k8s/services/` directory
- [ ] T146 [US10] Final verification: confirm only `kind-config.yaml`, `setup-cluster.sh`, `cleanup-cluster.sh` remain in `testing/k8s/`

**Checkpoint**: Test Infrastructure Migration complete - single source of truth achieved, no orphaned artifacts

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ─────────────────────────────────────────┐
                                                         │
Phase 2: Foundational ──────────────────────────────────┤ BLOCKS ALL
                                                         │
  ┌──────────────────────────────────────────────────────┘
  │
  ├─► Phase 3: US1 - Platform Services (P0) ────────────────────┐
  │                                                              │
  ├─► Phase 4: US2 - Data Product Jobs (P0) ──► depends on US1  │
  │                                                              │
  ├─► Phase 5: US3 - Helm Values Generator (P1) ─────────────────┤
  │                                                              │
  ├─► Phase 6: US4 - Environment Mapping (P1) ──► depends on US1 │
  │                                                              │
  ├─► Phase 7: US5 - Schema Validation (P1) ──► depends on US3  │
  │                                                              │
  ├─► Phase 8: US6 - GitOps (P2) ──► depends on US1, US4        │
  │                                                              │
  ├─► Phase 9: US7 - Chart Testing (P1) ──► depends on US1, US2 │
  │                                                              │
  ├─► Phase 10: US8 - Chart Publishing (P2) ──► depends on US7  │
  │                                                              │
  └─► Phase 11: US9 - Security (P1) ──► depends on US1          │
                                                                 │
Phase 12: Polish ◄───────────────────────────────────────────────┘
                        │
                        ▼
Phase 13: E2E Integration ──► depends on US1, US2, US7 (chart + jobs + testing)
                        │
                        ▼
Phase 14: Test Infrastructure Migration ──► depends on US1, US7 (charts + testing)
```

### Critical Path

1. **Phase 1 + 2**: Setup + Foundational (MUST complete first)
2. **Phase 3 (US1)**: Platform chart (enables US2, US4, US6, US7, US9)
3. **Phase 4 (US2)**: Jobs chart (enables US7)
4. **Phase 5 (US3)**: Generator (enables US5)
5. **Phase 12**: Polish (after all stories)
6. **Phase 13**: E2E Integration (validates complete vision)

### Parallel Opportunities

**After Phase 2 completes, these can run in parallel:**
- US1 (Platform) ─ no dependencies
- US3 (Generator) ─ no chart dependencies for core logic

**After US1 completes:**
- US2 (Jobs) + US4 (Mapping) + US9 (Security) can run in parallel

**After US1 + US2 complete:**
- US7 (Testing) can start

---

## Parallel Example: Setup Phase

```bash
# Launch all parallel setup tasks together:
Task: "Create charts/examples/argocd/ directory"
Task: "Create charts/examples/flux/ directory"
Task: "Create packages/floe-core/src/floe_core/helm/ module"
Task: "Create packages/floe-core/src/floe_core/cli/helm/ command"
Task: "Create tests/integration/helm/ directory"
Task: "Create tests/unit/helm/ directory"
```

## Parallel Example: User Story 1

```bash
# Launch all Polaris templates in parallel (different files):
Task: "Create Polaris ConfigMap in charts/floe-platform/templates/configmap-polaris.yaml"
Task: "Create Polaris Deployment in charts/floe-platform/templates/deployment-polaris.yaml"
Task: "Create Polaris Service in charts/floe-platform/templates/service-polaris.yaml"

# Launch all RBAC templates in parallel:
Task: "Create ServiceAccount in charts/floe-platform/templates/serviceaccount.yaml"
Task: "Create Role in charts/floe-platform/templates/role.yaml"
Task: "Create RoleBinding in charts/floe-platform/templates/rolebinding.yaml"
```

---

## Implementation Strategy

### MVP First (P0 Stories)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Platform Services)
4. Complete Phase 4: User Story 2 (Data Product Jobs)
5. Complete Phase 14: Test Infrastructure Migration (T122-T126 minimum)
6. Complete Phase 13: E2E Integration (T116-T117 minimum for MVP)
7. **STOP and VALIDATE**: Deploy platform + run sample job + verify E2E with Helm-based test infra
8. Deploy/demo if ready

### Incremental Delivery

| Milestone | Stories Complete | Value Delivered |
|-----------|------------------|-----------------|
| MVP | US1, US2, US10 (core), E2E (T116-T117) | Platform + Jobs + Helm-based test infra |
| Alpha | +US3, US4, US10 (cleanup) | Values generation, multi-env, old manifests deleted |
| Beta | +US5, US7, US9, E2E (T115, T118-T120) | Schema, testing, security, observability |
| GA | +US6, US8, E2E (T121) | GitOps, publishing, quickstart validation |

---

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 146 |
| Setup Tasks | 8 |
| Foundational Tasks | 8 |
| US1 (Platform) | 25 |
| US2 (Jobs) | 13 |
| US3 (Generator) | 12 |
| US4 (Mapping) | 9 |
| US5 (Schema) | 4 |
| US6 (GitOps) | 5 |
| US7 (Testing) | 7 |
| US8 (Publishing) | 4 |
| US9 (Security) | 8 |
| US10 (Test Infra Migration) | 25 |
| Polish | 10 |
| E2E Integration | 7 |
| Parallel Opportunities | 44 tasks marked [P] |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently

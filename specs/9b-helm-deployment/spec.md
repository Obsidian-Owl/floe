# Feature Specification: Helm Charts and Kubernetes Deployment

**Epic**: 9B (Helm Charts) - Merged with 9A requirements
**Feature Branch**: `9b-helm-deployment`
**Created**: 2026-02-01
**Status**: Draft
**Input**: User description: "Epic 9B: Helm Charts - Production-grade Helm charts for floe platform services and data product jobs, with GitOps integration, environment cluster mapping, and complete deployment automation."

## Overview

This epic delivers production-ready Kubernetes deployment infrastructure for the floe platform. It provides:

1. **floe-platform** umbrella chart for platform services (Dagster, Polaris, OTel, Marquez)
2. **floe-jobs** chart for data product workloads (dbt runs as K8s Jobs)
3. **GitOps integration** with ArgoCD/Flux ApplicationSet patterns
4. **Environment-to-cluster mapping** for enterprise hybrid deployments
5. **Helm values generation** from CompiledArtifacts

### Architectural Context

This epic operates at Layer 3 (Services) and Layer 4 (Data) of the four-layer architecture:

```
Layer 1: Foundation     -> Plugin packages (already implemented)
Layer 2: Configuration  -> manifest.yaml, floe.yaml (already implemented)
Layer 3: Services       -> THIS EPIC: K8s Deployments (Dagster, Polaris, OTel)
Layer 4: Data           -> THIS EPIC: K8s Jobs (dbt runs)
```

### Implementation Reality Check (Critical Gaps Analysis)

Based on deep codebase analysis, the following represents current state:

**What EXISTS and is production-ready:**
- 15 plugins across 13 plugin types with complete ABCs
- CompiledArtifacts v0.5.0 schema (817 lines, comprehensive)
- Testing K8s manifests in `testing/k8s/services/` (12 services)
- Kind cluster setup with all dependencies
- Plugin `get_helm_values()` methods (MarquezLineageBackendPlugin, etc.)
- Epic 8C promotion lifecycle (just completed)

**What is MISSING (this epic must create):**
- NO production Helm charts exist (only `cognee-platform` for agent memory)
- NO `charts/floe-platform/` directory
- NO `charts/floe-jobs/` directory
- Testing manifests are NOT production-grade (hardcoded values, no templating)
- No deployment controller or CLI deploy command
- No GitOps integration

### Relationship to Epic 8C

Epic 8C provides **promoted artifacts** with environment tags. This epic **deploys** those artifacts:

```
Epic 8C Output:                    Epic 9B Consumes:
+-------------------------+        +-------------------------+
| v1.2.3-staging (tagged) |   ->   | Helm install from tag   |
| + promotion metadata    |        | + cluster mapping       |
| + gate results          |        | + namespace isolation   |
+-------------------------+        +-------------------------+
```

### Separation of Concerns (ADR-0042)

**Epic 8C owns:** Logical environment promotion (gates, audit, tagging)
**Epic 9B owns:** Physical cluster deployment (Helm charts, namespace isolation, RBAC)

```yaml
# Epic 8C: manifest.yaml - LOGICAL environments
artifacts:
  promotion:
    environments: [dev, qa, uat, staging, prod]

# Epic 9B: Helm values - PHYSICAL clusters
clusterMapping:
  non-prod:
    cluster: aks-shared-nonprod
    environments: [dev, qa, uat, staging]
  prod:
    cluster: aks-shared-prod
    environments: [prod]
```

## Scope

### In Scope

**Platform Chart (floe-platform):**
- Umbrella chart with subcharts for Dagster, Polaris, OTel Collector, Marquez
- Production features: HPA, PDB, NetworkPolicy, Ingress, ResourceQuota
- External Secrets integration for secret management
- PostgreSQL StatefulSet for shared database
- MinIO/S3 configuration for object storage

**Data Product Chart (floe-jobs):**
- Job template for dbt runs triggered by Dagster
- CronJob template for scheduled pipelines
- ConfigMap mounting for CompiledArtifacts
- Secret mounting for data source credentials

**Helm Values Generation:**
- `floe helm generate` CLI command to generate values from CompiledArtifacts
- Plugin-specific Helm values via `plugin.get_helm_values()` pattern
- Environment-specific values files (values-dev.yaml, values-prod.yaml)

**GitOps Integration:**
- ArgoCD Application templates for multi-environment deployment
- Flux Kustomization templates
- Chart repository publishing (OCI + GitHub Pages)

**Testing:**
- Helm lint and template validation in CI
- Chart installation tests in Kind cluster
- Integration with existing contract tests

### Out of Scope

- CI/CD pipeline configuration (GitHub Actions for chart release)
- Multi-cluster management (ArgoCD multi-cluster is separate tooling)
- Service mesh (Istio/Linkerd) integration
- Cloud-specific managed services (GKE Autopilot, EKS Fargate)
- Monitoring dashboards (Grafana JSON)

### Integration Points

**Entry Point**: `floe helm generate` CLI command (floe-cli package)

**Dependencies**:
- `floe-core`: CompiledArtifacts, PluginRegistry, SecretReference
- `floe-core/oci`: OCIClient for pulling promoted artifacts
- `plugins/*`: Plugin `get_helm_values()` implementations
- Epic 8C: Promoted artifacts with environment tags

**Produces**:
- `charts/floe-platform/` umbrella chart
- `charts/floe-jobs/` data product chart
- `HelmValuesGenerator` class in floe-core
- CI workflow for chart publishing

**Used By**:
- Platform operators: Deploy via Helm/GitOps
- Data engineers: Data product jobs run via floe-jobs chart
- CI/CD pipelines: Automated deployments

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deploy Platform Services (Priority: P0)

As a **platform operator**, I want to deploy the entire floe platform to a Kubernetes cluster with a single Helm command so that I can quickly provision data infrastructure.

**Why this priority**: Core functionality - without platform services, nothing else works.

**Independent Test**: Run `helm install floe-platform charts/floe-platform -f values-dev.yaml` in Kind cluster and verify Dagster UI is accessible.

**Acceptance Scenarios**:

1. **Given** a Kind cluster with no floe services, **When** I run `helm install floe-platform charts/floe-platform`, **Then** Dagster webserver, daemon, Polaris catalog, OTel collector, and PostgreSQL pods are running and healthy within 5 minutes.

2. **Given** I want to customize resource limits, **When** I create a custom values.yaml with different CPU/memory, **Then** pods reflect the custom resource configuration.

3. **Given** I want dev vs prod configuration, **When** I use values-dev.yaml vs values-prod.yaml, **Then** resource allocations, replica counts, and security policies differ appropriately.

4. **Given** chart installation fails, **When** I check Helm status, **Then** clear error messages indicate which component failed and why (not just "timed out").

---

### User Story 2 - Deploy Data Product Jobs (Priority: P0)

As a **data engineer**, I want my dbt models to run as Kubernetes Jobs so that data transformations execute reliably with proper resource isolation.

**Why this priority**: Core data product execution - data engineers need their pipelines to run.

**Independent Test**: Create a simple dbt model, package as CompiledArtifacts, deploy with floe-jobs chart, verify Job completes.

**Acceptance Scenarios**:

1. **Given** a CompiledArtifacts package with dbt models, **When** Dagster triggers a run, **Then** a K8s Job is created with the correct image, environment variables, and volume mounts.

2. **Given** a scheduled pipeline, **When** CronJob fires, **Then** dbt run executes at the configured schedule with correct parameters.

3. **Given** a Job fails, **When** I check Job status, **Then** I can see dbt logs in the container logs and understand why it failed.

4. **Given** I want different resources for different models, **When** I configure per-model resources in CompiledArtifacts, **Then** Jobs have appropriate CPU/memory limits.

---

### User Story 3 - Generate Helm Values from Artifacts (Priority: P1)

As a **platform operator**, I want to automatically generate Helm values from CompiledArtifacts so that chart configuration matches my platform specification.

**Why this priority**: Automation bridge - connects Epic 8C artifacts to deployment.

**Independent Test**: Run `floe helm generate --artifact v1.2.3-staging --output values.yaml` and verify generated file has correct plugin configuration.

**Acceptance Scenarios**:

1. **Given** a promoted CompiledArtifacts with plugins configured, **When** I run `floe helm generate`, **Then** I get a values.yaml with plugin-specific configuration (Dagster resources, Polaris catalog, OTel exporters).

2. **Given** plugins have `get_helm_values()` methods, **When** values are generated, **Then** each plugin's Helm-specific configuration is merged into the output.

3. **Given** I specify an environment, **When** I run `floe helm generate --env=prod`, **Then** production-specific values are generated (higher resources, stricter security).

4. **Given** secrets are referenced in artifacts, **When** values are generated, **Then** External Secrets references are included (not actual secrets).

---

### User Story 4 - Environment Cluster Mapping (Priority: P1)

As a **platform operator** with 5 logical environments on 2 physical clusters, I want Helm to deploy to the correct namespace based on environment configuration so that I can optimize infrastructure costs.

**Why this priority**: Enterprise requirement - most organizations share clusters.

**Independent Test**: Configure clusterMapping in values, deploy to "staging" and "qa", verify they land in different namespaces on same cluster.

**Acceptance Scenarios**:

1. **Given** clusterMapping defines qa/staging on non-prod cluster, **When** I deploy to staging, **Then** resources are created in `floe-staging` namespace with appropriate labels.

2. **Given** multiple environments share a namespace, **When** I check resources, **Then** they have environment-specific labels for filtering.

3. **Given** prod is on a separate cluster, **When** I deploy to prod, **Then** the context switches to prod cluster (via kubeconfig/ArgoCD).

4. **Given** I want namespace isolation, **When** environments are deployed, **Then** NetworkPolicies prevent cross-environment traffic.

---

### User Story 5 - Values Schema Validation (Priority: P1)

As a **platform operator**, I want Helm values validated by JSON Schema so that configuration errors are caught before deployment.

**Why this priority**: Shift-left validation prevents runtime failures.

**Independent Test**: Attempt `helm install` with invalid values.yaml, verify schema validation fails with clear error.

**Acceptance Scenarios**:

1. **Given** a values.yaml with invalid structure, **When** I run `helm install`, **Then** validation fails with specific field errors.

2. **Given** required values are missing, **When** I run `helm template`, **Then** clear error indicates which values are required.

3. **Given** I use an IDE with JSON Schema support, **When** I edit values.yaml, **Then** I get autocomplete and inline validation.

---

### User Story 6 - GitOps Deployment (Priority: P2)

As a **DevOps engineer**, I want ArgoCD ApplicationSet templates so that I can deploy floe to multiple environments using GitOps patterns.

**Why this priority**: Enterprise deployment pattern - GitOps is standard.

**Independent Test**: Apply ArgoCD ApplicationSet, verify Application is created per environment.

**Acceptance Scenarios**:

1. **Given** an ArgoCD ApplicationSet template, **When** I configure environments in values, **Then** ArgoCD creates one Application per environment.

2. **Given** I push a chart version update, **When** ArgoCD syncs, **Then** deployments are updated with new chart version.

3. **Given** I want environment-specific overrides, **When** I configure per-env values in ApplicationSet, **Then** each environment uses correct values file.

---

### User Story 7 - Chart Testing (Priority: P1)

As a **platform developer**, I want charts tested automatically so that changes don't break deployments.

**Why this priority**: CI/CD quality gate - prevents broken charts from being published.

**Independent Test**: Run `make helm-test` and verify lint, template, and install tests pass.

**Acceptance Scenarios**:

1. **Given** I modify chart templates, **When** CI runs, **Then** `helm lint` validates syntax and best practices.

2. **Given** I want to preview rendered manifests, **When** I run `helm template`, **Then** all templates render without errors.

3. **Given** a Kind cluster is available, **When** CI runs integration tests, **Then** chart installs successfully and pods become ready.

---

### User Story 8 - Chart Publishing (Priority: P2)

As a **platform operator**, I want charts published to an OCI registry so that I can install from a versioned reference.

**Why this priority**: Distribution mechanism for production use.

**Independent Test**: Run chart publishing workflow, verify chart is pullable from registry.

**Acceptance Scenarios**:

1. **Given** chart version is updated, **When** release workflow runs, **Then** chart is pushed to OCI registry with version tag.

2. **Given** chart is published, **When** I run `helm pull oci://registry/floe-platform:1.0.0`, **Then** chart is downloaded.

3. **Given** I want to use GitHub Pages, **When** release runs, **Then** index.yaml is updated with new chart version.

---

### User Story 9 - Production Security (Priority: P1)

As a **security engineer**, I want charts to follow K8s security best practices so that deployments are hardened by default.

**Why this priority**: Security is non-negotiable for production.

**Independent Test**: Deploy chart and verify pods pass `kubectl auth can-i` restrictions.

**Acceptance Scenarios**:

1. **Given** default values, **When** chart is deployed, **Then** pods run as non-root with read-only root filesystem.

2. **Given** NetworkPolicies are enabled, **When** pods start, **Then** only required traffic is allowed (ingress from Ingress controller, egress to databases).

3. **Given** Pod Security Standards are enforced, **When** I deploy to a PSS-restricted namespace, **Then** pods comply with "restricted" profile.

4. **Given** I want to audit security posture, **When** I run security scanner (kubesec/trivy), **Then** chart passes with score > 8.

---

### User Story 10 - Test Infrastructure Convergence (Priority: P0)

As a **platform developer**, I want the test infrastructure to use the same Helm charts as production so that chart changes are automatically validated by tests without manual sync.

**Why this priority**: Eliminates drift between test and production deployment - critical for reliability.

**Independent Test**: Modify a chart template, run `make kind-up && make test-integration`, verify the change is reflected in test cluster.

**Acceptance Scenarios**:

1. **Given** I modify `charts/floe-platform/templates/deployment-polaris.yaml`, **When** I run `make kind-up`, **Then** the test cluster deploys with the modified template.

2. **Given** `testing/k8s/services/` directory, **When** Epic 9B is complete, **Then** the directory is empty (all manifests replaced by Helm).

3. **Given** I run `make kind-up`, **When** deployment completes, **Then** it uses `helm install floe-platform -f values-test.yaml` (not kubectl apply).

4. **Given** I add a new chart value, **When** I run tests, **Then** tests fail if `values-test.yaml` doesn't provide required value (schema validation).

---

### Edge Cases

- What happens when Helm release is interrupted mid-install? -> Transaction rollback with clear status
- What happens when subchart dependency is unavailable? -> Fail with "dependency not found" and fallback instructions
- What happens when values.yaml has conflicting configurations? -> Schema validation detects and reports conflicts
- How does system handle PVC creation on first install vs upgrade? -> StatefulSet handles PVC lifecycle
- What happens when PostgreSQL password changes during upgrade? -> Secret rotation handled via External Secrets
- What happens when node resources are insufficient? -> Pod scheduling fails with clear "insufficient resources" events

## Requirements *(mandatory)*

### Functional Requirements

#### Chart Structure

- **FR-001**: System MUST provide `floe-platform` umbrella chart in `charts/floe-platform/`
- **FR-002**: System MUST provide `floe-jobs` chart in `charts/floe-jobs/`
- **FR-003**: Charts MUST follow Helm v3 chart structure (Chart.yaml, values.yaml, templates/)
- **FR-004**: Charts MUST include JSON Schema for values validation (values.schema.json)
- **FR-005**: Charts MUST include comprehensive README.md with configuration reference
- **FR-006**: Charts MUST include compatibility matrix documenting supported floe-core versions

#### Platform Components (floe-platform)

- **FR-010**: Chart MUST use official Dagster Helm chart as dependency for webserver deployment
- **FR-011**: Chart MUST use official Dagster Helm chart configuration for daemon deployment
- **FR-012**: Chart MUST deploy Polaris catalog as Deployment with health probes
- **FR-013**: Chart MUST deploy OTel Collector as Deployment (gateway mode) with HPA for centralized trace collection
- **FR-014**: Chart MUST support environment-specific PostgreSQL: Operator (CloudNativePG/Zalando) for prod, simple StatefulSet for non-prod
- **FR-014a**: Chart MUST include MinIO subchart for dev/demo with WARNING log recommending external S3 for production
- **FR-014b**: Chart MUST support external S3-compatible storage as production configuration
- **FR-015**: Chart SHOULD deploy Marquez as optional component for lineage
- **FR-016**: Chart MUST configure inter-service networking via K8s Services

#### Data Product Components (floe-jobs)

- **FR-020**: Chart MUST provide Job template for dbt run execution
- **FR-021**: Chart MUST provide CronJob template for scheduled pipelines
- **FR-022**: Chart MUST mount CompiledArtifacts as ConfigMap or volume
- **FR-023**: Chart MUST mount secrets via External Secrets or K8s Secrets
- **FR-024**: Chart MUST configure resource limits per job type

#### Production Features

- **FR-030**: Charts MUST include HorizontalPodAutoscaler templates for scalable components
- **FR-031**: Charts MUST include PodDisruptionBudget templates for high availability
- **FR-032**: Charts MUST include NetworkPolicy templates for network isolation
- **FR-033**: Charts MUST include Ingress templates with configurable class
- **FR-034**: Charts MUST include ResourceQuota templates for namespace limits
- **FR-035**: Charts MUST include ServiceAccount with minimal RBAC permissions
- **FR-036**: Charts MUST support Pod Security Standards (restricted profile)

#### Secret Management

- **FR-040**: Charts MUST support External Secrets Operator integration
- **FR-041**: Charts MUST support direct K8s Secrets as fallback
- **FR-042**: Charts MUST NOT include any hardcoded credentials
- **FR-043**: Charts MUST use SecretKeyRef for all sensitive values

#### Environment Mapping

- **FR-050**: Charts MUST support `clusterMapping` values for logical-to-physical mapping
- **FR-051**: Charts MUST create namespace per logical environment when isolation is enabled
- **FR-052**: Charts MUST apply environment-specific labels to all resources
- **FR-053**: Charts MUST support multi-namespace deployment from single chart

#### Helm Values Generation

- **FR-060**: CLI MUST provide `floe helm generate` command
- **FR-061**: Generator MUST pull CompiledArtifacts from OCI registry
- **FR-062**: Generator MUST invoke `plugin.get_helm_values()` for each resolved plugin
- **FR-063**: Generator MUST merge plugin values into unified values.yaml
- **FR-064**: Generator MUST support `--env` flag for environment-specific generation
- **FR-065**: Generator MUST support `--output` flag for file or stdout

#### GitOps Integration

- **FR-070**: Charts MUST include ArgoCD Application template example
- **FR-071**: Charts MUST include ArgoCD ApplicationSet template for multi-env
- **FR-072**: Charts MUST include Flux HelmRelease template example
- **FR-073**: Charts MUST be publishable to OCI registry
- **FR-074**: Charts SHOULD support GitHub Pages Helm repository index

#### Testing

- **FR-080**: CI MUST run `helm lint` on all charts
- **FR-081**: CI MUST run `helm template` and validate output
- **FR-082**: CI MUST install charts in Kind cluster for integration tests
- **FR-083**: CI MUST run `helm test` hooks for deployment verification
- **FR-084**: Charts MUST include test connection pods for health verification

#### Test Infrastructure Convergence

- **FR-090**: Charts MUST include `values-test.yaml` with test-appropriate configuration (minimal resources, in-memory backends where applicable)
- **FR-091**: Test infrastructure MUST use Helm charts as the deployment mechanism (replacing raw kubectl apply)
- **FR-092**: `make kind-up` MUST deploy via `helm install floe-platform -f values-test.yaml`
- **FR-093**: Raw K8s manifests in `testing/k8s/services/` MUST be deleted after Helm migration is complete
- **FR-094**: Test values.yaml MUST NOT duplicate chart defaults - only override test-specific settings
- **FR-095**: CI MUST validate that `values-test.yaml` is a valid subset of chart schema

### Key Entities

- **FloeHelmChart**: Helm chart metadata (name, version, dependencies, values schema)
- **ClusterMapping**: Logical-to-physical environment mapping with namespace isolation settings
- **HelmValuesGenerator**: Class that produces values.yaml from CompiledArtifacts
- **PlatformDeployment**: Deployed instance of floe-platform with status tracking
- **DataProductJob**: K8s Job for dbt execution with lifecycle management

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Platform operators can deploy complete floe platform in under 10 minutes on any K8s cluster
- **SC-002**: Data engineers can trigger dbt runs that execute as K8s Jobs within 30 seconds of Dagster trigger
- **SC-003**: `helm lint` passes with zero warnings on all charts
- **SC-004**: Chart installation succeeds on Kind, GKE, EKS, and AKS without modification
- **SC-005**: Values schema catches 100% of common configuration errors before deployment
- **SC-006**: GitOps deployment via ArgoCD/Flux works with provided templates
- **SC-007**: All charts pass security scanning (kubesec score > 7)
- **SC-008**: Upgrade from N to N+1 chart version completes without downtime (rolling updates)
- **SC-009**: 5 logical environments can deploy to 2 physical clusters using namespace isolation
- **SC-010**: `floe helm generate` produces deployable values from any CompiledArtifacts in under 10 seconds
- **SC-011**: Test infrastructure uses identical Helm charts as production (single source of truth)
- **SC-012**: Changes to chart templates automatically propagate to test infrastructure without manual sync

### Non-Functional Requirements

- **NFR-001**: Chart templates MUST render in under 2 seconds
- **NFR-002**: Generated values.yaml MUST be under 1MB
- **NFR-003**: Chart dependencies MUST be version-pinned
- **NFR-004**: All images MUST support arm64 and amd64 architectures

## Assumptions

1. **Helm 3.12+ available**: Target clusters have Helm 3.12 or later installed
2. **External Secrets Operator**: Production clusters use ESO for secret management
3. **Ingress controller exists**: Target clusters have an Ingress controller (nginx, traefik)
4. **PostgreSQL is acceptable**: Shared PostgreSQL for Dagster/Marquez is acceptable for non-HA deployments
5. **OCI registry available**: OCI-compliant registry available for chart storage
6. **Testing manifests as baseline**: Existing `testing/k8s/services/` manifests provide correct baseline for initial chart development
7. **Test infrastructure migration**: After Epic 9B, `testing/k8s/services/` is deleted and replaced by Helm deployment via `values-test.yaml`

## Open Questions

None - decisions made:
1. Merge 9A + 9B: **Yes** - deployment logic tightly coupled with Helm
2. GitOps vs CLI: **GitOps first** - charts + ArgoCD templates, no direct CLI deploy
3. Scope: **Full stack** - platform services AND data product jobs

## Glossary

| Term | Definition |
|------|------------|
| **Umbrella chart** | Parent chart that includes multiple subcharts as dependencies |
| **Subchart** | Child chart included as dependency in umbrella chart |
| **HPA** | HorizontalPodAutoscaler - scales pods based on metrics |
| **PDB** | PodDisruptionBudget - ensures minimum availability during disruptions |
| **ESO** | External Secrets Operator - syncs secrets from external providers |
| **PSS** | Pod Security Standards - K8s security profiles (privileged, baseline, restricted) |
| **ApplicationSet** | ArgoCD resource for generating multiple Applications from template |

## Clarifications

- Q: Should we create Helm charts from scratch or convert testing manifests? A: **Convert testing manifests** - the `testing/k8s/services/` manifests provide correct baseline, just need templating and production features.

- Q: Should we include all platform components or make some optional? A: **Make Marquez optional** - Dagster, Polaris, OTel, PostgreSQL are required; Marquez for lineage is optional.

- Q: How do we handle cross-package plugin values? A: **Plugin `get_helm_values()` pattern** - each plugin knows its Helm configuration, generator aggregates.

- Q: What PostgreSQL strategy should charts support? A: **Environment-specific** - PostgreSQL Operator (CloudNativePG/Zalando) for prod with HA, backups, failover; simple StatefulSet for non-prod. Configurable per environment via values.

- Q: What object storage strategy should charts use? A: **Both options (MVP)** - Bundle MinIO subchart for dev/demo with WARNING recommending external S3 for production. Target architecture is external S3-compatible storage; bundled MinIO is convenience only.

- Q: Which subchart strategy should we use? A: **Official charts where available** - Use Dagster official Helm chart as dependency; create custom subcharts only for Polaris and Marquez which lack official charts.

- Q: What OTel Collector deployment mode should be default? A: **Deployment (gateway mode)** - Centralized collector with HPA for app-level traces. Simpler than DaemonSet since Dagster/dbt jobs send traces directly to collector endpoint.

- Q: What chart versioning strategy should we use? A: **Independent versioning** - Chart versions evolve independently from floe-core package versions. Maintain compatibility matrix in chart README documenting which chart versions work with which floe-core versions.

## References

- **ADR-0042**: Logical vs Physical Environment Model
- **Epic 8C**: Promotion Lifecycle (provides promoted artifacts)
- **testing/k8s/services/**: Baseline manifests to convert
- **charts/cognee-platform/**: Example of Helm conventions used in project
- **docs/architecture/ARCHITECTURE-SUMMARY.md**: Four-layer architecture

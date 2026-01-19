# Feature Specification: K8s RBAC Plugin System

**Epic**: 7B (K8s RBAC)
**Feature Branch**: `7b-k8s-rbac`
**Created**: 2026-01-19
**Status**: Draft
**Input**: User description: "K8s RBAC Plugin System for Kubernetes-native role-based access control with service account management, namespace isolation, and policy generation for the floe platform"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Service Account Generation for Data Jobs (Priority: P0)

As a platform operator, I want service accounts automatically generated with least-privilege permissions so that data pipeline jobs can access only the resources they need.

**Why this priority**: This is the foundation of K8s RBAC - without service accounts, no job can authenticate to K8s APIs or access secrets. All other RBAC functionality depends on this. Security is non-negotiable per ADR-0022.

**Independent Test**: Can be fully tested by deploying a dbt job, verifying the service account exists with correct Role/RoleBinding, and confirming the job can access specified secrets but nothing else.

**Acceptance Scenarios**:

1. **Given** a manifest.yaml with `security.rbac.job_service_account: auto`, **When** `floe deploy` runs, **Then** a `floe-job-runner` ServiceAccount is created in the `floe-jobs` namespace.

2. **Given** a `floe-job-runner` ServiceAccount, **When** a dbt job pod starts, **Then** it can read secrets named `compute-credentials` and `catalog-credentials` but no other secrets.

3. **Given** a ServiceAccount with RBAC Role, **When** the job attempts to create a ConfigMap, **Then** the operation fails with a clear permission denied error.

4. **Given** job completion, **When** the K8s audit logs are checked, **Then** all API calls from the job are attributed to the `floe-job-runner` ServiceAccount.

---

### User Story 2 - Namespace Isolation for Multi-Tenant Deployments (Priority: P0)

As a platform operator, I want namespace-based isolation so that jobs from different domains cannot access each other's resources (namespace isolation per ADR-0022).

**Why this priority**: Namespace isolation is the primary security boundary in Data Mesh deployments. Without this, domain A could read domain B's secrets or data. Critical for compliance (SOC2, ISO 27001).

**Independent Test**: Can be fully tested by creating two domain namespaces, deploying jobs in each, and verifying cross-namespace access is denied.

**Acceptance Scenarios**:

1. **Given** `floe-sales-domain` and `floe-marketing-domain` namespaces, **When** a job in `floe-sales-domain` attempts to read a secret in `floe-marketing-domain`, **Then** the operation fails with permission denied.

2. **Given** `security.namespace_isolation: strict` in manifest.yaml, **When** deploying a new domain, **Then** the RBAC plugin creates a namespace with `pod-security.kubernetes.io/enforce: restricted` label.

3. **Given** strict namespace isolation, **When** a job pod is created, **Then** it runs with `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, and `allowPrivilegeEscalation: false`.

4. **Given** a domain namespace, **When** a new service account is created for that domain, **Then** it has a RoleBinding scoped only to that namespace.

---

### User Story 3 - Cross-Namespace Access for Platform Services (Priority: P1)

As a platform operator, I want Dagster to create jobs in the `floe-jobs` namespace so that the orchestrator can manage data pipeline execution across namespaces.

**Why this priority**: Platform services (Dagster, Polaris) must operate across namespaces to function. This is the controlled exception to namespace isolation - explicit cross-namespace grants for platform components only.

**Independent Test**: Can be fully tested by deploying Dagster in `floe-platform`, triggering a job, and verifying it creates a job pod in `floe-jobs` namespace.

**Acceptance Scenarios**:

1. **Given** `floe-dagster` ServiceAccount in `floe-platform` namespace, **When** Dagster schedules a job, **Then** it can create Job resources in `floe-jobs` namespace.

2. **Given** a running job in `floe-jobs`, **When** Dagster queries job status, **Then** it can read Pod logs from `floe-jobs` namespace.

3. **Given** the `floe-dagster` ServiceAccount, **When** it attempts to create a Job in `floe-sales-domain`, **Then** the operation fails (only `floe-jobs` is permitted).

4. **Given** cross-namespace RoleBinding configuration, **When** `floe deploy` runs, **Then** the binding is created only in explicitly allowed target namespaces.

---

### User Story 4 - RBAC Manifest Generation (Priority: P1)

As a data engineer, I want RBAC manifests generated from floe.yaml so that I don't need to manually write Kubernetes RBAC resources.

**Why this priority**: Manual RBAC configuration is error-prone and a major source of security misconfigurations. Generated manifests ensure consistency and reduce human error.

**Independent Test**: Can be fully tested by running `floe compile`, examining the output RBAC manifests, and applying them to a test cluster.

**Acceptance Scenarios**:

1. **Given** `security.rbac.enabled: true` in manifest.yaml, **When** `floe compile` runs, **Then** `target/rbac/` directory contains ServiceAccount, Role, RoleBinding, and optional ClusterRole YAML files.

2. **Given** a data product with `compute.credentials_ref: snowflake-creds`, **When** compiling, **Then** the generated Role includes `get` permission on secrets with resourceName `snowflake-creds`.

3. **Given** multiple data products in the same domain, **When** compiling, **Then** a single aggregated Role is generated (not one per product).

4. **Given** generated RBAC manifests, **When** applying with `kubectl apply -f target/rbac/`, **Then** all resources are created without errors.

---

### User Story 5 - Pod Security Standards Enforcement (Priority: P2)

As a security officer, I want Pod Security Standards enforced so that all job pods meet security baselines (per ADR-0022 restricted level).

**Why this priority**: Pod Security Standards prevent privilege escalation and container escape attacks. Required for enterprise security compliance but not blocking for basic functionality.

**Independent Test**: Can be fully tested by deploying a job with a non-compliant security context and verifying admission rejection.

**Acceptance Scenarios**:

1. **Given** `security.pod_security.jobs_level: restricted` in manifest.yaml, **When** the `floe-jobs` namespace is created, **Then** it has label `pod-security.kubernetes.io/enforce: restricted`.

2. **Given** restricted pod security, **When** a job pod spec lacks `runAsNonRoot: true`, **Then** the pod admission controller rejects the pod.

3. **Given** platform services namespace, **When** checking its labels, **Then** it has `pod-security.kubernetes.io/enforce: baseline` (less restrictive for stateful services).

4. **Given** a generated job pod spec, **When** inspecting securityContext, **Then** it includes `seccompProfile: RuntimeDefault` and `capabilities.drop: ["ALL"]`.

---

### User Story 6 - RBAC Audit and Validation (Priority: P2)

As a security officer, I want to validate RBAC configurations so that I can ensure least-privilege principles are followed.

**Why this priority**: Audit capability is required for compliance but not for basic functionality. Important for ongoing security posture management.

**Independent Test**: Can be fully tested by running `floe rbac audit` and reviewing the generated report.

**Acceptance Scenarios**:

1. **Given** a deployed floe installation, **When** running `floe rbac audit`, **Then** a report is generated showing all service accounts and their permissions.

2. **Given** a service account with overly broad permissions (e.g., `secrets: ["*"]`), **When** running audit, **Then** a warning is flagged for excessive permissions.

3. **Given** generated RBAC manifests, **When** running `floe rbac validate`, **Then** the tool verifies manifests match the current manifest.yaml configuration.

4. **Given** RBAC drift (manual changes in cluster), **When** running `floe rbac diff`, **Then** differences between expected and actual RBAC are displayed.

---

### Edge Cases

- What happens when a namespace already exists with conflicting RBAC?
  - The plugin detects existing resources and reports conflicts
  - `--force` flag allows overwriting with warning
  - Existing resources not managed by floe are preserved

- How does the system handle service account token rotation?
  - K8s 1.22+ uses bound service account tokens (auto-rotated)
  - No manual rotation required for floe-managed service accounts
  - Legacy token secrets are not created (security best practice)

- What happens when a RoleBinding references a non-existent ServiceAccount?
  - `floe rbac validate` detects and reports dangling references
  - Compilation warns but does not fail (allow partial deployment)
  - Deployment fails if ServiceAccount doesn't exist at apply time

- How are cluster-scoped resources (ClusterRole) managed?
  - ClusterRoles are only generated when explicitly required
  - Cross-namespace access uses namespaced Roles with explicit bindings
  - ClusterRoleBindings require elevated install permissions (documented)

## Requirements *(mandatory)*

### Functional Requirements

#### Core RBAC Plugin Interface

- **FR-001**: System MUST provide `RBACPlugin` ABC with `generate_service_account()`, `generate_role()`, and `generate_role_binding()` methods.

- **FR-002**: System MUST provide `RBACManifestGenerator` that produces valid Kubernetes RBAC YAML from floe configuration.

- **FR-003**: `RBACPlugin` MUST inherit from `PluginMetadata` and declare `name`, `version`, and `floe_api_version`.

- **FR-004**: System MUST provide `K8sRBACPlugin` as the default implementation using kubernetes client library.

#### Service Account Management

- **FR-010**: System MUST generate `ServiceAccount` resources with configurable names following pattern `floe-{purpose}` (e.g., `floe-job-runner`, `floe-dagster`).

- **FR-011**: ServiceAccounts MUST configure `automountServiceAccountToken` based on pod requirements: `true` for pods needing K8s API access (job status reporting, secret watching), `false` for pure compute pods (dbt/dlt jobs using only environment variables).

- **FR-012**: System MUST support both namespace-scoped and cross-namespace ServiceAccount configurations.

- **FR-013**: Generated ServiceAccounts MUST include labels: `app.kubernetes.io/managed-by: floe`, `floe.dev/component: {component}`.

- **FR-014**: System MUST determine token mounting requirement based on job configuration: jobs with `k8s_api_access: true` get mounted tokens, jobs without (default) have `automountServiceAccountToken: false`.

#### Role and RoleBinding Generation

- **FR-020**: System MUST generate `Role` resources with least-privilege permissions based on declared secret references.

- **FR-021**: Roles MUST use `resourceNames` constraints when specific secrets are referenced (not wildcard access).

- **FR-022**: System MUST generate `RoleBinding` resources linking ServiceAccounts to Roles within the same namespace.

- **FR-023**: System MUST support cross-namespace RoleBindings for platform services (e.g., Dagster -> floe-jobs).

- **FR-024**: Generated Roles MUST include only these verbs for secrets: `get` (no `list`, `watch`, `create`, `update`, `delete`).

#### Namespace Configuration

- **FR-030**: System MUST generate `Namespace` resources with Pod Security Standard labels based on configuration.

- **FR-031**: `floe-jobs` namespace MUST have `pod-security.kubernetes.io/enforce: restricted` by default.

- **FR-032**: `floe-platform` namespace MUST have `pod-security.kubernetes.io/enforce: baseline` by default.

- **FR-033**: Domain namespaces (`floe-{domain}-domain`) MUST inherit security level from parent domain config or default to `restricted`.

- **FR-034**: Namespace resources MUST include labels: `floe.dev/layer: {layer}`, `app.kubernetes.io/part-of: floe`.

#### Pod Security Context Generation

- **FR-040**: System MUST generate pod `securityContext` with `runAsNonRoot: true` for job pods.

- **FR-041**: System MUST generate container `securityContext` with `allowPrivilegeEscalation: false` and `capabilities.drop: ["ALL"]`.

- **FR-042**: System MUST generate `seccompProfile: RuntimeDefault` for all pods.

- **FR-043**: System MUST support `readOnlyRootFilesystem: true` with configurable volume mounts for writable directories.

- **FR-044**: System MUST configure `runAsUser` and `runAsGroup` with configurable non-root UID/GID (default: 1000).

#### Compilation Integration

- **FR-050**: `floe compile` MUST generate RBAC manifests in `target/rbac/` directory when `security.rbac.enabled: true`.

- **FR-051**: Generated manifests MUST be valid YAML parseable by `kubectl apply --dry-run=client`.

- **FR-052**: Compilation MUST aggregate permissions across all data products into minimal Role definitions.

- **FR-053**: Compilation MUST produce separate files: `serviceaccounts.yaml`, `roles.yaml`, `rolebindings.yaml`, `namespaces.yaml`.

#### CLI Commands

- **FR-060**: System MUST provide `floe rbac generate` command to generate RBAC manifests without full compilation.

- **FR-061**: System MUST provide `floe rbac validate` command to validate generated manifests against configuration.

- **FR-062**: System MUST provide `floe rbac audit` command to analyze current cluster RBAC state.

- **FR-063**: System MUST provide `floe rbac diff` command to show differences between expected and deployed RBAC.

#### Security Requirements

- **FR-070**: Generated Roles MUST NOT include wildcard permissions (`*`) on any resource.

- **FR-071**: Generated ClusterRoleBindings MUST only be created with explicit `security.rbac.cluster_scope: true` configuration.

- **FR-072**: System MUST log all RBAC manifest generation operations to audit trail.

- **FR-073**: System MUST fail compilation if a secret reference points to a secret not included in RBAC permissions.

### Key Entities

- **RBACPlugin**: Abstract base class for RBAC operations. Handles service account, role, and binding generation across different deployment targets.

- **RBACManifestGenerator**: Core class that transforms floe configuration into Kubernetes RBAC YAML manifests. Handles aggregation and deduplication.

- **ServiceAccountConfig**: Pydantic model representing service account configuration including name, namespace, and annotations.

- **RoleConfig**: Pydantic model representing a Role with rules defining apiGroups, resources, verbs, and resourceNames.

- **RoleBindingConfig**: Pydantic model representing a RoleBinding linking subjects (ServiceAccounts) to roles.

- **NamespaceConfig**: Pydantic model representing namespace configuration including Pod Security Standard labels.

- **PodSecurityConfig**: Pydantic model representing pod and container security context settings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All RBAC plugin implementations pass compliance test suite (`BaseRBACPluginTests`) with 100% method coverage.

- **SC-002**: Generated RBAC manifests pass `kubectl apply --dry-run=server` validation without errors.

- **SC-003**: Service accounts have only the minimum permissions required for their declared secret references.

- **SC-004**: Zero instances of wildcard permissions (`*`) appear in generated Role rules.

- **SC-005**: Pod Security Standard enforcement blocks non-compliant pods within 1 second of submission.

- **SC-006**: `floe rbac audit` completes full cluster analysis within 30 seconds for clusters with up to 100 namespaces.

- **SC-007**: `floe rbac diff` accurately detects 100% of RBAC drift between expected and deployed state.

- **SC-008**: All generated manifests include `app.kubernetes.io/managed-by: floe` label for resource tracking.

## Assumptions

- Kubernetes 1.28+ is available (required for Pod Security Standards and bound service account tokens)
- The K8s cluster has Pod Security Admission controller enabled (default since K8s 1.25)
- Epic 7A (Identity & Secrets) is complete, providing `SecretsPlugin` for secret reference resolution
- Network policies are handled separately (Epic 7C - Network/Pod Security)
- Platform team has cluster-admin or equivalent permissions for initial RBAC setup
- Domain-scoped service accounts are created by domain platform teams (not floe)

## Out of Scope

- Network Policies (covered in Epic 7C - Network/Pod Security)
- Service mesh integration (Istio/Linkerd mTLS) - optional enhancement per ADR-0022
- ClusterRole/ClusterRoleBinding for non-platform components
- Custom RBAC for non-floe workloads
- RBAC for external identities (human users) - only service accounts
- OPA/Gatekeeper policy integration (future enhancement)
- Secret encryption at rest configuration (K8s admin responsibility)

## Clarifications

- Q: Should the spec differentiate token mounting based on whether pods need K8s API access? A: Yes, differentiate by pod type - only mount tokens for pods needing K8s API access (FR-011 updated). This follows K8s least-privilege best practices where pure compute jobs (dbt/dlt) that only need environment variables should not have K8s API tokens mounted.

## References

- ADR-0022: Security & RBAC Model - Comprehensive K8s RBAC architecture
- ADR-0030: Namespace-Based Identity Model - Namespace isolation patterns
- ADR-0023: Secrets Management - Secret access patterns
- Epic 7A spec (`specs/7a-identity-secrets/spec.md`) - Identity and secrets plugin foundation
- `packages/floe-core/src/floe_core/plugins/identity.py` - IdentityPlugin ABC
- `packages/floe-core/src/floe_core/plugins/secrets.py` - SecretsPlugin ABC
- `testing/base_classes/base_identity_plugin_tests.py` - Plugin test patterns
- [Kubernetes RBAC Documentation](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)

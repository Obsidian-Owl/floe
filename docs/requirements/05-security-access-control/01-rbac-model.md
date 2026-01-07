# REQ-400 to REQ-415: Kubernetes RBAC and Service Account Model

**Domain**: Security and Access Control
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines the Kubernetes RBAC model that implements least-privilege access control for floe. Each service account has minimal permissions needed for its function, preventing lateral movement and limiting blast radius of compromised pods.

**Key Principle**: Least Privilege + Namespace Isolation (ADR-0022)

## Requirements

### REQ-400: Service Account Isolation by Namespace **[New]**

**Requirement**: System MUST create dedicated Kubernetes service accounts per namespace with no cross-namespace token sharing. Service accounts in floe-jobs namespace MUST NOT have permissions in floe-platform namespace.

**Rationale**: Prevents lateral movement if a job pod is compromised. Ensures network-level isolation is backed by identity isolation.

**Acceptance Criteria**:
- [ ] Service accounts created for each namespace
- [ ] Each service account has unique name and restricted role
- [ ] Cross-namespace RoleBinding forbidden (no ClusterRoleBinding except system)
- [ ] Service account tokens mounted only in their namespace
- [ ] RBAC audit tests verify namespace boundaries

**Enforcement**:
- RBAC isolation tests
- Cross-namespace permission rejection tests
- Token scope validation tests

**Constraints**:
- MUST use Role (namespace-scoped), not ClusterRole for service isolation
- MUST NOT use ClusterRoleBinding for namespace-scoped privileges
- FORBIDDEN to share service account tokens across namespaces

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_service_account_namespace_isolation`

**Traceability**:
- ADR-0022 lines 56-121 (Namespace Strategy)
- security.md

---

### REQ-401: Platform Admin Service Account **[New]**

**Requirement**: System MUST create floe-platform-admin service account with full namespace admin permissions in floe-platform namespace only.

**Rationale**: Enables platform team to manage services without full cluster access.

**Acceptance Criteria**:
- [ ] ServiceAccount created: `floe-platform-admin` in `floe-platform` namespace
- [ ] Role created: `floe-platform-admin-role` with verbs: get, list, watch, create, update, patch, delete
- [ ] RoleBinding created: binding ServiceAccount to Role
- [ ] Permissions cover all floe-platform resources (deployments, statefulsets, secrets, configmaps)
- [ ] Scope limited to floe-platform namespace only

**Enforcement**:
- RBAC permission tests
- Scope limitation tests

**Constraints**:
- MUST be namespace-scoped (Role, not ClusterRole)
- MUST NOT grant cluster-admin permissions
- FORBIDDEN to allow deletion of system namespaces

**Configuration**:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: floe-platform-admin
  namespace: floe-platform
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: floe-platform-admin-role
  namespace: floe-platform
rules:
  - apiGroups: ["*"]
    resources: ["*"]
    verbs: ["*"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: floe-platform-admin-binding
  namespace: floe-platform
subjects:
  - kind: ServiceAccount
    name: floe-platform-admin
    namespace: floe-platform
roleRef:
  kind: Role
  name: floe-platform-admin-role
  apiGroup: rbac.authorization.k8s.io
```

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_platform_admin_permissions`

**Traceability**:
- ADR-0022 lines 129-143 (Platform Service Accounts)

---

### REQ-402: Dagster Service Account with Job Creation **[New]**

**Requirement**: System MUST create floe-dagster service account in floe-platform namespace with permissions to create, get, list, watch, and delete jobs in floe-jobs namespace.

**Rationale**: Enables Dagster daemon to orchestrate job execution without full platform admin access.

**Acceptance Criteria**:
- [ ] ServiceAccount created: `floe-dagster` in `floe-platform` namespace
- [ ] Role created in floe-jobs: `floe-dagster-role` with job verbs
- [ ] RoleBinding created: binding floe-dagster SA to role in floe-jobs
- [ ] Permissions include: batch/jobs (create, get, list, watch, delete)
- [ ] Permissions include: pods (get, list, watch) for log streaming
- [ ] Permissions scoped to floe-jobs namespace only

**Enforcement**:
- RBAC cross-namespace tests (floe-platform → floe-jobs)
- Job creation tests
- Log streaming tests

**Constraints**:
- MUST use RoleBinding (not ClusterRoleBinding) for cross-namespace access
- MUST NOT grant pod/exec or pod/attach (no shell access)
- FORBIDDEN to grant secret access in floe-platform namespace

**Configuration**:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: floe-dagster
  namespace: floe-platform
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: floe-dagster-role
  namespace: floe-jobs
rules:
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "get", "list", "watch", "delete"]
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: floe-dagster-job-creator
  namespace: floe-jobs
subjects:
  - kind: ServiceAccount
    name: floe-dagster
    namespace: floe-platform
roleRef:
  kind: Role
  name: floe-dagster-role
  apiGroup: rbac.authorization.k8s.io
```

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_dagster_job_creation_permissions`

**Traceability**:
- ADR-0022 lines 147-180 (Dagster Service Account)

---

### REQ-403: Job Runner Service Account (Minimal) **[New]**

**Requirement**: System MUST create floe-job-runner service account in floe-jobs namespace with minimal permissions: read-only access to specific secrets and configmaps.

**Rationale**: Limits blast radius if job pod is compromised. Job pods should only access credentials they need, not arbitrary secrets.

**Acceptance Criteria**:
- [ ] ServiceAccount created: `floe-job-runner` in `floe-jobs` namespace
- [ ] Role created: `floe-job-runner-role` with read-only verbs
- [ ] RoleBinding created: binding floe-job-runner to role
- [ ] Permissions include: secrets (get) with resourceNames: compute-credentials, catalog-credentials
- [ ] Permissions include: configmaps (get) with resourceNames: floe-job-config
- [ ] NO permissions to create, update, delete, or watch
- [ ] NO permissions for other namespaces

**Enforcement**:
- RBAC read-only tests
- Secret scope tests (resourceNames validation)
- Permission rejection tests

**Constraints**:
- MUST use resourceNames to limit which secrets/configmaps are readable
- MUST use verbs: ["get"] only (no create, update, delete, list, watch)
- FORBIDDEN to grant permissions for system namespaces (kube-system, kube-public)

**Configuration**:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: floe-job-runner
  namespace: floe-jobs
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: floe-job-runner-role
  namespace: floe-jobs
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["compute-credentials", "catalog-credentials"]
    verbs: ["get"]
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["floe-job-config"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: floe-job-runner-binding
  namespace: floe-jobs
subjects:
  - kind: ServiceAccount
    name: floe-job-runner
    namespace: floe-jobs
roleRef:
  kind: Role
  name: floe-job-runner-role
  apiGroup: rbac.authorization.k8s.io
```

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_job_runner_minimal_permissions`

**Traceability**:
- ADR-0022 lines 182-218 (Job Runner Service Account)

---

### REQ-404: Polaris Catalog Service Account **[New]**

**Requirement**: System MUST create floe-polaris service account in floe-platform namespace with permissions to manage namespace metadata and S3 credentials for storage location management.

**Rationale**: Enables Polaris to manage Iceberg namespace hierarchy and delegate storage credentials to job pods.

**Acceptance Criteria**:
- [ ] ServiceAccount created: `floe-polaris` in `floe-platform` namespace
- [ ] Permissions include: secrets (get, create, patch) for credential management
- [ ] Permissions include: configmaps (get, create, patch) for namespace metadata
- [ ] Scoped to floe-platform namespace
- [ ] Tests verify credential vending works

**Enforcement**:
- RBAC secret management tests
- Credential vending tests
- Scope validation tests

**Constraints**:
- MUST NOT grant delete permissions (prevent accidental data loss)
- MUST NOT grant permissions in floe-jobs namespace

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_polaris_credential_management`

**Traceability**:
- ADR-0022 lines 129-143

---

### REQ-405: Cube Semantic Layer Service Account **[New]**

**Requirement**: System MUST create floe-cube service account in floe-platform namespace with read-only permissions for catalog and secrets.

**Rationale**: Enables Cube to read metadata for semantic layer definitions without modification rights.

**Acceptance Criteria**:
- [ ] ServiceAccount created: `floe-cube` in `floe-platform` namespace
- [ ] Permissions: read-only (get, list, watch) for configmaps, secrets
- [ ] Scoped to floe-platform namespace
- [ ] NO permissions for job creation or cluster management

**Enforcement**:
- RBAC read-only tests
- Semantic layer metadata access tests

**Constraints**:
- MUST use read-only verbs only

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_cube_read_only_permissions`

**Traceability**:
- ADR-0022 lines 129-143

---

### REQ-406: MinIO Storage Service Account **[New]**

**Requirement**: System MUST create floe-minio service account in floe-platform namespace with PersistentVolumeClaim access for storage operations.

**Rationale**: Enables MinIO to manage persistent storage.

**Acceptance Criteria**:
- [ ] ServiceAccount created: `floe-minio` in `floe-platform` namespace
- [ ] Permissions: persistentvolumeclaims (get, list, watch)
- [ ] Scoped to floe-platform namespace

**Enforcement**:
- RBAC PVC access tests

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_minio_pvc_access`

**Traceability**:
- ADR-0022 lines 129-143

---

### REQ-407: Data Mesh Domain Service Accounts **[New]**

**Requirement**: System MUST support per-domain service accounts (floe-job-{domain}) in dedicated namespaces (floe-{domain}-domain) with domain-scoped credentials and permissions.

**Rationale**: Enables data mesh architecture where each domain team controls their own namespace and credentials.

**Acceptance Criteria**:
- [ ] ServiceAccount created per domain: `floe-job-{domain}` in `floe-{domain}-domain` namespace
- [ ] Permissions scoped to domain namespace only
- [ ] Domain credentials stored in domain namespace
- [ ] Cross-domain access denied by default

**Enforcement**:
- Data mesh isolation tests
- Cross-domain permission rejection tests

**Constraints**:
- MUST NOT allow cross-domain credential access
- MUST support dynamic domain namespace creation

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_data_mesh_domain_isolation`

**Traceability**:
- ADR-0022 lines 86-91 (Data Mesh Namespace Strategy)

---

### REQ-408: RBAC Audit Logging **[New]**

**Requirement**: System MUST configure Kubernetes audit logging to record all RBAC decisions: allow, deny, and error cases.

**Rationale**: Enables security monitoring and compliance auditing.

**Acceptance Criteria**:
- [ ] K8s audit policy configured to log RBAC decisions
- [ ] Audit logs include: verb, resource, user, namespace, decision
- [ ] Audit logs stored for minimum 90 days
- [ ] Audit logs searchable for security investigation
- [ ] Tests verify audit event format

**Enforcement**:
- Audit log format validation tests
- RBAC decision audit tests

**Constraints**:
- MUST log both allow and deny decisions
- MUST NOT log secret content (only secret names)

**Configuration**:
```yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  # Log all RBAC access
  - level: RequestResponse
    resources:
      - group: "rbac.authorization.k8s.io"
        resources: ["roles", "rolebindings", "clusterroles", "clusterrolebindings"]
    namespaces: ["floe-platform", "floe-jobs"]
```

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_rbac_audit_logging`

**Traceability**:
- ADR-0022 lines 722-765 (Audit Logging)

---

### REQ-409: RBAC Validation in Helm Charts **[New]**

**Requirement**: System MUST validate RBAC configuration in Helm charts before deployment with automated linting.

**Rationale**: Prevents RBAC misconfigurations from reaching production.

**Acceptance Criteria**:
- [ ] Helm chart linting includes RBAC schema validation
- [ ] ServiceAccount references in PodSpecs match created accounts
- [ ] RoleBinding subjects match actual ServiceAccounts
- [ ] Namespace references consistent throughout
- [ ] CI/CD pipeline runs validation on every change

**Enforcement**:
- Helm lint tests
- Schema validation tests
- Cross-reference validation tests

**Constraints**:
- MUST reject charts with dangling ServiceAccount references
- MUST validate namespace consistency

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_helm_rbac_validation`

**Traceability**:
- CLAUDE.md (Code Quality Standards)

---

### REQ-410: Service Account Token Management **[New]**

**Requirement**: System MUST configure service account token auto-mount, auto-rotation, and token expiration according to K8s best practices.

**Rationale**: Prevents token reuse and limits exposure window of compromised tokens.

**Acceptance Criteria**:
- [ ] automountServiceAccountToken=true for running pods only
- [ ] automountServiceAccountToken=false for jobs (mounts only when needed)
- [ ] Token expiration configured (K8s 1.24+ defaults to 3600s)
- [ ] Token audience configuration prevents token reuse across services

**Enforcement**:
- Pod spec validation tests
- Token lifecycle tests

**Constraints**:
- MUST respect pod.spec.serviceAccountName
- MUST use TokenRequest API (not static tokens) where supported

**Configuration**:
```yaml
spec:
  serviceAccountName: floe-job-runner
  automountServiceAccountToken: true  # Mounted automatically
  containers:
    - name: dbt
      # Token available at /var/run/secrets/kubernetes.io/serviceaccount/token
```

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_service_account_token_management`

**Traceability**:
- ADR-0022 lines 56-121

---

### REQ-411: Namespace Pod Security Standards Labels **[New]**

**Requirement**: System MUST apply Pod Security Standard labels to all floe namespaces to enforce security policies at namespace level.

**Rationale**: Prevents creation of privileged pods in restricted namespaces.

**Acceptance Criteria**:
- [ ] floe-platform namespace: pod-security.kubernetes.io/enforce=baseline
- [ ] floe-jobs namespace: pod-security.kubernetes.io/enforce=restricted
- [ ] All audit labels configured
- [ ] K8s 1.25+ required for enforcement
- [ ] Violation tests verify rejection of non-compliant pods

**Enforcement**:
- Namespace label validation tests
- Pod creation enforcement tests
- Non-compliant pod rejection tests

**Constraints**:
- MUST use enforce label (not audit or warn)
- MUST audit all PSS violations
- FORBIDDEN to use privileged pods in floe-jobs

**Configuration**:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: floe-platform
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
---
apiVersion: v1
kind: Namespace
metadata:
  name: floe-jobs
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_namespace_pod_security_labels`

**Traceability**:
- ADR-0022 lines 95-121

---

### REQ-412: Role RBAC Best Practices **[New]**

**Requirement**: System MUST follow RBAC best practices: least-privilege roles, resource-scoped permissions, verb-scoped permissions, and no wildcard verbs for sensitive operations.

**Rationale**: Reduces attack surface and limits blast radius of compromised credentials.

**Acceptance Criteria**:
- [ ] Roles use specific resources (not "*")
- [ ] Roles use specific verbs (not "*")
- [ ] Roles use resourceNames where applicable
- [ ] NO wildcard "*" verb for create, delete, update, patch
- [ ] RBAC policies follow principle of least privilege

**Enforcement**:
- RBAC policy validation tests
- Least-privilege verification tests

**Constraints**:
- FORBIDDEN: verbs: ["*"] for sensitive operations
- FORBIDDEN: resources: ["*"] except in admin role
- MUST use resourceNames for credential-related secrets

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_rbac_least_privilege_enforcement`

**Traceability**:
- ADR-0022 lines 128-218

---

### REQ-413: RBAC Compliance Testing **[New]**

**Requirement**: System MUST validate RBAC configuration through compliance tests that verify least-privilege, namespace isolation, and prevent privilege escalation.

**Rationale**: Automated tests catch RBAC misconfigurations before they reach production.

**Acceptance Criteria**:
- [ ] Tests verify each SA has minimal permissions
- [ ] Tests verify no cross-namespace privilege access
- [ ] Tests prevent service account impersonation
- [ ] Tests prevent RBAC policy modification by non-admin
- [ ] Tests prevent pod/exec access from restricted SAs

**Enforcement**:
- Compliance test suite
- Security regression tests

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_rbac_compliance_suite`

**Traceability**:
- .claude/rules/testing-standards.md

---

### REQ-414: RBAC Documentation and Governance **[New]**

**Requirement**: System MUST maintain documentation of all RBAC roles, their permissions, and justification in charts/floe-platform/rbac-governance.md.

**Rationale**: Enables security audits and prevents scope creep in permissions.

**Acceptance Criteria**:
- [ ] RBAC governance document created and maintained
- [ ] All roles documented with purpose and permissions
- [ ] Permission justification provided
- [ ] Change review process documented
- [ ] Document updated with every RBAC change

**Enforcement**:
- Documentation governance tests
- CI/CD checks that RBAC changes include doc updates

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_rbac_documentation_current`

**Traceability**:
- CLAUDE.md

---

### REQ-415: RBAC Rotation and Offboarding **[New]**

**Requirement**: System MUST support service account key rotation and safe offboarding through automated cleanup procedures.

**Rationale**: Reduces exposure of long-lived credentials.

**Acceptance Criteria**:
- [ ] Service account token rotation procedure documented
- [ ] Offboarding checklist removes SA tokens and permissions
- [ ] Cleanup automation prevents orphaned resources
- [ ] Tests verify cleanup completeness

**Enforcement**:
- Offboarding procedure tests
- Cleanup validation tests

**Test Coverage**: `tests/contract/test_rbac_isolation.py::test_rbac_rotation_offboarding`

**Traceability**:
- ADR-0022 lines 811-833

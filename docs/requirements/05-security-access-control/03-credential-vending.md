# REQ-426 to REQ-435: Pod Security Standards and Credential Vending

**Domain**: Security and Access Control
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines pod security standards that restrict pod capabilities in floe-jobs, and credential vending mechanisms that prevent hardcoded secrets while providing short-lived, scoped credentials to job pods.

**Key Principles**:
- Pod Security Standards (restricted execution)
- No Hardcoded Secrets (credential vending only)
- ADR-0022 + ADR-0023

## Requirements

### REQ-426: Pod Security Standards Enforcement **[New]**

**Requirement**: System MUST enforce Pod Security Standards at namespace level using labels: enforce=restricted for floe-jobs and enforce=baseline for floe-platform.

**Rationale**: Prevents creation of overly privileged pods and limits blast radius of container escapes.

**Acceptance Criteria**:
- [ ] floe-platform namespace has pod-security.kubernetes.io/enforce=baseline
- [ ] floe-jobs namespace has pod-security.kubernetes.io/enforce=restricted
- [ ] All audit/warn labels configured
- [ ] K8s 1.25+ required for enforcement
- [ ] Tests verify non-compliant pods rejected
- [ ] Tests verify compliant pods accepted

**Enforcement**:
- Namespace label validation tests
- Pod creation enforcement tests
- Non-compliant pod rejection tests
- Restricted PSS compliance tests

**Constraints**:
- MUST use enforce label (not audit or warn)
- MUST set to baseline (platform) or restricted (jobs)
- FORBIDDEN to use privileged pods in floe-jobs
- FORBIDDEN to use hostPath mounts in floe-jobs
- FORBIDDEN to run as root in floe-jobs

**Configuration**:
```yaml
# floe-platform namespace
apiVersion: v1
kind: Namespace
metadata:
  name: floe-platform
  labels:
    app.kubernetes.io/part-of: floe
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
---
# floe-jobs namespace
apiVersion: v1
kind: Namespace
metadata:
  name: floe-jobs
  labels:
    app.kubernetes.io/part-of: floe
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

**Test Coverage**: `tests/contract/test_pod_security.py::test_pod_security_standards_enforcement`

**Traceability**:
- ADR-0022 lines 605-667 (Pod Security Standards)

---

### REQ-427: Restricted Job Pod Security Context **[New]**

**Requirement**: System MUST configure all job pods with restrictive security context: runAsNonRoot=true, runAsUser=1000+, fsGroup=1000, seccompProfile=RuntimeDefault, readOnlyRootFilesystem=true, allowPrivilegeEscalation=false, capabilities.drop=[ALL].

**Rationale**: Prevents privilege escalation and contains blast radius of compromised job pods.

**Acceptance Criteria**:
- [ ] Job pods configured with runAsNonRoot=true
- [ ] Job pods have runAsUser >= 1000 (non-root)
- [ ] Job pods have fsGroup set consistently
- [ ] Job pods use seccompProfile=RuntimeDefault
- [ ] Job pods have readOnlyRootFilesystem=true
- [ ] Job pods have allowPrivilegeEscalation=false
- [ ] Job pods drop ALL Linux capabilities
- [ ] Tests verify pods run as non-root
- [ ] Tests verify filesystem read-only except /tmp, /home

**Enforcement**:
- Pod spec validation tests
- Security context compliance tests
- File system permission tests
- Capability drop validation tests

**Constraints**:
- MUST set runAsUser >= 1000
- MUST NOT use runAsUser: 0 (root)
- MUST drop ALL capabilities
- MUST NOT add back dangerous capabilities (CAP_SYS_ADMIN, CAP_NET_ADMIN)
- MUST have emptyDir volumes for /tmp, /home

**Configuration**:
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: dbt-run-example
  namespace: floe-jobs
spec:
  template:
    spec:
      serviceAccountName: floe-job-runner
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: dbt
          image: ghcr.io/floe/dbt:1.7
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: dbt-home
              mountPath: /home/dbt
      volumes:
        - name: tmp
          emptyDir: {}
        - name: dbt-home
          emptyDir: {}
      restartPolicy: Never
```

**Test Coverage**: `tests/contract/test_pod_security.py::test_restricted_job_pod_security_context`

**Traceability**:
- ADR-0022 lines 607-647

---

### REQ-428: Platform Service Security Context **[New]**

**Requirement**: System MUST configure platform service pods with restrictive security context: runAsNonRoot=true, runAsUser=1000+, allowPrivilegeEscalation=false, capabilities.drop=[ALL], with minimal capabilities.add if required.

**Rationale**: Reduces attack surface of platform services while allowing required functionality.

**Acceptance Criteria**:
- [ ] Platform pods configured with runAsNonRoot=true
- [ ] Platform pods have runAsUser >= 1000
- [ ] Platform pods have allowPrivilegeEscalation=false
- [ ] Platform pods drop ALL capabilities
- [ ] Platform pods add back only required capabilities (if any)
- [ ] Capability justification documented for any added capabilities

**Enforcement**:
- Pod spec validation tests
- Security context compliance tests
- Capability justification tests

**Constraints**:
- MUST NOT use runAsUser: 0 (root)
- FORBIDDEN capabilities: CAP_SYS_ADMIN, CAP_NET_ADMIN, CAP_SYS_MODULE
- MUST document justification for any capabilities.add
- FORBIDDEN to use NET_BIND_SERVICE without documentation

**Configuration Example** (Dagster):
```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
  containers:
    - name: dagster-webserver
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
          # Only add if binding to port < 1024 (not recommended)
          # add: ["NET_BIND_SERVICE"]
```

**Test Coverage**: `tests/contract/test_pod_security.py::test_platform_service_security_context`

**Traceability**:
- ADR-0022 lines 649-667

---

### REQ-429: No Hardcoded Secrets in Configuration **[New]**

**Requirement**: System MUST prevent hardcoded secrets in configuration files (manifest.yaml, floe.yaml, Helm values). All secrets MUST be referenced via SecretReference (Kubernetes Secrets, External Secrets, or Vault).

**Rationale**: Prevents accidental secret exposure in logs, diffs, and version control.

**Acceptance Criteria**:
- [ ] No literal passwords, API keys, or tokens in YAML files
- [ ] All secrets referenced via SecretReference pattern
- [ ] CI/CD scans detect hardcoded secrets (using tools like truffleHog, gitGuardian)
- [ ] Pre-commit hook prevents secret commits
- [ ] Tests verify SecretReference pattern used
- [ ] Documentation shows correct secret reference patterns

**Enforcement**:
- Secret scanning in CI/CD (Trivy, Aikido, gitGuardian)
- Pre-commit hook validation
- Configuration schema validation
- Code review process

**Constraints**:
- FORBIDDEN: password: "xyz123" in config
- FORBIDDEN: api_key: "sk-..." in code
- FORBIDDEN: database_url with hardcoded password
- MUST use: secret_ref: compute-credentials
- MUST use: SecretReference(name="polaris-oauth")

**Configuration Examples**:

Bad:
```yaml
# ❌ FORBIDDEN
plugins:
  compute:
    type: snowflake
    account: "xy12345.us-east-1"
    user: "dbt_user"
    password: "..."  # EXPOSED - hardcoded credential!
```

Good:
```yaml
# ✅ CORRECT
plugins:
  compute:
    type: snowflake
    config:
      connection_secret_ref: snowflake-credentials
      # actual secret stored in K8s Secret: snowflake-credentials
```

**Test Coverage**: `tests/contract/test_secrets.py::test_no_hardcoded_secrets`

**Traceability**:
- ADR-0023 lines 24-30 (Secrets Management Strategy)
- .claude/rules/security.md
- .claude/rules/code-quality.md (credentials in code section)

---

### REQ-430: Kubernetes Secrets Backend (Default) **[New]**

**Requirement**: System MUST support Kubernetes Secrets as default secrets backend, injecting secrets as environment variables into job pods via envFrom.secretRef.

**Rationale**: Simple, no external dependencies, works in all K8s clusters.

**Acceptance Criteria**:
- [ ] SecretsPlugin implementation for K8s Secrets created
- [ ] Secrets created as K8s Secret resources
- [ ] Secrets mounted as environment variables in pod spec
- [ ] envFrom.secretRef used for bulk secret injection
- [ ] Tests verify secrets mounted and accessible in pods
- [ ] Tests verify secret values available as env vars

**Enforcement**:
- Secrets plugin interface tests
- Pod spec validation tests
- Secret accessibility tests
- Environment variable injection tests

**Constraints**:
- MUST use envFrom for secret injection (not individual env vars)
- MUST NOT mount secrets as files (unless explicitly required)
- FORBIDDEN to log secret values
- MUST use base64 encoding (K8s standard)

**Configuration**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: snowflake-credentials
  namespace: floe-jobs
stringData:
  SNOWFLAKE_ACCOUNT: "xy12345.us-east-1"
  SNOWFLAKE_USER: "dbt_user"
  SNOWFLAKE_PASSWORD: "..."  # Anti-pattern: hardcoded
---
# Job pod spec
spec:
  containers:
    - name: dbt
      envFrom:
        - secretRef:
            name: snowflake-credentials
```

**Test Coverage**: `tests/contract/test_secrets.py::test_k8s_secrets_backend`

**Traceability**:
- ADR-0023 lines 223-270 (Kubernetes Secrets)

---

### REQ-431: Secrets Management Backend Integration **[Updated]**

**Requirement**: System MUST support Infisical as the default secrets management backend for syncing secrets to Kubernetes. System MAY support External Secrets Operator (ESO) for migration compatibility from legacy ESO deployments.

**Rationale**: Infisical provides open-source secrets management with active development and native Kubernetes integration. ESO development has been paused (August 2025) due to maintainer burnout, making Infisical the strategic choice for new deployments.

**Acceptance Criteria**:
- [ ] InfisicalSecretsPlugin implementation created (default)
- [ ] InfisicalSecret CRD integration configured
- [ ] Secrets synced automatically with auto-reload annotations
- [ ] Tests verify synced K8s Secrets created
- [ ] Tests verify auto-reload triggers pod restart
- [ ] ESO plugin maintained for migration path (optional)
- [ ] Migration guide from ESO to Infisical documented

**Enforcement**:
- Infisical integration tests (primary)
- Secret sync validation tests
- Auto-reload annotation tests
- ESO migration compatibility tests (optional)

**Constraints**:
- MUST use Infisical as default for new deployments
- MUST support auto-reload annotations for zero-downtime rotation
- MAY support ESO for migration compatibility (not recommended for new deployments)
- FORBIDDEN to hardcode credentials in InfisicalSecret CRDs

**Configuration (Infisical - Default)**:
```yaml
# Infisical Token Secret Store
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: snowflake-credentials
  namespace: floe-jobs
  annotations:
    secrets.infisical.com/auto-reload: "true"  # Auto-reload on secret change
spec:
  hostAPI: https://app.infisical.com/api
  resyncInterval: 60  # Sync every 60 seconds
  authentication:
    universalAuth:
      secretsScope:
        projectSlug: floe-platform
        envSlug: production
        secretsPath: /snowflake
      credentialsRef:
        secretName: infisical-universal-auth
        secretNamespace: floe-platform
  managedSecretReference:
    secretName: snowflake-credentials
    secretType: Opaque
    creationPolicy: Orphan
```

**Configuration (ESO - Migration Only)**:
```yaml
# External Secrets Operator (legacy - for migration only)
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: snowflake-credentials-eso
  namespace: floe-jobs
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: snowflake-credentials
    creationPolicy: Owner
  data:
    - secretKey: SNOWFLAKE_ACCOUNT
      remoteRef:
        key: floe/prod/snowflake
        property: account
```

**Test Coverage**:
- `tests/contract/test_secrets.py::test_infisical_integration` (primary)
- `tests/contract/test_secrets.py::test_eso_migration_compatibility` (optional)

**Traceability**:
- **ADR-0031** (Infisical Secrets Management) - **Supersedes ADR-0023**
- ADR-0023 lines 272-324 (External Secrets Operator) - **Deprecated**

**Migration Path**:
See `docs/guides/eso-to-infisical-migration.md` for step-by-step migration from ESO to Infisical.

---

### REQ-432: HashiCorp Vault Integration **[New]**

**Requirement**: System MUST support HashiCorp Vault as optional secrets backend for dynamic database credentials with automatic rotation.

**Rationale**: Enables short-lived credentials with automatic rotation, no manual credential management.

**Acceptance Criteria**:
- [ ] VaultSecretsPlugin implementation created
- [ ] K8s auth method configured in Vault
- [ ] Dynamic database credentials generated on demand
- [ ] Credential TTL enforced (default 1h)
- [ ] Tests verify dynamic credential generation
- [ ] Tests verify credential TTL enforcement

**Enforcement**:
- Vault integration tests
- Dynamic credential generation tests
- TTL enforcement tests
- Lease management tests

**Constraints**:
- MUST use K8s service account auth (JWT)
- MUST set credential TTL <= 1h
- MUST NOT cache credentials longer than TTL
- MUST revoke credentials on job failure

**Configuration**:
```hcl
# Vault policy
path "floe/*" {
  capabilities = ["read", "list"]
}

path "database/creds/snowflake-dbt" {
  capabilities = ["read"]
}

# Kubernetes auth method
resource "vault_kubernetes_auth_backend_role" "floe_runtime" {
  backend                          = vault_auth_backend.kubernetes.path
  role_name                        = "floe"
  bound_service_account_names      = ["floe-job-runner"]
  bound_service_account_namespaces = ["floe-jobs"]
  token_policies                   = ["floe"]
  token_ttl                        = 3600
}
```

**Test Coverage**: `tests/contract/test_secrets.py::test_hashicorp_vault_integration`

**Traceability**:
- ADR-0023 lines 375-443 (HashiCorp Vault)

---

### REQ-433: Polaris Credential Vending **[New]**

**Requirement**: System MUST integrate Polaris credential vending to provide short-lived S3 credentials for object storage access (1 hour TTL).

**Rationale**: Eliminates static S3 credentials, reduces exposure window, automatic rotation.

**Acceptance Criteria**:
- [ ] Polaris credential vending API calls implemented
- [ ] Credentials requested at job start (not compile time)
- [ ] Credentials include accessKeyId, secretAccessKey, sessionToken
- [ ] TTL <= 1 hour
- [ ] Credentials refreshed if job runs longer than TTL
- [ ] Tests verify credential vending works
- [ ] Tests verify expired credentials rejected

**Enforcement**:
- Polaris API integration tests
- Credential freshness validation tests
- TTL enforcement tests

**Constraints**:
- MUST request credentials at runtime (not compile time)
- MUST use table-specific permissions (scope to actual tables)
- MUST NOT cache credentials longer than TTL
- FORBIDDEN to hardcode S3 credentials

**Python API Example**:
```python
def vend_credentials(
    self,
    table_path: str,
    operations: list[str]  # ["READ", "WRITE"]
) -> dict:
    """Request short-lived credentials from Polaris."""
    response = self.client.post(
        f"{self.catalog_uri}/v1/credentials/vend",
        json={
            "table": table_path,
            "operations": operations,
        }
    )
    return {
        "access_key_id": response["accessKeyId"],
        "secret_access_key": response["secretAccessKey"],
        "session_token": response["sessionToken"],
        "expiration": response["expiration"],  # Unix timestamp
    }
```

**Test Coverage**: `tests/contract/test_secrets.py::test_polaris_credential_vending`

**Traceability**:
- ADR-0023 lines 581-605 (Credential Vending - Polaris)

---

### REQ-434: Secret Rotation and Lifecycle **[New]**

**Requirement**: System MUST support secret rotation without application downtime through Reloader or equivalent mechanism that detects K8s Secret changes and restarts pods.

**Rationale**: Enables rotating credentials without manual pod restarts.

**Acceptance Criteria**:
- [ ] Reloader (stakater/Reloader) deployed and configured
- [ ] Deployment annotations: reloader.stakater.com/auto=true
- [ ] Secret changes trigger automatic pod restart
- [ ] Tests verify pod restarts on secret change
- [ ] Tests verify new secrets available after restart
- [ ] Rotation procedure documented

**Enforcement**:
- Reloader deployment tests
- Secret rotation validation tests
- Pod restart trigger tests

**Constraints**:
- MUST use Reloader or equivalent
- MUST restart all affected pods
- MUST NOT lose in-flight requests (graceful termination)
- FORBIDDEN to require manual kubectl restart

**Configuration**:
```yaml
# Deployment with Reloader annotation
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dagster-daemon
  annotations:
    reloader.stakater.com/auto: "true"  # Auto-restart on secret change
spec:
  template:
    spec:
      containers:
        - name: daemon
          envFrom:
            - secretRef:
                name: snowflake-credentials
```

**Test Coverage**: `tests/contract/test_secrets.py::test_secret_rotation_without_downtime`

**Traceability**:
- ADR-0023 lines 509-550 (Secret Rotation)

---

### REQ-435: Secret Validation in CI/CD **[New]**

**Requirement**: System MUST validate secrets configuration in CI/CD pipeline: check secret references exist, verify no hardcoded secrets, validate secret naming conventions.

**Rationale**: Catches secret configuration errors before deployment.

**Acceptance Criteria**:
- [ ] CI/CD job validates secret references in manifest.yaml
- [ ] CI/CD job runs secret scanning (truffleHog, gitGuardian, Aikido)
- [ ] CI/CD job validates secret naming convention: {service}-{environment}-credentials
- [ ] CI/CD job checks referenced secrets exist in K8s cluster
- [ ] Tests verify validation catches errors
- [ ] Validation blocks deployment on failure

**Enforcement**:
- Secret validation tests
- Pre-deployment validation
- Secret scanning integration tests

**Constraints**:
- MUST validate secret naming convention
- MUST verify referenced secrets exist (except on first deploy)
- MUST block deployment if secrets missing
- FORBIDDEN to deploy with hardcoded secrets

**CLI Example**:
```bash
# Validate secret references
floe secrets validate

# Output:
# Validating secret references in manifest.yaml...
# ✓ snowflake-credentials: exists, 3 keys
# ✓ catalog-credentials: exists, 2 keys
# ✗ salesforce-credentials: NOT FOUND
#
# 1 error found. Run 'floe secrets create salesforce-credentials' to fix.
```

**Test Coverage**: `tests/contract/test_secrets.py::test_secret_validation_in_cicd`

**Traceability**:
- ADR-0023 lines 762-798 (CLI Commands)
- .claude/rules/security.md

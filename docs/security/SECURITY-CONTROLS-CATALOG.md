# Security Controls Catalog - floe-platform Helm Chart

**Purpose**: Comprehensive inventory of all existing security controls in the Helm chart. This serves as the baseline for consistent remediation patterns.

**Last Updated**: 2026-02-01
**Chart Version**: 0.1.0

---

## Table of Contents

1. [Pod Security Standards (PSS)](#pod-security-standards-pss)
2. [Security Contexts](#security-contexts)
   - [Pod-Level](#pod-level-security-context)
   - [Container-Level](#container-level-security-context)
3. [Network Policies](#network-policies)
4. [RBAC Configuration](#rbac-configuration)
5. [Service Accounts](#service-accounts)
6. [Secret Management](#secret-management)
7. [Image Configuration](#image-configuration)
8. [Volume Security](#volume-security)
9. [Pod Disruption Budgets](#pod-disruption-budgets)
10. [Resource Quotas](#resource-quotas)
11. [Configuration Hierarchy](#configuration-hierarchy)

---

## Pod Security Standards (PSS)

**Location**: `values.yaml` lines 521-532

**Configuration**:
```yaml
podSecurityStandards:
  # Enforce PSS restricted profile for production
  profile: restricted
  # Version for PSS enforcement (e.g., v1.25, latest)
  version: latest
  # Warn when pods don't meet PSS standards
  warn: true
  # Audit when pods don't meet PSS standards
  audit: true
```

**Status**: Configured but NOT enforced via namespace labels

**Key Characteristics**:
- Profile: `restricted` (most secure, equivalent to Pod Security Policy restricted)
- Version: `latest` (tracks upstream K8s security standards)
- Warn Mode: Enabled (generates warnings without blocking)
- Audit Mode: Enabled (records violations in audit logs)

**Implementation Gap**:
- Values define the desired profile but are NOT automatically applied
- Must be manually enforced via namespace labels at deployment time:
  ```bash
  kubectl label namespace floe-dev \
    pod-security.kubernetes.io/enforce=restricted \
    pod-security.kubernetes.io/warn=restricted \
    pod-security.kubernetes.io/audit=restricted
  ```

**Consistency Pattern for Remediation**:
- Add namespace labels automatically during Helm install/upgrade
- Use Helm hooks to ensure labels are applied before pod deployment
- Document in installation guide for manual K8s setup

---

## Security Contexts

### Pod-Level Security Context

**Location**: `values.yaml` lines 535-541

**Default Configuration**:
```yaml
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault
```

**Characteristics**:
- `runAsNonRoot: true` - Prevents root execution (matches restricted PSS)
- `runAsUser: 1000` - Non-root UID (standard for floe)
- `runAsGroup: 1000` - Non-root GID
- `fsGroup: 1000` - Filesystem group ownership (for volume mounts)
- `seccompProfile: RuntimeDefault` - Uses kernel default seccomp (matches restricted PSS)

**Template Integration**:
- Applied via `{{ include "floe-platform.podSecurityContext" . }}` in pod specs
- Used in: `deployment-polaris.yaml`, statefulset deployments

**Component Overrides**:
- PostgreSQL StatefulSet (lines 32-33): Only specifies `fsGroup: 1000`
- Init containers (busybox): Override with `runAsUser: 0` for permission setup (required)

**Consistency Pattern for Remediation**:
- All pods inherit from `podSecurityContext` via helper template
- Init containers override only when necessary (permission setup, init-data)
- Document why any overrides are needed

---

### Container-Level Security Context

**Location**: `values.yaml` lines 544-551

**Default Configuration**:
```yaml
containerSecurityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
  capabilities:
    drop:
      - ALL
```

**Characteristics**:
- `allowPrivilegeEscalation: false` - Prevents privilege escalation (matches restricted PSS)
- `readOnlyRootFilesystem: true` - Immutable root filesystem (matches restricted PSS)
- `runAsNonRoot: true` - Container runs as non-root
- `runAsUser: 1000` - Standard non-root UID
- `capabilities.drop: ALL` - All Linux capabilities removed (matches restricted PSS)

**Template Integration**:
- Applied via `{{ include "floe-platform.containerSecurityContext" . }}` in container specs
- Used in: all deployment/statefulset containers

**Practical Implementation**:
- Polaris deployment (line 46): Uses helper template
- PostgreSQL container (lines 45-52): Hardcoded inline (should use helper)
- All containers drop ALL capabilities

**Volume Mounts with Security Context**:
```yaml
volumeMounts:
  - name: config        # ConfigMap - readOnly
    mountPath: /opt/polaris/conf
    readOnly: true
  - name: tmp           # emptyDir - writable for logs/temp
    mountPath: /tmp
```

**Consistency Pattern for Remediation**:
- All containers use helper template (avoid hardcoding)
- Writable volumes limited to: `/tmp` (emptyDir), data directories (PVC)
- Config/secrets mounted as read-only
- Document any container that deviates from standard context

---

## Network Policies

**Location**: `templates/networkpolicy.yaml`
**Control**: `values.yaml` line 558 - `networkPolicy.enabled: false` (disabled by default)

**Current Status**: DISABLED - must be explicitly enabled per environment

**Policy Types Implemented**:

### 1. Default Deny All Ingress (lines 8-21)
```yaml
kind: NetworkPolicy
metadata:
  name: {release}-default-deny
spec:
  podSelector: {}  # Applies to all pods
  policyTypes:
    - Ingress
  # No allow rules = deny all ingress
```

**Effect**: All pods deny ingress traffic by default

---

### 2. Dagster Network Policy (lines 23-86)
```yaml
Ingress Rules:
  - From: Ingress controller (if enabled)
    Port: 3000 (webserver)
  - From: Other Dagster pods
    Ports: 3000, 4000

Egress Rules:
  - To: PostgreSQL pods (5432)
  - To: Polaris catalog (8181)
  - To: kube-dns (UDP 53 for DNS resolution)
```

**Key Characteristics**:
- Allows ingress from ingress controller ONLY if `ingress.enabled: true`
- Allows internal pod-to-pod communication on ports 3000, 4000
- Egress: Database, catalog, DNS only
- Denies all other egress

---

### 3. Polaris Network Policy (lines 88-145)
```yaml
Ingress Rules:
  - From: Dagster pods (8181)
  - From: floe-jobs pods (8181)

Egress Rules:
  - To: PostgreSQL pods (5432)
  - To: MinIO pods (9000)
  - To: kube-dns (UDP 53)
```

**Key Characteristics**:
- Restricted ingress from only Dagster and job pods
- Egress to: database, object storage, DNS
- Denies all other egress

---

### 4. PostgreSQL Network Policy (lines 147-177)
```yaml
Ingress Rules:
  - From: Dagster pods (5432)
  - From: Polaris pods (5432)

Egress Rules:
  - None configured (database pods don't initiate connections)
```

**Key Characteristics**:
- Only allows ingress from application pods
- No egress rules (PostgreSQL is passive)

---

### 5. OpenTelemetry Network Policy (lines 179-202)
```yaml
Ingress Rules:
  - From: All pods in namespace (podSelector: {})
  Ports:
    - 4317 (OTLP gRPC)
    - 4318 (OTLP HTTP)

Egress Rules:
  - None configured
```

**Key Characteristics**:
- Permissive: All pods can send traces
- Receive-only (passive)
- No external egress

---

**Consistency Pattern for Remediation**:
- Default deny + explicit allow pattern (zero-trust)
- Service-to-service communication documented by port/protocol
- DNS explicitly allowed (UDP 53)
- External egress restricted or documented
- Enable via: `--set networkPolicy.enabled=true`

---

## RBAC Configuration

**Location**:
- `values.yaml` lines 497-499 (enable/disable)
- `templates/role.yaml`
- `templates/rolebinding.yaml`

**Enable/Disable Control**:
```yaml
rbac:
  create: true  # Create RBAC resources (enabled by default)
```

### Role Definition

**Location**: `templates/role.yaml` lines 1-37

**Resources & Verbs**:

| API Group | Resources | Verbs | Purpose |
|-----------|-----------|-------|---------|
| `""` (core) | `pods`, `pods/log`, `pods/status` | `get`, `list`, `watch`, `create`, `delete` | K8sRunLauncher: Create/monitor/clean pod runs |
| `""` | `configmaps`, `secrets` | `get`, `list`, `watch` | Pod configuration |
| `""` | `events` | `get`, `list`, `watch`, `create` | Event recording |
| `batch` | `jobs`, `jobs/status` | `get`, `list`, `watch`, `create`, `delete`, `patch` | K8sRunLauncher: Job execution |
| `""` | `services` | `get`, `list`, `watch` | Service discovery |
| `""` | `persistentvolumeclaims` | `get`, `list`, `watch` | Volume access |

**Principle of Least Privilege**:
- Resource-scoped (no cluster-wide permissions)
- Namespace-scoped (via RoleBinding)
- Verb-limited to specific operations
- No wildcard verbs or resources

### RoleBinding

**Location**: `templates/rolebinding.yaml` lines 1-17

**Configuration**:
```yaml
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role  # Namespace-scoped (not ClusterRole)
  name: {release}

subjects:
  - kind: ServiceAccount
    name: {auto-generated or custom}
    namespace: {release-namespace}
```

**Characteristic**: Namespace-scoped RBAC (least privilege)

---

### Service Account

**Location**: `templates/serviceaccount.yaml`

**Configuration**:
```yaml
serviceAccount:
  create: true
  name: ""  # Auto-generated
  automountServiceAccountToken: true
  annotations: {}
```

**Token Automount**:
- Enabled by default (`automountServiceAccountToken: true`)
- Automatically mounts service account token at `/var/run/secrets/kubernetes.io/serviceaccount/`
- Used by K8sRunLauncher to authenticate API calls

**Consistency Pattern for Remediation**:
- RBAC resources created when `rbac.create: true`
- Service accounts auto-generated from release name
- No manual secret creation (Kubernetes automatic)
- Document RBAC usage in runLauncher configuration

---

## Secret Management

**Locations**:
- `templates/secret-postgresql.yaml`
- `templates/secret-dagster.yaml`
- `templates/externalsecret.yaml`
- `values.yaml` lines 662-703 (externalSecrets config)

### 1. PostgreSQL Secret (Kubernetes Native)

**Template**: `secret-postgresql.yaml` lines 1-18

**Configuration**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {release}-postgresql
type: Opaque
data:
  postgresql-password: (base64-encoded)
  postgresql-postgres-password: (base64-encoded)
stringData:
  postgresql-url: postgresql://user:password@host:5432/db  # pragma: allowlist secret
```

**Encryption Characteristics**:
- Type: `Opaque` (unencrypted at rest by default)
- Data keys: base64-encoded (NOT encrypted)
- StringData keys: plain text stored in etcd
- Vault behavior: Depends on cluster etcd encryption (`--encryption-provider-config`)

**Conditional Creation**:
```
IF postgresql.enabled AND NOT postgresql.auth.existingSecret
THEN create secret
```

**Limitations**:
- Default K8s secrets NOT encrypted at rest
- Must enable etcd encryption for production: https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/

---

### 2. Dagster Secret (Kubernetes Native)

**Template**: `secret-dagster.yaml` lines 1-41

**Configuration**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: dagster-postgresql-secret  # Configurable via values
type: Opaque
data:
  postgresql-password: (base64-encoded from postgresql.auth.password)
stringData:
  postgresql-connection: postgresql://user:password@host:5432/dagster  # pragma: allowlist secret
```

**Conditional Creation**:
```
IF dagster.enabled AND NOT dagster.generatePostgresqlPasswordSecret
THEN create secret
```

**Consumption Pattern**:
```yaml
env:
  - name: DAGSTER_PG_PASSWORD
    valueFrom:
      secretKeyRef:
        name: dagster-postgresql-secret
        key: postgresql-password
```

---

### 3. External Secrets Integration

**Template**: `externalsecret.yaml` lines 1-123

**Purpose**: Sync secrets from external providers (AWS Secrets Manager, Vault, Azure Key Vault)

**Configuration Location**: `values.yaml` lines 662-703

**Enable/Disable**:
```yaml
externalSecrets:
  enabled: false  # Disabled by default

  # Secret store reference (default for all secrets)
  secretStoreRef:
    name: ""  # Name of SecretStore/ClusterSecretStore
    kind: ClusterSecretStore

  # Refresh interval
  refreshInterval: 1h
```

**Pre-configured Secret Templates**:

#### PostgreSQL External Secret
```yaml
externalSecrets:
  postgresql:
    enabled: false
    remoteRef:
      key: ""  # e.g., floe/prod/postgresql
      property: password
```

When enabled, creates:
```yaml
kind: ExternalSecret
metadata:
  name: {release}-postgresql
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: {configured-store}
    kind: ClusterSecretStore
  target:
    name: {release}-postgresql  # Syncs to this K8s secret
  data:
    - secretKey: password
      remoteRef:
        key: floe/prod/postgresql
        property: password
```

#### MinIO External Secret
```yaml
externalSecrets:
  minio:
    enabled: false
    remoteRef:
      key: ""  # e.g., floe/prod/minio
      userProperty: username
      passwordProperty: password
```

When enabled, creates ExternalSecret for MinIO credentials

#### Custom Secrets
```yaml
externalSecrets:
  secrets:
    - name: custom-secret
      targetSecretName: my-secret  # Optional: defaults to name
      secretStoreRef:  # Optional: overrides default
        name: my-store
        kind: SecretStore
      data:
        - secretKey: password
          remoteRef:
            key: path/to/secret
            property: password
```

**Requirements**:
- External Secrets Operator must be installed in cluster
- SecretStore/ClusterSecretStore must be configured
- Provider credentials configured (AWS IAM, Vault token, Azure managed identity, etc.)

**Consistency Pattern for Remediation**:
- External Secrets optional (for production)
- K8s native secrets acceptable for dev/test
- Enable encryption at rest via cluster config
- Use existing secret references to avoid duplication
- Document provider setup in installation guide

---

## Image Configuration

**Locations**: `values.yaml` (per component)

### Global Image Settings
```yaml
global:
  imagePullPolicy: IfNotPresent
  imagePullSecrets: []  # For private registries
```

### Per-Component Image Configuration

| Component | Repository | Tag | Pull Policy | Configurable |
|-----------|------------|-----|-------------|-------------|
| Polaris | `apache/polaris` | `0.9.0` | Inherited | Yes |
| PostgreSQL | `postgres` | `16-alpine` | Inherited | Yes |
| Dagster | `docker.io/dagster/dagster-celery-k8s` | (from chart) | Inherited | Yes |
| OpenTelemetry | `otel/opentelemetry-collector-contrib` | (from chart) | Inherited | Yes |

### Security Characteristics
- **Image Digest**: NOT used (tag-only, vulnerable to tag mutations)
- **Image Pull Secrets**: Optional (for private registries)
- **Alpine Base**: PostgreSQL uses `postgres:16-alpine` (smaller attack surface)
- **Init Container Image**: `busybox:1.36` (minimal image for permission setup)

**Consistency Pattern for Remediation**:
- Use image digests (SHA256) instead of tags for production
- Scan images for vulnerabilities (Trivy, Snyk, etc.)
- Restrict image registries via admission controllers
- Document image scanning in CI/CD pipeline

---

## Volume Security

### Volume Types Used

| Volume Type | Mounted For | Read-Only | Encryption | Lifecycle |
|-------------|-----------|-----------|------------|-----------|
| ConfigMap | Config/credentials | Yes | No | Pod lifetime |
| Secret | Secrets | No | No (at rest) | Pod lifetime |
| emptyDir | Temp data (/tmp) | No | No | Pod lifetime |
| PVC | Persistent data | No | No | Beyond pod |

### Polaris Volumes (deployment-polaris.yaml lines 81-101)
```yaml
volumeMounts:
  - name: config              # ConfigMap
    mountPath: /opt/polaris/conf
    readOnly: true
  - name: polaris-data        # PVC (if type: file)
    mountPath: /data/polaris
  - name: tmp                 # emptyDir
    mountPath: /tmp
```

### PostgreSQL Volumes (statefulset-postgresql.yaml lines 93-99)
```yaml
volumeMounts:
  - name: data                # PVC
    mountPath: /var/lib/postgresql/data
  - name: init-scripts        # ConfigMap
    mountPath: /docker-entrypoint-initdb.d
```

### Init Container Volume Access
```yaml
initContainers:
  - name: init-data-dir
    securityContext:
      runAsUser: 0            # Elevated for chmod/chown
    volumeMounts:
      - name: polaris-data
        mountPath: /data
```

**Consistency Pattern for Remediation**:
- Config/secrets: Read-only mounts when possible
- Data directories: Mounted via PVC with ownership
- Temp data: emptyDir for container lifetime
- Init containers: Elevated privileges for permission setup only
- Document volume mount justification in deployment specs

---

## Pod Disruption Budgets

**Location**: `values.yaml` lines 593-616

**Enable/Disable**:
```yaml
podDisruptionBudget:
  enabled: false  # Disabled by default
  minAvailable: 1  # Global default
```

**Component-Specific PDB**:
```yaml
podDisruptionBudget:
  dagster:
    enabled: true  # Enabled when parent enabled
    minAvailable: 1

  polaris:
    enabled: true
    minAvailable: 1

  postgresql:
    enabled: true
    minAvailable: 1
```

**Template**: `templates/pdb.yaml`

**Characteristics**:
- Ensures minimum pod availability during voluntary disruptions
- Applied per component (Dagster, Polaris, PostgreSQL)
- Not security-related but prevents disruption exploitation

**Consistency Pattern for Remediation**:
- PDB standard for HA deployments
- Document in SLA/availability requirements

---

## Resource Quotas

**Location**: `values.yaml` lines 646-657

**Enable/Disable**:
```yaml
resourceQuota:
  enabled: false  # Disabled by default

  hard:
    requests.cpu: "10"
    requests.memory: 20Gi
    limits.cpu: "20"
    limits.memory: 40Gi
    pods: "50"
```

**Template**: `templates/resourcequota.yaml`

**Characteristics**:
- Namespace-level resource limits
- Prevents resource exhaustion attacks
- Requires resource requests/limits on all pods

**Consistency Pattern for Remediation**:
- Enable ResourceQuota for multi-tenant clusters
- Define reasonable limits per environment
- Document quota enforcement in admission controller policy

---

## Configuration Hierarchy

**Override Precedence** (highest to lowest):
1. Helm `--set` CLI flags
2. `values-{env}.yaml` files (environment-specific)
3. `values.yaml` (defaults)

**Security Context Inheritance Chain**:
```
values.yaml (podSecurityContext)
    ↓
_helpers.tpl (podSecurityContext helper)
    ↓
Deployment/StatefulSet spec
    ↓
Pod spec.securityContext
    ↓
Container spec.securityContext (can override)
```

**Example Override for Production**:
```bash
helm install floe ./charts/floe-platform \
  -f values-prod.yaml \
  --set podSecurityContext.fsGroup=2000 \
  --set networkPolicy.enabled=true \
  --set externalSecrets.enabled=true
```

---

## Security Control Status Summary

| Control | Type | Enabled | Enforced | Notes |
|---------|------|---------|----------|-------|
| Pod Security Standards | Admission | Configured | No | Must enable via namespace labels |
| Pod Security Context | Pod | Yes | Yes | Applied via pod spec |
| Container Security Context | Container | Yes | Yes | Applied via container spec |
| Network Policies | Network | Configurable | No | Disabled by default; zero-trust pattern |
| RBAC | Identity | Configurable | Yes | Namespace-scoped; least privilege |
| K8s Secrets | Secret | K8s Native | No | Unencrypted at rest (requires etcd encryption) |
| External Secrets | Secret | Optional | No | Requires External Secrets Operator |
| Image Pull Secrets | Registry | Optional | No | For private registries only |
| Pod Disruption Budget | Availability | Optional | No | HA feature, not security-focused |
| Resource Quota | Compute | Optional | No | Prevents resource exhaustion |

---

## Remediation Pattern Documentation

When implementing security fixes:

1. **Identify Control Gap**: Reference this catalog
2. **Determine Scope**: Affects which components? (values.yaml vs templates)
3. **Maintain Consistency**: Follow existing patterns (helper templates, variable naming)
4. **Document Override Path**: Show how to enable/configure via values
5. **Test in Tiers**: dev (values.yaml) → staging (values-staging.yaml) → prod (values-prod.yaml)
6. **Validate Compliance**: Verify against pod security standards

### Example: Enabling Network Policies

**Control Gap**: Network policies disabled by default

**Remediation Pattern**:
```bash
# Step 1: Enable in values
--set networkPolicy.enabled=true

# Step 2: Apply namespace labels for PSS
kubectl label namespace floe-prod \
  pod-security.kubernetes.io/enforce=restricted

# Step 3: Verify policies applied
kubectl get networkpolicies -n floe-prod

# Step 4: Test connectivity
kubectl run test-pod --image=busybox -- wget http://dagster:3000
# Expected: Connection denied
```

---

## References

- Kubernetes Pod Security Standards: https://kubernetes.io/docs/concepts/security/pod-security-standards/
- Kubernetes Network Policies: https://kubernetes.io/docs/concepts/services-networking/network-policies/
- Kubernetes RBAC: https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- External Secrets Operator: https://external-secrets.io/
- floe-platform Helm Chart: `charts/floe-platform/`

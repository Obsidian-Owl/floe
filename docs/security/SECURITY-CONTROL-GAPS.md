# Security Control Gaps and Inconsistencies

**Purpose**: Identifies gaps between configuration and enforcement, inconsistencies in implementation patterns, and recommendations for remediation.

**Audience**: Security engineers, Helm chart maintainers, K8s operators

---

## Executive Summary

The floe-platform Helm chart has well-defined security controls in `values.yaml` but several are **not automatically enforced** or have **implementation inconsistencies**. This document catalogs each gap and provides remediation patterns.

**Critical Issues** (affect security posture):
1. Pod Security Standards defined but NOT enforced
2. Network Policies disabled by default (zero-trust not enforced)
3. Secrets unencrypted at rest (K8s default)
4. PostgreSQL security context hardcoded (inconsistent pattern)

**Medium Issues** (implementation inconsistencies):
1. Container security context not using helper template in PostgreSQL
2. Init containers override security context without documentation
3. Image digests not used (tag mutation vulnerability)
4. External Secrets optional but not documented

**Low Issues** (operational):
1. Pod Disruption Budgets disabled by default
2. Resource Quotas disabled by default
3. Service account token automount always enabled

---

## Gap #1: Pod Security Standards Not Enforced

### Current State
```yaml
# values.yaml lines 521-532
podSecurityStandards:
  profile: restricted
  version: latest
  warn: true
  audit: true
```

**Issue**: Values define desired PSS profile but are **informational only**. They do NOT:
- Create namespace labels (requires manual kubectl)
- Apply admission controller policies
- Block non-compliant pods automatically

**Impact**:
- Anyone deploying to the cluster can ignore PSS
- No enforcement mechanism (helm chart responsibility)
- PSS profile not visible in pod status

### Remediation

**Option A: Helm-Native (Recommended)**

Add Helm hook to apply namespace labels:

```yaml
# templates/pss-namespace-labels.yaml
{{- if .Values.podSecurityStandards.enforceViaNamespaceLabels }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "floe-platform.fullname" . }}-pss-labels
  namespace: {{ include "floe-platform.namespace" . }}
  annotations:
    helm.sh/hook: pre-install,pre-upgrade
    helm.sh/hook-weight: "-5"
data:
  labels: |
    pod-security.kubernetes.io/enforce={{ .Values.podSecurityStandards.profile }}
    pod-security.kubernetes.io/warn={{ .Values.podSecurityStandards.profile }}
    pod-security.kubernetes.io/audit={{ .Values.podSecurityStandards.profile }}
{{- end }}
```

Add to `values.yaml`:
```yaml
podSecurityStandards:
  profile: restricted
  version: latest
  warn: true
  audit: true
  enforceViaNamespaceLabels: false  # Enable in prod
```

**Option B: Manual (Current Practice)**

Document in installation guide:
```bash
# After helm install, apply namespace labels
kubectl label namespace {{ .Release.Namespace }} \
  pod-security.kubernetes.io/enforce={{ .Values.podSecurityStandards.profile }} \
  pod-security.kubernetes.io/warn={{ .Values.podSecurityStandards.profile }} \
  pod-security.kubernetes.io/audit={{ .Values.podSecurityStandards.profile }} \
  --overwrite
```

### Consistency Pattern

Once implemented, other gaps will follow naturally:
- If PSS enforced, all pods must comply with `podSecurityContext` and `containerSecurityContext`
- If PSS enforced, `readOnlyRootFilesystem: true` forces volume mount planning
- If PSS enforced, network policies become critical (no host networking)

---

## Gap #2: Network Policies Disabled by Default

### Current State
```yaml
# values.yaml lines 556-564
networkPolicy:
  enabled: false  # Must be explicitly enabled
  ingress: []
  egress: []
```

**Issue**: Chart provides well-designed zero-trust network policies but they're:
- Disabled by default (development mode)
- Not enforced by default (staging/prod must explicitly enable)
- No upgrade path documented (enabling after deployment)

**Impact**:
- Production deployments may forget to enable
- No segregation between services
- No protection against lateral movement
- Pods can reach anything in cluster/internet

### Remediation

**Option A: Environment-Based Defaults**

Add to `values.yaml`:
```yaml
networkPolicy:
  # Enable based on environment
  enabled: {{ eq .Values.global.environment "prod" }}

  # Allow overrides per environment
  ingress: []
  egress: []
```

Update `values-prod.yaml`:
```yaml
networkPolicy:
  enabled: true
```

**Option B: Explicit Production Requirement**

Add validation in `templates/NOTES.txt`:
```
{{- if and (eq .Values.global.environment "prod") (not .Values.networkPolicy.enabled) }}
WARNING: NetworkPolicy disabled in PRODUCTION environment!
Enable with: --set networkPolicy.enabled=true
{{- end }}
```

**Option C: Helm Pre-Install Hook**

```yaml
# templates/validate-prod-networking.yaml
{{- if eq .Values.global.environment "prod" }}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "floe-platform.fullname" . }}-validate-networking
  annotations:
    helm.sh/hook: pre-install,pre-upgrade
    helm.sh/hook-weight: "-10"
spec:
  template:
    spec:
      serviceAccountName: {{ include "floe-platform.serviceAccountName" . }}
      containers:
        - name: validate
          image: bitnami/kubectl:latest
          command:
            - /bin/sh
            - -c
            - |
              {{- if not .Values.networkPolicy.enabled }}
              echo "ERROR: NetworkPolicy disabled in production!"
              exit 1
              {{- end }}
{{- end }}
```

### Consistency Pattern

Network policy design is already solid (zero-trust pattern):
- Default deny all
- Service-to-service allow rules
- DNS explicitly allowed
- No unnecessary egress

Just needs enforcement mechanism.

---

## Gap #3: Secrets Unencrypted at Rest

### Current State
```yaml
# templates/secret-postgresql.yaml
kind: Secret
type: Opaque  # Unencrypted by default
data:
  postgresql-password: (base64 only)
stringData:
  postgresql-url: postgresql://...
```

**Issue**:
- K8s Secrets are base64-encoded, NOT encrypted at rest
- Stored in etcd without encryption by default
- etcd encryption optional (requires cluster-level config)
- No chart-level mechanism to enforce encryption

**Impact**:
- Credentials visible in etcd backups
- Credentials exposed if etcd accessed
- No audit trail for secret access
- External Secrets optional (better alternative)

### Remediation

**Option A: Require External Secrets (Recommended for Prod)**

Make External Secrets mandatory:
```yaml
# values.yaml
externalSecrets:
  required: false  # false for dev, true for prod

  # Validation in template
  {{- if and (eq .Values.global.environment "prod") .Values.externalSecrets.required }}
    {{- if not .Values.externalSecrets.enabled }}
      {{- fail "ERROR: External Secrets required in production" }}
    {{- end }}
  {{- end }}
```

**Option B: Document Cluster-Level Encryption**

Add to installation guide:
```bash
# Enable etcd encryption at rest (cluster-level, not chart-level)
# Requires API server restart
--encryption-provider-config=/etc/kubernetes/pki/encryption-config.yaml
```

Configuration file (`/etc/kubernetes/pki/encryption-config.yaml`):
```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: <base64-encoded 32-byte key>
      - identity: {}  # Fallback
```

**Option C: Use Sealed Secrets (GitOps-Compatible)**

```yaml
# templates/sealedsecret-postgresql.yaml
{{- if .Values.sealedSecrets.enabled }}
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: {{ include "floe-platform.fullname" . }}-postgresql
spec:
  encryptedData:
    postgresql-password: AgBv...  # Sealed with public key
  template:
    metadata:
      name: {{ include "floe-platform.fullname" . }}-postgresql
    type: Opaque
{{- end }}
```

### Consistency Pattern

Order of preference:
1. **External Secrets** (best for production - syncs from AWS Secrets Manager, Vault, etc.)
2. **Sealed Secrets** (good for GitOps - commits encrypted secrets)
3. **etcd Encryption** (cluster-level - requires infrastructure setup)
4. **K8s Secrets only** (minimum security - for dev/test only)

Document each tier in values comments.

---

## Gap #4: PostgreSQL Security Context Hardcoded

### Current State

**Polaris Deployment** (uses helper):
```yaml
# deployment-polaris.yaml line 46
securityContext:
  {{- include "floe-platform.containerSecurityContext" . | nindent 12 }}
```

**PostgreSQL StatefulSet** (hardcoded):
```yaml
# statefulset-postgresql.yaml lines 45-52
securityContext:
  runAsUser: 1000
  runAsGroup: 1000
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
```

**Issue**:
- PostgreSQL duplicates security context instead of using helper
- Inconsistent patterns across deployments
- Harder to update security context globally
- Maintenance burden (two places to update)

### Remediation

**Option A: Use Helper Template**

Update `statefulset-postgresql.yaml`:
```yaml
containers:
  - name: postgresql
    securityContext:
      {{- include "floe-platform.containerSecurityContext" . | nindent 12 }}
```

**Option B: Add PostgreSQL-Specific Helper**

```tpl
{{- define "floe-platform.postgresqlSecurityContext" -}}
runAsUser: 1000
runAsGroup: 1000
runAsNonRoot: true
allowPrivilegeEscalation: false
capabilities:
  drop:
    - ALL
readOnlyRootFilesystem: {{ .Values.postgresql.readOnlyRootFilesystem | default true }}
{{- end }}
```

Then use:
```yaml
securityContext:
  {{- include "floe-platform.postgresqlSecurityContext" . | nindent 12 }}
```

### Consistency Pattern

All containers should use helper templates:
- `floe-platform.containerSecurityContext` (default for most)
- `floe-platform.postgresqlSecurityContext` (PostgreSQL-specific if needed)
- `floe-platform.initContainerSecurityContext` (init containers)

Benefits:
- Single source of truth
- Global security context updates easy
- Audit trail (diffs show all affected components)

---

## Gap #5: Init Containers Override Security Context Without Documentation

### Current State

**Polaris Init Container** (line 38-39):
```yaml
initContainers:
  - name: init-data-dir
    image: busybox:1.36
    securityContext:
      runAsUser: 0  # OVERRIDE: Requires root for chown
```

**PostgreSQL Init Container** (line 39):
```yaml
initContainers:
  - name: init-permissions
    image: busybox:1.36
    securityContext:
      runAsUser: 0
```

**Issue**:
- Init containers run as root (violation of `runAsNonRoot: true` in pod spec)
- No comments explaining why root is required
- No validation that commands only perform needed operations
- No cleanup after init (permissions remain elevated for container lifetime)

### Remediation

**Option A: Add Documentation**

```yaml
initContainers:
  - name: init-data-dir
    image: busybox:1.36
    # NOTE: Requires root (uid 0) for chown/chmod operations
    # This init container sets directory ownership to 1000:1000
    # After initialization, main container runs as uid 1000 (non-root)
    securityContext:
      runAsUser: 0
      runAsNonRoot: false  # Explicit override
      allowPrivilegeEscalation: false  # Still restrict escalation
    command:
      - sh
      - -c
      - |
        mkdir -p /data/polaris && \
        chown -R 1000:1000 /data/polaris
```

**Option B: Add Init Container Helper**

```tpl
{{- define "floe-platform.initContainerSecurityContext" -}}
# Init containers with elevated privileges for setup operations
# Main container runs as non-root (pod.securityContext)
runAsUser: 0
runAsNonRoot: false
allowPrivilegeEscalation: false
capabilities:
  drop:
    - ALL
{{- end }}
```

Usage:
```yaml
initContainers:
  - name: init-data-dir
    securityContext:
      {{- include "floe-platform.initContainerSecurityContext" . | nindent 6 }}
    command:
      - sh
      - -c
      - 'mkdir -p /data/polaris && chown -R 1000:1000 /data/polaris'
```

**Option C: Pre-populate Directories**

Instead of init container chown, use PVC with correct ownership:
```yaml
volumeClaimTemplates:
  - metadata:
      name: polaris-data
    spec:
      # fsGroup in pod spec handles ownership
      # No init container needed
```

### Consistency Pattern

Init containers should:
1. Have minimal scope (single responsibility)
2. Include comments explaining privilege elevation
3. Use helper templates (even for elevated contexts)
4. Prefer fsGroup over chown when possible

---

## Gap #6: Image Tags Not Using Digests

### Current State
```yaml
polaris:
  image:
    repository: apache/polaris
    tag: "0.9.0"  # Tag only, not digest

postgresql:
  image:
    repository: postgres
    tag: "16-alpine"  # Tag only
```

**Issue**:
- Tags are mutable (image tag could be reassigned)
- No guarantee container image hasn't changed
- Vulnerable to supply chain attacks
- Policy enforcement tools (image scanning) can be bypassed

**Impact**:
- Compromised image could be pushed with same tag
- Audit trail doesn't catch tag mutations
- Security scans not enforced per-deployment

### Remediation

**Option A: Use Image Digests (Recommended)**

```yaml
polaris:
  image:
    repository: apache/polaris
    tag: ""  # Deprecated
    digest: sha256:abc123...  # Use digest instead

postgresql:
  image:
    repository: postgres
    tag: ""
    digest: sha256:def456...
```

Template:
```yaml
image: "{{ .Values.polaris.image.repository }}@{{ .Values.polaris.image.digest }}"
```

**Option B: Support Both Tags and Digests**

```yaml
polaris:
  image:
    repository: apache/polaris
    tag: "0.9.0"
    digest: ""  # Optional override

postgresql:
  image:
    repository: postgres
    tag: "16-alpine"
    digest: ""  # Optional override
```

Template:
```yaml
{{- if .Values.polaris.image.digest }}
image: "{{ .Values.polaris.image.repository }}@{{ .Values.polaris.image.digest }}"
{{- else }}
image: "{{ .Values.polaris.image.repository }}:{{ .Values.polaris.image.tag | default .Chart.AppVersion }}"
{{- end }}
```

**Option C: Policy Enforcement**

Validate via pre-install hook:
```yaml
# templates/validate-image-digests.yaml
{{- if eq .Values.global.environment "prod" }}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "floe-platform.fullname" . }}-validate-images
  annotations:
    helm.sh/hook: pre-install,pre-upgrade
spec:
  template:
    spec:
      containers:
        - name: validate
          image: curlimages/curl:latest
          command:
            - sh
            - -c
            - |
              {{- if not (contains "@sha256" .Values.polaris.image.repository) }}
              echo "ERROR: Production requires image digests (not tags)"
              exit 1
              {{- end }}
{{- end }}
```

### Consistency Pattern

Image configuration hierarchy:
1. **Production**: Digests only (immutable)
2. **Staging**: Digests recommended, tags allowed
3. **Dev**: Tags allowed (faster iteration)

Document in installation guide.

---

## Gap #7: External Secrets Optional Without Clear Guidance

### Current State
```yaml
externalSecrets:
  enabled: false  # Optional

  postgresql:
    enabled: false  # Optional

  minio:
    enabled: false  # Optional

  secrets: []  # Optional
```

**Issue**:
- External Secrets optional without clear security justification
- No guidance on when to use vs. K8s native secrets
- Production deployments may not know they need it
- External Secrets Operator not mentioned as dependency

**Impact**:
- Secrets stored unencrypted in etcd by default
- Mixed patterns across environments
- No audit trail for secret access
- Difficult to rotate credentials

### Remediation

**Option A: Environment-Based Defaults**

```yaml
# values.yaml
externalSecrets:
  # Enable by default in prod (cluster admin must install operator)
  enabled: {{ eq .Values.global.environment "prod" }}

  # For dev/test, use K8s native secrets
  # For prod, require External Secrets Operator

  secretStoreRef:
    name: ""  # Must be configured for prod
    kind: ClusterSecretStore
```

**Option B: Add Requirements Documentation**

```yaml
externalSecrets:
  enabled: false

  # REQUIRED for production:
  # 1. External Secrets Operator must be installed
  #    helm repo add external-secrets https://charts.external-secrets.io
  #    helm install external-secrets external-secrets/external-secrets
  #
  # 2. SecretStore/ClusterSecretStore must be configured
  #    Example for AWS Secrets Manager:
  #    apiVersion: external-secrets.io/v1beta1
  #    kind: ClusterSecretStore
  #    metadata:
  #      name: aws-secrets
  #    spec:
  #      provider:
  #        aws:
  #          service: SecretsManager
  #          region: us-east-1
  #          auth:
  #            jwt:
  #              serviceAccountRef:
  #                name: external-secrets-sa

  secretStoreRef:
    name: ""
    kind: ClusterSecretStore
```

**Option C: Pre-Install Validation**

```yaml
# templates/validate-external-secrets.yaml
{{- if and (eq .Values.global.environment "prod") (not .Values.externalSecrets.enabled) }}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "floe-platform.fullname" . }}-validate-secrets
  annotations:
    helm.sh/hook: pre-install,pre-upgrade
    helm.sh/hook-weight: "-5"
spec:
  template:
    spec:
      containers:
        - name: validate
          image: bitnami/kubectl:latest
          command:
            - /bin/sh
            - -c
            - |
              # Check if External Secrets Operator is installed
              if ! kubectl get crd externalsecrets.external-secrets.io &>/dev/null; then
                echo "ERROR: External Secrets Operator not installed"
                echo "Install with: helm install external-secrets external-secrets/external-secrets"
                exit 1
              fi

              # Check if SecretStore is configured
              if ! kubectl get secretstore -A &>/dev/null; then
                echo "ERROR: No SecretStore configured"
                echo "See values.yaml for configuration examples"
                exit 1
              fi
{{- end }}
```

### Consistency Pattern

Secret management tiering:
1. **Development**: K8s native secrets (with etcd encryption recommended)
2. **Staging**: External Secrets (optional) or K8s native (with etcd encryption)
3. **Production**: External Secrets (required) + etcd encryption

Document decision tree in installation guide.

---

## Gap #8: Pod Disruption Budgets Disabled by Default

### Current State
```yaml
podDisruptionBudget:
  enabled: false  # Must be explicitly enabled
  minAvailable: 1
```

**Issue**:
- PDB disabled by default (development mode)
- No automatic protection during cluster upgrades
- Single replica deployments have no protection
- No documented when to enable

### Remediation

**Option A: Environment-Based Defaults**

```yaml
podDisruptionBudget:
  enabled: {{ eq .Values.global.environment "prod" }}
  minAvailable: 1

  dagster:
    enabled: {{ .Values.podDisruptionBudget.enabled }}
    minAvailable: 1
```

**Option B: Automatic for HA Deployments**

```yaml
podDisruptionBudget:
  # Automatically enable if replicas > 1
  enabled: false

  dagster:
    enabled: {{ gt .Values.dagster.dagsterWebserver.replicaCount 1 }}
    minAvailable: 1
```

### Consistency Pattern

PDB standard for:
- Multi-replica deployments (HA)
- StatefulSets with persistence
- Production environments

---

## Gap #9: Resource Quotas Disabled by Default

### Current State
```yaml
resourceQuota:
  enabled: false  # Must be explicitly enabled
  hard:
    requests.cpu: "10"
    requests.memory: 20Gi
    limits.cpu: "20"
    limits.memory: 40Gi
    pods: "50"
```

**Issue**:
- No namespace-level resource limits
- Vulnerable to resource exhaustion attacks
- Multi-tenant clusters need quotas
- No documented guidance

### Remediation

**Option A: Environment-Based Defaults**

```yaml
resourceQuota:
  # Enable in multi-tenant or prod environments
  enabled: {{ eq .Values.global.environment "prod" }}
```

**Option B: Dynamic Sizing**

```yaml
resourceQuota:
  enabled: false

  # Size quotas based on environment
  hard:
    requests.cpu: {{ .Values.clusterMapping[.Values.global.environment].resources.quota.cpu | default "10" }}
    requests.memory: {{ .Values.clusterMapping[.Values.global.environment].resources.quota.memory | default "20Gi" }}
```

### Consistency Pattern

Resource quotas for:
- Multi-tenant clusters (always)
- Production environments (recommended)
- Namespace isolation

---

## Gap #10: Service Account Token Automount Always Enabled

### Current State
```yaml
serviceAccount:
  automountServiceAccountToken: true  # Always mount token
```

**Issue**:
- Service account token automatically mounted
- Not all containers need API access
- Broader attack surface if container compromised
- No per-pod override mechanism

### Remediation

**Option A: Disable by Default**

```yaml
serviceAccount:
  # Most containers don't need API access
  automountServiceAccountToken: false
```

Then enable selectively:
```yaml
# Templates that need API access (Dagster, Polaris)
spec:
  automountServiceAccountToken: true
```

**Option B: Per-Container Override**

```yaml
# Pod spec
automountServiceAccountToken: false

# Containers that need API access
containers:
  - name: dagster-daemon
    volumeMounts:
      - name: token
        mountPath: /var/run/secrets/kubernetes.io/serviceaccount

# Alternative: use projected volumes
volumes:
  - name: token
    projected:
      sources:
        - serviceAccountToken:
            path: token
            expirationSeconds: 3600
```

### Consistency Pattern

Service account token automation:
- **Default**: Disabled (least privilege)
- **Dagster**: Enabled (uses K8s API for run launcher)
- **Polaris**: Disabled (no API access needed)
- **PostgreSQL**: Disabled (no API access needed)

Document in deployment specs.

---

## Summary Table: Gaps and Priorities

| Gap | Component | Severity | Remediation Type | Effort |
|-----|-----------|----------|------------------|--------|
| PSS not enforced | Namespace | Critical | Helm hook + labels | Medium |
| NetworkPolicy disabled | Pod | Critical | Values default + validation | Low |
| Secrets unencrypted | Infrastructure | Critical | Require External Secrets | Medium |
| PostgreSQL context hardcoded | PostgreSQL | Medium | Use helper template | Low |
| Init containers docs missing | All | Medium | Add comments | Low |
| Image tags not digests | All | Medium | Use digests in values | Low |
| External Secrets unclear | Dev | Medium | Add requirements docs | Low |
| PDB disabled by default | Pod | Low | Environment defaults | Low |
| Resource Quota disabled | Namespace | Low | Environment defaults | Low |
| Token automount always on | ServiceAccount | Low | Per-container override | Medium |

---

## Remediation Roadmap

**Phase 1 (Critical - Week 1)**
1. Enforce Pod Security Standards via namespace labels
2. Enable Network Policies by default (prod)
3. Require External Secrets (prod) or enforce etcd encryption

**Phase 2 (Medium - Week 2)**
1. Refactor PostgreSQL security context (use helper)
2. Add documentation for init container overrides
3. Support image digests in values

**Phase 3 (Low - Week 3)**
1. Set environment-based defaults (PDB, quotas)
2. Add External Secrets requirements documentation
3. Per-container token automount override

---

## References

- Pod Security Standards: https://kubernetes.io/docs/concepts/security/pod-security-standards/
- Network Policies: https://kubernetes.io/docs/concepts/services-networking/network-policies/
- External Secrets: https://external-secrets.io/
- Secret Encryption: https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/
- RBAC Best Practices: https://kubernetes.io/docs/reference/access-authn-authz/rbac/

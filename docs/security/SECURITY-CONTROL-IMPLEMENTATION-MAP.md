# Security Control Implementation Map

**Quick Reference**: Maps each security control to its implementation locations, helper templates, and configuration paths.

---

## Security Context Injection (Pod + Container)

### Helper Template Definition
**File**: `charts/floe-platform/templates/_helpers.tpl`

```tpl
{{/*
Pod security context (lines 195-197)
*/}}
{{- define "floe-platform.podSecurityContext" -}}
{{- toYaml .Values.podSecurityContext }}
{{- end }}

{{/*
Container security context (lines 202-204)
*/}}
{{- define "floe-platform.containerSecurityContext" -}}
{{- toYaml .Values.containerSecurityContext }}
{{- end }}
```

### Values Definition
**File**: `charts/floe-platform/values.yaml` (lines 535-551)

```yaml
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault

containerSecurityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
  capabilities:
    drop:
      - ALL
```

### Template Usage

| Component | File | Lines | Usage |
|-----------|------|-------|-------|
| Polaris Pod | `deployment-polaris.yaml` | 31-32 | Pod spec |
| Polaris Container | `deployment-polaris.yaml` | 46-47 | Container spec |
| PostgreSQL Pod | `statefulset-postgresql.yaml` | 32-33 | Pod spec (partial override) |
| PostgreSQL Container | `statefulset-postgresql.yaml` | 45-52 | Container spec (hardcoded) |
| PostgreSQL Init Container | `statefulset-postgresql.yaml` | 38-39 | Init container (runAsUser: 0) |
| Polaris Init Container | `deployment-polaris.yaml` | 38-39 | Init container (runAsUser: 0) |

**Implementation Pattern**:
```yaml
# Pod spec
spec:
  securityContext:
    {{- include "floe-platform.podSecurityContext" . | nindent 8 }}

# Container spec
containers:
  - name: component-name
    securityContext:
      {{- include "floe-platform.containerSecurityContext" . | nindent 12 }}
```

---

## NetworkPolicy Configuration

### Values Definition
**File**: `charts/floe-platform/values.yaml` (lines 556-564)

```yaml
networkPolicy:
  # Enable network policies
  enabled: false

  # Ingress rules
  ingress: []

  # Egress rules
  egress: []
```

### Template Implementation
**File**: `templates/networkpolicy.yaml` (lines 1-202)

**Conditional Creation**:
```yaml
{{- if .Values.networkPolicy.enabled }}
  # NetworkPolicies are created
{{- end }}
```

**Policy Definitions** (always present when enabled):

| Policy | Lines | Target | Type |
|--------|-------|--------|------|
| default-deny-ingress | 8-21 | All pods | Deny-all baseline |
| dagster | 23-86 | Dagster pods | Ingress + Egress |
| polaris | 88-145 | Polaris pods | Ingress + Egress |
| postgresql | 147-177 | PostgreSQL pods | Ingress only |
| otel-collector | 179-202 | OTel pods | Ingress only |

**Enable via Helm**:
```bash
helm install floe ./charts/floe-platform \
  --set networkPolicy.enabled=true
```

---

## RBAC Configuration

### Service Account
**File**: `templates/serviceaccount.yaml`

**Values**:
```yaml
serviceAccount:
  create: true              # Create if true
  name: ""                  # Auto-generated if empty
  automountServiceAccountToken: true
  annotations: {}
```

**Template**:
```yaml
{{- if .Values.serviceAccount.create -}}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "floe-platform.serviceAccountName" . }}
  {{- with .Values.serviceAccount.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
automountServiceAccountToken: {{ .Values.serviceAccount.automountServiceAccountToken | default true }}
{{- end }}
```

**Helper Template** (for retrieval):
```tpl
{{- define "floe-platform.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "floe-platform.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
```

### Role Definition
**File**: `templates/role.yaml` (lines 1-37)

**Values**:
```yaml
rbac:
  create: true  # Create Role + RoleBinding
```

**Resource Permissions**:

| API Group | Resources | Verbs |
|-----------|-----------|-------|
| `""` | pods, pods/log, pods/status | get, list, watch, create, delete |
| `""` | configmaps, secrets | get, list, watch |
| `""` | events | get, list, watch, create |
| `batch` | jobs, jobs/status | get, list, watch, create, delete, patch |
| `""` | services | get, list, watch |
| `""` | persistentvolumeclaims | get, list, watch |

### RoleBinding
**File**: `templates/rolebinding.yaml` (lines 1-17)

**Binding Pattern**:
```yaml
{{- if .Values.rbac.create -}}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: {{ include "floe-platform.fullname" . }}

subjects:
  - kind: ServiceAccount
    name: {{ include "floe-platform.serviceAccountName" . }}
    namespace: {{ .Release.Namespace }}
{{- end }}
```

**Enable/Disable**:
```bash
# Enable RBAC
--set rbac.create=true

# Disable RBAC (use default service account)
--set rbac.create=false
```

---

## Secret Management

### K8s Native Secrets

#### PostgreSQL Secret
**File**: `templates/secret-postgresql.yaml`

**Values**:
```yaml
postgresql:
  auth:
    database: floe
    username: floe
    password: ""              # Provide via helm install
    existingSecret: ""        # OR reference existing
    existingSecretKey: password
```

**Creation Logic**:
```
IF postgresql.enabled AND NOT postgresql.auth.existingSecret
THEN create secret with password data
```

**Usage by PostgreSQL**:
```yaml
containers:
  - name: postgresql
    env:
      - name: POSTGRES_PASSWORD
        valueFrom:
          secretKeyRef:
            name: {{ include "floe-platform.fullname" . }}-postgresql
            key: postgresql-password
```

#### Dagster Secret
**File**: `templates/secret-dagster.yaml`

**Values**:
```yaml
dagster:
  postgresqlSecretName: "dagster-postgresql-secret"
  generatePostgresqlPasswordSecret: false
```

**Creation Logic**:
```
IF dagster.enabled AND NOT dagster.generatePostgresqlPasswordSecret
THEN create secret with PostgreSQL connection details
```

**Usage Pattern** (Dagster subchart):
```yaml
env:
  - name: DAGSTER_POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: dagster-postgresql-secret
        key: postgresql-password
```

### External Secrets Integration

**File**: `templates/externalsecret.yaml` (lines 1-123)

**Values**:
```yaml
externalSecrets:
  enabled: false

  secretStoreRef:
    name: ""
    kind: ClusterSecretStore

  refreshInterval: 1h

  # Pre-configured templates
  postgresql:
    enabled: false
    remoteRef:
      key: ""
      property: password

  minio:
    enabled: false
    remoteRef:
      key: ""
      userProperty: username
      passwordProperty: password

  # Custom secrets
  secrets: []
```

**PostgreSQL Secret Example**:
```yaml
externalSecrets:
  enabled: true
  secretStoreRef:
    name: aws-secrets
    kind: ClusterSecretStore

  postgresql:
    enabled: true
    remoteRef:
      key: floe/prod/postgresql
      property: password
```

**Result ExternalSecret**:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: release-postgresql
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets
    kind: ClusterSecretStore
  target:
    name: release-postgresql
  data:
    - secretKey: password
      remoteRef:
        key: floe/prod/postgresql
        property: password
```

---

## Pod Security Standards (PSS)

**Values Definition**:
**File**: `values.yaml` (lines 521-532)

```yaml
podSecurityStandards:
  profile: restricted      # Pod Security Standard profile
  version: latest          # K8s version tracking
  warn: true               # Warn when non-compliant
  audit: true              # Audit non-compliance
```

**NOT Automatically Enforced** (values are informational only)

**Manual Enforcement via Namespace Labels**:
```bash
kubectl label namespace floe-prod \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/audit=restricted
```

**Equivalent to Security Policies**:
- Matches Kubernetes Pod Security Policy "restricted" mode
- Enforces all controls defined in `podSecurityContext` and `containerSecurityContext`

---

## Volume Security

### Config/Secret Mounts
**File**: `deployment-polaris.yaml` (lines 81-101)

```yaml
volumeMounts:
  - name: config
    mountPath: /opt/polaris/conf
    readOnly: true         # Config is read-only

volumes:
  - name: config
    configMap:
      name: {{ ... }}-config
```

### Persistent Data Mounts
**File**: `statefulset-postgresql.yaml` (lines 93-99, 107-125)

```yaml
volumeMounts:
  - name: data
    mountPath: /var/lib/postgresql/data

volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes:
        - ReadWriteOnce
      resources:
        requests:
          storage: 8Gi
```

### Temp/Log Mounts
**File**: `deployment-polaris.yaml` (lines 89-101)

```yaml
volumeMounts:
  - name: tmp
    mountPath: /tmp        # Writable temp directory

volumes:
  - name: tmp
    emptyDir: {}           # Pod-lifetime lifecycle
```

### Init Container Permissions
**File**: `deployment-polaris.yaml` (lines 34-42)

```yaml
initContainers:
  - name: init-data-dir
    image: busybox:1.36
    securityContext:
      runAsUser: 0         # Elevated for chmod/chown
    volumeMounts:
      - name: polaris-data
        mountPath: /data
    command:
      - sh
      - -c
      - 'mkdir -p /data/polaris && chown -R 1000:1000 /data/polaris'
```

---

## Pod Disruption Budgets

**File**: `templates/pdb.yaml`

**Values Definition**:
```yaml
podDisruptionBudget:
  enabled: false
  minAvailable: 1

  dagster:
    enabled: true
    minAvailable: 1

  polaris:
    enabled: true
    minAvailable: 1

  postgresql:
    enabled: true
    minAvailable: 1
```

**Enable via Helm**:
```bash
--set podDisruptionBudget.enabled=true
```

---

## Resource Quotas

**File**: `templates/resourcequota.yaml`

**Values Definition**:
```yaml
resourceQuota:
  enabled: false

  hard:
    requests.cpu: "10"
    requests.memory: 20Gi
    limits.cpu: "20"
    limits.memory: 40Gi
    pods: "50"
```

**Enable via Helm**:
```bash
--set resourceQuota.enabled=true
```

---

## Image Configuration

### Global Settings
**File**: `values.yaml` (lines 23-27)

```yaml
global:
  imagePullPolicy: IfNotPresent
  imagePullSecrets: []  # For private registries
```

### Component-Specific
**Examples**:

```yaml
polaris:
  image:
    repository: apache/polaris
    tag: "0.9.0"
    pullPolicy: IfNotPresent

postgresql:
  image:
    repository: postgres
    tag: "16-alpine"
    pullPolicy: IfNotPresent

dagster:
  dagsterWebserver:
    image:
      repository: "docker.io/dagster/dagster-celery-k8s"
      tag: ""  # Uses chart appVersion
      pullPolicy: IfNotPresent
```

**Template Usage**:
```yaml
image: "{{ .Values.polaris.image.repository }}:{{ .Values.polaris.image.tag | default .Chart.AppVersion }}"
imagePullPolicy: {{ .Values.polaris.image.pullPolicy | default .Values.global.imagePullPolicy }}
```

**Enable Private Registry**:
```bash
--set global.imagePullSecrets[0].name=regcred
```

---

## Health Probes

### Liveness Probe
**File**: `deployment-polaris.yaml` (lines 57-58)

```yaml
livenessProbe:
  {{- toYaml .Values.polaris.livenessProbe | nindent 12 }}
```

**Values**:
```yaml
polaris:
  livenessProbe:
    httpGet:
      path: /healthcheck
      port: metrics
    initialDelaySeconds: 30
    periodSeconds: 10
```

### Readiness Probe
**File**: `deployment-polaris.yaml` (lines 59-60)

```yaml
readinessProbe:
  {{- toYaml .Values.polaris.readinessProbe | nindent 12 }}
```

**Values**:
```yaml
polaris:
  readinessProbe:
    httpGet:
      path: /healthcheck
      port: metrics
    initialDelaySeconds: 10
    periodSeconds: 5
```

---

## Service Account Automount

**Helper Template**:
```tpl
{{- define "floe-platform.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "floe-platform.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
```

**Pod Spec Usage**:
```yaml
spec:
  serviceAccountName: {{ include "floe-platform.serviceAccountName" . }}
```

**Values Control**:
```yaml
serviceAccount:
  automountServiceAccountToken: true  # Mount token automatically
```

---

## Quick Remediation Checklist

When implementing security fixes, verify these files are updated:

| Control | Values | Template | Helper | Config |
|---------|--------|----------|--------|--------|
| Pod Security Context | ✓ | ✓ | ✓ | `podSecurityContext` |
| Container Security Context | ✓ | ✓ | ✓ | `containerSecurityContext` |
| NetworkPolicy | ✓ | ✓ | - | `networkPolicy.enabled` |
| RBAC | ✓ | ✓ | - | `rbac.create` |
| Service Account | ✓ | ✓ | ✓ | `serviceAccount.create` |
| Secrets (K8s) | ✓ | ✓ | - | `postgresql.auth` |
| Secrets (External) | ✓ | ✓ | - | `externalSecrets` |
| Pod Security Standards | ✓ | - | - | `podSecurityStandards` |
| Image Config | ✓ | ✓ | - | `global.imagePull*` |
| PDB | ✓ | ✓ | - | `podDisruptionBudget` |
| Resource Quota | ✓ | ✓ | - | `resourceQuota` |

---

## Configuration Override Examples

### Development (insecure, for testing)
```bash
helm install floe ./charts/floe-platform \
  -f values-dev.yaml \
  --set podSecurityStandards.profile=baseline \
  --set networkPolicy.enabled=false \
  --set externalSecrets.enabled=false
```

### Staging (moderate security)
```bash
helm install floe ./charts/floe-platform \
  -f values-staging.yaml \
  --set networkPolicy.enabled=true \
  --set podSecurityStandards.profile=restricted \
  --set externalSecrets.enabled=false
```

### Production (maximum security)
```bash
helm install floe ./charts/floe-platform \
  -f values-prod.yaml \
  --set networkPolicy.enabled=true \
  --set externalSecrets.enabled=true \
  --set externalSecrets.secretStoreRef.name=aws-secrets \
  --set podSecurityStandards.profile=restricted
```

---

## References

- Helper Templates: `charts/floe-platform/templates/_helpers.tpl`
- Values: `charts/floe-platform/values.yaml`
- Network Policies: `templates/networkpolicy.yaml`
- RBAC: `templates/role.yaml`, `templates/rolebinding.yaml`, `templates/serviceaccount.yaml`
- Secrets: `templates/secret-postgresql.yaml`, `templates/secret-dagster.yaml`, `templates/externalsecret.yaml`

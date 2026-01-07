# ADR-0022: Security & RBAC Model

## Status

Accepted

**RFC 2119 Compliance:** This ADR uses MUST/SHOULD/MAY keywords per [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119.txt). See [glossary](../../contracts/glossary.md#documentation-keywords-rfc-2119).

## Context

floe deploys data pipeline infrastructure across multiple Kubernetes namespaces with several interconnected services (Dagster, Polaris, Cube, MinIO). Without a documented security model, organizations cannot:

1. Understand the trust boundaries between components
2. Apply least-privilege principles consistently
3. Configure authentication for API access
4. Implement network segmentation
5. Meet compliance requirements (SOC2, ISO 27001)

Key security requirements:

- **Isolation**: Job pods MUST NOT access data outside their assigned namespace (namespace isolation enforced via NetworkPolicy and RBAC)
- **Least Privilege**: Services MUST have only the minimum required permissions (least privilege principle)
- **Authentication**: APIs MUST authenticate requests
- **Network Segmentation**: Control traffic flow between layers
- **Auditability**: All access MUST be logged to OpenTelemetry backends for audit trails

## Decision

Implement a layered security model aligned with the four-layer architecture:

1. **Kubernetes RBAC** for internal cluster access
2. **API Authentication** for external service access
3. **Network Policies** for traffic segmentation
4. **Pod Security Standards** for workload hardening

## Consequences

### Positive

- **Defense in depth**: Multiple security layers
- **Clear boundaries**: Each layer has defined trust boundaries
- **Audit trail**: All access logged via K8s audit + OTel
- **Compliance ready**: Meets SOC2/ISO 27001 controls

### Negative

- **Complexity**: More configuration to manage
- **Debugging**: Network policies can complicate troubleshooting
- **Performance**: mTLS adds latency (if enabled)

### Neutral

- Standard Kubernetes security patterns
- Optional service mesh for enhanced security

---

## Namespace Strategy

floe uses dedicated namespaces per architectural layer:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  KUBERNETES CLUSTER                                                          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  floe-platform (Layer 3 - Platform Services)                         │    │
│  │                                                                      │    │
│  │  • Dagster (webserver, daemon)                                      │    │
│  │  • Polaris (catalog API)                                            │    │
│  │  • Cube (semantic layer)                                            │    │
│  │  • MinIO (object storage)                                           │    │
│  │  • OTel Collector, Prometheus, Grafana                              │    │
│  │  • PostgreSQL instances (for Dagster, Polaris)                      │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  floe-jobs (Layer 4 - Ephemeral Job Pods)                            │    │
│  │                                                                      │    │
│  │  • dbt run jobs                                                     │    │
│  │  • dlt ingestion jobs                                               │    │
│  │  • Data quality jobs                                                │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  floe-<domain>-domain (Data Mesh - per domain)                       │    │
│  │                                                                      │    │
│  │  • Domain-specific jobs                                             │    │
│  │  • Domain service accounts                                          │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Namespace Configuration

```yaml
# floe-platform namespace
apiVersion: v1
kind: Namespace
metadata:
  name: floe-platform
  labels:
    app.kubernetes.io/part-of: floe
    floe.dev/layer: "3"
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
    floe.dev/layer: "4"
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

---

## Service Accounts

### Platform Service Accounts

| Service Account | Namespace | Purpose | Permissions |
|-----------------|-----------|---------|-------------|
| `floe-platform-admin` | floe-platform | Platform management | Full namespace admin |
| `floe-dagster` | floe-platform | Dagster webserver/daemon | Create jobs in floe-jobs, read secrets |
| `floe-polaris` | floe-platform | Polaris catalog | Read/write catalog secrets, S3 access |
| `floe-cube` | floe-platform | Cube semantic layer | Read catalog, read secrets |
| `floe-minio` | floe-platform | MinIO storage | PVC access |

### Job Service Accounts

| Service Account | Namespace | Purpose | Permissions |
|-----------------|-----------|---------|-------------|
| `floe-job-runner` | floe-jobs | dbt/dlt jobs | Read secrets, emit telemetry |
| `floe-job-<domain>` | floe-<domain>-domain | Domain jobs | Domain-scoped secrets |

### Service Account Definitions

```yaml
# Dagster service account with job creation permissions
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

```yaml
# Job runner service account (minimal permissions)
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
    verbs: ["get"]
    resourceNames: ["compute-credentials", "catalog-credentials"]
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get"]
    resourceNames: ["floe-job-config"]
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

---

## API Authentication

### Polaris Catalog (OAuth2)

Polaris uses OAuth2 Client Credentials flow for service-to-service authentication:

```
┌─────────────────┐     1. Client Credentials     ┌─────────────────┐
│  Job Pod        │ ─────────────────────────────►│   Polaris       │
│  (dbt/dlt)      │                               │   Catalog       │
└─────────────────┘                               └────────┬────────┘
        │                                                  │
        │ 2. Access Token (JWT)                            │
        │◄─────────────────────────────────────────────────┘
        │
        │ 3. Catalog API calls with Bearer token
        ▼
┌─────────────────┐
│  Iceberg Tables │
└─────────────────┘
```

**Configuration:**

```yaml
# platform-manifest.yaml
plugins:
  catalog:
    type: polaris
    config:
      uri: http://polaris.floe-platform.svc.cluster.local:8181
      auth:
        type: oauth2
        client_id_ref: polaris-client-credentials
        client_secret_ref: polaris-client-credentials
        token_endpoint: http://polaris.floe-platform.svc.cluster.local:8181/api/catalog/v1/oauth/tokens
```

### Cube Semantic Layer (JWT)

Cube uses JWT with security context for row-level security:

```yaml
# Cube configuration
security:
  jwt:
    key_ref: cube-jwt-secret
    algorithms: ["HS256"]
    claims_namespace: "https://floe.dev/"

# Security context in JWT payload
{
  "sub": "service-account:floe-job-runner",
  "https://floe.dev/namespace": "sales.customer-360",
  "https://floe.dev/roles": ["data_reader"],
  "exp": 1704067200
}
```

**Row-Level Security in Cube:**

```javascript
// cube.js security context
cube(`orders`, {
  sql: `SELECT * FROM iceberg.gold.orders`,

  dimensions: {
    namespace: {
      sql: `namespace`,
      type: `string`,
    },
  },

  // Filter by namespace from JWT
  queryRewrite: (query, { securityContext }) => {
    if (securityContext.namespace) {
      query.filters.push({
        member: `orders.namespace`,
        operator: `equals`,
        values: [securityContext.namespace],
      });
    }
    return query;
  },
});
```

### Cross-Service Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  AUTHENTICATION FLOW                                                         │
│                                                                              │
│  1. Dagster schedules job                                                    │
│     │                                                                        │
│     ▼                                                                        │
│  2. Job pod created with ServiceAccount (floe-job-runner)                   │
│     │                                                                        │
│     ├─► 3a. Read secrets from K8s (mounted as env vars)                     │
│     │                                                                        │
│     ├─► 3b. Authenticate to Polaris (OAuth2 → JWT)                          │
│     │       └─► Polaris vends short-lived S3 credentials                    │
│     │                                                                        │
│     ├─► 3c. Execute dbt (uses Polaris-vended credentials)                   │
│     │                                                                        │
│     └─► 3d. Emit telemetry to OTel Collector (see note below)               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Telemetry Emission Security

Telemetry emission to the OTel Collector uses **network-policy-based protection** by default, with an **optional service mesh upgrade path** for organizations requiring authenticated internal traffic.

#### Default Configuration (Network Policy Protection)

```yaml
# Network policy restricts OTel Collector access to floe-jobs namespace only
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: otel-collector-ingress
  namespace: floe-platform
spec:
  podSelector:
    matchLabels:
      app: otel-collector
  policyTypes:
    - Ingress
  ingress:
    # Only allow from floe-jobs namespace
    - from:
        - namespaceSelector:
            matchLabels:
              name: floe-jobs
      ports:
        - protocol: TCP
          port: 4317  # OTLP gRPC
        - protocol: TCP
          port: 4318  # OTLP HTTP
    # Allow from floe-platform (internal services)
    - from:
        - podSelector: {}
      ports:
        - protocol: TCP
          port: 4317
        - protocol: TCP
          port: 4318
```

**Security rationale**: This approach is common in Kubernetes observability deployments where:
1. Network policies enforce namespace-level isolation
2. Telemetry data flows are internal (pod-to-service within cluster)
3. The OTel Collector is not exposed externally
4. Telemetry injection would require already having cluster access

#### Authenticated Telemetry (Service Mesh)

For organizations with strict compliance requirements (e.g., zero-trust networking, FedRAMP), enable authenticated telemetry via service mesh:

```yaml
# Istio configuration for authenticated telemetry
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: otel-collector-mtls
  namespace: floe-platform
spec:
  selector:
    matchLabels:
      app: otel-collector
  mtls:
    mode: STRICT  # Require mTLS for all connections
---
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: otel-collector-authz
  namespace: floe-platform
spec:
  selector:
    matchLabels:
      app: otel-collector
  action: ALLOW
  rules:
    - from:
        - source:
            # Only allow job pods and platform services
            principals:
              - "cluster.local/ns/floe-jobs/sa/floe-job-runner"
              - "cluster.local/ns/floe-platform/sa/*"
      to:
        - operation:
            ports: ["4317", "4318"]
```

**Benefits of authenticated telemetry:**
- mTLS encrypts telemetry in transit
- Service identity verification prevents telemetry injection
- Audit trail of which service accounts emitted telemetry

#### Configuration Selection

| Requirement | Solution | Configuration |
|-------------|----------|---------------|
| Standard deployment | Network policies | Default (no additional config) |
| Zero-trust / FedRAMP | Service mesh + mTLS | `security.service_mesh.mtls: strict` |
| Air-gapped / regulated | Service mesh + mTLS + audit | Full service mesh with access logging |

```yaml
# platform-manifest.yaml
security:
  telemetry:
    # Options: network_policy (default) | service_mesh
    protection: network_policy

  # Enable service mesh for authenticated internal traffic
  service_mesh:
    enabled: false  # Set to true for mTLS on all internal traffic
    type: istio
    mtls: strict
```

**Recommendation**: Most deployments SHOULD use default network policy. Service mesh (Istio/Linkerd) SHOULD be enabled only when compliance requires mTLS or advanced traffic controls.

---

## Network Policies

### Default Deny Policy

```yaml
# Default deny all ingress/egress in floe-jobs
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: floe-jobs
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

### Allow Job → Platform Services

```yaml
# Allow job pods to access platform services
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-jobs-to-platform
  namespace: floe-jobs
spec:
  podSelector:
    matchLabels:
      floe.dev/job-type: data-pipeline
  policyTypes:
    - Egress
  egress:
    # Allow to Polaris catalog
    - to:
        - namespaceSelector:
            matchLabels:
              name: floe-platform
          podSelector:
            matchLabels:
              app: polaris
      ports:
        - protocol: TCP
          port: 8181

    # Allow to OTel Collector
    - to:
        - namespaceSelector:
            matchLabels:
              name: floe-platform
          podSelector:
            matchLabels:
              app: otel-collector
      ports:
        - protocol: TCP
          port: 4317  # OTLP gRPC
        - protocol: TCP
          port: 4318  # OTLP HTTP

    # Allow to MinIO
    - to:
        - namespaceSelector:
            matchLabels:
              name: floe-platform
          podSelector:
            matchLabels:
              app: minio
      ports:
        - protocol: TCP
          port: 9000

    # Allow DNS resolution
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
```

### Allow External Compute (Cloud DWH)

```yaml
# Allow jobs to connect to external data warehouses (Snowflake, BigQuery)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-external-compute
  namespace: floe-jobs
spec:
  podSelector:
    matchLabels:
      floe.dev/job-type: data-pipeline
  policyTypes:
    - Egress
  egress:
    # Snowflake (HTTPS)
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - protocol: TCP
          port: 443
```

### Platform Services Internal Communication

```yaml
# Allow platform services to communicate internally
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-platform-internal
  namespace: floe-platform
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from same namespace
    - from:
        - podSelector: {}
  egress:
    # Allow to same namespace
    - to:
        - podSelector: {}
    # Allow DNS
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
```

### Network Policy Summary

| Source | Destination | Ports | Status |
|--------|-------------|-------|--------|
| floe-jobs → floe-platform/polaris | 8181 | ALLOW |
| floe-jobs → floe-platform/otel-collector | 4317, 4318 | ALLOW |
| floe-jobs → floe-platform/minio | 9000 | ALLOW |
| floe-jobs → external (HTTPS) | 443 | ALLOW (compute targets) |
| floe-jobs → * | * | DENY (default) |
| floe-platform → floe-platform | * | ALLOW (internal) |
| external → floe-platform | ingress | ALLOW (via Ingress) |

---

## Pod Security Standards

### Job Pods (Restricted)

Job pods run with the `restricted` Pod Security Standard:

```yaml
# Job pod security context
apiVersion: batch/v1
kind: Job
metadata:
  name: dbt-run-customer-360
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
```

### Platform Services (Baseline)

Platform services run with the `baseline` Pod Security Standard (some require capabilities):

```yaml
# Platform pod security (example: Dagster)
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
          add: ["NET_BIND_SERVICE"]  # If binding to port < 1024
```

---

## Service Mesh (Optional)

For enhanced security, organizations can deploy a service mesh:

### Istio Configuration

```yaml
# Enable mTLS for all floe namespaces
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: floe-mtls
  namespace: floe-platform
spec:
  mtls:
    mode: STRICT
---
# Authorization policy
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: polaris-authz
  namespace: floe-platform
spec:
  selector:
    matchLabels:
      app: polaris
  action: ALLOW
  rules:
    - from:
        - source:
            principals:
              - "cluster.local/ns/floe-jobs/sa/floe-job-runner"
              - "cluster.local/ns/floe-platform/sa/floe-dagster"
      to:
        - operation:
            methods: ["GET", "POST", "PUT", "DELETE"]
            paths: ["/api/*"]
```

### Benefits of Service Mesh

| Feature | Without Mesh | With Mesh |
|---------|--------------|-----------|
| mTLS | Manual certificates | Automatic |
| Traffic observability | OTel instrumentation | Automatic |
| Retries/circuit breaking | Application code | Configuration |
| Zero-trust networking | Network policies | + identity-based |

---

## Audit Logging

### Kubernetes Audit Policy

```yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  # Log all secret access
  - level: Metadata
    resources:
      - group: ""
        resources: ["secrets"]
    namespaces: ["floe-platform", "floe-jobs"]

  # Log all job creation
  - level: RequestResponse
    resources:
      - group: "batch"
        resources: ["jobs"]
    namespaces: ["floe-jobs"]

  # Log RBAC changes
  - level: RequestResponse
    resources:
      - group: "rbac.authorization.k8s.io"
        resources: ["roles", "rolebindings", "clusterroles", "clusterrolebindings"]
```

### Application Audit Events

```python
# Emit audit events via OpenTelemetry
from opentelemetry import trace

tracer = trace.get_tracer("floe.audit")

def audit_catalog_access(user: str, table: str, operation: str):
    with tracer.start_as_current_span("audit.catalog_access") as span:
        span.set_attribute("audit.user", user)
        span.set_attribute("audit.table", table)
        span.set_attribute("audit.operation", operation)
        span.set_attribute("audit.timestamp", datetime.now(timezone.utc).isoformat())
```

---

## Configuration Schema

```yaml
# platform-manifest.yaml security section
security:
  # Pod Security Standards enforcement
  pod_security:
    platform_level: baseline    # For floe-platform namespace
    jobs_level: restricted      # For floe-jobs namespace

  # Network policy mode
  network_policies:
    enabled: true
    default_deny: true          # Default deny in job namespace
    allow_external_https: true  # Allow jobs to reach cloud DWH

  # Service mesh (optional)
  service_mesh:
    enabled: false
    type: istio | linkerd
    mtls: strict | permissive

  # API authentication
  api_auth:
    polaris:
      type: oauth2
      client_id_ref: polaris-credentials
      client_secret_ref: polaris-credentials
    cube:
      type: jwt
      secret_ref: cube-jwt-secret
      algorithms: ["HS256"]

  # Audit configuration
  audit:
    enabled: true
    secret_access: true
    job_lifecycle: true
```

---

## Security Checklist

### Pre-Deployment

- [ ] Namespaces created with correct Pod Security labels
- [ ] Service accounts created with least-privilege roles
- [ ] Network policies deployed and tested
- [ ] Secrets created (not committed to git)
- [ ] TLS certificates configured for ingress

### Post-Deployment

- [ ] Verify pods running as non-root
- [ ] Test network policy enforcement
- [ ] Confirm audit logging working
- [ ] Run security scan (Trivy, Kubescape)

### Ongoing

- [ ] Regular secret rotation
- [ ] Dependency vulnerability scanning
- [ ] RBAC permission review
- [ ] Audit log review

---

## References

- [Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Polaris Security](https://github.com/apache/polaris) - OAuth2 authentication
- [Cube Security](https://cube.dev/docs/product/auth) - JWT authentication
- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md) - Four-layer architecture
- [ADR-0019: Platform Services Lifecycle](0019-platform-services-lifecycle.md) - Service deployment
- [ADR-0023: Secrets Management](0023-secrets-management.md) - Credential management

# REQ-416 to REQ-425: Network Policies and Traffic Segmentation

**Domain**: Security and Access Control
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines Kubernetes NetworkPolicies that enforce zero-trust networking with default deny and explicit allow rules. Network policies segment traffic between namespaces and external services, preventing lateral movement and unauthorized communication.

**Key Principle**: Default Deny + Explicit Allow (ADR-0022)

## Requirements

### REQ-416: Default Deny NetworkPolicy for floe-jobs **[New]**

**Requirement**: System MUST create a default-deny NetworkPolicy in floe-jobs namespace that blocks all ingress and egress traffic by default.

**Rationale**: Implements zero-trust networking principle - all communication is explicit allow only.

**Acceptance Criteria**:
- [ ] NetworkPolicy created: `default-deny-all` in `floe-jobs` namespace
- [ ] Policy denies all ingress (podSelector: {})
- [ ] Policy denies all egress (podSelector: {})
- [ ] Tests verify traffic blocked before explicit allows
- [ ] All job pods blocked until specific allow rules added

**Enforcement**:
- Network policy deployment tests
- Traffic blocking validation tests
- Explicit allow rule prerequisite tests

**Constraints**:
- MUST use empty podSelector to match all pods
- MUST set both Ingress and Egress policyTypes
- FORBIDDEN to use any allow rules at pod level (only allow via explicit rules)

**Configuration**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: floe-jobs
spec:
  podSelector: {}  # Applies to all pods in namespace
  policyTypes:
    - Ingress
    - Egress
  # No ingress/egress rules = deny all
```

**Test Coverage**: `tests/contract/test_network_policies.py::test_default_deny_all_policy`

**Traceability**:
- ADR-0022 lines 451-465

---

### REQ-417: Allow Jobs to Polaris Catalog **[New]**

**Requirement**: System MUST create NetworkPolicy allowing egress from floe-jobs pods to Polaris catalog API in floe-platform namespace on port 8181.

**Rationale**: Enables job pods to access catalog metadata for table discovery.

**Acceptance Criteria**:
- [ ] NetworkPolicy created: `allow-jobs-to-polaris` in `floe-jobs` namespace
- [ ] Allows egress to floe-platform namespace
- [ ] Allows egress to pod selector: app=polaris
- [ ] Allows port 8181 (Polaris REST API)
- [ ] Tests verify Polaris connectivity from job pods
- [ ] Tests verify non-Polaris traffic still blocked

**Enforcement**:
- Network policy egress tests
- Polaris API access validation tests
- Traffic restriction tests

**Constraints**:
- MUST use namespaceSelector and podSelector for precise targeting
- MUST specify port 8181 explicitly
- FORBIDDEN to allow port 8181 to all namespaces

**Configuration**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-jobs-to-polaris
  namespace: floe-jobs
spec:
  podSelector:
    matchLabels:
      floe.dev/job-type: data-pipeline
  policyTypes:
    - Egress
  egress:
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
```

**Test Coverage**: `tests/contract/test_network_policies.py::test_allow_jobs_to_polaris`

**Traceability**:
- ADR-0022 lines 468-493

---

### REQ-418: Allow Jobs to OTel Collector **[New]**

**Requirement**: System MUST create NetworkPolicy allowing egress from floe-jobs pods to OTel Collector in floe-platform namespace on ports 4317 (gRPC) and 4318 (HTTP).

**Rationale**: Enables job pods to emit telemetry and observability data.

**Acceptance Criteria**:
- [ ] NetworkPolicy created: `allow-jobs-to-otel` in `floe-jobs` namespace
- [ ] Allows egress to floe-platform/otel-collector
- [ ] Allows ports 4317 and 4318
- [ ] Tests verify telemetry emission works
- [ ] Tests verify other ports still blocked

**Enforcement**:
- Network policy egress tests
- Telemetry emission validation tests

**Constraints**:
- MUST allow both gRPC (4317) and HTTP (4318) ports
- MUST use namespaceSelector and podSelector
- FORBIDDEN to allow to other namespaces

**Configuration**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-jobs-to-otel
  namespace: floe-jobs
spec:
  podSelector:
    matchLabels:
      floe.dev/job-type: data-pipeline
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: floe-platform
          podSelector:
            matchLabels:
              app: otel-collector
      ports:
        - protocol: TCP
          port: 4317
        - protocol: TCP
          port: 4318
```

**Test Coverage**: `tests/contract/test_network_policies.py::test_allow_jobs_to_otel_collector`

**Traceability**:
- ADR-0022 lines 495-507

---

### REQ-419: Allow Jobs to MinIO Storage **[New]**

**Requirement**: System MUST create NetworkPolicy allowing egress from floe-jobs pods to MinIO in floe-platform namespace on port 9000 (S3 API).

**Rationale**: Enables job pods to read/write data to object storage.

**Acceptance Criteria**:
- [ ] NetworkPolicy created: `allow-jobs-to-minio` in `floe-jobs` namespace
- [ ] Allows egress to floe-platform/minio
- [ ] Allows port 9000 (S3 API)
- [ ] Tests verify S3 operations work (put, get, delete)
- [ ] Tests verify other ports blocked

**Enforcement**:
- Network policy egress tests
- S3 API access validation tests

**Constraints**:
- MUST use port 9000 (S3 API), not 9001 (console)
- MUST use namespaceSelector and podSelector
- FORBIDDEN to allow external S3 from this rule (only internal MinIO)

**Configuration**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-jobs-to-minio
  namespace: floe-jobs
spec:
  podSelector:
    matchLabels:
      floe.dev/job-type: data-pipeline
  policyTypes:
    - Egress
  egress:
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
```

**Test Coverage**: `tests/contract/test_network_policies.py::test_allow_jobs_to_minio`

**Traceability**:
- ADR-0022 lines 509-519

---

### REQ-420: Allow Jobs to External Cloud DWH **[New]**

**Requirement**: System MUST create NetworkPolicy allowing egress from floe-jobs pods to external hosts on port 443 (HTTPS) for cloud data warehouse connectivity (Snowflake, BigQuery, Databricks, etc.).

**Rationale**: Enables job pods to execute queries against cloud data warehouses.

**Acceptance Criteria**:
- [ ] NetworkPolicy created: `allow-jobs-to-external-compute` in `floe-jobs` namespace
- [ ] Allows egress to 0.0.0.0/0 on port 443
- [ ] Tests verify cloud DWH connectivity
- [ ] Tests verify DNS resolution works
- [ ] Other ports to external IPs blocked

**Enforcement**:
- Network policy egress tests
- Cloud DWH connectivity validation tests

**Constraints**:
- MUST use ipBlock 0.0.0.0/0 (allow all external)
- MUST allow port 443 only (HTTPS)
- MUST NOT allow port 80 (unencrypted HTTP forbidden)

**Configuration**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-jobs-to-external-compute
  namespace: floe-jobs
spec:
  podSelector:
    matchLabels:
      floe.dev/job-type: data-pipeline
  policyTypes:
    - Egress
  egress:
    # Allow HTTPS to external compute targets (Snowflake, BigQuery, etc.)
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - protocol: TCP
          port: 443
```

**Test Coverage**: `tests/contract/test_network_policies.py::test_allow_jobs_to_external_compute`

**Traceability**:
- ADR-0022 lines 534-557

---

### REQ-421: Allow DNS Resolution for Jobs **[New]**

**Requirement**: System MUST create NetworkPolicy allowing egress from floe-jobs pods to kube-dns in kube-system namespace on port 53 (UDP) for DNS resolution.

**Rationale**: Enables domain name resolution for all services and external hosts.

**Acceptance Criteria**:
- [ ] NetworkPolicy created: `allow-jobs-to-dns` in `floe-jobs` namespace
- [ ] Allows egress to kube-system/kube-dns
- [ ] Allows port 53 UDP
- [ ] Tests verify DNS resolution works
- [ ] Tests verify hostname-based connections succeed

**Enforcement**:
- Network policy egress tests
- DNS resolution validation tests

**Constraints**:
- MUST use UDP protocol
- MUST allow only port 53
- MUST scope to kube-dns pod

**Configuration**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-jobs-to-dns
  namespace: floe-jobs
spec:
  podSelector:
    matchLabels:
      floe.dev/job-type: data-pipeline
  policyTypes:
    - Egress
  egress:
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

**Test Coverage**: `tests/contract/test_network_policies.py::test_allow_jobs_to_dns`

**Traceability**:
- ADR-0022 lines 521-531

---

### REQ-422: Allow Platform Services Internal Communication **[New]**

**Requirement**: System MUST create NetworkPolicy in floe-platform namespace allowing all pod-to-pod communication within the namespace for internal service communication.

**Rationale**: Enables platform services (Dagster, Polaris, Cube) to communicate with databases, message queues, and each other.

**Acceptance Criteria**:
- [ ] NetworkPolicy created: `allow-platform-internal` in `floe-platform` namespace
- [ ] Allows all ingress from same namespace (podSelector: {})
- [ ] Allows all egress to same namespace
- [ ] Allows DNS to kube-system
- [ ] Tests verify inter-service communication

**Enforcement**:
- Network policy ingress/egress tests
- Service-to-service communication validation tests

**Constraints**:
- MUST use empty podSelector for namespace-wide rules
- MUST allow DNS egress
- FORBIDDEN to allow all external traffic

**Configuration**:
```yaml
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
    # Allow from any pod in floe-platform
    - from:
        - podSelector: {}
  egress:
    # Allow to any pod in floe-platform
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

**Test Coverage**: `tests/contract/test_network_policies.py::test_allow_platform_internal_communication`

**Traceability**:
- ADR-0022 lines 559-589

---

### REQ-423: Restrict Ingress to Public Services **[New]**

**Requirement**: System MUST create NetworkPolicies restricting ingress to floe-platform public services (Dagster webserver, Polaris API) to explicitly allowed sources only.

**Rationale**: Prevents unauthorized access to management APIs.

**Acceptance Criteria**:
- [ ] NetworkPolicy created: `allow-ingress-dagster-webserver`
- [ ] NetworkPolicy created: `allow-ingress-polaris-api`
- [ ] Only allows ingress from Ingress controller (istio, ingress-nginx)
- [ ] Tests verify external access via ingress works
- [ ] Tests verify direct pod access blocked

**Enforcement**:
- Network policy ingress tests
- External access validation tests

**Constraints**:
- MUST restrict ingress to ingress controller namespace/pods
- MUST NOT allow direct pod-to-pod access to public services
- FORBIDDEN to allow all ingress

**Configuration**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress-dagster-webserver
  namespace: floe-platform
spec:
  podSelector:
    matchLabels:
      app: dagster-webserver
  policyTypes:
    - Ingress
  ingress:
    # Only from ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
          podSelector:
            matchLabels:
              app: ingress-nginx
```

**Test Coverage**: `tests/contract/test_network_policies.py::test_restrict_ingress_to_public_services`

**Traceability**:
- ADR-0022 lines 468-532

---

### REQ-424: Network Policy Testing and Validation **[New]**

**Requirement**: System MUST validate NetworkPolicy configuration through tests that verify traffic is allowed/blocked according to policy rules.

**Rationale**: Catches network policy misconfiguration before production.

**Acceptance Criteria**:
- [ ] Tests verify default deny blocks all traffic
- [ ] Tests verify explicit allow rules unblock traffic
- [ ] Tests verify non-matching traffic still blocked
- [ ] Tests verify namespace isolation enforced
- [ ] Tests verify cross-namespace communication blocked
- [ ] NetworkPolicy YAML validation passes in CI/CD

**Enforcement**:
- Network policy validation tests
- Traffic flow tests
- Cross-namespace isolation tests

**Test Coverage**: `tests/contract/test_network_policies.py::test_network_policy_compliance_suite`

**Traceability**:
- CLAUDE.md (.claude/rules/testing-standards.md)

---

### REQ-425: Network Policy Documentation and Governance **[New]**

**Requirement**: System MUST maintain documentation of all NetworkPolicies, their rules, and rationale in charts/floe-platform/network-policies-governance.md.

**Rationale**: Enables security audits and prevents scope creep in network access.

**Acceptance Criteria**:
- [ ] Network policy governance document created
- [ ] All policies documented with source/destination/port
- [ ] Rationale provided for each rule
- [ ] Change review process documented
- [ ] Document updated with every policy change

**Enforcement**:
- Documentation governance tests
- CI/CD checks that policy changes include doc updates

**Test Coverage**: `tests/contract/test_network_policies.py::test_network_policy_documentation_current`

**Traceability**:
- CLAUDE.md

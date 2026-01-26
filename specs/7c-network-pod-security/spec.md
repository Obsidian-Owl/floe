# Feature Specification: Network and Pod Security

**Epic**: 7C (Network/Pod Security)
**Feature Branch**: `7c-network-pod-security`
**Created**: 2026-01-26
**Status**: Draft
**Input**: User description: "Network and Pod Security for Kubernetes - NetworkPolicies, Pod Security Standards, and secure runtime configurations for the floe platform"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Default Deny Network Isolation for Job Pods (Priority: P0)

As a platform operator, I want default-deny network policies applied to the `floe-jobs` namespace so that job pods can only communicate with explicitly allowed services, preventing lateral movement attacks.

**Why this priority**: Network segmentation is the first line of defense against data exfiltration and lateral movement. Without default-deny policies, any compromised pod could communicate with any other pod across the cluster. This is a critical security control required for SOC2 and ISO 27001 compliance.

**Independent Test**: Can be fully tested by deploying a job pod, verifying it can reach allowed services (Polaris, OTel Collector, MinIO) and cannot reach unauthorized endpoints.

**Acceptance Scenarios**:

1. **Given** a `floe-jobs` namespace with network policies applied, **When** a job pod attempts to connect to an arbitrary pod in another namespace, **Then** the connection is blocked (timeout/refused).

2. **Given** default-deny egress policy, **When** a job pod attempts DNS resolution via `kube-dns`, **Then** the resolution succeeds (DNS explicitly allowed).

3. **Given** egress allowlist including Polaris, **When** a job pod connects to Polaris on port 8181, **Then** the connection succeeds.

4. **Given** egress allowlist including external HTTPS, **When** a job pod connects to a cloud data warehouse on port 443, **Then** the connection succeeds.

---

### User Story 2 - Platform Services Network Segmentation (Priority: P0)

As a platform operator, I want network policies for the `floe-platform` namespace so that platform services (Dagster, Polaris, Cube) can communicate with each other and receive external traffic through the ingress, but are isolated from unauthorized access.

**Why this priority**: Platform services contain control plane functionality and sensitive metadata. Segmenting these from job pods limits blast radius if a job is compromised. Platform services need inter-service communication but should not be directly accessible from job pods except via defined APIs.

**Independent Test**: Can be fully tested by deploying platform services, verifying ingress traffic works, inter-service communication works, and direct pod-to-pod from `floe-jobs` is blocked.

**Acceptance Scenarios**:

1. **Given** `floe-platform` namespace with network policies, **When** Dagster needs to query Polaris catalog API, **Then** the connection succeeds (intra-namespace allowed).

2. **Given** ingress controller in `ingress-nginx` namespace, **When** external traffic arrives at the Dagster webserver, **Then** the traffic is permitted through the ingress NetworkPolicy rule.

3. **Given** a job pod in `floe-jobs`, **When** it attempts direct connection to Dagster webserver pod in `floe-platform`, **Then** the connection is blocked (only ingress-routed traffic allowed).

4. **Given** Cube semantic layer needs to query compute target, **When** Cube connects to external Snowflake on port 443, **Then** the egress policy allows the connection.

---

### User Story 3 - Pod Security Standards Enforcement (Priority: P0)

As a security officer, I want Pod Security Standards (PSS) enforced at the namespace level so that all pods meet security baselines and cannot escalate privileges.

**Why this priority**: PSS prevents container escape attacks, privilege escalation, and host access. These are the most common attack vectors in Kubernetes. K8s 1.25+ includes Pod Security Admission controller by default, making this enforceable without additional tooling.

**Independent Test**: Can be fully tested by attempting to deploy a non-compliant pod (e.g., privileged container) and verifying admission controller rejection.

**Acceptance Scenarios**:

1. **Given** `floe-jobs` namespace with `pod-security.kubernetes.io/enforce: restricted`, **When** a pod spec requests privileged mode, **Then** the pod admission controller rejects it with a clear error.

2. **Given** `floe-platform` namespace with `pod-security.kubernetes.io/enforce: baseline`, **When** a stateful service needs hostPath volume, **Then** the pod admission controller rejects it (baseline prohibits hostPath).

3. **Given** restricted PSS enforcement, **When** a pod spec includes `runAsUser: 0` (root), **Then** the pod is rejected.

4. **Given** audit and warn modes set to `restricted` on `floe-platform`, **When** a baseline-compliant pod is deployed, **Then** audit logs show warnings about restricted violations (for future hardening).

---

### User Story 4 - Secure Container Runtime Configuration (Priority: P1)

As a platform operator, I want all job pods to run with hardened security contexts so that containers have minimal capabilities and cannot modify the host system.

**Why this priority**: Even if PSS enforcement is in place, generated pod specs must be correct by default. This ensures the compilation pipeline produces secure configurations without relying solely on admission control.

**Independent Test**: Can be fully tested by inspecting generated job pod specs and verifying all required security context fields are present.

**Acceptance Scenarios**:

1. **Given** `floe compile` with security enabled, **When** examining generated job pod specs, **Then** pod-level `securityContext` includes `runAsNonRoot: true`, `runAsUser: 1000`, `runAsGroup: 1000`, `fsGroup: 1000`.

2. **Given** generated container specs, **When** examining `securityContext`, **Then** it includes `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]`, `readOnlyRootFilesystem: true`.

3. **Given** read-only root filesystem requirement, **When** a job needs temporary file storage, **Then** the pod spec includes `emptyDir` volumes mounted at `/tmp` and `/home/floe`.

4. **Given** seccomp profile requirement, **When** examining generated pod specs, **Then** `seccompProfile.type: RuntimeDefault` is present.

---

### User Story 5 - NetworkPolicy Manifest Generation (Priority: P1)

As a data engineer, I want NetworkPolicy manifests generated from floe configuration so that I don't need to manually write complex YAML for network rules.

**Why this priority**: Manual NetworkPolicy authoring is error-prone and requires deep K8s networking knowledge. Generated policies ensure consistency and reduce misconfiguration risk.

**Independent Test**: Can be fully tested by running `floe compile`, examining generated NetworkPolicy YAMLs, and applying them with `kubectl apply --dry-run=server`.

**Acceptance Scenarios**:

1. **Given** `security.network_policies.enabled: true` in manifest.yaml, **When** `floe compile` runs, **Then** `target/network/` directory contains NetworkPolicy YAML files.

2. **Given** a data product with `compute.target: snowflake`, **When** compiling, **Then** egress policy includes allow rule for port 443 to Snowflake endpoints.

3. **Given** generated NetworkPolicies, **When** applying with `kubectl apply --dry-run=server`, **Then** all resources pass validation.

4. **Given** multiple namespaces configured, **When** compiling, **Then** separate NetworkPolicy files are generated for each namespace (`floe-platform-netpol.yaml`, `floe-jobs-netpol.yaml`).

---

### User Story 6 - DNS Egress Allow by Default (Priority: P1)

As a platform operator, I want DNS egress allowed by default in all NetworkPolicies so that pods can resolve service names without additional configuration.

**Why this priority**: DNS resolution is required for virtually all network communication in Kubernetes. Blocking DNS breaks all service discovery. This is a common pitfall when implementing default-deny policies.

**Independent Test**: Can be fully tested by deploying a pod with default-deny egress, verifying DNS resolution works, and verifying other arbitrary egress is blocked.

**Acceptance Scenarios**:

1. **Given** default-deny egress NetworkPolicy, **When** examining policy rules, **Then** UDP port 53 to `kube-system` namespace (`kube-dns` or `coredns`) is allowed.

2. **Given** DNS egress allowlist, **When** a job pod resolves `polaris.floe-platform.svc.cluster.local`, **Then** resolution succeeds.

3. **Given** DNS egress allowlist, **When** a job pod attempts TCP connection to arbitrary IP on port 53, **Then** the connection is blocked (only cluster DNS allowed).

---

### User Story 7 - Telemetry Egress for Observability (Priority: P1)

As a platform operator, I want job pods to send telemetry to the OpenTelemetry Collector so that observability data flows without manual network configuration.

**Why this priority**: Telemetry is critical for operations and debugging. Jobs must emit traces, metrics, and logs to the collector. This is a core operational requirement.

**Independent Test**: Can be fully tested by deploying a job with tracing enabled, verifying spans are received by OTel Collector.

**Acceptance Scenarios**:

1. **Given** egress allowlist for telemetry, **When** a job pod sends traces to OTel Collector on port 4317 (gRPC), **Then** the connection succeeds.

2. **Given** egress allowlist for telemetry, **When** a job pod sends metrics to OTel Collector on port 4318 (HTTP), **Then** the connection succeeds.

3. **Given** OTel Collector in `floe-platform` namespace, **When** examining generated NetworkPolicies, **Then** egress rules allow traffic to namespace `floe-platform` on ports 4317 and 4318.

---

### User Story 8 - Network Policy Validation and Audit (Priority: P2)

As a security officer, I want to validate and audit NetworkPolicies so that I can verify network segmentation is correctly implemented.

**Why this priority**: Audit capability is required for compliance reporting but not for basic functionality. Important for ongoing security posture management.

**Independent Test**: Can be fully tested by running `floe network audit` and reviewing the generated report.

**Acceptance Scenarios**:

1. **Given** a deployed floe installation, **When** running `floe network audit`, **Then** a report is generated showing all NetworkPolicies and their effective rules.

2. **Given** a namespace without default-deny policy, **When** running audit, **Then** a warning is flagged for missing default-deny.

3. **Given** generated NetworkPolicy manifests, **When** running `floe network validate`, **Then** the tool verifies manifests match the current manifest.yaml configuration.

4. **Given** NetworkPolicy drift (manual changes in cluster), **When** running `floe network diff`, **Then** differences between expected and deployed policies are displayed.

---

### User Story 9 - Domain Namespace Network Isolation (Priority: P2)

As a platform operator managing Data Mesh deployments, I want each domain namespace to have isolated network policies so that domains cannot access each other's resources.

**Why this priority**: Data Mesh deployments require strong boundaries between domain teams. This prevents cross-domain data access and limits blast radius of domain-specific incidents.

**Independent Test**: Can be fully tested by creating two domain namespaces, deploying pods in each, and verifying cross-domain network access is blocked.

**Acceptance Scenarios**:

1. **Given** `floe-sales-domain` and `floe-marketing-domain` namespaces, **When** a pod in `floe-sales-domain` attempts to connect to a pod in `floe-marketing-domain`, **Then** the connection is blocked.

2. **Given** domain namespace configuration, **When** deploying a new domain, **Then** default-deny ingress and egress NetworkPolicies are created.

3. **Given** domain isolation, **When** a domain job needs to access shared Polaris catalog, **Then** explicit egress to `floe-platform` namespace on port 8181 is allowed.

4. **Given** domain namespace NetworkPolicies, **When** examining ingress rules, **Then** only pods from the same domain namespace and ingress controller are allowed.

---

### Edge Cases

- What happens when NetworkPolicy CNI plugin is not installed?
  - `floe deploy` detects missing CNI support and warns with actionable remediation
  - Policies are still created but flagged as "unenforced" in status
  - Documentation recommends Calico or Cilium for production deployments

- How does the system handle cloud-managed Kubernetes (EKS, GKE, AKS) NetworkPolicy support?
  - EKS requires Calico add-on (documented in deployment guide)
  - GKE has native support with Dataplane V2
  - AKS requires Azure CNI with network policy feature enabled
  - `floe network check-cni` command validates CNI support

- What happens when egress needs to reach external services with dynamic IPs?
  - Support CIDR-based egress rules for known IP ranges
  - Support DNS-based egress (Cilium-specific feature, documented as optional)
  - Default: allow all egress to internet on port 443 with opt-in restriction

- How are headless services handled in NetworkPolicy selectors?
  - Headless services require pod selectors (not service selectors)
  - Generated policies use consistent labels for service discovery
  - Documentation notes headless service limitations

- What happens when a pod needs to bind to privileged ports (< 1024)?
  - Restricted PSS prohibits this; pods must use high ports (> 1024)
  - Services can map external port 443 to internal port 8443
  - Container images must be designed for non-root operation

- How does read-only root filesystem work with applications that need writable directories?
  - `emptyDir` volumes mounted at common writable paths (`/tmp`, `/home/floe`, `/var/cache`)
  - Configurable additional writable mount points via manifest.yaml
  - Base container images configured with correct directory permissions

## Requirements *(mandatory)*

### Functional Requirements

#### Core NetworkPolicy Framework

- **FR-001**: System MUST provide `NetworkPolicyGenerator` class that produces valid Kubernetes NetworkPolicy YAML from floe configuration.

- **FR-002**: System MUST generate default-deny ingress and egress NetworkPolicies for all managed namespaces when `security.network_policies.enabled: true`.

- **FR-003**: Generated NetworkPolicies MUST be valid YAML parseable by `kubectl apply --dry-run=server`.

- **FR-004**: System MUST support namespace-scoped NetworkPolicies (not ClusterNetworkPolicy unless Cilium/Calico enterprise features are enabled).

#### Default-Deny and Allowlist Policies

- **FR-010**: System MUST generate default-deny egress policy with empty `podSelector` to apply to all pods in namespace.

- **FR-011**: System MUST generate default-deny ingress policy with empty `podSelector` to apply to all pods in namespace.

- **FR-012**: System MUST include DNS egress allowlist (UDP port 53 to `kube-system` namespace) in all default-deny policies.

- **FR-013**: System MUST support configurable egress allowlist for external HTTPS endpoints (port 443).

- **FR-014**: System MUST allow ingress from `ingress-nginx` (or configured ingress namespace) for services exposed externally.

#### Platform Namespace Network Rules

- **FR-020**: `floe-platform` namespace MUST have NetworkPolicy allowing intra-namespace pod-to-pod communication.

- **FR-021**: `floe-platform` namespace MUST have egress rules allowing communication to:
  - Kubernetes API server (port 443)
  - DNS (UDP port 53)
  - External HTTPS for cloud integrations (port 443)

- **FR-022**: Platform services MUST have ingress rules allowing traffic from ingress controller namespace.

- **FR-023**: Dagster MUST have egress rules allowing job creation in `floe-jobs` namespace via Kubernetes API.

#### Jobs Namespace Network Rules

- **FR-030**: `floe-jobs` namespace MUST have default-deny ingress policy (jobs don't receive inbound connections).

- **FR-031**: `floe-jobs` namespace MUST have egress allowlist including:
  - DNS (UDP port 53 to kube-system)
  - Polaris catalog (port 8181 to floe-platform)
  - OTel Collector (ports 4317, 4318 to floe-platform)
  - MinIO/S3 (port 9000 to floe-platform, or cloud endpoint on 443)
  - External HTTPS (port 443 for cloud data warehouses)

- **FR-032**: `floe-jobs` namespace egress MUST NOT allow direct pod-to-pod communication within the namespace (isolation between jobs).

- **FR-033**: System MUST support additional egress rules via `security.network_policies.jobs_egress_allow` configuration list.

#### Domain Namespace Network Rules

- **FR-040**: Domain namespaces (`floe-{domain}-domain`) MUST have default-deny ingress and egress policies.

- **FR-041**: Domain namespaces MUST have egress to shared platform services (Polaris, OTel Collector) but NOT to other domain namespaces.

- **FR-042**: Domain namespaces MUST NOT allow ingress from other domain namespaces.

- **FR-043**: Domain namespace NetworkPolicies MUST include labels: `floe.dev/domain: {domain-name}`, `floe.dev/layer: data`.

#### Pod Security Standards Enforcement

- **FR-050**: System MUST generate `Namespace` resources with Pod Security Standard labels when `security.pod_security.enabled: true`.

- **FR-051**: `floe-jobs` namespace MUST have `pod-security.kubernetes.io/enforce: restricted` label by default.

- **FR-052**: `floe-platform` namespace MUST have `pod-security.kubernetes.io/enforce: baseline` label by default.

- **FR-053**: All managed namespaces MUST have `pod-security.kubernetes.io/audit: restricted` and `pod-security.kubernetes.io/warn: restricted` labels for visibility into potential hardening.

- **FR-054**: System MUST support configurable PSS levels via `security.pod_security.{namespace}_level` configuration.

#### Secure Container Runtime Configuration

- **FR-060**: Generated job pod specs MUST include pod-level `securityContext` with:
  - `runAsNonRoot: true`
  - `runAsUser: 1000` (configurable via `security.pod_security.run_as_user`)
  - `runAsGroup: 1000` (configurable via `security.pod_security.run_as_group`)
  - `fsGroup: 1000` (configurable via `security.pod_security.fs_group`)

- **FR-061**: Generated container specs MUST include container-level `securityContext` with:
  - `allowPrivilegeEscalation: false`
  - `readOnlyRootFilesystem: true`
  - `capabilities.drop: ["ALL"]`

- **FR-062**: Generated pod specs MUST include `seccompProfile.type: RuntimeDefault`.

- **FR-063**: System MUST generate `emptyDir` volume mounts for writable directories (`/tmp`, `/home/floe`) when `readOnlyRootFilesystem: true`.

- **FR-064**: System MUST support configurable writable mount points via `security.pod_security.writable_paths` configuration list.

#### Compilation and Output

- **FR-070**: `floe compile` MUST generate NetworkPolicy manifests in `target/network/` directory when `security.network_policies.enabled: true`.

- **FR-071**: Generated manifests MUST be organized as: `{namespace}-default-deny.yaml`, `{namespace}-allow-egress.yaml`, `{namespace}-allow-ingress.yaml`.

- **FR-072**: System MUST generate a summary file `target/network/NETWORK-POLICY-SUMMARY.md` documenting all generated policies.

- **FR-073**: Compilation MUST merge overlapping egress rules into minimal NetworkPolicy definitions.

#### CLI Commands

- **FR-080**: System MUST provide `floe network generate` command to generate NetworkPolicy manifests without full compilation.

- **FR-081**: System MUST provide `floe network validate` command to validate generated manifests against cluster CNI capabilities.

- **FR-082**: System MUST provide `floe network audit` command to analyze current cluster NetworkPolicy state.

- **FR-083**: System MUST provide `floe network diff` command to show differences between expected and deployed NetworkPolicies.

- **FR-084**: System MUST provide `floe network check-cni` command to verify CNI plugin supports NetworkPolicies.

#### Security and Compliance

- **FR-090**: Generated NetworkPolicies MUST include label `app.kubernetes.io/managed-by: floe` for resource tracking.

- **FR-091**: System MUST log all NetworkPolicy generation operations to audit trail.

- **FR-092**: System MUST warn if a namespace lacks default-deny policy during audit.

- **FR-093**: System MUST support NetworkPolicy dry-run mode for testing without deployment.

### Key Entities

- **NetworkPolicyGenerator**: Core class that transforms floe configuration into Kubernetes NetworkPolicy YAML manifests. Handles namespace-specific rule generation and policy aggregation.

- **NetworkPolicyConfig**: Pydantic model representing NetworkPolicy configuration including default-deny settings, egress allowlists, and namespace mappings.

- **EgressRule**: Pydantic model representing a single egress allowlist entry with destination namespace, port, protocol, and optional CIDR.

- **IngressRule**: Pydantic model representing a single ingress allowlist entry with source namespace, pod selector, and port.

- **PodSecurityConfig**: Pydantic model representing pod and container security context settings (inherited from Epic 7B, extended for read-only filesystem support).

- **NamespaceSecurityConfig**: Pydantic model representing namespace-level security settings including PSS labels and NetworkPolicy configuration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Generated NetworkPolicies pass `kubectl apply --dry-run=server` validation without errors.

- **SC-002**: Default-deny policies block 100% of unauthorized cross-namespace traffic in integration tests.

- **SC-003**: Authorized egress (DNS, Polaris, OTel, external HTTPS) succeeds 100% of the time with policies applied.

- **SC-004**: Pod Security Standard enforcement rejects 100% of non-compliant pod specs within 1 second of submission.

- **SC-005**: `floe network audit` completes full cluster analysis within 30 seconds for clusters with up to 100 namespaces.

- **SC-006**: `floe network diff` accurately detects 100% of NetworkPolicy drift between expected and deployed state.

- **SC-007**: All generated pod specs include required security context fields (runAsNonRoot, capabilities.drop, seccompProfile).

- **SC-008**: Zero instances of missing default-deny policies for managed namespaces in production deployments.

## Assumptions

- Kubernetes 1.25+ is available (required for Pod Security Admission controller as default)
- CNI plugin supports NetworkPolicies (Calico, Cilium, or cloud-native CNI with policy support)
- Epic 7B (K8s RBAC) is complete, providing namespace configuration and ServiceAccount generation
- Platform team has cluster-admin or equivalent permissions for NetworkPolicy and namespace configuration
- OTel Collector is deployed in `floe-platform` namespace on standard ports (4317/4318)
- Ingress controller is deployed in `ingress-nginx` namespace (or configurable alternative)

## Out of Scope

- Service mesh integration (Istio/Linkerd mTLS) - optional enhancement, separate Epic
- eBPF-based observability (Cilium Hubble) - optional enhancement
- GlobalNetworkPolicy (Calico/Cilium enterprise feature) - namespaced policies only
- Runtime security monitoring (Falco, Sysdig) - separate security tooling
- Network encryption beyond service mesh - K8s CNI encryption features
- Custom CNI plugins - only standard K8s NetworkPolicy API
- DNS-based egress policies (Cilium-specific) - CIDR-based only for portability

## References

- [Kubernetes NetworkPolicy Documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Calico NetworkPolicy Tutorial](https://docs.tigera.io/calico/latest/network-policy/get-started/kubernetes-policy/kubernetes-network-policy)
- [EKS Workshop - Pod Security Standards](https://www.eksworkshop.com/docs/security/pod-security-standards/)
- [Kubernetes Network Policy Best Practices](https://snyk.io/blog/kubernetes-network-policy-best-practices/)
- Epic 7B spec (`specs/7b-k8s-rbac/spec.md`) - RBAC and namespace configuration foundation
- `packages/floe-core/src/floe_core/rbac/` - Existing RBAC schema definitions
- `charts/cognee-platform/` - Existing Helm chart NetworkPolicy patterns
- `testing/k8s/` - K8s testing infrastructure with security contexts

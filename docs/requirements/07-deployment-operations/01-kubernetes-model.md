# REQ-600 to REQ-620: Kubernetes Deployment Model

**Domain**: Deployment and Operations
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines the Kubernetes resource model, networking, resource management, and security policies that enable cloud-native deployment of floe. All components deploy to Kubernetes—there is no fallback to Docker Compose or local services.

**Key Principle**: Kubernetes-native architecture (ADR-0017)

## Requirements

### REQ-600: Service Deployments (Layer 3) **[New]**

**Requirement**: System MUST deploy all Layer 3 (Services) components as Kubernetes Deployments with multiple replicas and rolling update strategy.

**Rationale**: Enables high availability and zero-downtime updates.

**Acceptance Criteria**:
- [ ] Layer 3 services: Dagster webserver, Polaris server, Cube server, OTLP Collector
- [ ] Each service deployed as Deployment (not Deployment for dev/test, Pod for prod)
- [ ] Minimum 2 replicas for prod, 1 for dev
- [ ] Rolling update strategy: maxSurge=1, maxUnavailable=0
- [ ] Pod disruption budgets defined (minAvailable=1)
- [ ] Service LoadBalancer or ClusterIP created for inter-pod communication

**Enforcement**:
- Helm chart validation tests (deployment strategy)
- Replica count verification
- Rolling update tests (pods replace without downtime)

**Constraints**:
- MUST use Deployment resource (not StatefulSet unless ordered startup needed)
- MUST define readiness and liveness probes
- MUST set resource requests and limits
- FORBIDDEN to use single replica in production

**Test Coverage**: `tests/integration/test_k8s_deployments.py`

**Traceability**:
- four-layer-overview.md Layer 3 (Services)
- ADR-0017 section "Service Deployment"

---

### REQ-601: Stateful Services (Databases, Caches) **[New]**

**Requirement**: System MUST deploy stateful services (PostgreSQL, Redis, MinIO) as Kubernetes StatefulSets with persistent volumes.

**Rationale**: Ensures data persistence, ordered startup, and stable network identities.

**Acceptance Criteria**:
- [ ] PostgreSQL deployed as StatefulSet with PersistentVolumeClaim
- [ ] Redis deployed as StatefulSet with persistence enabled
- [ ] MinIO (if used) deployed as StatefulSet with PersistentVolumeClaims
- [ ] StatefulSet headless Service created for DNS-based discovery
- [ ] PVC provisioned with StorageClass (e.g., `local-path` for dev, `ebs-gp3` for prod)
- [ ] Data backups configured (snapshots, WAL archiving)

**Enforcement**:
- StatefulSet deployment tests
- PVC binding verification
- Data persistence tests (pod restart → data preserved)
- Backup/recovery tests

**Constraints**:
- MUST use StatefulSet for ordered startup and stable DNS
- MUST define PVC with appropriate storage size
- MUST set resource requests for database pods
- FORBIDDEN to use local volumes for databases in production

**Test Coverage**: `tests/integration/test_k8s_statefulsets.py`

**Traceability**:
- four-layer-overview.md Layer 3 (Databases)
- ADR-0019 (Platform Services Lifecycle)

---

### REQ-602: Job Execution Model (Layer 4) **[New]**

**Requirement**: System MUST execute all Layer 4 (Data) operations as Kubernetes Jobs with run-to-completion semantics.

**Rationale**: Enables scalable, managed job execution with automatic retry and cleanup.

**Acceptance Criteria**:
- [ ] dbt run operations: K8s Job (one-time execution)
- [ ] dlt ingestion operations: K8s Job
- [ ] Quality checks: K8s Job
- [ ] Each job configured with: backoffLimit, ttlSecondsAfterFinished, activeDeadlineSeconds
- [ ] Job status monitored (pending, running, succeeded, failed)
- [ ] Failed jobs retained for 7 days (ttlSecondsAfterFinished=604800) for debugging
- [ ] Successful jobs cleaned up after 1 hour (ttlSecondsAfterFinished=3600)

**Enforcement**:
- Job execution tests (verify run-to-completion)
- Retry behavior tests (failed jobs retry up to backoffLimit)
- TTL cleanup tests (jobs deleted after TTL expires)

**Constraints**:
- MUST use Job resource (not Deployment for stateless jobs)
- MUST set backoffLimit (default: 0 for fail-fast, 3 for retryable operations)
- MUST set ttlSecondsAfterFinished for automatic cleanup
- FORBIDDEN to use long-running containers as Jobs (use Deployment/CronJob instead)

**Test Coverage**: `tests/integration/test_k8s_jobs.py`

**Traceability**:
- four-layer-overview.md Layer 4 (Data)
- ADR-0017 section "Test Execution as K8s Jobs"

---

### REQ-603: CronJob Scheduling **[New]**

**Requirement**: System MUST support scheduled pipeline execution via Kubernetes CronJobs managed by platform tools.

**Rationale**: Enables recurring data operations (nightly runs, hourly incremental loads).

**Acceptance Criteria**:
- [ ] CronJob created for each scheduled pipeline in floe.yaml
- [ ] Schedule defined as cron expression (e.g., "0 2 * * *" for 2am daily)
- [ ] Job template inherited from base Job spec
- [ ] Concurrency policy: Allow (multiple runs can overlap), Forbid (wait), Replace
- [ ] Starting deadline seconds: 3600 (skip runs older than 1 hour)
- [ ] Successful job history: keep last 3 runs
- [ ] Failed job history: keep last 10 runs

**Enforcement**:
- CronJob creation tests
- Schedule validation (cron syntax)
- Concurrency policy tests
- Job history cleanup tests

**Constraints**:
- MUST use CronJob resource (not custom schedulers)
- MUST validate cron syntax at compilation time
- MUST set concurrency policy explicitly (default: Allow)
- FORBIDDEN to hardcode schedules in application code (must be in floe.yaml)

**Test Coverage**: `tests/integration/test_k8s_cronjobs.py`

**Traceability**:
- floe.yaml schema (schedule configuration)
- ADR-0017 (K8s-native execution)

---

### REQ-604: Pod Networking (Service Discovery) **[New]**

**Requirement**: System MUST enable pod-to-pod communication via Kubernetes Service discovery (DNS-based).

**Rationale**: Enables service-to-service communication without hardcoded IP addresses.

**Acceptance Criteria**:
- [ ] Service created for each Layer 3 deployment
- [ ] Service type: ClusterIP (internal), LoadBalancer (external, staging/prod only)
- [ ] DNS name: `{service-name}.{namespace}.svc.cluster.local`
- [ ] Pod environment variables populated: `{SERVICE_NAME}_SERVICE_HOST`, `{SERVICE_NAME}_SERVICE_PORT`
- [ ] Pods can resolve service names and connect (tested)
- [ ] Network policies restrict pod-to-pod traffic (if enabled)

**Enforcement**:
- Service discovery tests (pods can reach services)
- DNS resolution tests (nslookup succeeds inside pod)
- Service endpoint verification (all pods are endpoints)

**Constraints**:
- MUST use Service resource for service discovery
- MUST use DNS names (not hardcoded IPs)
- MUST configure liveness/readiness probes for health checks
- FORBIDDEN to expose services externally without reason (use NodePort/LoadBalancer carefully)

**Test Coverage**: `tests/integration/test_k8s_service_discovery.py`

**Traceability**:
- Kubernetes Service documentation
- four-layer-overview.md networking model

---

### REQ-605: Pod Resource Management (Requests/Limits) **[New]**

**Requirement**: System MUST define CPU and memory requests and limits on all pod containers.

**Rationale**: Enables proper cluster resource allocation and prevents resource starvation.

**Acceptance Criteria**:
- [ ] All Deployments define resource requests (minimum guaranteed)
- [ ] All Deployments define resource limits (maximum allowed)
- [ ] Typical service: request 500m CPU, 512Mi RAM; limit 2000m CPU, 2Gi RAM
- [ ] Typical job: request 1000m CPU, 2Gi RAM; limit 4000m CPU, 4Gi RAM
- [ ] Database pods: larger limits (configurable in values.yaml)
- [ ] Resource metrics validated in Kind cluster (actual usage observed)

**Enforcement**:
- Resource definition validation tests (requests/limits present)
- Cluster resource capacity tests (total requests don't exceed cluster capacity)
- OOMKilled tests (pod behavior on memory limit exceeded)

**Constraints**:
- MUST define both requests and limits (requests ≤ limits)
- MUST use valid Kubernetes resource units (m for millicpu, Mi/Gi for memory)
- MUST NOT define requests > available cluster capacity
- FORBIDDEN to omit resource definitions (causes eviction during contention)

**Test Coverage**: `tests/integration/test_k8s_resources.py`

**Traceability**:
- Kubernetes Resource documentation
- Kind cluster capacity planning

---

### REQ-606: Pod Security Context **[New]**

**Requirement**: System MUST enforce security contexts on pods (non-root user, read-only filesystem).

**Rationale**: Reduces attack surface and enforces principle of least privilege.

**Acceptance Criteria**:
- [ ] runAsUser: non-root (typically 1000)
- [ ] runAsNonRoot: true
- [ ] allowPrivilegeEscalation: false
- [ ] readOnlyRootFilesystem: true (with writable /tmp if needed)
- [ ] seccomp profile: restricted
- [ ] Containers run as non-root verified in pod logs

**Enforcement**:
- Security context validation tests
- Pod admission tests (reject privileged pods)
- Non-root execution verification

**Constraints**:
- MUST run containers as non-root user
- MUST enable readOnlyRootFilesystem (except /tmp for temp files)
- MUST NOT use privileged containers
- FORBIDDEN to run as UID 0 (root)

**Test Coverage**: `tests/integration/test_k8s_security.py`

**Traceability**:
- Kubernetes Pod Security Standards
- NIST container security guidelines

---

### REQ-607: Namespace Isolation **[New]**

**Requirement**: System MUST deploy platform components in isolated Kubernetes namespaces by environment (floe-dev, floe-staging, floe-prod).

**Rationale**: Enables multi-environment deployment and reduces blast radius.

**Acceptance Criteria**:
- [ ] Development: namespace `floe-dev`
- [ ] Staging: namespace `floe-staging`
- [ ] Production: namespace `floe-prod`
- [ ] Each namespace isolated with NetworkPolicy (if enabled)
- [ ] RBAC rules restrict access by namespace
- [ ] Resource quotas limit namespace resource usage

**Enforcement**:
- Namespace creation tests
- Namespace isolation tests (pods in floe-dev can't reach floe-prod)
- RBAC rule validation

**Constraints**:
- MUST use separate namespaces for dev/staging/prod
- MUST define resource quotas per namespace
- MUST configure RBAC rules per namespace
- FORBIDDEN to share namespace between environments

**Test Coverage**: `tests/integration/test_k8s_namespaces.py`

**Traceability**:
- Kubernetes Namespaces documentation
- TESTING.md (environment separation)

---

### REQ-608: Network Policies **[New]**

**Requirement**: System SHOULD define NetworkPolicies to restrict pod-to-pod traffic (opt-in, production recommended).

**Rationale**: Enforces network segmentation and reduces lateral movement risk.

**Acceptance Criteria**:
- [ ] NetworkPolicy allows Layer 3 service → Layer 4 job communication
- [ ] NetworkPolicy allows Layer 4 job → external storage (Iceberg, S3)
- [ ] NetworkPolicy denies unexpected traffic (default deny)
- [ ] Exceptions documented (e.g., Dagster → PostgreSQL)
- [ ] Network policies disabled in dev (for ease of debugging), enabled in prod
- [ ] Network policy configuration in values.yaml (networkPolicies.enabled)

**Enforcement**:
- Network policy validation tests
- Policy denial tests (blocked traffic not reaching destination)
- Exception tests (allowed traffic succeeds)

**Constraints**:
- MUST use NetworkPolicy resource (if not available, skip requirement)
- SHOULD enable by default in prod environments
- MUST document all ingress/egress rules
- FORBIDDEN to create overly restrictive policies that break services

**Test Coverage**: `tests/integration/test_k8s_network_policies.py`

**Traceability**:
- Kubernetes NetworkPolicy documentation
- CIS Kubernetes Benchmarks

---

### REQ-609: Health Checks (Probes) **[New]**

**Requirement**: System MUST define liveness and readiness probes for all pods.

**Rationale**: Enables automatic pod restart and traffic steering based on health.

**Acceptance Criteria**:
- [ ] Liveness probe: detects crashed processes (periodically check health)
- [ ] Readiness probe: detects ready-to-receive-traffic state
- [ ] HTTP probes: GET /health endpoint (or service-specific)
- [ ] TCP probes: port connectivity checks
- [ ] Exec probes: custom health scripts
- [ ] Probe configuration: initialDelaySeconds=10, periodSeconds=10, timeoutSeconds=2, failureThreshold=3

**Enforcement**:
- Probe validation tests (probes defined and working)
- Pod restart verification (unhealthy pod → restart)
- Traffic steering tests (unready pod excluded from endpoints)

**Constraints**:
- MUST define both liveness and readiness probes
- MUST use appropriate probe type (HTTP for REST APIs, TCP for databases)
- MUST set reasonable timeout and failure thresholds
- FORBIDDEN to set overly aggressive probe thresholds (causes flapping)

**Test Coverage**: `tests/integration/test_k8s_probes.py`

**Traceability**:
- Kubernetes Probe documentation
- four-layer-overview.md (Layer 3 services)

---

### REQ-610: Resource Quotas **[New]**

**Requirement**: System MUST enforce resource quotas per namespace to prevent resource monopolization.

**Rationale**: Ensures fair cluster resource allocation across environments.

**Acceptance Criteria**:
- [ ] Dev namespace quota: requests.cpu=4, requests.memory=8Gi
- [ ] Staging namespace quota: requests.cpu=8, requests.memory=16Gi
- [ ] Prod namespace quota: requests.cpu=16, requests.memory=32Gi
- [ ] Quota objects: ResourceQuota (CPU, memory), PodQuota (max pods per namespace)
- [ ] Quota exceeded → new pod creation fails (clear error message)
- [ ] Quota monitoring via kubectl describe resourcequota

**Enforcement**:
- ResourceQuota creation tests
- Quota limit tests (exceed quota → fail)
- Quota monitoring tests

**Constraints**:
- MUST define ResourceQuota per namespace
- MUST set requests.cpu and requests.memory quotas
- MUST NOT exceed available cluster capacity when summed
- FORBIDDEN to disable quotas in production

**Test Coverage**: `tests/integration/test_k8s_quotas.py`

**Traceability**:
- Kubernetes ResourceQuota documentation
- Kind cluster capacity planning

---

### REQ-611: Init Containers and Sidecar Patterns **[New]**

**Requirement**: System MAY use Kubernetes init containers for pre-startup tasks and sidecars for cross-cutting concerns.

**Rationale**: Enables clean separation of concerns (initialization, observability injection).

**Acceptance Criteria**:
- [ ] Init containers run before main container (e.g., database migration)
- [ ] Sidecar containers run alongside main container (e.g., log shipping)
- [ ] Init container failure blocks pod startup (enforcement)
- [ ] Sidecars monitored independently (own probes and restart policy)
- [ ] Example: Dagster init container → database schema migration

**Enforcement**:
- Init container execution tests
- Sidecar lifecycle tests
- Pod startup order verification

**Constraints**:
- MUST use init containers only for startup tasks (not long-running)
- MUST define resource requests/limits for all init containers
- MUST handle init container failure gracefully
- FORBIDDEN to use sidecar injection without explicit configuration

**Test Coverage**: `tests/integration/test_k8s_init_containers.py`

**Traceability**:
- Kubernetes init containers documentation
- Kubernetes sidecar patterns

---

### REQ-612: Logging and Log Collection **[New]**

**Requirement**: System MUST enable container log collection to centralized logging backend (via OTLP collector or sidecar).

**Rationale**: Enables log aggregation and debugging across all pods.

**Acceptance Criteria**:
- [ ] Container logs written to stdout (not files)
- [ ] Logs captured by Kubernetes (kubectl logs works)
- [ ] Fluent-bit sidecar (optional) ships logs to OTLP Collector
- [ ] Logs structured as JSON for parsing
- [ ] Log retention: 7 days in Kind, configurable in prod

**Enforcement**:
- Log collection tests (kubectl logs returns logs)
- Sidecar log shipping tests (logs appear in backend)
- Log format validation (JSON parsing)

**Constraints**:
- MUST write logs to stdout (not files)
- MUST NOT exceed 100MB per container (log rotation by kubelet)
- MUST structure logs as JSON (for parsing)
- FORBIDDEN to rely on container filesystem logs (lost on container restart)

**Test Coverage**: `tests/integration/test_k8s_logging.py`

**Traceability**:
- Kubernetes logging documentation
- REQ-506 (Structured Logging)

---

### REQ-613: ImagePullPolicy **[New]**

**Requirement**: System MUST define appropriate imagePullPolicy for container images.

**Rationale**: Controls when images are pulled and enables efficient image caching.

**Acceptance Criteria**:
- [ ] Dev environment: imagePullPolicy=IfNotPresent (use local images if available)
- [ ] Prod environment: imagePullPolicy=Always (always pull latest)
- [ ] Image tags: use semantic versioning (not :latest in prod)
- [ ] Private registries: configure imagePullSecrets
- [ ] Image pull failures: pod stays in ImagePullBackOff until resolved

**Enforcement**:
- ImagePullPolicy validation tests
- Image pull secret tests (if using private registry)
- Image tag validation (no :latest in prod)

**Constraints**:
- MUST use IfNotPresent for local development
- MUST use Always for production (ensures latest code)
- MUST use specific image tags (not :latest)
- FORBIDDEN to use :latest tag in production manifests

**Test Coverage**: `tests/integration/test_k8s_image_policy.py`

**Traceability**:
- Kubernetes Container Images documentation
- Helm chart image configuration

---

### REQ-614: Secret Management (Kubernetes Secrets) **[New]**

**Requirement**: System MUST store sensitive data (credentials, keys) in Kubernetes Secrets, not in ConfigMaps or environment variables.

**Rationale**: Enables RBAC-based access control and audit logging for credentials.

**Acceptance Criteria**:
- [ ] Database passwords: stored in Secret (not ConfigMap)
- [ ] API keys: stored in Secret
- [ ] SSL/TLS certificates: stored as Secret type: tls
- [ ] Secrets mounted as volumes (not env vars) for sensitive data
- [ ] Secret rotation enabled (if using sealed secrets or external secret manager)
- [ ] Audit logging captures secret access

**Enforcement**:
- Secret creation tests
- Secret mounting verification
- RBAC access control tests

**Constraints**:
- MUST use Kubernetes Secrets (not hardcoded in manifests)
- MUST NOT use ConfigMaps for sensitive data
- MUST mount secrets as volumes (not env vars for passwords)
- FORBIDDEN to commit secrets to git (use sealed secrets or external secret manager)

**Test Coverage**: `tests/integration/test_k8s_secrets.py`

**Traceability**:
- Kubernetes Secrets documentation
- REQ-514 (Secret Management - general)

---

### REQ-615: Image Registry Configuration **[New]**

**Requirement**: System MUST configure container image registries for pulling platform and plugin images.

**Rationale**: Enables using private registries and mirrors.

**Acceptance Criteria**:
- [ ] Default registry: ghcr.io (GitHub Container Registry)
- [ ] Registry configurable via values.yaml: image.registry
- [ ] Image names: ghcr.io/anthropics/floe/{component}:{version}
- [ ] Private registries: use imagePullSecret (if required)
- [ ] Mirror registries: support via registryMirrors (in containerd config)

**Enforcement**:
- Image registry validation tests
- Image pull tests (images pull successfully)
- imagePullSecret validation (if using private registry)

**Constraints**:
- MUST use GHCR as default registry
- MUST support registry override via values.yaml
- MUST support multiple registries (if using mirrors)
- FORBIDDEN to hardcode registry URLs in Helm charts (use values.yaml)

**Test Coverage**: `tests/integration/test_k8s_image_registry.py`

**Traceability**:
- Helm image configuration best practices
- GHCR documentation

---

### REQ-616: Volume Management (PVCs and ConfigMaps) **[New]**

**Requirement**: System MUST manage persistent and configuration storage via PersistentVolumeClaims and ConfigMaps.

**Rationale**: Enables data persistence and configuration management.

**Acceptance Criteria**:
- [ ] Database data: PersistentVolumeClaim with StorageClass
- [ ] Configuration: ConfigMap (not hardcoded in image)
- [ ] Logs: emptyDir volume for temporary logs (cleared on pod restart)
- [ ] Temp files: emptyDir volume for scratch space
- [ ] PVC size: configurable in values.yaml
- [ ] StorageClass: configurable (local-path for dev, ebs-gp3 for prod)

**Enforcement**:
- PVC binding tests (PVC bound to PV)
- ConfigMap mounting tests (config available in pod)
- Volume persistence tests (data survives pod restart)

**Constraints**:
- MUST use PVC for persistent data (not local volumes)
- MUST use ConfigMap for configuration (not env vars)
- MUST use emptyDir for temporary storage
- FORBIDDEN to use hostPath volumes in production

**Test Coverage**: `tests/integration/test_k8s_volumes.py`

**Traceability**:
- Kubernetes PersistentVolume documentation
- Kubernetes ConfigMap documentation

---

### REQ-617: Multi-Container Pod Coordination **[New]**

**Requirement**: System MAY use multi-container pods with shared namespaces and volumes.

**Rationale**: Enables sidecar patterns and coordinated initialization.

**Acceptance Criteria**:
- [ ] Main container: application logic
- [ ] Init containers: startup tasks (migrations, configuration)
- [ ] Sidecar containers: cross-cutting concerns (logging, tracing)
- [ ] Containers share network namespace (localhost communication)
- [ ] Containers share volumes (shared storage)
- [ ] Each container has own resource requests/limits and probes

**Enforcement**:
- Multi-container pod tests
- Sidecar lifecycle tests
- Container-to-container communication tests

**Constraints**:
- MUST define liveness/readiness probes per container
- MUST set resource limits per container (not just pod)
- MUST handle init container failure gracefully
- FORBIDDEN to couple container lifecycles (each container independently restartable)

**Test Coverage**: `tests/integration/test_k8s_multi_container.py`

**Traceability**:
- Kubernetes Pod documentation
- Kubernetes sidecar patterns

---

### REQ-618: Pod Affinity and Anti-Affinity **[New]**

**Requirement**: System MAY define pod affinity rules to co-locate or spread pods across nodes.

**Rationale**: Enables high availability and performance optimization.

**Acceptance Criteria**:
- [ ] Pod anti-affinity: spread replicas across nodes (recommended for services)
- [ ] Pod affinity: co-locate related pods (optional, e.g., app + database)
- [ ] Node affinity: restrict pods to specific node pools (optional, e.g., GPU nodes)
- [ ] Soft affinity: guide scheduling without blocking pod creation
- [ ] Hard affinity: block pod creation if constraint unsatisfiable

**Enforcement**:
- Affinity rule validation tests
- Pod distribution tests (verify spreading/co-location)
- Node pool tests (verify node selection)

**Constraints**:
- MUST use soft affinity (preferredDuringScheduling) in development
- SHOULD use hard affinity (requiredDuringScheduling) in production
- MUST NOT over-constrain scheduling (causes pending pods)
- FORBIDDEN to use affinity without verifying cluster capacity

**Test Coverage**: `tests/integration/test_k8s_affinity.py`

**Traceability**:
- Kubernetes Pod Affinity documentation
- Kubernetes Node Affinity documentation

---

### REQ-619: Container Registry Credentials **[New]**

**Requirement**: System MUST manage private registry credentials securely (if using private registries).

**Rationale**: Enables authentication to private container registries without exposing credentials.

**Acceptance Criteria**:
- [ ] imagePullSecret created for private registry access
- [ ] Secret type: kubernetes.io/dockercfg or kubernetes.io/dockerconfigjson
- [ ] Credentials provided via environment variables (not hardcoded)
- [ ] Service account linked to imagePullSecret
- [ ] Credentials rotated periodically

**Enforcement**:
- imagePullSecret validation tests
- Service account linking tests
- Private image pull tests (succeeds with secret, fails without)

**Constraints**:
- MUST use imagePullSecret (not docker login)
- MUST NOT commit registry credentials to git
- MUST use environment variables for credential provisioning
- FORBIDDEN to hardcode credentials in Helm values

**Test Coverage**: `tests/integration/test_k8s_registry_credentials.py`

**Traceability**:
- Kubernetes Image Pull Secrets documentation
- Helm secret management best practices

---

### REQ-620: Node Selection and Taints/Tolerations **[New]**

**Requirement**: System MAY use node selectors, taints, and tolerations for workload targeting.

**Rationale**: Enables workload isolation and optimization (e.g., dedicated data job nodes).

**Acceptance Criteria**:
- [ ] Node selector: route pods to labeled nodes (e.g., node-type=compute)
- [ ] Taints: mark nodes (e.g., dedicated=batch, NoSchedule)
- [ ] Tolerations: allow pods to run on tainted nodes
- [ ] Example: data jobs tolerate batch taint, services don't
- [ ] Taints/tolerations documented and configurable

**Enforcement**:
- Node selector validation tests
- Taint/toleration matching tests
- Pod placement verification

**Constraints**:
- MUST use nodeSelector for simple workload targeting
- SHOULD use taints/tolerations for complex scenarios
- MUST document all taints and corresponding tolerations
- FORBIDDEN to create pods without matching tolerations on tainted nodes (stuck pending)

**Test Coverage**: `tests/integration/test_k8s_node_selection.py`

**Traceability**:
- Kubernetes Node Selection documentation
- Kubernetes Taints and Tolerations documentation

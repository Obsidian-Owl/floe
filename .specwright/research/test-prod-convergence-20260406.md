# Research Brief: Test Infrastructure Stabilisation & Test-Production Convergence

**Date:** 2026-04-06
**Confidence:** HIGH (official docs, GitHub issues, multiple corroborating sources per track)
**Tracks:** 4
**Depends on:** `tunnel-stability-20260329.md`, `e2e-ci-resilience-20260329.md`, `e2e-structural-resolution-20260405.md`

---

## Executive Summary

The recurring E2E/integration test failures trace to a fundamental architecture problem: **tests run on the host, services run in a remote cluster, connected by fragile port-forwards that die silently**. This is not how the industry does it. The fix is not better port-forwards — it's eliminating the need for them entirely.

Separately, security hardening gaps (containers running as root, no capability drops) reveal that **test infrastructure diverges from production posture**. The fix is making security contexts a base-chart default, not an environment overlay.

| Problem | Root Cause | Industry Pattern | floe Gap |
|---|---|---|---|
| Port-forwards die mid-test | kubectl port-forward has no auto-recovery (K8s #78446, closed won't-fix) | In-cluster test runner OR direct Docker socket access | Tests run from host via SSH tunnel + port-forward (2 failure points) |
| 7 containers run as root | Security contexts default to `{}` in subchart values | Security-hardened base defaults, PSS namespace enforcement | Security contexts only in values-dev.yaml, not base chart |
| Missing tools (kubeconform, kubesec) | Tools expected on host but not installed | Docker-based tool execution (`docker run -v`) | Tests call binaries directly, fail when missing |
| Destructive tests kill infrastructure | Resilience tests restart pods, killing port-forwards for remaining tests | Session separation (`-m "not resilience"` then `-m "resilience"`) | All 313 E2E tests in one pytest session |
| Test ≠ production config | Different security contexts, storage classes, service types | Same chart, security in base values, only sizing/replicas in overlays | Security contexts in overlay values files, not templates |

---

## Track 1: Test Infrastructure Stabilisation

### Finding 1.1: kubectl port-forward Is Architecturally Broken for Long-Running Test Suites

**Confidence: HIGH** | Sources: [K8s kubectl#686](https://github.com/kubernetes/kubectl/issues/686), [kubectl#1525](https://github.com/kubernetes/kubectl/issues/1525), [kubectl#1620](https://github.com/kubernetes/kubectl/issues/1620)

kubectl port-forward has no auto-recovery. Issue #686 was closed as "not planned" in December 2019. Multiple issues confirm ongoing instability: connections drop every 5-10 minutes (#1525), die on TCP cancellation (#1620). The SPDY protocol (pre-K8s 1.31) adds proxy/gateway failures.

**For floe**: The SSH tunnel → kubectl port-forward chain has **two independent failure points**. When either dies, all service connectivity is lost silently. Processes remain as zombies — running but non-functional.

### Finding 1.2: Industry Pattern Is In-Cluster Test Execution or Direct Docker Socket Access

**Confidence: HIGH** | Sources: [Testkube docs](https://docs.testkube.io/articles/test-workflows), [Istio Test Framework wiki](https://github.com/istio/istio/wiki/Istio-Test-Framework), [Cilium E2E docs](https://docs.cilium.io/en/stable/contributing/testing/e2e/), [Crossplane testing](https://deepwiki.com/crossplane/crossplane/6.3-testing-framework)

| Project | Test Location | Service Connectivity | Port-Forward? |
|---|---|---|---|
| **Istio** | Host machine | MetalLB external IPs | No |
| **Cilium** | Hybrid (CLI on host, workloads in cluster) | K8s API + in-cluster pods | No |
| **Crossplane** | Host machine | K8s API polling, no direct service access | No |
| **Testkube** | K8s Job inside cluster | Cluster-internal DNS | No |
| **Kubeflow** | K8s Job inside cluster | NFS-backed PV for results | No |

**Key quote** (Istio wiki): *"Running tests natively on the host machine are orders of magnitude faster and inherently more reliable than in-cluster."*

**None of these projects use SSH-tunnelled port-forwards.** They either:
- (a) Run on a machine with direct Docker socket access to Kind (GitHub Actions runners)
- (b) Run tests as K8s Jobs inside the cluster (Testkube, Kubeflow)
- (c) Use MetalLB/cloud-provider-kind for stable external IPs (Istio)

### Finding 1.3: In-Cluster Test Runner Pattern (K8s Job)

**Confidence: HIGH** | Sources: [Testkube pytest example](https://docs.testkube.io/articles/examples/pytest-basic), [Kubeflow testing README](https://github.com/kubeflow/testing/blob/master/README.md)

The minimal DIY pattern:
1. Build a Docker image: `python:3.11-slim` + pip install pytest + test dependencies
2. Create a K8s Job with `serviceAccountName` bound to a Role with read access
3. Mount test sources via Git clone initContainer or ConfigMap
4. Run `pytest --junitxml=/results/junit.xml`
5. Extract results via S3 upload from within the pod, or `kubectl cp` before GC

**Key advantage**: Services accessed via cluster-internal DNS (e.g., `floe-platform-polaris.floe-test.svc.cluster.local:8181`) — no port-forward needed. Pod restarts don't break connectivity because DNS resolves to the new pod automatically.

### Finding 1.4: Port-Forward Alternatives (If Host-Based Tests Are Retained)

**Confidence: MEDIUM** | Sources: [kubefwd GitHub](https://github.com/txn2/kubefwd), [inlets blog](https://inlets.dev/blog/2022/06/24/fixing-kubectl-port-forward.html), [kftray GitHub](https://github.com/hcavarsan/kftray)

| Tool | Auto-Reconnect | Sudo Required | CI Suitable | License |
|---|---|---|---|---|
| **kubefwd** | Yes (K8s Informers) | Yes | Partial (needs root) | Apache-2.0 |
| **inlets-pro** | Yes (outbound WebSocket) | No | Yes | Commercial |
| **kftray** | Yes (watch API) | No | No (GUI/TUI) | Apache-2.0 |
| **krelay** | No | No | Yes | MIT |

kubefwd is the most practical OSS option but requires sudo. inlets-pro is architecturally the best fit (outbound connection from cluster survives SSH tunnel drops) but is commercial.

### Finding 1.5: Containerised Tool Execution

**Confidence: HIGH** | Sources: [kubeconform GitHub](https://github.com/yannh/kubeconform), [helm-unittest GitHub](https://github.com/helm-unittest/helm-unittest), [kubesec GitHub](https://github.com/controlplaneio/kubesec)

All three missing tools have official Docker images:

| Tool | Docker Image | Invocation |
|---|---|---|
| kubeconform | `ghcr.io/yannh/kubeconform:latest` | `docker run -v $(pwd):/manifests ghcr.io/yannh/kubeconform /manifests/` |
| helm-unittest | `helmunittest/helm-unittest:3.11.1-0.3.0` | `docker run -v $(pwd):/apps helmunittest/helm-unittest .` |
| kubesec | `kubesec/kubesec:v2` | `docker run -i kubesec/kubesec:v2 scan /dev/stdin < manifest.yaml` |

### Finding 1.6: Test Ordering for Destructive Tests

**Confidence: HIGH** | Sources: [pytest-order docs](https://pytest-dev.github.io/pytest-order/stable/usage.html), [pytest fixture docs](https://docs.pytest.org/en/stable/how-to/fixtures.html)

Two patterns:

1. **Session separation** (preferred for floe): `pytest tests/e2e/ -m "not resilience"` then `pytest tests/e2e/ -m "resilience"`. Simple, no plugin needed, no ordering risks.

2. **pytest-order** plugin: `@pytest.mark.order("last")` on destructive tests. Works within a single session but has unresolved interactions with pytest-xdist.

---

## Track 2: Production Deployment Patterns

### Finding 2.1: Comparable Platform Deployment Patterns

**Confidence: HIGH** | Sources: [Dagster deployment docs](https://docs.dagster.io/deployment/oss/oss-deployment-architecture), [Airbyte implementation guide](https://docs.airbyte.com/platform/enterprise-setup/implementation-guide), [Kubeflow installing](https://www.kubeflow.org/docs/started/installing-kubeflow/)

| Platform | Deployment Mechanism | Production Requirements |
|---|---|---|
| **Dagster** | Helm (two-release: infra + user code) | External PostgreSQL, separate code location pods |
| **Airbyte** | Helm (single chart, `global:` values) | External PostgreSQL, external S3, external secrets manager |
| **Kubeflow** | Kustomize + vendor distributions | Cloud-specific distributions recommended |
| **Strimzi** | Helm installs operator, CRDs manage clusters | Operator handles Day-2 lifecycle |

**Key pattern**: All production deployments externalize stateful services (PostgreSQL, object storage) and use external secrets managers. Internal/embedded services are dev/test only.

### Finding 2.2: GitOps Delivery — ArgoCD and Flux

**Confidence: HIGH** | Sources: [ArgoCD multi-source](https://argo-cd.readthedocs.io/en/stable/user-guide/multiple_sources/), [Flux Helm promotion](https://fluxcd.io/flux/use-cases/gh-actions-helm-promotion/), [flux2-kustomize-helm-example](https://github.com/fluxcd/flux2-kustomize-helm-example)

Both ArgoCD and Flux support the "same chart, different values" pattern natively:

- **ArgoCD**: Multi-source Application (stable since 2.6) — one source for chart, second source for environment-specific values from a separate Git repo
- **Flux**: HelmRelease CRD with composable `valuesFrom` (Secrets, ConfigMaps) and Kustomize patches for environment variants

**Flux promotion pattern**: Staging auto-upgrades → runs tests → emits repository dispatch → GitHub Actions creates PR updating production HelmRelease → human review + merge → production deploys.

### Finding 2.3: floe's Existing ADRs Align with Industry

**Confidence: HIGH** | Internal: ADR-0039, ADR-0042

floe already has accepted ADRs for:
- **ADR-0039**: GitOps promotion with immutable OCI artifacts tagged per environment
- **ADR-0042**: Logical environments (manifest.yaml) vs physical clusters (Helm values)

No conflicts found between external best practices and current floe architecture decisions.

### Finding 2.4: Operator vs Helm — When to Transition

**Confidence: HIGH** | Sources: [Strimzi blog](https://strimzi.io/blog/2018/11/01/using-helm/), [CloudNativePG charts](https://cloudnative-pg.io/charts/), [Datadog operator blog](https://www.datadoghq.com/blog/datadog-operator-helm/)

The heuristic: if the application needs continuous in-cluster reconciliation of runtime state (failover, backup, schema migration, self-healing), it needs an operator. For initial deployment and config-driven upgrades, Helm is sufficient.

**For floe currently**: Helm charts for initial deployment are appropriate. An operator becomes relevant when floe needs to manage lifecycle operations (e.g., auto-rolling Dagster daemon on config change, Polaris schema migration, automated backup/restore).

---

## Track 3: Test-Production Convergence

### Finding 3.1: The Convergence Principle — Security in Base, Sizing in Overlays

**Confidence: HIGH** | Sources: [K8s PSS docs](https://kubernetes.io/docs/concepts/security/pod-security-standards/), [Bitnami production-ready charts](https://engineering.bitnami.com/articles/the-road-to-production-ready-charts.html), [Helm security guide](https://oneuptime.com/blog/post/2026-01-17-helm-security-contexts-network-policies/view)

The industry consensus:

**MUST be identical across all environments** (defined in base chart templates or base values):
- `securityContext.runAsNonRoot: true`
- `securityContext.allowPrivilegeEscalation: false`
- `securityContext.capabilities.drop: ["ALL"]`
- `securityContext.seccompProfile.type: RuntimeDefault`
- RBAC structure (ServiceAccount, Role, RoleBinding shapes)
- Network policy templates (present everywhere, even if permissive in dev)

**MAY differ between environments** (defined in environment overlay values):
- `replicaCount` (1 in test, 2+ in prod)
- `resources.requests/limits` (minimal in test, production-sized in prod)
- `persistence.size` and `storageClass`
- `ingress.enabled` and TLS configuration
- Secrets source (hardcoded test creds vs ExternalSecret/Vault)
- `autoscaling.enabled`, `podDisruptionBudget.enabled`

### Finding 3.2: Pod Security Standards Enforcement

**Confidence: HIGH** | Sources: [K8s PSA docs](https://kubernetes.io/docs/concepts/security/pod-security-admission/), [Kyverno policies](https://kyverno.io/policies/pod-security/restricted/require-run-as-nonroot/require-run-as-nonroot/)

PSS is enforced via namespace labels:
```yaml
pod-security.kubernetes.io/enforce: restricted
pod-security.kubernetes.io/audit: restricted
pod-security.kubernetes.io/warn: restricted
```

**Recommended migration path** (3-phase):
1. `enforce: privileged`, `audit: restricted`, `warn: restricted` — observe without blocking
2. `enforce: baseline`, `audit: restricted`, `warn: restricted` — block worst offenders
3. `enforce: restricted` — full enforcement

**PSS restricted profile requires ALL of:**
- `runAsNonRoot: true`
- `allowPrivilegeEscalation: false`
- `capabilities.drop` includes `ALL`
- `seccompProfile.type: RuntimeDefault` or `Localhost`
- No hostNetwork, hostPID, hostIPC
- No hostPath volumes

### Finding 3.3: The Kind-vs-Production "Test Gap"

**Confidence: HIGH** | Sources: [Kind known issues](https://kind.sigs.k8s.io/docs/user/known-issues/), [Kind LoadBalancer](https://kind.sigs.k8s.io/docs/user/loadbalancer/)

| Divergence Point | Kind | Production (EKS/GKE/AKS) | Mitigation |
|---|---|---|---|
| CNI | kindnetd (basic) | Calico/Cilium/VPC CNI | Accept — network policy behavior may differ |
| StorageClass | local-path (single-node) | gp2/premium-ssd (replicated) | Use `storageClass: ""` in values |
| LoadBalancer | `<pending>` without cloud-provider-kind | Cloud LB provisioned | Use NodePort in test |
| DNS from host | Not resolvable | Not applicable (apps are in-cluster) | Port-forward or in-cluster test runner |
| IAM | No IRSA/Workload Identity | Cloud-native IAM | Mock or skip IAM-dependent tests |
| Node autoscaling | None | Cloud autoscaler | Accept — test with fixed node count |

**Key insight**: Most divergence points are about _infrastructure capabilities_, not _application behavior_. If the application chart uses the same security contexts, the same RBAC, the same network policies across environments, the application-level test gap is minimal. The remaining gap is infrastructure-level and is best addressed by running production-path tests in a staging cluster (not Kind).

### Finding 3.4: vCluster as Alternative to Kind

**Confidence: MEDIUM** | Source: [vCluster comparison](https://website.vcluster.com/blog/kubernetes-development-environments-a-comparison) (vendor source — treat comparisons with caution)

vCluster creates a logically-isolated K8s cluster running as a StatefulSet inside a host cluster. Provisioning takes seconds (uses k3s). Shares host worker nodes, so CNI/storage/scheduling match the host cluster — better parity than Kind if the host is a cloud cluster.

**For floe**: vCluster on a Hetzner K8s cluster would give better parity than Kind-on-DevPod, but adds complexity. Worth evaluating when floe targets cloud deployments.

---

## Track 4: Security Hardening Defaults

### Finding 4.1: Per-Component Security Context Support

**Confidence: HIGH** | Sources: [Dagster values.yaml](https://github.com/dagster-io/dagster/blob/master/helm/dagster/values.yaml), [Dagster #16092](https://github.com/dagster-io/dagster/issues/16092), [OTel collector values.yaml](https://github.com/open-telemetry/opentelemetry-helm-charts/blob/main/charts/opentelemetry-collector/values.yaml), [Jaeger values.yaml](https://github.com/jaegertracing/helm-charts/blob/main/charts/jaeger/values.yaml), [Marquez #3060](https://github.com/MarquezProject/marquez/issues/3060)

| Component | Supports securityContext? | Default | Can Run Non-Root? | Notes |
|---|---|---|---|---|
| **Dagster** (webserver, daemon) | Yes — `podSecurityContext`, `securityContext` | Empty `{}` | Yes (UID 1001 in Cloud Agent image) | Init container fix merged post-1.4.9 (#16092) |
| **OTel Collector** | Yes — `podSecurityContext`, `securityContext` | Empty `{}` | Yes | No special requirements |
| **Jaeger** (all-in-one) | Partial — `podSecurityContext` at top level | `runAsUser: 10001` pod-level | Maybe — image may need USER directive | [Jaeger #105](https://github.com/jaegertracing/helm-charts/issues/105) |
| **MinIO** (Bitnami) | Yes — fully hardened defaults | `runAsNonRoot: true`, `drop: ["ALL"]`, `readOnly: true` | Yes (UID 1001) | Already production-ready |
| **Marquez** | **No** — no securityContext in chart or Dockerfile | Runs as root (UID 0) | **No** — no USER in Dockerfile | Open issue #3060, no PR merged |

### Finding 4.2: Marquez Is the Blocker

Marquez has no upstream path to non-root. Options:
1. Build a custom Marquez image with `USER 1001` directive
2. Use Helm post-rendering to inject securityContext (may fail if JVM needs /tmp writes)
3. Grant a namespace-level PSS exemption for the Marquez pod
4. Replace Marquez with an alternative lineage backend

### Finding 4.3: Capability Dropping Is Safe for All Data Platform Workloads

**Confidence: HIGH** | Sources: [kubesec.io](https://kubesec.io/basics/securitycontext-capabilities/), [Datadog Security Labs](https://securitylabs.datadoghq.com/articles/container-security-fundamentals-part-3/)

`capabilities.drop: ["ALL"]` with no adds is safe for Dagster, dbt jobs, OTel collector, Marquez, Jaeger, and MinIO. None of these bind privileged ports or perform kernel operations. Init containers doing readiness checks (e.g., `wait-for-postgresql` using `pg_isready`) also don't need capabilities.

**readOnlyRootFilesystem** constraint: Marquez (JVM) and Jaeger will need `emptyDir` volumes mounted at `/tmp` for JVM temp files.

### Finding 4.4: The Hardening Pattern for floe's Chart

The correct approach is **security-hardened base defaults in the chart templates**, not in environment overlay values files. Environment overlays should only weaken security if explicitly justified (and documented as a deviation).

In `values.yaml` (base):
```yaml
global:
  containerSecurityContext:
    runAsNonRoot: true
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: true
    capabilities:
      drop: ["ALL"]
    seccompProfile:
      type: RuntimeDefault
```

Templates should apply this to ALL containers (including init containers) unless a component has a documented exception.

---

## Open Questions

1. **In-cluster test runner vs host-based**: Which pattern should floe adopt? In-cluster eliminates port-forward fragility but requires building a test runner image and extracting results. Host-based with direct Docker socket access (GitHub Actions) is simpler but doesn't work for DevPod.

2. **Marquez non-root**: Should floe build a custom Marquez image, request an upstream fix, or grant a PSS exemption?

3. **vCluster evaluation**: Should floe evaluate vCluster on Hetzner as a replacement for Kind-on-DevPod for better production parity?

4. **Dagster subchart version**: Is the vendored Dagster subchart recent enough to include the init container securityContext fix (#16092)?

---

## Sources (Consolidated)

### Test Infrastructure
- [K8s kubectl#686 — port-forward won't-fix](https://github.com/kubernetes/kubectl/issues/686)
- [Testkube TestWorkflow docs](https://docs.testkube.io/articles/test-workflows)
- [Testkube pytest example](https://docs.testkube.io/articles/examples/pytest-basic)
- [Istio Test Framework wiki](https://github.com/istio/istio/wiki/Istio-Test-Framework)
- [Cilium E2E testing docs](https://docs.cilium.io/en/stable/contributing/testing/e2e/)
- [Crossplane testing framework](https://deepwiki.com/crossplane/crossplane/6.3-testing-framework)
- [kubefwd GitHub](https://github.com/txn2/kubefwd)
- [inlets blog](https://inlets.dev/blog/2022/06/24/fixing-kubectl-port-forward.html)
- [kubeconform GitHub](https://github.com/yannh/kubeconform)
- [helm-unittest GitHub](https://github.com/helm-unittest/helm-unittest)
- [kubesec GitHub](https://github.com/controlplaneio/kubesec)
- [pytest-order docs](https://pytest-dev.github.io/pytest-order/stable/usage.html)
- [Kind LoadBalancer](https://kind.sigs.k8s.io/docs/user/loadbalancer/)

### Production Deployment
- [Dagster OSS deployment](https://docs.dagster.io/deployment/oss/oss-deployment-architecture)
- [Dagster Code Locations](https://dagster.io/blog/dagster-code-locations)
- [Airbyte implementation guide](https://docs.airbyte.com/platform/enterprise-setup/implementation-guide)
- [ArgoCD multi-source](https://argo-cd.readthedocs.io/en/stable/user-guide/multiple_sources/)
- [Flux Helm promotion](https://fluxcd.io/flux/use-cases/gh-actions-helm-promotion/)
- [flux2-kustomize-helm-example](https://github.com/fluxcd/flux2-kustomize-helm-example)
- [Helmfile best practices](https://helmfile.readthedocs.io/en/latest/writing-helmfile/)
- [Strimzi Helm deployment](https://strimzi.io/blog/2018/11/01/using-helm/)
- [CloudNativePG charts](https://cloudnative-pg.io/charts/)
- [Datadog operator vs Helm](https://www.datadoghq.com/blog/datadog-operator-helm/)

### Test-Production Convergence
- [K8s Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [K8s Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/)
- [Kyverno require-run-as-nonroot](https://kyverno.io/policies/pod-security/restricted/require-run-as-nonroot/require-run-as-nonroot/)
- [Kind known issues](https://kind.sigs.k8s.io/docs/user/known-issues/)
- [vCluster comparison](https://website.vcluster.com/blog/kubernetes-development-environments-a-comparison)
- [Bitnami production-ready charts](https://engineering.bitnami.com/articles/the-road-to-production-ready-charts.html)

### Security Hardening
- [Dagster Helm values.yaml](https://github.com/dagster-io/dagster/blob/master/helm/dagster/values.yaml)
- [Dagster #16092 — init container securityContext](https://github.com/dagster-io/dagster/issues/16092)
- [OTel collector Helm values.yaml](https://github.com/open-telemetry/opentelemetry-helm-charts/blob/main/charts/opentelemetry-collector/values.yaml)
- [Jaeger Helm values.yaml](https://github.com/jaegertracing/helm-charts/blob/main/charts/jaeger/values.yaml)
- [Marquez #3060 — non-root](https://github.com/MarquezProject/marquez/issues/3060)
- [kubesec capabilities](https://kubesec.io/basics/securitycontext-capabilities/)
- [Datadog container security](https://securitylabs.datadoghq.com/articles/container-security-fundamentals-part-3/)

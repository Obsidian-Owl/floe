# Research Brief: Service Mesh Evaluation for Infrastructure Stability

**Topic**: Istio, Linkerd, Cilium, and alternative approaches for reducing infrastructure instability and wrapper code
**Date**: 2026-03-30
**Confidence**: HIGH (official docs, multiple corroborating sources, codebase analysis)
**Tracks**: 4
**Depends on**: `tunnel-stability-20260329.md`, `e2e-ci-resilience-20260329.md`

---

## Executive Summary

**Istio and service meshes do NOT address floe's #1 infrastructure problem.** The dominant
failure mode (45+ of 91 test failures) is port-forward and SSH tunnel instability between
the developer host and the Kind cluster. Service meshes only govern service-to-service
traffic *inside* the mesh — `kubectl port-forward` bypasses Istio's iptables rules entirely.

The structural solution is the **in-cluster test runner** (already 90% built), which
eliminates host-to-cluster connectivity as a dependency. A service mesh would provide
incremental value for service-to-service retry/circuit-breaking but at significant
resource cost and operational complexity.

---

## Track 1: Istio Applicability Assessment

### What Istio Does

Istio injects Envoy sidecar proxies into pods, intercepting all TCP/HTTP traffic via
iptables REDIRECT rules. It provides:

- **Automatic mTLS** between meshed services
- **Retry policies** with configurable budgets (`retries.attempts`, `retryOn`)
- **Circuit breaking** via `DestinationRule` (`outlierDetection`)
- **Request-level observability** (L7 metrics, distributed tracing headers)
- **Traffic management** (canary, blue-green, fault injection)

### What Istio Does NOT Do

- **Does NOT help with kubectl port-forward** — port-forward creates a direct TCP tunnel
  from host to pod, bypassing the pod's iptables rules. The connection terminates at
  kubelet, not at the Envoy sidecar.
- **Does NOT help with SSH tunnels** — SSH tunnels operate at the transport layer between
  host and K8s API server. Mesh traffic policies don't apply.
- **Does NOT replace OTel/Jaeger/Prometheus** — Istio generates its own L7 telemetry but
  doesn't replace application-level OTel instrumentation. It adds a separate telemetry
  plane that must be reconciled.
- **Does NOT help with Kind-specific issues** — Docker networking, NodePort instability,
  and container DNS are outside mesh scope.

### Resource Overhead

| Component | CPU | Memory | Notes |
|-----------|-----|--------|-------|
| Istiod (control plane) | 1 vCPU | 1.5 GB | Minimum for stable operation |
| Envoy sidecar (per pod) | 0.1-0.2 vCPU | 40-60 MB | ~15 pods in floe = 1.5-3 vCPU total |
| **Total** | **2.5-4 vCPU** | **2.1-2.4 GB** | Significant for dev Kind cluster |

### Kind Support

- Istio on Kind is supported but fragile
- Ambient mode (sidecar-less) has known macOS CNI bugs (`istio/istio#49057`)
- `istioctl install --set profile=demo` works but doubles pod count
- Gateway API CRDs must be installed manually before `istioctl install`

### Verdict: NOT RECOMMENDED for floe's current problem

Istio addresses service-to-service stability, but floe's stability problem is
host-to-cluster connectivity. The resource overhead (2.5-4 vCPU + 2+ GB) would strain
dev Kind clusters. The in-cluster test runner eliminates the problem Istio can't touch.

---

## Track 2: Alternative Service Meshes

### Linkerd

- **Lighter weight** than Istio: control plane ~200MB RAM, proxies ~10MB each (Rust-based)
- **Simpler** operational model: no Envoy, purpose-built proxy (linkerd2-proxy)
- **Same limitation**: does not help with port-forward/SSH tunnel stability
- **Automatic retries**: yes, via `ServiceProfile` retry annotations
- **mTLS**: automatic, zero-config
- **Resource overhead**: ~0.5-1 vCPU + 0.5 GB total for floe's scale
- **Kind support**: well-tested, `linkerd install | kubectl apply -f -`
- **CNCF graduated** project, active maintenance

### Cilium Service Mesh

- **eBPF-based**: no sidecar proxies, kernel-level networking
- **Lowest overhead**: no per-pod proxy, uses eBPF programs in kernel
- **Same limitation**: does not help with port-forward/SSH tunnel stability
- **L7 policies**: supported via Envoy proxy (optional, not per-pod)
- **Kind support**: requires `disableDefaultCNI: true` in Kind config, replaces default CNI
- **Complexity**: replaces the entire CNI stack, not just a mesh overlay
- **Risk**: replacing Kind's default CNI (kindnet) adds a significant failure surface

### Comparison

| Factor | Istio | Linkerd | Cilium |
|--------|-------|---------|--------|
| Solves port-forward issue | No | No | No |
| Resource overhead (floe) | 2.5-4 vCPU / 2+ GB | 0.5-1 vCPU / 0.5 GB | ~0.3 vCPU / 0.2 GB |
| Operational complexity | High | Medium | High (CNI replacement) |
| Automatic retries | Yes | Yes | Limited |
| mTLS | Yes | Yes | Yes |
| Kind stability | Fragile | Good | Requires CNI replacement |
| CNCF status | Graduated | Graduated | Graduated |

---

## Track 3: Stability Code Audit

floe has approximately **1,560 lines** of infrastructure stability/wrapper code:

| Category | Lines | Files | Mesh Eliminable? |
|----------|-------|-------|-------------------|
| Port-forward management | ~190 | `testing/ci/test-e2e.sh` | **No** — mesh doesn't govern this |
| SSH tunnel management | ~80 | `scripts/devpod-tunnels.sh` | **No** — mesh doesn't govern this |
| Service connectivity fixtures | ~210 | `testing/fixtures/services.py` | Partial — retry logic could be replaced |
| K8s/Helm recovery | ~270 | `tests/e2e/conftest.py` | Partial — Helm rollback still needed |
| E2E test fixtures | ~250 | `tests/e2e/conftest.py` | **No** — test orchestration logic |
| App-level retry decorators | ~280 | Various | Yes — mesh retries replace app retries |
| Network policies | ~180 | Helm templates | Partial — mesh policies could replace |

**Mesh-eliminable code**: ~350-500 lines (22-32%) — primarily app-level retry decorators
and some network policy definitions.

**NOT mesh-eliminable**: ~1,060-1,210 lines (68-78%) — port-forward/tunnel management,
test orchestration, Helm recovery, and service connectivity abstraction.

### Key Insight

The **in-cluster test runner** eliminates ~540 lines (port-forward + SSH tunnel + most
service connectivity code) — MORE than a service mesh would, and without the resource
overhead or operational complexity.

---

## Track 4: What Other Projects Do

### Dagster (dagster-io/dagster)

- Tests run **in-cluster** via Kubernetes Jobs for integration/E2E
- Uses `pytest-xdist` for parallel execution
- No service mesh in test infrastructure
- Service discovery via Kubernetes DNS (no port-forwards for test traffic)

### Airflow (apache/airflow)

- KubernetesExecutor tests use **in-cluster** test pods
- `breeze` CLI manages test environments
- No service mesh for testing
- Minikube/Kind with direct K8s DNS resolution

### dbt-core

- Does not test against K8s infrastructure
- Database adapters tested against real databases via direct connections
- CI uses GitHub Actions with service containers

### Common Pattern

No major data infrastructure project uses a service mesh for test stability.
The universal pattern is: **run tests where the services are** (in-cluster), not
bridge the gap with network proxies.

---

## Recommendations

### Do NOT adopt now

1. **Istio** — wrong tool for the problem, excessive resource overhead
2. **Cilium** — CNI replacement too risky for dev clusters, same limitation
3. **Any mesh** — none solve host-to-cluster connectivity

### Consider for later (post-production)

1. **Linkerd** — if service-to-service retry/mTLS becomes a production need,
   Linkerd is the lightest option. Evaluate when floe moves beyond dev/demo.
2. **Cilium** — if network policy management becomes complex in production,
   Cilium's eBPF approach avoids sidecar overhead.

### Do now (highest impact)

1. **Complete in-cluster test runner** — eliminates 45+ infrastructure failures
   and ~540 lines of stability code. Already 90% built.
2. **Fix root conftest hardcoded endpoints** — unblocks 12+ compilation tests.
   Two-line change.
3. **Profile isolation fix** — 3 test failures from profile mutation.

---

## Open Questions

| Question | Status | Impact |
|----------|--------|--------|
| Would Linkerd's retry policies reduce Dagster<->Polaris flakiness? | DEFERRED | Low — in-cluster eliminates the transport problem |
| Could Cilium replace custom NetworkPolicy templates? | DEFERRED | Medium — relevant for production, not dev |
| Is the ~280 lines of app-level retry code still needed after in-cluster? | TO VERIFY | Some retries are for real transient failures, not transport |

---

## Sources

- Istio documentation: https://istio.io/latest/docs/
- Istio Kind setup: https://istio.io/latest/docs/setup/platform-setup/kind/
- Linkerd documentation: https://linkerd.io/2/overview/
- Cilium documentation: https://docs.cilium.io/
- kubectl port-forward source: bypasses pod iptables (confirmed via K8s source)
- Dagster CI: https://github.com/dagster-io/dagster (`.github/workflows/`)
- Airflow CI: https://github.com/apache/airflow (`breeze` documentation)

# Research Brief: E2E CI Resilience — kubefwd, In-Cluster Testing, and Infrastructure Hardening

**Topic**: kubefwd, in-cluster test runner patterns, and CI resilience for K8s E2E tests
**Date**: 2026-03-29
**Confidence**: HIGH (official docs, multiple corroborating sources, codebase evidence)
**Tracks**: 4
**Depends on**: `tunnel-stability-20260329.md` (SSH tunnel root cause analysis)

---

## Track 1: kubefwd as kubectl port-forward Replacement

### How It Works

kubefwd discovers all Services in target namespace(s), assigns each a unique `127.x.x.x` loopback IP, creates loopback aliases (`ifconfig lo0 alias`), writes `/etc/hosts` entries mapping service DNS names to those IPs, then establishes port-forwards to the first matching pod per service via the K8s API.

**Auto-reconnect**: Uses K8s Informers for pod lifecycle events (restarts, rollouts) + TCP connection monitoring with exponential backoff for network drops. This is the key differentiator from `kubectl port-forward`.

### Version & Health

- **Latest**: v1.25.12 (2026-02-10), 6 releases in 6 weeks
- **Stars**: 4,100 | **Open issues**: 1 | **License**: Apache-2.0
- **Compliance**: OpenSSF Scorecard, SLSA Level 3
- Active maintainer (Craig Johnston / txn2)

### CI Suitability

| Factor | Assessment |
|--------|-----------|
| Headless mode | Yes — REST API mode (`--api` flag) for programmatic control |
| Docker image | `txn2/kubefwd` (Alpine-based), requires `--privileged` |
| sudo required | Yes — `/etc/hosts` writes + loopback aliases |
| GitHub Actions | `sudo kubefwd svc -n floe-test` works on ubuntu-latest |
| macOS Docker | Containers can't access host `127.x.x.x` — need shared network namespace |

### Known Limitations

1. **`/etc/hosts` cleanup on crash** (issue #5) — not reliably restored after SIGKILL
2. **macOS inetutils conflict** (issue #77) — Homebrew `inetutils` shadows BSD `ifconfig`
3. **Single-pod binding** — forwards to first matching pod, not load-balanced
4. **Docker Desktop macOS** — VM boundary isolates loopback namespace from containers

### Relevance to floe

kubefwd would replace the 9 individual `kubectl port-forward` processes in `test-e2e.sh` with a single command: `sudo kubefwd svc -n floe-test`. Auto-reconnect eliminates the zombie port-forward problem. The `ServiceEndpoint` abstraction already supports custom hosts, so no test code changes needed.

**However**: The SSH tunnel to port 26443 (K8s API) is a separate concern — kubefwd uses the K8s API and would also die if that tunnel drops. kubefwd solves port-forward flakiness but not the upstream tunnel problem.

Sources: [kubefwd GitHub](https://github.com/txn2/kubefwd), [imti.co/kubefwd-2026](https://imti.co/kubefwd-2026/)

---

## Track 2: In-Cluster Test Runner Pattern

### Two Variants

**Variant A — Host-based (current floe pattern)**: pytest runs on host/CI runner, uses port-forward to reach services. This is what Dagster, Airflow, and most Python projects do.

**Variant B — True in-cluster**: pytest runs inside a K8s pod. Services reached via ClusterIP DNS (`svc.namespace.svc.cluster.local`). No port-forward needed. Result extraction via `kubectl logs` or PVC mount.

### floe's Current Readiness for Variant B

**Already exists**:
- `testing/Dockerfile` — production-ready test image (Python 3.11-slim, uv, kubectl, dbt)
- `testing/k8s/jobs/test-runner.yaml` — 3 Job definitions (general, unit, integration)
- `ServiceEndpoint` abstraction — auto-detects K8s DNS vs localhost via `INTEGRATION_TEST_HOST=k8s`
- Integration job already sets `INTEGRATION_TEST_HOST=k8s` for DNS resolution

**Blockers (2 lines)**:
- `tests/e2e/conftest.py:974` hardcodes `"http://localhost:4317"` for OTel
- `tests/e2e/conftest.py:977` hardcodes `"http://localhost:5100/api/v1/lineage"` for OpenLineage
- These must use `ServiceEndpoint` or env var fallback for in-cluster to work

### How Major Projects Do It

| Project | Pattern | Port-forward? |
|---------|---------|--------------|
| **Dagster** | Host-based, Kind cluster, `--kind-cluster` flag to reuse | Yes |
| **Airflow** | Host-based (Breeze env), exported KUBECONFIG | Yes |
| **Kubeflow** | In-cluster (Variant B), Argo Workflows + NFS + GCS upload | No |
| **Linkerd** | Per-PR ephemeral Kind clusters on GHA, 8 parallel | Minimal |

### Tradeoffs

| Factor | Host-based (Variant A) | In-cluster (Variant B) |
|--------|----------------------|----------------------|
| Port-forward needed | Yes (flaky) | No (DNS direct) |
| Build cycle | No image rebuild | Rebuild + `kind load` per change |
| Debugging | Local IDE works | `kubectl logs` only |
| Environment parity | Port-forward adds latency/instability | True prod-equivalent network |
| Result collection | Trivial (local process) | `kubectl logs` or PVC extraction |
| Current floe effort | Maintain current infra | Fix 2 conftest lines + build flow |

### pytest-kubernetes (actively maintained alternative)

- `Blueshoe/pytest-kubernetes` v0.7.2 (2025-10-23) — supports `--k8s-kubeconfig-override` for existing clusters
- Provides `k8s` fixture with auto-provider detection (kind, k3d, minikube)
- More actively maintained than pytest-kind (stale since 2022) or kubetest (stale since 2021)

Sources: [kubetest](https://github.com/vapor-ware/kubetest), [pytest-kind](https://codeberg.org/hjacobs/pytest-kind), [pytest-kubernetes](https://github.com/Blueshoe/pytest-kubernetes)

---

## Track 3: CI Resilience Patterns

### 3.1 pytest-rerunfailures (recommended for infra retries)

**Version**: 16.1 (2025-10-10), Python 3.10+, pytest 8.0+

Key capability: **selective retry by exception type**
```bash
# Retry infrastructure failures but NOT assertion failures
pytest --reruns 3 --rerun-except AssertionError
```

Per-test decorator:
```python
@pytest.mark.flaky(
    reruns=3,
    reruns_delay=2,
    only_rerun=["ConnectionError", "TimeoutError", "PollingTimeoutError"],
    rerun_except="AssertionError",
)
```

**`--fail-on-flaky`** (added 15.0): Returns non-zero if any test needed reruns — surfaces infrastructure instability even when tests eventually pass.

Sources: [pytest-rerunfailures GitHub](https://github.com/pytest-dev/pytest-rerunfailures), [docs](https://pytest-rerunfailures.readthedocs.io/latest/)

### 3.2 Smoke Test Gate Pattern

```python
@pytest.fixture(scope="session", autouse=True)
def infrastructure_smoke_check():
    try:
        httpx.get("http://localhost:8080/health", timeout=5).raise_for_status()
    except Exception as e:
        pytest.exit(reason=f"Infrastructure not ready: {e}", returncode=3)
```

`pytest.exit()` aborts the entire session immediately — prevents 72 ERRORs when infrastructure is dead. floe's `conftest.py` already has test reordering for destructive tests but no smoke gate.

### 3.3 Port-Forward Watchdog (for host-based testing)

```bash
# Background health-check + restart loop
port_forward_watchdog() {
    local svc=$1 local_port=$2 remote_port=$3
    while true; do
        if ! curl -sf "http://localhost:${local_port}/health" >/dev/null 2>&1; then
            pkill -f "port-forward.*${local_port}" || true
            sleep 1
            kubectl port-forward "svc/${svc}" "${local_port}:${remote_port}" -n floe-test &
            echo "Restarted port-forward for ${svc}" >&2
        fi
        sleep 30
    done &
}
```

### 3.4 Connection Resilience in Fixtures

floe already has strong retry patterns:
- `floe_catalog_polaris/retry.py` — exponential backoff with tenacity
- `floe_core/oci/resilience.py` — `RetryPolicy` + `CircuitBreaker`
- `testing/fixtures/polling.py` — `wait_for_condition()`, `wait_for_service()`

**Gap**: These are used within individual tests but not at the fixture level for service connections. A session-scoped fixture that retries service connections on startup would be more resilient.

### 3.5 GitHub Actions + Kind (for CI)

**helm/kind-action v1.14.0** (2026-02-17):
- Kind 0.31.0, kubectl 1.35.0
- No SSH tunnel needed — localhost ports directly accessible on GHA runner
- `registry: true` enables local Docker registry
- Works with floe's existing `kind-config.yaml`

On GHA runners, port-forward is more stable because there's no SSH tunnel layer — kubectl talks directly to the Kind cluster's API server on localhost.

Sources: [helm/kind-action](https://github.com/helm/kind-action), [Linkerd CI on GHA](https://www.buoyant.io/blog/linkerds-ci-kubernetes-in-docker-github-actions)

---

## Track 4: floe-Specific Infrastructure Assessment

### What's Already Ready

| Component | Status | Notes |
|-----------|--------|-------|
| `ServiceEndpoint` abstraction | Ready | Auto-detects K8s DNS vs localhost |
| `INTEGRATION_TEST_HOST=k8s` env var | Ready | Switches all service resolution |
| Test container image | Ready | `testing/Dockerfile` with uv, kubectl, dbt |
| In-cluster Job definitions | Ready | 3 jobs in `testing/k8s/jobs/test-runner.yaml` |
| Retry/polling utilities | Ready | tenacity + custom `PollingConfig` |
| Kind NodePort config | Ready | 15+ services mapped |
| Test reordering | Ready | Destructive tests moved to end |

### What Needs Fixing

| Issue | Effort | Impact |
|-------|--------|--------|
| Conftest OTel hardcoded `localhost:4317` | 1 line | Blocks in-cluster OTel testing |
| Conftest OpenLineage hardcoded `localhost:5100` | 1 line | Blocks in-cluster lineage testing |
| No SSH keepalive in tunnel scripts | ~10 lines | Root cause of cascade failures |
| No port-forward health monitoring | ~20 lines | Silent zombie forwards |
| No smoke gate fixture | ~10 lines | 72 ERRORs when infra dies vs 1 clean abort |
| No pytest-rerunfailures for infra errors | Config change | Retry connection failures automatically |

---

## Synthesis: Recommended Approach by Scenario

### Scenario A: DevPod/Hetzner (current remote setup)

**Minimum fix** (P0, ship this week):
1. Add SSH keepalive to tunnel scripts
2. Add port-forward watchdog to `test-e2e.sh`
3. Add smoke gate fixture to `conftest.py`
4. Add `pytest-rerunfailures --reruns 2 --rerun-except AssertionError`

**Enhancement** (P1):
5. Replace 9x `kubectl port-forward` with `kubefwd svc -n floe-test`
6. Fix 2 hardcoded localhost lines in conftest

### Scenario B: GitHub Actions CI (future)

**No SSH tunnel needed** — Kind runs directly on GHA runner. Port-forward still needed for Dagster but more stable without SSH layer. Use `helm/kind-action@v1.14.0` + existing `kind-config.yaml`.

### Scenario C: Full in-cluster testing (long-term)

**No port-forward at all** — tests run as K8s Job inside the cluster. Infrastructure already exists (`testing/Dockerfile`, job manifests, `ServiceEndpoint` with DNS mode). Only blockers are the 2 hardcoded localhost lines. Result extraction via `kubectl logs` of the test pod.

---

## Open Questions

1. Should DevPod tests use kubefwd (easier, auto-reconnect) or go straight to in-cluster (eliminates all tunneling)?
2. For GHA CI, is Dagster's missing NodePort worth working around (port-forward watchdog) or should we contribute upstream?
3. What's the acceptable retry count for infrastructure failures? (Suggest 2 retries for connection errors, 0 for assertions)
4. Should the smoke gate abort the entire suite or just mark tests as ERROR?

---

## Sources

All sources cited inline. Key references:
- [kubefwd](https://github.com/txn2/kubefwd) — managed port forwarding with auto-reconnect
- [pytest-rerunfailures](https://github.com/pytest-dev/pytest-rerunfailures) — selective retry by exception type
- [helm/kind-action](https://github.com/helm/kind-action) — GitHub Actions Kind setup
- [pytest-kubernetes](https://github.com/Blueshoe/pytest-kubernetes) — actively maintained K8s test fixtures
- [Linkerd CI on GHA](https://www.buoyant.io/blog/linkerds-ci-kubernetes-in-docker-github-actions) — per-PR ephemeral clusters
- [Dagster K8s testing](https://docs.dagster.io/integrations/libraries/k8s/dagster-k8s) — host-based with Kind
- [Kubeflow testing](https://github.com/kubeflow/testing) — in-cluster with Argo + NFS

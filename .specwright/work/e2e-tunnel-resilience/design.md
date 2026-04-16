# Design: E2E Tunnel Resilience

## Problem

The E2E test suite (48 min, 230 tests) runs against a Kind cluster inside a DevPod workspace on Hetzner via two layers of SSH tunneling. During the last run, tunnels died at ~16% (minute 8), causing 72 ERRORs and 18 cascading FAILs. Root cause chain:

```
SSH tunnel (port 26443) has no keepalive → idle timeout kills tunnel
  → kubectl port-forwards lose API server → all 9 service ports die
    → 72 ERRORs + 18 cascading FAILs
```

## Approach: Layered Resilience (3 Layers)

Rather than replacing the tunneling architecture (kubefwd or in-cluster runner), this design adds resilience at each failure point. This is the simplest approach that addresses the root cause while leaving the path open for future architecture changes.

### Layer 1: SSH Keepalive (prevent tunnel death)

**What**: Add `ServerAliveInterval=30` and `ServerAliveCountMax=3` to all SSH tunnel commands. Add stdin redirect (`< /dev/null`) to the kubeconfig sync tunnel.

**Where**:
- `scripts/devpod-sync-kubeconfig.sh` — K8s API tunnel (port 26443)
- `scripts/devpod-tunnels.sh` — service tunnels (9 ports)

**Why**: SSH keepalive sends application-layer probes every 30 seconds. If 3 consecutive probes fail (90 seconds), SSH terminates cleanly instead of hanging. This prevents the silent tunnel death that causes zombie port-forwards. The `< /dev/null` stdin redirect prevents the `nohup` process from hanging waiting for input.

**Risk**: LOW — SSH keepalive is a standard, well-understood mechanism. No behavioral change when the tunnel is healthy.

### Layer 2: Port-Forward Watchdog (detect and recover from dead forwards)

**What**: Add a background health-check loop to `testing/ci/test-e2e.sh` that monitors port-forward liveness and restarts dead forwards.

**How**: A watchdog function runs every 30 seconds, checking TCP connectivity to each forwarded port. If a port is dead, the watchdog kills the old process and starts a new port-forward. The watchdog runs as a background process and is cleaned up with the existing trap handler.

**Where**: `testing/ci/test-e2e.sh` — new `start_port_forward_watchdog()` function

**Why**: Even with SSH keepalive, individual port-forwards can die from kubelet idle timeout (4h default) or connection interruption (kubernetes/kubernetes#78446). The watchdog provides defense-in-depth.

**Risk**: LOW — the watchdog only acts when TCP connectivity fails. It cannot cause a working port-forward to die. If the K8s API tunnel itself is dead, the watchdog will fail to restart forwards (expected — the SSH keepalive layer should prevent this).

### Layer 3: Test Infrastructure Resilience (graceful degradation)

Three changes to the test infrastructure:

#### 3a: Smoke Gate Fixture

**What**: Add a session-scoped autouse fixture that checks core infrastructure (Dagster, Polaris, MinIO) before any test runs. If infrastructure is unreachable, `pytest.exit()` aborts the session with a clear message instead of producing 72 individual ERRORs.

**Where**: `tests/e2e/conftest.py` — new `infrastructure_smoke_check` fixture

**Why**: When infrastructure dies, every subsequent test produces an identical ERROR. A smoke gate collapses 72 ERRORs into 1 clear abort message, saving CI time and making the root cause immediately obvious.

#### 3b: pytest-rerunfailures for Infrastructure Errors

**What**: Add `pytest-rerunfailures` dependency and configure with `--only-rerun` whitelist of infrastructure exception types:
```
--reruns 2 --reruns-delay 5
--only-rerun "ConnectionError"
--only-rerun "ConnectError"
--only-rerun "TimeoutError"
--only-rerun "PollingTimeoutError"
--only-rerun "ConnectionRefusedError"
```

This uses a **whitelist** approach (only retry known infrastructure exceptions) instead of a **blacklist** (`--rerun-except AssertionError`). The whitelist is safer because:
- `assert response.status_code == 200` raises `AssertionError` even when the root cause is a dead tunnel — a blacklist would NOT retry this
- `pytest.fail("Service not accessible")` raises `Failed` (subclass of `AssertionError`) — a blacklist would NOT retry this
- The whitelist only retries exceptions that are unambiguously infrastructure-related

Add `--fail-on-flaky` to surface instability even when tests eventually pass.

**Where**: `pyproject.toml` (dependency + pytest config)

**Why**: Infrastructure flakiness (port-forward blip, brief service restart) should be retried. The whitelist ensures only unambiguous connection errors trigger retry — never masking real test failures.

#### 3c: Remove Hardcoded localhost in Telemetry Seeding

**What**: Replace 2 hardcoded `localhost` references in conftest with `ServiceEndpoint`-based resolution:
- `os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4317"` → use `ServiceEndpoint("otel-collector")`
- `os.environ["OPENLINEAGE_URL"] = "http://localhost:5100/api/v1/lineage"` → use `ServiceEndpoint("marquez")`

**Where**: `tests/e2e/conftest.py` lines 974, 977

**Why**: These hardcoded values block future in-cluster test execution. The `ServiceEndpoint` abstraction already handles both localhost and K8s DNS resolution. This change has zero impact on current behavior (both resolve to the same localhost endpoints) but unblocks Variant B in-cluster testing for the future.

## What This Design Does NOT Do

- Does NOT replace kubectl port-forward with kubefwd (future work)
- Does NOT implement in-cluster test runner (future work, now unblocked by 3c)
- Does NOT change the SSH tunnel architecture (DevPod → Hetzner)
- Does NOT modify test assertions or weaken tests
- Does NOT add new dependencies beyond pytest-rerunfailures
- Does NOT change Kind cluster config or Helm charts

## Blast Radius

| Module/File | Change | Failure Scope |
|-------------|--------|--------------|
| `scripts/devpod-sync-kubeconfig.sh` | Add SSH options | Local — only affects DevPod tunnel setup |
| `scripts/devpod-tunnels.sh` | Add SSH options | Local — only affects service tunnels |
| `testing/ci/test-e2e.sh` | Add watchdog function | Local — watchdog is additive, cleanup via existing trap |
| `tests/e2e/conftest.py` | Add smoke gate, fix localhost | Adjacent — affects all E2E test sessions |
| `pyproject.toml` | Add pytest-rerunfailures dep | Adjacent — affects test execution behavior |

**Not changed**: Production code, Helm charts, Kind config, Dockerfile, test assertions, service fixtures.

## Integration Points

1. **SSH keepalive ↔ DevPod SSH**: DevPod uses system OpenSSH when available (default on macOS). `-o ServerAliveInterval=30` is a standard OpenSSH option. If DevPod uses its Go SSH client (`USE_BUILTIN_SSH=true`), this option may be ignored — noted as assumption A1.

2. **Watchdog ↔ test-e2e.sh cleanup**: The watchdog PID must be added to the existing `cleanup_port_forwards()` function so it's killed on test exit. The watchdog must not interfere with the existing `port_already_available()` checks.

3. **Smoke gate ↔ E2E conftest**: The fixture is session-scoped and autouse, so it runs before all tests. It checks the same services that `test-e2e.sh` validates at startup, but catches mid-run infrastructure death. Uses `pytest.exit()` not `pytest.fail()` — aborts session cleanly.

4. **pytest-rerunfailures ↔ pytest-timeout**: Both are pytest plugins. They are compatible — rerunfailures retries after timeout failures. The `--reruns-delay` is set to 5s to allow port-forward recovery.

5. **ServiceEndpoint ↔ conftest telemetry**: `ServiceEndpoint` is already imported and used extensively in conftest. The 2-line change uses the existing abstraction.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| SSH keepalive not respected by DevPod Go client | LOW | MEDIUM | Check `USE_BUILTIN_SSH` setting; test empirically |
| Watchdog restart storm | LOW | LOW | 30s check interval prevents rapid restarts |
| Smoke gate false-positives | LOW | LOW | Only checks 3 core services with 5s timeout each |
| pytest-rerunfailures masks real failures | LOW | LOW | `--only-rerun` whitelist (5 infra exceptions only) + `--fail-on-flaky` flag |
| ServiceEndpoint resolves differently than hardcoded | LOW | LOW | Both resolve to localhost in current setup; verify empirically |

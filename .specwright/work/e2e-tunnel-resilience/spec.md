# Spec: E2E Tunnel Resilience

## Acceptance Criteria

### T1: SSH Keepalive on API Tunnel

**AC-1.1**: `scripts/devpod-sync-kubeconfig.sh` passes `-o ServerAliveInterval=30 -o ServerAliveCountMax=3` to the `devpod ssh` command for the K8s API tunnel.

**AC-1.2**: The `nohup devpod ssh` command redirects stdin from `/dev/null` (`< /dev/null`) to prevent the background process from hanging on stdin.

**AC-1.3**: Existing tunnel behavior is unchanged — the tunnel still forwards `LOCAL_API_PORT` to `TUNNEL_TARGET:REMOTE_API_PORT` and logs to `devpod-ssh.log`.

### T2: SSH Keepalive on Service Tunnels

**AC-2.1**: `scripts/devpod-tunnels.sh` includes `-o ServerAliveInterval=30 -o ServerAliveCountMax=3` in the SSH command arguments for service tunnels.

**AC-2.2**: The SSH command continues to forward all ports in `PORTS` array and skip ports already in use.

### T3: Port-Forward Watchdog

**AC-3.1**: `testing/ci/test-e2e.sh` contains a `start_port_forward_watchdog()` function that runs a background health-check loop.

**AC-3.2**: The watchdog checks TCP connectivity to each forwarded port every 30 seconds using `(echo >/dev/tcp/localhost/PORT) 2>/dev/null`.

**AC-3.3**: When a port is dead, the watchdog kills the old `kubectl port-forward` process and starts a new one for the same service mapping.

**AC-3.4**: The watchdog PID is tracked and killed in the existing `cleanup_port_forwards()` function on script exit.

**AC-3.5**: The watchdog does NOT interfere with ports that were already available via NodePort (skipped during setup). It only monitors ports with active `kubectl port-forward` processes.

**AC-3.6**: The watchdog logs each restart event to stderr (per P56: best-effort cleanup MUST log).

### T4: Smoke Gate Fixture

**AC-4.1**: `tests/e2e/conftest.py` contains a session-scoped autouse fixture `infrastructure_smoke_check` that runs before any test.

**AC-4.2**: The fixture checks TCP connectivity to Dagster, Polaris, and MinIO with a 5-second timeout per service.

**AC-4.3**: If ANY of the 3 core services is unreachable, the fixture calls `pytest.exit("Infrastructure unreachable: {details}", returncode=3)`.

**AC-4.4**: If all services are reachable, the fixture completes silently (no output on success).

### T5: pytest-rerunfailures Configuration

**AC-5.1**: `pyproject.toml` includes `pytest-rerunfailures>=16.1` in the workspace dependencies.

**AC-5.2**: `tests/e2e/conftest.py` configures pytest-rerunfailures programmatically (not in global `addopts`) so reruns only apply to E2E tests, not unit/contract/integration tests. Configuration: `--reruns 2 --reruns-delay 5 --fail-on-flaky`.

**AC-5.3**: The E2E rerun configuration includes `--only-rerun` for exactly these exception types: `ConnectionError`, `ConnectError`, `TimeoutError`, `PollingTimeoutError`, `ConnectionRefusedError`.

### T6: ServiceEndpoint for Telemetry Endpoints

**AC-6.1**: `tests/e2e/conftest.py` replaces `"http://localhost:4317"` with a `ServiceEndpoint("otel-collector-grpc")` URL construction.

**AC-6.2**: `tests/e2e/conftest.py` replaces `"http://localhost:5100/api/v1/lineage"` with a `ServiceEndpoint("marquez")` URL construction that appends `/api/v1/lineage`.

**AC-6.3**: Both replacements produce the same URL as the hardcoded values when `INTEGRATION_TEST_HOST` is not set to `k8s` (default localhost behavior preserved).

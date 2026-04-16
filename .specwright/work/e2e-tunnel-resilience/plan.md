# Plan: E2E Tunnel Resilience

## Task Order

Tasks are ordered by dependency: SSH keepalive first (foundation), then watchdog (depends on port-forward infrastructure), then test-level changes (independent of each other).

## Task Breakdown

### T1: SSH Keepalive on API Tunnel

**File changes**:
- `scripts/devpod-sync-kubeconfig.sh` (lines 111-114)

**What to change**:
- Add SSH options to the `devpod ssh` command: `-o ServerAliveInterval=30 -o ServerAliveCountMax=3`
- Add `< /dev/null` stdin redirect to the `nohup` command

**Testing**: Shell script — verify by inspection. No automated test (shell scripts are validated by E2E run).

### T2: SSH Keepalive on Service Tunnels

**File changes**:
- `scripts/devpod-tunnels.sh` (lines 93, 122)

**What to change**:
- Add `-o ServerAliveInterval=30 -o ServerAliveCountMax=3` to the `SSH_ARGS` array initialization

**Testing**: Shell script — verify by inspection. No automated test.

### T3: Port-Forward Watchdog

**File changes**:
- `testing/ci/test-e2e.sh`

**What to change**:
- Add `start_port_forward_watchdog()` function after port-forward setup
- Function tracks which ports have active `kubectl port-forward` processes (by PID variable name)
- Background loop: every 30s, check each tracked port via TCP, restart dead forwards
- Store watchdog PID in `WATCHDOG_PID` variable
- Add `WATCHDOG_PID` cleanup to `cleanup_port_forwards()`
- Call `start_port_forward_watchdog` after all port-forwards are established

**Function signature**:
```bash
start_port_forward_watchdog() {
    # Runs in background, checks port health every 30s
    # Restarts dead kubectl port-forwards
}
```

**Port-to-service mapping** (from existing code):
| Variable | Port | Service | K8s target |
|----------|------|---------|------------|
| `DAGSTER_PF_PID` | `$DAGSTER_HOST_PORT` | `svc/floe-platform-dagster-webserver` | `3000` |
| `POLARIS_PF_PID` | `8181` | `svc/floe-platform-polaris` | `8181 8182` |
| `MINIO_API_PF_PID` | `9000` | `svc/floe-platform-minio` | `9000` |
| `MINIO_UI_PF_PID` | `9001` | `svc/floe-platform-minio` | `9001` |
| `OTEL_PF_PID` | `4317` | `svc/floe-platform-otel` | `4317` |
| `MARQUEZ_PF_PID` | `$MARQUEZ_HOST_PORT` | `svc/floe-platform-marquez` | `5000` |
| `JAEGER_PF_PID` | `$JAEGER_QUERY_PORT` | `svc/floe-platform-jaeger-query` | `16686` |
| `POSTGRES_PF_PID` | `5432` | `svc/floe-platform-postgresql` | `5432` |

**Testing**: Shell script — verify by inspection + E2E run.

### T4: Smoke Gate Fixture

**File changes**:
- `tests/e2e/conftest.py`

**What to change**:
- Add session-scoped autouse fixture `infrastructure_smoke_check`
- Check 3 core services: Dagster (`$DAGSTER_HOST_PORT` or 3100), Polaris (8181), MinIO (9000)
- Use socket connection with 5s timeout per service
- On failure: `pytest.exit(msg, returncode=3)`

**Fixture signature**:
```python
@pytest.fixture(scope="session", autouse=True)
def infrastructure_smoke_check() -> None:
    """Abort test session if core infrastructure is unreachable."""
```

**Testing**: Unit test not practical (fixture uses `pytest.exit`). Validated by E2E run.

### T5: pytest-rerunfailures Configuration

**File changes**:
- `pyproject.toml` (dependency only)
- `tests/e2e/conftest.py` (programmatic rerun config)

**What to change**:
- Add `"pytest-rerunfailures>=16.1"` to `[project] dependencies` in `pyproject.toml`
- In `tests/e2e/conftest.py`, add a `pytest_configure` hook (or `conftest_options` fixture) that programmatically adds rerun flags so they only apply to E2E tests:
  ```
  --reruns 2 --reruns-delay 5 --fail-on-flaky
  --only-rerun ConnectionError
  --only-rerun ConnectError
  --only-rerun TimeoutError
  --only-rerun PollingTimeoutError
  --only-rerun ConnectionRefusedError
  ```
- Do NOT add rerun flags to global `addopts` in `pyproject.toml`

**Testing**: Verify by `uv sync` + `uv run pytest tests/e2e/ --co` (collection succeeds with rerun plugin). Verify `uv run pytest tests/unit/ --co` does NOT show rerun plugin active.

### T6: ServiceEndpoint for Telemetry Endpoints

**File changes**:
- `tests/e2e/conftest.py` (lines 974, 977)

**What to change**:
- Line 974: Replace `"http://localhost:4317"` with `ServiceEndpoint("otel-collector-grpc").url`
  - Note: `ServiceEndpoint.url` returns `http://host:port` — matches required format
- Line 977: Replace `"http://localhost:5100/api/v1/lineage"` with `f"{ServiceEndpoint('marquez').url}/api/v1/lineage"`
  - Note: `ServiceEndpoint("marquez").url` returns `http://localhost:5100` — append path

**Testing**: Verify by E2E run. Both resolve to same localhost URLs in current setup.

## File Change Map

| File | Tasks | Lines Changed (est.) |
|------|-------|---------------------|
| `scripts/devpod-sync-kubeconfig.sh` | T1 | ~3 |
| `scripts/devpod-tunnels.sh` | T2 | ~2 |
| `testing/ci/test-e2e.sh` | T3 | ~40 |
| `tests/e2e/conftest.py` | T4, T5, T6 | ~30 |
| `pyproject.toml` | T5 | ~1 |

## Architecture Decisions

- **No unit tests for shell scripts**: T1-T3 modify bash scripts. Shell script testing frameworks (bats, shunit2) are not in the project's toolchain. These are validated by E2E execution.
- **Smoke gate uses raw socket, not httpx**: The fixture runs before any test infrastructure. Using `socket.connect_ex()` avoids importing test dependencies and is faster than HTTP health checks.
- **Watchdog uses associative array**: Maps port→PID for O(1) lookup during health checks.
- **Watchdog logs restarts to stderr**: Per P56, best-effort cleanup must log for CI debuggability.
- **Rerun config scoped to E2E**: `pytest_configure` hook in `tests/e2e/conftest.py` ensures reruns don't affect unit/contract/integration test runs.
- **Polaris split-port handling**: Watchdog must handle the case where 8181 is NodePort but 8182 needs port-forward — only monitor ports with actual PF processes.

## As-Built Notes

### Deviations from Plan

- **T3 watchdog implementation**: Used a flat array of `"LOCAL:REMOTE:SERVICE:PID_VAR"` entries instead of a bash associative array. Simpler and avoids bash 4+ requirement. The `register_port_forward()` function is called inline after each `kubectl port-forward` setup, building the array incrementally.
- **T5 rerun config**: Used `config.option.*` attributes directly instead of `config.addinivalue_line()` since `only_rerun` and `fail_on_flaky` are command-line options, not ini options. The `reruns` and `reruns_delay` ini options exist but setting via `config.option` is simpler and consistent.
- **T5 `--fail-on-flaky`**: Added via `config.option.fail_on_flaky = True` as designed.

### Actual File Changes

| File | Commit | Lines |
|------|--------|-------|
| `scripts/devpod-sync-kubeconfig.sh` | `19a2b67` | +4/-1 |
| `scripts/devpod-tunnels.sh` | `412f9b5` | +2/-1 |
| `testing/ci/test-e2e.sh` | `4ff4a5e` | +59 |
| `tests/e2e/conftest.py` | `d426832`, `4382c68`, `8289376` | +36, +15, +6/-3 |
| `pyproject.toml` + `uv.lock` | `4382c68` | +2 (pyproject) |

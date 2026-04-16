# Context: E2E Tunnel Resilience

## Research Briefs

- `.specwright/research/tunnel-stability-20260329.md` — SSH tunnel and port-forward root cause analysis
- `.specwright/research/e2e-ci-resilience-20260329.md` — kubefwd, in-cluster testing, CI resilience patterns

## Key File Paths

### Scripts to modify
- `scripts/devpod-sync-kubeconfig.sh` — K8s API SSH tunnel (lines 111-114: `nohup devpod ssh` command)
- `scripts/devpod-tunnels.sh` — Service SSH tunnels (lines 93-127: SSH command builder)
- `testing/ci/test-e2e.sh` — E2E test runner (lines 127-145: port-forward cleanup)

### Test infrastructure to modify
- `tests/e2e/conftest.py` — E2E conftest (lines 974, 977: hardcoded localhost)
- `pyproject.toml` — Test dependencies

### Reference files (read-only)
- `testing/fixtures/services.py` — `ServiceEndpoint` class, `get_effective_port()`, `SERVICE_DEFAULT_PORTS`
- `testing/fixtures/polling.py` — `wait_for_condition()`, `wait_for_service()`, `PollingTimeoutError`
- `testing/k8s/kind-config.yaml` — Kind cluster NodePort mappings
- `testing/k8s/jobs/test-runner.yaml` — In-cluster test Job definitions (future reference)
- `testing/Dockerfile` — Test container image (future reference)

## Root Cause Evidence

### devpod-ssh.log entries showing tunnel death
```
"listen tcp 127.0.0.1:26443: bind: address already in use"
"wait: remote command exited without exit status or exit signal"
"timeout waiting for instance connection"
```

### E2E test output showing cascade
```
28 failed, 130 passed, 1 xfailed, 26 warnings, 72 errors in 2884.50s (0:48:04)
```

Error pattern: 72 ERRORs all show `TCP connection to localhost:XXXX failed` or `PollingTimeoutError`.

## ServiceEndpoint Resolution

`ServiceEndpoint` in `testing/fixtures/services.py` auto-detects host:
1. `{SERVICE}_HOST` env var
2. `INTEGRATION_TEST_HOST` env var (can be `"k8s"` for DNS)
3. Auto-detection: tries K8s DNS, falls back to localhost

Port resolution:
1. `{SERVICE}_PORT` env var
2. `SERVICE_DEFAULT_PORTS` dict (otel-collector: 4317, marquez: 5100)

## Gotchas

1. **Dagster has no NodePort** — Dagster 1.12+ schema disallows it. Port-forward is mandatory for Dagster webserver.
2. **DevPod SSH may use Go client** — If `USE_BUILTIN_SSH=true`, standard SSH options like `ServerAliveInterval` won't work. Default is system OpenSSH when available (macOS has it).
3. **pytest-rerunfailures 16.0 broke pytest-xdist** — Use 16.1+ specifically.
4. **`pytest.exit()` vs `pytest.fail()`** — `exit()` aborts entire session; `fail()` marks one test as failed. Smoke gate needs `exit()`.
5. **Watchdog must not kill working forwards** — Only restart when TCP check fails, not on any other signal.
6. **nohup stdin** — `nohup ... &` without `< /dev/null` can cause SSH to hang. Must redirect stdin.

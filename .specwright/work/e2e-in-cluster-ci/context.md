# Context: In-Cluster E2E Test Execution

## Research Briefs Consumed

- `.specwright/research/e2e-ci-resilience-20260329.md` — kubefwd, in-cluster patterns, CI resilience
- `.specwright/research/tunnel-stability-20260329.md` — SSH tunnel root cause analysis

## Key Files

### Infrastructure (already exists)
- `testing/Dockerfile` — complete test image (Python 3.11, uv, kubectl, dbt)
- `testing/k8s/jobs/test-runner.yaml` — 3 existing Job definitions (general, unit, integration)
- `testing/ci/test-integration.sh` — builds image, loads to Kind, runs Job, streams logs
- `testing/ci/test-e2e.sh` — host-based runner with port-forward watchdog (545 lines)
- `testing/k8s/kind-config.yaml` — NodePort mappings, network config

### Service Resolution
- `testing/fixtures/services.py` — `ServiceEndpoint` class, `_get_effective_host()`, `SERVICE_DEFAULT_PORTS`
  - Lines 129-164: `_get_effective_host()` — precedence: `{SERVICE}_HOST` → `INTEGRATION_TEST_HOST` → auto-detect
  - Lines 36-51: Default ports dict
  - Lines 182-226: `ServiceEndpoint` dataclass with `host`, `port`, `url` properties

### E2E Test Code
- `tests/e2e/conftest.py` — smoke check fixture (lines 155-188), test reordering (lines 62-152)
- `tests/e2e/test_observability.py` — hardcoded localhost:4317 (lines 542, 1164), localhost:5100 (lines 167, 289, 723, 921)
- `tests/e2e/test_observability_roundtrip_e2e.py` — hardcoded localhost:4317 (line 180)
- `tests/e2e/test_platform_deployment_e2e.py` — hardcoded localhost:5100 (line 294)

### RBAC
- `charts/floe-platform/templates/role.yaml` — dagster Role (pods, jobs, configmaps, events, services, PVCs)
- `charts/floe-platform/templates/serviceaccount.yaml` — dagster SA
- `charts/floe-platform/templates/rolebinding.yaml` — dagster RoleBinding

### CI
- `.github/workflows/weekly.yml` — integration tests job (lines 45-97) using `test-integration.sh`
- `.github/workflows/ci.yml` — no E2E gate currently

## Gotchas

1. `kind load docker-image` does full tarball export/import — no layer dedup. 500MB+ test image.
2. `dagster` SA only has pod/job/configmap/event/service/PVC access — no secrets, no exec, no deployments.
3. `test_observability.py:542` intentionally sets `OTEL_EXPORTER_OTLP_ENDPOINT` env var — this is testing OTel config behavior, not a bug. Must use `ServiceEndpoint` for the URL value but keep the env var pattern.
4. `test_helm_workflow.py:509` has `localhost` in a regex pattern matching template output — not a connection, no change needed.
5. `test_promotion.py:67` uses `localhost:5000` for OCI registry — separate concern from K8s services.
6. `emptyDir` for `/artifacts` in existing Job (line 89-90) — unreliable for artifact extraction.

## Functional Localhost Changes Needed (5 total)

| File:Line | Current | Replacement |
|-----------|---------|-------------|
| `conftest.py:349` | `"http://localhost:3000/health"` | `f"{ServiceEndpoint('dagster-webserver').url}/health"` |
| `test_observability.py:542` | `"http://localhost:4317"` | `ServiceEndpoint("otel-collector-grpc").url` |
| `test_observability.py:1164` | `"http://localhost:4317"` | `ServiceEndpoint("otel-collector-grpc").url` |
| `test_observability_roundtrip_e2e.py:180` | `"http://localhost:4317"` | `ServiceEndpoint("otel-collector-grpc").url` |
| `test_platform_deployment_e2e.py:294` | `f"http://localhost:{marquez_port}"` | `ServiceEndpoint("marquez").url` |

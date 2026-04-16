# Design: Test Infrastructure Convergence

## Overview

Converge test and production infrastructure so they share the same Helm charts,
security posture, and networking model. The central change is making the in-cluster
test runner the default execution path, with baked-in observability for debugging.

## Approach

### Principle: Build on what exists

The in-cluster test runner infrastructure is ~90% built. The Dockerfile, Job manifests,
RBAC, secrets, and ServiceEndpoint wiring are complete and tested. This design focuses
on closing the gaps rather than rebuilding.

### Five work streams

#### 1. In-Cluster Runner as Default Path (DevPod-aware)

**Problem**: `make test-e2e` uses port-forwards. `make test-e2e-cluster` only works
with local Kind (via `kind load docker-image`).

**Solution**: Make the in-cluster runner work for both local Kind and remote DevPod:

- **Local Kind**: Keep `kind load docker-image` (fast, no registry needed).
- **DevPod/remote**: Use `docker save | ssh devpod | docker load` pipe, OR push to
  an in-cluster registry (one already exists: `testing/k8s/services/registry.yaml`).
- **CI**: Push to registry (standard pattern).

`make test-e2e` becomes the unified entrypoint that auto-detects environment:
- If `kind` is available locally and cluster exists → use `kind load docker-image`.
- If `DEVPOD_WORKSPACE` is set → use `docker save | ssh devpod | docker load` pipe
  (guaranteed to work — DevPod provides SSH access). Registry push is an optimization
  for later if the pipe is too slow.
- Otherwise → fail-fast with diagnostic: "No Kind cluster or DevPod workspace detected.
  Set up a cluster with `make kind-up` or start DevPod."

Registry push URL discovery (future optimization):
- Local Kind: `localhost:30500` (Kind maps NodePort directly).
- DevPod: requires SSH tunnel to NodePort (`ssh -L 30500:localhost:30500 devpod`).
- CI: registry URL from CI environment variable.

The host-based port-forward runner moves to `make test-e2e-host` (explicit opt-in,
documented as legacy/debugging path).

#### 2. Test Runner Observability (user's explicit request)

**Problem**: When tests fail in-cluster, the only output is raw pytest console logs
captured via `kubectl logs`. No structure, no correlation, no HTML reports.

**Solution**: Three layers of observability baked into the test runner:

**Layer A — Structured test output**:
- `pytest-html` for human-readable HTML reports (saved to PVC, extracted post-run).
- `pytest-json-report` for machine-parseable results.
- JUnit XML (already exists) for CI integration.
- All artifacts saved to `/artifacts/` volume mount (PVC already exists).

**Layer B — Structured logging from test code**:
- Test runner image already has `structlog` (via floe packages).
- Add `OTEL_EXPORTER_OTLP_ENDPOINT` env var pointing to in-cluster OTel collector.
- Tests that use `ensure_telemetry_initialized()` will emit traces to the collector.
- Traces are queryable in Jaeger after test run.

**Layer C — Log extraction on failure**:
- Extend `test-e2e-cluster.sh` to capture service pod logs on Job failure.
- Collect logs from all pods in the test namespace (last 100 lines each).
- Save to `test-artifacts/pod-logs/` directory alongside test results.
- Add `kubectl get events --sort-by='.lastTimestamp'` capture for K8s-level failures.

**Layer D — Pytest live-log forwarding**:
- Set `log_cli=true` and `log_cli_level=INFO` in pytest config for the in-cluster run.
- `kubectl logs -f` already streams — this makes the stream useful for real-time debugging.

#### 3. Security Hardening (PSS Restricted)

**Problem**: Base chart defines security contexts but subcharts use their own defaults.

**Solution**: Wire security contexts through subchart value mappings in `values.yaml`.

Each subchart has its own schema for security context keys. Verified via
`helm show values` for each:

| Subchart | Pod-level key | Container-level key | Notes |
|----------|--------------|---------------------|-------|
| `dagster` (webserver) | `dagsterWebserver.podSecurityContext` | `dagsterWebserver.securityContext` | Per-component |
| `dagster` (daemon) | `dagsterDaemon.podSecurityContext` | `dagsterDaemon.securityContext` | Per-component |
| `dagster` (run launcher) | `runLauncher.config.k8sRunLauncher.podSecurityContext` | `runLauncher.config.k8sRunLauncher.securityContext` | Nested under config |
| `dagster` (code server) | `dagsterUserDeployments.deployments[0].podSecurityContext` | `dagsterUserDeployments.deployments[0].securityContext` | Per-deployment |
| `jaeger` (all-in-one) | `allInOne.podSecurityContext` | `allInOne.securityContext` | Jaeger already sets runAsUser: 10001 |
| `opentelemetry-collector` | `podSecurityContext` | `securityContext` | Top-level |
| `minio` | `podSecurityContext.enabled: true` + subkeys | `containerSecurityContext.enabled: true` + subkeys | Bitnami schema (enabled flag) |

YAML anchors define the context once at the top of values.yaml and reference it
per-subchart with the correct key path:

```yaml
# Anchors (top of values.yaml)
podSecurityContext: &podSecCtx
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault

containerSecurityContext: &containerSecCtx
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
  capabilities:
    drop: ["ALL"]

# Subchart mappings (correct key paths)
dagster:
  dagsterWebserver:
    podSecurityContext: *podSecCtx
    securityContext: *containerSecCtx
  dagsterDaemon:
    podSecurityContext: *podSecCtx
    securityContext: *containerSecCtx

opentelemetry-collector:
  podSecurityContext: *podSecCtx
  securityContext: *containerSecCtx
```

Jaeger already runs as non-root (UID 10001) — only verify and lock down capabilities.
MinIO uses Bitnami schema with `enabled: true` + subkeys — needs explicit mapping.

**Validation**: Add a contract test that renders `helm template` and asserts every
pod spec contains `runAsNonRoot: true`. This catches silent value-key mismatches.

**Marquez exception**: Marquez runs as root (UID 0), upstream has no fix (GitHub #3060).

Options considered:
- (A) Custom Dockerfile with `USER 1000` — risks breaking Marquez internals.
- (B) Separate K8s namespace for Marquez with PSS `baseline` (not `restricted`).
- (C) Accept the gap, document it, revisit when upstream fixes.

**Recommendation**: Option (C) for now, with Option (B) as follow-up. PSS admission
is namespace-scoped only (no pod-level exemption in standard K8s PSA). Moving Marquez
to its own namespace requires additional networking (cross-namespace DNS) and RBAC.
This is a separate work unit, not part of the initial convergence. Document in AUDIT.md
as a known gap with the upstream issue reference.

#### 4. Destructive Test Isolation

**Problem**: Destructive tests (pod kill, helm upgrade) crash services that other tests
depend on, cascading failures.

**Solution** (already partially implemented):
- Separate Job manifest (`test-e2e-destructive.yaml`) with elevated RBAC.
- Sequential execution: standard E2E first, then destructive.
- `test-e2e-cluster.sh` already supports `TEST_SUITE=e2e|e2e-destructive`.
- **Gap**: Need a top-level orchestrator script that runs both in sequence and
  aggregates results. Currently manual.

Add `testing/ci/test-e2e-full.sh`:
```bash
./testing/ci/test-e2e-cluster.sh  # standard E2E
STANDARD_EXIT=$?
TEST_SUITE=e2e-destructive ./testing/ci/test-e2e-cluster.sh  # destructive
DESTRUCTIVE_EXIT=$?
# Aggregate: fail if either failed
exit $(( STANDARD_EXIT > DESTRUCTIVE_EXIT ? STANDARD_EXIT : DESTRUCTIVE_EXIT ))
```

Note: Both suites use the same `test-e2e-cluster.sh` with `TEST_SUITE` override.
Sequential execution ensures the PVC (ReadWriteOnce) is released between runs.

#### 5. Containerized Tool Execution

**Problem**: kubeconform, kubesec, helm-unittest require host installation. Missing
tools cause integration test failures.

**Solution**: Run validation tools via Docker containers:

```makefile
helm-validate:
    docker run --rm -v $(PWD)/charts:/charts ghcr.io/yannh/kubeconform:latest ...

helm-security:
    docker run --rm -v $(PWD)/charts:/charts kubesec/kubesec:latest ...

helm-unittest:
    docker run --rm -v $(PWD)/charts:/charts helmunittest/helm-unittest:latest ...
```

No host installation required. Pin image versions for reproducibility.

## Blast Radius

| Module/File | Scope | Failure Propagation |
|-------------|-------|---------------------|
| `testing/ci/test-e2e-cluster.sh` | Extended with observability extraction | Local — only affects E2E runner script |
| `testing/ci/test-e2e-full.sh` | New orchestrator | Local — only affects E2E execution |
| `testing/Dockerfile` | Add pytest-html, pytest-json-report | Local — only affects test image |
| `testing/k8s/jobs/test-e2e.yaml` | Add OTel env vars, artifact volume | Adjacent — affects E2E Job pods |
| `charts/floe-platform/values.yaml` | Security context propagation | Adjacent — affects all deployed pods |
| `charts/floe-platform/templates/` | Subchart security wiring | Adjacent — could break pod startup if misconfigured |
| `Makefile` | Target reorganization | Local — user-facing CLI |
| `.claude/hooks/check-e2e-ports.sh` | Update to support in-cluster path | Local — developer experience |

**What this design does NOT change**:
- No changes to application code (floe-core, floe-dagster, plugins, etc.)
- No changes to test code (tests/e2e/, tests/integration/, etc.)
- No changes to ServiceEndpoint or credential resolution logic
- No changes to Helm chart templates for application services
- No changes to CI/CD pipeline configuration

## Risk Assessment

### Primary risk: Subchart security context breakage

Some subcharts may not support the security context structure we're propagating.
Dagster's Helm chart has its own `securityContext` schema. If our values don't match,
pods won't start.

**Mitigation**: Test with `helm template` before deploying. Add a contract test that
renders the chart and validates all pods have `runAsNonRoot: true`.

### Secondary risk: Marquez runs as root

Marquez has no upstream non-root support. PSS admission is namespace-scoped — there's
no pod-level exemption without Kyverno/OPA. Accepted and documented as known gap.

**Mitigation**: Document in AUDIT.md. Defer separate namespace for Marquez as follow-up
work unit when it becomes blocking.

### Tertiary risk: DevPod image loading

`docker save | ssh | docker load` pipe may be slow for large images.

**Mitigation**: Optimize image size (multi-stage build, slim base). Registry push
available as future optimization. Image build is already ~90s, pipe adds ~30s.

## Architect Review Warnings (acknowledged)

The following were raised in adversarial review and are documented for downstream awareness:

- **Dockerfile dbt path**: dbt installs to `/root/.local/bin/` then symlinks. Non-root
  user may not have execute permission. Verify during build; fix by installing to shared path.
- **Make target semantic change**: `make test-e2e` changes from host-based to in-cluster.
  Add deprecation notice in help text. CI migration deferred (A8).
- **Log tail count**: Failure log extraction captures last 100 lines per pod. Make
  configurable via `LOG_TAIL_LINES` env var (default 100).
- **PVC ReadWriteOnce**: Sequential execution ensures only one pod uses PVC at a time.
  Cleanup between runs prevents mount conflicts.

## Alternatives Considered

### A. Service mesh sidecar for test observability

Inject Envoy/Linkerd sidecars into test pods for automatic tracing. Rejected:
too much infrastructure overhead for the value. OTel SDK in the test code + log
extraction provides equivalent debugging capability with zero additional infra.

### B. Telepresence/remote port-forward tools

Tools like Telepresence can provide more robust host-to-cluster networking. Rejected:
adds complexity, licensing concerns, and still fundamentally relies on tunneling.
In-cluster execution eliminates the problem entirely.

### C. Rebuild test runner from scratch

Replace the existing Dockerfile/Job/runner with a new framework. Rejected: existing
infrastructure is well-built and ~90% complete. The design builds on proven foundation.

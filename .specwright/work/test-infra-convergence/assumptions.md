# Assumptions: Test Infrastructure Convergence

## ACCEPTED

### A1: In-cluster registry is accessible from DevPod host (Type 2 — technical)

The registry at `testing/k8s/services/registry.yaml` is reachable via SSH tunnel
from the DevPod host. If not, fallback to `docker save | ssh | docker load` pipe.

**Basis**: DevPod architecture guarantees SSH access to the workspace. Registry
is a standard K8s service. Tunnel pattern proven by existing kubeconfig sync.

**Resolution**: ACCEPTED — fallback path exists, no blocking risk.

### A2: Subchart Helm values support security context passthrough (Type 2 — VERIFIED)

Verified via `helm show values` for each subchart:
- **Dagster**: `podSecurityContext` and `securityContext` per-component (webserver,
  daemon, run launcher, user deployments). Schema confirmed.
- **Jaeger**: `allInOne.podSecurityContext` and `allInOne.securityContext`. Already
  sets `runAsUser: 10001`.
- **OTel Collector**: Top-level `podSecurityContext` and `securityContext`. Standard schema.
- **MinIO**: Bitnami schema with `podSecurityContext.enabled: true` + subkeys.
  Non-standard but documented.

**Resolution**: VERIFIED — all subcharts accept security contexts. Key paths differ
(documented in design.md security hardening section). MinIO uses Bitnami's `enabled`
flag pattern.

### A3: pytest-html and pytest-json-report are compatible with current test suite (Type 2)

These plugins don't conflict with existing pytest plugins (pytest-rerunfailures,
pytest-ordering, etc.) or marker-based test selection.

**Basis**: Both are widely used, output-only plugins with no test behavior changes.

**Resolution**: ACCEPTED — standard pytest plugins, no conflict expected.

### A4: Marquez has no upstream non-root support (Type 2 — external)

Marquez Docker image runs as root. GitHub issue #3060 is open with no fix timeline.

**Basis**: Verified via research brief. Marquez Dockerfile uses `USER root` implicitly.

**Resolution**: ACCEPTED — design accounts for this with PSS exemption approach.

## DEFERRED

### A5: OTel collector is deployed and healthy during test execution (Type 2 — environmental)

The OTel collector (`floe-platform-otel`) is part of the standard platform deployment.
If it's unavailable, OTel SDK fails open (no traces, no crash). Tests still pass.

**Basis**: OTel SDK design is fail-open by spec. Job manifest already references
`OTEL_HOST: floe-platform-otel`. Smoke check fixture validates connectivity.

**Resolution**: ACCEPTED — OTel SDK is fail-open. Test runner observability degrades
gracefully (no traces) but tests don't hang or fail.

### A6: Test code runs without modification in-cluster (Type 2 — behavioral)

Tests use `ServiceEndpoint` for host resolution. When `INTEGRATION_TEST_HOST=k8s`,
cluster DNS is used. No tests hardcode `localhost` for service access.

**Basis**: ServiceEndpoint class verified in `testing/fixtures/services.py`. Job
manifest sets all `*_HOST` env vars. Previous in-cluster runs succeeded.

**Resolution**: ACCEPTED — ServiceEndpoint abstraction handles this. Any test that
hardcodes `localhost` is already a bug per testing standards.

### A7: dbt Fusion CLI is executable by non-root user (Type 2 — technical)

The Dockerfile installs dbt to `/root/.local/bin/dbt` then symlinks to
`/usr/local/bin/dbt`. The symlink target in root's home may not be readable by
the `floe` user (UID 1000).

**Basis**: Dockerfile line 58: `ln -sf /root/.local/bin/dbt /usr/local/bin/dbt`.
This is an existing potential issue in the Dockerfile.

**Resolution**: ACCEPTED — will verify and fix during build if needed. Fix is to
install dbt to a shared path or `chmod +rx /root/.local/bin/dbt`.

### A8: CI pipeline will adopt in-cluster execution (Type 1 — scope)

The CI pipeline (GitHub Actions) will be updated to use `make test-e2e-cluster`
instead of the current host-based approach.

**Basis**: This is a CI configuration change that depends on CI access and secrets
setup. Out of scope for this design — tracked as a follow-up.

**Resolution**: DEFERRED — CI migration is a separate work unit.

### A9: PVC ReadWriteOnce is sufficient for sequential test suites (Type 2 — technical)

The `test-artifacts` PVC uses `ReadWriteOnce`. Since standard and destructive tests
run sequentially (not concurrently), only one pod accesses the PVC at a time.

**Basis**: `test-e2e-full.sh` orchestrator waits for each Job to complete before
starting the next. Pod cleanup between runs ensures PVC is released.

**Resolution**: ACCEPTED — sequential execution means RWO is sufficient. If parallel
execution is needed later, upgrade to ReadWriteMany or use separate PVCs.

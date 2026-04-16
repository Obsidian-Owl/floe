# Context: Test Infrastructure Convergence

baselineCommit: 52c979b55adc39881fe02e9fe61fa6d9ac14aa3a

## Problem Statement

E2E tests are unreliable because they depend on kubectl port-forwards from the
host machine to in-cluster services. Port-forwards die when pods restart (e.g.,
`test_service_failure_resilience_e2e` kills Polaris), cascading to 30+ failures.
This is architecturally unfixable — K8s #78446 (closed won't-fix), SPDY protocol
limitations, no auto-reconnect.

Additionally: security hardening gaps (containers running as root), missing host
tools (kubeconform, kubesec), and no test-time observability for debugging failures.

## Existing Infrastructure (CRITICAL — much already exists)

### In-cluster test runner (built but underused)

| File | Purpose | Status |
|------|---------|--------|
| `testing/Dockerfile` | Python 3.11 + uv + kubectl + Helm 4 + dbt Fusion. Non-root UID 1000. | Complete |
| `testing/k8s/jobs/test-e2e.yaml` | K8s Job for non-destructive E2E. Uses cluster DNS. Creds from Secrets. | Complete |
| `testing/k8s/jobs/test-e2e-destructive.yaml` | Separate Job with elevated RBAC for destructive tests. | Complete |
| `testing/ci/test-integration.sh` | Full runner: build -> kind load -> create Job -> stream logs -> extract JUnit XML. | Complete |
| `testing/ci/test-e2e-cluster.sh` | Simplified wrapper: build -> load -> submit -> wait -> extract. | Complete |
| `testing/ci/test-e2e.sh` | Host-based runner with port-forward management (fragile). | Complete |
| `testing/k8s/rbac/e2e-test-runner.yaml` | ServiceAccount + RBAC for standard tests. | Complete |
| `testing/k8s/rbac/e2e-destructive-runner.yaml` | Elevated RBAC for destructive tests. | Complete |
| `testing/k8s/pvc/test-artifacts.yaml` | PVC for JUnit XML and artifacts. | Complete |
| `testing/k8s/secrets/polaris-secret.yaml` | Polaris credentials Secret. | Complete |

### Makefile targets

| Target | Behavior | Gap |
|--------|----------|-----|
| `make test-e2e` | DevPod + port-forwards (fragile) | Uses host-based runner |
| `make test-e2e-local` | Local Kind + port-forwards (fragile) | Uses host-based runner |
| `make test-e2e-cluster` | In-cluster Job (correct path) | Only works with local Kind (`kind load`) |
| `make test-e2e-devpod` | Inside DevPod DooD (rewrite kubeconfig) | Still uses port-forwards |

### Security contexts (partially implemented)

- `charts/floe-platform/values.yaml:652-682`: PSS restricted profile, `runAsNonRoot`,
  capability drops, seccomp. **Defined but NOT propagated to subcharts** — Dagster,
  Jaeger, OTel collector, Marquez all use their own defaults.
- Marquez: Runs as root (UID 0). Upstream issue #3060 open, no fix.

### ServiceEndpoint class

- `testing/fixtures/services.py`: Auto-resolves host/port via env vars -> K8s DNS.
- When `INTEGRATION_TEST_HOST=k8s`, uses cluster DNS names.
- Job manifests already set all `*_HOST` env vars to K8s service names.

### Credential management

- `testing/fixtures/credentials.py`: Centralized credential access.
- Priority: env vars -> manifest.yaml -> hardcoded defaults.
- Job manifests source credentials from K8s Secrets.

## Key Gaps to Address

1. **DevPod image loading**: `kind load docker-image` requires local Docker socket.
   DevPod on Hetzner needs alternative (registry push, or `docker save | ssh | docker load`).

2. **Log extraction / observability**: Current runner only captures raw `kubectl logs`.
   No structured log shipping, no OTel from test runner, no pytest-html reports.

3. **Security context propagation**: Base values.yaml has contexts but subcharts ignore them.
   Need to wire `podSecurityContext`/`containerSecurityContext` through each subchart.

4. **Marquez non-root**: Needs custom image or PSS exemption for the namespace.

5. **Containerized tools**: kubeconform, kubesec, helm-unittest need to run in containers
   rather than requiring host installation.

6. **Makefile convergence**: `make test-e2e` should use in-cluster runner by default,
   with host-based as explicit fallback.

## Research Brief Reference

`.specwright/research/test-prod-convergence-20260406.md` — covers 4 tracks:
- Track 1: Test infrastructure stabilization (in-cluster execution pattern)
- Track 2: Production deployment patterns (Helm values layering)
- Track 3: Test-production convergence (same charts, different values)
- Track 4: Security hardening (PSS restricted, non-root containers)

## File Paths for Implementation

- `testing/Dockerfile` — add observability tooling (pytest-html, structlog)
- `testing/k8s/jobs/test-e2e.yaml` — add OTel sidecar or env vars
- `testing/ci/test-e2e-cluster.sh` — extend for DevPod (registry or pipe)
- `testing/ci/test-integration.sh` — add log extraction improvements
- `charts/floe-platform/values.yaml` — security context propagation
- `charts/floe-platform/templates/` — subchart security context wiring
- `Makefile` — consolidate E2E targets
- New: `testing/k8s/jobs/observability-sidecar.yaml` or inline sidecar config

# Context: In-Cluster Runner (Unit 1)

## Problem

`make test-e2e` uses host-based port-forwards that die when pods restart, cascading
to 30+ test failures. `make test-e2e-cluster` works but only with local Kind via
`kind load docker-image`. No DevPod support. No orchestration of standard + destructive
test suites.

## Existing Infrastructure

| File | Status | What exists |
|------|--------|-------------|
| `testing/ci/test-e2e-cluster.sh` | Complete | Build, load (Kind only), submit Job, wait, extract artifacts |
| `testing/ci/test-integration.sh` | Complete | Full runner with RBAC setup, log streaming, JUnit extraction |
| `testing/ci/test-e2e.sh` | Complete | Host-based runner with port-forwards (fragile — to be demoted) |
| `testing/k8s/jobs/test-e2e.yaml` | Complete | K8s Job for non-destructive tests |
| `testing/k8s/jobs/test-e2e-destructive.yaml` | Complete | K8s Job for destructive tests |
| `Makefile` | Needs changes | Has `test-e2e`, `test-e2e-local`, `test-e2e-cluster`, `test-e2e-devpod` |
| `.claude/hooks/check-e2e-ports.sh` | Needs update | Blocks direct pytest if port-forwards missing |

## Key Design Decisions

- **D-5/D-7**: DevPod image loading via `docker save | ssh | docker load` pipe
  (SSH is guaranteed by DevPod architecture). Registry push deferred.
- **D-1**: Build on existing `test-e2e-cluster.sh`, don't rebuild.
- Auto-detect environment: Kind → `kind load`, DevPod → SSH pipe, else → fail-fast.
- Sequential orchestrator for standard + destructive suites.

## File Paths

- `testing/ci/test-e2e-cluster.sh` — extend with DevPod auto-detection
- `testing/ci/test-e2e-full.sh` — new orchestrator
- `Makefile` — reorganize E2E targets
- `.claude/hooks/check-e2e-ports.sh` — update for in-cluster path

## Patterns Reference

- P71: Always use `127.0.0.1` not `localhost` in scripts
- P52: Guard post-loop actions against empty iteration
- P53: Pin exact versions for npx/tool installs

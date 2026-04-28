# DevPod Remote E2E Execution Design

## Goal

Make `make devpod-test` run E2E validation inside the Hetzner DevPod workspace instead of building and streaming the 5.4 GB `floe-test-runner:latest` image from the laptop to the remote Kind cluster.

## Context

The platform bootstrap path already uses a remote Git source, a disposable Hetzner DevPod workspace, Flux manifests, chart-rendered values, and remote Kind. The remaining bottleneck is Step 4 in `scripts/devpod-test.sh`: it syncs a kubeconfig back to the host, opens tunnels, then invokes local `make test-e2e KUBECONFIG=...`. Because `testing/ci/test-e2e-cluster.sh` auto-detects the DevPod kubeconfig, it builds the test-runner image locally and streams it through `devpod ssh` before loading it into remote Kind.

That design is correct for a fallback, but wrong for the primary full-lifecycle Hetzner path. Floe exceeds practical local-memory and network assumptions, so the full validation path must execute from the remote workspace that already has the repository, Docker daemon, and Kind cluster.

## Design

`scripts/devpod-test.sh` will run the E2E command through `devpod ssh` in `DEVPOD_REMOTE_WORKDIR` after the health gate and tunnel setup:

```bash
devpod ssh "${WORKSPACE}" \
  --start-services=false \
  --workdir "${DEVPOD_REMOTE_WORKDIR}" \
  --command "IMAGE_LOAD_METHOD=kind make test-e2e"
```

The remote command uses `IMAGE_LOAD_METHOD=kind` so `testing/ci/test-e2e-cluster.sh` builds the image on the DevPod VM and loads it directly into the remote Kind cluster. It does not use the DevPod image transport path. The current local path remains available behind an explicit environment switch for debugging the transport behavior, not as the default.

`scripts/devpod-test.sh` will also fix the health gate count parsing. The current `wc -l | tr -d ' '` can produce a newline plus fallback text when the left side fails under `set -o pipefail`, which creates arithmetic values like `0\n0`. The health gate should capture pod output once per loop and derive numeric counts from that captured value.

## Boundaries

This change does not hardcode product images, service names, manifest paths, or pipeline values. E2E Job rendering continues to flow through `testing/ci/common.sh`, Helm chart templates, and `charts/floe-platform/values-test.yaml`.

This change does not introduce a registry dependency. Registry-backed BuildKit caching is the next long-term optimization, but the immediate blocker is the local-to-remote image upload. Remote build plus direct Kind load removes that blocker while preserving disposable Hetzner validation.

## Testing

Unit-level structural tests will verify that:

- `scripts/devpod-test.sh` defaults to remote E2E execution via `devpod ssh`.
- The remote command runs in `DEVPOD_REMOTE_WORKDIR`.
- The remote command uses `IMAGE_LOAD_METHOD=kind make test-e2e`.
- The legacy local E2E path is gated behind an explicit opt-in variable.
- The health gate computes pod counts from captured pod output and does not pipe `wc -l` into arithmetic values.

Runtime validation remains `make devpod-test` on Hetzner.

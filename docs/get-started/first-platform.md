# Deploy Your First Platform

This tutorial brings up the alpha-supported DevPod + Hetzner workspace, syncs Kubernetes access back to your laptop, and validates that the docs remain publishable before you run the demo path.

## Prerequisites

- A Hetzner Cloud API token in the environment expected by `scripts/devpod-setup.sh` or your local `.env`.
- The DevPod CLI installed locally.
- Docker available in the DevPod workspace after provisioning.
- A local checkout of the Floe repository, with a pushed Git branch or explicit `DEVPOD_SOURCE`; `make devpod-up` resolves the workspace source from Git unless local-source overrides are set.
- `kubectl`, `helm`, `uv`, `npm`, and `make` available locally.

## What This Does

The platform-first path creates or starts a remote DevPod workspace on Hetzner, syncs the workspace kubeconfig to `~/.kube/devpod-${DEVPOD_WORKSPACE}.config` unless `DEVPOD_KUBECONFIG` overrides it, opens the Kubernetes API tunnel, reports workspace and tunnel status, and verifies the docs site before you continue.

Use this path instead of local Kind when you need the supported alpha demo environment or release-style evidence.

## Steps

```bash
make devpod-setup
make devpod-up
make devpod-sync
make devpod-status
make docs-validate
```

## Expected Output

`make devpod-setup` should either configure the Hetzner provider or report that it is already configured.

`make devpod-up` should show the resolved DevPod source and a workspace named by `DEVPOD_WORKSPACE` or the default `floe`.

`make devpod-sync` should include patterns like:

```text
[devpod-sync] Kubeconfig written to .../.kube/devpod-floe.config
[devpod-sync] SUCCESS: K8s cluster accessible at localhost:26443
```

`make devpod-status` should include:

```text
=== Workspace Status ===
=== Tunnel Status ===
=== Cluster Health ===
workspace: reachable
kubeconfig: present
cluster: reachable
```

`make docs-validate` should finish without navigation, link, or build errors.

## Troubleshooting

- If `make devpod-up` cannot resolve a source, push the branch or set `DEVPOD_SOURCE` explicitly.
- If `make devpod-sync` says the workspace is not running, run `make devpod-up` and retry.
- If `kubectl` still uses the wrong cluster, export the synced kubeconfig and retry:

```bash
export KUBECONFIG="${DEVPOD_KUBECONFIG:-$HOME/.kube/devpod-${DEVPOD_WORKSPACE:-floe}.config}"
kubectl cluster-info
```

- If tunnel ports are already in use, inspect ownership with `make devpod-status` and stop demo forwards with `make demo-stop` before starting manual tunnels.

See [DevPod + Hetzner operations](../operations/devpod-hetzner.md) and [Troubleshooting](../operations/troubleshooting.md) for deeper recovery steps.

## Cleanup

Stop the workspace when you want to preserve the VM disk but pause the active workspace:

```bash
make devpod-stop
```

Delete the workspace when you want to stop all Hetzner workspace charges:

```bash
make devpod-delete
```

## Next Steps

- [Build your first data product](first-data-product.md)
- [Run the Customer 360 demo](../demo/customer-360.md)

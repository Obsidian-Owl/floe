# DevPod + Hetzner Operations

Use this guide to operate the remote alpha workspace after you choose the DevPod + Hetzner path.

## Prerequisites

- DevPod CLI installed locally.
- Hetzner provider configured with `make devpod-setup`.
- A reachable DevPod workspace from `make devpod-up`.
- `kubectl` installed locally.

## What This Does

The lifecycle is explicit: `make devpod-up` creates or starts the workspace, `make devpod-sync` copies and rewrites kubeconfig for local access, `make devpod-status` reports workspace/tunnel/cluster health, `make devpod-stop` stops the workspace while preserving its disk, and `make devpod-delete` removes the workspace when you want billing to stop.

## Steps

```bash
make devpod-setup
make devpod-up
make devpod-sync
make devpod-status
```

Verify kubeconfig after sync:

```bash
export KUBECONFIG="${DEVPOD_KUBECONFIG:-$HOME/.kube/devpod-${DEVPOD_WORKSPACE:-floe}.config}"
kubectl cluster-info
kubectl get pods -n floe-dev
```

## Expected Output

| Check | Healthy pattern | If unhealthy |
| --- | --- | --- |
| Workspace | `devpod status` reports the workspace as running | Run `make devpod-up` and check source resolution errors |
| Kubeconfig | `make devpod-sync` writes `~/.kube/devpod-floe.config` or `DEVPOD_KUBECONFIG` | Confirm workspace is running and inspect `~/.kube/devpod-ssh.log` |
| Cluster | `kubectl cluster-info` succeeds with the synced kubeconfig | Re-run `make devpod-sync`; check tunnel port `26443` |
| Manual tunnels | `make devpod-tunnels` reports forwarded localhost ports | Stop conflicting forwards or use `make demo-stop` |

`make devpod-status` prints three sections:

```text
=== Workspace Status ===
=== Tunnel Status ===
=== Cluster Health ===
```

## Port-Forward Ownership

`make demo` owns the automated Customer 360 demo port-forwards while the demo runs and records them in `.demo-pids`. Use `make demo-stop` to stop those forwards.

Use `make devpod-tunnels` only for manual UI inspection outside the automated demo flow. Do not run it at the same time as `make demo` unless you intentionally want to reuse or inspect already-open local ports.

Manual tunnel commands:

```bash
make devpod-tunnels
make devpod-status
```

## Troubleshooting

- Workspace unreachable: run `make devpod-status`, then `make devpod-up` if the workspace is stopped.
- Wrong cluster: export the kubeconfig shown by `make devpod-sync` and retry `kubectl cluster-info`.
- Port in use: run `make demo-stop`, then `make devpod-status`; if needed, stop manual tunnels with `scripts/devpod-tunnels.sh --kill`.

## Cleanup

Stop the workspace but keep its disk:

```bash
make devpod-stop
```

Delete the workspace and stop workspace billing:

```bash
make devpod-delete
```

## Next Step

- [Troubleshoot alpha operations](troubleshooting.md)

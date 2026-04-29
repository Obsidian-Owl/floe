# DevPod + Hetzner Operations

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Prepare a DevPod workspace backed by the Hetzner provider.
- Sync kubeconfig from the workspace to your local machine.
- Start service tunnels only when you need manual UI inspection.
- Check workspace status before and after running Customer 360.

## Commands

```bash
make devpod-setup
make devpod-up
make devpod-sync
make devpod-status
```

## Manual UI Tunnels

`make demo` owns the automated Customer 360 demo flow, including the port-forwards it needs while the demo runs. Use `make devpod-tunnels` separately when you want to inspect UIs manually outside that automated flow.

```bash
make devpod-tunnels
make devpod-status
```

## Success Criteria

- The DevPod CLI is installed and `make devpod-setup` completes provider setup.
- `make devpod-up` creates or starts the configured workspace.
- `make devpod-sync` writes a kubeconfig that local commands can use.
- `make devpod-tunnels` exposes service ports for manual UI inspection when needed.
- `make devpod-status` reports workspace, tunnel, and cluster reachability.

## Next Step

- [Troubleshoot alpha operations](troubleshooting.md)

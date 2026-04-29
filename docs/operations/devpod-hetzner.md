# Devpod + Hetzner Operations

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Prepare a Devpod workspace backed by the Hetzner provider.
- Sync kubeconfig from the workspace to your local machine.
- Start service tunnels for demo validation.
- Check workspace status before and after running Customer 360.

## Commands

```bash
make devpod-setup
make devpod-up
make devpod-sync
make devpod-tunnels
make devpod-status
```

## Success Criteria

- The Devpod CLI is installed and `make devpod-setup` completes provider setup.
- `make devpod-up` creates or starts the configured workspace.
- `make devpod-sync` writes a kubeconfig that local commands can use.
- `make devpod-tunnels` exposes the demo service ports for validation.
- `make devpod-status` reports workspace, tunnel, and cluster reachability.

## Next Step

- [Troubleshoot alpha operations](troubleshooting.md)

# Deploy Your First Platform

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Prepare for the alpha platform path on a remote DevPod workspace backed by Hetzner.
- Confirm local documentation and Make targets before starting Kubernetes-heavy work.
- Use the operations guide to create, sync, and inspect the remote workspace.
- Run the Customer 360 demo only after the DevPod workspace is reachable.

## Commands

```bash
make help
make docs-validate
make devpod-status
```

## Success Criteria

- `make help` lists the DevPod, demo, docs, Helm, and Kind targets.
- `make docs-validate` passes before you run the alpha platform workflow.
- `make devpod-status` shows whether a DevPod workspace, tunnels, and cluster are already reachable.
- You continue to [DevPod + Hetzner operations](../operations/devpod-hetzner.md) before running the Customer 360 demo.

## Local Smoke Test

Use Kind only for a local platform smoke test. This does not run the Customer 360 alpha demo.

```bash
make kind-up
make helm-test-infra
kubectl get pods -n floe-test
```

## Cleanup

When you are finished with the local smoke-test cluster, stop it explicitly:

```bash
make kind-down
```

## Next Step

- [Prepare DevPod + Hetzner operations](../operations/devpod-hetzner.md)
- [Build your first data product](first-data-product.md)
- [Run the Customer 360 demo](../demo/customer-360.md)

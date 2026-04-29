# Deploy Your First Platform

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Create or reuse a Kind cluster for the Floe test platform.
- Install the platform Helm chart with repository-provided values.
- Check Kubernetes service health before running demos.
- Stop the local cluster when the validation session is complete.

## Commands

```bash
make kind-up
make helm-test-infra
kubectl get pods -n floe-test
make kind-down
```

## Success Criteria

- `make kind-up` completes without Helm or Kubernetes errors.
- `make helm-test-infra` reports the test namespace and pods as reachable.
- `kubectl get pods -n floe-test` shows platform pods rather than a missing namespace.
- Cleanup is explicit with `make kind-down` when you no longer need the local cluster.

## Next Step

- [Build your first data product](first-data-product.md)
- [Run the Customer 360 demo](../demo/customer-360.md)

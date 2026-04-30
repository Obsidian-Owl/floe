# Get Started

This page is part of the `v0.1.0-alpha.1` release path.

## Choose A Path

- Choose [Deploy Your First Platform](first-platform.md) if you need DevPod + Hetzner, kubeconfig sync, and platform reachability before running demos.
- Choose [Build Your First Data Product](first-data-product.md) if you want to inspect the Customer 360 source files and generated artifacts before touching Kubernetes.
- Choose [Customer 360](../demo/customer-360.md) after platform setup and compilation are understood.

## Validate The Docs

```bash
make help
make docs-build
make docs-validate
```

Expected outcomes:

- `make help` lists the docs, demo, Helm, Kind, and DevPod targets.
- `make docs-build` completes the Starlight static site build.
- `make docs-validate` catches navigation, link, and tutorial-structure regressions before the docs are published.

## Next Steps

- [Deploy your first platform](first-platform.md)
- [Build your first data product](first-data-product.md)

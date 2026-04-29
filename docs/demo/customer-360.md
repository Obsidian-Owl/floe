# Customer 360 Golden Demo

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Run the alpha golden demo with the repository-provided Customer 360 project.
- Exercise the integrated Dagster, dbt, Iceberg, Polaris, MinIO, Marquez, and Jaeger path.
- Keep this page as a brief placeholder until the dedicated Task 4 guide expands it.
- Stop demo tunnels when you finish validation.

## Commands

```bash
make compile-demo
make demo
make demo-stop
```

## Success Criteria

- `make compile-demo` completes before the demo is deployed.
- `make demo` reaches the Devpod-backed Kubernetes cluster.
- Demo service tunnels are started for the alpha validation workflow.
- No Customer 360 validation Make target is documented here yet; that target is planned for a later task.

## Next Step

- [Validate Customer 360](customer-360-validation.md)

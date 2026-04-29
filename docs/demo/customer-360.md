# Customer 360 Golden Demo

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Run the alpha golden demo with the repository-provided Customer 360 project.
- Exercise the integrated Dagster, dbt, Iceberg, Polaris, MinIO, Marquez, and Jaeger path.
- Use the DevPod-backed alpha path prepared in the operations guide.
- Stop demo tunnels when you finish validation.

## Commands

```bash
make compile-demo
make demo
make demo-stop
```

## Success Criteria

- `make compile-demo` completes before the demo is deployed.
- `make demo` reaches the DevPod-backed Kubernetes cluster.
- Demo service port-forwards are started for the alpha validation workflow.
- Customer 360 automated validation will be documented before alpha tagging.

## Next Step

- [Validate Customer 360](customer-360-validation.md)

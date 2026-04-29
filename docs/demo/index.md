# Demo

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Use Customer 360 as the alpha golden demo.
- Deploy demo services through existing Make targets.
- Keep validation evidence separate from setup commands.
- Move from demo execution to validation when services are reachable.

## Commands

```bash
make compile-demo
make demo
make demo-stop
```

## Success Criteria

- Demo artifacts compile before deployment.
- `make demo` starts the demo workflow against the configured Devpod workspace.
- Service tunnels are available for Dagster, MinIO, Marquez, Jaeger, Polaris, and OTLP.
- `make demo-stop` stops local port-forward processes when validation is complete.

## Next Step

- [Run the Customer 360 demo](customer-360.md)

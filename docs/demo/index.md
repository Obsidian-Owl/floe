# Demo

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Use Customer 360 as the alpha golden demo.
- Validate an already deployed Floe platform through the Customer 360 evidence path.
- Use contributor-only Make targets when running the remote release-validation lane.
- Keep validation evidence separate from setup commands.
- Move from demo execution to validation when services are reachable.

## Platform And Data Product Validation

Platform Engineers and Data Engineers should start from a deployed Floe platform, then use the Customer 360 guide to validate platform readiness, orchestration, storage, lineage, traces, and business output evidence.

The Customer 360 demo validates Floe's alpha platform and data product path. Platform Engineers can run it on a deployed Floe platform; Floe Contributors can use the DevPod workspace when they need the remote release-validation lane.

## Contributor Commands

```bash
make compile-demo
make demo
make demo-stop
```

## Success Criteria

- Demo artifacts compile before deployment.
- `make demo` is used only for the contributor remote release-validation lane.
- `make demo` starts and owns the port-forwards needed by the automated contributor demo flow.
- `make devpod-tunnels` is not required before `make demo`; contributors can use it separately for manual UI inspection.
- `make demo-stop` stops local port-forward processes when validation is complete.

## Next Step

- [Run the Customer 360 demo](customer-360.md)

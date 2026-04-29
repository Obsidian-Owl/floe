# Customer 360 Validation

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Capture manual validation evidence for the Customer 360 alpha demo.
- Confirm the demo run is visible through service endpoints.
- Record gaps that automated validation must close before alpha tagging.
- Keep evidence concise and reproducible while the validation checklist is expanded.

## Commands

```bash
make devpod-status
make docs-validate
```

## Success Criteria

- DevPod status shows the workspace and cluster are reachable.
- Documentation validation continues to pass while Customer 360 validation docs are expanded.
- Planned Customer 360 validation automation is not treated as available until its Make target exists.
- Manual evidence identifies demo run status, generated data, lineage, and tracing observations.

## Next Step

- [DevPod + Hetzner operations](../operations/devpod-hetzner.md)

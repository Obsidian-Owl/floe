# Troubleshooting

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Diagnose common alpha setup failures without changing architecture.
- Separate documentation/build failures from Kubernetes runtime failures.
- Check DevPod reachability before rerunning demo deployment.
- Capture reproducible command output for release evidence.

## Commands

```bash
make docs-validate
make devpod-status
kubectl get pods -n floe-dev
kubectl get pods -n floe-test
```

## Success Criteria

- Docs validation and Starlight build failures are reproduced with `make docs-validate`.
- DevPod failures are reproduced with `make devpod-status`.
- Runtime failures include namespace-specific pod status.
- Follow-up issues include exact commands and relevant output snippets.

## Next Step

- [Review reference material](../reference/index.md)

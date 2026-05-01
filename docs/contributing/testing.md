# Contributor Testing

This guide is for Floe Contributors changing the Floe repository.

## Primary Commands

```bash
make test-unit
make test
make docs-validate
```

## Test Boundaries

| Tier | Purpose | Typical Command |
| --- | --- | --- |
| Unit | Fast package and function tests | `make test-unit` |
| Integration | Kubernetes-native service integration | `make test-integration` |
| E2E | Full platform workflows | `make demo-customer-360-validate` after setup |
| Docs | Starlight sync, build, and content gates | `make docs-validate` |

## Remote Validation

Use DevPod when the full validation lane does not fit on a local machine.

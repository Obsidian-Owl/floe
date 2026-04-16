# Assumptions

## A1: dagster-k8s version compatibility
- **Status**: VERIFIED
- **Assumption**: dagster-k8s 0.28.14 is compatible with dagster 1.12.14
- **Evidence**: Same release train; pyproject.toml declares `>=1.10.0,<2.0.0`; dagster-postgres uses same 0.28.14 versioning

## A2: bitnami/kubectl:1.32.0 exists
- **Status**: ACCEPTED
- **Assumption**: bitnami/kubectl:1.32.0 is a valid Docker Hub tag
- **Risk**: Low — Bitnami publishes all Kubernetes minor.patch versions
- **Mitigation**: The build will fail at Helm deploy if tag is wrong, easily detected

## A3: Existing tests continue to pass
- **Status**: ACCEPTED
- **Assumption**: The 128 passing E2E tests will continue to pass after these additive changes
- **Evidence**: Changes are additive (new package, fixed tag, new Makefile target) — no existing behavior modified

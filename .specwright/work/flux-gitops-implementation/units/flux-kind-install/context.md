# Context: flux-kind-install

**Parent work**: flux-gitops-implementation
**Baseline commit**: 412b1c4 (origin/main)

## What This Unit Does

Install Flux v2 controllers in the Kind cluster and replace direct `helm upgrade --install`
in `setup-cluster.sh` with HelmRelease CRDs that Flux reconciles. This is the infrastructure
foundation that all subsequent Flux work depends on.

## Key Files

| File | Lines | Role |
|------|-------|------|
| `testing/k8s/setup-cluster.sh` | 365 | Kind cluster creation + Helm deployment — **primary modification target** |
| `testing/ci/common.sh` | 79 | Shared identifiers: `FLOE_RELEASE_NAME`, `FLOE_NAMESPACE`, etc. — add `FLUX_VERSION` |
| `charts/floe-platform/flux/` | NEW | HelmRelease + GitRepository CRD manifests for Kind |
| `charts/examples/flux/helmrelease.yaml` | 155 | Existing example using deprecated v2beta2 API (NOT modified in this unit) |

## Flux-Specific Gotchas

- HelmRelease cannot point to local filesystem paths — must use GitRepository or OCI source
- `strategy: uninstall` performs uninstall-between-each-retry (not "rollback N times then uninstall")
- `remediateLastFailure` defaults to `true` when `retries > 0`
- SemVer `>=1.0.0` does NOT match pre-releases — use `>=1.0.0-0`
- Flux auto-adopts existing Helm releases by matching release name + namespace
- **CRITICAL**: fluxcd/flux2#4614 — cannot cleanly adopt a release in `failed` state with no previous `deployed` revision. Must `helm uninstall` first on existing clusters.

## Kind/DevPod Gotchas

- Docker images must be `--platform linux/amd64` (Mac arm64 -> Hetzner amd64)
- source-controller must have network access to GitHub from inside Kind
- Flux CLI must be version-pinned per P53 (no `@latest`)

## Current State

- Helm release stuck at revision 54, status `failed` — blocks all 306 E2E tests
- Test runner SA lacks `clusterroles` RBAC for `helm rollback`
- `setup-cluster.sh` currently runs `helm upgrade --install` directly (lines ~200-280)
- `common.sh` defines `FLOE_RELEASE_NAME=floe-platform`, `FLOE_NAMESPACE=floe-test`

## Design Decisions (from design.md)

- D3: Flux over ArgoCD (ArgoCD selfHeal bug #18442)
- D4: Minimal install (source-controller + helm-controller only)
- D8: Pre-Flux cleanup required for existing clusters
- D9: `kubectl wait --for=condition=Ready --timeout=900s` for readiness
- D11: Both `floe-platform` and `floe-jobs-test` managed by Flux

## Shell Script Standards

- Use `[[` for conditionals, `>&2` for error output
- Pin exact versions for CLI tools (P53)
- Use `127.0.0.1` not `localhost` (P71)
- Guard post-loop actions against empty iteration (P52)

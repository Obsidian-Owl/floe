# Assumptions: Flux v2 GitOps Implementation

## A1: Flux v2 GA API stability [ACCEPTED]
**Type**: Technical (Type 2 — reversible)
**Assumption**: Flux v2 (`helm.toolkit.fluxcd.io/v2`, `source.toolkit.fluxcd.io/v1`) API is stable and will not have breaking changes.
**Evidence**: Promoted to GA in Flux v2.3 (2024). CNCF graduated project. Active maintenance.
**Resolution**: Auto-ACCEPT — official docs confirm GA status, CNCF graduation provides stability guarantee.

## A2: Kind cluster has sufficient resources for Flux controllers [ACCEPTED]
**Type**: Technical (Type 2 — reversible)
**Assumption**: The Hetzner DevPod VM running the Kind cluster has at least 150m CPU and 128Mi memory headroom for Flux controllers.
**Evidence**: Flux docs specify these as the request values. Kind cluster already runs Dagster, Polaris, MinIO, PostgreSQL, Jaeger, OTel Collector.
**Resolution**: Auto-ACCEPT — if resources are tight, Flux controllers can be removed. Reversible.

## A3: GitRepository source works for Kind dev iteration [ACCEPTED]
**Type**: Clarify (Type 2 — reversible)
**Assumption**: Using a GitRepository pointing to the repo with `chart: ./charts/floe-platform` is acceptable for Kind dev, even though changes must be committed before Flux picks them up.
**Evidence**: Flux docs recommend this for dev. Direct `helm` CLI remains available as escape hatch when Flux is suspended.
**Resolution**: Auto-ACCEPT — `flux suspend` provides escape hatch. Dev workflow documented.

## A4: Existing Helm release can be auto-adopted by Flux [ACCEPTED]
**Type**: Technical (Type 2 — reversible)
**Assumption**: Flux HelmRelease can take over management of the existing `floe-platform` release in `floe-test` namespace without requiring uninstall/reinstall.
**Evidence**: Flux docs confirm auto-adoption: "If the HelmRelease object specifies an existing release name and namespace, Flux will adopt the release."
**Resolution**: Auto-ACCEPT — verified in official docs.

## A5: GHCR OCI is the right chart registry [ACCEPTED]
**Type**: Clarify (Type 2 — reversible)
**Assumption**: GitHub Container Registry is appropriate for Floe's chart distribution.
**Evidence**: Floe is open source on GitHub. GHCR is free for public repos. The existing `helm-release.yaml` workflow already publishes to GHCR.
**Resolution**: Auto-ACCEPT — already in use, free, no migration needed.

## A6: SOPS (Age) is the right default secrets approach [ACCEPTED]
**Type**: Clarify (Type 2 — reversible)
**Assumption**: SOPS with Age keys is the appropriate default for Floe's recommended secrets management.
**Evidence**: Zero extra controllers (built into kustomize-controller). Simplest for small/medium teams. Flux officially recommends SOPS. ESO documented as enterprise alternative.
**Resolution**: Auto-ACCEPT — Type 2 (can switch to ESO later), simplest path for pre-alpha.

## A7: Template repo is preferred over CLI subcommand [DEFERRED]
**Type**: Reference (external decision)
**Assumption**: A GitHub template repository for GitOps bootstrapping is preferred over a `floe flux bootstrap` CLI subcommand.
**Evidence**: Research found that `flux create helmrelease --export` already generates HelmRelease YAML. Template repos include directory structure, Kustomize overlays, CI workflows — things a CLI can't maintain.
**Resolution**: Auto-DEFER — this is a product strategy decision. Template repo is the Phase 2 deliverable, but the CLI approach could be added later if user demand exists. BL-flux-cli.

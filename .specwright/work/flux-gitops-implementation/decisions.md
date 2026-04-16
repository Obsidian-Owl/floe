# Decisions: Flux v2 GitOps Implementation

## D1: Start new work (not continue existing)
**Rule**: DISAMBIGUATION — argument provided, start new.
**Context**: Prior `currentWork` was `debug-dagster-readonly-fs` with status `shipped`. User invoked `/sw-design` in context of completed Flux research. Clear intent to design Flux implementation.
**Decision**: Start new work unit `flux-gitops-implementation`. Prior work moved to `completedWork`.

## D2: Two-phase approach (test infra first, user-facing second)
**Rule**: DISAMBIGUATION — simplest viable path.
**Context**: Flux serves dual purpose: (1) immediate test stability, (2) strategic platform deployment. Phase 1 (test infra) is smaller scope, delivers immediate value, and validates Flux before exposing to users.
**Decision**: Phase 1 focuses on Kind cluster Flux installation + HelmRelease remediation. Phase 2 focuses on user-facing GitOps artifacts.
**Trade-off**: Could do everything at once, but Phase 1 alone unblocks the 306 stuck E2E tests.

## D3: Flux over ArgoCD
**Rule**: Technical evidence — known bug.
**Context**: ArgoCD `selfHeal` has issue #18442 where healing is silently skipped when previous sync against same commit SHA failed. This is the exact failure mode we need to prevent.
**Decision**: Flux. Its remediation model with `strategy: uninstall` is purpose-built for this.

## D4: Minimal Flux install (source-controller + helm-controller only)
**Rule**: DISAMBIGUATION — simplest viable path.
**Context**: Full Flux includes 5+ controllers (source, helm, kustomize, notification, image-automation). We only need Helm release management.
**Decision**: Install only `source-controller` and `helm-controller`. ~150m CPU / 128Mi memory vs ~500m+ for full install.
**Trade-off**: No Kustomize reconciliation (we'd need to add `kustomize-controller` if we want the ConfigMap hash pattern in-cluster). For Phase 1, inline values are sufficient.

## D5: Hybrid values pattern (inline + ConfigMap)
**Rule**: Research evidence — Flux maintainer recommendation.
**Context**: Three options: (A) all inline, (B) all ConfigMap, (C) hybrid. Stefan Prodan recommends ConfigMap for dynamic values with inline for structural toggles.
**Decision**: Hybrid. Plugin toggles inline in HelmRelease. Compiled values in ConfigMap via `valuesFrom`. Secrets in Secret via `valuesFrom`.
**Trade-off**: Slightly more complex than all-inline, but provides hash-based rollout and clean separation of concerns.

## D6: SOPS (Age) as default, ESO as documented alternative
**Rule**: DISAMBIGUATION — simplest viable path for pre-alpha.
**Context**: SOPS has zero extra dependencies, ESO adds 3 pods. Both work. Pre-alpha users are small teams.
**Decision**: Default to SOPS. Document ESO. Add `secrets.provider` field to manifest schema for future integration.

## D7: Template repo over CLI subcommand
**Rule**: Research evidence — lower maintenance, broader capability.
**Context**: A CLI subcommand wraps what `flux create helmrelease --export` already does. A template repo provides directory structure, CI workflows, and env-specific configs that a CLI can't.
**Decision**: Template repo as primary artifact. `floe compile --output-format=configmap` as CLI integration point.

## D8: Pre-Flux cleanup required for existing clusters (BLOCK-1 resolution)
**Rule**: Technical evidence — fluxcd/flux2#4614.
**Context**: Architect review identified that Flux cannot cleanly adopt a release in `failed` state with no previous `deployed` revision. Flux attempts an upgrade, fails, then enters remediation loop.
**Decision**: Require `helm uninstall` before applying HelmRelease CRD on existing clusters. New clusters created by `setup-cluster.sh` don't need this — Flux performs initial install. Document as one-time migration step.
**Trade-off**: Destructive first migration, but acceptable for test infrastructure.

## D9: Synchronous readiness via kubectl wait (BLOCK-2 resolution)
**Rule**: DISAMBIGUATION — simplest viable mechanism.
**Context**: Architect review identified that the design lacked a concrete readiness polling mechanism. Options: (a) `kubectl wait --for=condition=Ready`, (b) `flux get --watch`, (c) custom polling loop.
**Decision**: Use `kubectl wait --for=condition=Ready helmrelease/floe-platform --timeout=900s`. This is the most standard K8s-native wait mechanism, requires no Flux CLI for the wait step, and provides clear timeout + exit code semantics.

## D10: Crash-safe Flux suspend/resume fixture (BLOCK-3 resolution)
**Rule**: Technical requirement — pytest finalizer mechanism.
**Context**: Architect review identified that `test_helm_upgrade_e2e.py` conflicts with Flux management. `flux suspend` is needed, but crashes between suspend/resume leave Flux permanently suspended.
**Decision**: Module-scoped pytest fixture using `request.addfinalizer()` for crash-safe resume. Session fixture checks for suspended state at startup and resumes (handles previous session crashes).
**Trade-off**: Adds Flux awareness to test infrastructure, but the alternative (ignoring the conflict) produces unreliable test results.

## D11: Both Helm releases managed by Flux (WARN-1 resolution)
**Rule**: Consistency — avoid split-brain.
**Context**: `setup-cluster.sh` deploys both `floe-platform` and `floe-jobs-test`. If only one is Flux-managed, a stuck release on the other causes the same cascading failure pattern.
**Decision**: Both releases get HelmRelease CRDs. `floe-jobs-test` uses `dependsOn: floe-platform`.

## D12: Phase 1 justified despite simpler alternatives
**Rule**: Dogfooding — test what you ship.
**Context**: Architect's simplicity assessment correctly noted that `--atomic` + enhanced RBAC could solve Phase 1 alone. But Phase 2 (user-facing GitOps) requires Flux. Testing Flux on our own infrastructure validates the user experience before shipping it.
**Decision**: Proceed with Flux for Phase 1. `--atomic` is simpler but doesn't validate the GitOps path we'll recommend to users.

## D13: Three-unit decomposition
**Rule**: DISAMBIGUATION — blast radius boundaries.
**Context**: Design has Phase 1 (test infra) and Phase 2 (user GitOps). Phase 1 splits further: infrastructure provisioning (shell/YAML) vs pytest integration (Python). Phase 2 is independent of both Phase 1 sub-units.
**Decision**: Three units ordered by dependency:
1. `flux-kind-install` (shell/YAML) — Flux controllers + CRDs + setup-cluster.sh
2. `flux-test-fixtures` (Python) — pytest fixtures + conftest integration (depends on Unit 1)
3. `flux-user-gitops` (mixed) — examples + CLI + OCI publishing (independent)
**Trade-off**: Could merge Units 1+2 into a single Phase 1 unit, but they have different failure modes (shell vs Python), different test strategies, and Unit 2's integration tests require Unit 1 to be deployed. Keeping them separate enables incremental validation.

## D14: --no-flux flag for backward compatibility
**Rule**: DISAMBIGUATION — simplest viable path.
**Context**: Some CI environments (minimal runners, offline) cannot run Flux controllers. The existing direct `helm upgrade --install` path must remain available.
**Decision**: Add `--no-flux` flag (and `FLOE_NO_FLUX=1` env var) to setup-cluster.sh. Flux is the default path; flag opts out to existing behavior.
**Trade-off**: Two code paths to maintain, but ensures no regressions for environments that can't support Flux.

## D15: ConfigMap output as method on CompiledArtifacts (not standalone utility)
**Rule**: DISAMBIGUATION — follows existing pattern.
**Context**: `CompiledArtifacts` already has `to_json_file()` and `to_yaml_file()`. Adding `to_configmap_yaml()` follows the same pattern.
**Decision**: Add `to_configmap_yaml(name, namespace)` returning a string. CLI handles file I/O (consistent with how `to_yaml_file()` is used).
**Trade-off**: Adds K8s awareness to a schemas module, but the method is purely string formatting with no K8s imports.

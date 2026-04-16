# Decisions: Alpha RunLauncher Fix

## D1: Scope — K8sRunLauncher image + values hygiene only

**Decision**: Fix K8sRunLauncher image config across all values files, fix snake_case
key bug in prod/staging, correct vuln-ignore comment. No production code changes.

**Rule**: DISAMBIGUATION — user explicitly requested "long term fixes" and "not a rushed
version." The scope is bounded by the research brief's Track 1 (critical path) plus
hygiene fixes discovered during research (Track 3 comment, snake_case keys).

**Alternatives considered**: Track 2 (OpenLineage parentRun) requires no code changes
(cascade fix). Track 3 (requests CVE) is blocked by upstream — vuln-ignore comment
correction is the only actionable item.

## D2: Same image for run pods as webserver/daemon

**Decision**: Use `floe-dagster-demo:latest` (test/dev) as the run launcher image,
matching the existing webserver and daemon image config.

**Rule**: DISAMBIGUATION — single valid approach. `python_module` code locations require
the demo code to be in the run pod. The `floe-dagster-demo` image is the only image
that contains the demo modules and dbt project.

## D3: Fix snake_case key in prod/staging values

**Decision**: Fix `run_launcher` → `runLauncher` in `values-prod.yaml` and
`values-staging.yaml`. This is not a breaking change — the old key was silently
ignored, so these files never had working run launcher resource config.

**Rule**: Type 2 — locally reversible, no blast radius beyond the two files.

## D4: Add Helm unit tests for run launcher image

**Decision**: Add tests to verify the Dagster configmap renders `job_image` when
the image is configured. This prevents regression.

**Rule**: Constitution V (K8s-native testing) — structural tests for packaging per
"Structural Tests for Packaging" rule.

## D5: Do NOT update ParentRunFacet schemaURL from 1-0-1 to 1-1-0

**Decision**: Defer. The `_schemaURL` mismatch (1-0-1 vs 1-1-0) is cosmetic — Marquez
accepts both. Changing it risks breaking existing event parsing without functional
benefit. Track as tech debt for beta.

**Rule**: User requested "stable alpha" — cosmetic changes increase risk without
fixing failures.

## D6: Single work unit (no decomposition)

**Decision**: All 6 tasks are LOCAL blast radius, all touch the same domain (Helm
values files), and can be completed in a single build cycle.

**Rule**: DISAMBIGUATION — no high-blast-radius systemic components that warrant
separate units.

## D7: Demo imagePullPolicy: Never (not IfNotPresent)

**Decision**: Demo uses `pullPolicy: Never` for webserver/daemon (values-demo.yaml:50,65).
The run launcher `imagePullPolicy` MUST match: `Never`. Both demo and test use Kind
with pre-loaded images.

**Rule**: Spec pre-review identified inconsistency between initial AC-3 (`IfNotPresent`)
and existing demo convention (`Never`). Corrected to match existing convention.

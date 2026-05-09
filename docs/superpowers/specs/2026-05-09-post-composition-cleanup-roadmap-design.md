# Post-Composition Cleanup Roadmap Design

Date: 2026-05-09
Repo: `/Users/dmccarthy/Projects/floe`
Branch: `main`
Status: Approved design, pending implementation plan

## Purpose

Define the full cleanup roadmap required after the plugin-composition work landed on `main`.

This roadmap converts the post-composition audit findings into ordered cleanup workstreams. It is intentionally broader than the immediate trunk-unblocking fix, but it preserves implementation safety by separating stale residue removal from live compatibility-layer migration and new composition-contract design.

Primary evidence sources:

- `docs/validation/2026-05-09-post-composition-final-synthesis.md`
- `docs/validation/2026-05-09-post-composition-integration-audit.md`
- `docs/validation/2026-05-09-post-composition-plugin-matrix.md`
- `docs/validation/2026-05-09-post-composition-compatibility-ledger.md`
- `docs/validation/2026-05-09-post-composition-docs-truth-pass.md`
- `docs/validation/2026-05-09-post-composition-runtime-validation.md`

## Current State

The runtime product path passed remote DevPod/Hetzner validation against `origin/main` at `d9e3582a4d7d76ffaaf0b3b40bed96247fc39938` with `261 passed, 86 deselected, 7 warnings`.

Local trunk health is mixed. `make lint`, `make typecheck`, focused composition tests, focused Helm renderer tests, and Helm chart tests passed. `make test-unit` and the strict MinIO rename contract failed because stale `floe_storage_s3` / S3 alias residue remains in the local environment and generated artifacts.

The cleanup must preserve these composition constraints:

- Capabilities, requirements, typed bindings, and resolver validation own cross-plugin contracts.
- Plugins must not know another plugin's implementation details.
- `CompiledArtifacts` must remain secret-free.
- Helm/renderers consume resolved deployment bindings instead of rediscovering plugin config.
- Compatibility layers should be retired only after replacement contracts and consumers are proven.

## Cleanup Taxonomy

### Known Stale Residue

These surfaces have no valid future ownership and should be removed or regenerated.

- Stale `floe_storage_s3` registry target and S3 storage alias.
- Ignored local `plugins/floe-storage-s3` residue.
- Demo/generated artifacts that represent the Floe storage plugin as `"type": "s3"`.
- User-facing docs that still describe old status, old paths, wrong entry point groups, stale S3/LocalStack wording, or broad composability claims.

### Live Compatibility Surfaces

These surfaces are not clean target architecture, but they still have live consumers or unclear public-contract status. They require replacement contracts before removal.

- `StoragePlugin.get_pyiceberg_catalog_config()`.
- MinIO `get_helm_values_override()`.
- Dagster resource/export/validation paths that combine `artifacts.plugins.*.config` with deployment bindings.
- `floe_iceberg.writer` reflective probing for storage-owned catalog config.
- dlt sink `get_source_config(catalog_config)`.
- Semantic/Cube Helm override datasource config.

### Missing Composition Contracts

These areas need design before implementation because they affect public contracts, typed bindings, or cross-plugin ownership.

- Identity and credential-provider deployment projections.
- Binding-first Dagster/Iceberg runtime inputs.
- Compute deployment-aware profile/catalog attachment.
- Semantic datasource binding.
- RBAC policy generation from identity and plugin requirements.
- Network security policy inputs from endpoint and identity bindings.

## Recommended Approach

Use a phased contract-first cleanup.

This approach removes proven stale residue early, restores local validation, and then migrates live compatibility surfaces only when typed replacements exist. It avoids a large mixed cleanup branch where stale deletion, runtime contract migration, and docs reconciliation are reviewed as one change.

Rejected alternatives:

- One large composition cleanup epic: rejected because it mixes direct deletion with public contract redesign and would be hard to review safely.
- Docs-first only: rejected because it leaves known local unit/contract failures in place and risks producing aspirational documentation before code catches up.

## Roadmap

### Wave 1: Strict MinIO Baseline Cleanup

Goal: restore local static/unit/contract health by removing strict MinIO/S3 residue without touching live compatibility surfaces.

Scope:

- Remove stale S3 storage plugin alias/package residue after confirming ownership.
- Remove stale installed entry point or environment state that exposes `floe_storage_s3.plugin:S3StoragePlugin`.
- Regenerate or update active demo artifacts that use Floe storage plugin `"type": "s3"` to `"type": "minio"`.
- Preserve protocol-level S3-compatible uses, such as DuckDB/dbt `secrets: type: s3`.

Acceptance evidence:

- `make test-unit` passes.
- `uv run pytest tests/contract/test_storage_minio_rename.py -q` passes.
- Focused storage deployment binding tests still pass.
- No raw secrets are introduced into generated artifacts.

Non-goals:

- Do not remove `get_pyiceberg_catalog_config()`.
- Do not redesign Dagster/Iceberg runtime contracts.
- Do not remove protocol-level S3-compatible config where it is not the Floe storage plugin type.

### Wave 2: Documentation Truth Reconciliation

Goal: make current docs reflect implemented post-composition truth.

Scope:

- Reconcile `docs/architecture/plugin-composition-uplift-tracker.md` with the plugin matrix and compatibility ledger.
- Correct interface doc source paths from conceptual or stale `floe_core/interfaces/*.py` paths to live `floe_core.plugins.*` paths, or explicitly label snippets as conceptual.
- Correct identity entry point language to match the live plugin type.
- Separate strict MinIO/S3-compatible implementation truth from future native S3/GCS/Azure storage targets.
- Tighten README, `TESTING.md`, `CLAUDE.md`, and `AGENTS.md` language around alpha composition status, plugin category count, MinIO/LocalStack wording, and DevPod/Hetzner failure classification.
- Add historical banners or archive treatment for dated plans/specs when they appear in current navigation or search surfaces.

Acceptance evidence:

- Repo-native docs validators pass.
- Docs no longer imply native S3 plugin support where only MinIO/S3-compatible protocol support is implemented.
- Docs distinguish landed capabilities from remaining typed projection work.

Non-goals:

- Do not rewrite historical plans as if they were current specs.
- Do not hide audit evidence.

### Wave 3: Binding-First Dagster/Iceberg Runtime Migration

Goal: remove live runtime dependence on storage-owned catalog config by introducing a binding-first runtime contract.

Scope:

- Design a neutral runtime catalog/warehouse input contract sourced from `CompiledArtifacts.deployment`.
- Define which package owns translation from compiled bindings into PyIceberg/Dagster runtime config.
- Migrate Dagster resource/export/validation paths to use the binding-first contract.
- Migrate `floe_iceberg.writer` away from reflective `StoragePlugin.get_pyiceberg_catalog_config()` probing.
- Retain compatibility helper behavior only behind explicit migration tests until all consumers move.

Acceptance evidence:

- Contract tests prove runtime config can be built from compiled deployment bindings without raw secrets.
- Dagster runtime/export/validation tests prove no plugin implementation detail is required.
- Iceberg writer tests prove binding-first config works and legacy fallback is no longer needed or is explicitly quarantined.
- Helm renderer tests continue to prove rendered values come from deployment bindings.

Non-goals:

- Do not delete compatibility helpers before consumer migration is complete.
- Do not let Dagster discover storage/catalog plugin config independently of compiled bindings.

### Wave 4: Identity And Credential Typed Projections

Goal: move identity and credential-provider composition beyond capability validation into typed, secret-free deployment projections.

Scope:

- Add typed identity deployment projection fields for issuer, audience, workload identity mode, and credential mode metadata.
- Add typed credential-provider projection fields that carry references and provider metadata without raw secret material.
- Keep `CredentialRef` as the only representation of credential material in compiled artifacts.
- Extend resolver validation to prove required identity and credential-provider capabilities are present before emitting projections.
- Add schema and contract tests to prevent raw secrets in `CompiledArtifacts`.

Acceptance evidence:

- Compiled artifact schema tests cover the new typed projections.
- Contract tests prove projections are reference-only and secret-free.
- Resolver tests cover incompatible identity/credential-provider modes.
- Existing storage binding security tests continue to pass.

Non-goals:

- Do not add runtime secret retrieval to `CompiledArtifacts`.
- Do not make one plugin consume another plugin's concrete implementation.

### Wave 5: Secondary Composition Designs

Goal: produce separate designs for plugin families that need composition uplift but do not block the immediate runtime baseline.

Design units:

- Compute: resolver-backed deployment-aware profile/catalog attachment contract.
- Semantic: datasource binding from compute/catalog/storage projections before replacing Cube static Helm values.
- RBAC: mapping identity and plugin requirements into generated Kubernetes access policy.
- Network: typed endpoint and identity inputs for Kubernetes network policy generation.

Acceptance evidence:

- Each design identifies the owning typed binding or requirement model.
- Each design defines which plugin remains Level 0/1/2/3 and why.
- No design introduces plugin-to-plugin concrete implementation coupling.
- Each design has an explicit compatibility-retirement section if a legacy API exists.

Non-goals:

- Do not implement these as opportunistic side effects of Wave 1 or Wave 3.
- Do not uplift telemetry, lineage, quality, or alert plugins without a concrete composition trigger.

### Wave 6: Compatibility Layer Retirement

Goal: remove deprecated helpers only after replacement contracts and consumers are proven.

Scope:

- Remove or quarantine `get_pyiceberg_catalog_config()` after Dagster and Iceberg writer consumers move.
- Remove or quarantine MinIO `get_helm_values_override()` after confirming no public consumer remains and binding-owned Helm rendering is canonical.
- Decide the future of dlt sink `get_source_config(catalog_config)` after a typed binding or `CredentialRef`-only source config is designed.
- Decide the future of semantic Helm overrides after semantic datasource binding is implemented.
- Add guard tests that prevent reintroducing renderer/runtime config rediscovery from plugin config.

Acceptance evidence:

- No production source references deprecated helper APIs.
- Compatibility-removal tests fail if legacy plugin config is reintroduced as a cross-plugin contract.
- Remote DevPod runtime validation still passes.
- Local unit and contract suites stay green.

Non-goals:

- Do not remove compatibility APIs solely because they are ugly.
- Do not preserve compatibility APIs indefinitely when no live consumer remains.

## Workstream Dependencies

Wave 1 can start immediately.

Wave 2 can run after or in parallel with Wave 1, but should not claim code behavior that Wave 1 has not landed.

Wave 3 depends on a short design checkpoint because it changes runtime ownership boundaries.

Wave 4 depends on a design checkpoint because it extends compiled artifact contracts and secret handling.

Wave 5 should be decomposed into separate specs. These workstreams are related, but they should not share a single implementation PR.

Wave 6 depends on Wave 3 and the relevant Wave 5 workstream. Compatibility removal is the final step, not the first step.

## Out Of Scope

- Provider compatibility spike.
- Product fixes during roadmap design.
- Direct plugin implementation changes in this design artifact.
- Compatibility-layer removal without replacement contract and consumer migration.
- Mutation of retired feature worktrees.
- Treating historical plans/specs as current behavior.
- Claiming unpublished local audit docs were remote-tested as product code.

## Risks

- Removing broad `s3` strings can break valid S3-compatible protocol config. Cleanup must distinguish Floe storage plugin type from protocol-level S3 settings.
- Migrating Dagster/Iceberg runtime config without a typed replacement can reintroduce tight coupling or config rediscovery.
- Identity/credential projections can accidentally leak secrets if they carry values instead of references.
- Docs can become aspirational again if updated ahead of implementation evidence.
- Large combined cleanup PRs can hide regressions across runtime, schema, docs, and tests.

## Success Criteria

The roadmap is complete when:

- Local trunk validation and strict MinIO contract pass.
- Remote DevPod runtime remains green.
- Current docs align with implemented source and validation truth.
- Runtime consumers use resolved deployment bindings for cross-plugin contracts.
- `CompiledArtifacts` remains secret-free.
- Deprecated compatibility helpers either have no live consumers and are removed, or are explicitly quarantined with rationale and tests.
- Plugin families with composition triggers have explicit Level 1/2/3 decisions backed by designs or implementation evidence.

# Post-Composition Documentation Truth Pass

Date: 2026-05-09
Repo: /Users/dmccarthy/Projects/floe
Branch: main
Scope: Audit evidence only; no product-code or user-facing doc fixes.

## Commands Run

| Command | Result | Evidence |
| --- | --- | --- |
| `find docs -type f -name '*.md' \| sort` | Completed | 295 Markdown files inventoried. |
| `rg -n "composition\|composability\|deployment binding\|storage binding\|compiled artifacts\|CompiledArtifacts\|MinIO\|floe-storage-minio\|floe-storage-s3\|storage: s3\|type: s3\|Polaris\|identity mode\|credential mode\|CredentialRef\|secret\|Helm\|renderer\|get_helm_values_override\|get_pyiceberg_catalog_config\|dlt\|Iceberg writer\|DevPod\|Hetzner\|TODO\|TBD\|aspirational\|target state\|legacy\|deprecated" docs README.md TESTING.md CLAUDE.md AGENTS.md -g '*.md'` | Completed | 4,644 hits. Hits were triaged into current docs, validation docs, and dated planning/history. |
| `rg -n "docs/superpowers\|docs/requirements\|docs/research\|plugin-composition-uplift-tracker\|storage-minio\|identity-secret\|dlt-ingestion\|composition-closeout" docs README.md TESTING.md CLAUDE.md AGENTS.md -g '*.md'` | Completed | 212 hits. Current-doc links mainly point to the composition tracker and ADR/research provenance; most plan/spec hits are under historical directories. |
| `rg -n "markdown\|link\|lychee\|markdownlint\|mdformat\|remark\|vale\|mkdocs\|docs" Makefile pyproject.toml .pre-commit-config.yaml` | Completed | Repo-native docs validators found: `make docs-validate`, `testing/ci/validate-docs-navigation.py`, `testing/ci/validate-docs-content.py`, and docs-site validation scripts. No standalone external link checker such as lychee was configured. |
| `rg -n "link\|href\|missing\|exists\|markdown" testing/ci/validate-docs-navigation.py docs-site/scripts/check-source-docs.mjs docs-site/scripts/check-built-docs.mjs` | Completed | `testing/ci/validate-docs-navigation.py` checks local Markdown links for published docs; docs-site scripts check source and built-site link/path invariants. |
| `uv run python testing/ci/validate-docs-navigation.py` | Pass | Exit 0; no navigation or published Markdown link errors emitted. |
| `uv run python testing/ci/validate-docs-content.py` | Pass | Exit 0; output: `docs content validation passed`. |

## Inventory Summary

| Area | Count | Classification | Notes |
| --- | ---: | --- | --- |
| Architecture overview and ADRs | 79 | Mixed: Authoritative current plus Needs reconciliation plus Historical only | Current overview and composition/storage docs mostly point in the right direction, but the composition tracker and several interface/ADR pages can mislead implementers about status, entry points, and live ABC paths. |
| Plugin system/interface docs | Included in architecture count | Needs reconciliation | Storage and catalog pages describe the binding-first model well. Interface index and several interface pages still cite `floe_core/interfaces/*.py`, while implementation lives under `floe_core/plugins/*.py`. Identity and secrets pages describe capability validation but also show stale interface snippets and, for identity, the wrong entry point group. |
| Contract docs | 5 | Authoritative current | `docs/contracts/compiled-artifacts.md` is the best current narrative for secret-free deployment bindings, renderer ownership, `CredentialRef`, and `COMPOSITION_*` diagnostics. Some broader contract pages include planned root lifecycle commands, but they are explicitly caveated. |
| Testing docs | 2 docs plus root `TESTING.md` | Needs reconciliation | Current lane separation and dlt E2E material is useful. `TESTING.md` still names `S3 (LocalStack)` in the integration-test service table while the post-composition service path is MinIO/Polaris. |
| User-facing README/CLAUDE/AGENTS docs | 4 top-level docs | Needs reconciliation | README is mostly alpha-caveated but still uses broad composability/default-stack language. `CLAUDE.md` and `AGENTS.md` carry older plugin counts, S3/MinIO phrasing, and target-state wording that should be reconciled with implementation truth. |
| Validation docs | 10 | Authoritative current for audit trail; older files Historical only | The 2026-05-09 post-composition validation docs are current audit evidence. Earlier alpha/release validation files are historical evidence, not current product behavior. |
| Historical specs/plans/requirements/research | 123 | Historical only or Remove/Archive candidate | `docs/superpowers/**`, `docs/plans/**`, `docs/requirements/**`, and `docs/research/**` are useful provenance. They should not be treated as current implementation contracts unless a current architecture page explicitly promotes them. Superseded dated plans are archive candidates rather than live docs. |
| Other docs: analysis, audits, internal, security, releases | 19 | Mixed Historical only and Needs reconciliation | Useful for provenance and release history. Not authoritative for post-composition runtime ownership unless cross-linked from current product docs. |

## Key Findings

| Classification | Files | Finding | Next action |
| --- | --- | --- | --- |
| Authoritative current | `docs/contracts/compiled-artifacts.md` | Accurately describes `CompiledArtifacts.deployment`, secret-free deployment bindings, catalog/runtime projections, renderer output ownership, `CredentialRef`, and `COMPOSITION_*` diagnostics. | Keep as the primary contract doc; use it as the reconciliation source for stale interface and tracker docs. |
| Authoritative current | `docs/architecture/interfaces/storage-plugin.md`, `docs/architecture/interfaces/catalog-plugin.md`, `docs/architecture/plugin-system/interfaces.md` storage section | Correctly states that storage emits neutral desired state, `floe-core` resolves compatibility, catalog/compute/orchestrator/renderers translate owned bindings, and legacy helper methods are compatibility surface. | Keep, then update examples when legacy storage helper methods are actually removed. |
| Authoritative current | `docs/reference/plugin-catalog.md` | Matches implementation truth that `PluginType` defines 15 categories and `PluginType.LINEAGE` is a code alias rather than an extra category. | Keep as the canonical public plugin category reference. |
| Needs reconciliation | `docs/architecture/plugin-composition-uplift-tracker.md` | Still says the immediate Iceberg path is "In storage composition PR" after the post-composition closeout. It marks PCU-005 implemented, while the matrix/ledger still call for typed credential-provider and identity deployment projections. It also lists remote E2E and direct Hetzner cleanup as storage PR exit criteria, but the integration audit records those lanes as not run. | Reconcile statuses against `docs/validation/2026-05-09-post-composition-plugin-matrix.md` and `docs/validation/2026-05-09-post-composition-compatibility-ledger.md`; distinguish landed capability validation from remaining deployment-binding work. |
| Needs reconciliation | `docs/architecture/interfaces/index.md`, `docs/architecture/interfaces/*.md` | Interface pages cite `floe_core/interfaces/*.py`, but source truth is `packages/floe-core/src/floe_core/plugins/*.py`. This affects compute, orchestrator, catalog, storage, telemetry, lineage, dbt, semantic, ingestion, quality, secrets, and identity pages. | Update interface locations to implementation paths, or explicitly label snippets as conceptual target interfaces. |
| Needs reconciliation | `docs/architecture/interfaces/identity-plugin.md` | Says entry point is `floe.identities`, but `PluginType.IDENTITY` uses `floe.identity`. The interface snippet describes client creation/OIDC methods and `generate_helm_values()`, while the live ABC is under `floe_core.plugins.identity` and now includes `get_identity_capabilities()` as the composition bridge. | Align entry point, live ABC path, and capability-vs-deployment-projection status. |
| Needs reconciliation | `docs/architecture/interfaces/secrets-plugin.md`, `docs/architecture/adr/0023-secrets-management.md`, `docs/architecture/adr/0031-infisical-secrets.md` | Secret docs describe secret retrieval/storage APIs and default secret-management direction, but the post-composition implementation currently validates `get_secret_capabilities()` and still lacks a typed credential deployment projection. Some ADR snippets include old `floe_core/interfaces/secrets.py` paths and secret CLI examples. | Mark older ADR content as historical where appropriate; update current interface docs to the capability-only bridge and remaining typed projection gap. |
| Needs reconciliation | `docs/architecture/storage-integration.md`, `docs/architecture/adr/0036-storage-plugin-interface.md` | These pages mix current MinIO/S3-compatible protocol guidance with broader native S3/GCS/Azure target-state material. The current audit found strict `floe-storage-minio` is the implemented path, stale `floe-storage-s3` residue is broken, and native S3 should not be implied as current implementation truth. | Separate S3-compatible protocol language from a native `s3` storage plugin; mark native cloud storage sections as target or future unless implemented. |
| Needs reconciliation | `README.md` | Mostly alpha-caveated, but broad "Full composability" and "batteries-included OSS defaults" wording can overstate current post-composition completeness while matrix items still require runtime/binding design for compute, Dagster, Iceberg writer, identity, RBAC, network, and semantic composition. | Tighten public claims around alpha-supported composition and provider-swap status. |
| Needs reconciliation | `TESTING.md` | The service matrix says integration tests require `S3 (LocalStack)`, while current dlt/platform lanes and Helm values use MinIO with Polaris. DevPod/Hetzner lane separation is otherwise useful and should remain separate from product failure classification. | Replace stale LocalStack/S3 wording with MinIO/S3-compatible protocol wording; preserve DevPod/Hetzner infra-vs-product separation. |
| Needs reconciliation | `CLAUDE.md`, `AGENTS.md` | Agent docs still include older plugin counts or simplified target-state phrasing and use broad S3/MinIO language. `AGENTS.md` also says integration tests use "Polaris, S3, PostgreSQL" and older plugin type counts even though implementation truth is 15 categories. | Reconcile agent docs with `docs/reference/plugin-catalog.md`, `docs/contracts/compiled-artifacts.md`, and current testing lanes. |
| Historical only | `docs/superpowers/plans/**`, `docs/superpowers/specs/**`, especially storage/dlt/identity/composition plans | Dated implementation plans include old snippets and transitional commands such as historical `storage: s3` examples. They are valuable provenance, not current user-facing contract. | Keep as history; add historical banners only if linked from current public docs. |
| Historical only | `docs/requirements/**`, `docs/plans/**`, `docs/research/**` | Requirements, epics, and research describe intended design or spike evidence. Current docs link to some of these for provenance, but they should not override implemented source/validation docs. | Treat as historical or archive candidates; avoid using them as source of truth without a current reconciliation page. |
| Remove/Archive candidate | Superseded dated plans such as `docs/superpowers/plans/2026-05-05-storage-minio-architecture.md` | Some plans are explicitly superseded by later closeout plans. They are not wrong as history, but they are noisy if surfaced as current implementation guidance. | Archive or clearly fence from current docs navigation/search surfaces. |

## Current Truth Anchors

- Implementation plugin category truth: `packages/floe-core/src/floe_core/plugin_types.py`.
- Composition and error-code truth: `packages/floe-core/src/floe_core/composition/`, `packages/floe-core/src/floe_core/compilation/stages.py`.
- Deployment binding schema truth: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`.
- Storage implementation truth: `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py`.
- Helm renderer ownership truth: `packages/floe-core/src/floe_core/cli/helm/generate.py`.
- Runtime compatibility surfaces still live: `StoragePlugin.get_pyiceberg_catalog_config()`, MinIO `get_helm_values_override()`, Dagster Iceberg resource/export/validation paths, and `floe_iceberg.writer`.
- Validation truth for remaining work: `docs/validation/2026-05-09-post-composition-plugin-matrix.md`, `docs/validation/2026-05-09-post-composition-compatibility-ledger.md`, and `docs/validation/2026-05-09-post-composition-integration-audit.md`.

## Recommended Documentation Follow-Ups

1. Reconcile the composition tracker with the post-composition matrix and compatibility ledger.
2. Correct interface doc source paths and entry point groups against `floe_core.plugins.*` and `PluginType`.
3. Separate current strict MinIO/S3-compatible implementation truth from future native S3/GCS/Azure storage targets.
4. Update identity/secrets docs to distinguish capability validation from missing typed deployment projections.
5. Update testing and agent docs to remove stale LocalStack/S3 and plugin-count language.
6. Add historical banners or archive treatment for dated superpowers/plans/requirements/research artifacts that are likely to appear in search results.

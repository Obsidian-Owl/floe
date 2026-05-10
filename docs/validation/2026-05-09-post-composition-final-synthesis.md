# Post-Composition Final Audit Synthesis

Date: 2026-05-09
Repo: `/Users/dmccarthy/Projects/floe`
Branch: `main`
Purpose: Evidence summary and follow-up specification source. This audit did not change product code.

## Final Verdict

| Area | Verdict | Evidence |
| --- | --- | --- |
| Product runtime after composition | Passed | Remote DevPod E2E validated `origin/main` at `d9e3582a4d7d76ffaaf0b3b40bed96247fc39938` with `261 passed, 86 deselected, 7 warnings`. |
| Local trunk static/unit/contract health | Mixed | `make lint`, `make typecheck`, focused composition tests, focused Helm renderer tests, and Helm chart tests passed. `make test-unit` and the strict MinIO rename contract failed because stale `floe_storage_s3` / S3 alias residue remains in the local environment and generated artifacts. |
| Infra and cleanup | Passed | DevPod workspace teardown completed; post-run `devpod list` was empty; direct Hetzner API inventory found no current-run servers, volumes, or SSH keys. |

Branch status: local `main` is ahead of `origin/main` by audit documentation commits. Runtime validation used remote `origin/main`, so the validated product code equals `d9e3582a4d7d76ffaaf0b3b40bed96247fc39938`; unpublished local audit documentation commits were not remote-tested as product code.

## Evidence Map

| Evidence | Path | Key commands or checks |
| --- | --- | --- |
| Integration audit ledger | [2026-05-09-post-composition-integration-audit.md](2026-05-09-post-composition-integration-audit.md) | `make lint`; `make typecheck`; `make test-unit`; focused composition, schema, contract, and Helm tests; baseline finding ledger. |
| Plugin composability matrix | [2026-05-09-post-composition-plugin-matrix.md](2026-05-09-post-composition-plugin-matrix.md) | Per-plugin Level 0-3 assessment and follow-up decisions. |
| Compatibility and dead-code ledger | [2026-05-09-post-composition-compatibility-ledger.md](2026-05-09-post-composition-compatibility-ledger.md) | Compatibility search, filename sweep, stale S3 path triage, live legacy helper surfaces. |
| Documentation truth pass | [2026-05-09-post-composition-docs-truth-pass.md](2026-05-09-post-composition-docs-truth-pass.md) | Docs inventory, stale-language searches, `uv run python testing/ci/validate-docs-navigation.py`, `uv run python testing/ci/validate-docs-content.py`. |
| Runtime validation | [2026-05-09-post-composition-runtime-validation.md](2026-05-09-post-composition-runtime-validation.md) | `DEVPOD_WORKSPACE=floe-postcomp-audit make devpod-test`; `devpod list`; direct Hetzner Cloud API inventory. |

## Top Findings

| Severity | Finding | Why it matters | Follow-up disposition |
| --- | --- | --- | --- |
| High | Stale S3 alias, package, and generated artifacts remain. | `make test-unit` and `tests/contract/test_storage_minio_rename.py` fail because the runtime registry still exposes `floe_storage_s3.plugin:S3StoragePlugin`, ignored local `plugins/floe-storage-s3` residue exists, and demo compiled artifacts still contain `"type": "s3"`. | Remove stale path and restore local unit/contract baseline. |
| High | Live Dagster/Iceberg runtime compatibility surfaces still consume legacy storage-owned catalog config. | Dagster resource/export/validation paths and `floe_iceberg.writer` still call or probe `StoragePlugin.get_pyiceberg_catalog_config()` and overlay binding data, so compatibility-layer removal needs a binding-first migration. | Design and migrate the runtime contract before removing compatibility helpers. |
| Medium | Documentation truth is not fully reconciled with implementation truth. | The composition tracker, interface docs, testing docs, README, and agent docs still contain stale status, old interface paths, S3/LocalStack wording, plugin-count drift, or over-broad composability claims. | Run a documentation reconciliation pass anchored to the validation files and current source paths. |
| Medium | Identity and secrets composition stops at capability validation. | Credential-provider and identity plugins expose capabilities, but the compiled contract does not yet emit typed, secret-free credential or identity deployment projections. | Design and implement `CredentialRef`-only typed projections. |
| Medium | Compute, semantic, RBAC, and network composition need explicit designs before implementation. | DuckDB profile augmentation, Cube datasource config, Kubernetes RBAC, and network policy generation have composition triggers but lack complete typed binding/resolver contracts. | Treat as later design workstreams rather than opportunistic fixes. |
| Low | Secret scan and generated local artifacts are baseline hygiene concerns. | The audit recorded existing secret-scan findings and ignored local generated artifacts, but neither changed the remote product runtime verdict. | Address in cleanup or security-baseline work, not in this synthesis. |

## Ordered Follow-Up Workstreams

1. Strict MinIO cleanup to restore local unit/contract baseline.
   - Remove stale S3 package/entry-point residue after ownership checks.
   - Regenerate or update active demo artifacts from `type: s3` to `type: minio` where they represent the Floe storage plugin.
   - Preserve protocol-level S3-compatible usages such as DuckDB/dbt secret `type: s3`.
   - Acceptance evidence: `make test-unit` and `uv run pytest tests/contract/test_storage_minio_rename.py -q` pass.

2. Binding-first Dagster/Iceberg runtime contract migration.
   - Define the runtime catalog/warehouse input contract sourced from compiled deployment bindings.
   - Migrate Dagster resource/export/validation paths and `floe_iceberg.writer` away from storage-owned catalog config.
   - Remove or quarantine `get_pyiceberg_catalog_config()` only after consumers move.

3. Identity/credential typed projection design and implementation.
   - Add typed identity and credential deployment projections that carry issuer, audience, credential mode, and reference metadata without raw secrets.
   - Keep `CredentialRef` as the only credential material in compiled artifacts.
   - Extend resolver, schema, and contract tests before wiring runtime consumers.

4. Documentation reconciliation pass.
   - Reconcile the composition tracker with the plugin matrix and compatibility ledger.
   - Correct interface doc paths and entry point groups against `floe_core.plugins.*` and `PluginType`.
   - Tighten README, TESTING, CLAUDE, and AGENTS language around MinIO/S3-compatible truth, plugin category count, DevPod/Hetzner lane separation, and remaining alpha composition gaps.
   - Add historical banners or archive treatment for dated plans/specs that surface in search.

5. Compute, semantic, RBAC, and network composition designs as later work.
   - Compute: resolver-backed deployment-aware profile/catalog attachment contract.
   - Semantic: datasource binding from compute/catalog/storage projections before replacing Cube static Helm values.
   - RBAC: map identity and plugin requirements into generated Kubernetes access policy.
   - Network: typed endpoint and identity inputs for policy generation.

## Explicitly Out Of Scope

- No provider compatibility spike.
- No product-code fixes.
- No direct plugin implementation changes.
- No compatibility-layer removal without design and consumer migration.
- No mutation of retired feature worktrees.
- No guarantee that unpublished local audit docs were remote-tested as product code.

## Closeout Use

Use this synthesis as the entry point for follow-up specs/plans. Use the linked ledgers for detailed evidence and exact command output summaries; do not duplicate raw logs into specs unless a specific acceptance criterion needs them.

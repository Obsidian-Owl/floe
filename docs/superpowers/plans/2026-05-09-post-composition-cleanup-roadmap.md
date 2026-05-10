# Post-Composition Cleanup Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the full post-composition cleanup roadmap without collapsing stale-residue removal, runtime contract migration, identity/credential projection work, and documentation reconciliation into one unsafe change.

**Architecture:** The plan uses a phased contract-first cleanup. Wave 1 removes proven stale MinIO/S3 residue and restores local validation; Waves 2-6 create or execute bounded follow-up workstreams for docs truth, binding-first runtime migration, identity/credential projections, secondary plugin composition designs, and final compatibility retirement.

**Tech Stack:** Python 3.10+, Pydantic v2, uv, pytest, Helm unittest, DevPod/Hetzner remote validation, Markdown validation scripts.

---

## Scope Boundary

The approved design covers multiple independent subsystems. This plan is therefore an execution roadmap with one implementation-ready cleanup wave and separate design/plan gates for cross-contract work.

Do not implement Dagster/Iceberg runtime migration, identity/credential projections, semantic datasource bindings, RBAC composition, network composition, or compatibility-helper removal inside the Wave 1 strict MinIO cleanup task.

## File Map

Wave 1 strict MinIO cleanup:

- Inspect/remove ignored local residue: `plugins/floe-storage-s3/`
- Modify: `demo/customer-360/compiled_artifacts.json`
- Modify: `demo/iot-telemetry/compiled_artifacts.json`
- Modify: `demo/financial-risk/compiled_artifacts.json`
- Verify existing tests: `tests/contract/test_storage_minio_rename.py`
- Verify existing tests: `packages/floe-core/tests/unit/plugins/test_plugin_system.py`
- Verify existing tests: `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`

Wave 2 documentation reconciliation:

- Modify: `docs/architecture/plugin-composition-uplift-tracker.md`
- Modify: `docs/architecture/interfaces/index.md`
- Modify: `docs/architecture/interfaces/catalog-plugin.md`
- Modify: `docs/architecture/interfaces/compute-plugin.md`
- Modify: `docs/architecture/interfaces/data-quality-plugin.md`
- Modify: `docs/architecture/interfaces/dbt-plugin.md`
- Modify: `docs/architecture/interfaces/ingestion-plugin.md`
- Modify: `docs/architecture/interfaces/lineage-backend-plugin.md`
- Modify: `docs/architecture/interfaces/orchestrator-plugin.md`
- Modify: `docs/architecture/interfaces/semantic-layer-plugin.md`
- Modify: `docs/architecture/interfaces/storage-plugin.md`
- Modify: `docs/architecture/interfaces/telemetry-backend-plugin.md`
- Modify: `docs/architecture/interfaces/identity-plugin.md`
- Modify: `docs/architecture/interfaces/secrets-plugin.md`
- Modify: `docs/architecture/storage-integration.md`
- Modify: `docs/architecture/adr/0036-storage-plugin-interface.md`
- Modify: `README.md`
- Modify: `TESTING.md`
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`

Wave 3 binding-first runtime migration design:

- Create: `docs/superpowers/specs/2026-05-09-binding-first-dagster-iceberg-runtime-design.md`

Wave 4 identity/credential projection design:

- Create: `docs/superpowers/specs/2026-05-09-identity-credential-projections-design.md`

Wave 5 secondary composition design decomposition:

- Create: `docs/superpowers/specs/2026-05-09-compute-composition-contract-design.md`
- Create: `docs/superpowers/specs/2026-05-09-semantic-datasource-binding-design.md`
- Create: `docs/superpowers/specs/2026-05-09-rbac-composition-design.md`
- Create: `docs/superpowers/specs/2026-05-09-network-security-composition-design.md`

Wave 6 compatibility retirement:

- Create: `docs/superpowers/specs/2026-05-09-compatibility-retirement-design.md`

## Task 1: Strict MinIO Cleanup Preflight

**Files:**
- Read: `tests/contract/test_storage_minio_rename.py`
- Read: `pyproject.toml`
- Inspect: `plugins/floe-storage-s3/`
- Inspect: `demo/customer-360/compiled_artifacts.json`
- Inspect: `demo/iot-telemetry/compiled_artifacts.json`
- Inspect: `demo/financial-risk/compiled_artifacts.json`

- [ ] **Step 1: Confirm branch and workspace state**

Run:

```bash
git status --short --branch
git worktree list --porcelain
git branch --format='%(refname:short)'
```

Expected:

- Current branch is `main`.
- Worktree is clean before edits.
- Only local branch listed is `main`.
- Only root worktree `/Users/dmccarthy/Projects/floe` is listed.

- [ ] **Step 2: Confirm stale S3 residue is ignored local state**

Run:

```bash
git ls-files plugins/floe-storage-s3
git status --ignored --short plugins/floe-storage-s3
```

Expected:

- `git ls-files plugins/floe-storage-s3` prints no tracked files.
- `git status --ignored --short plugins/floe-storage-s3` prints `!! plugins/floe-storage-s3/`.

- [ ] **Step 3: Confirm the existing strict MinIO contract failure**

Run:

```bash
uv run pytest tests/contract/test_storage_minio_rename.py -q
```

Expected before cleanup:

- Fails on the stale ignored package directory, stale runtime S3 alias, or active `"type": "s3"` generated artifact references.
- If this unexpectedly passes, stop and inspect `git status --ignored --short plugins/floe-storage-s3` before editing.

- [ ] **Step 4: Confirm root workspace metadata is already MinIO-only**

Run:

```bash
rg -n "floe-storage-minio|floe-storage-s3|floe_storage_s3" pyproject.toml uv.lock plugins/floe-storage-minio/pyproject.toml
```

Expected:

- `pyproject.toml` and `uv.lock` reference `floe-storage-minio`.
- No tracked root workspace metadata references `floe-storage-s3` or `floe_storage_s3`.

## Task 2: Remove Ignored S3 Package Residue And Environment Alias

**Files:**
- Remove local ignored directory: `plugins/floe-storage-s3/`
- No tracked file changes expected in this task unless the environment lock metadata unexpectedly references S3.

- [ ] **Step 1: Remove ignored S3 package residue after ownership check**

Run:

```bash
test -z "$(git ls-files plugins/floe-storage-s3)"
rm -rf plugins/floe-storage-s3
git status --ignored --short plugins/floe-storage-s3
```

Expected:

- The `test -z ...` command exits 0.
- `git status --ignored --short plugins/floe-storage-s3` prints nothing after removal.

- [ ] **Step 2: Remove stale installed editable package if present**

Run:

```bash
uv pip list | rg '^floe-storage-s3\\b|^floe-storage-minio\\b' || true
uv pip uninstall floe-storage-s3 || true
uv pip list | rg '^floe-storage-s3\\b|^floe-storage-minio\\b' || true
```

Expected:

- Final package list does not include `floe-storage-s3`.
- Final package list includes `floe-storage-minio`.

- [ ] **Step 3: Refresh the uv environment from the workspace**

Run:

```bash
uv sync
```

Expected:

- Sync completes without reinstalling `floe-storage-s3`.

- [ ] **Step 4: Verify runtime plugin registry no longer exposes the S3 alias**

Run:

```bash
uv run pytest tests/contract/test_storage_minio_rename.py::test_runtime_plugin_registry_exposes_minio_without_s3_alias -q
```

Expected:

- Test passes.
- If it fails with `floe_storage_s3.plugin:S3StoragePlugin`, inspect editable installs and entry point metadata before changing product code.

- [ ] **Step 5: Commit environment-residue cleanup only if tracked files changed**

Run:

```bash
git status --short
```

Expected:

- If no tracked files changed, do not create a commit for this task.
- If tracked lock or metadata files changed, review them and commit:

```bash
git add pyproject.toml uv.lock
git commit -m "Remove stale S3 storage package metadata"
```

## Task 3: Regenerate Or Correct Active Demo Compiled Artifacts

**Files:**
- Modify: `demo/customer-360/compiled_artifacts.json`
- Modify: `demo/iot-telemetry/compiled_artifacts.json`
- Modify: `demo/financial-risk/compiled_artifacts.json`

- [ ] **Step 1: Confirm each stale artifact reference is a Floe storage plugin identity**

Run:

```bash
rg -n '"storage"|"type": "s3"|"endpoint": "http://floe-platform-minio:9000"' demo/customer-360/compiled_artifacts.json demo/iot-telemetry/compiled_artifacts.json demo/financial-risk/compiled_artifacts.json
```

Expected:

- Each file has a `plugins.storage.type` value of `"s3"`.
- The same storage block points at `http://floe-platform-minio:9000`, so this is a stale plugin identity and not protocol-level `s3://` syntax.

- [ ] **Step 2: Edit only the storage plugin type**

Use `apply_patch` to change exactly this field in each of the three demo artifacts:

```json
"storage": {
  "type": "minio",
  "version": "0.0.0",
  "config": {
```

Do not change `warehouse_path`, S3-compatible endpoint keys, Polaris Helm keys, or `s3://` URI strings.

- [ ] **Step 3: Validate JSON syntax**

Run:

```bash
uv run python -m json.tool demo/customer-360/compiled_artifacts.json >/dev/null
uv run python -m json.tool demo/iot-telemetry/compiled_artifacts.json >/dev/null
uv run python -m json.tool demo/financial-risk/compiled_artifacts.json >/dev/null
```

Expected:

- All commands exit 0.

- [ ] **Step 4: Run strict MinIO rename contract**

Run:

```bash
uv run pytest tests/contract/test_storage_minio_rename.py -q
```

Expected:

- All tests pass.

- [ ] **Step 5: Run focused storage composition tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py tests/contract/test_storage_binding_security.py -q
```

Expected:

- All tests pass.
- Output includes `tests/contract/test_storage_binding_security.py` passing, proving generated binding paths remain secret-free.

- [ ] **Step 6: Commit demo artifact cleanup**

Run:

```bash
git add demo/customer-360/compiled_artifacts.json demo/iot-telemetry/compiled_artifacts.json demo/financial-risk/compiled_artifacts.json
git commit -m "Replace stale S3 demo storage plugin references"
```

## Task 4: Restore Local Unit Baseline

**Files:**
- Verify existing tests: `packages/floe-core/tests/unit/plugins/test_plugin_system.py`
- Verify existing tests: `tests/contract/test_storage_minio_rename.py`
- Verify existing tests: `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`
- Verify existing tests: `packages/floe-core/tests/unit/helm/test_generate_cli.py`

- [ ] **Step 1: Run the plugin system tests that failed in the audit**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/plugins/test_plugin_system.py -q
```

Expected:

- Tests pass.
- No failure mentions `floe_storage_s3.plugin`.

- [ ] **Step 2: Run full unit suite**

Run:

```bash
make test-unit
```

Expected:

- Unit suite passes.
- If unrelated failures appear, classify them separately and do not hide the stale-S3 cleanup result.

- [ ] **Step 3: Run focused Helm renderer checks**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/helm/test_generate_cli.py -q
helm unittest charts/floe-platform
```

Expected:

- Both commands pass.
- Helm output still contains `polaris.storage.s3.*` only as Polaris chart storage protocol config, not as Floe storage plugin identity.

- [ ] **Step 4: Run static gates**

Run:

```bash
make lint
make typecheck
```

Expected:

- Both commands pass.

- [ ] **Step 5: Record Wave 1 validation evidence**

Modify or add a validation note only if the cleanup PR needs an evidence record. Preferred path:

```text
docs/validation/2026-05-09-post-composition-strict-minio-cleanup.md
```

Include:

- Commands run.
- Pass/fail result.
- Explanation that protocol-level S3-compatible config was preserved.
- Explanation that stale Floe storage plugin `s3` identity was removed.

- [ ] **Step 6: Commit validation evidence if created**

Run:

```bash
git add docs/validation/2026-05-09-post-composition-strict-minio-cleanup.md
git commit -m "Record strict MinIO cleanup validation"
```

Skip this commit if no validation note was created.

## Task 5: Documentation Truth Reconciliation

**Files:**
- Modify: `docs/architecture/plugin-composition-uplift-tracker.md`
- Modify: `docs/architecture/interfaces/index.md`
- Modify: `docs/architecture/interfaces/catalog-plugin.md`
- Modify: `docs/architecture/interfaces/compute-plugin.md`
- Modify: `docs/architecture/interfaces/data-quality-plugin.md`
- Modify: `docs/architecture/interfaces/dbt-plugin.md`
- Modify: `docs/architecture/interfaces/ingestion-plugin.md`
- Modify: `docs/architecture/interfaces/lineage-backend-plugin.md`
- Modify: `docs/architecture/interfaces/orchestrator-plugin.md`
- Modify: `docs/architecture/interfaces/semantic-layer-plugin.md`
- Modify: `docs/architecture/interfaces/storage-plugin.md`
- Modify: `docs/architecture/interfaces/telemetry-backend-plugin.md`
- Modify: `docs/architecture/interfaces/identity-plugin.md`
- Modify: `docs/architecture/interfaces/secrets-plugin.md`
- Modify: `docs/architecture/storage-integration.md`
- Modify: `docs/architecture/adr/0036-storage-plugin-interface.md`
- Modify: `README.md`
- Modify: `TESTING.md`
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Re-run the docs truth search**

Run:

```bash
rg -n "composition|composability|deployment binding|storage binding|compiled artifacts|CompiledArtifacts|MinIO|floe-storage-minio|floe-storage-s3|storage: s3|type: s3|Polaris|identity mode|credential mode|CredentialRef|secret|Helm|renderer|get_helm_values_override|get_pyiceberg_catalog_config|dlt|Iceberg writer|DevPod|Hetzner|target state|legacy|deprecated" docs README.md TESTING.md CLAUDE.md AGENTS.md -g '*.md'
```

Expected:

- Hits match the docs truth pass categories: current docs, validation docs, and historical dated plans.

- [ ] **Step 2: Update current docs to implementation truth**

Make only current user-facing docs changes:

- Composition tracker distinguishes landed MinIO/storage composition from remaining credential, identity, Dagster/Iceberg, semantic, RBAC, and network work.
- Interface docs reference live `packages/floe-core/src/floe_core/plugins/*.py` paths or explicitly label snippets as conceptual.
- Identity docs use the live `floe.identity` entry point group.
- Testing docs say MinIO/S3-compatible protocol rather than LocalStack/native S3 for the implemented lane.
- README and agent docs describe current alpha composition scope without claiming complete provider interchangeability.

- [ ] **Step 3: Preserve historical plans**

Do not rewrite dated `docs/superpowers/**`, `docs/requirements/**`, or `docs/research/**` as current truth. If a current doc links to a dated plan as guidance, change the current doc text so the link is explicitly historical.

- [ ] **Step 4: Run repo-native docs validators**

Run:

```bash
uv run python testing/ci/validate-docs-navigation.py
uv run python testing/ci/validate-docs-content.py
```

Expected:

- Both commands pass.

- [ ] **Step 5: Commit documentation reconciliation**

Run:

```bash
git add README.md TESTING.md CLAUDE.md AGENTS.md docs/architecture/plugin-composition-uplift-tracker.md docs/architecture/interfaces/index.md docs/architecture/interfaces/catalog-plugin.md docs/architecture/interfaces/compute-plugin.md docs/architecture/interfaces/data-quality-plugin.md docs/architecture/interfaces/dbt-plugin.md docs/architecture/interfaces/identity-plugin.md docs/architecture/interfaces/ingestion-plugin.md docs/architecture/interfaces/lineage-backend-plugin.md docs/architecture/interfaces/orchestrator-plugin.md docs/architecture/interfaces/secrets-plugin.md docs/architecture/interfaces/semantic-layer-plugin.md docs/architecture/interfaces/storage-plugin.md docs/architecture/interfaces/telemetry-backend-plugin.md docs/architecture/storage-integration.md docs/architecture/adr/0036-storage-plugin-interface.md
git commit -m "Reconcile post-composition documentation truth"
```

## Task 6: Binding-First Dagster/Iceberg Runtime Design

**Files:**
- Create: `docs/superpowers/specs/2026-05-09-binding-first-dagster-iceberg-runtime-design.md`

- [ ] **Step 1: Map current live consumers**

Run:

```bash
rg -n "get_pyiceberg_catalog_config|artifacts\\.plugins\\.(storage|catalog)\\.config|StorageDeploymentBinding|CatalogDeploymentBinding|_catalog_connection_config_from_binding" plugins/floe-orchestrator-dagster packages/floe-iceberg packages/floe-core -g '*.py'
```

Expected:

- Hits include Dagster resource/export/validation paths and `packages/floe-iceberg/src/floe_iceberg/writer.py`.

- [ ] **Step 2: Write the runtime design spec**

Create `docs/superpowers/specs/2026-05-09-binding-first-dagster-iceberg-runtime-design.md` with these sections:

```markdown
# Binding-First Dagster/Iceberg Runtime Design

Date: 2026-05-09
Status: Draft for review

## Goal

Migrate Dagster and `floe_iceberg.writer` runtime connection setup from storage-owned catalog config to a neutral runtime input derived from `CompiledArtifacts.deployment`.

## Current Consumers

- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py`
- `packages/floe-iceberg/src/floe_iceberg/writer.py`

## Proposed Contract

Define a runtime catalog connection object derived from storage and catalog deployment bindings. The object carries endpoint, warehouse, path-style, region, and credential-reference metadata without raw secrets.

## Ownership

`floe-core` owns compiled deployment binding schema. Runtime packages own translation into their execution library config. Storage and catalog plugins do not expose cross-plugin implementation config to other plugins.

## Migration Plan

1. Add tests for constructing runtime config from compiled deployment bindings.
2. Migrate Dagster resource/export/validation paths.
3. Migrate `floe_iceberg.writer`.
4. Remove or quarantine `StoragePlugin.get_pyiceberg_catalog_config()` after no production consumer remains.

## Acceptance Evidence

- Contract tests prove runtime config is derived from deployment bindings.
- Dagster tests pass without storage-owned catalog config.
- Iceberg writer tests pass without reflective helper probing.
- Secret-free compiled artifact tests pass.
```

- [ ] **Step 3: Commit the runtime design spec**

Run:

```bash
git add docs/superpowers/specs/2026-05-09-binding-first-dagster-iceberg-runtime-design.md
git commit -m "Design binding-first Dagster Iceberg runtime"
```

## Task 7: Identity And Credential Projection Design

**Files:**
- Create: `docs/superpowers/specs/2026-05-09-identity-credential-projections-design.md`

- [ ] **Step 1: Map current identity and credential capability surfaces**

Run:

```bash
rg -n "get_identity_capabilities|get_secret_capabilities|CredentialRef|credential.*capabil|identity.*capabil|floe\\.identity|floe\\.secrets" packages plugins docs/architecture -g '*.py' -g '*.md' -g '*.toml'
```

Expected:

- Hits include `plugins/floe-identity-keycloak`, `plugins/floe-secrets-k8s`, `plugins/floe-secrets-infisical`, `CredentialRef`, and compilation stages capability validation.

- [ ] **Step 2: Write the projection design spec**

Create `docs/superpowers/specs/2026-05-09-identity-credential-projections-design.md` with these sections:

```markdown
# Identity And Credential Projection Design

Date: 2026-05-09
Status: Draft for review

## Goal

Extend composition from capability validation to typed, secret-free identity and credential deployment projections.

## Proposed Projections

- Identity projection: issuer, audience, workload identity mode, token audience metadata, and provider reference.
- Credential projection: provider reference, supported credential modes, and `CredentialRef` fields for runtime lookup.

## Secret Handling

Compiled artifacts carry references only. Raw tokens, passwords, client secrets, and provider secret values remain outside `CompiledArtifacts`.

## Resolver Validation

Resolver validation fails when selected plugins require identity or credential modes that the configured providers cannot satisfy.

## Acceptance Evidence

- Schema tests cover the new projection models.
- Contract tests prove projection JSON contains references but no raw secret material.
- Resolver tests cover compatible and incompatible mode combinations.
```

- [ ] **Step 3: Commit the projection design spec**

Run:

```bash
git add docs/superpowers/specs/2026-05-09-identity-credential-projections-design.md
git commit -m "Design identity and credential projections"
```

## Task 8: Secondary Composition Design Decomposition

**Files:**
- Create: `docs/superpowers/specs/2026-05-09-compute-composition-contract-design.md`
- Create: `docs/superpowers/specs/2026-05-09-semantic-datasource-binding-design.md`
- Create: `docs/superpowers/specs/2026-05-09-rbac-composition-design.md`
- Create: `docs/superpowers/specs/2026-05-09-network-security-composition-design.md`

- [ ] **Step 1: Create compute composition design**

Create `docs/superpowers/specs/2026-05-09-compute-composition-contract-design.md` with:

```markdown
# Compute Composition Contract Design

Date: 2026-05-09
Status: Draft for review

## Goal

Define resolver-backed deployment-aware compute profile and catalog attachment behavior.

## Current Trigger

DuckDB profile augmentation already consumes deployment configuration, but there is no explicit compute composition contract.

## Target Contract

Compute plugins declare requirements for catalog/storage profile attachment and consume typed deployment bindings without reading another plugin's concrete config.

## Acceptance Evidence

- Resolver tests cover compute requirements.
- dbt profile tests prove deployment-aware profile generation.
- Secret-free binding tests remain green.
```

- [ ] **Step 2: Create semantic datasource design**

Create `docs/superpowers/specs/2026-05-09-semantic-datasource-binding-design.md` with:

```markdown
# Semantic Datasource Binding Design

Date: 2026-05-09
Status: Draft for review

## Goal

Replace static Cube datasource Helm values with a typed datasource binding derived from compute, catalog, and storage projections.

## Current Trigger

Cube uses static Helm override values while compute/catalog/storage projections exist elsewhere.

## Target Contract

Semantic layer plugins consume a datasource deployment binding and do not rediscover compute, catalog, or storage plugin config.

## Acceptance Evidence

- Schema tests cover semantic datasource binding.
- Cube tests prove Helm values are rendered from the binding.
- Compatibility tests prevent static plugin-config rediscovery.
```

- [ ] **Step 3: Create RBAC composition design**

Create `docs/superpowers/specs/2026-05-09-rbac-composition-design.md` with:

```markdown
# RBAC Composition Design

Date: 2026-05-09
Status: Draft for review

## Goal

Map identity and plugin requirements into generated Kubernetes access policy.

## Current Trigger

The Kubernetes RBAC plugin is discoverable and generation tests exist, but it does not consume typed identity or plugin requirement bindings.

## Target Contract

RBAC generation consumes identity bindings and plugin requirements, then emits Kubernetes access policy without direct knowledge of concrete plugin implementation details.

## Acceptance Evidence

- Resolver tests cover required identity modes.
- RBAC generation tests cover generated service accounts, roles, and bindings from typed inputs.
- No generated policy embeds raw secrets.
```

- [ ] **Step 4: Create network security composition design**

Create `docs/superpowers/specs/2026-05-09-network-security-composition-design.md` with:

```markdown
# Network Security Composition Design

Date: 2026-05-09
Status: Draft for review

## Goal

Define typed endpoint and identity inputs for Kubernetes network policy generation.

## Current Trigger

The Kubernetes network security plugin is discoverable, but it does not consume typed endpoint or identity bindings.

## Target Contract

Network policy generation consumes endpoint and identity bindings emitted by composition, not concrete plugin config.

## Acceptance Evidence

- Schema tests cover endpoint and identity input models.
- Network policy tests cover allowed service-to-service flows from typed bindings.
- No plugin imports another plugin's concrete implementation.
```

- [ ] **Step 5: Commit secondary design decomposition**

Run:

```bash
git add docs/superpowers/specs/2026-05-09-compute-composition-contract-design.md docs/superpowers/specs/2026-05-09-semantic-datasource-binding-design.md docs/superpowers/specs/2026-05-09-rbac-composition-design.md docs/superpowers/specs/2026-05-09-network-security-composition-design.md
git commit -m "Decompose secondary composition designs"
```

## Task 9: Compatibility Retirement Design

**Files:**
- Create: `docs/superpowers/specs/2026-05-09-compatibility-retirement-design.md`

- [ ] **Step 1: Map remaining compatibility helpers**

Run:

```bash
rg -n "get_pyiceberg_catalog_config|get_helm_values_override|get_source_config\\(catalog_config|artifacts\\.plugins\\.(storage|catalog)\\.config" packages plugins tests docs -g '*.py' -g '*.md'
```

Expected:

- Hits match the compatibility ledger's live surfaces.

- [ ] **Step 2: Write the compatibility retirement design**

Create `docs/superpowers/specs/2026-05-09-compatibility-retirement-design.md` with:

```markdown
# Compatibility Retirement Design

Date: 2026-05-09
Status: Draft for review

## Goal

Retire deprecated compatibility helpers only after typed replacement contracts and consumer migrations are proven.

## Candidate Helpers

- `StoragePlugin.get_pyiceberg_catalog_config()`
- MinIO `get_helm_values_override()`
- dlt sink `get_source_config(catalog_config)`
- Semantic layer `get_helm_values_override()`

## Retirement Rules

1. A helper can be removed only when no production source references it.
2. A guard test must fail if renderer or runtime code rediscover plugin config instead of consuming deployment bindings.
3. Secret-free compiled artifact tests must pass after removal.
4. Remote DevPod runtime validation must pass after the final retirement wave.

## Acceptance Evidence

- Source search shows no production references to removed helpers.
- Guard tests cover renderer/runtime ownership.
- Unit, contract, Helm, and remote runtime lanes pass.
```

- [ ] **Step 3: Commit compatibility retirement design**

Run:

```bash
git add docs/superpowers/specs/2026-05-09-compatibility-retirement-design.md
git commit -m "Design compatibility retirement"
```

## Task 10: Final Roadmap Verification

**Files:**
- Verify all changed files from previous tasks.

- [ ] **Step 1: Run static and focused test gates**

Run:

```bash
make lint
make typecheck
uv run pytest tests/contract/test_storage_minio_rename.py tests/contract/test_storage_binding_security.py packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py packages/floe-core/tests/unit/helm/test_generate_cli.py -q
helm unittest charts/floe-platform
```

Expected:

- All commands pass.

- [ ] **Step 2: Run docs validators**

Run:

```bash
uv run python testing/ci/validate-docs-navigation.py
uv run python testing/ci/validate-docs-content.py
```

Expected:

- Both commands pass.

- [ ] **Step 3: Run remote runtime validation when product code changed**

Run only after Wave 1 product artifact changes or after runtime migration changes:

```bash
DEVPOD_WORKSPACE=floe-postcomp-cleanup make devpod-test
devpod list
```

Expected:

- Remote E2E passes.
- `devpod list` shows no current-run workspace after cleanup.
- If direct Hetzner API credentials are available, no current-run servers, volumes, or SSH keys remain.

- [ ] **Step 4: Confirm final diff and branch state**

Run:

```bash
git status --short --branch
git log --oneline origin/main..HEAD
```

Expected:

- Working tree is clean.
- Commits are small and match task boundaries.

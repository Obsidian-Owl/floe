# Post-Composition Integration Audit

Date: 2026-05-09
Repo: /Users/dmccarthy/Projects/floe
Branch: main
Status: Final synthesis complete; see [2026-05-09-post-composition-final-synthesis.md](2026-05-09-post-composition-final-synthesis.md)

## Summary

Final synthesis is captured in [2026-05-09-post-composition-final-synthesis.md](2026-05-09-post-composition-final-synthesis.md). Product runtime passed remote DevPod E2E against `origin/main` at `d9e3582a4d7d76ffaaf0b3b40bed96247fc39938` with `261 passed, 86 deselected, 7 warnings`. Local trunk health remains mixed because `make test-unit` and the strict MinIO rename contract fail on stale `floe_storage_s3` / S3 alias residue, while lint, typecheck, focused composition, focused Helm, and Helm chart checks pass. Infrastructure cleanup passed; no current-run DevPod/Hetzner resources remain.

## Entry Gate

| Check | Result | Evidence |
| --- | --- | --- |
| Repo root is /Users/dmccarthy/Projects/floe | Pass | `pwd` -> `/Users/dmccarthy/Projects/floe` |
| Branch is main | Pass | `git rev-parse --abbrev-ref HEAD` -> `main` |
| Worktree is clean except audit artifacts | Pass | `git status --short --branch` -> `## main...origin/main` before scaffold creation |
| Remotes fetched before scaffold creation | Pass | `git fetch --all --prune` exited 0 |
| main is aligned with origin/main | Pass | `git rev-list --left-right --count HEAD...origin/main` -> `0\t0` |
| Active feature worktrees inventoried | Pass | `git worktree list --porcelain` listed only `/Users/dmccarthy/Projects/floe` |
| Provider compatibility spike deferred | Pass | No provider spike branch or worktree remains after trunk cleanup |

## Merge Context

| Branch or PR | Expected state | Evidence |
| --- | --- | --- |
| PR #317 storage MinIO architecture and composition contracts | Merged before audit | Not recorded |
| feat/iceberg-writer-contract | Merged or removed from prerequisite list | Not recorded |
| feat/identity-secret-composition | Merged or removed from prerequisite list | Not recorded |
| feat/composition-error-taxonomy | Merged or removed from prerequisite list | Not recorded |
| feat/e2e-dlt-ingestion | Merged or removed from prerequisite list | Not recorded |
| docs/provider-compatibility-spike | Deferred | No local branch or worktree remains |

## Baseline Health

| Gate | Result | Evidence |
| --- | --- | --- |
| make lint | Pass | `make lint` exited 0; `All checks passed!`; `1256 files already formatted` |
| make typecheck | Pass | `make typecheck` exited 0; `Success: no issues found in 358 source files` |
| make test-unit | Fail | `make test-unit` exited 2; `2 failed, 10485 passed, 1 skipped, 1 xfailed`; first failure: `ModuleNotFoundError: No module named 'floe_storage_s3.plugin'` in `TestPluginSystem.test_abc_compliance`. Classification: product/test contract baseline failure. |
| focused composition tests | Pass | `uv run pytest packages/floe-core/tests/unit/composition -q` -> `9 passed`; `uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py -q` -> `15 passed`; `uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py -q` -> `152 passed` |
| focused Helm renderer tests | Pass | `uv run pytest packages/floe-core/tests/unit/helm/test_generate_cli.py -q` -> `45 passed`; `helm unittest charts/floe-platform` -> `17 passed` suites, `184 passed` tests |
| contract tests | Fail | `uv run pytest tests/contract/test_storage_binding_security.py -q` -> `3 passed`; `uv run pytest tests/contract/test_compiled_artifacts_schema.py -q` -> `26 passed`; `uv run pytest tests/contract/test_storage_minio_rename.py -q` exited 1 with `3 failed, 7 passed`. Classification: product/test contract baseline failure. |
| secret scan | Fail | `pre-commit run detect-secrets --all-files` exited 3; reported potential secrets in existing files and rewrote `.secrets.baseline`. The hook side-effect was restored to keep this task's write scope limited to this audit document. Classification: security baseline/dependency blocker. |

## Contract Boundary Findings

| Severity | Surface | Finding | Evidence | Disposition |
| --- | --- | --- | --- | --- |
| High | Plugin registry / storage plugin boundary | The installed plugin registry still exposes `STORAGE:s3`, but the module target `floe_storage_s3.plugin` is not importable after the MinIO rename. | `make test-unit` failed in `packages/floe-core/tests/unit/plugins/test_plugin_system.py::TestPluginSystem::test_abc_compliance` with `ModuleNotFoundError: No module named 'floe_storage_s3.plugin'`; `test_plugin_health_checks` also reported `STORAGE:s3 - No module named 'floe_storage_s3.plugin'`. | Baseline trunk failure recorded; do not fix in Task 2. |
| High | Strict MinIO rename contract | The old S3 storage package and alias are still present from the perspective of the strict rename contract. | `uv run pytest tests/contract/test_storage_minio_rename.py -q` failed `test_storage_plugin_directory_is_strictly_minio` because `plugins/floe-storage-s3` exists; `test_runtime_plugin_registry_exposes_minio_without_s3_alias` discovered `name=s3 plugin_type=STORAGE value=floe_storage_s3.plugin:S3StoragePlugin`. | Baseline trunk failure recorded; do not fix in Task 2. |
| Medium | Active references / generated artifacts | Old S3 plugin names remain in active references and generated artifacts. | `test_active_references_do_not_use_old_s3_plugin_names` reported 53 matches; first reported match: `demo/financial-risk/compiled_artifacts.json:88` with `"type": "s3"`. | Baseline trunk failure recorded; candidate cleanup follow-up. |
| Medium | Secret scan baseline | The current all-files secret scan reports existing potential secrets and attempts to update `.secrets.baseline`, which blocks a clean commit hook path. | `pre-commit run detect-secrets --all-files` failed with exit code 3; examples include `packages/floe-core/tests/integration/test_lineage_wiring.py:448`, `charts/floe-platform/tests/job_polaris_bootstrap_test.yaml:11`, `docs/architecture/adr/0036-storage-plugin-interface.md:321`, and `charts/floe-platform/tests/polaris_persistence_test.yaml:102`. | Baseline security/dependency blocker recorded; `.secrets.baseline` hook rewrite restored because Task 2 write scope excludes it. |
| Map only | Composition resolver public contract | Capability and requirement models are centralized in `floe_core.composition.models`, and resolver validation is centralized in `CompositionResolver`. | Required map search found `CapabilitySet`, `RequirementSet`, `PluginCapabilities`, and `PluginRequirements` in `packages/floe-core/src/floe_core/composition/models.py:33`; `CompositionResolver` in `packages/floe-core/src/floe_core/composition/resolver.py:24`; unit coverage in `packages/floe-core/tests/unit/composition/test_resolver.py:22`. | Map only; no product-code change in Task 3. |
| Map only | Compiled artifact deployment binding contract | Storage, catalog, ingestion, and credential binding models are in compiled artifacts and are tested at schema and contract layers. | Required map search found `CredentialRef` at `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py:653`, `StorageDeploymentBinding` at `:872`, `PolarisCatalogDeploymentBinding` at `:892`, `CatalogDeploymentBinding` at `:958`, `IngestionDeploymentBinding` at `:1005`; tests include `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py:705` and `tests/contract/test_core_to_ingestion_contract.py:436`. | Map only; no issue found in model placement. |
| Map only | Compilation assembly path | Compilation assembles plugin capabilities, resolver checks, storage deployment bindings, and catalog deployment bindings in `floe_core.compilation.stages`. | Required map search found `PluginCapabilities` assembly in `packages/floe-core/src/floe_core/compilation/stages.py:576`, catalog `CompositionResolver().validate(...)` at `:680`, and ingestion validation at `:867`; focused binding tests appear in `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py:256`. | Map only; no issue found in the primary assembly path. |
| Low | Cross-plugin imports | Source-level implementation imports are primarily package-internal or through `floe_core` ABCs/registry; no direct storage-to-catalog or catalog-to-storage concrete plugin import was found. Dagster and core import `floe_iceberg`, which appears to be an allowed public package API rather than a plugin implementation boundary. | Required cross-plugin search was noisy with intra-package imports. Targeted review found `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py:122` importing `IcebergTableManager`, `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py:15` importing `floe_iceberg` writer APIs, and `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py:968` importing `DriftDetector`; no concrete `floe_storage_*`/`floe_catalog_*` import edge was found outside tests. | Map only for current task; keep as an explicit allowed API boundary to avoid future plugin-to-plugin coupling. |
| Medium | Runtime storage/catalog consumption | Dagster runtime/export paths still configure catalog/storage plugins from `artifacts.plugins.*.config` and call `StoragePlugin.get_pyiceberg_catalog_config()`, then overlay compiled binding endpoint data in some paths. This keeps legacy plugin config/methods live alongside deployment bindings and is a compatibility surface to retire carefully. | Renderer search found `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py:137` configuring catalog from `catalog_ref.config`, `:154` configuring storage from `storage_ref.config`, and `:172` calling `storage_plugin.get_pyiceberg_catalog_config()` before `_catalog_connection_config_from_binding(storage_binding)`; export path mirrors this at `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py:175` and `:211`. | Finding recorded only; candidate Task 4 design/cleanup, not a Task 3 fix. |
| Medium | Legacy Helm override renderer path | The MinIO storage plugin still exposes `get_helm_values_override()`, building `polaris.storage.s3.*` directly from plugin config. The primary Helm renderer now reads deployment bindings, but this deprecated helper remains a stale renderer path and could reintroduce semantic rediscovery if used. | Renderer search found binding-driven Helm values in `packages/floe-core/src/floe_core/cli/helm/generate.py:191` through `:197`; legacy helper remains in `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py:397` through `:430` with a deprecation warning at `:405`. | Finding recorded only; candidate compatibility-ledger removal plan. |
| Low | Legacy ingestion catalog config guard | Product-level dlt `catalog_config` fallback is explicitly rejected by core and plugin config tests, which supports the new deployment-binding path. | Renderer search found rejection in `packages/floe-core/src/floe_core/compilation/resolver.py:166`; unit coverage in `plugins/floe-ingestion-dlt/tests/unit/test_config.py:77`. | Map only; keep as compatibility guard. |
| Low | Secret-free generated artifacts | No raw secret keywords were found in `target` JSON/YAML artifacts during the required secret-material search, and the focused storage binding security contract passed. Search hits in tests/docs were references, allowlisted fakes, or secret-safety assertions. | `rg -n "access_key|access-key|secret_access_key|secret-access-key|password|token|client_secret" target ...` returned no `target` hits; `docs/contracts/compiled-artifacts.md:169` is `client_secret_env`; `uv run pytest tests/contract/test_storage_binding_security.py -q` -> `3 passed`. | No Critical finding. |

## Documentation Findings

| Severity | Page | Finding | Evidence | Disposition |
| --- | --- | --- | --- | --- |
| Medium | `docs/architecture/plugin-composition-uplift-tracker.md` | The tracker is still useful, but some status language is pre-closeout or broader than the current evidence. It says several areas are "In storage composition PR" and records PCU-005 as implemented, while the post-composition matrix still recommends credential-provider projection work. | Task 5 composition search found the tracker rows and compared them with `docs/validation/2026-05-09-post-composition-plugin-matrix.md`. | Verify and reconcile in a docs follow-up. |
| Low | `docs/architecture/interfaces/storage-plugin.md`, `docs/architecture/plugin-system/interfaces.md`, `docs/architecture/ARCHITECTURE-SUMMARY.md`, `docs/architecture/adr/0036-storage-plugin-interface.md` | Current architecture docs correctly frame legacy storage helpers as compatibility surfaces and typed deployment bindings as target state. | Task 5 compatibility search found `get_helm_values_override()` references, but these docs explicitly describe the helpers as migration-era compatibility rather than target architecture. | Keep; update examples when helper APIs are actually removed. |
| Low | `docs/superpowers/plans/**`, `docs/superpowers/specs/**` | Dated plans/specs contain old snippets and transitional instructions, including a historical `storage: s3` example in the identity/secret composition plan. | Task 5 searches found `docs/superpowers/plans/2026-05-07-identity-secret-composition.md:1335` and multiple dlt/storage composition plan snippets. | Historical only; do not treat as current public contract. |

## Task 5 Compatibility Ledger Summary

| Area | Result | Evidence |
| --- | --- | --- |
| Required compatibility/staleness search | Completed | `rg -n "deprecated|DeprecationWarning|legacy|compat|compatibility|get_helm_values_override|alias|floe-storage-s3|storage type.*s3|plugins\\.storage\\.type.*s3" packages plugins docs tests charts -g '*.py' -g '*.md' -g '*.yaml' -g '*.yml' -g '*.tpl'` returned 1661 hits. Ledger triage separates live compatibility, uplift-now migration surfaces, stale paths, and historical docs. |
| Required composition-era search | Completed | `rg -n "composition|MinIO|Polaris|storage binding|deployment binding|identity mode|credential mode|dlt|Iceberg writer" docs/superpowers docs/validation docs/architecture docs/contracts tests packages plugins -g '*.md' -g '*.py' -g '*.json' -g '*.yaml' -g '*.yml'` returned 3898 hits. Findings were narrowed to current contract docs/tests versus historical plans and stale user-facing tracker language. |
| Required filename sweep | Completed | `find tests packages plugins docs -type f \( -name '*composition*' -o -name '*storage*' -o -name '*minio*' -o -name '*polaris*' -o -name '*identity*' -o -name '*secret*' \) | sort` found tracked docs/tests/source plus ignored `.mypy_cache`, `.venv`, and `__pycache__` artifacts. The ledger records grouped purpose and disposition. |
| Key stale path | Recorded | Ignored local `plugins/floe-storage-s3/`, stale installed `floe_storage_s3.plugin:S3StoragePlugin`, and demo compiled artifacts with `"type": "s3"` remain the strict MinIO cleanup target. |
| Key live compatibility layers | Recorded | `StoragePlugin.get_pyiceberg_catalog_config()`, MinIO `get_helm_values_override()`, Dagster storage/catalog plugin-config fallback, dlt sink `get_source_config(catalog_config)`, semantic Cube Helm override, and identity/secrets capability-only validation are now ledgered with dispositions. |
| Historical docs | Recorded | Dated `docs/superpowers` plans/specs and older epic/requirements docs are classified separately from current architecture docs. |
| Generated artifacts | Recorded | Raw filename sweep surfaced ignored generated artifacts. They are classified as local cleanup candidates, not tracked contract evidence. |

Recommended next actions from Task 5:

1. Remove the stale S3 storage alias/package residue and regenerate demo compiled artifacts with `minio`.
2. Reconcile `docs/architecture/plugin-composition-uplift-tracker.md` against the post-composition matrix and compatibility ledger.
3. Design binding-first runtime inputs for Dagster/Iceberg writer and dlt sink/source config before removing legacy catalog-config helpers.
4. Design semantic datasource and identity/credential deployment projections so Level 2/3 plugin composition work has typed, secret-free bindings.

## Task 6 Documentation Truth Pass Summary

| Area | Result | Evidence |
| --- | --- | --- |
| Documentation inventory | Completed | `find docs -type f -name '*.md' \| sort` found 295 Markdown files. |
| Composition-era/stale language search | Completed | `rg -n "composition\|composability\|deployment binding\|storage binding\|compiled artifacts\|CompiledArtifacts\|MinIO\|floe-storage-minio\|floe-storage-s3\|storage: s3\|type: s3\|Polaris\|identity mode\|credential mode\|CredentialRef\|secret\|Helm\|renderer\|get_helm_values_override\|get_pyiceberg_catalog_config\|dlt\|Iceberg writer\|DevPod\|Hetzner\|TODO\|TBD\|aspirational\|target state\|legacy\|deprecated" docs README.md TESTING.md CLAUDE.md AGENTS.md -g '*.md'` returned 4,644 hits. |
| Historical planning link search | Completed | `rg -n "docs/superpowers\|docs/requirements\|docs/research\|plugin-composition-uplift-tracker\|storage-minio\|identity-secret\|dlt-ingestion\|composition-closeout" docs README.md TESTING.md CLAUDE.md AGENTS.md -g '*.md'` returned 212 hits. |
| Repo-native docs link/content validation | Pass | Repo-native validators found in `Makefile`, `.pre-commit-config.yaml`, `testing/ci/validate-docs-navigation.py`, and docs-site scripts. `uv run python testing/ci/validate-docs-navigation.py` exited 0 and includes published Markdown link checks. `uv run python testing/ci/validate-docs-content.py` exited 0 with `docs content validation passed`. No standalone external link checker such as lychee was configured. |
| Separate truth-pass inventory | Added | `docs/validation/2026-05-09-post-composition-docs-truth-pass.md` records the doc-area classification table and exact reconciliation targets. |

Key documentation findings:

1. `docs/contracts/compiled-artifacts.md`, `docs/reference/plugin-catalog.md`, and the storage/catalog composition sections are the strongest current truth anchors for secret-free deployment bindings, plugin category count, renderer ownership, and composition diagnostics.
2. `docs/architecture/plugin-composition-uplift-tracker.md` needs reconciliation: it still uses "In storage composition PR" language and marks PCU-005 implemented even though typed identity/credential deployment projections remain follow-up work.
3. `docs/architecture/interfaces/index.md` and many `docs/architecture/interfaces/*.md` pages cite old `floe_core/interfaces/*.py` paths while implementation truth is under `floe_core/plugins/*.py`; `docs/architecture/interfaces/identity-plugin.md` also uses the wrong entry point group (`floe.identities` instead of `floe.identity`).
4. `docs/architecture/storage-integration.md`, storage ADR material, `README.md`, `TESTING.md`, `CLAUDE.md`, and `AGENTS.md` should separate current strict MinIO/S3-compatible implementation truth from future native S3/GCS/Azure targets and broad target-state composability claims.
5. `docs/superpowers/**`, `docs/plans/**`, `docs/requirements/**`, and `docs/research/**` are historical/provenance material. They should not be treated as current implementation contracts unless a current architecture page explicitly promotes them.

Recommended next actions from Task 6:

1. Reconcile the composition tracker with the plugin matrix and compatibility ledger.
2. Correct interface docs against live `PluginType` entry points and `floe_core.plugins.*` ABC paths.
3. Tighten public/agent docs around current MinIO binding ownership, secret-free `CompiledArtifacts`, Helm renderer ownership, DevPod/Hetzner infra-vs-product separation, and remaining post-composition design gaps.
4. Add historical banners or archive treatment for superseded dated plans that can surface in search results.

## Runtime Validation

| Lane | Result | Evidence | Classification |
| --- | --- | --- | --- |
| Preflight | Pass | `git status --short --branch` -> `## main...origin/main [ahead 6]`; local `HEAD` -> `ad8a27e088c565fee93f0cc7b9ef4c82a228b0ac`; `origin/main` -> `d9e3582a4d7d76ffaaf0b3b40bed96247fc39938`; `devpod version` -> `v0.6.15`; Hetzner provider initialized; `devpod list` empty before run. | Evidence lane |
| DevPod remote E2E | Pass | `DEVPOD_WORKSPACE=floe-postcomp-audit make devpod-test` provisioned workspace `floe-postcomp-audit` / machine `floe-postc-a353f`, cloned `https://github.com/Obsidian-Owl/floe` branch `main`, and waited for Flux revision `d9e3582a4d7d76ffaaf0b3b40bed96247fc39938`. Remote E2E artifact path: `test-artifacts/devpod-run-20260509T030016Z-21729`. Exit code file: `0`. Final result: `261 passed, 86 deselected, 7 warnings in 1034.53s (0:17:14)`. | Product validation pass for `origin/main` product code, not local audit-doc commits |
| DevPod remote teardown | Warn | After the remote command completed, DevPod emitted `Error tunneling to container: wait: remote command exited without exit status or exit signal`, then saved artifacts, reported `E2E tests PASSED`, and continued cleanup. | Tooling warning; not a product failure |
| DevPod cleanup | Pass | `make devpod-test` Step 5 deleted workspace `floe-postcomp-audit`; post-run `devpod list` was empty. | Infra cleanup pass |
| Hetzner direct cleanup inventory | Pass | `hcloud` was unavailable locally, so `.env` `DEVPOD_HETZNER_TOKEN` was used with direct Hetzner Cloud API `curl` calls. Pre-run inventory found no server, volume, or SSH key matching `floe-postcomp-audit`. Post-run inventory found no server, volume, or SSH key matching `floe-postcomp-audit` or actual machine prefix `floe-postc-a353f`; no manual deletion was required. | Infra cleanup pass |

See `docs/validation/2026-05-09-post-composition-runtime-validation.md` for the concise command/result ledger.

## Follow-Up Workstreams

| Workstream | Reason | Required next artifact |
| --- | --- | --- |
| Storage strict MinIO cleanup | Matrix decision is `Remove stale path`; stale S3 package, registry entry point, and generated `"type": "s3"` artifacts still break trunk validation. | Cleanup PR removing stale S3 path and regenerating active artifacts with `minio`. |
| Compute deployment-aware profile contract | Matrix decision is `Uplift now`; DuckDB consumes deployment bindings but has no explicit resolver-backed compute composition contract. | Compute composition contract and tests for deployment-aware dbt profile/catalog attachment behavior. |
| Dagster binding-first runtime migration | Matrix decision is `Uplift now`; Dagster resource/export/validation paths still consume legacy storage-owned catalog config. | Binding-first Dagster runtime connection migration plan and regression tests. |
| Iceberg writer runtime contract | Matrix decision is `Needs design`; `floe_iceberg.writer` still probes `StoragePlugin.get_pyiceberg_catalog_config()`. | Design note for neutral Iceberg writer connection inputs before product-code migration. |
| Credential provider projection | Matrix decision is `Uplift now`; credential-provider plugins expose capabilities but no typed credential deployment projection. | Sensitive-value-safe credential binding contract using `CredentialRef` only. |
| Identity workload binding | Matrix decision is `Uplift now`; identity capabilities are declared but not projected into typed deployment/runtime bindings. | Workload identity binding contract covering issuer, audience, and credential mode metadata. |
| RBAC composition design | Matrix decision is `Needs design`; RBAC generation is plugin-backed but not composed from identity/capability bindings. | RBAC composition design mapping identity and plugin requirements into generated access policy. |
| Network security composition design | Matrix decision is `Needs design`; K8s network security is discoverable but does not consume typed endpoint or identity bindings. | Endpoint and identity binding design for network policy generation. |
| Semantic layer datasource composition | Matrix decision is `Needs design`; Cube still uses static Helm override while compute/catalog/storage projections are available elsewhere. | Semantic datasource binding design sourced from compute/catalog/storage deployment projections. |

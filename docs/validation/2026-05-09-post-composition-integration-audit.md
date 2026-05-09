# Post-Composition Integration Audit

Date: 2026-05-09
Repo: /Users/dmccarthy/Projects/floe
Branch: main
Status: Baseline failures recorded

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

## Runtime Validation

| Lane | Result | Evidence | Classification |
| --- | --- | --- | --- |
| DevPod remote E2E | Not run | Not recorded | Not recorded |
| Hetzner cleanup inventory | Not run | Not recorded | Not recorded |

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

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

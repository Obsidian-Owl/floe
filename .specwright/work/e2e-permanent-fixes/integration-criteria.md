# Integration Criteria: E2E Permanent Fixes

After all 4 units are built, these structural connections must exist:

- [ ] IC-1: `tests/e2e/dbt_utils.py` calls `catalog.purge_table()` (not `drop_table()`) in `_purge_iceberg_namespace()`
- [ ] IC-2: `tests/e2e/dbt_utils.py` `_purge_iceberg_namespace()` includes S3 prefix deletion logic after catalog purge
- [ ] IC-3: `charts/floe-platform/templates/configmap-polaris.yaml` contains a conditional block for `polaris.persistence.type == "relational-jdbc"` that adds Quarkus datasource properties
- [ ] IC-4: `charts/floe-platform/values-test.yaml` sets `polaris.persistence.type: relational-jdbc` and includes JDBC env vars under `polaris.env`
- [ ] IC-5: `charts/floe-platform/values-test.yaml` sets `postgresql.persistence.enabled: true`
- [ ] IC-6: `testing/ci/extract-manifest-config.py` exports `MANIFEST_S3_ENDPOINT` from `plugins.storage.config.endpoint`
- [ ] IC-7: `testing/ci/test-e2e.sh` catalog creation block uses extracted manifest S3 endpoint, not hardcoded `http://floe-platform-minio:9000`
- [ ] IC-8: `tests/e2e/conftest.py` `_read_manifest_config()` raises an error (not a warning) when manifest is not found
- [ ] IC-9: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/lineage_extraction.py` uses `"parent"` facet key (not `"parentRun"`)
- [ ] IC-10: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` `generate_entry_point_code()` emits thin loader pattern (imports `load_product_definitions`, not inline Iceberg/lineage logic)

## Pivot: Runtime Loader (Unit 5)

- [ ] IC-11: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py` exports `load_product_definitions()` that returns `dagster.Definitions`
- [ ] IC-12: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py` exports `export_dbt_to_iceberg()` with `product_name`, `project_dir`, `artifacts` parameters
- [ ] IC-13: `demo/customer-360/definitions.py` imports from `floe_orchestrator_dagster.loader` and calls `load_product_definitions("customer-360", PROJECT_DIR)`
- [ ] IC-14: `demo/iot-telemetry/definitions.py` imports from `floe_orchestrator_dagster.loader` and calls `load_product_definitions("iot-telemetry", PROJECT_DIR)`
- [ ] IC-15: `demo/financial-risk/definitions.py` imports from `floe_orchestrator_dagster.loader` and calls `load_product_definitions("financial-risk", PROJECT_DIR)`
- [ ] IC-16: None of the 3 demo `definitions.py` files contain `_export_dbt_to_iceberg`, `_load_iceberg_resources`, `get_registry`, or `CompiledArtifacts`

## Loud Failures (Unit 6)

- [ ] IC-17: `try_create_ingestion_resources()` re-raises exceptions (no `return {}` in except block)
- [ ] IC-18: All 4 `try_create_*` functions log at WARNING level for unconfigured plugins (no DEBUG)
- [ ] IC-19: All 4 `try_create_*` functions use structured log keys: `"{resource}_not_configured"` and `"{resource}_creation_failed"`
- [ ] IC-20: `tests/contract/test_resource_factory_semantics.py` exists and parametrizes all 4 factories

## Config Merge Fix (Unit 7)

- [ ] IC-21: `charts/floe-platform/templates/job-polaris-bootstrap.yaml` does NOT contain `table-default.s3.endpoint`
- [ ] IC-22: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` applies client endpoint override after table load
- [ ] IC-23: `tests/contract/test_s3_endpoint_preservation.py` exists and traces endpoint from CompiledArtifacts through to PyIceberg config
- [ ] IC-24: Helm unit test asserts absence of `table-default.s3.endpoint` in bootstrap job

## Credential Consolidation (Unit 8)

- [ ] IC-25: `testing/fixtures/credentials.py` exports `get_minio_credentials()`, `get_polaris_credentials()`, `get_polaris_endpoint()`
- [ ] IC-26: Zero occurrences of hardcoded `minioadmin`, `demo-secret`, or `demo-admin` in Python test files (excluding comments/docs)
- [ ] IC-27: `tests/contract/test_no_hardcoded_credentials.py` exists and scans executable code for credential patterns

## E2E Proof (Unit 9)

- [ ] IC-28: `tests/e2e/test_runtime_loader_e2e.py` exists and verifies thin loader happy path with Iceberg row count assertions
- [ ] IC-29: `tests/e2e/test_loud_failure_e2e.py` exists and verifies pipeline FAILS when Polaris is down
- [ ] IC-30: `tests/e2e/test_s3_endpoint_e2e.py` exists and verifies endpoint preservation
- [ ] IC-31: `tests/e2e/test_credential_consistency_e2e.py` exists and verifies zero credential drift
- [ ] IC-32: `make test-e2e` passes with zero failures after all units are built

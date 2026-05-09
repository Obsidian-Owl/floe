# Post-Composition Plugin Composability Matrix

Date: 2026-05-09
Repo: /Users/dmccarthy/Projects/floe
Status: Complete

## Level Definitions

| Level | Meaning | Required evidence |
| --- | --- | --- |
| 0 | Discoverable plugin only | Entry point, metadata, config schema |
| 1 | Declares capabilities and requirements | PluginCapabilities, PluginRequirements, compatibility tests |
| 2 | Emits or consumes typed bindings | Contract model, schema tests, no raw secrets |
| 3 | Has deployment/runtime translators validated by resolver | Resolver tests, generated deployment binding, renderer tests, runtime evidence where applicable |

## Decisions

| Plugin family | Current level | Target level | Decision | Composition trigger | Evidence | Follow-up |
| --- | --- | --- | --- | --- | --- | --- |
| Storage / MinIO | Level 3 for `minio`; stale S3 path is broken | Level 3 | Remove stale path | Current Iceberg runtime path | `floe.storage` entry point in `plugins/floe-storage-minio/pyproject.toml`; `MinIOStoragePlugin.get_deployment_binding()`; `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`; stale `plugins/floe-storage-s3` and `floe_storage_s3.plugin` failures in audit | Remove stale S3 package/entry point and regenerate stale `"type": "s3"` artifacts; keep binding-first MinIO path |
| Catalog / Polaris | Level 3 | Level 3 | Verify Level 3 | Current Iceberg runtime path | `PolarisCatalogPlugin.get_storage_requirements()` and `build_catalog_deployment()`; `plugins/floe-catalog-polaris/tests/unit/test_storage_composition.py`; `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py` | None |
| Compute / DuckDB | Level 2 | Level 3 | Uplift now | dbt/storage runtime path | `ComputePlugin.augment_dbt_profile()`; `DuckDBComputePlugin.augment_dbt_profile()` consumes `DeploymentConfig`; `plugins/floe-compute-duckdb/tests/unit/test_plugin.py`; `packages/floe-core/tests/unit/compilation/test_dbt_profiles.py` | Add explicit compute composition contract or resolver validation for deployment-aware profile/catalog attachment behavior |
| DBT / Core and Fusion | Level 1 | Level 1 | Leave untouched | dbt SQL compilation and runtime packaging | `floe.dbt` entry points; `get_manifest()`, `get_run_results()`, and `get_runtime_metadata()` in dbt plugins; `plugins/floe-dbt-core/tests/unit/test_plugin.py`; `plugins/floe-dbt-fusion/tests/unit/test_plugin.py` | None |
| Orchestrator / Dagster | Level 2 | Level 3 | Uplift now | runtime execution and Iceberg writer handoff | `DagsterPlugin.get_helm_values()`; Dagster loader accepts `DeploymentConfig`; runtime/export still call storage `get_pyiceberg_catalog_config()` per audit | Migrate Dagster resource/export/validation paths to binding-first catalog connection contract |
| Iceberg package | Level 1 runtime consumer | Level 3 | Needs design | platform-owned Iceberg write semantics | `packages/floe-iceberg/src/floe_iceberg/writer.py` still probes `get_pyiceberg_catalog_config()`; writer tests cover fallback | Design neutral Iceberg runtime connection input before removing storage-owned catalog config |
| Ingestion / dlt | Level 3 | Level 3 | Verify Level 3 | landing/quarantine/checkpoint/raw bucket needs | `DltIngestionPlugin.get_composition_requirements()` and `build_deployment_binding()`; `plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py`; `tests/contract/test_core_to_ingestion_contract.py` | None |
| Secrets / Kubernetes and Infisical | Level 1 | Level 2 | Uplift now | credential binding and credential refs | Capability declarations in both credential-provider plugins; provider unit tests; `CredentialRef` compiled-artifact model | Add typed credential projection/binding contract that maps provider capabilities into deployment refs without embedding sensitive values |
| Identity / Keycloak | Level 1 | Level 2 | Uplift now | workload identity and credential modes | `KeycloakIdentityPlugin.get_identity_capabilities()`; `plugins/floe-identity-keycloak/tests/unit/test_init.py`; workload identity trigger is shared with secrets/RBAC | Add typed identity binding contract for workload identity modes and credential issuer metadata |
| RBAC / Kubernetes | Level 0 | Level 2 | Needs design | workload identity and generated access policy | `floe.rbac` entry point; `RBACPlugin` ABC; RBAC generation tests under `packages/floe-core/tests/unit/test_rbac_*` and `packages/floe-core/tests/integration/test_rbac_generation.py` | Design how plugin capability and identity bindings become generated Kubernetes access policy |
| Network security / Kubernetes | Level 0 | Level 2 | Needs design | plugin endpoints and identity bindings | `floe.network_security` entry point in `plugins/floe-network-security-k8s/pyproject.toml`; `NetworkSecurityPlugin` ABC and K8s implementation generate policy/security context but do not consume typed endpoint or identity bindings | Design typed endpoint/identity inputs before composition uplift |
| Telemetry backends | Level 0 | Level 0 | Leave untouched | backend deployment topology or auth | `floe.telemetry_backends` entry points; `TelemetryBackendPlugin.get_helm_values()`; console/Jaeger unit and integration tests | None |
| Lineage backend / Marquez | Level 0 | Level 0 | Leave untouched | endpoint/auth/deployment wiring | `floe.lineage_backends` entry point; `LineageBackendPlugin.get_helm_values()`; `plugins/floe-lineage-marquez/tests/unit/test_plugin.py` | None |
| Quality / dbt and GX | Level 0 | Level 0 | Defer | compute/storage runtime needs | `floe.quality` entry points; quality plugins expose validation/lineage behavior and config schemas; no binding or resolver trigger found | Reassess only when quality runs need deployment-owned compute/storage inputs |
| Semantic layer / Cube | Level 0 | Level 2 | Needs design | compute/catalog/storage runtime consumption | `floe.semantic_layers` entry point; `SemanticLayerPlugin.get_helm_values_override()`; Cube tests cover static Helm values; DuckDB exposes `get_cube_datasource_config()` | Design semantic datasource binding from compute/catalog/storage projections before replacing Helm override path |
| Alert channels | Level 0 | Level 0 | Leave untouched | user-facing alert delivery composition | `floe.alert_channels` entry points; `AlertChannelPlugin` ABC; no deployment binding or resolver trigger found | None |

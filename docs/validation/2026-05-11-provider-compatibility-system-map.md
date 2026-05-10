# Provider Compatibility Implemented-System Map

Date: 2026-05-11
Repo: `/Users/dmccarthy/Projects/floe`
Branch: `main`
Purpose: Source map for the provider compatibility spike.

## Baseline Head

| Item | Evidence |
| --- | --- |
| Branch | `main` |
| Baseline HEAD before this artifact | `901cfbb404e8b5ccc140de1a63e7d42e80257fa6` |
| Five recent commits captured before this artifact | `901cfbb4 docs: plan provider compatibility spike`<br>`7347e8cb docs: add provider compatibility spike design`<br>`d97785cd [codex] Binding-first Dagster Iceberg runtime (#328)`<br>`50670b79 [codex] Post-composition cleanup roadmap (#327)`<br>`d9e3582a Stabilize dlt ingestion through composability layers (#326)` |

## Composition Contracts

| Contract | Source | Role |
| --- | --- | --- |
| `CapabilitySet` | `packages/floe-core/src/floe_core/composition/models.py` | Provider capability declaration |
| `RequirementSet` | `packages/floe-core/src/floe_core/composition/models.py` | Provider requirement declaration |
| `CompositionResolver` | `packages/floe-core/src/floe_core/composition/resolver.py` | Compatibility validation |
| `COMPOSITION_*` diagnostics | `packages/floe-core/src/floe_core/composition/error_codes.py` | Operator-facing composition failures |

## Typed Bindings

| Binding | Source | Role |
| --- | --- | --- |
| `StorageDeploymentBinding` | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | Secret-free storage deployment state |
| `CatalogDeploymentBinding` | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | Secret-free catalog deployment state |
| `IngestionDeploymentBinding` | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | Secret-free ingestion runtime state |
| `RuntimeCatalogConnection` | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | Neutral Iceberg runtime catalog projection |
| `CredentialRef` | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | Secret-free credential reference |

## Current Provider Consumers

| Consumer | Source | Current behavior |
| --- | --- | --- |
| MinIO storage | `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py` | Emits `StorageDeploymentBinding` |
| Polaris catalog | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | Declares storage requirements and emits `CatalogDeploymentBinding` |
| dlt ingestion | `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py` | Declares storage/catalog requirements and emits `IngestionDeploymentBinding` |
| DuckDB compute | `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py` | Augments dbt profile from deployment bindings |
| Dagster runtime | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/` | Consumes `RuntimeCatalogConnection` |
| Helm renderer | `packages/floe-core/src/floe_core/cli/helm/generate.py` | Renders from deployment bindings |

## Baseline Conclusion

MinIO plus Polaris is the control path. New provider compatibility must either reuse the current neutral contracts or justify a new capability, binding, runtime translator, or renderer dimension.

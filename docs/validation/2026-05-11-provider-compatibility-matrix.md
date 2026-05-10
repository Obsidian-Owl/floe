# Provider Compatibility Matrix

Date: 2026-05-11
Repo: `/Users/dmccarthy/Projects/floe`
Purpose: Provider-by-provider assessment against the merged binding/composition model.

## Level Definitions

| Level | Meaning | Evidence required |
| --- | --- | --- |
| 0 | Discoverable plugin only | Entry point, metadata, config schema |
| 1 | Declares capabilities and requirements | `PluginCapabilities`, `PluginRequirements`, resolver tests |
| 2 | Emits or consumes typed bindings | Contract model, schema tests, secret-free artifacts |
| 3 | Runtime/deployment translated and validated | Resolver tests, binding output, renderer/runtime translation, E2E or live proof where applicable |

## Matrix

| Provider combination | Storage protocol | Catalog protocol | Credential mode | Identity mode | Endpoint shape | Warehouse ownership | Server-side storage access | Current expressibility | Required model change | Target level | Live proof |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MinIO + Polaris | `s3-compatible` | Iceberg REST via Polaris | Kubernetes Secret | none | explicit internal/external endpoint, path-style | storage binding plus Polaris warehouse | yes, via referenced MinIO credentials | Expressed today | none | Level 3 | Existing DevPod/Hetzner E2E control path |
| AWS S3 + AWS Glue | `s3` | Glue Catalog | workload identity or secret-backed AWS credentials | IRSA, AWS Pod Identity, or external AWS credentials | regional AWS endpoints, optional custom endpoint for tests | S3 bucket/prefix plus Glue database/table metadata | yes, through AWS IAM | Partially expressible conceptually; provider plugins absent | native S3 storage plugin, Glue catalog binding, AWS identity/credential requirements, PyIceberg Glue translation proof | Level 3 target after implementation | Preferred live proof |
| AWS S3 + Iceberg REST or Polaris | `s3` | Iceberg REST | workload identity or secret-backed AWS credentials | IRSA, AWS Pod Identity, or external AWS credentials | AWS S3 regional endpoint plus REST catalog URI | storage owns bucket/prefix, catalog owns warehouse reference | depends on catalog deployment | Partially expressible conceptually; native S3 plugin absent | native S3 storage binding plus catalog-specific requirements | Level 2 or 3 depending on live catalog | Optional second proof |
| MinIO + Nessie | `s3-compatible` | Nessie Iceberg catalog | Kubernetes Secret | none | MinIO path-style endpoint plus Nessie REST endpoint | storage bucket/prefix plus Nessie catalog branch/namespace | yes, if Nessie service accesses storage | MinIO side expressed; Nessie provider absent | Nessie catalog plugin and typed catalog binding | Level 3 fallback target | Fallback live proof |
| AWS S3 + Nessie | `s3` | Nessie Iceberg catalog | workload identity or secret-backed AWS credentials | IRSA, AWS Pod Identity, or external AWS credentials | AWS S3 endpoint plus Nessie REST endpoint | S3 bucket/prefix plus Nessie branch/namespace | yes, if Nessie service accesses storage | Not implemented | native S3 storage plugin, Nessie catalog plugin, identity/credential binding proof | Level 3 second-wave target | Deferred live proof |
| GCS + future catalog | `gcs` | provider-specific | workload identity or secret-backed service account | GCP Workload Identity or service account reference | GCS bucket URI and regional/multi-region behavior | GCS bucket/prefix plus catalog metadata | provider-dependent | Not implemented | GCS storage capability, credential mode, runtime translator pressure test | Level 1 or 2 design target | No first live proof |
| Azure Blob or ADLS + future catalog | `abfs` or provider-specific | provider-specific | workload identity or secret-backed identity | Azure Workload Identity or managed identity | account/container/path endpoint | container/path plus catalog metadata | provider-dependent | Not implemented | Azure storage capability, identity mode, runtime translator pressure test | Level 1 or 2 design target | No first live proof |
| Hive catalog | object-store dependent | Hive metastore | provider-dependent | provider-dependent | metastore URI plus object-store endpoint | storage path plus Hive metadata | yes | Not implemented and no concrete alpha trigger | defer until deployment path exists | Level 0 deferred | No live proof |

## Entry Point Evidence

The entry point inventory found first-party plugins for alert channels, Polaris catalog, DuckDB compute, dbt Core/Fusion, Keycloak identity, dlt ingestion, Marquez lineage, Kubernetes network security, Dagster orchestrator, dbt/GX quality, Kubernetes RBAC, Infisical/Kubernetes secrets, Cube semantic layer, MinIO storage, and console/Jaeger telemetry.

Storage/catalog evidence is limited to:

| Plugin package | Entry point group | Entry point names |
| --- | --- | --- |
| `floe-storage-minio` | `floe.storage` | `minio` |
| `floe-catalog-polaris` | `floe.catalogs` | `polaris` |

The inventory did not include entry points for AWS S3, AWS Glue, Nessie, GCS, Azure, ADLS, or Hive provider plugins. The `plugins/` directory likewise contains `floe-storage-minio` and `floe-catalog-polaris`, with no first-party `floe-storage-s3`, `floe-catalog-glue`, `floe-catalog-nessie`, `floe-storage-gcs`, `floe-storage-azure`, or `floe-catalog-hive` package.

## Provider-Specific Assumption Search

The provider-specific search found the current implemented assumptions concentrated around the MinIO + Polaris control path:

- `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py` emits `provider="minio"`, `protocol="s3-compatible"`, `s3.endpoint`, `s3.path-style-access`, bucket/warehouse bindings, dbt profile fragments, and Helm value fragments.
- `plugins/floe-storage-minio/src/floe_storage_minio/config.py` documents `path_style_access` as required for MinIO and LocalStack.
- `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` declares storage requirements for `s3-compatible` and `s3`, supports path-style access, builds Polaris deployment bindings from storage warehouse state, and re-applies client-side `s3.endpoint` to loaded PyIceberg tables.
- `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`, `packages/floe-core/tests/unit/composition/test_resolver.py`, `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`, and `packages/floe-core/tests/unit/test_runtime_catalog_connection.py` assert MinIO/Polaris protocol compatibility, path-style access, secret-free bindings, and runtime catalog projection.
- `tests/e2e/conftest.py`, `tests/e2e/dbt_utils.py`, and current E2E suites default runtime catalog access to Polaris plus MinIO endpoints and `s3.path-style-access=true`.
- Architecture docs name future Glue, Hive, Nessie, GCS, and Azure paths, but targeted implementation search found those names only in docs and examples, not as production provider plugin packages or entry points.

The search therefore supports treating MinIO + Polaris as the only Level 3 provider combination today, with AWS Glue, Nessie, GCS, Azure/ADLS, and Hive as future provider paths requiring new plugin and binding work.

## Matrix Conclusion

AWS S3 plus Glue is the preferred first live target because it stresses native cloud storage, managed catalog semantics, IAM, and PyIceberg runtime translation. Nessie plus MinIO is the fallback because it validates catalog variation without cloud-provider setup.

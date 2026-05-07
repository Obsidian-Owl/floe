# REQ-041 to REQ-051: StoragePlugin Standards

**Domain**: Plugin Architecture
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

StoragePlugin emits a neutral, secret-free storage deployment binding for
pluggable object storage backends (S3, GCS, Azure Blob, MinIO). It may also
wrap the PyIceberg FileIO pattern for direct runtime access. Catalog, compute,
orchestrator, and deployment renderers consume the typed binding through their
own translators instead of receiving storage-owned per-consumer projections.

**Key ADR**: ADR-0036 (Storage Plugin Interface)

## Requirements

### REQ-041: StoragePlugin ABC Definition **[New]**

**Requirement**: StoragePlugin MUST define typed provider methods for neutral
storage composition: `get_deployment_binding()` and, where direct PyIceberg use
is supported, `get_pyiceberg_fileio()`.

**Rationale**: Enforces a composable interface where storage owns provider facts
and `floe-core` validates compatibility before catalogs, runtimes, and Helm
renderers consume the resolved deployment bindings.

**Acceptance Criteria**:
- [ ] ABC defined in `packages/floe-core/src/floe_core/plugins/storage.py`
- [ ] `get_deployment_binding()` defined with type hints and returns `StorageDeploymentBinding`
- [ ] Direct FileIO support, when provided, returns a PyIceberg-compatible `FileIO`
- [ ] Legacy helper methods are marked compatibility surface until removed by plugin uplift
- [ ] Docstrings explain purpose, parameters, return values
- [ ] mypy --strict passes on interface definition

**Enforcement**: ABC enforcement tests, mypy strict mode, plugin compliance test suite
**Test Coverage**: `tests/contract/test_storage_plugin.py::test_abc_compliance`
**Traceability**: plugin-architecture.md, ADR-0036

---

### REQ-042: StoragePlugin PyIceberg FileIO **[New]**

**Requirement**: StoragePlugin.get_pyiceberg_fileio() MUST return a PyIceberg-compatible FileIO instance for the storage backend.

**Rationale**: Enables PyIceberg to read and write Iceberg tables on any storage backend.

**Acceptance Criteria**:
- [ ] Returns PyIceberg FileIO instance (PyArrowFileIO, GCSFileIO, etc.)
- [ ] FileIO is immediately usable for table operations
- [ ] Credentials properly configured and not logged
- [ ] Supports multi-cloud backends (S3, GCS, Azure)
- [ ] FileIO passes PyIceberg API compliance

**Enforcement**: FileIO instantiation tests, API compliance tests
**Test Coverage**: `tests/integration/test_storage_fileio.py`
**Traceability**: ADR-0036

---

### REQ-043: StoragePlugin Deployment Binding **[New]**

**Requirement**: `StoragePlugin.get_deployment_binding()` MUST return a
secret-free `StorageDeploymentBinding` for the storage backend.

**Rationale**: Gives `floe-core`, catalog plugins, compute plugins,
orchestrators, and deployment renderers one typed storage contract without
coupling storage plugins to every consumer.

**Acceptance Criteria**:
- [ ] Includes protocol and endpoint roles
- [ ] Includes warehouse location and allowed locations
- [ ] Includes bucket requirements with purpose and create policy
- [ ] Includes credential references, never raw credential values
- [ ] Includes capabilities such as credential modes, path-style support, and STS support
- [ ] Includes provisioning intent for self-hosted storage such as MinIO

**Enforcement**: schema tests, composition resolver tests, catalog attachment tests
**Example**: MinIO returns an S3-compatible binding with bucket requirements and Kubernetes Secret refs.
**Test Coverage**: `plugins/floe-storage-minio/tests/unit/test_plugin.py`, `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`
**Traceability**: ADR-0036

---

### REQ-044: Storage Runtime Fragments **[New]**

**Requirement**: StoragePlugin runtime fragments MUST expose neutral,
secret-free storage facts and environment references for dbt and other runtimes.

**Rationale**: Enables dbt and compute runtimes to access Iceberg table files
without making storage plugins own dbt profile shape or SQL execution details.

**Acceptance Criteria**:
- [ ] Runtime fragments are JSON-compatible and schema validated
- [ ] Runtime fragments contain no raw credential material
- [ ] Credential use is represented by environment or Kubernetes Secret refs
- [ ] dbt-specific profile rendering is owned by the dbt/compute integration that consumes the binding
- [ ] Supports S3-compatible, GCS, and Azure-style runtime facts through typed capabilities

**Enforcement**: dbt profile generation tests, dbt debug tests
**Example**: `StorageRuntimeBinding.pyiceberg_properties` plus `env_refs`
**Test Coverage**: `tests/integration/test_storage_dbt_config.py`
**Traceability**: ADR-0036

---

### REQ-045: Orchestrator Storage Consumption **[New]**

**Requirement**: Orchestrator integrations MUST consume storage deployment
bindings or neutral runtime fragments instead of invoking storage-owned
orchestrator projection methods.

**Rationale**: Keeps Dagster, Airflow, and future orchestrators independently
composable with storage plugins.

**Acceptance Criteria**:
- [ ] Dagster storage resources derive from `CompiledArtifacts.deployment.storage`
- [ ] Runtime credentials use Secret/env refs, never compiled raw values
- [ ] Orchestrator-specific resource keys remain owned by the orchestrator integration
- [ ] Storage plugins do not import or construct Dagster resources

**Enforcement**: IOManager instantiation tests, asset I/O tests
**Test Coverage**: `tests/integration/test_storage_dagster_config.py`
**Traceability**: ADR-0036

---

### REQ-046: Storage Deployment Rendering **[New]**

**Requirement**: Helm values MUST be rendered from resolved deployment bindings,
not from storage plugin Helm override methods or raw chart credential values.

**Rationale**: Keeps deployment rendering declarative and prevents storage
plugins from knowing catalog-specific or chart-specific bootstrap formats.

**Acceptance Criteria**:
- [ ] For self-hosted MinIO, `deployment.storage.buckets` drives bucket creation values
- [ ] Catalog-specific storage fields come from `deployment.catalog`, not storage plugin config
- [ ] S3 credentials are Kubernetes Secret refs with key names
- [ ] Raw S3 access keys are not valid generated chart values
- [ ] Values validate against chart schema

**Enforcement**: Helm validation tests, Helm dry-run tests
**Test Coverage**: `packages/floe-core/tests/unit/helm/test_generate_cli.py`, `charts/floe-platform/tests/`
**Traceability**: ADR-0036

---

### REQ-047: StoragePlugin Credential Management **[New]**

**Requirement**: StoragePlugin MUST handle credentials securely with no secrets logged or exposed.

**Rationale**: Prevents credential compromise via logs or error messages.

**Acceptance Criteria**:
- [ ] Credentials never logged or printed
- [ ] Uses environment variables or K8s Secrets
- [ ] Supports multiple auth mechanisms per backend
- [ ] Compile-time artifacts carry credential references, not credential values
- [ ] Error messages never expose credential values

**Enforcement**: Credential security tests, secret scanning tests
**Test Coverage**: `tests/unit/test_storage_credentials.py`
**Traceability**: security.md, ADR-0036

---

### REQ-048: StoragePlugin Multi-Cloud Support **[New]**

**Requirement**: StoragePlugin implementations MUST support at least S3, GCS, Azure Blob and MinIO backends.

**Rationale**: Enables organizations to migrate or diversify across cloud providers without code changes.

**Acceptance Criteria**:
- [ ] S3Plugin: AWS S3 with IAM or access keys
- [ ] GCSPlugin: Google Cloud Storage with service account
- [ ] AzurePlugin: Azure Blob Storage with SAS tokens
- [ ] MinIOStoragePlugin: S3-compatible local/on-prem storage
- [ ] All backends pass compliance test suite

**Enforcement**: Multi-backend integration tests, portability tests
**Test Coverage**: `tests/integration/test_storage_backends.py`
**Traceability**: ADR-0036

---

### REQ-049: Storage Reachability Validation **[New]**

**Requirement**: Storage reachability validation MUST verify that configured
credential references and object storage endpoints are usable before production
deployment.

**Rationale**: Pre-deployment validation ensures storage is reachable without
making live infrastructure checks part of the compile-time StoragePlugin
contract.

**Acceptance Criteria**:
- [ ] Validation runs in an explicit integration/deployment lane, not during compile
- [ ] Uses credential references resolved by the runtime environment
- [ ] Tests credential validity where safe (e.g., list buckets)
- [ ] Returns boolean success/failure
- [ ] Error messages actionable (not stack traces)
- [ ] Validates without exposing credentials

**Enforcement**: Credential validation tests, error handling tests
**Test Coverage**: `tests/integration/test_storage_validation.py`
**Traceability**: ADR-0036

---

### REQ-050: StoragePlugin Compliance Test Suite **[New]**

**Requirement**: System MUST provide BaseStoragePluginTests class that all StoragePlugin implementations inherit to validate compliance.

**Rationale**: Ensures all storage backends meet minimum functionality requirements.

**Acceptance Criteria**:
- [ ] BaseStoragePluginTests in testing/base_classes/
- [ ] Tests the typed storage deployment binding contract
- [ ] Tests FileIO instantiation
- [ ] Tests warehouse, bucket, capability, and credential-reference fields
- [ ] Tests compatibility resolver interaction with catalog requirements
- [ ] Tests error handling

**Enforcement**: Plugin compliance tests must pass for all storage backends
**Test Coverage**: `testing/base_classes/base_storage_plugin_tests.py`
**Traceability**: TESTING.md

---

### REQ-051: StoragePlugin Test Fixtures **[New]**

**Requirement**: System MUST provide test fixtures for StoragePlugin implementations that extend the Epic 9C testing framework.

**Rationale**: Integration tests for storage adapters require object storage connectivity fixtures to validate FileIO operations, deployment bindings, and credential-reference management.

**Acceptance Criteria**:
- [ ] Fixture module: `testing/fixtures/storage.py` (extends 9C patterns)
- [ ] `StorageTestConfig(BaseModel)` with `frozen=True`
- [ ] Context manager: `storage_connection_context()` for lifecycle
- [ ] Cloud-specific fixtures: `s3_fixture()`, `gcs_fixture()`, `azure_fixture()` for testing
- [ ] Mock fixtures for unit tests (no real storage required)
- [ ] Extends: `IntegrationTestBase` from Epic 9C
- [ ] Type hints: mypy --strict passes
- [ ] Test coverage: >80% of fixture code

**Constraints**:
- MUST extend Epic 9C testing framework (`testing.base_classes`)
- MUST follow fixture pattern from `testing/fixtures/__init__.py`
- MUST use Pydantic v2 `ConfigDict(frozen=True)` for config
- MUST NOT duplicate MinIO fixture from Epic 9C (reference implementation)
- MUST support credential injection via environment variables or Kubernetes Secret refs

**Test Coverage**: `testing/tests/unit/test_storage_fixtures.py`

**Traceability**:
- Epic 9C (Testing Framework dependency)
- Epic 4D (StoragePlugin)
- ADR-0065 (K8s-native testing)

---

## Domain Acceptance Criteria

StoragePlugin Standards (REQ-041 to REQ-051) complete when:

- [ ] All 10 requirements documented with complete fields
- [ ] StoragePlugin ABC defined in floe-core
- [ ] At least 4 reference implementations (S3, GCS, MinIO, Azure)
- [ ] Contract tests pass for all implementations
- [ ] Integration tests validate file I/O operations
- [ ] Composition resolver validates storage/catalog compatibility
- [ ] Helm renders deployment bindings without literal storage secrets
- [ ] Documentation backreferences all requirements

## Epic Mapping

**Epic 3: Plugin Interface Extraction** - Extract storage abstraction to plugins

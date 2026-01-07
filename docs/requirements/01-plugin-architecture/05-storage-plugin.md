# REQ-041 to REQ-050: StoragePlugin Standards

**Domain**: Plugin Architecture
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

StoragePlugin wraps PyIceberg FileIO pattern for pluggable object storage backends (S3, GCS, Azure Blob, MinIO). This enables multi-cloud support while maintaining a single unified interface for data pipeline execution.

**Key ADR**: ADR-0036 (Storage Plugin Interface)

## Requirements

### REQ-041: StoragePlugin ABC Definition **[New]**

**Requirement**: StoragePlugin MUST define abstract methods: get_pyiceberg_fileio(), get_warehouse_uri(), get_dbt_profile_config(), get_dagster_io_manager_config(), get_helm_values_override().

**Rationale**: Enforces consistent interface for PyIceberg FileIO pattern across storage implementations.

**Acceptance Criteria**:
- [ ] ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 5 abstract methods defined with type hints
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

### REQ-043: StoragePlugin Warehouse URI **[New]**

**Requirement**: StoragePlugin.get_warehouse_uri() MUST return a valid warehouse URI for the storage backend with namespace scoping.

**Rationale**: Enables Iceberg catalog to locate table data files on storage.

**Acceptance Criteria**:
- [ ] Returns URI matching storage backend (s3://, gs://, abfss://)
- [ ] Includes namespace path for bronze/silver/gold separation
- [ ] URI is valid for Iceberg catalog warehouse location
- [ ] Supports path-style addressing for MinIO

**Enforcement**: URI validation tests, catalog attachment tests
**Example**: S3 returns `s3://bucket/warehouse/bronze`; GCS returns `gs://bucket/warehouse/bronze`
**Test Coverage**: `tests/unit/test_storage_warehouse_uri.py`
**Traceability**: ADR-0036

---

### REQ-044: StoragePlugin dbt Profile Config **[New]**

**Requirement**: StoragePlugin.get_dbt_profile_config() MUST return filesystem configuration for dbt-duckdb to access storage.

**Rationale**: Enables dbt to query Iceberg tables via DuckDB's filesystem plugins.

**Acceptance Criteria**:
- [ ] Returns dict with filesystems configuration
- [ ] Includes credentials references (${env:VAR} syntax)
- [ ] Supports S3, GCS, Azure filesystems
- [ ] Configuration integrates with dbt profiles.yml

**Enforcement**: dbt profile generation tests, dbt debug tests
**Example**: `{"filesystems": {"s3": {"key_id": "${env:AWS_ACCESS_KEY_ID}", ...}}}`
**Test Coverage**: `tests/integration/test_storage_dbt_config.py`
**Traceability**: ADR-0036

---

### REQ-045: StoragePlugin Dagster IOManager Config **[New]**

**Requirement**: StoragePlugin.get_dagster_io_manager_config() MUST return configuration for Dagster's IcebergIOManager.

**Rationale**: Enables Dagster to store and retrieve asset data on any storage backend.

**Acceptance Criteria**:
- [ ] Returns dict with storage_options configuration
- [ ] Includes credentials references (${env:VAR} syntax)
- [ ] Compatible with dagster-iceberg IOManager API
- [ ] Supports cloud provider auth mechanisms

**Enforcement**: IOManager instantiation tests, asset I/O tests
**Test Coverage**: `tests/integration/test_storage_dagster_config.py`
**Traceability**: ADR-0036

---

### REQ-046: StoragePlugin Helm Values **[New]**

**Requirement**: StoragePlugin.get_helm_values_override() MUST return Helm chart values for deploying storage services or empty dict for cloud storage.

**Rationale**: Enables declarative deployment of self-hosted storage (MinIO) via Helm.

**Acceptance Criteria**:
- [ ] For self-hosted (MinIO): returns valid Helm values
- [ ] For cloud storage (S3, GCS, Azure): returns empty dict
- [ ] Helm values include persistence configuration
- [ ] Values validate against chart schema

**Enforcement**: Helm validation tests, Helm dry-run tests
**Test Coverage**: `tests/unit/test_storage_helm_values.py`
**Traceability**: ADR-0036

---

### REQ-047: StoragePlugin Credential Management **[New]**

**Requirement**: StoragePlugin MUST handle credentials securely with no secrets logged or exposed.

**Rationale**: Prevents credential compromise via logs or error messages.

**Acceptance Criteria**:
- [ ] Credentials never logged or printed
- [ ] Uses environment variables or K8s Secrets
- [ ] Supports multiple auth mechanisms per backend
- [ ] validate_credentials() method checks presence
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
- [ ] MinIOPlugin: S3-compatible local/on-prem storage
- [ ] All backends pass compliance test suite

**Enforcement**: Multi-backend integration tests, portability tests
**Test Coverage**: `tests/integration/test_storage_backends.py`
**Traceability**: ADR-0036

---

### REQ-049: StoragePlugin Connection Validation **[New]**

**Requirement**: StoragePlugin.validate_credentials() MUST verify that storage credentials are valid and accessible.

**Rationale**: Pre-deployment validation ensures storage is reachable.

**Acceptance Criteria**:
- [ ] Tests credential validity (e.g., list buckets)
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
- [ ] Tests all ABC methods
- [ ] Tests FileIO instantiation
- [ ] Tests warehouse URI generation
- [ ] Tests credential validation
- [ ] Tests error handling

**Enforcement**: Plugin compliance tests must pass for all storage backends
**Test Coverage**: `testing/base_classes/base_storage_plugin_tests.py`
**Traceability**: TESTING.md

---

## Domain Acceptance Criteria

StoragePlugin Standards (REQ-041 to REQ-050) complete when:

- [ ] All 10 requirements documented with complete fields
- [ ] StoragePlugin ABC defined in floe-core
- [ ] At least 4 reference implementations (S3, GCS, MinIO, Azure)
- [ ] Contract tests pass for all implementations
- [ ] Integration tests validate file I/O operations
- [ ] Documentation backreferences all requirements

## Epic Mapping

**Epic 3: Plugin Interface Extraction** - Extract storage abstraction to plugins

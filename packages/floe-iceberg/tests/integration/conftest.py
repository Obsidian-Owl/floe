"""Integration test configuration for floe-iceberg.

Integration tests require real services (Polaris, S3/MinIO) and
inherit from IntegrationTestBase for service lifecycle management.

Fixtures:
    polaris_config: PolarisConfig for connecting to Polaris REST catalog
    polaris_catalog: PyIceberg Catalog instance connected to Polaris
    integration_catalog_plugin: CatalogPlugin wrapping real Polaris
    integration_storage_plugin: StoragePlugin wrapping real S3/MinIO

Test Credentials Pattern
------------------------
This module uses default credentials that match the K8s service bootstrap
configuration in ``testing/k8s/services/``. This is an **intentional design**:

1. **Polaris** (``test-admin:test-secret``):
   - Matches ``testing/k8s/services/polaris.yaml`` POLARIS_BOOTSTRAP_CREDENTIALS
   - Override via: ``POLARIS_CREDENTIAL`` environment variable

2. **MinIO** (``minioadmin:minioadmin123``):
   - Matches ``testing/k8s/services/minio.yaml`` root user configuration
   - Override via: ``MINIO_ACCESS_KEY`` and ``MINIO_SECRET_KEY`` environment variables

**Why defaults?** Integration tests run in Kind clusters where services are
bootstrapped with known credentials. The defaults enable zero-config local
testing while environment variables allow CI/CD override for different environments.

**Security Note**: These are TEST-ONLY credentials. Production systems MUST use
secure credential management (Kubernetes Secrets, HashiCorp Vault, etc.).

Note:
    No __init__.py files in test directories - pytest uses importlib mode.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING, Any, Protocol

import pytest
from testing.fixtures.polaris import (
    PolarisConfig,
    create_polaris_catalog,
    drop_test_namespace,
)
from testing.fixtures.services import get_effective_host

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog
    from pyiceberg.io import FileIO


# =============================================================================
# Protocol definitions for plugins
# =============================================================================


class CatalogPluginProtocol(Protocol):
    """Protocol for CatalogPlugin used by IcebergTableManager."""

    def connect(self) -> Any:
        """Connect and return a PyIceberg Catalog."""
        ...

    def create_namespace(
        self, namespace: str, properties: dict[str, str] | None = None
    ) -> None:
        """Create a namespace in the catalog."""
        ...

    @property
    def name(self) -> str:
        """Plugin name."""
        ...


class StoragePluginProtocol(Protocol):
    """Protocol for StoragePlugin used by IcebergTableManager."""

    def get_pyiceberg_fileio(self) -> Any:
        """Return a PyIceberg FileIO instance."""
        ...

    @property
    def name(self) -> str:
        """Plugin name."""
        ...


# =============================================================================
# Real Plugin Implementations
# =============================================================================


class IntegrationPolarisCatalogPlugin:
    """Real CatalogPlugin wrapping Polaris REST catalog.

    This is a minimal implementation that satisfies the CatalogPlugin protocol
    for integration testing with real Polaris.
    """

    def __init__(self, config: PolarisConfig) -> None:
        """Initialize with Polaris config."""
        self._config = config
        self._catalog: Catalog | None = None
        self._namespaces: list[str] = []
        self._tables: dict[str, Any] = {}

    def connect(self, config: dict[str, Any] | None = None) -> Catalog:
        """Connect and return PyIceberg Catalog.

        Args:
            config: Optional connection config. If not provided, uses
                the PolarisConfig from __init__.
        """
        if self._catalog is None:
            # If a config dict is provided, use it; otherwise use self._config
            if config:
                from pyiceberg.catalog import load_catalog

                self._catalog = load_catalog(
                    "polaris",
                    type="rest",
                    uri=config.get("uri", self._config.uri),
                    warehouse=config.get("warehouse", self._config.warehouse),
                    credential=config.get(
                        "credential", self._config.credential.get_secret_value()
                    ),
                    scope=config.get("scope", self._config.scope),
                )
            else:
                self._catalog = create_polaris_catalog(self._config)
        return self._catalog

    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create namespace in Polaris catalog."""
        # Ensure catalog is connected
        if self._catalog is None:
            self.connect()
        assert self._catalog is not None

        # Convert to tuple for PyIceberg API (namespace param is always str)
        ns_tuple = (namespace,)
        try:
            self._catalog.create_namespace(ns_tuple, properties or {})
            # Store as string for manager's _validate_namespace_exists check
            self._namespaces.append(namespace)
        except Exception:
            # Namespace might already exist
            pass

    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> Any:
        """Create a table in the Polaris catalog.

        Args:
            identifier: Full table identifier (e.g., "namespace.table_name").
            schema: Schema dictionary representation.
            location: Optional table location.
            properties: Optional table properties.

        Returns:
            PyIceberg Table instance.
        """
        if self._catalog is None:
            self.connect()
        assert self._catalog is not None

        # Parse identifier
        parts = identifier.split(".")
        if len(parts) != 2:
            msg = f"Invalid identifier format: {identifier}"
            raise ValueError(msg)

        namespace, table_name = parts

        # Convert schema dict to PyIceberg Schema
        from pyiceberg.schema import NestedField, Schema
        from pyiceberg.types import (
            BooleanType,
            DateType,
            DoubleType,
            FloatType,
            IntegerType,
            LongType,
            StringType,
            TimestampType,
            TimestamptzType,
        )

        type_mapping = {
            "boolean": BooleanType(),
            "int": IntegerType(),
            "long": LongType(),
            "float": FloatType(),
            "double": DoubleType(),
            "string": StringType(),
            "date": DateType(),
            "timestamp": TimestampType(),
            "timestamptz": TimestamptzType(),
        }

        fields = []
        for field_dict in schema.get("fields", []):
            field_type_str = field_dict.get("type", "string").lower()
            iceberg_type = type_mapping.get(field_type_str, StringType())
            fields.append(
                NestedField(
                    field_id=field_dict.get("field_id", len(fields) + 1),
                    name=field_dict["name"],
                    field_type=iceberg_type,
                    required=field_dict.get("required", False),
                    doc=field_dict.get("doc"),
                )
            )

        iceberg_schema = Schema(*fields)

        # Create table properties
        table_props = dict(properties or {})
        if location:
            table_props["location"] = location

        # Create the table
        table = self._catalog.create_table(
            identifier=(namespace, table_name),
            schema=iceberg_schema,
            properties=table_props,
        )

        # Track the table
        self._tables[identifier] = table

        return table

    def cleanup_namespaces(self) -> None:
        """Clean up all created namespaces."""
        if self._catalog is None:
            return
        for ns in self._namespaces:
            try:
                drop_test_namespace(self._catalog, (ns,), cascade=True)
            except Exception:
                pass

    @property
    def name(self) -> str:
        """Plugin name."""
        return "polaris"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Floe API version."""
        return "1.0"


class IntegrationMinIOStoragePlugin:
    """Real StoragePlugin wrapping MinIO S3 storage.

    This is a minimal implementation that satisfies the StoragePlugin protocol
    for integration testing with real MinIO.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin123",
        bucket: str = "floe-warehouse",
    ) -> None:
        """Initialize with MinIO config."""
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket = bucket

    def get_pyiceberg_fileio(self) -> FileIO:
        """Return PyIceberg FileIO configured for MinIO."""
        from pyiceberg.io import load_file_io

        return load_file_io(
            {
                "s3.endpoint": self._endpoint,
                "s3.access-key-id": self._access_key,
                "s3.secret-access-key": self._secret_key,
                "s3.region": "us-east-1",
                "s3.path-style-access": "true",
            },
            location=f"s3://{self._bucket}",
        )

    def get_warehouse_uri(self, namespace: str) -> str:
        """Generate warehouse URI for namespace."""
        return f"s3://{self._bucket}/{namespace}"

    def get_dbt_profile_config(self) -> dict[str, Any]:
        """Generate dbt profile configuration for MinIO."""
        return {
            "s3_endpoint": self._endpoint,
            "s3_access_key_id": self._access_key,
            "s3_secret_access_key": self._secret_key,
            "s3_region": "us-east-1",
        }

    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        """Generate Dagster IOManager configuration for MinIO."""
        return {
            "endpoint": self._endpoint,
            "access_key_id": self._access_key,
            "secret_access_key": self._secret_key,
            "region": "us-east-1",
            "bucket": self._bucket,
        }

    def get_helm_values_override(self) -> dict[str, Any]:
        """Generate Helm values override for MinIO."""
        return {
            "storage": {
                "endpoint": self._endpoint,
                "bucket": self._bucket,
            }
        }

    @property
    def warehouse_path(self) -> str:
        """Return S3 warehouse path."""
        return f"s3://{self._bucket}"

    @property
    def name(self) -> str:
        """Plugin name."""
        return "minio"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Floe API version."""
        return "1.0"


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def polaris_config() -> PolarisConfig:
    """Get Polaris configuration for tests.

    Uses environment variables if set, otherwise defaults to localhost
    (Kind cluster NodePort).

    Default credentials match testing/k8s/services/polaris.yaml bootstrap credentials.
    """
    host = get_effective_host("polaris", "floe-test")
    uri = f"http://{host}:8181/api/catalog"

    return PolarisConfig(
        uri=uri,
        warehouse=os.environ.get("POLARIS_WAREHOUSE", "test_warehouse"),
        # Default to test-admin:test-secret from POLARIS_BOOTSTRAP_CREDENTIALS
        credential=os.environ.get("POLARIS_CREDENTIAL", "test-admin:test-secret"),
        scope=os.environ.get("POLARIS_SCOPE", "PRINCIPAL_ROLE:ALL"),
    )


@pytest.fixture(scope="function")
def polaris_catalog(polaris_config: PolarisConfig) -> Catalog:
    """Get connected PyIceberg Catalog instance."""
    return create_polaris_catalog(polaris_config)


@pytest.fixture(scope="function")
def integration_catalog_plugin(
    polaris_config: PolarisConfig,
) -> IntegrationPolarisCatalogPlugin:
    """Get real CatalogPlugin wrapping Polaris.

    Yields plugin and cleans up created namespaces after test.
    """
    plugin = IntegrationPolarisCatalogPlugin(polaris_config)
    yield plugin
    plugin.cleanup_namespaces()


@pytest.fixture(scope="function")
def integration_storage_plugin() -> IntegrationMinIOStoragePlugin:
    """Get real StoragePlugin wrapping MinIO.

    Default credentials match testing/k8s/services/minio.yaml configuration.
    Bucket name matches init-polaris.sh warehouse location.
    """
    host = get_effective_host("minio", "floe-test")
    endpoint = f"http://{host}:9000"

    return IntegrationMinIOStoragePlugin(
        endpoint=endpoint,
        access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin123"),
        bucket=os.environ.get("MINIO_BUCKET", "floe-warehouse"),
    )


@pytest.fixture(scope="function")
def unique_namespace() -> str:
    """Generate a unique namespace for test isolation."""
    return f"test_{uuid.uuid4().hex[:8]}"


__all__ = [
    "CatalogPluginProtocol",
    "IntegrationMinIOStoragePlugin",
    "IntegrationPolarisCatalogPlugin",
    "StoragePluginProtocol",
    "polaris_catalog",
    "polaris_config",
    "integration_catalog_plugin",
    "integration_storage_plugin",
    "unique_namespace",
]

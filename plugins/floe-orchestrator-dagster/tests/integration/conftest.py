"""Integration test configuration for floe-orchestrator-dagster.

Integration tests require real services (Polaris, MinIO) and
inherit from IntegrationTestBase for service lifecycle management.

Fixtures:
    polaris_config: PolarisConfig for connecting to Polaris REST catalog
    integration_catalog_plugin: CatalogPlugin wrapping real Polaris
    integration_storage_plugin: StoragePlugin wrapping real S3/MinIO
    real_table_manager: IcebergTableManager with real plugins
    real_io_manager: IcebergIOManager wrapping real table manager
    sample_pyarrow_table: Real PyArrow table for test data

Test Credentials Pattern
------------------------
This module uses default credentials that match the K8s service bootstrap
configuration in ``testing/k8s/services/``. This is an **intentional design**:

1. **Polaris** (``demo-admin:demo-secret``):
   - Matches ``testing/k8s/services/polaris.yaml`` POLARIS_BOOTSTRAP_CREDENTIALS
   - Override via: ``POLARIS_CREDENTIAL`` environment variable

2. **MinIO** (``minioadmin:minioadmin123``):
   - Matches ``testing/k8s/services/minio.yaml`` root user configuration
   - Override via: ``MINIO_ACCESS_KEY`` and ``MINIO_SECRET_KEY`` environment variables

**Security Note**: These are TEST-ONLY credentials. Production systems MUST use
secure credential management (Kubernetes Secrets, HashiCorp Vault, etc.).

Note:
    No __init__.py files in test directories - pytest uses importlib mode.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING, Any, Generator

import pyarrow as pa
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


class IntegrationPolarisCatalogPlugin:
    """Real CatalogPlugin wrapping Polaris REST catalog.

    This is a minimal implementation that satisfies the CatalogPlugin protocol
    for integration testing with real Polaris.
    """

    def __init__(
        self,
        config: PolarisConfig,
    ) -> None:
        """Initialize with Polaris config.

        Args:
            config: Polaris connection configuration.
        """
        self._config = config
        self._catalog: Catalog | None = None
        self._namespaces: list[str] = []
        self._tables: dict[str, Any] = {}

    def connect(self, config: dict[str, Any] | None = None) -> Catalog:
        """Connect and return PyIceberg Catalog.

        Args:
            config: Optional connection config. If provided, merges with
                PolarisConfig defaults. Extra keys (e.g., oauth2-server-uri)
                are passed through to load_catalog.
        """
        if self._catalog is None:
            if config:
                from pyiceberg.catalog import load_catalog

                # Build kwargs from config, falling back to PolarisConfig
                catalog_kwargs: dict[str, Any] = {
                    "type": "rest",
                    "uri": config.get("uri", self._config.uri),
                    "warehouse": config.get("warehouse", self._config.warehouse),
                    "credential": config.get(
                        "credential", self._config.credential.get_secret_value()
                    ),
                    "scope": config.get("scope", self._config.scope),
                }
                # Forward extra config keys (e.g., oauth2-server-uri)
                for key in config:
                    if key not in catalog_kwargs:
                        catalog_kwargs[key] = config[key]

                self._catalog = load_catalog("polaris", **catalog_kwargs)
            else:
                self._catalog = create_polaris_catalog(self._config)
        return self._catalog

    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create namespace in Polaris catalog."""
        if self._catalog is None:
            self.connect()
        assert self._catalog is not None

        ns_tuple = (namespace,)
        try:
            self._catalog.create_namespace(ns_tuple, properties or {})
            self._namespaces.append(namespace)
        except Exception:
            pass

    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> Any:
        """Create a table in the Polaris catalog."""
        if self._catalog is None:
            self.connect()
        assert self._catalog is not None

        parts = identifier.split(".")
        if len(parts) != 2:
            msg = f"Invalid identifier format: {identifier}"
            raise ValueError(msg)

        namespace, table_name = parts

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
        table_props = dict(properties or {})
        if location:
            table_props["location"] = location

        table = self._catalog.create_table(
            identifier=(namespace, table_name),
            schema=iceberg_schema,
            properties=table_props,
        )
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


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests",
    )


@pytest.fixture(scope="function")
def polaris_config() -> PolarisConfig:
    """Get Polaris configuration for tests.

    Uses environment variables if set, otherwise defaults to localhost
    (Kind cluster NodePort).
    """
    host = get_effective_host("polaris", "floe-test")
    uri = f"http://{host}:8181/api/catalog"

    return PolarisConfig(
        uri=uri,
        warehouse=os.environ.get("POLARIS_WAREHOUSE", "floe-e2e"),
        credential=os.environ.get("POLARIS_CREDENTIAL", "demo-admin:demo-secret"),
        scope=os.environ.get("POLARIS_SCOPE", "PRINCIPAL_ROLE:ALL"),
    )


@pytest.fixture(scope="function")
def integration_catalog_plugin(
    polaris_config: PolarisConfig,
) -> Generator[IntegrationPolarisCatalogPlugin, None, None]:
    """Get real CatalogPlugin wrapping Polaris.

    Yields plugin and cleans up created namespaces after test.
    Tests run inside K8s where service hostnames resolve natively.
    """
    plugin = IntegrationPolarisCatalogPlugin(polaris_config)
    yield plugin
    plugin.cleanup_namespaces()


@pytest.fixture(scope="function")
def integration_storage_plugin() -> IntegrationMinIOStoragePlugin:
    """Get real StoragePlugin wrapping MinIO.

    Default credentials match testing/k8s/services/minio.yaml configuration.
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


@pytest.fixture(scope="function")
def real_table_manager(
    integration_catalog_plugin: IntegrationPolarisCatalogPlugin,
    integration_storage_plugin: IntegrationMinIOStoragePlugin,
    polaris_config: PolarisConfig,
) -> Any:
    """Create real IcebergTableManager with real plugins.

    Passes catalog_connection_config to override the default memory://
    fallback in IcebergTableManager._connect_to_catalog().

    S3 credentials are included so PyIceberg can write to MinIO.
    When tests run inside K8s (Option B), hostnames resolve natively
    via K8s DNS — no monkey-patching required.
    """
    from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig

    # Build catalog connection config with explicit OAuth2 server URI
    # to avoid PyIceberg's memory:// fallback (pyiceberg#10537)
    oauth2_server_uri = polaris_config.uri.replace("/api/catalog", "") + "/api/catalog/v1/oauth/tokens"
    minio_host = get_effective_host("minio", "floe-test")

    return IcebergTableManager(
        catalog_plugin=integration_catalog_plugin,
        storage_plugin=integration_storage_plugin,
        config=IcebergTableManagerConfig(
            catalog_connection_config={
                "uri": polaris_config.uri,
                "warehouse": polaris_config.warehouse,
                "credential": polaris_config.credential.get_secret_value(),
                "scope": polaris_config.scope,
                "oauth2-server-uri": oauth2_server_uri,
                "s3.endpoint": f"http://{minio_host}:9000",
                "s3.access-key-id": os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
                "s3.secret-access-key": os.environ.get("MINIO_SECRET_KEY", "minioadmin123"),
                "s3.region": "us-east-1",
                "s3.path-style-access": "true",
            },
        ),
    )


@pytest.fixture(scope="function")
def real_io_manager(
    real_table_manager: Any,
    unique_namespace: str,
    integration_catalog_plugin: IntegrationPolarisCatalogPlugin,
) -> Any:
    """Create real IcebergIOManager wrapping real table manager.

    Also creates the test namespace in Polaris so tables can be written.
    """
    from floe_orchestrator_dagster.io_manager import (
        IcebergIOManager,
        IcebergIOManagerConfig,
    )

    # Create namespace in catalog for this test
    integration_catalog_plugin.create_namespace(unique_namespace)

    config = IcebergIOManagerConfig(
        namespace=unique_namespace,
        default_write_mode="append",
        infer_schema_from_data=True,
    )

    return IcebergIOManager(
        table_manager=real_table_manager,
        config=config,
    )


@pytest.fixture
def sample_pyarrow_table() -> pa.Table:
    """Real PyArrow table for testing."""
    return pa.table(
        {
            "id": pa.array([1, 2, 3], type=pa.int64()),
            "name": pa.array(["Alice", "Bob", "Charlie"], type=pa.string()),
            "amount": pa.array([100.0, 200.0, 300.0], type=pa.float64()),
        }
    )


__all__ = [
    "IntegrationMinIOStoragePlugin",
    "IntegrationPolarisCatalogPlugin",
    "integration_catalog_plugin",
    "integration_storage_plugin",
    "polaris_config",
    "real_io_manager",
    "real_table_manager",
    "sample_pyarrow_table",
    "unique_namespace",
]

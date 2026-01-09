"""Polaris catalog pytest fixture for integration tests.

Provides Polaris REST catalog fixture for tests running in Kind cluster.

Example:
    from testing.fixtures.polaris import polaris_catalog_context

    def test_with_catalog(polaris_catalog):
        namespace = polaris_catalog.create_namespace("test_ns")
        tables = polaris_catalog.list_tables(namespace)
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog  # type: ignore[import-not-found]


class PolarisConfig(BaseModel):
    """Configuration for Polaris catalog connection.

    Attributes:
        uri: Polaris REST API endpoint URL.
        warehouse: Default warehouse name.
        credential: OAuth2 client credentials (client_id:client_secret).
        scope: OAuth2 scope for token request.
        namespace: K8s namespace where Polaris runs.
    """

    model_config = ConfigDict(frozen=True)

    uri: str = Field(
        default_factory=lambda: os.environ.get("POLARIS_URI", "http://polaris:8181/api/catalog")
    )
    warehouse: str = Field(
        default_factory=lambda: os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")
    )
    credential: SecretStr = Field(
        default_factory=lambda: SecretStr(os.environ.get("POLARIS_CREDENTIAL", "root:secret"))
    )
    scope: str = Field(
        default_factory=lambda: os.environ.get("POLARIS_SCOPE", "PRINCIPAL_ROLE:ALL")
    )
    namespace: str = Field(default="floe-test")

    @property
    def k8s_uri(self) -> str:
        """Get K8s DNS URI for Polaris service."""
        # Parse URI and replace host with K8s DNS name
        if "://" in self.uri:
            proto, rest = self.uri.split("://", 1)
            host_port, path = rest.split("/", 1) if "/" in rest else (rest, "")
            host = host_port.split(":")[0]
            port = host_port.split(":")[1] if ":" in host_port else "8181"
            k8s_host = f"{host}.{self.namespace}.svc.cluster.local"
            return f"{proto}://{k8s_host}:{port}/{path}"
        return self.uri


class PolarisConnectionError(Exception):
    """Raised when Polaris catalog connection fails."""

    pass


def create_polaris_catalog(config: PolarisConfig) -> Catalog:
    """Create Polaris REST catalog from config.

    Args:
        config: Polaris configuration.

    Returns:
        PyIceberg Catalog instance connected to Polaris.

    Raises:
        PolarisConnectionError: If catalog creation fails.
    """
    try:
        from pyiceberg.catalog import load_catalog
    except ImportError as e:
        raise PolarisConnectionError(
            "pyiceberg not installed. Install with: pip install pyiceberg"
        ) from e

    try:
        catalog = load_catalog(
            "polaris",
            type="rest",
            uri=config.uri,
            warehouse=config.warehouse,
            credential=config.credential.get_secret_value(),
            scope=config.scope,
        )
        return catalog
    except Exception as e:
        raise PolarisConnectionError(
            f"Failed to create Polaris catalog at {config.uri}: {e}"
        ) from e


@contextmanager
def polaris_catalog_context(
    config: PolarisConfig | None = None,
) -> Generator[Catalog, None, None]:
    """Context manager for Polaris catalog.

    Creates catalog on entry, no cleanup needed on exit.

    Args:
        config: Optional PolarisConfig. Uses defaults if not provided.

    Yields:
        PyIceberg Catalog instance.

    Example:
        with polaris_catalog_context() as catalog:
            namespaces = catalog.list_namespaces()
    """
    if config is None:
        config = PolarisConfig()

    catalog = create_polaris_catalog(config)
    yield catalog
    # PyIceberg catalog doesn't need explicit close


def create_test_namespace(
    catalog: Catalog,
    namespace: str | tuple[str, ...],
) -> tuple[str, ...]:
    """Create a test namespace in the catalog.

    Args:
        catalog: PyIceberg catalog.
        namespace: Namespace name or tuple of namespace parts.

    Returns:
        Namespace as tuple (for PyIceberg API consistency).
    """
    if isinstance(namespace, str):
        namespace = (namespace,)

    catalog.create_namespace(namespace)
    return namespace


def drop_test_namespace(
    catalog: Catalog,
    namespace: str | tuple[str, ...],
    *,
    cascade: bool = True,
) -> None:
    """Drop a test namespace from the catalog.

    Args:
        catalog: PyIceberg catalog.
        namespace: Namespace name or tuple of namespace parts.
        cascade: If True, drop all tables in namespace first.
    """
    if isinstance(namespace, str):
        namespace = (namespace,)

    if cascade:
        # Drop all tables in namespace first
        for table in catalog.list_tables(namespace):
            catalog.drop_table(table)

    catalog.drop_namespace(namespace)


def namespace_exists(
    catalog: Catalog,
    namespace: str | tuple[str, ...],
) -> bool:
    """Check if namespace exists in catalog.

    Args:
        catalog: PyIceberg catalog.
        namespace: Namespace name or tuple of namespace parts.

    Returns:
        True if namespace exists.
    """
    if isinstance(namespace, str):
        namespace = (namespace,)

    return namespace in catalog.list_namespaces()


def get_connection_info(config: PolarisConfig) -> dict[str, Any]:
    """Get connection info dictionary (for logging/debugging).

    Args:
        config: Polaris configuration.

    Returns:
        Dictionary with connection info (credential masked).
    """
    return {
        "uri": config.uri,
        "warehouse": config.warehouse,
        "scope": config.scope,
        "namespace": config.namespace,
        "k8s_uri": config.k8s_uri,
    }


__all__ = [
    "PolarisConfig",
    "PolarisConnectionError",
    "create_polaris_catalog",
    "create_test_namespace",
    "drop_test_namespace",
    "get_connection_info",
    "namespace_exists",
    "polaris_catalog_context",
]

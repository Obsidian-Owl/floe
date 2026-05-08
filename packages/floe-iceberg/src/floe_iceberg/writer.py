"""Orchestrator-neutral Iceberg table writer contract."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from inspect import getattr_static
from typing import Any, Literal, Protocol, cast, runtime_checkable

from floe_iceberg.errors import (
    is_stale_table_metadata_error,
    stale_table_metadata_error_from_exception,
)
from floe_iceberg.models import IcebergTableManagerConfig, StaleTableRecoveryMode

try:
    from pyiceberg.exceptions import (
        NamespaceAlreadyExistsError as _NamespaceAlreadyExistsError,
    )
    from pyiceberg.exceptions import (
        NoSuchIcebergTableError as _NoSuchIcebergTableError,
    )
    from pyiceberg.exceptions import (
        NoSuchTableError as _NoSuchTableError,
    )
except ImportError:  # pragma: no cover - PyIceberg is optional at import time.
    _NamespaceAlreadyExistsError = None  # type: ignore[assignment,misc]
    _NoSuchIcebergTableError = None  # type: ignore[assignment,misc]
    _NoSuchTableError = None  # type: ignore[assignment,misc]

IcebergWriteMode = Literal["append", "overwrite"]

_NULL_SEQUENCE_OVERWRITE_ERROR = "only entries with status added can have null sequence number"


@runtime_checkable
class WriteCapableIcebergCatalog(Protocol):
    """Catalog operations required by Iceberg table writes."""

    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create an Iceberg namespace."""
        ...

    def load_table(self, identifier: str) -> Any:
        """Load an existing Iceberg table."""
        ...

    def create_table(
        self,
        identifier: str,
        schema: Any,
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> Any:
        """Create an Iceberg table."""
        ...


class EndpointPreservingTableLoader(Protocol):
    """Optional catalog plugin hook for endpoint-preserving table loads."""

    def load_table_with_client_endpoint(self, identifier: str) -> Any:
        """Load a table while preserving client-side storage endpoint config."""
        ...


class IcebergTableWriter(Protocol):
    """Contract for writing Arrow-compatible data to Iceberg tables."""

    def ensure_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Ensure the destination namespace exists."""
        ...

    def write_table(
        self,
        identifier: str,
        arrow_table: Any,
        *,
        mode: IcebergWriteMode = "overwrite",
    ) -> None:
        """Write one table."""
        ...

    def write_tables(
        self,
        namespace: str,
        writes: Iterable[IcebergTableWrite],
    ) -> IcebergWriterResult:
        """Write a batch of tables."""
        ...


@dataclass(frozen=True)
class IcebergTableWrite:
    """Description of one Iceberg table write."""

    identifier: str
    arrow_table: Any
    mode: IcebergWriteMode = "overwrite"


@dataclass(frozen=True)
class IcebergWriterResult:
    """Result proving concrete Iceberg table writes occurred."""

    tables_written: int
    table_names: tuple[str, ...]


class DefaultIcebergTableWriter:
    """Default writer for orchestrator-neutral Iceberg table writes."""

    def __init__(
        self,
        catalog_plugin: object,
        storage_plugin: object,
        catalog_connection_config: dict[str, Any] | None = None,
        config: IcebergTableManagerConfig | None = None,
    ) -> None:
        """Initialize the writer.

        Args:
            catalog_plugin: Catalog plugin used to connect to an Iceberg catalog.
            storage_plugin: Storage plugin used for default PyIceberg catalog config.
            catalog_connection_config: Optional explicit catalog connection config.
            config: Optional Iceberg manager configuration for stale metadata repair.
        """
        self._catalog_plugin = catalog_plugin
        self._storage_plugin = storage_plugin
        self._catalog_connection_config = catalog_connection_config
        self._config = config or IcebergTableManagerConfig()
        self._catalog: WriteCapableIcebergCatalog | None = None

    def ensure_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Ensure the Iceberg namespace exists.

        Existing namespace errors are idempotent success.
        """
        catalog = self._connect_catalog()
        try:
            catalog.create_namespace(namespace, properties)
        except Exception as exc:
            if _is_existing_namespace_error(exc):
                return
            raise

    def write_table(
        self,
        identifier: str,
        arrow_table: Any,
        *,
        mode: IcebergWriteMode = "overwrite",
    ) -> None:
        """Write one table to Iceberg."""
        _validate_write_mode(mode)
        table, created = self._load_or_create_table(identifier, arrow_table)

        if not created:
            if mode == "append":
                table.append(arrow_table)
            elif mode == "overwrite":
                try:
                    table.overwrite(arrow_table)
                except Exception as exc:
                    table = self._repair_and_recreate(identifier, arrow_table, exc)

        if hasattr(table, "refresh"):
            table.refresh()

    def write_tables(
        self,
        namespace: str,
        writes: Iterable[IcebergTableWrite],
    ) -> IcebergWriterResult:
        """Write a batch of tables and return a write summary."""
        pending_writes = tuple(writes)
        for write in pending_writes:
            _validate_write_mode(write.mode)

        self.ensure_namespace(namespace)
        table_names: list[str] = []
        for write in pending_writes:
            self.write_table(write.identifier, write.arrow_table, mode=write.mode)
            table_names.append(write.identifier)
        return IcebergWriterResult(
            tables_written=len(table_names),
            table_names=tuple(table_names),
        )

    def _load_or_create_table(self, identifier: str, arrow_table: Any) -> tuple[Any, bool]:
        catalog = self._connect_catalog()
        try:
            return self._load_table(identifier), False
        except Exception as exc:
            if _is_repairable_table_state_error(exc):
                return self._repair_and_recreate(identifier, arrow_table, exc), True
            if not _is_missing_table_error(exc):
                raise
        table = _create_table(catalog, identifier, arrow_table)
        # A newly created table is empty, so append is equivalent to overwrite.
        table.append(arrow_table)
        return table, True

    def _load_table(self, identifier: str) -> Any:
        catalog = self._connect_catalog()
        method_marker = getattr_static(
            self._catalog_plugin,
            "load_table_with_client_endpoint",
            None,
        )
        method = getattr(self._catalog_plugin, "load_table_with_client_endpoint", None)
        if method_marker is not None and callable(method):
            loader = cast(EndpointPreservingTableLoader, self._catalog_plugin)
            return loader.load_table_with_client_endpoint(identifier)
        return catalog.load_table(identifier)

    def _repair_and_recreate(
        self,
        identifier: str,
        arrow_table: Any,
        exc: Exception,
    ) -> Any:
        is_stale_metadata = is_stale_table_metadata_error(exc)
        is_repairable_overwrite_state = _is_repairable_overwrite_state_error(exc)
        if not is_stale_metadata and not is_repairable_overwrite_state:
            raise

        if self._config.stale_table_recovery_mode is StaleTableRecoveryMode.STRICT:
            if is_stale_metadata:
                stale_error = stale_table_metadata_error_from_exception(
                    table_identifier=identifier,
                    recovery_mode=self._config.stale_table_recovery_mode,
                    original_error=exc,
                )
                raise stale_error from exc
            raise

        drop_table = getattr(self._catalog_plugin, "drop_table", None)
        if not callable(drop_table):
            raise
        drop_table(identifier, purge=False)
        self._catalog = None
        catalog = self._connect_catalog()
        table = _create_table(catalog, identifier, arrow_table)
        table.append(arrow_table)
        return table

    def _connect_catalog(self) -> WriteCapableIcebergCatalog:
        if self._catalog is not None:
            return self._catalog

        connect = getattr(self._catalog_plugin, "connect", None)
        if not callable(connect):
            msg = (
                "Catalog plugin did not return a write-capable Iceberg catalog; "
                "missing method(s): connect"
            )
            raise RuntimeError(msg)

        catalog = connect(config=self._catalog_config())
        self._catalog = _require_write_capable_catalog(catalog)
        return self._catalog

    def _catalog_config(self) -> dict[str, Any]:
        if self._catalog_connection_config is not None:
            return self._catalog_connection_config

        get_config = getattr(self._storage_plugin, "get_pyiceberg_catalog_config", None)
        if callable(get_config):
            config = get_config()
            if isinstance(config, dict):
                return config
        return {}


def _require_write_capable_catalog(catalog: object) -> WriteCapableIcebergCatalog:
    required_methods = ("create_namespace", "load_table", "create_table")
    missing_methods = [
        method for method in required_methods if not callable(getattr(catalog, method, None))
    ]
    if missing_methods:
        missing = ", ".join(missing_methods)
        msg = (
            "Catalog plugin did not return a write-capable Iceberg catalog; "
            f"missing method(s): {missing}"
        )
        raise RuntimeError(msg)
    return cast(WriteCapableIcebergCatalog, catalog)


def _arrow_schema(data: Any) -> Any:
    schema = getattr(data, "schema", None)
    if schema is None:
        msg = "Iceberg table writes require data with an Arrow schema"
        raise RuntimeError(msg)
    return schema


def _create_table(
    catalog: WriteCapableIcebergCatalog,
    identifier: str,
    arrow_table: Any,
) -> Any:
    return catalog.create_table(identifier, schema=_arrow_schema(arrow_table))


def _validate_write_mode(mode: str) -> None:
    if mode in ("append", "overwrite"):
        return
    msg = f"Unsupported Iceberg write mode: {mode}"
    raise ValueError(msg)


def _is_existing_namespace_error(exc: Exception) -> bool:
    if _NamespaceAlreadyExistsError is not None and isinstance(
        exc,
        _NamespaceAlreadyExistsError,
    ):
        return True
    exc_name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "alreadyexists" in exc_name or "already exists" in message


def _is_missing_table_error(exc: Exception) -> bool:
    if _NoSuchTableError is not None and isinstance(exc, _NoSuchTableError):
        return True
    if _NoSuchIcebergTableError is not None and isinstance(exc, _NoSuchIcebergTableError):
        return True
    exc_name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "nosuchtable" in exc_name or "no such table" in message


def _is_repairable_overwrite_state_error(exc: Exception) -> bool:
    return _NULL_SEQUENCE_OVERWRITE_ERROR in str(exc).lower()


def _is_repairable_table_state_error(exc: Exception) -> bool:
    return is_stale_table_metadata_error(exc) or _is_repairable_overwrite_state_error(exc)


__all__ = [
    "DefaultIcebergTableWriter",
    "EndpointPreservingTableLoader",
    "IcebergTableWrite",
    "IcebergTableWriter",
    "IcebergWriteMode",
    "IcebergWriterResult",
    "WriteCapableIcebergCatalog",
]

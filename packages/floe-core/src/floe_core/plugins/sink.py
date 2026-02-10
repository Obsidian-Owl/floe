"""SinkConnector ABC for reverse ETL plugins.

This module defines the abstract base class for reverse ETL plugins that
push curated data from the Iceberg Gold layer to external SaaS APIs and
databases. SinkConnector is an opt-in mixin — plugins can implement both
IngestionPlugin and SinkConnector for bidirectional data movement.

SinkConnector is independently implementable: it does NOT require
inheritance from PluginMetadata or IngestionPlugin (FR-015).

Example:
    >>> from floe_core.plugins.sink import SinkConnector, SinkConfig, EgressResult
    >>> class MySinkPlugin(SinkConnector):
    ...     def list_available_sinks(self) -> list[str]:
    ...         return ["rest_api"]
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SinkConfig:
    """Configuration for a reverse ETL sink destination.

    Attributes:
        sink_type: Sink identifier (e.g., "rest_api", "sql_database").
        connection_config: Destination-specific connection configuration.
        field_mapping: Source-to-destination column name translation.
        retry_config: Retry policy configuration.
        batch_size: Auto-chunking size (None = all rows at once).

    Example:
        >>> config = SinkConfig(
        ...     sink_type="rest_api",
        ...     connection_config={"base_url": "https://api.example.com"},
        ...     field_mapping={"customer_id": "Id", "email": "Email"},
        ...     batch_size=500,
        ... )
    """

    sink_type: str
    connection_config: dict[str, Any] = field(default_factory=lambda: {})
    field_mapping: dict[str, str] | None = None
    retry_config: dict[str, Any] | None = None
    batch_size: int | None = None

    def __post_init__(self) -> None:
        """Validate SinkConfig fields at construction time.

        Raises:
            ValueError: If any field fails validation.
        """
        # sink_type must be non-empty
        if not self.sink_type or not self.sink_type.strip():
            msg = "sink_type must be a non-empty string"
            raise ValueError(msg)

        # batch_size bounds: 1 <= batch_size <= 100_000
        if self.batch_size is not None:
            if self.batch_size < 1:
                msg = f"batch_size must be >= 1, got {self.batch_size}"
                raise ValueError(msg)
            if self.batch_size > 100_000:
                msg = f"batch_size must be <= 100_000, got {self.batch_size}"
                raise ValueError(msg)

        # connection_config depth/size limits
        if len(self.connection_config) > 50:
            msg = f"connection_config has {len(self.connection_config)} keys, max 50"
            raise ValueError(msg)

        # field_mapping values must be valid identifiers (prevent injection)
        if self.field_mapping is not None:
            identifier_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
            for source, dest in self.field_mapping.items():
                if not identifier_pattern.match(dest):
                    msg = (
                        f"field_mapping destination '{dest}' for source "
                        f"'{source}' must be a valid identifier "
                        "(alphanumeric + underscore)"
                    )
                    raise ValueError(msg)


@dataclass
class EgressResult:
    """Result of a reverse ETL egress operation.

    Provides a rich delivery receipt with load-assurance fields for
    confirming successful data delivery to external systems.

    Attributes:
        success: Whether the egress operation succeeded.
        rows_delivered: Number of rows delivered to destination.
        bytes_transmitted: Bytes transmitted to destination.
        duration_seconds: Execution duration in seconds.
        checksum: SHA-256 checksum of delivered payload.
        delivery_timestamp: ISO-8601 delivery timestamp.
        idempotency_key: Key for retry deduplication.
        destination_record_ids: IDs returned by destination API.
        errors: List of error messages if failed.

    Example:
        >>> result = EgressResult(
        ...     success=True,
        ...     rows_delivered=1000,
        ...     bytes_transmitted=524288,
        ...     duration_seconds=2.5,
        ...     checksum="sha256:abc123...",
        ...     delivery_timestamp="2026-01-15T10:30:00Z",
        ...     idempotency_key="batch-001-uuid",
        ... )
    """

    success: bool
    rows_delivered: int = 0
    bytes_transmitted: int = 0
    duration_seconds: float = 0.0
    checksum: str = ""
    delivery_timestamp: str = ""
    idempotency_key: str = ""
    destination_record_ids: list[str] = field(default_factory=lambda: [])
    errors: list[str] = field(default_factory=lambda: [])


class SinkConnector(ABC):
    """Abstract base class for reverse ETL sink connectors.

    SinkConnector is an opt-in mixin ABC that defines the contract for
    pushing data from the Iceberg Gold layer to external destinations.
    It is independently implementable — no inheritance from PluginMetadata
    or IngestionPlugin is required.

    Plugins supporting bidirectional data movement implement both
    IngestionPlugin and SinkConnector:

        class BidirectionalPlugin(IngestionPlugin, SinkConnector):
            ...

    Runtime capability detection uses isinstance():

        if isinstance(plugin, SinkConnector):
            sinks = plugin.list_available_sinks()

    Concrete plugins must implement:
        - list_available_sinks() — enumerate supported sink types
        - create_sink() — configure a destination from SinkConfig
        - write() — push data to the configured destination
        - get_source_config() — provide Iceberg Gold read configuration

    Example:
        >>> class MySinkPlugin(SinkConnector):
        ...     def list_available_sinks(self) -> list[str]:
        ...         return ["rest_api", "sql_database"]
        ...
        ...     def create_sink(self, config: SinkConfig) -> Any:
        ...         return create_destination(config.sink_type)
        ...
        ...     def write(self, sink: Any, data: Any, **kwargs: Any) -> EgressResult:
        ...         sink.push(data)
        ...         return EgressResult(success=True, rows_delivered=data.num_rows)
        ...
        ...     def get_source_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
        ...         return {"catalog_uri": catalog_config["uri"]}

    See Also:
        - IngestionPlugin: Complementary ABC for data ingestion
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
    """

    @abstractmethod
    def list_available_sinks(self) -> list[str]:
        """List sink types supported by this connector.

        Returns identifiers for the destination types this plugin can
        write to (e.g., REST API endpoints, SQL databases).

        Returns:
            List of supported sink type identifiers.

        Example:
            >>> plugin.list_available_sinks()
            ['rest_api', 'sql_database']
        """
        ...

    @abstractmethod
    def create_sink(self, config: SinkConfig) -> Any:
        """Create a configured sink destination from SinkConfig.

        Validates the configuration and returns a destination object
        ready for writing. Should fail fast with a clear error if
        credentials are invalid.

        .. note::
            TODO(SEC-001): When implementing real destination writes,
            validate connection URLs against SSRF (block RFC1918,
            link-local, metadata endpoints). See security review #5.

        Args:
            config: Sink destination configuration.

        Returns:
            Configured destination object (implementation-specific).

        Raises:
            SinkConfigurationError: If config is invalid.
            SinkConnectionError: If unable to connect to destination.

        Example:
            >>> config = SinkConfig(
            ...     sink_type="rest_api",
            ...     connection_config={"base_url": "https://api.example.com"},
            ... )
            >>> sink = plugin.create_sink(config)
        """
        ...

    @abstractmethod
    def write(self, sink: Any, data: Any, **kwargs: Any) -> EgressResult:
        """Push data to the configured sink destination.

        Writes data to the destination, auto-chunking into batches when
        SinkConfig.batch_size is set. The ``data`` parameter is a
        ``pyarrow.Table`` at runtime (typed as Any to avoid a hard
        dependency on pyarrow in floe-core).

        Args:
            sink: Configured destination object from create_sink().
            data: Data to write (pyarrow.Table at runtime).
            **kwargs: Additional write options.

        Returns:
            EgressResult with delivery metrics and receipt.

        Raises:
            SinkWriteError: If write operation fails.
            SinkConnectionError: If destination is unreachable.

        Example:
            >>> result = plugin.write(sink, arrow_table)
            >>> result.success
            True
            >>> result.rows_delivered
            1000
        """
        ...

    @abstractmethod
    def get_source_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
        """Generate source configuration for reading from Iceberg Gold layer.

        Creates configuration for reading from the Iceberg Gold layer
        via the Polaris catalog. This is the inverse of
        IngestionPlugin.get_destination_config().

        Args:
            catalog_config: Catalog connection configuration.

        Returns:
            Source configuration dict for reading from Iceberg.

        Raises:
            ValueError: If catalog_config is missing required fields.

        Example:
            >>> config = plugin.get_source_config({
            ...     "uri": "http://polaris:8181/api/catalog",
            ...     "warehouse": "floe_warehouse",
            ... })
            >>> config
            {'catalog_uri': 'http://polaris:8181/api/catalog', 'warehouse': 'floe_warehouse'}
        """
        ...

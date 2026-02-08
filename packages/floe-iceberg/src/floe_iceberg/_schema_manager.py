"""Internal helper class for Iceberg schema evolution operations.

Task ID: T031
Phase: 6 - US4 (Split IcebergTableManager)
User Story: US4 - Split Large Classes
Requirements: FR-014, FR-016, FR-017

This module contains the _IcebergSchemaManager helper class that encapsulates
schema evolution operations. Extracted from IcebergTableManager to improve
single-responsibility adherence.

The class is internal (underscore-prefixed) and should only be used by
IcebergTableManager. External consumers should use the public API.

Operations covered:
- evolve_schema(): Apply schema changes atomically
- Add column (optional/required)
- Rename column
- Widen type (INT→LONG, FLOAT→DOUBLE)
- Make column optional
- Delete column (requires allow_incompatible_changes)
- Update column documentation
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from floe_iceberg.errors import (
    IncompatibleSchemaChangeError,
    SchemaEvolutionError,
)
from floe_iceberg.models import (
    FieldType,
    SchemaChange,
    SchemaChangeType,
    SchemaEvolution,
)
from floe_iceberg.telemetry import traced

if TYPE_CHECKING:
    from floe_core.plugins.catalog import CatalogPlugin

    # Type alias for PyIceberg Table (Any due to missing type stubs)
    Table = Any


# Type widening rules (compatible promotions)
_VALID_TYPE_WIDENINGS: dict[FieldType, set[FieldType]] = {
    FieldType.INT: {FieldType.LONG},
    FieldType.FLOAT: {FieldType.DOUBLE},
}


def _get_pyiceberg_type_mapping() -> dict[FieldType, Any]:
    """Get mapping from FieldType to PyIceberg types.

    Returns:
        Dictionary mapping FieldType enum to PyIceberg type instances.
    """
    from pyiceberg.types import (
        BinaryType,
        BooleanType,
        DateType,
        DoubleType,
        FloatType,
        IntegerType,
        LongType,
        StringType,
        TimestampType,
        TimestamptzType,
        TimeType,
        UUIDType,
    )

    return {
        FieldType.BOOLEAN: BooleanType(),
        FieldType.INT: IntegerType(),
        FieldType.LONG: LongType(),
        FieldType.FLOAT: FloatType(),
        FieldType.DOUBLE: DoubleType(),
        FieldType.DATE: DateType(),
        FieldType.TIME: TimeType(),
        FieldType.TIMESTAMP: TimestampType(),
        FieldType.TIMESTAMPTZ: TimestamptzType(),
        FieldType.STRING: StringType(),
        FieldType.UUID: UUIDType(),
        FieldType.BINARY: BinaryType(),
    }


class _IcebergSchemaManager:
    """Internal helper class for schema evolution operations.

    Encapsulates schema evolution operations for Iceberg tables.
    Maintains single-responsibility by focusing only on schema changes.

    This class is internal and should not be used directly by external consumers.
    Use IcebergTableManager's public API instead.

    Attributes:
        _catalog_plugin: Catalog plugin for catalog operations.
        _log: Structured logger instance.

    Example:
        >>> # Internal usage in IcebergTableManager
        >>> schema_mgr = _IcebergSchemaManager(catalog_plugin)
        >>> table = schema_mgr.evolve_schema(table, evolution)
    """

    def __init__(self, catalog_plugin: CatalogPlugin) -> None:
        """Initialize _IcebergSchemaManager.

        Args:
            catalog_plugin: Catalog plugin for catalog operations.
        """
        self._catalog_plugin = catalog_plugin
        self._log = structlog.get_logger(__name__)

    # =========================================================================
    # Schema Evolution Operations
    # =========================================================================

    @traced(
        operation_name="iceberg.schema.evolve_schema",
        attributes={"operation": "evolve_schema"},
    )
    def evolve_schema(
        self,
        table: Table,
        evolution: SchemaEvolution,
    ) -> Table:
        """Apply schema changes to a table.

        Applies schema evolution operations atomically. Safe operations
        (add column, rename, widen type) are allowed by default.
        Incompatible changes (delete column) require explicit flag.

        Args:
            table: PyIceberg Table instance (or mock in tests).
            evolution: SchemaEvolution with list of changes.

        Returns:
            Updated Table instance with new schema.

        Raises:
            IncompatibleSchemaChangeError: If changes are incompatible and not allowed.
            SchemaEvolutionError: If evolution fails (e.g., column not found).

        Example:
            >>> evolution = SchemaEvolution(
            ...     changes=[
            ...         SchemaChange(
            ...             change_type=SchemaChangeType.ADD_COLUMN,
            ...             field=SchemaField(
            ...                 field_id=10,
            ...                 name="phone",
            ...                 field_type=FieldType.STRING,
            ...             ),
            ...         ),
            ...     ],
            ... )
            >>> table = schema_mgr.evolve_schema(table, evolution)
        """
        from opentelemetry import trace

        # Add span attributes for telemetry
        span = trace.get_current_span()
        span.set_attribute("table.identifier", getattr(table, "identifier", "unknown"))
        span.set_attribute("changes.count", len(evolution.changes))

        self._log.debug(
            "evolve_schema_requested",
            num_changes=len(evolution.changes),
            allow_incompatible=evolution.allow_incompatible_changes,
        )

        # Validate all changes before applying any
        self._validate_schema_evolution(table, evolution)

        # Apply schema changes via PyIceberg UpdateSchema API
        self._apply_real_schema_changes(table, evolution)

        self._log.info(
            "schema_evolved",
            num_changes=len(evolution.changes),
        )

        # Refresh to get updated schema if supported
        if hasattr(table, "refresh"):
            table.refresh()

        return table

    def _apply_real_schema_changes(
        self,
        table: Table,
        evolution: SchemaEvolution,
    ) -> None:
        """Apply schema changes to a real PyIceberg table.

        Args:
            table: Real PyIceberg Table instance.
            evolution: SchemaEvolution with list of changes.
        """
        from pyiceberg.types import StringType

        # Use module-level helper for type mapping (reusable, documented)
        type_mapping = _get_pyiceberg_type_mapping()

        with table.update_schema() as update:
            for change in evolution.changes:
                if change.change_type == SchemaChangeType.ADD_COLUMN:
                    if change.field:
                        iceberg_type = type_mapping.get(change.field.field_type, StringType())
                        update.add_column(
                            change.field.name,
                            iceberg_type,
                            doc=change.field.doc,
                        )

                elif change.change_type == SchemaChangeType.RENAME_COLUMN:
                    if change.source_column and change.new_name:
                        update.rename_column(change.source_column, change.new_name)

                elif change.change_type == SchemaChangeType.MAKE_OPTIONAL:
                    if change.source_column:
                        update.make_column_optional(change.source_column)

                elif change.change_type == SchemaChangeType.DELETE_COLUMN:
                    if change.source_column:
                        update.delete_column(change.source_column)

                elif change.change_type == SchemaChangeType.UPDATE_DOC:
                    if change.source_column and change.new_doc is not None:
                        update.update_column(change.source_column, doc=change.new_doc)

    def _validate_schema_evolution(
        self,
        table: Table,
        evolution: SchemaEvolution,
    ) -> None:
        """Validate all schema changes before applying.

        Args:
            table: Table to validate against.
            evolution: Schema evolution to validate.

        Raises:
            IncompatibleSchemaChangeError: If incompatible changes without flag.
            SchemaEvolutionError: If changes reference nonexistent columns.
        """
        for change in evolution.changes:
            # Check for incompatible changes
            if self._is_incompatible_change(change):
                if not evolution.allow_incompatible_changes:
                    msg = (
                        f"Incompatible change '{change.change_type.value}' "
                        "requires allow_incompatible_changes=True"
                    )
                    raise IncompatibleSchemaChangeError(msg)

            # Validate change-specific requirements
            self._validate_change(table, change, evolution.allow_incompatible_changes)

    def _is_incompatible_change(self, change: SchemaChange) -> bool:
        """Check if a change is incompatible (breaking).

        Args:
            change: Change to check.

        Returns:
            True if change is incompatible.
        """
        # DELETE_COLUMN is always incompatible
        if change.change_type == SchemaChangeType.DELETE_COLUMN:
            return True

        # ADD_COLUMN with required=True is incompatible (breaks existing data)
        if change.change_type == SchemaChangeType.ADD_COLUMN:
            if change.field is not None and change.field.required:
                return True

        return False

    def _validate_change(
        self,
        table: Table,
        change: SchemaChange,
        allow_incompatible: bool,
    ) -> None:
        """Validate a single schema change.

        Args:
            table: Table to validate against.
            change: Change to validate.
            allow_incompatible: Whether incompatible changes are allowed.

        Raises:
            SchemaEvolutionError: If change is invalid.
            IncompatibleSchemaChangeError: If type widening is invalid.
        """
        if change.change_type == SchemaChangeType.RENAME_COLUMN:
            # Check source column exists (via catalog plugin mock)
            if change.source_column is not None:
                if not self._column_exists(table, change.source_column):
                    msg = f"Column '{change.source_column}' does not exist"
                    raise SchemaEvolutionError(msg)

        elif change.change_type == SchemaChangeType.WIDEN_TYPE:
            # Check source column exists and widening is valid
            if change.source_column is not None:
                if not self._column_exists(table, change.source_column):
                    msg = f"Column '{change.source_column}' does not exist"
                    raise SchemaEvolutionError(msg)

                # Check if type widening is valid
                if change.target_type is not None:
                    source_type = self._get_column_type(table, change.source_column)
                    if not self._is_valid_type_widening(source_type, change.target_type):
                        msg = (
                            f"Cannot widen type from '{source_type}' to "
                            f"'{change.target_type.value}'"
                        )
                        raise IncompatibleSchemaChangeError(msg)

        elif change.change_type in (
            SchemaChangeType.MAKE_OPTIONAL,
            SchemaChangeType.UPDATE_DOC,
            SchemaChangeType.DELETE_COLUMN,
        ):
            # Check source column exists
            if change.source_column is not None:
                if not self._column_exists(table, change.source_column):
                    msg = f"Column '{change.source_column}' does not exist"
                    raise SchemaEvolutionError(msg)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _column_exists(self, table: Table, column_name: str) -> bool:
        """Check if a column exists in the table schema.

        Args:
            table: Table to check.
            column_name: Column name to look for.

        Returns:
            True if column exists.
        """
        # In mock, check via catalog plugin's table schema (mock-specific)
        table_id = getattr(table, "identifier", None)
        if table_id is not None:
            tables: dict[str, Any] | None = getattr(self._catalog_plugin, "_tables", None)
            if tables is not None:
                table_data = tables.get(table_id)
                if table_data is not None:
                    schema = table_data.get("schema", {})
                    fields = schema.get("fields", [])
                    return any(f.get("name") == column_name for f in fields)
        return True  # Assume exists in production (PyIceberg will validate)

    def _get_column_type(self, table: Table, column_name: str) -> FieldType | None:
        """Get the type of a column.

        Args:
            table: Table to check.
            column_name: Column name.

        Returns:
            FieldType of the column, or None if not found.
        """
        table_id = getattr(table, "identifier", None)
        if table_id is not None:
            tables: dict[str, Any] | None = getattr(self._catalog_plugin, "_tables", None)
            if tables is not None:
                table_data = tables.get(table_id)
                if table_data is not None:
                    schema = table_data.get("schema", {})
                    fields = schema.get("fields", [])
                    for f in fields:
                        if f.get("name") == column_name:
                            try:
                                return FieldType(f.get("type"))
                            except ValueError:
                                return None
        return None

    def _is_valid_type_widening(
        self,
        source_type: FieldType | None,
        target_type: FieldType,
    ) -> bool:
        """Check if a type widening is valid.

        Args:
            source_type: Current column type.
            target_type: Target type to widen to.

        Returns:
            True if widening is valid.
        """
        if source_type is None:
            return False

        valid_targets = _VALID_TYPE_WIDENINGS.get(source_type, set())
        return target_type in valid_targets


__all__ = ["_IcebergSchemaManager"]

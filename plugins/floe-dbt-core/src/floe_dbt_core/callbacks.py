"""dbtRunner callback handling for structured event capture.

This module provides callback handlers for dbtRunner events, enabling
structured capture of dbt execution events for observability and error reporting.

dbtRunner emits EventMsg objects during execution. This module provides:
- DBTEventCollector: Collects and categorizes events during execution
- Event filtering and structured extraction

Example:
    >>> from floe_dbt_core.callbacks import DBTEventCollector
    >>> collector = DBTEventCollector()
    >>> dbt = dbtRunner(callbacks=[collector.callback])
    >>> dbt.invoke(["run"])
    >>> print(collector.errors)
    [DBTEvent(name="GenericExceptionOnRun", level="error", ...)]

Requirements:
    FR-015: Capture and parse dbt stdout/stderr for structured error reporting
    FR-016: Support all dbtRunner callbacks (on_event, on_warning, on_error)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class DBTEventLevel(str, Enum):
    """dbt event severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warn"
    ERROR = "error"


@dataclass
class DBTEvent:
    """Structured representation of a dbt event.

    Captures event name, level, message, and associated data from
    dbtRunner callbacks.

    Attributes:
        name: Event type name (e.g., "MainReportVersion", "LogLine").
        level: Event severity level.
        message: Human-readable message.
        node_id: Optional dbt node ID (for model/test events).
        data: Raw event data dictionary.
    """

    name: str
    level: DBTEventLevel
    message: str
    node_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class DBTEventCollector:
    """Collector for dbtRunner events.

    Provides a callback function for dbtRunner that captures all events
    and categorizes them by severity. Useful for structured error reporting
    and execution tracing.

    Attributes:
        events: All collected events.
        errors: Events with error level.
        warnings: Events with warning level.

    Example:
        >>> collector = DBTEventCollector()
        >>> dbt = dbtRunner(callbacks=[collector.callback])
        >>> result = dbt.invoke(["run"])
        >>> if collector.errors:
        ...     for error in collector.errors:
        ...         print(f"Error: {error.message}")
    """

    def __init__(self) -> None:
        """Initialize empty event collector."""
        self._events: list[DBTEvent] = []

    @property
    def events(self) -> list[DBTEvent]:
        """All collected events."""
        return self._events.copy()

    @property
    def errors(self) -> list[DBTEvent]:
        """Events with error level."""
        return [e for e in self._events if e.level == DBTEventLevel.ERROR]

    @property
    def warnings(self) -> list[DBTEvent]:
        """Events with warning level."""
        return [e for e in self._events if e.level == DBTEventLevel.WARNING]

    @property
    def info_events(self) -> list[DBTEvent]:
        """Events with info level."""
        return [e for e in self._events if e.level == DBTEventLevel.INFO]

    def clear(self) -> None:
        """Clear all collected events."""
        self._events.clear()

    def callback(self, event: Any) -> None:
        """Callback function for dbtRunner.

        Processes EventMsg objects from dbt-common and converts them
        to structured DBTEvent instances.

        Args:
            event: EventMsg from dbt-common.events.base_types.
        """
        try:
            # Extract event info
            event_info = getattr(event, "info", None)
            if event_info is None:
                return

            event_name = getattr(event_info, "name", "Unknown")
            event_level_str = getattr(event_info, "level", "info")
            event_msg = getattr(event_info, "msg", "")

            # Map dbt level to our enum
            level = self._parse_level(event_level_str)

            # Extract node ID if present
            node_id = None
            event_data = getattr(event, "data", None)
            if event_data is not None:
                node_id = getattr(event_data, "node_info", {})
                if isinstance(node_id, dict):
                    node_id = node_id.get("unique_id")
                else:
                    node_id = getattr(node_id, "unique_id", None)

            # Convert event data to dict
            data_dict: dict[str, Any] = {}
            if event_data is not None:
                # Try to convert to dict if possible
                if hasattr(event_data, "__dict__"):
                    data_dict = {
                        k: v for k, v in event_data.__dict__.items() if not k.startswith("_")
                    }
                elif hasattr(event_data, "to_dict"):
                    data_dict = event_data.to_dict()

            # Create structured event
            dbt_event = DBTEvent(
                name=event_name,
                level=level,
                message=event_msg,
                node_id=node_id,
                data=data_dict,
            )
            self._events.append(dbt_event)

            # Log at appropriate level
            log = logger.bind(
                event_name=event_name,
                node_id=node_id,
            )
            if level == DBTEventLevel.ERROR:
                log.error("dbt_event", message=event_msg)
            elif level == DBTEventLevel.WARNING:
                log.warning("dbt_event", message=event_msg)
            elif level == DBTEventLevel.DEBUG:
                log.debug("dbt_event", message=event_msg)
            # Skip info level to reduce noise

        except Exception as e:
            # Don't let callback errors break dbt execution
            logger.warning("dbt_callback_error", error=str(e))

    def _parse_level(self, level_str: str) -> DBTEventLevel:
        """Parse dbt level string to DBTEventLevel enum.

        Args:
            level_str: Level string from dbt (e.g., "info", "warn", "error").

        Returns:
            Corresponding DBTEventLevel.
        """
        level_str = str(level_str).lower()
        if level_str in ("error", "critical", "fatal"):
            return DBTEventLevel.ERROR
        if level_str in ("warn", "warning"):
            return DBTEventLevel.WARNING
        if level_str == "debug":
            return DBTEventLevel.DEBUG
        return DBTEventLevel.INFO

    def get_error_summary(self) -> str | None:
        """Get summary of all errors.

        Returns:
            Combined error messages, or None if no errors.
        """
        if not self.errors:
            return None
        return "\n".join(e.message for e in self.errors if e.message)

    def get_failed_nodes(self) -> list[str]:
        """Get list of failed node IDs.

        Returns:
            List of unique_id values for failed nodes.
        """
        return [e.node_id for e in self.errors if e.node_id]


def create_event_collector() -> DBTEventCollector:
    """Factory function to create a new event collector.

    Returns:
        New DBTEventCollector instance.
    """
    return DBTEventCollector()

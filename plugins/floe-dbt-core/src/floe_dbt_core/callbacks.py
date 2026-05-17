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

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog
from floe_core.telemetry.sanitization import sanitize_error_message

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)
_SAFE_ERROR_TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,63}$")
_DBT_NODE_FAILURE = "DbtNodeFailure"


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


@dataclass(frozen=True)
class DBTNodeRecord:
    """Secret-free observability record for one dbt node execution."""

    unique_id: str
    node_name: str
    resource_type: str
    status: str
    duration_seconds: float | None = None
    error_type: str | None = None

    def to_span_attributes(self) -> dict[str, str | float]:
        """Return span attributes for this dbt node record."""
        attrs: dict[str, str | float] = {
            "dbt.node.unique_id": self.unique_id,
            "dbt.node.name": self.node_name,
            "dbt.node.resource_type": self.resource_type,
            "dbt.node.status": self.status,
        }
        if self.duration_seconds is not None:
            attrs["dbt.node.duration_seconds"] = self.duration_seconds
        if self.error_type is not None:
            attrs["dbt.node.error_type"] = self.error_type
        return attrs

    def to_metric_labels(self) -> dict[str, str]:
        """Return bounded-cardinality metric labels for this dbt node record."""
        labels = {
            "dbt.resource_type": self.resource_type,
            "dbt.status": self.status,
        }
        if self.error_type is not None:
            labels["dbt.error_type"] = self.error_type
        return labels

    @classmethod
    def from_run_result(cls, result: dict[str, Any]) -> DBTNodeRecord | None:
        """Build a record from a run_results.json result entry."""
        unique_id = _string_value(result.get("unique_id"))
        if unique_id is None:
            return None

        node = result.get("node")
        node_data = node if isinstance(node, dict) else {}
        node_name = _string_value(node_data.get("name")) or _node_name_from_unique_id(unique_id)
        resource_type = _string_value(node_data.get("resource_type")) or _resource_type(unique_id)
        status = _string_value(result.get("status")) or "unknown"
        duration = _float_value(result.get("execution_time"))
        error_type = _error_type(result, status)

        return cls(
            unique_id=unique_id,
            node_name=node_name,
            resource_type=resource_type,
            status=status,
            duration_seconds=duration,
            error_type=error_type,
        )

    @classmethod
    def from_event(cls, event: DBTEvent) -> DBTNodeRecord | None:
        """Build a record from a structured dbt callback event."""
        if event.node_id is None:
            return None

        node_info_raw = event.data.get("node_info")
        node_info = node_info_raw if isinstance(node_info_raw, dict) else {}
        status = _string_value(event.data.get("status")) or (
            "error" if event.level is DBTEventLevel.ERROR else "unknown"
        )
        error_type = None
        if event.level is DBTEventLevel.ERROR:
            explicit_error_type = _string_value(event.data.get("error_type"))
            if explicit_error_type is not None:
                error_type = _safe_error_type(explicit_error_type, fallback=_DBT_NODE_FAILURE)
            else:
                error_type = _safe_error_type(event.name, fallback=_DBT_NODE_FAILURE)

        return cls(
            unique_id=event.node_id,
            node_name=_string_value(node_info.get("node_name"))
            or _string_value(node_info.get("name"))
            or _node_name_from_unique_id(event.node_id),
            resource_type=_string_value(node_info.get("resource_type"))
            or _resource_type(event.node_id),
            status=status,
            duration_seconds=_float_value(event.data.get("execution_time"))
            or _float_value(event.data.get("duration")),
            error_type=error_type,
        )


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

    @property
    def node_records(self) -> list[DBTNodeRecord]:
        """Per-node observability records derived from callback events."""
        records: list[DBTNodeRecord] = []
        seen: set[str] = set()
        for event in self._events:
            record = DBTNodeRecord.from_event(event)
            if record is None:
                continue
            key = f"{record.unique_id}:{record.status}:{record.duration_seconds}"
            if key in seen:
                continue
            seen.add(key)
            records.append(record)
        return records

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


def dbt_node_records_from_run_results(run_results: dict[str, Any]) -> list[DBTNodeRecord]:
    """Return per-node records from a parsed run_results.json document."""
    results = run_results.get("results", [])
    if not isinstance(results, list):
        return []
    records: list[DBTNodeRecord] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        record = DBTNodeRecord.from_run_result(result)
        if record is not None:
            records.append(record)
    return records


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _float_value(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _resource_type(unique_id: str) -> str:
    return unique_id.split(".", 1)[0] if "." in unique_id else "unknown"


def _node_name_from_unique_id(unique_id: str) -> str:
    return unique_id.rsplit(".", 1)[-1]


def _error_type(result: dict[str, Any], status: str) -> str | None:
    explicit = _string_value(result.get("error_type"))
    if explicit is not None:
        return _safe_error_type(explicit, fallback=_DBT_NODE_FAILURE)
    if status.lower() in {"error", "fail", "failed"}:
        return _DBT_NODE_FAILURE
    return None


def _safe_error_type(value: str, *, fallback: str) -> str:
    sanitized = sanitize_error_message(value, max_length=128).strip()
    if sanitized != value:
        return fallback
    if _SAFE_ERROR_TYPE_RE.fullmatch(sanitized) is None:
        return fallback
    if "://" in sanitized or "@" in sanitized or "/" in sanitized or "?" in sanitized:
        return fallback
    return sanitized

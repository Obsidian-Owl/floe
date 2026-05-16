"""Runtime observability context for Floe-managed execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast
from urllib.parse import SplitResult, urlsplit, urlunsplit

from floe_core.telemetry.conventions import (
    FLOE_ASSET_KEY,
    FLOE_ENVIRONMENT,
    FLOE_LINEAGE_NAMESPACE,
    FLOE_NAMESPACE,
    FLOE_PLUGIN_NAME,
    FLOE_PLUGIN_TYPE,
    FLOE_PRODUCT_NAME,
    FLOE_PRODUCT_VERSION,
    FLOE_RUN_ID,
    FLOE_STAGE,
    FLOE_STATUS,
    FLOE_TABLE_NAME,
)

_SECRET_KEY_MARKERS = ("secret", "password", "token", "credential", "private_key")
_REDACTED = "[REDACTED]"
_SUPPORTED_STATUSES = frozenset(("success", "failure", "error", "skipped"))

AttributeValue = str | int | float | bool
ObservabilityStatus = Literal["success", "failure", "error", "skipped"]


def _is_secret_key(key: str) -> bool:
    """Return True when an attribute key appears to identify secret material."""
    lowered = key.lower()
    return any(marker in lowered for marker in _SECRET_KEY_MARKERS)


def _contains_unsafe_value(value: Any) -> bool:
    """Return True when a nested value may contain secret material."""
    if isinstance(value, dict):
        return any(
            _is_secret_key(str(key)) or _contains_unsafe_value(nested_value)
            for key, nested_value in value.items()
        )
    if isinstance(value, list | tuple | set | frozenset):
        return any(_contains_unsafe_value(item) for item in value)
    if isinstance(value, str):
        return _has_url_credentials(value)
    return False


def _has_url_credentials(value: str) -> bool:
    """Return True when a string URL includes userinfo credentials."""
    parsed = urlsplit(value)
    return bool(parsed.scheme and parsed.netloc and (parsed.username or parsed.password))


def _redact_url_credentials(value: str) -> str:
    """Remove userinfo credentials from URL strings."""
    parsed = urlsplit(value)
    if not (parsed.scheme and parsed.netloc and (parsed.username or parsed.password)):
        return value

    try:
        netloc = _safe_url_netloc(parsed)
    except ValueError:
        return _REDACTED

    return urlunsplit(
        SplitResult(
            scheme=parsed.scheme,
            netloc=netloc,
            path=parsed.path,
            query=parsed.query,
            fragment=parsed.fragment,
        )
    )


def _safe_url_netloc(parsed: SplitResult) -> str:
    """Return URL netloc without userinfo, failing closed on malformed ports."""
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("URL host is required")

    host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    return f"{host}:{parsed.port}" if parsed.port is not None else host


def _clean_value(value: Any) -> AttributeValue:
    """Convert arbitrary attribute values to OpenTelemetry-compatible scalars."""
    if isinstance(value, str):
        return _redact_url_credentials(value)
    if _contains_unsafe_value(value):
        return _REDACTED
    if isinstance(value, int | float | bool):
        return value
    return str(value)


def _validate_status(status: str) -> ObservabilityStatus:
    """Validate metric status labels against the bounded vocabulary."""
    if status not in _SUPPORTED_STATUSES:
        supported = ", ".join(sorted(_SUPPORTED_STATUSES))
        raise ValueError(
            f"Unsupported observability status {status!r}; expected one of: {supported}"
        )
    return cast(ObservabilityStatus, status)


@dataclass(frozen=True)
class ObservabilityContext:
    """Secret-free context attached to traces, logs, metrics, and lineage."""

    product_name: str
    product_version: str
    environment: str
    namespace: str
    run_id: str | None = None
    asset_key: str | None = None
    stage: str | None = None
    table_name: str | None = None
    plugin_type: str | None = None
    plugin_name: str | None = None
    lineage_namespace: str | None = None
    extra_attributes: dict[str, Any] = field(default_factory=dict)

    def to_span_attributes(self) -> dict[str, AttributeValue]:
        """Return sanitized span attributes for the current execution context."""
        attrs: dict[str, AttributeValue] = {
            FLOE_PRODUCT_NAME: self.product_name,
            FLOE_PRODUCT_VERSION: self.product_version,
            FLOE_ENVIRONMENT: self.environment,
            FLOE_NAMESPACE: self.namespace,
        }

        optionals: dict[str, str | None] = {
            FLOE_RUN_ID: self.run_id,
            FLOE_ASSET_KEY: self.asset_key,
            FLOE_STAGE: self.stage,
            FLOE_TABLE_NAME: self.table_name,
            FLOE_PLUGIN_TYPE: self.plugin_type,
            FLOE_PLUGIN_NAME: self.plugin_name,
            FLOE_LINEAGE_NAMESPACE: self.lineage_namespace,
        }
        attrs.update({key: value for key, value in optionals.items() if value is not None})

        for key, value in self.extra_attributes.items():
            if _is_secret_key(key) or key in attrs:
                continue
            attrs[key] = _clean_value(value)
        return attrs

    def to_log_fields(self) -> dict[str, AttributeValue]:
        """Return sanitized structured log fields for this context."""
        return self.to_span_attributes()

    def to_metric_labels(
        self,
        *,
        status: ObservabilityStatus | str | None = None,
    ) -> dict[str, str]:
        """Return bounded-cardinality labels safe for metric aggregation."""
        labels: dict[str, str] = {
            FLOE_PRODUCT_NAME: self.product_name,
            FLOE_ENVIRONMENT: self.environment,
            FLOE_NAMESPACE: self.namespace,
        }

        optionals: dict[str, str | None] = {
            FLOE_STAGE: self.stage,
            FLOE_PLUGIN_TYPE: self.plugin_type,
            FLOE_PLUGIN_NAME: self.plugin_name,
            FLOE_STATUS: _validate_status(status) if status is not None else None,
        }
        labels.update({key: value for key, value in optionals.items() if value is not None})
        return labels

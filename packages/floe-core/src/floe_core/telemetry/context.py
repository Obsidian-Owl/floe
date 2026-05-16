"""Runtime observability context for Floe-managed execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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

AttributeValue = str | int | float | bool


def _is_secret_key(key: str) -> bool:
    """Return True when an attribute key appears to identify secret material."""
    lowered = key.lower()
    return any(marker in lowered for marker in _SECRET_KEY_MARKERS)


def _clean_value(value: Any) -> AttributeValue:
    """Convert arbitrary attribute values to OpenTelemetry-compatible scalars."""
    if isinstance(value, str | int | float | bool):
        return value
    return str(value)


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

        attrs.update(
            {
                key: _clean_value(value)
                for key, value in self.extra_attributes.items()
                if not _is_secret_key(key)
            }
        )
        return attrs

    def to_log_fields(self) -> dict[str, AttributeValue]:
        """Return sanitized structured log fields for this context."""
        return self.to_span_attributes()

    def to_metric_labels(self, *, status: str | None = None) -> dict[str, str]:
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
            FLOE_STATUS: status,
        }
        labels.update({key: value for key, value in optionals.items() if value is not None})
        return labels

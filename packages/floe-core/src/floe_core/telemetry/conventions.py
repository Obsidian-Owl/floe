"""Floe span attributes (semantic conventions).

Contract Version: 1.0.0

Per ADR-0006: Every span MUST include floe.namespace.
These semantic conventions ensure consistent telemetry across all Floe components.

See Also:
    - specs/001-opentelemetry/contracts/span_attributes.py: Contract source
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FloeSpanAttributes(BaseModel):
    """Floe semantic conventions for span attributes.

    Per ADR-0006: Every span MUST include floe.namespace.
    These attributes provide consistent identification and correlation
    across all telemetry signals (traces, metrics, logs).

    Attributes:
        namespace: Polaris catalog namespace (MANDATORY per ADR-0006)
        product_name: Data product name
        product_version: Data product version
        mode: Execution mode (dev, staging, prod)
        pipeline_id: Optional pipeline execution ID
        job_type: Optional job type (e.g., 'dbt_run', 'dlt_sync')
        model_name: Optional dbt model name
        asset_key: Optional Dagster asset key

    Examples:
        >>> attrs = FloeSpanAttributes(
        ...     namespace="analytics",
        ...     product_name="customer-360",
        ...     product_version="2.1.0",
        ...     mode="prod",
        ...     pipeline_id="run-12345",
        ...     model_name="stg_customers",
        ... )
        >>> attrs.to_otel_dict()
        {
            'floe.namespace': 'analytics',
            'floe.product.name': 'customer-360',
            'floe.product.version': '2.1.0',
            'floe.mode': 'prod',
            'floe.pipeline.id': 'run-12345',
            'floe.dbt.model': 'stg_customers',
        }
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # MANDATORY attributes (per ADR-0006)
    namespace: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Polaris catalog namespace (MANDATORY per ADR-0006)",
    )
    product_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Data product name",
    )
    product_version: str = Field(
        ...,
        description="Data product version",
    )
    mode: Literal["dev", "staging", "prod"] = Field(
        ...,
        description="Execution mode",
    )

    # Optional operation-specific attributes
    pipeline_id: str | None = Field(
        default=None,
        description="Pipeline execution ID",
    )
    job_type: str | None = Field(
        default=None,
        description="Job type (e.g., 'dbt_run', 'dlt_sync', 'dagster_asset')",
    )
    model_name: str | None = Field(
        default=None,
        description="dbt model name",
    )
    asset_key: str | None = Field(
        default=None,
        description="Dagster asset key",
    )

    def to_otel_dict(self) -> dict[str, str]:
        """Convert to OpenTelemetry span attributes dictionary.

        Returns dictionary with OTel semantic convention keys.
        Only includes non-None optional attributes.

        Returns:
            Dictionary with 'floe.*' prefixed keys.
        """
        attrs: dict[str, str] = {
            "floe.namespace": self.namespace,
            "floe.product.name": self.product_name,
            "floe.product.version": self.product_version,
            "floe.mode": self.mode,
        }

        # Add optional attributes if present
        if self.pipeline_id is not None:
            attrs["floe.pipeline.id"] = self.pipeline_id
        if self.job_type is not None:
            attrs["floe.job.type"] = self.job_type
        if self.model_name is not None:
            attrs["floe.dbt.model"] = self.model_name
        if self.asset_key is not None:
            attrs["floe.dagster.asset"] = self.asset_key

        return attrs


# Semantic convention constants for programmatic access
FLOE_NAMESPACE = "floe.namespace"
FLOE_PRODUCT_NAME = "floe.product.name"
FLOE_PRODUCT_VERSION = "floe.product.version"
FLOE_MODE = "floe.mode"
FLOE_PIPELINE_ID = "floe.pipeline.id"
FLOE_JOB_TYPE = "floe.job.type"
FLOE_DBT_MODEL = "floe.dbt.model"
FLOE_DAGSTER_ASSET = "floe.dagster.asset"

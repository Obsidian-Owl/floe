"""Configuration model for the native AWS Glue catalog plugin."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GlueCredentialMode = Literal["environment", "workload-identity", "kubernetes-secret"]
RetryMode = Literal["standard", "adaptive", "legacy"]


class GlueCatalogConfig(BaseModel):
    """AWS Glue catalog configuration.

    Credentials are represented by environment variable names, Kubernetes Secret
    references, or workload identity service account references. Raw AWS
    credential values are intentionally not accepted by this model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    region: str = Field(..., min_length=1, description="AWS region.")
    catalog_id: str | None = Field(
        default=None,
        pattern=r"^\d{12}$",
        description="Optional AWS account/catalog ID.",
    )
    warehouse: str | None = Field(
        default=None,
        min_length=1,
        description="Optional warehouse URI override.",
    )
    database_prefix: str | None = Field(
        default=None,
        min_length=1,
        description="Optional namespace prefix for Floe-created databases.",
    )
    endpoint_override: str | None = Field(
        default=None,
        pattern=r"^https?://",
        description="Optional Glue endpoint override for tests or local emulation.",
    )
    credential_mode: GlueCredentialMode = "workload-identity"
    credential_secret_name: str | None = Field(
        default=None,
        min_length=1,
        description="Kubernetes Secret name for kubernetes-secret mode.",
    )
    credential_secret_namespace: str = Field(
        default="floe-system",
        min_length=1,
        description="Kubernetes namespace for credential_secret_name.",
    )
    access_key_secret_key: str = Field(default="accessKeyId", min_length=1)
    secret_key_secret_key: str = Field(default="secretAccessKey", min_length=1)
    session_token_secret_key: str = Field(default="sessionToken", min_length=1)
    service_account_ref: str | None = Field(
        default=None,
        min_length=1,
        description="Kubernetes ServiceAccount reference for workload identity.",
    )
    skip_archive: bool = True
    max_retries: int | None = Field(default=None, ge=1)
    retry_mode: RetryMode | None = None

    @field_validator("warehouse")
    @classmethod
    def normalize_warehouse(cls, value: str | None) -> str | None:
        """Normalize S3 warehouse overrides to slash-terminated form."""
        if value is None:
            return value
        if not value.startswith("s3://"):
            msg = "warehouse must be an s3:// URI"
            raise ValueError(msg)
        return value if value.endswith("/") else f"{value}/"

    @model_validator(mode="before")
    @classmethod
    def reject_raw_aws_key_fields(cls, data: Any) -> Any:
        """Reject common raw AWS credential keys if provided by mistake."""
        if isinstance(data, dict):
            raw_keys = {"access_key_id", "secret_access_key", "session_token"}
            present = raw_keys & set(data)
            if present:
                msg = f"raw AWS credential fields are not accepted: {sorted(present)}"
                raise ValueError(msg)
        return data

    @model_validator(mode="after")
    def validate_credential_mode(self) -> GlueCatalogConfig:
        """Ensure credential reference fields match credential_mode."""
        if self.credential_mode == "workload-identity":
            if self.service_account_ref is None:
                msg = "workload-identity credential_mode requires service_account_ref"
                raise ValueError(msg)
            if self.credential_secret_name is not None:
                msg = "workload-identity credential_mode only accepts service_account_ref"
                raise ValueError(msg)
            return self

        if self.credential_mode == "kubernetes-secret":
            if self.credential_secret_name is None:
                msg = "kubernetes-secret credential_mode requires credential_secret_name"
                raise ValueError(msg)
            if self.service_account_ref is not None:
                msg = "kubernetes-secret credential_mode only accepts credential_secret_name"
                raise ValueError(msg)
            return self

        if self.credential_secret_name is not None or self.service_account_ref is not None:
            msg = "environment credential_mode only accepts environment variable names"
            raise ValueError(msg)
        return self

"""Configuration model for the native AWS S3 storage plugin."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self

AwsS3ObjectStoreCredentialMode = Literal["environment", "workload-identity", "kubernetes-secret"]
CreatePolicy = Literal["must-exist", "never-create"]


def _normalize_prefix(value: str) -> str:
    """Normalize an S3 prefix to either empty or slash-terminated form."""
    prefix = value.strip("/")
    if not prefix:
        return ""
    return f"{prefix}/"


class AwsS3ObjectStoreConfig(BaseModel):
    """AWS S3 storage configuration.

    Credentials are represented by environment variable names, Kubernetes Secret
    references, or workload identity service account references. Raw AWS
    credential values are intentionally not accepted by this model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    bucket: str = Field(..., min_length=1, description="Warehouse bucket name.")
    warehouse_prefix: str = Field(
        default="warehouse/",
        description="Warehouse prefix within the bucket.",
    )
    artifact_bucket: str | None = Field(
        default=None,
        description="Artifact bucket. Defaults to bucket when unset.",
    )
    artifact_prefix: str = Field(
        default="artifacts/",
        description="Artifact prefix within artifact_bucket.",
    )
    region: str = Field(..., min_length=1, description="AWS region.")
    endpoint_override: str | None = Field(
        default=None,
        description="Optional S3 endpoint override for local emulation.",
        pattern=r"^https?://",
    )
    path_style_access: bool = Field(
        default=False,
        description="Use path-style access. False for native AWS S3.",
    )
    credential_mode: AwsS3ObjectStoreCredentialMode = "workload-identity"
    credential_secret_name: str | None = Field(
        default=None,
        description="Kubernetes Secret name for kubernetes-secret mode.",
        min_length=1,
    )
    credential_secret_namespace: str = Field(
        default="floe-system",
        description="Kubernetes namespace for credential_secret_name.",
        min_length=1,
    )
    access_key_secret_key: str = Field(default="accessKeyId", min_length=1)
    secret_key_secret_key: str = Field(default="secretAccessKey", min_length=1)
    session_token_secret_key: str = Field(default="sessionToken", min_length=1)
    service_account_ref: str | None = Field(
        default=None,
        description="Kubernetes ServiceAccount reference for workload identity.",
        min_length=1,
    )
    create_policy: CreatePolicy = "must-exist"
    sts_supported: bool = True

    @field_validator("warehouse_prefix", "artifact_prefix")
    @classmethod
    def normalize_prefix(cls, value: str) -> str:
        """Normalize S3 prefixes so URI generation is deterministic."""
        return _normalize_prefix(value)

    @model_validator(mode="before")
    @classmethod
    def default_artifact_bucket(cls, data: Any) -> Any:
        """Default artifact_bucket to bucket before frozen model creation."""
        if isinstance(data, dict) and data.get("artifact_bucket") is None and "bucket" in data:
            data = dict(data)
            data["artifact_bucket"] = data["bucket"]
        return data

    @model_validator(mode="after")
    def validate_credential_mode(self) -> Self:
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

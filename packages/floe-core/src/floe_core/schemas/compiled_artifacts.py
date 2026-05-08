"""CompiledArtifacts schema for compiled output from floe compile.

CompiledArtifacts is the single source of truth for pipeline execution.
It contains resolved, validated configuration after manifest inheritance.

Contract Version: See COMPILED_ARTIFACTS_VERSION in versions.py

Version History:
    See COMPILED_ARTIFACTS_VERSION_HISTORY in versions.py

See Also:
    - docs/contracts/compiled-artifacts.md: Full contract specification
    - ADR-0006: Telemetry architecture
    - ADR-0012: CompiledArtifacts contract
    - ADR-0035: Plugin system architecture
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from floe_core.schemas.data_contract import DataContract
from floe_core.schemas.quality_config import QualityConfig
from floe_core.schemas.quality_score import QualityCheck
from floe_core.schemas.telemetry import TelemetryConfig
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

_K8S_DNS_SUBDOMAIN_PATTERN = re.compile(
    r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$"
)
_K8S_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
PRODUCT_NAME_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_-]*$"
_MAX_K8S_NAME_LENGTH = 253
_MAX_K8S_NAMESPACE_LENGTH = 63
NonEmptyString = Annotated[str, Field(min_length=1)]
_SECRET_FIELD_MARKERS = (
    "access-key",
    "access_key",
    "accesskey",
    "credential",
    "password",
    "secret",
    "token",
)
_SECRET_VALUE_MARKERS = (
    "password",
    "raw-secret-value",
    "secret-value",
    "token",
)
_INGESTION_OUTPUT_SOURCE_PATH_SECRET_MARKERS = (
    "credential",
    "credentials",
    "access_key",
    "secret_key",
    "api_key",
    "password",
    "token",
    "signature",
    "awsaccesskeyid",
    "aws_access_key_id",
    "aws_secret_access_key",
)
_INGESTION_OUTPUT_TABLE_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DLT_FILESYSTEM_CREDENTIAL_KEYS = frozenset(
    {
        "endpoint_url",
        "region_name",
        "s3_url_style",
    }
)
_DEFAULT_ADMIN_CREDENTIAL_PATTERN = re.compile(r"(?<![a-z0-9])[a-z0-9_-]*admin[0-9]*(?![a-z0-9])")


def _validate_configmap_name(name: str) -> str:
    """Validate ConfigMap metadata.name as a Kubernetes DNS subdomain."""
    if len(name) > _MAX_K8S_NAME_LENGTH:
        raise ValueError(
            f"Invalid ConfigMap name: {name!r} exceeds {_MAX_K8S_NAME_LENGTH} characters"
        )
    if not _K8S_DNS_SUBDOMAIN_PATTERN.fullmatch(name):
        raise ValueError(
            f"Invalid ConfigMap name: {name!r} must match Kubernetes DNS subdomain rules"
        )
    return name


def _validate_configmap_namespace(namespace: str) -> str:
    """Validate ConfigMap metadata.namespace as a Kubernetes namespace name."""
    if len(namespace) > _MAX_K8S_NAMESPACE_LENGTH:
        raise ValueError(
            f"Invalid namespace: {namespace!r} exceeds {_MAX_K8S_NAMESPACE_LENGTH} characters"
        )
    if not _K8S_NAMESPACE_PATTERN.fullmatch(namespace):
        raise ValueError(f"Invalid namespace: {namespace!r} must match Kubernetes namespace rules")
    return namespace


def _validate_kubernetes_secret_name(name: str) -> str:
    """Validate Secret metadata.name as a Kubernetes DNS subdomain."""
    if len(name) > _MAX_K8S_NAME_LENGTH:
        raise ValueError(f"Invalid Secret name: {name!r} exceeds {_MAX_K8S_NAME_LENGTH} characters")
    if not _K8S_DNS_SUBDOMAIN_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid Secret name: {name!r} must match Kubernetes DNS subdomain rules")
    return name


def _validate_kubernetes_namespace(namespace: str) -> str:
    """Validate Kubernetes metadata.namespace as a namespace name."""
    if len(namespace) > _MAX_K8S_NAMESPACE_LENGTH:
        raise ValueError(
            f"Invalid namespace: {namespace!r} exceeds {_MAX_K8S_NAMESPACE_LENGTH} characters"
        )
    if not _K8S_NAMESPACE_PATTERN.fullmatch(namespace):
        raise ValueError(f"Invalid namespace: {namespace!r} must match Kubernetes namespace rules")
    return namespace


def _assert_no_secret_material(value: Any, path: str) -> None:
    """Reject raw credential-looking fields in serialized artifact fragments."""
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            child_path = f"{path}.{key}"
            if any(marker in key_text for marker in _SECRET_FIELD_MARKERS):
                msg = (
                    f"{child_path} looks like raw credential material; use env_refs "
                    "or CredentialRef fields instead"
                )
                raise ValueError(msg)
            _assert_no_secret_material(child, child_path)
        return

    if isinstance(value, list | tuple | set | frozenset):
        for index, child in enumerate(value):
            _assert_no_secret_material(child, f"{path}[{index}]")
        return

    if isinstance(value, str):
        value_text = value.lower()
        if any(marker in value_text for marker in _SECRET_VALUE_MARKERS) or (
            _DEFAULT_ADMIN_CREDENTIAL_PATTERN.search(value_text) is not None
        ):
            msg = (
                f"{path} looks like raw credential material; use env_refs "
                "or CredentialRef fields instead"
            )
            raise ValueError(msg)
        return

    if isinstance(value, Iterable):
        msg = (
            f"{path} contains unsupported runtime fragment type {type(value).__name__}; "
            "use JSON-compatible dict, list, string, number, boolean, or null values"
        )
        raise ValueError(msg)


def _assert_json_compatible_fragment(value: Any, path: str) -> None:
    """Reject values that cannot be serialized into compiled artifact JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        msg = f"{path} contains non-finite number {value!r}; use finite JSON numbers"
        raise ValueError(msg)

    if value is None or isinstance(value, str | int | float | bool):
        return

    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                msg = (
                    f"{path} contains unsupported runtime fragment key type "
                    f"{type(key).__name__}; use string keys for JSON-compatible maps"
                )
                raise ValueError(msg)
            _assert_json_compatible_fragment(child, f"{path}.{key}")
        return

    if isinstance(value, list):
        for index, child in enumerate(value):
            _assert_json_compatible_fragment(child, f"{path}[{index}]")
        return

    msg = (
        f"{path} contains unsupported runtime fragment type {type(value).__name__}; "
        "use JSON-compatible dict, list, string, number, boolean, or null values"
    )
    raise ValueError(msg)


def _assert_dlt_filesystem_fragment_secret_free(value: Any, path: str) -> None:
    """Reject secrets while allowing dlt filesystem credential config containers."""
    _assert_json_compatible_fragment(value, path)

    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key) == "credentials" and isinstance(child, dict):
                unknown_keys = set(child) - _DLT_FILESYSTEM_CREDENTIAL_KEYS
                if unknown_keys:
                    unknown_key = sorted(unknown_keys)[0]
                    _assert_no_secret_material({unknown_key: child[unknown_key]}, child_path)
                    msg = (
                        f"{child_path}.{unknown_key} is not an allowed dlt filesystem "
                        "credential config key"
                    )
                    raise ValueError(msg)
                for credential_key, credential_value in child.items():
                    _assert_no_secret_material(credential_value, f"{child_path}.{credential_key}")
                continue

            _assert_no_secret_material({key: child}, path)
        return

    _assert_no_secret_material(value, path)


class CompilationMetadata(BaseModel):
    """Information about the compilation process.

    Attributes:
        compiled_at: Timestamp of compilation
        floe_version: Version of floe used for compilation
        source_hash: SHA256 hash of input files
        product_name: Name of the data product
        product_version: Version of the data product
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    compiled_at: datetime = Field(
        ...,
        description="Timestamp of compilation",
    )
    floe_version: str = Field(
        ...,
        description="Version of floe used for compilation",
    )
    source_hash: str = Field(
        ...,
        description="SHA256 hash of input files",
    )
    product_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=PRODUCT_NAME_PATTERN,
        description="Name of the data product",
    )
    product_version: str = Field(
        ...,
        description="Version of the data product",
    )


class ProductIdentity(BaseModel):
    """Product identity information from catalog registration.

    See ADR-0030 for the namespace-based identity model.

    Attributes:
        product_id: Fully qualified product ID (e.g., 'sales.customer_360')
        domain: Domain name (e.g., 'sales')
        repository: Source repository URL
        namespace_registered: Whether registered in catalog
        registration_timestamp: When first registered
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(
        ...,
        min_length=1,
        description="Fully qualified product ID",
    )
    domain: str = Field(
        ...,
        min_length=1,
        description="Domain name",
    )
    repository: str = Field(
        ...,
        description="Source repository URL",
    )
    namespace_registered: bool = Field(
        default=False,
        description="Whether registered in catalog",
    )
    registration_timestamp: datetime | None = Field(
        default=None,
        description="When first registered",
    )


class ManifestRef(BaseModel):
    """Reference to a manifest in the inheritance chain.

    Attributes:
        name: Manifest name
        version: Manifest version
        scope: Manifest scope (enterprise or domain)
        ref: OCI reference
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Manifest name")
    version: str = Field(..., description="Manifest version")
    scope: Literal["enterprise", "domain"] = Field(..., description="Manifest scope")
    ref: str = Field(..., description="OCI reference")


class PluginRef(BaseModel):
    """Reference to a resolved plugin.

    Contains the plugin type, version, and configuration after
    resolution from the platform manifest.

    Attributes:
        type: Plugin type name (e.g., "duckdb", "snowflake")
        version: Plugin version (semver)
        config: Plugin-specific configuration dictionary

    Example:
        >>> plugin = PluginRef(
        ...     type="duckdb",
        ...     version="0.9.0",
        ...     config={"threads": 4, "memory_limit": "8GB"}
        ... )
        >>> plugin.type
        'duckdb'

    See Also:
        - data-model.md: PluginRef entity specification
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str = Field(
        ...,
        min_length=1,
        description="Plugin type name (e.g., 'duckdb', 'snowflake')",
        examples=["duckdb", "snowflake", "dagster"],
    )
    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Plugin version (semver)",
        examples=["0.9.0", "1.2.3"],
    )
    config: dict[str, Any] | None = Field(
        default=None,
        description="Plugin-specific configuration",
        examples=[{"threads": 4, "memory_limit": "8GB"}],
    )


class ResolvedPlugins(BaseModel):
    """Resolved plugin selections after inheritance.

    Contains references to all resolved plugins that will be used
    for pipeline execution. Required plugins (compute, orchestrator)
    must be present; optional plugins may be None.

    Attributes:
        compute: Resolved compute plugin (required)
        orchestrator: Resolved orchestrator plugin (required)
        catalog: Resolved catalog plugin (optional)
        storage: Resolved storage plugin (optional)
        ingestion: Resolved ingestion plugin (optional)
        semantic: Resolved semantic layer plugin (optional)

    Example:
        >>> plugins = ResolvedPlugins(
        ...     compute=PluginRef(type="duckdb", version="0.9.0"),
        ...     orchestrator=PluginRef(type="dagster", version="1.5.0"),
        ...     catalog=PluginRef(type="polaris", version="0.1.0"),
        ... )
        >>> plugins.compute.type
        'duckdb'

    See Also:
        - data-model.md: ResolvedPlugins entity specification
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    compute: PluginRef = Field(
        ...,
        description="Resolved compute plugin (required)",
    )
    orchestrator: PluginRef = Field(
        ...,
        description="Resolved orchestrator plugin (required)",
    )
    catalog: PluginRef | None = Field(
        default=None,
        description="Resolved catalog plugin (optional)",
    )
    storage: PluginRef | None = Field(
        default=None,
        description="Resolved storage plugin (optional)",
    )
    ingestion: PluginRef | None = Field(
        default=None,
        description="Resolved ingestion plugin (optional)",
    )
    semantic: PluginRef | None = Field(
        default=None,
        description="Resolved semantic layer plugin (optional)",
    )
    lineage_backend: PluginRef | None = Field(
        default=None,
        description="Resolved lineage backend plugin (optional, v0.5.0+)",
    )


class KubernetesSecretRef(BaseModel):
    """Reference to keys in a Kubernetes Secret."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NonEmptyString
    namespace: NonEmptyString
    keys: dict[str, NonEmptyString] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: str) -> str:
        """Validate the referenced Secret name."""
        return _validate_kubernetes_secret_name(name)

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, namespace: str) -> str:
        """Validate the referenced Secret namespace."""
        return _validate_kubernetes_namespace(namespace)


class CredentialRef(BaseModel):
    """Secret-free credential reference used by consumer projections."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Literal["kubernetes-secret", "environment", "workload-identity", "none"]
    name: NonEmptyString
    key: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_key_for_source(self) -> CredentialRef:
        """Ensure only Kubernetes Secret credential refs carry key names."""
        if self.source == "kubernetes-secret":
            if self.key is None:
                msg = "kubernetes-secret credential ref requires key"
                raise ValueError(msg)
            return self
        if self.key is not None:
            msg = f"{self.source} credential ref does not accept key"
            raise ValueError(msg)
        return self


class StorageCredentialBinding(BaseModel):
    """Secret-free storage credential source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["kubernetes-secret", "environment", "workload-identity", "none"]
    secret_ref: KubernetesSecretRef | None = None
    env_refs: dict[str, NonEmptyString] = Field(default_factory=dict)
    service_account_ref: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_mode_sources(self) -> StorageCredentialBinding:
        """Ensure credential source fields match the selected mode."""
        if self.mode == "kubernetes-secret":
            if self.secret_ref is None:
                msg = "kubernetes-secret credential binding requires secret_ref"
                raise ValueError(msg)
            if self.env_refs or self.service_account_ref is not None:
                msg = "kubernetes-secret credential binding only accepts secret_ref"
                raise ValueError(msg)
            return self
        if self.mode == "environment":
            if not self.env_refs:
                msg = "environment credential binding requires env_refs"
                raise ValueError(msg)
            if self.secret_ref is not None or self.service_account_ref is not None:
                msg = "environment credential binding only accepts env_refs"
                raise ValueError(msg)
            return self
        if self.mode == "workload-identity":
            if self.service_account_ref is None:
                msg = "workload-identity credential binding requires service_account_ref"
                raise ValueError(msg)
            if self.secret_ref is not None or self.env_refs:
                msg = "workload-identity credential binding only accepts service_account_ref"
                raise ValueError(msg)
            return self
        if self.secret_ref is not None or self.env_refs or self.service_account_ref is not None:
            msg = "none credential binding does not accept credential source fields"
            raise ValueError(msg)
        return self

    def as_credential_ref(self, logical_key: str) -> CredentialRef:
        """Return a consumer credential reference for a logical key."""
        if self.mode == "kubernetes-secret":
            if self.secret_ref is None:
                msg = "kubernetes-secret credential binding requires secret_ref"
                raise ValueError(msg)
            secret_key = self.secret_ref.keys.get(logical_key)
            if secret_key is None:
                msg = f"credential key {logical_key!r} not present in secret_ref.keys"
                raise ValueError(msg)
            return CredentialRef(source=self.mode, name=self.secret_ref.name, key=secret_key)
        if self.mode == "environment":
            env_name = self.env_refs.get(logical_key)
            if env_name is None:
                msg = f"credential key {logical_key!r} not present in env_refs"
                raise ValueError(msg)
            return CredentialRef(source=self.mode, name=env_name)
        if self.mode == "workload-identity":
            if self.service_account_ref is None:
                msg = "workload-identity credential binding requires service_account_ref"
                raise ValueError(msg)
            return CredentialRef(source=self.mode, name=self.service_account_ref)
        return CredentialRef(source="none", name="none")


class StorageWarehouse(BaseModel):
    """Resolved warehouse location owned by a storage deployment binding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    uri: NonEmptyString
    bucket: NonEmptyString
    prefix: str = ""


class StorageBucketRequirement(BaseModel):
    """Desired storage bucket state emitted by storage plugins."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NonEmptyString
    uri: NonEmptyString
    purpose: Literal["warehouse", "artifacts", "landing", "quarantine", "checkpoints", "exports"]
    create_policy: Literal["create-if-missing", "must-exist", "never-create"]
    prefixes: list[str] = Field(default_factory=list)
    features: dict[str, str] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)


class StorageCapabilities(BaseModel):
    """Storage protocol and credential capabilities available to consumers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocols: list[NonEmptyString] = Field(default_factory=list)
    credential_modes: list[NonEmptyString] = Field(default_factory=list)
    sts_supported: bool = False
    path_style_access: bool = False


class StorageProvisioningIntent(BaseModel):
    """Storage provisioning desired state without performing side effects."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    mode: Literal["helm-job", "external", "manual", "future-plugin-runtime"] = "manual"
    default_create_policy: Literal["create-if-missing", "must-exist", "never-create"] = (
        "never-create"
    )


class StorageRuntimeBinding(BaseModel):
    """Runtime-specific storage fragments derived from neutral storage state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pyiceberg_properties: dict[str, str] = Field(default_factory=dict)
    dbt_profile_fragment: dict[str, Any] = Field(default_factory=dict)
    dagster_resources: dict[str, Any] = Field(default_factory=dict)
    env_refs: dict[str, NonEmptyString] = Field(default_factory=dict)

    @field_validator("pyiceberg_properties", "dbt_profile_fragment", "dagster_resources")
    @classmethod
    def validate_secret_free_fragments(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Ensure runtime fragments carry config only, not credential values."""
        _assert_no_secret_material(value, "runtime")
        return value


class StorageServiceEndpoint(BaseModel):
    """Resolved storage service endpoint for deployment consumers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    internal_url: NonEmptyString
    external_url: NonEmptyString
    region: NonEmptyString
    warehouse_path: NonEmptyString
    path_style_access: bool = False


class DbtStorageBinding(BaseModel):
    """dbt profile storage projection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_name: NonEmptyString
    target_name: NonEmptyString
    schema_name: NonEmptyString
    profile_fragment: dict[str, Any] = Field(default_factory=dict)
    env_refs: dict[str, NonEmptyString] = Field(default_factory=dict)

    @field_validator("profile_fragment")
    @classmethod
    def validate_secret_free_profile_fragment(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Ensure dbt profile fragments do not inline credential values."""
        _assert_no_secret_material(value, "dbt.profile_fragment")
        return value


class DagsterStorageBinding(BaseModel):
    """Dagster resource storage projection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_key: NonEmptyString
    asset_io_manager_key: NonEmptyString
    resources: dict[str, Any] = Field(default_factory=dict)
    env_refs: dict[str, NonEmptyString] = Field(default_factory=dict)

    @field_validator("resources")
    @classmethod
    def validate_secret_free_resources(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Ensure Dagster resource fragments do not inline credential values."""
        _assert_no_secret_material(value, "dagster.resources")
        return value


class StorageDeploymentBinding(BaseModel):
    """Secret-free storage deployment binding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: NonEmptyString
    protocol: NonEmptyString = "s3-compatible"
    endpoint: StorageServiceEndpoint
    warehouse: StorageWarehouse | None = None
    allowed_locations: list[NonEmptyString] = Field(default_factory=list)
    buckets: list[StorageBucketRequirement] = Field(default_factory=list)
    credentials: StorageCredentialBinding
    capabilities: StorageCapabilities = Field(default_factory=StorageCapabilities)
    provisioning: StorageProvisioningIntent = Field(default_factory=StorageProvisioningIntent)
    runtime: StorageRuntimeBinding = Field(default_factory=StorageRuntimeBinding)
    dbt: DbtStorageBinding
    dagster: DagsterStorageBinding
    notes: list[str] = Field(default_factory=list)


class PolarisCatalogDeploymentBinding(BaseModel):
    """Polaris catalog-owned storage configuration for deployment renderers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    storage_type: Literal["S3"]
    warehouse: NonEmptyString | None = None
    default_base_location: NonEmptyString
    allowed_locations: list[NonEmptyString]
    endpoint: NonEmptyString
    endpoint_internal: NonEmptyString
    catalog_uri: NonEmptyString | None = None
    path_style_access: bool
    sts_unavailable: bool
    credential_refs: dict[str, CredentialRef] = Field(default_factory=dict)


class IcebergRestCatalogBinding(BaseModel):
    """Secret-free Iceberg REST catalog projection for runtime consumers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog_name: NonEmptyString = "iceberg"
    uri: NonEmptyString
    warehouse: NonEmptyString
    properties: dict[str, str] = Field(default_factory=dict)

    @field_validator("properties")
    @classmethod
    def validate_secret_free_properties(cls, value: dict[str, str]) -> dict[str, str]:
        """Ensure catalog properties do not inline credential values."""
        _assert_no_secret_material(value, "catalog.iceberg_rest.properties")
        return value


class DbtCatalogBinding(BaseModel):
    """dbt profile catalog projection derived from catalog-owned deployment state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_fragment: dict[str, Any] = Field(default_factory=dict)
    env_refs: dict[str, NonEmptyString] = Field(default_factory=dict)
    iceberg_rest: IcebergRestCatalogBinding | None = None

    @field_validator("profile_fragment")
    @classmethod
    def validate_secret_free_profile_fragment(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Ensure catalog profile fragments do not inline credential values."""
        _assert_no_secret_material(value, "dbt.catalog.profile_fragment")
        return value


class CatalogDeploymentBinding(BaseModel):
    """Secret-free catalog deployment binding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: NonEmptyString
    polaris: PolarisCatalogDeploymentBinding | None = None
    iceberg_rest: IcebergRestCatalogBinding | None = None
    dbt: DbtCatalogBinding | None = None

    @model_validator(mode="after")
    def validate_provider_binding(self) -> CatalogDeploymentBinding:
        """Ensure provider-specific catalog binding is present when required."""
        if self.provider == "polaris" and self.polaris is None:
            msg = "polaris catalog deployment binding requires polaris details"
            raise ValueError(msg)
        return self


class DltIngestionBinding(BaseModel):
    """Secret-free dlt runtime binding derived from composed platform plugins."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_name: NonEmptyString
    destination: Literal["filesystem"]
    table_format: Literal["iceberg"]
    source_filesystem: dict[str, Any] = Field(default_factory=dict)
    destination_filesystem: dict[str, Any] = Field(default_factory=dict)
    iceberg_catalog_env: dict[str, str] = Field(default_factory=dict)
    env_refs: dict[str, NonEmptyString] = Field(default_factory=dict)

    @field_validator("source_filesystem", "destination_filesystem")
    @classmethod
    def validate_secret_free_runtime_maps(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Ensure dlt runtime maps carry config only, not credential values."""
        _assert_dlt_filesystem_fragment_secret_free(value, "ingestion.dlt.runtime")
        return value

    @field_validator("iceberg_catalog_env")
    @classmethod
    def validate_secret_free_catalog_env(cls, value: dict[str, str]) -> dict[str, str]:
        """Ensure dlt catalog env carries only non-secret PyIceberg properties."""
        _assert_no_secret_material(value, "ingestion.dlt.iceberg_catalog_env")
        return value


class IngestionDeploymentBinding(BaseModel):
    """Secret-free ingestion deployment binding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Literal["dlt"]
    dlt: DltIngestionBinding


class IngestionOutputTable(BaseModel):
    """Platform-visible Iceberg table state created by ingestion sources."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_name: NonEmptyString
    source_type: Literal["filesystem"]
    table_format: Literal["iceberg"] = "iceberg"
    logical_table: NonEmptyString
    physical_table: NonEmptyString
    file_format: Literal["csv", "jsonl", "parquet"]
    source_path: NonEmptyString
    write_mode: Literal["append", "replace", "merge"]
    schema_contract: Literal["evolve", "freeze"]
    freshness_field: NonEmptyString | None = None
    primary_key: NonEmptyString | list[NonEmptyString] | None = None
    cursor_field: NonEmptyString | None = None
    quality_tier: Literal["bronze", "silver", "gold"] = "bronze"

    @field_validator("logical_table", "physical_table")
    @classmethod
    def validate_namespace_table_identifier(cls, value: str) -> str:
        """Validate table identifiers as exactly namespace.table."""
        parts = value.split(".")
        if len(parts) != 2 or any(part.strip() != part or not part for part in parts):
            msg = "table identifier must be exactly namespace.table with non-empty parts"
            raise ValueError(msg)
        if any(_INGESTION_OUTPUT_TABLE_IDENTIFIER.fullmatch(part) is None for part in parts):
            msg = "table identifier parts must use safe identifier characters"
            raise ValueError(msg)
        return value

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        """Validate source path using FloeSpec ingestion source path semantics."""
        path = value.strip()
        if not path:
            msg = "source_path must not be empty"
            raise ValueError(msg)
        if path != value:
            msg = "source_path must not contain leading or trailing whitespace"
            raise ValueError(msg)

        parsed = urlsplit(value)
        if _contains_ingestion_output_credential_path_part(
            parsed.query
        ) or _contains_ingestion_output_credential_path_part(parsed.fragment):
            msg = "source_path must not contain embedded credential material"
            raise ValueError(msg)

        if parsed.scheme:
            if parsed.scheme not in {"s3", "gs", "az"}:
                msg = "source_path URI scheme must be one of s3://, gs://, or az://"
                raise ValueError(msg)
            if parsed.username or parsed.password or "@" in parsed.netloc:
                msg = "source_path must not contain embedded credential material"
                raise ValueError(msg)
            if not parsed.netloc:
                msg = "object-store source_path must include a bucket or container"
                raise ValueError(msg)
            return value

        if value.startswith("/"):
            msg = "local source_path must be relative"
            raise ValueError(msg)
        if "://" in value:
            msg = "source_path URI scheme must be one of s3://, gs://, or az://"
            raise ValueError(msg)
        return value


def _contains_ingestion_output_credential_path_part(value: str) -> bool:
    """Return True when a URI query or fragment contains credential-like terms."""
    if not value:
        return False

    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "", lowered)
    return any(
        term in lowered or re.sub(r"[^a-z0-9]+", "", term) in normalized
        for term in _INGESTION_OUTPUT_SOURCE_PATH_SECRET_MARKERS
    )


class DeploymentConfig(BaseModel):
    """Deployment bindings derived during compilation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    storage: StorageDeploymentBinding | None = None
    catalog: CatalogDeploymentBinding | None = None
    ingestion: IngestionDeploymentBinding | None = None


class ResolvedModel(BaseModel):
    """A transform model with resolved compute target and quality configuration.

    Represents a single dbt model after compilation, with the compute
    target resolved (never None - uses platform default if not specified)
    and optional quality checks attached from the quality gate configuration.

    Attributes:
        name: Model name (dbt model identifier).
        compute: Resolved compute target (never None).
        tags: dbt tags for selection.
        depends_on: Explicit dependencies (model names).
        quality_checks: Quality checks assigned to this model (from quality gates).
        quality_tier: Quality tier for this model (bronze, silver, gold).

    Example:
        >>> model = ResolvedModel(
        ...     name="stg_customers",
        ...     compute="duckdb",
        ...     tags=["staging", "customers"],
        ...     depends_on=["raw_customers"],
        ...     quality_tier="silver",
        ... )
        >>> model.compute
        'duckdb'

    See Also:
        - data-model.md: ResolvedModel entity specification
        - quality_config.py: QualityGates tier definitions
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        description="Model name (dbt model identifier)",
        examples=["stg_customers", "fct_orders"],
    )
    compute: str = Field(
        ...,
        min_length=1,
        description="Resolved compute target (never None)",
        examples=["duckdb", "snowflake"],
    )
    tags: list[str] | None = Field(
        default=None,
        description="dbt tags for selection",
        examples=[["staging", "customers"]],
    )
    depends_on: list[str] | None = Field(
        default=None,
        description="Explicit dependencies (model names)",
        examples=[["raw_customers", "raw_orders"]],
    )
    quality_checks: list[QualityCheck] | None = Field(
        default=None,
        description="Quality checks for this model",
    )
    quality_tier: Literal["bronze", "silver", "gold"] | None = Field(
        default=None,
        description="Quality tier for this model",
    )


class ResolvedTransforms(BaseModel):
    """Compiled transform configuration.

    Contains the list of resolved models and the default compute target
    used for models that don't specify an override.

    Attributes:
        models: List of resolved models with compute targets
        default_compute: Default compute target from platform

    Example:
        >>> transforms = ResolvedTransforms(
        ...     models=[
        ...         ResolvedModel(name="stg_customers", compute="duckdb"),
        ...         ResolvedModel(name="fct_orders", compute="duckdb"),
        ...     ],
        ...     default_compute="duckdb"
        ... )
        >>> len(transforms.models)
        2

    See Also:
        - data-model.md: ResolvedTransforms entity specification
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    models: list[ResolvedModel] = Field(
        ...,
        min_length=1,
        description="List of resolved models with compute targets",
    )
    default_compute: str = Field(
        ...,
        min_length=1,
        description="Default compute target from platform",
        examples=["duckdb", "snowflake"],
    )


class ResolvedGovernance(BaseModel):
    """Governance settings after inheritance resolution.

    Contains security and compliance settings resolved from the
    inheritance chain, with child manifests unable to weaken parent policies.

    Attributes:
        pii_encryption: PII encryption policy (required or optional)
        audit_logging: Audit logging policy (enabled or disabled)
        policy_enforcement_level: Enforcement level (off, warn, strict)
        data_retention_days: Data retention period in days
        default_ttl_hours: Table-level partition TTL in hours
        snapshot_keep_last: Minimum Iceberg snapshots to retain per table

    Example:
        >>> governance = ResolvedGovernance(
        ...     pii_encryption="required",
        ...     audit_logging="enabled",
        ...     policy_enforcement_level="strict",
        ...     data_retention_days=90,
        ...     default_ttl_hours=720,
        ...     snapshot_keep_last=10,
        ... )
        >>> governance.pii_encryption
        'required'

    See Also:
        - data-model.md: ResolvedGovernance entity specification
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pii_encryption: Literal["required", "optional"] | None = Field(
        default=None,
        description="PII encryption policy",
    )
    audit_logging: Literal["enabled", "disabled"] | None = Field(
        default=None,
        description="Audit logging policy",
    )
    policy_enforcement_level: Literal["off", "warn", "strict"] | None = Field(
        default=None,
        description="Policy enforcement level",
    )
    data_retention_days: int | None = Field(
        default=None,
        ge=1,
        description="Data retention period in days",
    )
    default_ttl_hours: int | None = Field(
        default=None,
        ge=1,
        le=8760,
        description="Table-level partition TTL in hours",
    )
    snapshot_keep_last: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Minimum Iceberg snapshots to retain per table",
    )
    stale_table_recovery_mode: Literal["strict", "repair"] | None = Field(
        default=None,
        description="Configured stale Iceberg metadata recovery mode for runtimes",
    )


class ObservabilityConfig(BaseModel):
    """Observability settings including telemetry configuration.

    This configuration controls all observability aspects:
    - OpenTelemetry traces, metrics, and logs (via TelemetryConfig)
    - OpenLineage data lineage tracking
    - Lineage namespace for correlation

    Attributes:
        telemetry: Full OpenTelemetry configuration (TelemetryConfig)
        lineage: Whether OpenLineage is enabled
        lineage_namespace: Namespace for lineage events

    Examples:
        >>> from floe_core.schemas.telemetry import TelemetryConfig, ResourceAttributes
        >>> config = ObservabilityConfig(
        ...     telemetry=TelemetryConfig(
        ...         enabled=True,
        ...         resource_attributes=ResourceAttributes(
        ...             service_name="my-pipeline",
        ...             service_version="1.0.0",
        ...             deployment_environment="prod",
        ...             floe_namespace="analytics",
        ...             floe_product_name="customer-360",
        ...             floe_product_version="2.1.0",
        ...             floe_mode="prod",
        ...         ),
        ...     ),
        ...     lineage=True,
        ...     lineage_namespace="my-pipeline",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    telemetry: TelemetryConfig = Field(
        ...,
        description="OpenTelemetry configuration (traces, metrics, logs)",
    )
    lineage: bool = Field(
        default=True,
        description="Whether OpenLineage is enabled",
    )
    lineage_namespace: str = Field(
        ...,
        min_length=1,
        description="Namespace for lineage events",
    )
    lineage_endpoint: str | None = Field(
        default=None,
        description="OpenLineage HTTP endpoint for lineage events",
    )
    lineage_transport: Literal["http", "console", "noop"] | None = Field(
        default=None,
        description="OpenLineage transport type",
    )


# ==============================================================================
# Epic 3B: Enforcement Result Summary
# ==============================================================================


class EnforcementResultSummary(BaseModel):
    """Lightweight summary of enforcement result for inclusion in CompiledArtifacts.

    This summary contains only the essential metrics for downstream consumption.
    Full violation details are exported separately (SARIF/JSON/HTML).

    Contract Version: 0.7.0 (Epic 3E additions)

    Attributes:
        passed: Overall pass/fail status.
        error_count: Number of error-severity violations.
        warning_count: Number of warning-severity violations.
        policy_types_checked: List of policy types that were enforced.
        models_validated: Number of models that were validated.
        enforcement_level: Applied enforcement level (off, warn, strict).
        rbac_principal: Authenticated principal name from RBAC validation (Epic 3E).
        secrets_scanned: Count of secret scanning violations found (Epic 3E).

    Example:
        >>> summary = EnforcementResultSummary(
        ...     passed=False,
        ...     error_count=3,
        ...     warning_count=5,
        ...     policy_types_checked=["naming", "coverage", "documentation"],
        ...     models_validated=50,
        ...     enforcement_level="strict",
        ... )
        >>> summary.passed
        False

    See Also:
        - data-model.md: EnforcementResultSummary entity specification
        - EnforcementResult: Full result in enforcement module
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool = Field(
        ...,
        description="Overall pass/fail status",
    )
    error_count: int = Field(
        ...,
        ge=0,
        description="Number of error-severity violations",
    )
    warning_count: int = Field(
        ...,
        ge=0,
        description="Number of warning-severity violations",
    )
    policy_types_checked: list[str] = Field(
        ...,
        description="List of policy types that were enforced",
    )
    models_validated: int = Field(
        ...,
        ge=0,
        description="Number of models that were validated",
    )
    enforcement_level: Literal["off", "warn", "strict"] = Field(
        ...,
        description="Applied enforcement level",
    )
    # Epic 3E: Governance integration fields
    rbac_principal: str | None = Field(
        default=None,
        description="Authenticated principal name from RBAC validation",
    )
    secrets_scanned: int = Field(
        default=0,
        ge=0,
        description="Count of secret scanning violations found",
    )


# Deployment mode types
DeploymentMode = Literal["simple", "centralized", "mesh"]
"""Valid deployment modes for data products.

- simple: Single floe.yaml, no inheritance
- centralized: Enterprise manifest inheritance
- mesh: Full Data Mesh with domains and contracts
"""


class CompiledArtifacts(BaseModel):
    """Output of floe compile - unified for all deployment modes.

    CompiledArtifacts is the single source of truth for pipeline execution.
    It contains resolved, validated configuration after manifest inheritance.

    The observability field contains TelemetryConfig which provides:
    - OpenTelemetry SDK configuration (Layer 1 - ENFORCED)
    - OTLP Collector endpoint (Layer 2 - ENFORCED)
    - Backend plugin selection (Layer 3 - PLUGGABLE)

    Contract Version: See COMPILED_ARTIFACTS_VERSION in versions.py

    Attributes:
        version: Schema version (semver)
        metadata: Compilation metadata
        identity: Product identity from catalog
        mode: Deployment mode (simple, centralized, mesh)
        inheritance_chain: Manifest inheritance lineage
        observability: Observability configuration with TelemetryConfig
        plugins: Resolved plugin selections (v0.2.0+)
        transforms: Compiled transform configuration (v0.2.0+)
        dbt_profiles: Generated profiles.yml content (v0.2.0+)
        governance: Resolved governance settings (v0.2.0+, optional)
        enforcement_result: Enforcement result summary (v0.3.0+, optional)
        data_contracts: Validated data contracts (v0.3.0+, Epic 3C)
        deployment: Secret-free deployment bindings for composed platform services
        ingestion_outputs: Platform-visible Iceberg tables created by ingestion sources

    Examples:
        >>> from datetime import datetime
        >>> from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION
        >>> from floe_core.schemas.telemetry import TelemetryConfig, ResourceAttributes
        >>> artifacts = CompiledArtifacts(
        ...     version=COMPILED_ARTIFACTS_VERSION,
        ...     metadata=CompilationMetadata(
        ...         compiled_at=datetime.now(),
        ...         floe_version="0.2.0",
        ...         source_hash="sha256:abc123",
        ...         product_name="my-pipeline",
        ...         product_version="1.0.0",
        ...     ),
        ...     identity=ProductIdentity(
        ...         product_id="default.my_pipeline",
        ...         domain="default",
        ...         repository="github.com/acme/my-pipeline",
        ...     ),
        ...     mode="simple",
        ...     observability=ObservabilityConfig(
        ...         telemetry=TelemetryConfig(
        ...             resource_attributes=ResourceAttributes(...),
        ...         ),
        ...         lineage_namespace="my-pipeline",
        ...     ),
        ...     plugins=ResolvedPlugins(
        ...         compute=PluginRef(type="duckdb", version="0.9.0"),
        ...         orchestrator=PluginRef(type="dagster", version="1.5.0"),
        ...     ),
        ...     transforms=ResolvedTransforms(
        ...         models=[ResolvedModel(name="stg_customers", compute="duckdb")],
        ...         default_compute="duckdb",
        ...     ),
        ...     dbt_profiles={"default": {"target": "dev", "outputs": {...}}},
        ... )

    See Also:
        - docs/contracts/compiled-artifacts.md: Full specification
        - ADR-0012: CompiledArtifacts contract design
        - TelemetryConfig: OpenTelemetry configuration
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[
        str,
        Field(
            default=COMPILED_ARTIFACTS_VERSION,
            pattern=r"^\d+\.\d+\.\d+$",
            description="Schema version (semver)",
        ),
    ]

    metadata: CompilationMetadata = Field(
        ...,
        description="Compilation metadata",
    )

    identity: ProductIdentity = Field(
        ...,
        description="Product identity from catalog",
    )

    mode: DeploymentMode = Field(
        default="simple",
        description="Deployment mode (simple, centralized, mesh)",
    )

    inheritance_chain: Annotated[
        list[ManifestRef],
        Field(
            default_factory=list,
            description="Manifest inheritance lineage",
        ),
    ]

    observability: ObservabilityConfig = Field(
        ...,
        description="Observability configuration with TelemetryConfig",
    )

    # Epic 2B additions (v0.2.0)
    plugins: ResolvedPlugins | None = Field(
        default=None,
        description="Resolved plugin selections (v0.2.0+, optional for backward compat)",
    )

    deployment: DeploymentConfig | None = Field(
        default=None,
        description="Deployment bindings derived from resolved plugin configuration",
    )

    ingestion_outputs: list[IngestionOutputTable] = Field(
        default_factory=list,
        description="Platform-visible Iceberg tables created by ingestion sources",
    )

    transforms: ResolvedTransforms | None = Field(
        default=None,
        description="Compiled transform configuration (v0.2.0+, optional for backward compat)",
    )

    dbt_profiles: dict[str, Any] | None = Field(
        default=None,
        description="Generated profiles.yml content (v0.2.0+, optional for backward compat)",
    )

    governance: ResolvedGovernance | None = Field(
        default=None,
        description="Resolved governance settings (v0.2.0+, optional)",
    )

    # Epic 3B addition (v0.3.0)
    enforcement_result: EnforcementResultSummary | None = Field(
        default=None,
        description="Enforcement result summary (v0.3.0+, optional for backward compat)",
    )

    # Epic 3C addition (v0.3.0)
    data_contracts: list[DataContract] = Field(
        default_factory=list,
        description="Validated data contracts with schema hash and validation metadata (v0.3.0+)",
    )

    quality_config: QualityConfig | None = Field(
        default=None,
        description="Resolved quality configuration",
    )

    def _to_serializable_dict(self) -> dict[str, Any]:
        """Return the shared JSON-safe artifact payload."""
        return self.model_dump(mode="json", by_alias=True)

    def to_json_file(self, path: Path) -> None:
        """Write CompiledArtifacts to a JSON file.

        Uses Pydantic's model_dump with mode='json' and by_alias=True
        for proper JSON serialization of datetime and other types.

        Args:
            path: Path to write the JSON file.

        Example:
            >>> artifacts = CompiledArtifacts(...)
            >>> artifacts.to_json_file(Path("target/compiled_artifacts.json"))

        See Also:
            - from_json_file: Load artifacts from JSON
            - to_yaml_file: Write artifacts to YAML
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._to_serializable_dict(), indent=2))

    def to_yaml_file(self, path: Path) -> None:
        """Write CompiledArtifacts to a YAML file.

        Uses PyYAML for serialization with human-readable formatting.
        The YAML output is semantically equivalent to JSON output.

        Args:
            path: Path to write the YAML file.

        Example:
            >>> artifacts = CompiledArtifacts(...)
            >>> artifacts.to_yaml_file(Path("target/compiled_artifacts.yaml"))

        See Also:
            - from_yaml_file: Load artifacts from YAML
            - to_json_file: Write artifacts to JSON
        """
        import yaml

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(
                self._to_serializable_dict(),
                default_flow_style=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

    def to_configmap_yaml(
        self,
        name: str = "floe-compiled-values",
        namespace: str | None = None,
    ) -> str:
        """Render CompiledArtifacts as a Kubernetes ConfigMap.

        The embedded ``data.values.yaml`` payload is generated from the same
        JSON-safe dictionary used by the existing JSON and YAML serializers so
        ConfigMap output stays a wrapper around the single CompiledArtifacts
        contract rather than becoming a parallel representation.

        Args:
            name: ConfigMap metadata.name. Defaults to ``floe-compiled-values``.
            namespace: Optional ConfigMap metadata.namespace.

        Returns:
            YAML string containing a v1 ConfigMap with ``data.values.yaml``.
        """
        import yaml

        validated_name = _validate_configmap_name(name)
        validated_namespace = (
            _validate_configmap_namespace(namespace) if namespace is not None else None
        )

        class _LiteralYamlString(str):
            """Force PyYAML to emit multiline values as a literal block."""

        class _ConfigMapDumper(yaml.SafeDumper):
            """Safe dumper with literal-block support for embedded YAML."""

        def _represent_literal_yaml(
            dumper: yaml.SafeDumper,
            value: _LiteralYamlString,
        ) -> yaml.nodes.ScalarNode:
            return dumper.represent_scalar(
                "tag:yaml.org,2002:str",
                value,
                style="|",
            )

        _ConfigMapDumper.add_representer(_LiteralYamlString, _represent_literal_yaml)

        metadata: dict[str, str] = {"name": validated_name}
        if validated_namespace is not None:
            metadata["namespace"] = validated_namespace

        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": metadata,
            "data": {
                "values.yaml": _LiteralYamlString(
                    yaml.safe_dump(
                        self._to_serializable_dict(),
                        default_flow_style=False,
                        allow_unicode=True,
                        sort_keys=False,
                    )
                )
            },
        }
        return yaml.dump(
            configmap,
            Dumper=_ConfigMapDumper,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    @classmethod
    def from_json_file(cls, path: Path) -> CompiledArtifacts:
        """Load CompiledArtifacts from a JSON file.

        Uses Pydantic's model_validate for strict validation.

        Args:
            path: Path to the JSON file.

        Returns:
            CompiledArtifacts instance.

        Raises:
            FileNotFoundError: If file does not exist.
            pydantic.ValidationError: If JSON is invalid.

        Example:
            >>> artifacts = CompiledArtifacts.from_json_file(
            ...     Path("target/compiled_artifacts.json")
            ... )
            >>> artifacts.version
            '0.2.0'

        See Also:
            - to_json_file: Write artifacts to JSON
            - from_yaml_file: Load artifacts from YAML
        """
        data = json.loads(path.read_text())
        return cls.model_validate(data)

    @classmethod
    def from_yaml_file(cls, path: Path) -> CompiledArtifacts:
        """Load CompiledArtifacts from a YAML file.

        Uses PyYAML for parsing and Pydantic's model_validate for validation.
        YAML is parsed first, then validated against the schema.

        Args:
            path: Path to the YAML file.

        Returns:
            CompiledArtifacts instance.

        Raises:
            FileNotFoundError: If file does not exist.
            yaml.YAMLError: If YAML syntax is invalid.
            pydantic.ValidationError: If schema validation fails.

        Example:
            >>> artifacts = CompiledArtifacts.from_yaml_file(
            ...     Path("target/compiled_artifacts.yaml")
            ... )
            >>> artifacts.version
            '0.2.0'

        See Also:
            - to_yaml_file: Write artifacts to YAML
            - from_json_file: Load artifacts from JSON
        """
        import yaml

        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        return cls.model_validate(data)

    @classmethod
    def export_json_schema(cls) -> dict[str, Any]:
        """Export JSON Schema for IDE autocomplete and external validation.

        Returns the Pydantic-generated JSON Schema with $id and $schema
        metadata for standards compliance.

        Returns:
            JSON Schema dictionary.

        Example:
            >>> schema = CompiledArtifacts.export_json_schema()
            >>> schema["$schema"]
            'https://json-schema.org/draft/2020-12/schema'
            >>> "properties" in schema
            True

        See Also:
            - model_json_schema: Underlying Pydantic method
        """
        schema = cls.model_json_schema()
        # Add standard JSON Schema metadata
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = "https://floe.dev/schemas/compiled-artifacts.json"
        return schema


__all__ = [
    # Core artifacts
    "CatalogDeploymentBinding",
    "CompiledArtifacts",
    "CompilationMetadata",
    "CredentialRef",
    "DbtCatalogBinding",
    "DeploymentConfig",
    "DeploymentMode",
    "DltIngestionBinding",
    "IcebergRestCatalogBinding",
    "IngestionDeploymentBinding",
    "IngestionOutputTable",
    "KubernetesSecretRef",
    "ManifestRef",
    "ObservabilityConfig",
    "ProductIdentity",
    # Plugin resolution (v0.2.0)
    "PluginRef",
    "ResolvedPlugins",
    # Transform resolution (v0.2.0)
    "ResolvedModel",
    "ResolvedTransforms",
    # Governance resolution (v0.2.0)
    "ResolvedGovernance",
    # Enforcement summary (v0.3.0 - Epic 3B)
    "EnforcementResultSummary",
    # Deployment bindings
    "DagsterStorageBinding",
    "DbtStorageBinding",
    "PolarisCatalogDeploymentBinding",
    "StorageBucketRequirement",
    "StorageCapabilities",
    "StorageCredentialBinding",
    "StorageDeploymentBinding",
    "StorageProvisioningIntent",
    "StorageRuntimeBinding",
    "StorageServiceEndpoint",
    "StorageWarehouse",
]

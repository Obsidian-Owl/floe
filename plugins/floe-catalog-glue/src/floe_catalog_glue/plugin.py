"""AWS Glue CatalogPlugin implementation for Floe."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

from floe_core.composition.models import (
    CredentialMode,
    IdentityMode,
    PluginRequirements,
    RequirementSet,
)
from floe_core.plugin_errors import CatalogUnavailableError, NotSupportedError
from floe_core.plugins import CatalogPlugin
from floe_core.plugins.catalog import Catalog
from floe_core.schemas.compiled_artifacts import (
    CatalogDeploymentBinding,
    CredentialRef,
    GlueCatalogDeploymentBinding,
    KubernetesSecretRef,
    StorageDeploymentBinding,
)
from pyiceberg.catalog import load_catalog

from floe_catalog_glue.config import GlueCatalogConfig

if TYPE_CHECKING:
    from pydantic import BaseModel

TRACER_NAME = "floe.catalog.glue"
KEY_ACCESS_KEY_ID = "accessKeyId"
KEY_SECRET_ACCESS_KEY = "secretAccessKey"  # pragma: allowlist secret
KEY_SESSION_TOKEN = "sessionToken"


class _GlueCatalogOps(Protocol):
    """PyIceberg catalog operations used by the Glue plugin."""

    def create_namespace(self, namespace: str, properties: dict[str, str]) -> None:
        """Create a namespace with properties."""
        ...

    def list_namespaces(self, namespace: tuple[str, ...] | None = None) -> list[tuple[str, ...]]:
        """List namespaces, optionally below a parent namespace."""
        ...

    def drop_namespace(self, namespace: str) -> None:
        """Drop a namespace."""
        ...

    def create_table(self, identifier: str, schema: dict[str, Any], **kwargs: Any) -> None:
        """Create an Iceberg table."""
        ...

    def list_tables(self, namespace: str) -> list[tuple[str, ...]]:
        """List tables in a namespace."""
        ...

    def drop_table(self, identifier: str, purge: bool = False) -> None:
        """Drop a table."""
        ...


class GlueCatalogPlugin(CatalogPlugin):
    """Native AWS Glue catalog plugin implementing the CatalogPlugin ABC."""

    def __init__(self, config: GlueCatalogConfig | None = None) -> None:
        """Initialize the AWS Glue catalog plugin."""
        super().__init__()
        self._config = config
        self._catalog: Catalog | None = None

    def _require_config(self) -> GlueCatalogConfig:
        """Return config or raise a structured plugin configuration error."""
        if self._config is None:
            from floe_core.plugin_errors import PluginConfigurationError

            raise PluginConfigurationError(
                "glue",
                [{"field": "_config", "message": "Plugin 'glue' not configured"}],
            )
        return cast(GlueCatalogConfig, self._config)

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "glue"

    @property
    def version(self) -> str:
        """Return the plugin version."""
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Return the required Floe API version."""
        return "1.0"

    @property
    def description(self) -> str:
        """Return a human-readable plugin description."""
        return "AWS Glue catalog plugin for Iceberg table management"

    @property
    def tracer_name(self) -> str:
        """Return the OpenTelemetry tracer name."""
        return TRACER_NAME

    def get_config_schema(self) -> type[BaseModel]:
        """Return the Pydantic config schema for this plugin."""
        return GlueCatalogConfig

    def connect(self, config: dict[str, Any]) -> Catalog:
        """Connect to AWS Glue using PyIceberg's Glue catalog."""
        catalog_config = self._pyiceberg_config()
        conflicts = {
            key
            for key, value in config.items()
            if key in catalog_config and catalog_config[key] != value
        }
        if conflicts:
            msg = f"connect() config conflicts with plugin config: {sorted(conflicts)}"
            raise ValueError(msg)
        catalog_config.update(config)
        catalog = cast(Catalog, load_catalog("glue", **catalog_config))
        self._catalog = catalog
        return catalog

    def _pyiceberg_config(self) -> dict[str, Any]:
        """Return non-secret PyIceberg Glue catalog properties."""
        cfg = self._require_config()
        catalog_config: dict[str, Any] = {
            "type": "glue",
            "glue.region": cfg.region,
            "glue.skip-archive": str(cfg.skip_archive).lower(),
        }
        if cfg.warehouse is not None:
            catalog_config["warehouse"] = cfg.warehouse
        if cfg.catalog_id is not None:
            catalog_config["glue.id"] = cfg.catalog_id
        if cfg.endpoint_override is not None:
            catalog_config["glue.endpoint"] = cfg.endpoint_override
        if cfg.max_retries is not None:
            catalog_config["glue.max-retries"] = cfg.max_retries
        if cfg.retry_mode is not None:
            catalog_config["glue.retry-mode"] = cfg.retry_mode
        return catalog_config

    def get_storage_requirements(self) -> PluginRequirements:
        """Return storage requirements Glue can compose with."""
        cfg = self._require_config()
        identity_modes: list[IdentityMode] = (
            ["aws-irsa", "aws-pod-identity"] if cfg.credential_mode == "workload-identity" else []
        )
        credential_modes: list[CredentialMode] = [cast(CredentialMode, cfg.credential_mode)]
        return PluginRequirements(
            plugin_type="catalog",
            plugin_name="glue",
            requirements=RequirementSet(
                protocols=["s3"],
                credential_modes=credential_modes,
                identity_modes=identity_modes,
                requires_server_side_storage_access=True,
                supports_no_sts=False,
                supports_path_style_access=False,
            ),
        )

    def build_catalog_deployment(
        self,
        storage: StorageDeploymentBinding,
    ) -> CatalogDeploymentBinding:
        """Translate neutral AWS S3 storage state into Glue deployment config."""
        cfg = self._require_config()
        if storage.protocol != "s3":
            msg = "AWS Glue catalog requires storage protocol 's3'"
            raise ValueError(msg)
        if storage.warehouse is None:
            msg = "AWS Glue catalog deployment requires storage warehouse binding"
            raise ValueError(msg)
        if storage.credentials.mode != cfg.credential_mode:
            msg = f"AWS Glue catalog requires storage credential mode {cfg.credential_mode!r}"
            raise ValueError(msg)

        warehouse = cfg.warehouse or storage.warehouse.uri
        return CatalogDeploymentBinding(
            provider="glue",
            glue=GlueCatalogDeploymentBinding(
                catalog_name="glue",
                region=cfg.region,
                warehouse=warehouse,
                catalog_id=cfg.catalog_id,
                database_prefix=cfg.database_prefix,
                endpoint=cfg.endpoint_override,
                skip_archive=cfg.skip_archive,
                max_retries=cfg.max_retries,
                retry_mode=cfg.retry_mode,
                credential_refs=self._credential_refs(storage),
            ),
        )

    def _credential_refs(self, storage: StorageDeploymentBinding) -> dict[str, CredentialRef]:
        """Return secret-free Glue credential references derived from storage."""
        cfg = self._require_config()
        if cfg.credential_mode == "kubernetes-secret":
            if cfg.credential_secret_name is None:
                msg = "kubernetes-secret mode requires credential_secret_name"
                raise ValueError(msg)
            secret_ref = KubernetesSecretRef(
                name=cfg.credential_secret_name,
                namespace=cfg.credential_secret_namespace,
                keys={
                    KEY_ACCESS_KEY_ID: cfg.access_key_secret_key,
                    KEY_SECRET_ACCESS_KEY: cfg.secret_key_secret_key,
                    KEY_SESSION_TOKEN: cfg.session_token_secret_key,
                },
            )
            return {
                logical_key: CredentialRef(
                    source="kubernetes-secret",
                    name=secret_ref.name,
                    key=secret_key,
                )
                for logical_key, secret_key in secret_ref.keys.items()
            }
        return {
            KEY_ACCESS_KEY_ID: storage.credentials.as_credential_ref(KEY_ACCESS_KEY_ID),
            KEY_SECRET_ACCESS_KEY: storage.credentials.as_credential_ref(KEY_SECRET_ACCESS_KEY),
            KEY_SESSION_TOKEN: storage.credentials.as_credential_ref(KEY_SESSION_TOKEN),
        }

    def _connected_catalog(self) -> _GlueCatalogOps:
        """Return the connected catalog or raise a catalog availability error."""
        if self._catalog is None:
            raise CatalogUnavailableError(
                "glue",
                cause=ValueError("Catalog not connected; call connect() first."),
            )
        return cast(_GlueCatalogOps, self._catalog)

    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a namespace in AWS Glue."""
        self._connected_catalog().create_namespace(namespace, properties=properties or {})

    def list_namespaces(self, parent: str | None = None) -> list[str]:
        """List namespaces in AWS Glue."""
        catalog = self._connected_catalog()
        raw_namespaces = (
            catalog.list_namespaces(tuple(parent.split(".")))
            if parent
            else catalog.list_namespaces()
        )
        return [".".join(namespace) for namespace in raw_namespaces]

    def delete_namespace(self, namespace: str) -> None:
        """Delete a namespace from AWS Glue."""
        self._connected_catalog().drop_namespace(namespace)

    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create an Iceberg table in AWS Glue."""
        kwargs: dict[str, Any] = {}
        if location is not None:
            kwargs["location"] = location
        if properties is not None:
            kwargs["properties"] = properties
        self._connected_catalog().create_table(identifier, schema, **kwargs)

    def list_tables(self, namespace: str) -> list[str]:
        """List tables in an AWS Glue namespace."""
        raw_tables = self._connected_catalog().list_tables(namespace)
        return [".".join(table) for table in raw_tables]

    def drop_table(self, identifier: str, purge: bool = False) -> None:
        """Drop an Iceberg table from AWS Glue."""
        self._connected_catalog().drop_table(identifier, purge=purge)

    def vend_credentials(
        self,
        table_path: str,
        operations: list[str],
    ) -> dict[str, Any]:
        """Reject credential vending; Glue access is handled by AWS identity."""
        raise NotSupportedError(
            "vend_credentials",
            "glue",
            reason="AWS Glue does not vend credentials; use AWS identity or references.",
        )

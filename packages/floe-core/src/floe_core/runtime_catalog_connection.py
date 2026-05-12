"""Build secret-free runtime catalog connection projections from deployment bindings."""

from __future__ import annotations

from floe_core.schemas.compiled_artifacts import (
    CatalogDeploymentBinding,
    CredentialRef,
    RuntimeCatalogConnection,
    RuntimeCatalogPropertyValue,
    StorageDeploymentBinding,
)


def build_runtime_catalog_connection(
    *,
    storage: StorageDeploymentBinding | None,
    catalog: CatalogDeploymentBinding | None,
) -> RuntimeCatalogConnection:
    """Derive a neutral runtime catalog connection from compiled deployment bindings."""
    catalog_name = "iceberg"
    catalog_uri: str | None = None
    warehouse: str | None = None
    region: str | None = None
    path_style_access: bool | None = None
    properties: dict[str, RuntimeCatalogPropertyValue] = {}
    credential_refs: dict[str, CredentialRef] = {}
    env_refs: dict[str, str] = {}

    if catalog is not None and catalog.iceberg_rest is not None:
        iceberg_rest = catalog.iceberg_rest
        catalog_name = iceberg_rest.catalog_name
        catalog_uri = iceberg_rest.uri
        warehouse = iceberg_rest.warehouse
        properties.update(iceberg_rest.properties)
        if iceberg_rest.oauth2 is not None:
            env_refs["oauth2_client_id"] = iceberg_rest.oauth2.client_id_env
            env_refs["oauth2_client_secret"] = iceberg_rest.oauth2.client_secret_env
            env_refs["oauth2_server_uri"] = iceberg_rest.oauth2.oauth2_server_uri_env
            if iceberg_rest.oauth2.oauth2_scope_env is not None:
                env_refs["oauth2_scope"] = iceberg_rest.oauth2.oauth2_scope_env

    if catalog is not None and catalog.polaris is not None:
        polaris = catalog.polaris
        catalog_name = "polaris"
        catalog_uri = polaris.catalog_uri or catalog_uri
        warehouse = polaris.warehouse or warehouse or polaris.default_base_location
        path_style_access = polaris.path_style_access
        credential_refs.update(polaris.credential_refs)

    if catalog is not None and catalog.glue is not None:
        glue = catalog.glue
        catalog_name = glue.catalog_name
        warehouse = glue.warehouse
        region = glue.region
        credential_refs.update(glue.credential_refs)
        properties["type"] = "glue"
        properties["glue.region"] = glue.region
        # PyIceberg parses skip-archive with strtobool, so keep its canonical string form.
        properties["glue.skip-archive"] = str(glue.skip_archive).lower()
        # database_prefix is consumed by Glue namespace operations, not PyIceberg loading.
        if glue.catalog_id is not None:
            properties["glue.id"] = glue.catalog_id
        if glue.endpoint is not None:
            properties["glue.endpoint"] = glue.endpoint
        if glue.max_retries is not None:
            properties["glue.max-retries"] = glue.max_retries
        if glue.retry_mode is not None:
            properties["glue.retry-mode"] = glue.retry_mode
        properties.update(glue.properties)

    storage_endpoint: str | None = None
    if storage is not None:
        storage_endpoint = storage.endpoint.internal_url
        region = storage.endpoint.region
        if warehouse is None:
            warehouse = (
                storage.warehouse.uri
                if storage.warehouse is not None
                else storage.endpoint.warehouse_path
            )
        if path_style_access is None:
            path_style_access = storage.endpoint.path_style_access
        properties.update(storage.runtime.pyiceberg_properties)
        env_refs.update(storage.runtime.env_refs)

    return RuntimeCatalogConnection(
        catalog_name=catalog_name,
        catalog_uri=catalog_uri,
        warehouse=warehouse,
        storage_endpoint=storage_endpoint,
        region=region,
        path_style_access=path_style_access,
        properties=properties,
        credential_refs=credential_refs,
        env_refs=env_refs,
    )

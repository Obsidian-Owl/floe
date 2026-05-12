"""Live AWS provider validation for S3 storage plus Glue catalog composition."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping

import pytest
from floe_catalog_glue.config import GlueCatalogConfig
from floe_catalog_glue.plugin import GlueCatalogPlugin
from floe_core.runtime_catalog_connection import build_runtime_catalog_connection
from floe_iceberg.runtime_catalog import runtime_catalog_connection_to_pyiceberg_config
from floe_storage_aws_s3.config import AwsS3ObjectStoreConfig
from floe_storage_aws_s3.plugin import AwsS3ObjectStorePlugin
from pyiceberg.exceptions import NamespaceAlreadyExistsError, NoSuchNamespaceError
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live_aws,
    pytest.mark.requirement("LIVE-VALIDATION"),
]

LOGGER = logging.getLogger(__name__)

RUN_ID_PATTERN = re.compile(r"^floe-provider-[0-9]{8}T[0-9]{6}Z$")
REQUIRED_ENV = (
    "FLOE_AWS_REGION",
    "FLOE_AWS_TEST_BUCKET",
    "FLOE_AWS_TEST_PREFIX",
    "FLOE_AWS_GLUE_DATABASE_PREFIX",
    "FLOE_PROVIDER_SPIKE_RUN",
)


def _require_live_aws_env() -> dict[str, str]:
    if os.environ.get("FLOE_RUN_LIVE_AWS_PROVIDER_TESTS") != "1":
        pytest.fail("set FLOE_RUN_LIVE_AWS_PROVIDER_TESTS=1 to run live AWS provider tests")

    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        pytest.fail(f"missing live AWS provider test env vars: {', '.join(missing)}")

    env = {name: os.environ[name] for name in REQUIRED_ENV}
    if not RUN_ID_PATTERN.fullmatch(env["FLOE_PROVIDER_SPIKE_RUN"]):
        pytest.fail("FLOE_PROVIDER_SPIKE_RUN must match floe-provider-YYYYMMDDTHHMMSSZ")
    if not env["FLOE_AWS_TEST_PREFIX"].endswith("/"):
        pytest.fail("FLOE_AWS_TEST_PREFIX must end with /")
    if not env["FLOE_AWS_GLUE_DATABASE_PREFIX"].endswith("_"):
        pytest.fail("FLOE_AWS_GLUE_DATABASE_PREFIX must end with _")
    return env


def _run_database_name(env: Mapping[str, str]) -> str:
    return (
        f"{env['FLOE_AWS_GLUE_DATABASE_PREFIX']}{env['FLOE_PROVIDER_SPIKE_RUN'].replace('-', '_')}"
    )


def _assert_secret_values_are_not_embedded(payload: str) -> None:
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        value = os.environ.get(name)
        if value:
            assert value not in payload


def test_live_aws_s3_glue_runtime_composition_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate the real AWS S3 and Glue path through resolved deployment bindings."""
    env = _require_live_aws_env()
    region = env["FLOE_AWS_REGION"]
    bucket = env["FLOE_AWS_TEST_BUCKET"]
    run_id = env["FLOE_PROVIDER_SPIKE_RUN"]
    run_prefix = f"{env['FLOE_AWS_TEST_PREFIX']}{run_id}/"
    requested_namespace = _run_database_name(env)
    # AWS Glue stores database names in lowercase even when callers provide
    # mixed-case run identifiers, so follow its canonical catalog shape after
    # proving create_namespace accepts the requested Floe cleanup target.
    catalog_namespace = requested_namespace.lower()
    table_identifier = f"{catalog_namespace}.provider_validation"
    table_location = f"s3://{bucket}/{run_prefix}warehouse/provider_validation"
    object_location = f"s3://{bucket}/{run_prefix}artifacts/provider-validation.txt"

    monkeypatch.setenv("AWS_REGION", region)
    monkeypatch.setenv("AWS_DEFAULT_REGION", region)

    storage_plugin = AwsS3ObjectStorePlugin(
        AwsS3ObjectStoreConfig(
            bucket=bucket,
            warehouse_prefix=f"{run_prefix}warehouse/",
            artifact_prefix=f"{run_prefix}artifacts/",
            region=region,
            credential_mode="environment",
        )
    )
    storage_binding = storage_plugin.get_deployment_binding()

    catalog_plugin = GlueCatalogPlugin(
        GlueCatalogConfig(
            region=region,
            warehouse=storage_binding.warehouse.uri,
            database_prefix=env["FLOE_AWS_GLUE_DATABASE_PREFIX"],
            credential_mode="environment",
        )
    )
    catalog_binding = catalog_plugin.build_catalog_deployment(storage_binding)
    runtime_connection = build_runtime_catalog_connection(
        storage=storage_binding,
        catalog=catalog_binding,
    )
    pyiceberg_config = runtime_catalog_connection_to_pyiceberg_config(runtime_connection)

    assert pyiceberg_config["type"] == "glue"
    assert pyiceberg_config["warehouse"] == storage_binding.warehouse.uri
    assert pyiceberg_config["glue.region"] == region
    assert pyiceberg_config["s3.region"] == region
    assert storage_binding.credentials.mode == "environment"
    assert catalog_binding.glue is not None
    assert catalog_binding.glue.credential_refs["accessKeyId"].source == "environment"

    _assert_secret_values_are_not_embedded(storage_binding.model_dump_json())
    _assert_secret_values_are_not_embedded(catalog_binding.model_dump_json())
    _assert_secret_values_are_not_embedded(runtime_connection.model_dump_json())
    _assert_secret_values_are_not_embedded(repr(pyiceberg_config))

    fileio = storage_plugin.get_pyiceberg_fileio()
    expected_payload = f"floe live provider validation: {run_id}\n".encode()
    with fileio.new_output(object_location).create(overwrite=True) as output:
        output.write(expected_payload)
    with fileio.new_input(object_location).open() as input_file:
        assert input_file.read() == expected_payload

    catalog_plugin.connect(pyiceberg_config)
    try:
        try:
            catalog_plugin.create_namespace(requested_namespace, {"floe.provider.test.run": run_id})
        except NamespaceAlreadyExistsError:
            catalog_plugin.delete_namespace(catalog_namespace)
            catalog_plugin.create_namespace(requested_namespace, {"floe.provider.test.run": run_id})

        assert catalog_namespace in catalog_plugin.list_namespaces()

        schema = Schema(NestedField(1, "run_id", StringType(), required=True))
        catalog_plugin.create_table(
            table_identifier,
            schema,  # type: ignore[arg-type]
            location=table_location,
            properties={"floe.provider.test.run": run_id},
        )
        assert table_identifier in catalog_plugin.list_tables(catalog_namespace)
    finally:
        try:
            catalog_plugin.drop_table(table_identifier, purge=True)
        except Exception:  # noqa: BLE001
            LOGGER.warning("Best-effort AWS Glue table cleanup failed", exc_info=True)
        try:
            catalog_plugin.delete_namespace(catalog_namespace)
        except NoSuchNamespaceError:
            pass

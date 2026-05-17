"""Focused runtime observability tests for Polaris catalog operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from floe_core.plugin_metadata import HealthState
from floe_core.schemas.compiled_artifacts import (
    DagsterStorageBinding,
    DbtStorageBinding,
    KubernetesSecretRef,
    StorageCapabilities,
    StorageCredentialBinding,
    StorageDeploymentBinding,
    StorageProvisioningIntent,
    StorageRuntimeBinding,
    StorageServiceEndpoint,
    StorageWarehouse,
)
from pydantic import SecretStr

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin, _safe_endpoint_identity
from floe_catalog_polaris.tracing import _sanitize_uri


def _plugin_with_secret_url() -> PolarisCatalogPlugin:
    return PolarisCatalogPlugin(
        config=PolarisCatalogConfig(
            uri="https://user:" + "super-secret@polaris.example.com/api/catalog",
            warehouse="floe",
            oauth2=OAuth2Config(
                client_id="polaris",
                client_secret=SecretStr("oauth-secret"),
                token_url="https://auth.example.com/oauth/token",
            ),
            max_retries=0,
        )
    )


def _storage_binding() -> StorageDeploymentBinding:
    return StorageDeploymentBinding(
        provider="minio",
        endpoint=StorageServiceEndpoint(
            internal_url="http://minio:9000",
            external_url="http://localhost:9000",
            region="us-east-1",
            warehouse_path="s3://floe-warehouse",
            path_style_access=True,
        ),
        warehouse=StorageWarehouse(uri="s3://floe-warehouse", bucket="floe-warehouse"),
        allowed_locations=["s3://floe-warehouse"],
        credentials=StorageCredentialBinding(
            mode="kubernetes-secret",
            secret_ref=KubernetesSecretRef(
                name="minio-credentials",
                namespace="floe-system",
                keys={
                    "accessKeyId": "access-key-id",
                    "secretAccessKey": "secret-access-key",  # pragma: allowlist secret
                },
            ),
        ),
        capabilities=StorageCapabilities(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
            sts_supported=False,
            path_style_access=True,
        ),
        provisioning=StorageProvisioningIntent(
            enabled=True,
            mode="helm-job",
            default_create_policy="create-if-missing",
        ),
        runtime=StorageRuntimeBinding(
            pyiceberg_properties={},
            dbt_profile_fragment={},
            dagster_resources={},
            env_refs={},
        ),
        dbt=DbtStorageBinding(
            profile_name="floe",
            target_name="dev",
            schema_name="analytics",
            profile_fragment={},
            env_refs={},
        ),
        dagster=DagsterStorageBinding(
            resource_key="minio_storage",
            asset_io_manager_key="iceberg_io_manager",
            resources={},
            env_refs={},
        ),
    )


def test_connect_emits_sanitized_endpoint_identity() -> None:
    """connect() spans and logs do not emit credential-bearing endpoint URLs."""
    plugin = _plugin_with_secret_url()
    mock_tracer = MagicMock()
    mock_catalog = MagicMock()

    with (
        patch("floe_catalog_polaris.plugin.get_tracer", return_value=mock_tracer),
        patch("floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog),
        patch("floe_catalog_polaris.plugin.logger") as mock_logger,
    ):
        plugin.connect({})

    attrs = mock_tracer.start_as_current_span.call_args.kwargs["attributes"]
    assert attrs["catalog.uri"] == "https://polaris.example.com"
    assert attrs["catalog.name"] == "polaris"
    assert attrs["catalog.warehouse"] == "floe"
    assert "super-secret" not in str(attrs)
    assert "oauth-secret" not in str(mock_logger.method_calls)


def test_endpoint_identity_strips_userinfo_query_and_fragment() -> None:
    """Endpoint identity used by telemetry never includes presigned query material."""
    uri = (
        "https://user:"
        "super-secret@polaris.example.com:8181/api/catalog"
        "?X-Amz-Signature=credential-signature&token=super-token#frag"
    )

    assert _safe_endpoint_identity(uri) == "https://polaris.example.com:8181"
    assert _sanitize_uri(uri) == "https://polaris.example.com:8181"
    assert "super-secret" not in _safe_endpoint_identity(uri)
    assert "X-Amz-Signature" not in _sanitize_uri(uri)


def test_connect_failure_logs_sanitized_error_message() -> None:
    """connect() failure logs sanitize exception messages before recording them."""
    plugin = _plugin_with_secret_url()

    with (
        patch(
            "floe_catalog_polaris.plugin.load_catalog",
            side_effect=RuntimeError("failed password=super-secret token=super-token"),
        ),
        patch("floe_catalog_polaris.plugin.logger") as mock_logger,
    ):
        with patch("floe_catalog_polaris.plugin.get_tracer"):
            try:
                plugin.connect({})
            except RuntimeError:
                pass

    log_kwargs = mock_logger.bind.return_value.error.call_args.kwargs
    assert log_kwargs["error_type"] == "RuntimeError"
    assert log_kwargs["error_message"] == "failed password=<REDACTED> token=<REDACTED>"
    assert "super-secret" not in str(mock_logger.method_calls)
    assert "super-token" not in str(mock_logger.method_calls)


def test_build_catalog_deployment_emits_secret_free_storage_context() -> None:
    """Deployment binding generation records only logical storage identity."""
    plugin = _plugin_with_secret_url()
    mock_tracer = MagicMock()

    with patch("floe_catalog_polaris.plugin.get_tracer", return_value=mock_tracer):
        binding = plugin.build_catalog_deployment(_storage_binding())

    attrs = mock_tracer.start_as_current_span.call_args.kwargs["attributes"]
    assert binding.provider == "polaris"
    assert attrs["catalog.operation"] == "build_catalog_deployment"
    assert attrs["catalog.uri"] == "https://polaris.example.com"
    assert attrs["storage.provider"] == "minio"
    assert attrs["storage.protocol"] == "s3-compatible"
    assert attrs["storage.bucket"] == "floe-warehouse"
    assert "super-secret" not in str(attrs)
    assert "secret-access-key" not in str(attrs)


def test_health_check_emits_status_for_unconnected_plugin() -> None:
    """health_check() emits health status even before a catalog connection exists."""
    plugin = _plugin_with_secret_url()
    mock_tracer = MagicMock()

    with patch("floe_catalog_polaris.plugin.get_tracer", return_value=mock_tracer):
        status = plugin.health_check()

    assert status.state == HealthState.UNHEALTHY
    span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
    span.set_attribute.assert_any_call("health.status", "unhealthy")
    attrs = mock_tracer.start_as_current_span.call_args.kwargs["attributes"]
    assert attrs["catalog.uri"] == "https://polaris.example.com"
    assert "super-secret" not in str(attrs)

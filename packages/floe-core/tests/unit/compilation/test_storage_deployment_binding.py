"""Compilation tests for storage deployment bindings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from floe_core.compilation.errors import CompilationException
from floe_core.compilation.stages import CompilationStage, compile_pipeline
from floe_core.plugin_errors import PluginConfigurationError
from floe_core.plugins.storage import FileIO, StoragePlugin

ROOT = Path(__file__).resolve().parents[5]


def test_demo_compile_emits_minio_storage_deployment_binding() -> None:
    """Demo compilation must attach the MinIO deployment storage binding."""
    artifacts = compile_pipeline(
        ROOT / "demo" / "customer-360" / "floe.yaml",
        ROOT / "demo" / "manifest.yaml",
        emit_lineage=False,
    )

    assert artifacts.plugins is not None
    assert artifacts.plugins.storage is not None
    assert artifacts.plugins.storage.type == "minio"
    assert artifacts.deployment is not None
    assert artifacts.deployment.storage is not None

    storage = artifacts.deployment.storage
    payload = storage.model_dump_json()

    assert storage.provider == "minio"
    assert storage.endpoint.internal_url == "http://floe-platform-minio:9000"
    assert storage.endpoint.warehouse_path == "s3://floe-iceberg"
    assert storage.credentials.mode == "kubernetes-secret"
    assert storage.credentials.secret_ref is not None
    assert storage.credentials.secret_ref.name == "floe-platform-minio-credentials"
    assert storage.dbt.profile_fragment["s3_endpoint"] == "http://floe-platform-minio:9000"
    assert storage.dagster.resources["endpoint_url"] == "http://floe-platform-minio:9000"
    assert artifacts.dbt_profiles is not None
    dev_profile = artifacts.dbt_profiles["customer-360"]["outputs"]["dev"]
    assert dev_profile["s3_endpoint"] == "http://floe-platform-minio:9000"
    assert dev_profile["s3_region"] == "us-east-1"
    assert dev_profile["s3_access_key_id"] == "{{ env_var('AWS_ACCESS_KEY_ID') }}"
    assert "minioadmin" not in payload


def test_storage_binding_compile_uses_isolated_plugin_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Storage binding compilation must not mutate the global plugin registry."""
    import floe_core.plugin_registry as plugin_registry

    def fail_global_registry() -> None:
        raise AssertionError("compile must use an isolated storage plugin registry")

    monkeypatch.setattr(plugin_registry, "get_registry", fail_global_registry)

    artifacts = compile_pipeline(
        ROOT / "demo" / "customer-360" / "floe.yaml",
        ROOT / "demo" / "manifest.yaml",
        emit_lineage=False,
    )

    assert artifacts.deployment is not None
    assert artifacts.deployment.storage is not None
    assert artifacts.deployment.storage.provider == "minio"


def test_missing_storage_plugin_raises_structured_compilation_error(tmp_path: Path) -> None:
    """Storage plugin resolution failures must use the compilation error model."""
    manifest_path = tmp_path / "manifest.yaml"
    manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["plugins"]["storage"]["type"] = "missing-storage"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            manifest_path,
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "E201"
    assert "missing-storage" in error.message
    assert error.context == {"storage_plugin": "missing-storage"}


def test_storage_plugin_binding_failure_raises_structured_compilation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-resolution StoragePlugin failures must use the compilation error model."""

    class FailingStoragePlugin(StoragePlugin):
        @property
        def name(self) -> str:
            return "minio"

        @property
        def version(self) -> str:
            return "0.1.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"

        def get_config_schema(self) -> None:
            return None

        def get_pyiceberg_fileio(self) -> FileIO:
            raise NotImplementedError

        def get_warehouse_uri(self, namespace: str) -> str:
            return f"s3://unused/{namespace}"

        def get_dbt_profile_config(self) -> dict[str, Any]:
            return {}

        def get_dagster_io_manager_config(self) -> dict[str, Any]:
            return {}

        def get_helm_values_override(self) -> dict[str, Any]:
            return {}

        def get_deployment_binding(self) -> Any:
            raise PluginConfigurationError(
                "minio",
                [{"field": "endpoint", "message": "post-resolution failure"}],
            )

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class IsolatedFailingRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> FailingStoragePlugin:
            return FailingStoragePlugin()

    monkeypatch.setattr(plugin_registry, "PluginRegistry", IsolatedFailingRegistry)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "E201"
    assert "could not build deployment binding" in error.message
    assert error.context == {"storage_plugin": "minio"}
